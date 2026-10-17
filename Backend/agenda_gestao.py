"""Salon-scoped schedule management; individual prices and immutable booking totals."""
from responses import mensagem_json
from datetime import date, datetime, time, timedelta
from flask import jsonify, request, g
from application import app, conectar_banco
from funcoes import decodificar_token
from agenda_equipe import dinheiro, percentual, funcionario_logado
from auditoria import registrar_log

DIAS = ('segunda','terca','quarta','quinta','sexta','sabado','domingo')


class GestaoErro(ValueError):
    def __init__(self, texto, status=400):
        super().__init__(texto); self.status = status


def escopo(cursor, usuario, escrita=False, permitir_barbeiro=False):
    if not usuario: raise GestaoErro('Faça login.',401)
    tipo = int(usuario.get('tipo',-1)); pedido = request.args.get('id_barbearia')
    if tipo == 0:
        try: salon = int(pedido or 0)
        except ValueError: raise GestaoErro('Barbearia inválida.')
        if not salon: raise GestaoErro('Selecione a barbearia.')
    elif tipo == 2:
        salon = int(usuario['id_usuario'])
        if pedido and int(pedido) != salon: raise GestaoErro('Sem permissão para esta barbearia.',403)
    elif tipo == 3 and permitir_barbeiro:
        fun = funcionario_logado(cursor,usuario)
        if not fun: raise GestaoErro('Profissional inativo.',403)
        salon = fun[1]
        if pedido and int(pedido) != salon: raise GestaoErro('Sem permissão.',403)
    else: raise GestaoErro('Sem permissão.',403)
    cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1' + (' WITH LOCK' if escrita else ''),(salon,))
    if not cursor.fetchone(): raise GestaoErro('Barbearia indisponível.',404)
    return salon


def config_agenda(cursor,salon):
    cursor.execute('SELECT CANCELAMENTO_HORAS,REAGENDAMENTO_HORAS,LEMBRETE_HORAS FROM AGENDA_CONFIG WHERE ID_BARBEARIA=?',(salon,))
    row=cursor.fetchone() or (0,0,24)
    return dict(zip(('cancelamento_horas','reagendamento_horas','lembrete_horas'),row))


def validar_prazo(cursor,usuario,linha,acao):
    if int(usuario.get('tipo',-1)) != 1: return
    horas=config_agenda(cursor,linha[2])[acao+'_horas']
    if linha[4] <= datetime.now()+timedelta(hours=horas):
        raise ValueError(f'Este salão exige antecedência de {horas} horas para {acao}. Entre em contato com a barbearia.')


def intervalos_profissional(cursor,salon,dia,funcionario=None):
    from visagismo import intervalos_do_dia, dias_semana_do_funcionario
    salon_intervals=intervalos_do_dia(cursor,salon,dia)
    if not funcionario: return salon_intervals
    cursor.execute('SELECT HORARIOS_CONFIGURADOS FROM FUNCIONARIO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=?',(funcionario,salon))
    row=cursor.fetchone()
    if not row: return []
    if not row[0]:
        return salon_intervals if DIAS[dia.weekday()] in dias_semana_do_funcionario(cursor,funcionario) else []
    cursor.execute('SELECT INICIO,FIM FROM FUNCIONARIO_HORARIO WHERE ID_FUNCIONARIO=? AND DIA=? ORDER BY INICIO',(funcionario,DIAS[dia.weekday()]))
    rows=cursor.fetchall(); result=[]
    for ini,end in rows:
        a,b=datetime.combine(dia,ini),datetime.combine(dia,end)
        for c,d in salon_intervals:
            if max(a,c)<min(b,d): result.append((max(a,c),min(b,d)))
    return result


def bloqueios_intervalo(cursor,salon,funcionario,inicio,fim):
    cursor.execute('''SELECT INICIO_EM,FIM_EM FROM AGENDA_BLOQUEIO WHERE ID_BARBEARIA=?
        AND INICIO_EM<? AND FIM_EM>? AND (CAST(? AS INTEGER) IS NULL OR ID_FUNCIONARIO IS NULL OR ID_FUNCIONARIO=?)''',
        (salon,fim,inicio,funcionario,funcionario))
    return cursor.fetchall()


def validar_expediente(cursor,salon,funcionario,inicio,fim):
    if not any(inicio>=a and fim<=b for a,b in intervalos_profissional(cursor,salon,inicio.date(),funcionario)):
        raise ValueError('O horário está fora do expediente do profissional ou não comporta todos os serviços.')
    if bloqueios_intervalo(cursor,salon,funcionario,inicio,fim):
        raise ValueError('Este horário está bloqueado por folga, feriado ou intervalo.')


def precos_servicos(cursor,servicos,funcionario=None):
    ids=[s['id_servico'] for s in servicos]
    if not ids: return []
    marks=','.join('?' for _ in ids)
    cursor.execute(f'SELECT ID_SERVICO,PRECO FROM SERVICO WHERE ID_SERVICO IN ({marks})',ids)
    prices={r[0]:dinheiro(r[1]) for r in cursor.fetchall()}
    if funcionario:
        cursor.execute(f'SELECT ID_SERVICO,PRECO FROM FUNCIONARIO_PRECO WHERE ID_FUNCIONARIO=? AND ID_SERVICO IN ({marks})',[funcionario,*ids])
        prices.update({r[0]:dinheiro(r[1]) for r in cursor.fetchall()})
    return [{**s,'preco':float(prices[s['id_servico']])} for s in servicos]


def _horario(value):
    try: return datetime.strptime(str(value),'%H:%M').time()
    except ValueError: raise GestaoErro('Horário inválido. Use HH:MM.')


def validar_turnos(horarios):
    if not isinstance(horarios,list) or len(horarios)>28: raise GestaoErro('Informe até 28 turnos semanais.')
    result=[]
    for item in horarios:
        if not isinstance(item,dict) or item.get('dia') not in DIAS: raise GestaoErro('Dia da semana inválido.')
        a,b=_horario(item.get('inicio')),_horario(item.get('fim'))
        if a>=b: raise GestaoErro('O fim do turno deve ser posterior ao início.')
        if any(dia==item['dia'] and a<end and b>start for dia,start,end in result): raise GestaoErro('Turnos não podem se sobrepor.')
        result.append((item['dia'],a,b))
    return result


def obter_config_profissional(cursor,salon,id_fun):
    cursor.execute('''SELECT NOME,ATIVO,COMISSAO_TIPO,COMISSAO_VALOR,COMISSAO_PERCENTUAL,HORARIOS_CONFIGURADOS
        FROM FUNCIONARIO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=?''',(id_fun,salon))
    fun=cursor.fetchone()
    if not fun: raise GestaoErro('Profissional não encontrado.',404)
    cursor.execute('SELECT DIA,INICIO,FIM FROM FUNCIONARIO_HORARIO WHERE ID_FUNCIONARIO=? ORDER BY DIA,INICIO',(id_fun,))
    horarios=[{'dia':r[0],'inicio':r[1].strftime('%H:%M'),'fim':r[2].strftime('%H:%M')} for r in cursor.fetchall()]
    if not fun[5]:
        from visagismo import dias_semana_do_funcionario
        dias=dias_semana_do_funcionario(cursor,id_fun)
        cursor.execute('SELECT DIAS,ENTRADA_MANHA,SAIDA_MANHA,ENTRADA_TARDE,SAIDA_TARDE FROM DIAS_DE_SERVICO WHERE ID_USUARIO=?',(salon,))
        for r in cursor.fetchall():
            if r[0] in dias:
                for a,b in ((r[1],r[2]),(r[3],r[4])):
                    if a and b: horarios.append({'dia':r[0],'inicio':a.strftime('%H:%M'),'fim':b.strftime('%H:%M')})
    cursor.execute('SELECT ID_SERVICO,PRECO FROM FUNCIONARIO_PRECO WHERE ID_FUNCIONARIO=?',(id_fun,))
    precos=[{'id_servico':r[0],'preco':float(r[1])} for r in cursor.fetchall()]
    cursor.execute('SELECT P.ID_SERVICO FROM SERVICO_POR_FUNCIONARIO P JOIN SERVICO S ON S.ID_SERVICO=P.ID_SERVICO WHERE P.ID_FUNCIONARIO=? AND S.ID_USUARIO=?',(id_fun,salon))
    vinculados=[r[0] for r in cursor.fetchall()]
    precos=[r for r in precos if r['id_servico'] in vinculados]
    return {'id_funcionario':id_fun,'nome':fun[0],'ativo':bool(fun[1]),'comissao_tipo':fun[2],
        'comissao_valor':float(fun[3] if fun[2]=='fixa' else fun[4]),'horarios':horarios,'precos':precos,'ids_servicos_vinculados':vinculados}


def _executar(handler,escrita=False,permitir_barbeiro=False):
    usuario=decodificar_token()
    if not usuario: return mensagem_json('Faça login.', 'erro'),401
    con=conectar_banco(); cur=con.cursor()
    try:
        g.agenda_auditoria=[]
        salon=escopo(cur,usuario,escrita,permitir_barbeiro)
        result=handler(cur,salon,usuario)
        if escrita:
            con.commit()
            for args,kwargs in g.agenda_auditoria: registrar_log(*args,**kwargs)
        return jsonify(result)
    except (ValueError,TypeError,KeyError) as exc:
        con.rollback(); return mensagem_json(str(exc), 'erro'),getattr(exc,'status',400)
    finally: cur.close();con.close()


def _auditar(*args,**kwargs):
    g.agenda_auditoria.append((args,kwargs))


@app.route('/gestao/agenda/config',methods=['GET','PUT'])
def agenda_config():
    def handler(cur,salon,usuario):
        if request.method=='PUT':
            antes=config_agenda(cur,salon)
            data=request.get_json(silent=True) or {}; values=[]
            for key in ('cancelamento_horas','reagendamento_horas','lembrete_horas'):
                value=data.get(key)
                if isinstance(value,bool) or not isinstance(value,int) or not 0<=value<=720: raise GestaoErro('Informe horas inteiras entre 0 e 720.')
                values.append(value)
            cur.execute('UPDATE OR INSERT INTO AGENDA_CONFIG (ID_BARBEARIA,CANCELAMENTO_HORAS,REAGENDAMENTO_HORAS,LEMBRETE_HORAS) VALUES(?,?,?,?) MATCHING(ID_BARBEARIA)',(salon,*values))
            cur.execute("UPDATE EMAIL_OUTBOX SET ESTADO='cancelado' WHERE ID_AGENDAMENTO IN (SELECT ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_BARBEARIA=?) AND EVENTO='lembrete' AND ESTADO='pendente'",(salon,))
            _auditar('UPDATE','AGENDA_CONFIG',id_registro=salon,id_usuario=usuario['id_usuario'],dados_antes=antes,dados_depois=config_agenda(cur,salon))
        return {'id_barbearia':salon,**config_agenda(cur,salon)}
    return _executar(handler,request.method=='PUT')


@app.route('/gestao/profissionais/<int:id_fun>/config',methods=['GET','PUT'])
def profissional_config(id_fun):
    def handler(cur,salon,usuario):
        antes=obter_config_profissional(cur,salon,id_fun)
        if request.method=='PUT':
            dados=request.get_json(silent=True) or {}; tipo=dados.get('comissao_tipo','percentual')
            if tipo not in ('percentual','fixa'): raise GestaoErro('Tipo de comissão inválido.')
            valor=percentual(dados.get('comissao_valor',0)) if tipo=='percentual' else dinheiro(dados.get('comissao_valor',0))
            if valor<0 or valor>1000000: raise GestaoErro('Comissão inválida.')
            turnos=validar_turnos(dados.get('horarios',[])); precos=dados.get('precos',[])
            if not isinstance(precos,list): raise GestaoErro('Preços inválidos.')
            valid=[];seen=set()
            for item in precos:
                id_service=int(item['id_servico']); price=dinheiro(item['preco'])
                if id_service in seen or price<0 or price>1000000: raise GestaoErro('Preço inválido ou serviço duplicado.')
                cur.execute('SELECT S.ID_SERVICO FROM SERVICO S JOIN SERVICO_POR_FUNCIONARIO P ON P.ID_SERVICO=S.ID_SERVICO WHERE S.ID_SERVICO=? AND S.ID_USUARIO=? AND P.ID_FUNCIONARIO=?',(id_service,salon,id_fun))
                if not cur.fetchone(): raise GestaoErro('O profissional não está vinculado a este serviço.')
                seen.add(id_service); valid.append((id_fun,id_service,price))
            # Every persisted future booking remains possible under the new shifts.
            cur.execute("SELECT INICIO_EM,FIM_EM FROM AGENDAMENTO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=? AND STATUS IN ('agendado','confirmado') AND FIM_EM>CURRENT_TIMESTAMP",(id_fun,salon))
            for a,b in cur.fetchall():
                if not any(d==DIAS[a.weekday()] and a.time()>=x and b.date()==a.date() and b.time()<=y for d,x,y in turnos):
                    raise GestaoErro('Há agendamentos futuros fora dos turnos propostos. Remarque ou cancele antes de alterar.',409)
            cur.execute('DELETE FROM FUNCIONARIO_HORARIO WHERE ID_FUNCIONARIO=?',(id_fun,))
            for d,a,b in turnos: cur.execute('INSERT INTO FUNCIONARIO_HORARIO VALUES(NEXT VALUE FOR SEQ_FUNCIONARIO_HORARIO,?,?,?,?)',(id_fun,d,a,b))
            cur.execute('DELETE FROM FUNCIONARIO_PRECO WHERE ID_FUNCIONARIO=?',(id_fun,))
            for p in valid: cur.execute('INSERT INTO FUNCIONARIO_PRECO VALUES(?,?,?)',p)
            cur.execute('UPDATE FUNCIONARIO SET COMISSAO_TIPO=?,COMISSAO_VALOR=?,COMISSAO_PERCENTUAL=?,HORARIOS_CONFIGURADOS=1 WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=?',(tipo,valor,valor if tipo=='percentual' else 0,id_fun,salon))
            _auditar('UPDATE','FUNCIONARIO',id_registro=id_fun,id_usuario=usuario['id_usuario'],dados_antes=antes,dados_depois=obter_config_profissional(cur,salon,id_fun))
        return obter_config_profissional(cur,salon,id_fun)
    return _executar(handler,request.method=='PUT')


@app.route('/gestao/agenda/bloqueios',methods=['GET','POST'])
def agenda_bloqueios():
    def handler(cur,salon,usuario):
        if request.method=='POST':
            data=request.get_json(silent=True) or {}; fun=int(data['id_funcionario']) if data.get('id_funcionario') else None
            if fun: obter_config_profissional(cur,salon,fun)
            a,b=datetime.fromisoformat(data['inicio_em']),datetime.fromisoformat(data['fim_em'])
            motivo=str(data.get('motivo') or '').strip()
            if a.tzinfo or b.tzinfo or a>=b or not motivo or len(motivo)>200: raise GestaoErro('Informe intervalo e motivo válidos, em horário local.')
            cur.execute("SELECT FIRST 1 ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_BARBEARIA=? AND STATUS IN ('agendado','confirmado') AND INICIO_EM<? AND FIM_EM>? AND (CAST(? AS INTEGER) IS NULL OR ID_FUNCIONARIO=? OR ID_FUNCIONARIO IS NULL)",(salon,b,a,fun,fun))
            if cur.fetchone(): raise GestaoErro('Há agendamentos neste intervalo. Remarque ou cancele antes de bloquear.',409)
            cur.execute('INSERT INTO AGENDA_BLOQUEIO VALUES(NEXT VALUE FOR SEQ_AGENDA_BLOQUEIO,?,?,?,?,?) RETURNING ID_BLOQUEIO',(salon,fun,a,b,motivo)); id_block=cur.fetchone()[0]
            _auditar('INSERT','AGENDA_BLOQUEIO',id_registro=id_block,id_usuario=usuario['id_usuario'],dados_depois={'id_barbearia':salon,'id_funcionario':fun,'inicio_em':a,'fim_em':b,'motivo':motivo})
        cur.execute('SELECT ID_BLOQUEIO,ID_FUNCIONARIO,INICIO_EM,FIM_EM,MOTIVO FROM AGENDA_BLOQUEIO WHERE ID_BARBEARIA=? ORDER BY INICIO_EM',(salon,))
        return {'bloqueios':[{'id_bloqueio':r[0],'id_funcionario':r[1],'inicio_em':r[2].isoformat(),'fim_em':r[3].isoformat(),'motivo':r[4]} for r in cur.fetchall()]}
    return _executar(handler,request.method=='POST')


@app.delete('/gestao/agenda/bloqueios/<int:id_block>')
def excluir_bloqueio(id_block):
    def handler(cur,salon,usuario):
        cur.execute('SELECT ID_BLOQUEIO,ID_FUNCIONARIO,INICIO_EM,FIM_EM,MOTIVO FROM AGENDA_BLOQUEIO WHERE ID_BLOQUEIO=? AND ID_BARBEARIA=?',(id_block,salon))
        row=cur.fetchone()
        if not row: raise GestaoErro('Bloqueio não encontrado.',404)
        cur.execute('DELETE FROM AGENDA_BLOQUEIO WHERE ID_BLOQUEIO=? AND ID_BARBEARIA=?',(id_block,salon))
        _auditar('DELETE','AGENDA_BLOQUEIO',id_registro=id_block,id_usuario=usuario['id_usuario'],dados_antes=dict(zip(('id_bloqueio','id_funcionario','inicio_em','fim_em','motivo'),row)))
        return {'mensagem':{'informacao':'Bloqueio removido.','tipo':'sucesso'}}
    return _executar(handler,True)


@app.put('/gestao/servicos/<int:id_service>/ativo')
def ativar_servico(id_service):
    def handler(cur,salon,usuario):
        ativo=(request.get_json(silent=True) or {}).get('ativo')
        if not isinstance(ativo,bool): raise GestaoErro('Informe ativo verdadeiro ou falso.')
        cur.execute('SELECT ATIVO FROM SERVICO WHERE ID_SERVICO=? AND ID_USUARIO=?',(id_service,salon))
        row=cur.fetchone()
        if not row: raise GestaoErro('Serviço não encontrado.',404)
        cur.execute('UPDATE SERVICO SET ATIVO=? WHERE ID_SERVICO=? AND ID_USUARIO=?',(int(ativo),id_service,salon))
        _auditar('UPDATE','SERVICO',id_registro=id_service,id_usuario=usuario['id_usuario'],campo='ATIVO',valor_antes=int(row[0]),valor_depois=int(ativo))
        return {'id_servico':id_service,'ativo':ativo}
    return _executar(handler,True)


@app.route('/gestao/agenda',methods=['GET','POST'])
def agenda():
    if request.method=='POST':
        # Reuses the exact lock, validation and snapshot path used by client bookings.
        from visagismo import criar_agendamento
        return criar_agendamento()
    def handler(cur,salon,usuario):
        from visagismo import parse_data,COLUNAS_AGENDAMENTO,serializar_agendamento
        a=parse_data(request.args.get('inicio',date.today().isoformat()));b=parse_data(request.args.get('fim',a.isoformat()))
        if b<a or (b-a).days>366: raise GestaoErro('Informe período de até 366 dias.')
        staff=funcionario_logado(cur,usuario) if int(usuario['tipo'])==3 else None
        query=f'SELECT {COLUNAS_AGENDAMENTO} FROM AGENDAMENTO WHERE ID_BARBEARIA=? AND INICIO_EM>=? AND INICIO_EM<?'
        params=[salon,datetime.combine(a,time.min),datetime.combine(b+timedelta(days=1),time.min)]
        if staff: query+=' AND ID_FUNCIONARIO=?';params.append(staff[0])
        cur.execute(query+' ORDER BY INICIO_EM',params);bookings=cur.fetchall()
        ags=[serializar_agendamento(cur,row,usuario) for row in bookings]
        cur.execute('SELECT ID_FUNCIONARIO,NOME,ATIVO FROM FUNCIONARIO WHERE ID_BARBEARIA=?'+(' AND ID_FUNCIONARIO=?' if staff else '')+' ORDER BY NOME',[salon,staff[0]] if staff else [salon])
        funcs=[{'id_funcionario':r[0],'nome':r[1],'ativo':bool(r[2])} for r in cur.fetchall()]
        for profissional in funcs:
            cur.execute('''SELECT P.ID_SERVICO FROM SERVICO_POR_FUNCIONARIO P
                JOIN SERVICO S ON S.ID_SERVICO=P.ID_SERVICO
                WHERE P.ID_FUNCIONARIO=? AND S.ID_USUARIO=? ORDER BY P.ID_SERVICO''',
                (profissional['id_funcionario'],salon))
            vinculados=[r[0] for r in cur.fetchall()]
            profissional['servicos']=vinculados
            profissional['ids_servicos']=vinculados
        cur.execute('SELECT ID_SERVICO,NOME_SERVICO,PRECO,DURACAO,ATIVO FROM SERVICO WHERE ID_USUARIO=? ORDER BY NOME_SERVICO',(salon,))
        services=[{'id_servico':r[0],'nome':r[1],'preco':float(r[2]),'duracao':r[3],'ativo':bool(r[4])} for r in cur.fetchall()]
        if staff:
            from visagismo import servicos_do_funcionario
            allowed=servicos_do_funcionario(cur,salon,staff[0]);services=[s for s in services if s['id_servico'] in allowed]
        # No global client directory: only customers who used this salon; explicit
        # registration lookup below may locate a new client by exact email/phone.
        query_clients='''SELECT DISTINCT U.ID_USUARIO,U.NOME,U.EMAIL,U.TELEFONE FROM USUARIO U
            JOIN AGENDAMENTO A ON A.ID_USUARIO=U.ID_USUARIO WHERE A.ID_BARBEARIA=? AND U.TIPO=1'''
        if staff: query_clients+=' AND A.ID_FUNCIONARIO=?'
        cur.execute(query_clients+' ORDER BY U.NOME',[salon,staff[0]] if staff else [salon])
        clients=[{'id_usuario':r[0],'nome':r[1],'email':r[2],'telefone':r[3]} for r in cur.fetchall()]
        return {'agendamentos':ags,'funcionarios':funcs,'servicos':services,'clientes':clients,'id_barbearia':salon}
    return _executar(handler,permitir_barbeiro=True)


@app.get('/gestao/agenda/cliente')
def buscar_cliente_reserva():
    def handler(cur,salon,usuario):
        email=str(request.args.get('email','')).strip().lower()
        if not email or '@' not in email: raise GestaoErro('Informe o e-mail exato do cliente.')
        cur.execute('SELECT ID_USUARIO,NOME,EMAIL,TELEFONE FROM USUARIO WHERE LOWER(EMAIL)=? AND TIPO=1 AND ATIVO=1',(email,))
        row=cur.fetchone()
        if not row: raise GestaoErro('Cliente não cadastrado.',404)
        return {'cliente':{'id_usuario':row[0],'nome':row[1],'email':row[2],'telefone':row[3]}}
    return _executar(handler,permitir_barbeiro=True)


def enfileirar_evento(cursor,linha,evento,versao=None):
    """Same-transaction outbox; event key prevents retries creating duplicates."""
    if evento not in ('confirmacao','cancelamento','reagendamento','lembrete'): raise ValueError('Evento inválido.')
    inicio=linha[4]; salon=linha[2]
    key=f'ag:{linha[0]}:{evento}:'+str(versao or inicio.isoformat())
    if evento=='lembrete':
        horas=config_agenda(cursor,salon)['lembrete_horas']
        if not horas or inicio<=datetime.now(): return
        key+=':'+str(horas);quando=max(datetime.now(),inicio-timedelta(hours=horas))
    else: quando=datetime.now()
    titulos={'confirmacao':'Agendamento confirmado','cancelamento':'Agendamento cancelado','reagendamento':'Agendamento reagendado','lembrete':'Lembrete de agendamento'}
    text=f"{titulos[evento]}: atendimento #{linha[0]} em {inicio.strftime('%d/%m/%Y às %H:%M')}."
    destinatarios=[('cliente',linha[1])]
    if evento!='lembrete': destinatarios.append(('salao',salon))
    for papel,id_usuario in destinatarios:
        chave=key+':'+papel
        cursor.execute('SELECT ID_EMAIL,ESTADO FROM EMAIL_OUTBOX WHERE CHAVE=?',(chave,));existing=cursor.fetchone()
        if existing:
            if evento=='lembrete' and existing[1]=='cancelado':
                cursor.execute("UPDATE EMAIL_OUTBOX SET ESTADO='pendente',PROXIMA_TENTATIVA=?,TENTATIVAS=0 WHERE ID_EMAIL=?",(quando,existing[0]))
            continue
        cursor.execute('SELECT NOME,EMAIL FROM USUARIO WHERE ID_USUARIO=?',(id_usuario,));client=cursor.fetchone()
        if not client or not client[1]: continue
        cursor.execute('''INSERT INTO EMAIL_OUTBOX (ID_EMAIL,CHAVE,DESTINATARIO,NOME,ASSUNTO,MENSAGEM,PROXIMA_TENTATIVA,ID_AGENDAMENTO,EVENTO,INICIO_REFERENCIA)
            VALUES(NEXT VALUE FOR SEQ_EMAIL_OUTBOX,?,?,?,?,?,?,?,?,?)''',(chave,client[1],client[0],titulos[evento],text,quando,linha[0],evento,inicio))


def preparar_lembretes():
    from visagismo import COLUNAS_AGENDAMENTO
    con=conectar_banco();cur=con.cursor()
    try:
        cur.execute(f"SELECT {COLUNAS_AGENDAMENTO} FROM AGENDAMENTO WHERE STATUS IN ('agendado','confirmado') AND INICIO_EM>CURRENT_TIMESTAMP AND INICIO_EM<DATEADD(31 DAY TO CURRENT_TIMESTAMP)")
        for row in cur.fetchall(): enfileirar_evento(cur,row,'lembrete')
        con.commit()
    finally:cur.close();con.close()


def email_evento_valido(cursor,row):
    # row extends the worker's seven existing fields with booking/event/reference.
    if not row[7]: return True
    cursor.execute('SELECT STATUS,INICIO_EM FROM AGENDAMENTO WHERE ID_AGENDAMENTO=?',(row[7],));booking=cursor.fetchone()
    if not booking: return False
    if row[8]=='cancelamento': return booking[0]=='cancelado'
    return booking[0] in ('agendado','confirmado') and booking[1]==row[9] and (row[8]!='lembrete' or booking[1]>datetime.now())
