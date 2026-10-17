"""Staff invitations, scoped dashboard, durable waiting-list notifications."""
from responses import mensagem_json
from financial_reference import id_agendamento_descricao
import hashlib
import json
import re
import secrets
import threading
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import jsonify, request
from application import app, conectar_banco
from funcoes import decodificar_token as obter_usuario_logado
from funcoes import criptografar_senha, enviar_aviso_email, verificar_senha_forte
from auditoria import registrar_registro, registrar_log


def erro(texto, status=400):
    return mensagem_json(texto, 'erro'), status


def dinheiro(valor):
    try:
        number = Decimal(str(valor or 0))
        if not number.is_finite():
            raise ValueError('Valor inválido.')
        return number.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError('Valor inválido.') from exc


def percentual(valor):
    result = dinheiro(valor)
    if result < 0 or result > 100:
        raise ValueError('A comissão deve estar entre 0 e 100%.')
    return result


def funcionario_logado(cursor, usuario):
    if int(usuario.get('tipo', -1)) != 3:
        return None
    cursor.execute('''SELECT F.ID_FUNCIONARIO,F.ID_BARBEARIA,F.NOME,F.EMAIL,F.TELEFONE,F.COMISSAO_PERCENTUAL,F.COMISSAO_TIPO,F.COMISSAO_VALOR
        FROM FUNCIONARIO F JOIN USUARIO U ON U.ID_USUARIO=F.ID_BARBEARIA
        WHERE F.ID_USUARIO_LOGIN=? AND F.ATIVO=1 AND U.ATIVO=1 AND U.TIPO=2''', (usuario['id_usuario'],))
    return cursor.fetchone()


def acesso_agendamento(cursor, usuario, linha):
    if int(usuario.get('tipo', -1)) == 3:
        fun = funcionario_logado(cursor, usuario)
        return bool(fun and linha[2] == fun[1] and linha[3] == fun[0])
    from visagismo import pode_ver_agendamento
    return pode_ver_agendamento(usuario, linha)


def travar_agendamento(cursor, id_agendamento):
    """Always salon first, then re-read booking under lock (READ COMMITTED)."""
    from visagismo import COLUNAS_AGENDAMENTO
    cursor.execute('SELECT ID_BARBEARIA FROM AGENDAMENTO WHERE ID_AGENDAMENTO=?', (id_agendamento,))
    salon = cursor.fetchone()
    if not salon:
        return None
    cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (salon[0],))
    cursor.fetchone()
    cursor.execute(f'SELECT {COLUNAS_AGENDAMENTO} FROM AGENDAMENTO WHERE ID_AGENDAMENTO=? WITH LOCK', (id_agendamento,))
    return cursor.fetchone()


def registrar_evento(cursor, linha, status, id_usuario, novo_inicio=None, novo_fim=None):
    cursor.execute('''INSERT INTO AGENDAMENTO_HISTORICO
        (ID_HISTORICO,ID_AGENDAMENTO,STATUS,ID_USUARIO_RESPONSAVEL,ID_FUNCIONARIO,
         INICIO_ANTES,FIM_ANTES,INICIO_DEPOIS,FIM_DEPOIS)
        VALUES(NEXT VALUE FOR SEQ_AGENDAMENTO_HISTORICO,?,?,?,?,?,?,?,?) RETURNING ID_HISTORICO''',
        (linha[0],status,id_usuario,linha[3],linha[4],linha[5],novo_inicio,novo_fim))
    return cursor.fetchone()[0]


def validar_contexto_visagismo(cursor, dados, id_usuario, id_barbearia):
    session = dados.get('id_visagismo')
    corte = dados.get('id_corte')
    if session not in (None, ''):
        cursor.execute('SELECT ID_VISAGISMO FROM VISAGISMO_SESSAO WHERE ID_VISAGISMO=? AND ID_USUARIO=? AND ID_BARBEARIA=?', (int(session),id_usuario,id_barbearia))
        if not cursor.fetchone(): raise ValueError('Sessão de visagismo inválida para este cliente e barbearia.')
    if corte not in (None, ''):
        cursor.execute('SELECT ID_CORTE FROM CORTE_VISAGISMO WHERE ID_CORTE=? AND ATIVO=1', (int(corte),))
        if not cursor.fetchone(): raise ValueError('Corte não disponível no catálogo.')


def generos_servicos(servicos):
    """Actual service audiences, including unisex; independent of client gender."""
    encontrados={str(s.get('genero') or 'unissex').strip().lower() for s in servicos}
    return [g for g in ('masculino','feminino','unissex') if g in encontrados]


def nome_escolha_corte(escolha,servicos):
    if escolha=='na_hora': return 'Escolho na hora'
    if escolha=='profissional':
        generos=generos_servicos(servicos)
        if generos==['feminino']: return 'A cabeleireira escolhe'
        if generos==['masculino']: return 'O barbeiro escolhe'
        return 'Profissional escolhe'
    return None


def validar_escolha_corte(cursor,dados,id_usuario,id_barbearia,servicos):
    escolha=dados.get('escolha_corte')
    if escolha is not None and escolha not in ('catalogo','na_hora','profissional'):
        raise ValueError('Escolha de corte inválida.')
    corte=dados.get('id_corte');sessao=dados.get('id_visagismo')
    if escolha in ('na_hora','profissional'):
        if corte not in (None,'') or sessao not in (None,''):
            raise ValueError('A escolha na hora ou pelo profissional não aceita corte de catálogo ou sessão de visagismo.')
        from visagismo import normalizar
        if any(any(p in normalizar(s['nome']) for p in ('pintar','color','tinta')) for s in servicos):
            raise ValueError('Serviços de pintura ou coloração precisam manter o fluxo de simulação; não permitem estas escolhas de corte.')
    elif escolha=='catalogo' and corte in (None,''):
        raise ValueError('Selecione um corte válido do catálogo.')
    validar_contexto_visagismo(cursor,dados,id_usuario,id_barbearia)
    return escolha or ('catalogo' if corte not in (None,'') else None)


def salvar_snapshot(cursor, id_agendamento, servicos, inicio, fim,id_funcionario=None,precos_confirmados=None):
    ids = [s['id_servico'] for s in servicos]
    marks = ','.join('?' for _ in ids)
    cursor.execute(f'SELECT ID_SERVICO,PRECO FROM SERVICO WHERE ID_SERVICO IN ({marks})', ids)
    prices = {row[0]: dinheiro(row[1]) for row in cursor.fetchall()}
    if len(prices) != len(ids): raise ValueError('Serviços inválidos para registrar o valor.')
    if id_funcionario:
        cursor.execute(f'SELECT ID_SERVICO,PRECO FROM FUNCIONARIO_PRECO WHERE ID_FUNCIONARIO=? AND ID_SERVICO IN ({marks})',[id_funcionario,*ids])
        prices.update({r[0]:dinheiro(r[1]) for r in cursor.fetchall()})
    if precos_confirmados is not None:
        confirmed={item['id_servico']:dinheiro(item['preco']) for item in precos_confirmados}
        if prices != confirmed:
            from taxa_plataforma import ResumoAlterado
            raise ResumoAlterado('Os preços dos serviços mudaram. Confira o novo resumo antes de confirmar.')
    servicos = [{**s, 'preco': prices[s['id_servico']]} for s in servicos]
    total = sum((dinheiro(s['preco']) for s in servicos), Decimal('0.00'))
    snapshot = [{'id_servico':s['id_servico'], 'nome':s['nome'], 'preco':str(dinheiro(s['preco'])), 'duracao':s['duracao'],'genero':s.get('genero') or 'unissex'} for s in servicos]
    cursor.execute('''UPDATE AGENDAMENTO SET VALOR_TOTAL=?,DURACAO_MINUTOS=?,SERVICOS_SNAPSHOT=?
        WHERE ID_AGENDAMENTO=? AND VALOR_TOTAL IS NULL''', (total,int((fim-inicio).total_seconds()/60),json.dumps(snapshot,ensure_ascii=False),id_agendamento))
    return total


def registrar_comissao(cursor, linha):
    if not linha[3]:
        return None
    cursor.execute('SELECT VALOR_TOTAL FROM AGENDAMENTO WHERE ID_AGENDAMENTO=?', (linha[0],))
    total = cursor.fetchone()
    if not total or total[0] is None:
        # Legacy rows have no historical price. Explicitly refuse an invented fee.
        raise ValueError('Este agendamento antigo não possui valor histórico. A barbearia deve informar o valor realizado.')
    cursor.execute('SELECT COMISSAO_PERCENTUAL,COMISSAO_TIPO,COMISSAO_VALOR FROM FUNCIONARIO WHERE ID_FUNCIONARIO=?', (linha[3],))
    fun = cursor.fetchone()
    tipo=fun[1] if fun and len(fun)>1 else 'percentual'
    configurado=dinheiro(fun[2]) if tipo=='fixa' else percentual(fun[0] if fun else 0)
    pct=Decimal('0.00') if tipo=='fixa' else configurado
    cursor.execute('SELECT ID_AGENDAMENTO FROM COMISSAO_ATENDIMENTO WHERE ID_AGENDAMENTO=?', (linha[0],))
    if cursor.fetchone():
        return None
    base = dinheiro(total[0]); valor = configurado if tipo=='fixa' else dinheiro(base*pct/100)
    cursor.execute('''INSERT INTO COMISSAO_ATENDIMENTO
        (ID_AGENDAMENTO,ID_FUNCIONARIO,ID_BARBEARIA,VALOR_BASE,PERCENTUAL,VALOR_COMISSAO,TIPO,VALOR_CONFIGURADO)
        VALUES(?,?,?,?,?,?,?,?)''', (linha[0],linha[3],linha[2],base,pct,valor,tipo,configurado))
    return valor


def atualizar_acesso_funcionario(cursor, id_funcionario, id_barbearia, indice, dados):
    """Creates an inactive staff account; never claims someone else's email."""
    email = str(dados.get(f'funcionarios[{indice}][email]') or '').strip().lower()
    phone = str(dados.get(f'funcionarios[{indice}][telefone]') or '').strip()
    pct = percentual(dados.get(f'funcionarios[{indice}][comissao_percentual]', 0))
    novo = not dados.get(f'funcionarios[{indice}][id_funcionario]')
    if novo and (not email or not phone): raise ValueError('Informe e-mail e telefone do novo barbeiro.')
    if phone and len(re.sub(r'\D', '', phone)) not in (10, 11): raise ValueError('Telefone deve conter DDD e 10 ou 11 dígitos.')
    if email and (len(email)>150 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)):
        raise ValueError('Informe um e-mail válido para o barbeiro.')
    if phone: phone=re.sub(r'\D','',phone)
    cursor.execute('SELECT ID_USUARIO_LOGIN,EMAIL,NOME FROM FUNCIONARIO WHERE ID_FUNCIONARIO=?', (id_funcionario,))
    old = cursor.fetchone()
    linked = old[0]
    if linked and email != str(old[1] or '').lower():
        raise ValueError('O e-mail de uma conta de barbeiro vinculada não pode ser trocado pela personalização.')
    cursor.execute('''UPDATE FUNCIONARIO SET ID_BARBEARIA=?,EMAIL=?,TELEFONE=?,COMISSAO_PERCENTUAL=?,ATIVO=1
        WHERE ID_FUNCIONARIO=?''', (id_barbearia,email or None,phone or None,pct,id_funcionario))
    if not email:
        return None
    if linked:
        cursor.execute('UPDATE USUARIO SET NOME=?,TELEFONE=? WHERE ID_USUARIO=?', (old[2],phone or None,linked))
        return None
    cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE LOWER(EMAIL)=?', (email,))
    if cursor.fetchone():
        raise ValueError('Este e-mail já pertence a uma conta. Use outro e-mail para o barbeiro.')
    cursor.execute('''INSERT INTO USUARIO(ID_USUARIO,NOME,EMAIL,TELEFONE,SENHA_HASH,TIPO,ATIVO,EMAIL_CONFIRMADO,TENTATIVA)
        VALUES(NEXT VALUE FOR SEQ_USUARIO,?,?,?,?,3,0,0,0) RETURNING ID_USUARIO''',
        (old[2],email,phone or None,criptografar_senha(secrets.token_urlsafe(48))))
    uid = cursor.fetchone()[0]
    cursor.execute('UPDATE FUNCIONARIO SET ID_USUARIO_LOGIN=? WHERE ID_FUNCIONARIO=?', (uid,id_funcionario))
    return criar_convite(cursor,id_funcionario,email)


def criar_convite(cursor,id_funcionario,email):
    token = secrets.token_urlsafe(32)
    cursor.execute('UPDATE BARBEIRO_CONVITE SET UTILIZADO_EM=CURRENT_TIMESTAMP WHERE ID_FUNCIONARIO=? AND UTILIZADO_EM IS NULL', (id_funcionario,))
    cursor.execute('''INSERT INTO BARBEIRO_CONVITE(ID_CONVITE,ID_FUNCIONARIO,TOKEN_HASH,EXPIRA_EM)
        VALUES(NEXT VALUE FOR SEQ_BARBEIRO_CONVITE,?,?,?)''', (id_funcionario,hashlib.sha256(token.encode()).hexdigest(),datetime.now()+timedelta(hours=48)))
    origin = app.config.get('PUBLIC_FRONTEND_URL',app.config.get('FRONTEND_URL','http://127.0.0.1:5173')).rstrip('/')
    return {'id_funcionario':id_funcionario,'email':email,'link_ativacao':f'{origin}/ativar-barbeiro?token={token}'}


def enviar_convites(convites):
    for convite in convites:
        try:
            convite['email_enviado'] = bool(enviar_aviso_email(convite['email'],'barbeiro','Ative seu acesso ao Cortaê',
                f"Defina sua senha pelo link abaixo. Ele expira em 48 horas e funciona uma vez:\n{convite['link_ativacao']}"))
        except Exception:
            convite['email_enviado'] = False
    return convites


@app.post('/barbeiros/ativar')
def ativar_barbeiro():
    dados = request.get_json(silent=True) or {}; token = str(dados.get('token') or '')
    senha = dados.get('senha'); confirma = dados.get('confirmarSenha')
    if not token or len(token)>200 or not isinstance(senha,str) or len(senha)<8 or len(senha)>128 or senha != confirma:
        return erro('Informe o convite e uma senha de 8 a 128 caracteres, com confirmação igual.')
    forte,motivo=verificar_senha_forte(senha)
    if not forte: return erro(motivo)
    con = conectar_banco(); cur = con.cursor()
    try:
        cur.execute('''SELECT ID_CONVITE,ID_FUNCIONARIO,EXPIRA_EM,UTILIZADO_EM FROM BARBEIRO_CONVITE
            WHERE TOKEN_HASH=? WITH LOCK''', (hashlib.sha256(token.encode()).hexdigest(),))
        invite = cur.fetchone()
        if not invite or invite[3] or invite[2] <= datetime.now():
            return erro('Convite inválido, expirado ou já utilizado.',400)
        cur.execute('SELECT ID_USUARIO_LOGIN,ATIVO FROM FUNCIONARIO WHERE ID_FUNCIONARIO=? WITH LOCK', (invite[1],))
        fun = cur.fetchone()
        if not fun or fun[1] != 1 or not fun[0]:
            return erro('O acesso deste barbeiro está desativado.',403)
        cur.execute('UPDATE USUARIO SET SENHA_HASH=?,ATIVO=1,EMAIL_CONFIRMADO=1,TENTATIVA=0 WHERE ID_USUARIO=? AND TIPO=3', (criptografar_senha(senha),fun[0]))
        cur.execute('UPDATE BARBEIRO_CONVITE SET UTILIZADO_EM=CURRENT_TIMESTAMP WHERE ID_CONVITE=?', (invite[0],))
        con.commit()
        registrar_log('UPDATE','USUARIO',id_registro=fun[0],id_usuario=fun[0],campo='ACESSO_BARBEIRO',valor_antes='PENDENTE',valor_depois='ATIVADO')
        return mensagem_json('Acesso ativado. Entre com seu e-mail e senha.', 'sucesso')
    finally:
        cur.close();con.close()


@app.post('/barbearias/<int:id_barbearia>/funcionarios/<int:id_funcionario>/convite')
def reenviar_convite(id_barbearia,id_funcionario):
    usuario=obter_usuario_logado()
    if not usuario:
        return erro('Faça login.',401)
    if int(usuario.get('tipo',-1)) not in (0,2) or (int(usuario['tipo'])==2 and usuario['id_usuario']!=id_barbearia):
        return erro('Sem permissão.',403)
    con=conectar_banco();cur=con.cursor()
    try:
        cur.execute('''SELECT F.EMAIL,U.ATIVO FROM FUNCIONARIO F JOIN USUARIO U ON U.ID_USUARIO=F.ID_USUARIO_LOGIN
            WHERE F.ID_FUNCIONARIO=? AND F.ID_BARBEARIA=? AND F.ATIVO=1''',(id_funcionario,id_barbearia))
        fun=cur.fetchone()
        if not fun:
            return erro('Conta de barbeiro não encontrada.',404)
        if fun[1]==1:
            return erro('Conta já ativada. Use recuperação de senha.')
        convite=criar_convite(cur,id_funcionario,fun[0]);con.commit()
        return jsonify(convites=enviar_convites([convite]),mensagem={'informacao':'Novo convite criado.','tipo':'sucesso'})
    finally:
        cur.close();con.close()


def slot_disponivel(cursor,espera):
    from visagismo import carregar_servicos,servicos_do_funcionario,buscar_funcionario
    from agenda_gestao import validar_expediente
    if espera[4] <= datetime.now():
        return False
    ids=json.loads(str(espera[6])); services=carregar_servicos(cursor,espera[2],ids)
    if not services:
        return False
    if timedelta(minutes=sum(s['duracao'] for s in services)) != espera[5]-espera[4]:
        return False
    try: validar_expediente(cursor,espera[2],espera[3],espera[4],espera[5])
    except ValueError: return False
    if espera[3] and (not buscar_funcionario(cursor,espera[2],espera[3]) or not set(ids)<=servicos_do_funcionario(cursor,espera[2],espera[3])): return False
    cursor.execute('''SELECT FIRST 1 ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_BARBEARIA=?
        AND STATUS IN ('agendado','confirmado') AND INICIO_EM<? AND FIM_EM>?
        AND (CAST(? AS INTEGER) IS NULL OR ID_FUNCIONARIO=? OR ID_FUNCIONARIO IS NULL)''',
        (espera[2],espera[5],espera[4],espera[3],espera[3]))
    return not cursor.fetchone()


COLUNAS_ESPERA='ID_ESPERA,ID_USUARIO,ID_BARBEARIA,ID_FUNCIONARIO,INICIO_EM,FIM_EM,SERVICOS_JSON,ID_CORTE,ID_VISAGISMO,STATUS,CRIADO_EM,NOTIFICADO_EM,ESCOLHA_CORTE'


def enfileirar_liberacao(cursor,linha):
    cursor.execute(f'''SELECT {COLUNAS_ESPERA} FROM LISTA_ESPERA WHERE ID_BARBEARIA=?
        AND STATUS='aguardando' AND INICIO_EM<? AND FIM_EM>? ORDER BY CRIADO_EM,ID_ESPERA''', (linha[2],linha[5],linha[4]))
    waits=cursor.fetchall()
    for wait in waits:
        if not slot_disponivel(cursor,wait):
            continue
        cursor.execute('SELECT NOME,EMAIL,ATIVO FROM USUARIO WHERE ID_USUARIO=?', (wait[1],)); client=cursor.fetchone()
        if not client or client[2]!=1 or not client[1]:
            continue
        key=f'espera:{wait[0]}'
        cursor.execute('SELECT ID_EMAIL FROM EMAIL_OUTBOX WHERE CHAVE=?', (key,))
        if cursor.fetchone():
            continue
        texto=(f'O horário de {wait[4]:%d/%m/%Y às %H:%M} ficou disponível. Acesse o Cortaê para agendar. '
               'Este aviso não reserva o horário; a disponibilidade pode mudar.')
        cursor.execute('''INSERT INTO EMAIL_OUTBOX(ID_EMAIL,CHAVE,ID_ESPERA,DESTINATARIO,NOME,ASSUNTO,MENSAGEM)
            VALUES(NEXT VALUE FOR SEQ_EMAIL_OUTBOX,?,?,?,?,?,?)''', (key,wait[0],client[1],client[0],'Horário disponível na lista de espera',texto))
        cursor.execute("UPDATE LISTA_ESPERA SET STATUS='aviso_pendente' WHERE ID_ESPERA=?", (wait[0],))


@app.route('/agendamentos/lista-espera',methods=['GET','POST'])
def lista_espera():
    usuario=obter_usuario_logado()
    if not usuario:
        return erro('Faça login para acessar a lista de espera.',401)
    if int(usuario.get('tipo',-1))!=1:
        return erro('A lista de espera é destinada a clientes.',403)
    con=conectar_banco();cur=con.cursor()
    try:
        if request.method=='GET':
            cur.execute(f'SELECT {COLUNAS_ESPERA} FROM LISTA_ESPERA WHERE ID_USUARIO=? ORDER BY CRIADO_EM DESC',(usuario['id_usuario'],))
            return jsonify(lista_espera=[serializar_espera(row,cur) for row in cur.fetchall()])
        from visagismo import parse_data,ids_servicos_da_requisicao,carregar_servicos,horarios_disponiveis
        dados=request.get_json(silent=True) or {};salon=int(dados.get('id_barbearia') or 0);ids=ids_servicos_da_requisicao(dados)
        fun=int(dados['id_funcionario']) if dados.get('id_funcionario') not in (None,'') else None
        dia=parse_data(dados.get('data'));start=datetime.combine(dia,datetime.strptime(str(dados.get('horario')),'%H:%M').time())
        if start<=datetime.now():
            return erro('A lista de espera exige um horário futuro.')
        services=carregar_servicos(cur,salon,ids)
        if not services:
            return erro('Serviços inválidos.')
        escolha=validar_escolha_corte(cur,dados,usuario['id_usuario'],salon,services)
        duration=sum(s['duracao'] for s in services);end=start+timedelta(minutes=duration)
        from visagismo import buscar_funcionario,servicos_do_funcionario
        if fun and (not buscar_funcionario(cur,salon,fun) or not set(ids)<=servicos_do_funcionario(cur,salon,fun)):
            return erro('Profissional inválido para estes serviços.')
        cur.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1 WITH LOCK',(salon,))
        if not cur.fetchone():
            return erro('Barbearia indisponível.',404)
        slots=horarios_disponiveis(cur,salon,dia,duration,fun)
        selected=next((s for s in slots if s['horario']==start.strftime('%H:%M')),None)
        if not selected:
            return erro('Horário fora do expediente ou do profissional.')
        if selected['disponivel']:
            return erro('O horário já está livre. Faça o agendamento normalmente.',409)
        if not selected.get('lista_espera_disponivel',False):
            return erro('Este horário está bloqueado ou indisponível para lista de espera.')
        cur.execute('''SELECT ID_ESPERA FROM LISTA_ESPERA WHERE ID_USUARIO=? AND ID_BARBEARIA=? AND INICIO_EM=?
            AND FIM_EM=? AND (ID_FUNCIONARIO=? OR (ID_FUNCIONARIO IS NULL AND CAST(? AS INTEGER) IS NULL))
            AND STATUS IN ('aguardando','aviso_pendente')''',(usuario['id_usuario'],salon,start,end,fun,fun))
        old=cur.fetchone()
        if old:
            return jsonify(id_espera=old[0],mensagem={'informacao':'Você já está nesta lista de espera.','tipo':'aviso'})
        cur.execute('''INSERT INTO LISTA_ESPERA(ID_ESPERA,ID_USUARIO,ID_BARBEARIA,ID_FUNCIONARIO,INICIO_EM,FIM_EM,SERVICOS_JSON,ID_CORTE,ID_VISAGISMO,ESCOLHA_CORTE)
            VALUES(NEXT VALUE FOR SEQ_LISTA_ESPERA,?,?,?,?,?,?,?,?,?) RETURNING ID_ESPERA''',
            (usuario['id_usuario'],salon,fun,start,end,json.dumps(ids),dados.get('id_corte'),dados.get('id_visagismo'),escolha))
        wid=cur.fetchone()[0];con.commit()
        registrar_registro(cur,'INSERT','LISTA_ESPERA','ID_ESPERA',wid,id_usuario=usuario['id_usuario'])
        return jsonify(id_espera=wid,mensagem={'informacao':'Você entrou na lista de espera. Avisaremos por e-mail quando o horário ficar livre.','tipo':'sucesso'}),201
    except (ValueError,TypeError) as exc:
        con.rollback();return erro(str(exc))
    finally:
        cur.close();con.close()


def serializar_espera(row,cursor=None):
    escolha=row[12] if len(row)>12 else None
    services=[]
    if escolha in ('na_hora','profissional') and cursor is not None:
        ids=json.loads(str(row[6]));marks=','.join('?' for _ in ids)
        cursor.execute(f'SELECT GENERO FROM SERVICO WHERE ID_USUARIO=? AND ID_SERVICO IN ({marks})',[row[2],*ids])
        services=[{'genero':r[0]} for r in cursor.fetchall()]
    return {'id_espera':row[0],'id_lista_espera':row[0],'id_barbearia':row[2],'id_funcionario':row[3],'inicio_em':row[4].isoformat(),
            'fim_em':row[5].isoformat(),'ids_servicos':json.loads(str(row[6])),'id_corte':row[7],'id_visagismo':row[8],
            'status':row[9],'criado_em':row[10].isoformat(),'notificado_em':row[11].isoformat() if row[11] else None,
            'escolha_corte':escolha,'corte_nome':nome_escolha_corte(escolha,services)}


@app.delete('/agendamentos/lista-espera/<int:id_espera>')
def sair_lista_espera(id_espera):
    usuario=obter_usuario_logado()
    if not usuario:
        return erro('Faça login.',401)
    con=conectar_banco();cur=con.cursor()
    try:
        cur.execute('SELECT ID_USUARIO FROM LISTA_ESPERA WHERE ID_ESPERA=?',(id_espera,)); row=cur.fetchone()
        if not row:
            return erro('Inscrição não encontrada.',404)
        if row[0]!=usuario['id_usuario']:
            return erro('Sem permissão.',403)
        cur.execute('SELECT ID_EMAIL FROM EMAIL_OUTBOX WHERE ID_ESPERA=? WITH LOCK', (id_espera,));cur.fetchall()
        cur.execute('SELECT ID_USUARIO FROM LISTA_ESPERA WHERE ID_ESPERA=? WITH LOCK', (id_espera,));cur.fetchone()
        cur.execute("UPDATE LISTA_ESPERA SET STATUS='cancelada' WHERE ID_ESPERA=?",(id_espera,))
        cur.execute("UPDATE EMAIL_OUTBOX SET ESTADO='cancelado' WHERE ID_ESPERA=? AND ESTADO='pendente'",(id_espera,));con.commit()
        registrar_log('UPDATE','LISTA_ESPERA',id_registro=id_espera,id_usuario=usuario['id_usuario'],campo='STATUS',valor_depois='cancelada')
        return mensagem_json('Você saiu da lista de espera.', 'sucesso')
    finally:
        cur.close();con.close()


def processar_emails(limite=20):
    """Persisted retries; row lock ensures only one worker delivers each item.

    SMTP does not support exactly-once delivery after a process crash between
    remote acceptance and commit. Normal retries never repeat a committed send.
    """
    enviados=0
    for _ in range(max(0,min(int(limite),100))):
        con=conectar_banco();cur=con.cursor()
        try:
            cur.execute('''SELECT FIRST 1 ID_EMAIL,ID_ESPERA,DESTINATARIO,NOME,ASSUNTO,MENSAGEM,TENTATIVAS,ID_AGENDAMENTO,EVENTO,INICIO_REFERENCIA
                FROM EMAIL_OUTBOX WHERE ESTADO='pendente' AND PROXIMA_TENTATIVA<=CURRENT_TIMESTAMP
                ORDER BY CRIADO_EM,ID_EMAIL WITH LOCK''');row=cur.fetchone()
            if not row:
                break
            if row[1]:
                cur.execute(f'SELECT {COLUNAS_ESPERA} FROM LISTA_ESPERA WHERE ID_ESPERA=?',(row[1],));wait=cur.fetchone()
                if not wait or wait[9]=='cancelada' or wait[4]<=datetime.now():
                    cur.execute("UPDATE EMAIL_OUTBOX SET ESTADO='cancelado' WHERE ID_EMAIL=?",(row[0],));con.commit();continue
                if not slot_disponivel(cur,wait):
                    cur.execute('UPDATE EMAIL_OUTBOX SET PROXIMA_TENTATIVA=? WHERE ID_EMAIL=?',(datetime.now()+timedelta(minutes=5),row[0]));con.commit();continue
            elif len(row)>7:
                from agenda_gestao import email_evento_valido
                if not email_evento_valido(cur,row):
                    cur.execute("UPDATE EMAIL_OUTBOX SET ESTADO='cancelado' WHERE ID_EMAIL=?",(row[0],));con.commit();continue
            try:
                ok=bool(enviar_aviso_email(row[2],row[3] or 'cliente',row[4],str(row[5])))
            except Exception:
                ok=False
            if ok:
                cur.execute("UPDATE EMAIL_OUTBOX SET ESTADO='enviado',ENVIADO_EM=CURRENT_TIMESTAMP,TENTATIVAS=TENTATIVAS+1 WHERE ID_EMAIL=?",(row[0],))
                cur.execute("UPDATE LISTA_ESPERA SET STATUS='notificada',NOTIFICADO_EM=CURRENT_TIMESTAMP WHERE ID_ESPERA=? AND STATUS<>'cancelada'",(row[1],));enviados+=1
            else:
                attempts=int(row[6])+1
                cur.execute('UPDATE EMAIL_OUTBOX SET TENTATIVAS=?,PROXIMA_TENTATIVA=?,ESTADO=? WHERE ID_EMAIL=?',
                    (attempts,datetime.now()+timedelta(minutes=min(60,2**min(attempts,6))),'falhou' if attempts>=8 else 'pendente',row[0]))
                if attempts>=8: cur.execute("UPDATE LISTA_ESPERA SET STATUS='aviso_falhou' WHERE ID_ESPERA=? AND STATUS='aviso_pendente'",(row[1],))
            con.commit()
        except Exception:
            con.rollback();app.logger.exception('Falha no processamento da lista de espera');break
        finally:
            cur.close();con.close()
    return enviados


_worker_iniciado=False
_worker_lock=threading.Lock()


def iniciar_worker_emails():
    global _worker_iniciado
    with _worker_lock:
        if _worker_iniciado:
            return
        _worker_iniciado=True
    def run():
        while True:
            with app.app_context():
                try:
                    from agenda_gestao import preparar_lembretes
                    preparar_lembretes()
                    processar_emails()
                except Exception:
                    app.logger.exception('Falha temporária na conexão do worker de e-mail')
            threading.Event().wait(30)
    threading.Thread(target=run,name='cortae-lista-espera',daemon=True).start()


@app.get('/barbeiro/painel')
def painel_barbeiro():
    usuario=obter_usuario_logado()
    if not usuario:
        return erro('Faça login.',401)
    if int(usuario.get('tipo',-1))!=3:
        return erro('Este painel é exclusivo do barbeiro.',403)
    con=conectar_banco();cur=con.cursor()
    try:
        fun=funcionario_logado(cur,usuario)
        if not fun:
            return erro('Acesso do barbeiro desativado.',403)
        from visagismo import COLUNAS_AGENDAMENTO,serializar_agendamento
        from ranking_avaliacoes import periodo_solicitado
        inicio,fim,a,b=periodo_solicitado()
        # Full own schedule includes future bookings; statistics use selected period.
        cur.execute(f'SELECT {COLUNAS_AGENDAMENTO} FROM AGENDAMENTO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=? ORDER BY INICIO_EM DESC',(fun[0],fun[1])); rows=cur.fetchall()
        bookings=[serializar_agendamento(cur,row,usuario) for row in rows]
        period=[row for row in rows if a<=row[4]<b]
        stats={'realizados':sum(row[9]=='concluido' for row in period),'cancelados':sum(row[9]=='cancelado' for row in period),
               'faltas':sum(row[9]=='faltou' for row in period),'agendados':sum(row[9] in ('agendado','confirmado') for row in period)}
        cur.execute('''SELECT COUNT(DISTINCT H.ID_AGENDAMENTO) FROM AGENDAMENTO_HISTORICO H
            JOIN AGENDAMENTO A ON A.ID_AGENDAMENTO=H.ID_AGENDAMENTO WHERE H.ID_FUNCIONARIO=? AND A.ID_BARBEARIA=?
            AND H.STATUS='remarcado' AND H.REGISTRADO_EM>=? AND H.REGISTRADO_EM<?''',(fun[0],fun[1],a,b));stats['remarcados']=cur.fetchone()[0]
        cur.execute('''SELECT C.ID_AGENDAMENTO,C.VALOR_BASE,C.PERCENTUAL,C.VALOR_COMISSAO,C.REGISTRADO_EM,C.TIPO,C.VALOR_CONFIGURADO
            FROM COMISSAO_ATENDIMENTO C JOIN AGENDAMENTO A ON A.ID_AGENDAMENTO=C.ID_AGENDAMENTO
            WHERE C.ID_FUNCIONARIO=? AND C.ID_BARBEARIA=? AND A.INICIO_EM>=? AND A.INICIO_EM<? ORDER BY C.REGISTRADO_EM DESC''',(fun[0],fun[1],a,b)); commissions=cur.fetchall()
        cur.execute("SELECT VALOR_TOTAL FROM AGENDAMENTO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=? AND STATUS='concluido' AND INICIO_EM>=? AND INICIO_EM<?",(fun[0],fun[1],a,b)); totals=cur.fetchall()
        stats['valor_arrecadado']=float(sum((dinheiro(row[0]) for row in totals if row[0] is not None),Decimal('0')))
        stats['valores_historicos_ausentes']=sum(row[0] is None for row in totals)
        stats['comissao_total']=float(sum((dinheiro(row[3]) for row in commissions),Decimal('0')))
        # Only confirmed paid financial records, exact ag# match; pending is excluded.
        cur.execute("SELECT DESCRICAO,VALOR,ID_USUARIO FROM FINANCEIRO WHERE TIPO IN ('pix_pago','cartao_pago','boleto_pago','na_hora')"); financial=cur.fetchall()
        relevant={row[0]:row[1] for row in period}; received=Decimal('0')
        for desc,value,client_id in financial:
            booking_id=id_agendamento_descricao(desc)
            if booking_id is not None and relevant.get(booking_id)==client_id:
                received+=dinheiro(value)
        stats['valor_recebido']=float(received)
        from ranking_avaliacoes import resumo_avaliacoes
        avaliacoes=resumo_avaliacoes(cur,fun[1],fun[0],a,b)
        return jsonify(funcionario={'id_funcionario':fun[0],'id_barbearia':fun[1],'nome':fun[2],'email':fun[3],'telefone':fun[4],'comissao_percentual':float(fun[5] or 0),'comissao_tipo':fun[6] if len(fun)>6 else 'percentual','comissao_valor':float(fun[7]) if len(fun)>7 and fun[6]=='fixa' else float(fun[5] or 0)},
            inicio=inicio.isoformat(),fim=fim.isoformat(),estatisticas=stats,agendamentos=bookings,
            resumo_avaliacoes=avaliacoes,
            comissoes=[{'id_agendamento':row[0],'valor_base':float(row[1]),'percentual':float(row[2]),'valor_comissao':float(row[3]),'registrado_em':row[4].isoformat(),'tipo':row[5] if len(row)>5 else 'percentual','valor_configurado':float(row[6]) if len(row)>6 and row[6] is not None else float(row[2])} for row in commissions])
    except ValueError as exc:
        return erro(str(exc))
    finally:
        cur.close();con.close()


@app.get('/barbearia/comissoes')
def comissoes_barbearia():
    """Read-only amounts earned; payment to staff is performed manually by the salon."""
    usuario = obter_usuario_logado()
    if not usuario:
        return erro('Faça login.', 401)
    tipo = int(usuario.get('tipo', -1))
    if tipo not in (0, 2):
        return erro('Este relatório é exclusivo da barbearia e do administrador.', 403)
    from barbearia import pegar_id_barbearia_alvo
    from visagismo import parse_data
    try:
        pedido = request.args.get('id_barbearia') or request.args.get('id_usuario') or request.args.get('usuario')
        if tipo == 2:
            id_barbearia = int(usuario['id_usuario'])
            if pedido and int(pedido) != id_barbearia:
                return erro('Sem permissão para esta barbearia.', 403)
        else:
            id_barbearia = int(pedido) if pedido else pegar_id_barbearia_alvo()
            if not id_barbearia:
                return erro('Selecione uma barbearia para consultar as comissões.')
        inicio = parse_data(request.args['inicio']) if request.args.get('inicio') else date.today().replace(day=1)
        fim = parse_data(request.args['fim']) if request.args.get('fim') else date.today()
        if fim < inicio or (fim - inicio).days > 366:
            return erro('Informe um período válido de até 366 dias.')
    except (TypeError, ValueError) as exc:
        return erro(str(exc))
    a = datetime.combine(inicio, time.min)
    b = datetime.combine(fim + timedelta(days=1), time.min)
    con = conectar_banco(); cur = con.cursor()
    try:
        cur.execute('SELECT ID_USUARIO,NOME FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2', (id_barbearia,))
        salon = cur.fetchone()
        if not salon:
            return erro('Barbearia não encontrada.', 404)
        cur.execute('SELECT ID_FUNCIONARIO,NOME,ATIVO,COMISSAO_PERCENTUAL,COMISSAO_TIPO,COMISSAO_VALOR FROM FUNCIONARIO WHERE ID_BARBEARIA=? ORDER BY NOME', (id_barbearia,))
        grupos = {row[0]: {'id_funcionario': row[0], 'nome': row[1], 'ativo': row[2] == 1,
                          'comissao_percentual': float(row[3] or 0),'comissao_tipo':row[4] if len(row)>4 else 'percentual','comissao_valor':float(row[5]) if len(row)>5 and row[4]=='fixa' else float(row[3] or 0), 'quantidade_atendimentos': 0,
                          'valor_base': Decimal('0.00'), 'valor_comissao': Decimal('0.00'), 'atendimentos': []}
                  for row in cur.fetchall()}
        cur.execute('''SELECT C.ID_FUNCIONARIO,F.NOME,F.ATIVO,F.COMISSAO_PERCENTUAL,C.ID_AGENDAMENTO,
            A.INICIO_EM,U.NOME,C.VALOR_BASE,C.PERCENTUAL,C.VALOR_COMISSAO,C.REGISTRADO_EM,C.TIPO,C.VALOR_CONFIGURADO
            FROM COMISSAO_ATENDIMENTO C JOIN AGENDAMENTO A ON A.ID_AGENDAMENTO=C.ID_AGENDAMENTO
            LEFT JOIN FUNCIONARIO F ON F.ID_FUNCIONARIO=C.ID_FUNCIONARIO
            LEFT JOIN USUARIO U ON U.ID_USUARIO=A.ID_USUARIO
            WHERE C.ID_BARBEARIA=? AND A.ID_BARBEARIA=? AND A.INICIO_EM>=? AND A.INICIO_EM<?
            ORDER BY F.NOME,A.INICIO_EM DESC,C.ID_AGENDAMENTO DESC''', (id_barbearia,id_barbearia,a,b))
        total_base = Decimal('0.00'); total_comissao = Decimal('0.00'); quantidade = 0
        for row in cur.fetchall():
            grupo = grupos.setdefault(row[0], {'id_funcionario': row[0], 'nome': row[1] or f'Profissional #{row[0]}',
                'ativo': row[2] == 1, 'comissao_percentual': float(row[3] or 0), 'quantidade_atendimentos': 0,
                'valor_base': Decimal('0.00'), 'valor_comissao': Decimal('0.00'), 'atendimentos': []})
            base = dinheiro(row[7]); comissao = dinheiro(row[9])
            grupo['quantidade_atendimentos'] += 1; grupo['valor_base'] += base; grupo['valor_comissao'] += comissao
            total_base += base; total_comissao += comissao; quantidade += 1
            grupo['atendimentos'].append({'id_agendamento': row[4], 'inicio_em': row[5].isoformat(),
                'cliente_nome': row[6], 'valor_base': float(base), 'percentual': float(row[8]),
                'valor_comissao': float(comissao), 'registrado_em': row[10].isoformat(),'tipo':row[11] if len(row)>11 else 'percentual','valor_configurado':float(row[12]) if len(row)>12 and row[12] is not None else float(row[8])})
        cur.execute('''SELECT
            SUM(CASE WHEN VALOR_TOTAL IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN ID_FUNCIONARIO IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN ID_FUNCIONARIO IS NOT NULL AND NOT EXISTS(
                SELECT 1 FROM COMISSAO_ATENDIMENTO C WHERE C.ID_AGENDAMENTO=A.ID_AGENDAMENTO) THEN 1 ELSE 0 END)
            FROM AGENDAMENTO A WHERE ID_BARBEARIA=? AND STATUS='concluido' AND INICIO_EM>=? AND INICIO_EM<?''', (id_barbearia,a,b))
        avisos = cur.fetchone()
        funcionarios = []
        for grupo in grupos.values():
            grupo['valor_base'] = float(grupo['valor_base']); grupo['valor_comissao'] = float(grupo['valor_comissao'])
            funcionarios.append(grupo)
        return jsonify(id_barbearia=id_barbearia,barbearia_nome=salon[1],inicio=inicio.isoformat(),fim=fim.isoformat(),
            funcionarios=funcionarios,totais={'quantidade_atendimentos':quantidade,'valor_base':float(total_base),'valor_comissao':float(total_comissao)},
            avisos={'valores_historicos_ausentes':int(avisos[0] or 0),'atendimentos_sem_profissional':int(avisos[1] or 0),
                    'atendimentos_sem_comissao':int(avisos[2] or 0)})
    finally:
        cur.close(); con.close()


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Processa e-mails pendentes da lista de espera, sem reenviar mensagens confirmadas.')
    parser.add_argument('--limite',type=int,default=20)
    args=parser.parse_args()
    with app.app_context():
        print(json.dumps({'enviados':processar_emails(args.limite)}))
