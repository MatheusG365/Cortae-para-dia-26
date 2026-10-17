"""Local salon management. No provider, messaging or bank-transfer integrations."""
from responses import mensagem_json
from financial_reference import id_agendamento_descricao
from database import travar_usuario
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from flask import jsonify, request
from application import app, conectar_banco
from barbearia import obter_usuario_logado
from auditoria import registrar_log, registrar_registro, capturar_registro, _valor_para_texto

PAGOS = {'na_hora','pix_pago','cartao_pago','boleto_pago'}
ZERO = Decimal('0.00')


class Conflito(ValueError):
    pass


def erro(texto, status=400):
    return mensagem_json(texto, 'erro'),status


def inteiro(valor, nome='Identificação'):
    if isinstance(valor,bool) or not re.fullmatch(r'[1-9]\d*',str(valor or '')):
        raise ValueError(f'{nome} inválida.')
    result=int(valor)
    if result>2147483647:raise ValueError(f'{nome} inválida.')
    return result


def dinheiro(valor, positivo=False):
    if isinstance(valor,bool):raise ValueError('Valor inválido.')
    try:
        result=Decimal(str(valor))
        if not result.is_finite() or abs(result)>Decimal('9999999999.99'):raise ValueError('Valor inválido.')
        result=result.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
        if positivo and result<=0:raise ValueError('Informe um valor maior que zero.')
        return result
    except (InvalidOperation,TypeError):raise ValueError('Valor inválido.') from None


def texto(valor, limite, nome, vazio=True):
    if valor is None:valor=''
    if not isinstance(valor,str):raise ValueError(f'{nome} deve ser texto.')
    result=valor.strip()
    if len(result)>limite or (not vazio and not result):raise ValueError(f'{nome} inválido ou muito longo.')
    return result


def dia(valor, padrao=None):
    if valor in (None,''):return padrao
    if not isinstance(valor,str):raise ValueError('Data inválida; use AAAA-MM-DD.')
    try:
        result=date.fromisoformat(valor)
        if result.year<1900 or result.year>=9999:raise ValueError()
        return result
    except ValueError:raise ValueError('Data inválida; use AAAA-MM-DD.') from None


def periodo(padrao=True):
    a=dia(request.args.get('inicio'),date.today().replace(day=1) if padrao else None)
    b=dia(request.args.get('fim'),date.today() if padrao else None)
    if bool(a)!=bool(b) or (a and (b<a or (b-a).days>366)):
        raise ValueError('Informe início e fim válidos, em um período de até 366 dias.')
    return a,b


def iso(valor):return valor.isoformat() if valor else None


def js(valor,padrao):
    try:return json.loads(str(valor)) if valor else padrao
    except (ValueError,TypeError):return padrao


def id_descricao(descricao):
    return id_agendamento_descricao(descricao)


def protegido(admin=False,log=False):
    def decorate(func):
        @wraps(func)
        def wrapped(*args,**kwargs):
            user=obter_usuario_logado()
            if not user:return erro('Faça login.',401)
            role=int(user.get('tipo',-1))
            if role not in ((0,) if admin else (0,2)):return erro('Sem permissão para acessar a gestão.',403)
            try:
                salon=None
                if not log:
                    requested=request.args.get('id_barbearia')
                    salon=inteiro(user['id_usuario']) if role==2 else inteiro(requested,'Barbearia')
                    if role==2 and requested and inteiro(requested)!=salon:return erro('Sem permissão para outra barbearia.',403)
                con=conectar_banco(log=log);cur=con.cursor()
                try:
                    if not log:
                        cur.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2',(salon,))
                        if not cur.fetchone():return erro('Barbearia não encontrada.',404)
                    return func(user,salon,cur,con,*args,**kwargs)
                except Conflito as exc:
                    con.rollback();return erro(str(exc),409)
                except (ValueError,TypeError) as exc:
                    con.rollback();return erro(str(exc))
                except Exception:
                    con.rollback();raise
                finally:cur.close();con.close()
            except (ValueError,TypeError) as exc:return erro(str(exc))
        return wrapped
    return decorate


def travar_salao(cur,salon):
    travar_usuario(cur, salon)


def auditar(cur,user,acao,tabela,coluna,id_,antes=None):
    registrar_registro(cur,acao,tabela,coluna,id_,dados_antes=antes,id_usuario=user['id_usuario'])


def reserva(cur,salon,id_,lock=False):
    id_=inteiro(id_,'Agendamento')
    if lock:
        from agenda_equipe import travar_agendamento
        row=travar_agendamento(cur,id_)
        if not row or row[2]!=salon:return None
        # Match the lightweight management shape below.
        cur.execute('SELECT VALOR_TOTAL FROM AGENDAMENTO WHERE ID_AGENDAMENTO=?',(id_,));value=cur.fetchone()[0]
        return (row[0],row[1],row[2],row[3],row[4],row[5],row[9],value)
    cur.execute('''SELECT ID_AGENDAMENTO,ID_USUARIO,ID_BARBEARIA,ID_FUNCIONARIO,INICIO_EM,FIM_EM,STATUS,VALOR_TOTAL
        FROM AGENDAMENTO WHERE ID_AGENDAMENTO=? AND ID_BARBEARIA=?''',(id_,salon))
    return cur.fetchone()


def financeiro_reservas(cur,salon):
    cur.execute('SELECT ID_AGENDAMENTO,ID_USUARIO FROM AGENDAMENTO WHERE ID_BARBEARIA=?',(salon,))
    related=dict(cur.fetchall())
    if not related:return []
    clients=sorted(set(related.values()));marks=','.join('?' for _ in clients)
    cur.execute(f'''SELECT ID_FINANCEIRO,ID_USUARIO,TIPO,DESCRICAO,VALOR,DATA_TRANSACAO
        FROM FINANCEIRO WHERE ID_USUARIO IN ({marks}) ORDER BY DATA_TRANSACAO,ID_FINANCEIRO''',clients)
    return [row for row in cur.fetchall() if related.get(id_descricao(row[3]))==row[1]]


def roster(cur,salon,a=None,b=None):
    cur.execute('''SELECT U.ID_USUARIO,U.NOME,U.EMAIL,U.TELEFONE,A.ID_AGENDAMENTO,A.INICIO_EM,A.STATUS,
        G.OBSERVACOES,G.PREFERENCIAS FROM AGENDAMENTO A JOIN USUARIO U ON U.ID_USUARIO=A.ID_USUARIO
        LEFT JOIN GESTAO_CLIENTE G ON G.ID_USUARIO=U.ID_USUARIO AND G.ID_BARBEARIA=A.ID_BARBEARIA
        WHERE A.ID_BARBEARIA=? ORDER BY U.NOME,A.INICIO_EM''',(salon,))
    groups={}
    for row in cur.fetchall():
        entry=groups.setdefault(row[0],dict(id_usuario=row[0],nome=row[1],email=row[2],telefone=row[3],total_agendamentos=0,
            atendimentos_realizados=0,faltas=0,ultima_visita=None,dias_inativo=None,observacoes=str(row[7] or ''),preferencias=str(row[8] or '')))
        when=row[5].date()
        if row[6]=='concluido' and when<=date.today():
            entry['ultima_visita']=max(entry['ultima_visita'] or when,when)
        if a and not a<=when<=b:continue
        entry['total_agendamentos']+=1
        entry['atendimentos_realizados']+=row[6]=='concluido';entry['faltas']+=row[6]=='faltou'
    for entry in groups.values():
        entry['dias_inativo']=(date.today()-entry['ultima_visita']).days if entry['ultima_visita'] else None
        entry['ultima_visita']=iso(entry['ultima_visita'])
    return [entry for entry in groups.values() if not a or entry['total_agendamentos']]


@app.get('/gestao/clientes')
@protegido()
def clientes(user,salon,cur,con):
    a,b=periodo(False);entries=roster(cur,salon,a,b)
    search=texto(request.args.get('busca'),150,'Busca').casefold()
    if search:entries=[c for c in entries if search in ' '.join(str(c[k] or '') for k in ('nome','email','telefone')).casefold()]
    if request.args.get('inativos_dias'):
        days=inteiro(request.args['inativos_dias'],'Dias de inatividade')
        entries=[c for c in entries if c['dias_inativo'] is None or c['dias_inativo']>=days]
    return jsonify(clientes=entries,total=len(entries))


@app.route('/gestao/clientes/<int:id_cliente>',methods=['GET','PUT'])
@protegido()
def cliente_detalhe(user,salon,cur,con,id_cliente):
    cur.execute('SELECT FIRST 1 ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_BARBEARIA=? AND ID_USUARIO=?',(salon,id_cliente))
    if not cur.fetchone():return erro('Cliente sem atendimento nesta barbearia.',404)
    if request.method=='PUT':
        data=request.get_json(silent=True) or {}
        obs=texto(data.get('observacoes'),10000,'Observações');prefs=texto(data.get('preferencias'),10000,'Preferências')
        travar_salao(cur,salon)
        cur.execute('SELECT OBSERVACOES,PREFERENCIAS FROM GESTAO_CLIENTE WHERE ID_BARBEARIA=? AND ID_USUARIO=?',(salon,id_cliente))
        previous=cur.fetchone()
        before={'ID_BARBEARIA':salon,'OBSERVACOES':str(previous[0] or ''),'PREFERENCIAS':str(previous[1] or '')} if previous else None
        cur.execute('''UPDATE OR INSERT INTO GESTAO_CLIENTE(ID_BARBEARIA,ID_USUARIO,OBSERVACOES,PREFERENCIAS,ATUALIZADO_EM)
            VALUES(?,?,?,?,CURRENT_TIMESTAMP) MATCHING(ID_BARBEARIA,ID_USUARIO)''',(salon,id_cliente,obs,prefs));con.commit()
        registrar_log('UPDATE','GESTAO_CLIENTE',id_registro=id_cliente,id_usuario=user['id_usuario'],dados_antes=before,dados_depois={'ID_BARBEARIA':salon,'OBSERVACOES':obs,'PREFERENCIAS':prefs})
    entry=next(c for c in roster(cur,salon) if c['id_usuario']==id_cliente)
    cur.execute('''SELECT A.ID_AGENDAMENTO,A.ID_FUNCIONARIO,F.NOME,A.INICIO_EM,A.FIM_EM,A.STATUS,A.VALOR_TOTAL,A.SERVICOS_SNAPSHOT
        FROM AGENDAMENTO A LEFT JOIN FUNCIONARIO F ON F.ID_FUNCIONARIO=A.ID_FUNCIONARIO
        WHERE A.ID_BARBEARIA=? AND A.ID_USUARIO=? ORDER BY A.INICIO_EM DESC,A.ID_AGENDAMENTO DESC''',(salon,id_cliente))
    appointments=[dict(id_agendamento=r[0],id_funcionario=r[1],funcionario_nome=r[2],inicio_em=iso(r[3]),fim_em=iso(r[4]),status=r[5],valor_total=float(r[6]) if r[6] is not None else None,servicos=js(r[7],[])) for r in cur.fetchall()]
    payments=[dict(id_financeiro=r[0],tipo=r[2],descricao=r[3],valor=float(r[4]),data_pagamento=iso(r[5]),id_agendamento=id_descricao(r[3])) for r in financeiro_reservas(cur,salon) if r[1]==id_cliente]
    return jsonify(cliente=entry,observacoes=entry['observacoes'],preferencias=entry['preferencias'],agendamentos=appointments,pagamentos=payments)


def valor_log_seguro(value,field):
    def sensivel(name):
        return any(word in str(name or '').upper() for word in ('CLIENT_ID','CREDENCIAIS','CREDENTIALS'))
    if sensivel(field):return '[PROTEGIDO]' if value is not None else None
    protected=_valor_para_texto(value,field)
    if protected=='[PROTEGIDO]':return protected
    def redact(data):
        if isinstance(data,dict):return {k:('[PROTEGIDO]' if sensivel(k) or _valor_para_texto(v,k)=='[PROTEGIDO]' else redact(v)) for k,v in data.items()}
        if isinstance(data,list):return [redact(v) for v in data]
        return data
    try:
        data=json.loads(str(value))
        if isinstance(data,(dict,list)):return json.dumps(redact(data),ensure_ascii=False)
    except (ValueError,TypeError):pass
    return protected


@app.get('/gestao/logs')
@protegido(admin=True,log=True)
def logs(user,salon,cur,con):
    page=inteiro(request.args.get('page',request.args.get('pagina','1')),'Página')
    limit=min(inteiro(request.args.get('limite','30'),'Limite'),100)
    if (page-1)*limit>2147483647:raise ValueError('Página fora do limite permitido.')
    clauses=[];args=[]
    for query,column in (('acao','ACAO'),('tabela','TABELA_ALTERADA')):
        if request.args.get(query):clauses.append(f'UPPER({column}) CONTAINING ?');args.append(texto(request.args[query],100,'Filtro').upper())
    if request.args.get('usuario'):clauses.append('ID_USUARIO=?');args.append(inteiro(request.args['usuario'],'Usuário'))
    a,b=periodo(False)
    if a:clauses.append('DATA_HORA>=? AND DATA_HORA<?');args.extend([datetime.combine(a,time.min),datetime.combine(b+timedelta(days=1),time.min)])
    if request.args.get('busca'):
        search=texto(request.args['busca'],100,'Busca').upper()
        clauses.append('(UPPER(ACAO) CONTAINING ? OR UPPER(TABELA_ALTERADA) CONTAINING ? OR UPPER(CAMPO_ALTERADO) CONTAINING ?)');args.extend([search]*3)
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    cur.execute('SELECT COUNT(*) FROM LOG_ALTERACAO'+where,args);total=cur.fetchone()[0]
    cur.execute(f'''SELECT FIRST {limit} SKIP {(page-1)*limit} ID_LOG,ID_USUARIO,MAQUINA_IP,ACAO,TABELA_ALTERADA,
        ID_REGISTRO_ALTERADO,CAMPO_ALTERADO,VALOR_ANTES,VALOR_DEPOIS,DATA_HORA FROM LOG_ALTERACAO'''+where+' ORDER BY DATA_HORA DESC,ID_LOG DESC',args)
    rows=[dict(id_log=r[0],id_usuario=r[1],ip=r[2],acao=r[3],tabela=r[4],id_registro=r[5],campo=r[6],antes=valor_log_seguro(r[7],r[6]),depois=valor_log_seguro(r[8],r[6]),data_hora=iso(r[9])) for r in cur.fetchall()]
    return jsonify(logs=rows,pagina=page,limite=limit,total=total,paginas=(total+limit-1)//limit)


@app.get('/gestao/relatorios')
@protegido()
def relatorios(user,salon,cur,con):
    a,b=periodo();start=datetime.combine(a,time.min);end=datetime.combine(b+timedelta(days=1),time.min)
    cur.execute('''SELECT A.ID_AGENDAMENTO,A.ID_USUARIO,A.ID_FUNCIONARIO,F.NOME,A.INICIO_EM,A.STATUS,A.VALOR_TOTAL,A.SERVICOS_SNAPSHOT,A.SERVICOS_JSON
        FROM AGENDAMENTO A LEFT JOIN FUNCIONARIO F ON F.ID_FUNCIONARIO=A.ID_FUNCIONARIO
        WHERE A.ID_BARBEARIA=? AND A.INICIO_EM>=? AND A.INICIO_EM<?''',(salon,start,end));rows=cur.fetchall()
    cur.execute('SELECT ID_SERVICO,NOME_SERVICO FROM SERVICO WHERE ID_USUARIO=?',(salon,));names=dict(cur.fetchall())
    services={};staff={};hours=Counter()
    for row in rows:
        group=staff.setdefault(row[2],dict(id_funcionario=row[2],nome=row[3] or 'Sem profissional',quantidade=0,realizados=0,valor=ZERO))
        group['quantidade']+=1;group['realizados']+=row[5]=='concluido'
        if row[5]=='concluido' and row[6] is not None:group['valor']+=dinheiro(row[6])
        if row[5] in ('cancelado','faltou'):continue
        hours[row[4].strftime('%H:00')]+=1
        snapshot=js(row[7],[])
        if not isinstance(snapshot,list):snapshot=[]
        if not snapshot:
            ids=js(row[8],[])
            snapshot=[{'id_servico':id_,'nome':names.get(id_,'Serviço histórico'),'preco':None} for id_ in ids if isinstance(id_,int)] if isinstance(ids,list) else []
        for item in snapshot:
            if not isinstance(item,dict):continue
            id_=item.get('id_servico');service=services.setdefault(id_,dict(id_servico=id_,nome=item.get('nome') or names.get(id_,'Serviço histórico'),quantidade=0,valor=ZERO))
            service['quantidade']+=1
            if row[5]=='concluido' and item.get('preco') is not None:service['valor']+=dinheiro(item['preco'])
    for item in list(services.values())+list(staff.values()):item['valor']=float(item['valor'])
    entries=roster(cur,salon,a,b);all_clients=roster(cur,salon)
    inactive_days=inteiro(request.args.get('inativos_dias','30'),'Dias de inatividade')
    summary={'agendamentos':len(rows),'realizados':sum(r[5]=='concluido' for r in rows),'cancelados':sum(r[5]=='cancelado' for r in rows),
        'faltas':sum(r[5]=='faltou' for r in rows),'valor_realizado':float(sum((dinheiro(r[6]) for r in rows if r[5]=='concluido' and r[6] is not None),ZERO)),
        'clientes':len(entries),'valores_historicos_ausentes':sum(r[5]=='concluido' and r[6] is None for r in rows)}
    return jsonify(inicio=iso(a),fim=iso(b),resumo=summary,servicos=sorted(services.values(),key=lambda x:-x['quantidade']),profissionais=list(staff.values()),
        horarios=[{'hora':hour,'quantidade':qty} for hour,qty in hours.most_common()],clientes=sorted(entries,key=lambda x:-x['atendimentos_realizados']),
        inativos=[c for c in all_clients if c['dias_inativo'] is None or c['dias_inativo']>=inactive_days])


@app.route('/gestao/financeiro/categorias',methods=['GET','POST'])
@protegido()
def categorias(user,salon,cur,con):
    if request.method=='POST':
        data=request.get_json(silent=True) or {};name=texto(data.get('nome'),100,'Nome',False);kind=data.get('tipo')
        if kind not in ('entrada','saida'):raise ValueError('Categoria deve ser entrada ou saída.')
        travar_salao(cur,salon)
        cur.execute('SELECT ID_CATEGORIA FROM GESTAO_CATEGORIA WHERE ID_BARBEARIA=? AND UPPER(NOME)=? AND TIPO=? AND ATIVO=1',(salon,name.upper(),kind))
        if cur.fetchone():raise Conflito('Já existe uma categoria ativa com este nome e tipo.')
        cur.execute('INSERT INTO GESTAO_CATEGORIA(ID_CATEGORIA,ID_BARBEARIA,NOME,TIPO) VALUES(NEXT VALUE FOR SEQ_GESTAO_CATEGORIA,?,?,?) RETURNING ID_CATEGORIA',(salon,name,kind))
        id_=cur.fetchone()[0];con.commit();auditar(cur,user,'INSERT','GESTAO_CATEGORIA','ID_CATEGORIA',id_)
    cur.execute('SELECT ID_CATEGORIA,NOME,TIPO,ATIVO FROM GESTAO_CATEGORIA WHERE ID_BARBEARIA=? ORDER BY NOME',(salon,))
    return jsonify(categorias=[dict(id_categoria=r[0],nome=r[1],tipo=r[2],ativo=r[3]==1) for r in cur.fetchall()]),201 if request.method=='POST' else 200


@app.delete('/gestao/financeiro/categorias/<int:id_categoria>')
@protegido()
def cancelar_categoria(user,salon,cur,con,id_categoria):
    cur.execute('SELECT ID_CATEGORIA FROM GESTAO_CATEGORIA WHERE ID_CATEGORIA=? AND ID_BARBEARIA=? WITH LOCK',(id_categoria,salon))
    if not cur.fetchone():return erro('Categoria não encontrada.',404)
    before=capturar_registro(cur,'GESTAO_CATEGORIA','ID_CATEGORIA',id_categoria)
    cur.execute('UPDATE GESTAO_CATEGORIA SET ATIVO=0 WHERE ID_CATEGORIA=?',(id_categoria,));con.commit();auditar(cur,user,'UPDATE','GESTAO_CATEGORIA','ID_CATEGORIA',id_categoria,before)
    return mensagem_json('Categoria desativada. O histórico permanece disponível.', 'sucesso')


def lancamentos_dados(cur,salon):
    cur.execute('''SELECT L.ID_LANCAMENTO,L.TIPO,L.ID_CATEGORIA,C.NOME,L.DESCRICAO,L.VALOR,L.VENCIMENTO,L.STATUS,L.DATA_PAGAMENTO,L.CRIADO_EM,P.ID_PAGAMENTO
        FROM GESTAO_LANCAMENTO L LEFT JOIN GESTAO_CATEGORIA C ON C.ID_CATEGORIA=L.ID_CATEGORIA
        LEFT JOIN GESTAO_COMISSAO_PAGAMENTO P ON P.ID_LANCAMENTO=L.ID_LANCAMENTO WHERE L.ID_BARBEARIA=?''',(salon,))
    items=[dict(id_lancamento=r[0],tipo=r[1],categoria_id=r[2],categoria_nome=r[3],descricao=r[4],valor=float(r[5]),vencimento=iso(r[6]),status=r[7],data_pagamento=iso(r[8]),criado_em=iso(r[9]),origem='comissao' if r[10] else 'manual',editavel=not bool(r[10])) for r in cur.fetchall()]
    financial=financeiro_reservas(cur,salon)
    cur.execute('SELECT ID_AGENDAMENTO,VALOR_TOTAL,STATUS FROM AGENDAMENTO WHERE ID_BARBEARIA=?',(salon,))
    booked_values={r[0]:(r[1],r[2]) for r in cur.fetchall()};confirmed=defaultdict(lambda:ZERO);pending={}
    for row in financial:
        booking=id_descricao(row[3])
        if row[2] in PAGOS:confirmed[booking]+=dinheiro(row[4] or 0)
        elif str(row[2]).endswith('_pendente'):pending[booking]=row
    for row in financial:
        if row[2] not in PAGOS and not str(row[2]).endswith('_pendente'):continue
        booking=id_descricao(row[3]);value=dinheiro(row[4] or 0)
        if row[2] not in PAGOS:
            if pending[booking][0]!=row[0]:continue
            expected,booking_status=booked_values.get(booking,(None,None))
            if booking_status in ('cancelado','faltou'):continue
            value=max(ZERO,dinheiro(expected if expected is not None else value)-confirmed[booking])
            if not value:continue
        items.append(dict(id_lancamento=None,id_financeiro=row[0],tipo='entrada',categoria_id=None,categoria_nome='Atendimentos',descricao=row[3],valor=float(value),
            vencimento=iso(row[5].date()) if row[5] else None,status='pago' if row[2] in PAGOS else 'pendente',data_pagamento=iso(row[5].date()) if row[5] and row[2] in PAGOS else None,
            criado_em=iso(row[5]),origem='agendamento',editavel=False,id_agendamento=id_descricao(row[3])))
    return items


def normalizar_lancamento(cur,salon,data,old=None):
    merged={**(old or {}),**data};kind=merged.get('tipo');status=merged.get('status','pendente')
    if kind not in ('entrada','saida'):raise ValueError('Tipo deve ser entrada ou saída.')
    if status not in ('pendente','pago','cancelado'):raise ValueError('Status deve ser pendente, pago ou cancelado.')
    value=dinheiro(merged.get('valor'),True);desc=texto(merged.get('descricao'),500,'Descrição',False)
    due=dia(merged.get('vencimento'),date.today());paid=dia(merged.get('data_pagamento'),date.today() if status=='pago' else None)
    if status!='pago':paid=None
    if paid and paid>date.today():raise ValueError('Data de pagamento não pode estar no futuro.')
    category=merged.get('categoria_id')
    if category not in (None,''):
        category=inteiro(category,'Categoria');cur.execute('SELECT TIPO,ATIVO FROM GESTAO_CATEGORIA WHERE ID_CATEGORIA=? AND ID_BARBEARIA=?',(category,salon));cat=cur.fetchone()
        # A preserved historical category may be inactive; assigning a different one may not.
        if not cat or cat[0]!=kind or (cat[1]!=1 and (not old or old.get('categoria_id')!=category)):raise ValueError('Categoria inválida para esta barbearia e tipo.')
    else:category=None
    return kind,category,desc,value,due,status,paid


@app.route('/gestao/financeiro/lancamentos',methods=['GET','POST'])
@protegido()
def lancamentos(user,salon,cur,con):
    if request.method=='POST':
        values=normalizar_lancamento(cur,salon,request.get_json(silent=True) or {})
        cur.execute('''INSERT INTO GESTAO_LANCAMENTO(ID_LANCAMENTO,ID_BARBEARIA,TIPO,ID_CATEGORIA,DESCRICAO,VALOR,VENCIMENTO,STATUS,DATA_PAGAMENTO)
            VALUES(NEXT VALUE FOR SEQ_GESTAO_LANCAMENTO,?,?,?,?,?,?,?,?) RETURNING ID_LANCAMENTO''',(salon,*values));id_=cur.fetchone()[0]
        con.commit();auditar(cur,user,'INSERT','GESTAO_LANCAMENTO','ID_LANCAMENTO',id_)
    a,b=periodo(False);items=lancamentos_dados(cur,salon)
    if a:items=[r for r in items if (r['data_pagamento'] or r['vencimento']) and a.isoformat()<=(r['data_pagamento'] or r['vencimento'])<=b.isoformat()]
    if request.args.get('status'):items=[r for r in items if r['status']==request.args['status']]
    if request.args.get('tipo'):items=[r for r in items if r['tipo']==request.args['tipo']]
    return jsonify(lancamentos=sorted(items,key=lambda r:r['criado_em'] or '',reverse=True)),201 if request.method=='POST' else 200


@app.put('/gestao/financeiro/lancamentos/<int:id_lancamento>')
@protegido()
def editar_lancamento(user,salon,cur,con,id_lancamento):
    cur.execute('SELECT ID_LANCAMENTO FROM GESTAO_LANCAMENTO WHERE ID_LANCAMENTO=? AND ID_BARBEARIA=? WITH LOCK',(id_lancamento,salon))
    if not cur.fetchone():return erro('Lançamento não encontrado.',404)
    old=next(r for r in lancamentos_dados(cur,salon) if r['id_lancamento']==id_lancamento)
    if not old['editavel']:return erro('Pagamento de comissão é histórico vinculado e não pode ser alterado neste formulário.',409)
    before=capturar_registro(cur,'GESTAO_LANCAMENTO','ID_LANCAMENTO',id_lancamento)
    values=normalizar_lancamento(cur,salon,request.get_json(silent=True) or {},old)
    cur.execute('''UPDATE GESTAO_LANCAMENTO SET TIPO=?,ID_CATEGORIA=?,DESCRICAO=?,VALOR=?,VENCIMENTO=?,STATUS=?,DATA_PAGAMENTO=?,ATUALIZADO_EM=CURRENT_TIMESTAMP
        WHERE ID_LANCAMENTO=?''',(*values,id_lancamento));con.commit();auditar(cur,user,'UPDATE','GESTAO_LANCAMENTO','ID_LANCAMENTO',id_lancamento,before)
    return jsonify(lancamento=next(r for r in lancamentos_dados(cur,salon) if r['id_lancamento']==id_lancamento))


def totais_financeiro(items,a,b):
    totals={k:ZERO for k in ('receitas','despesas','pendentes_receber','pendentes_pagar')}
    selected=[]
    for item in items:
        when=item['data_pagamento'] if item['status']=='pago' else item['vencimento']
        if not when or not a.isoformat()<=when<=b.isoformat() or item['status']=='cancelado':continue
        value=dinheiro(item['valor']);key=('receitas' if item['tipo']=='entrada' else 'despesas') if item['status']=='pago' else ('pendentes_receber' if item['tipo']=='entrada' else 'pendentes_pagar')
        totals[key]+=value;selected.append(item)
    totals['lucro']=totals['receitas']-totals['despesas'];totals['pendentes']=totals['pendentes_receber']+totals['pendentes_pagar']
    return {k:float(v) for k,v in totals.items()},selected


@app.get('/gestao/financeiro/resumo')
@protegido()
def resumo_financeiro(user,salon,cur,con):
    a,b=periodo();group=request.args.get('agrupamento','dia')
    if group not in ('dia','semana','mes'):raise ValueError('Agrupamento deve ser dia, semana ou mês.')
    items=lancamentos_dados(cur,salon);totals,selected=totais_financeiro(items,a,b)
    span=(b-a).days+1;prior_end=a-timedelta(days=1);prior_start=prior_end-timedelta(days=span-1)
    prior,_=totais_financeiro(items,prior_start,prior_end);comparison={k:prior[k] for k in ('receitas','despesas','lucro')}
    comparison.update(inicio=iso(prior_start),fim=iso(prior_end))
    for key in ('receitas','despesas','lucro'):comparison['variacao_'+key]=round((totals[key]-prior[key])/abs(prior[key])*100,2) if prior[key] else None
    series={}
    for item in selected:
        if item['status']!='pago':continue
        when=date.fromisoformat(item['data_pagamento']);week=when.isocalendar()
        key=when.isoformat() if group=='dia' else f'{week.year}-W{week.week:02}' if group=='semana' else when.strftime('%Y-%m')
        entry=series.setdefault(key,dict(periodo=key,receitas=ZERO,despesas=ZERO, lucro=ZERO));entry['receitas' if item['tipo']=='entrada' else 'despesas']+=dinheiro(item['valor'])
    for entry in series.values():entry['lucro']=entry['receitas']-entry['despesas'];entry.update({k:float(entry[k]) for k in ('receitas','despesas','lucro')})
    return jsonify(inicio=iso(a),fim=iso(b),resumo=totals,comparacao=comparison,serie=[series[k] for k in sorted(series)])


def repetir_operacao(cur,salon,kind,ref,data):
    key=data.get('chave_idempotencia')
    if not key:return None,False
    key=texto(key,64,'Chave de idempotência',False)
    digest=hashlib.sha256(json.dumps({k:v for k,v in data.items() if k!='chave_idempotencia'},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    cur.execute('SELECT TIPO,ID_REFERENCIA,HASH_PEDIDO FROM GESTAO_OPERACAO WHERE ID_BARBEARIA=? AND CHAVE=?',(salon,key));old=cur.fetchone()
    if old and (old[0]!=kind or old[1]!=ref or old[2].strip()!=digest):raise Conflito('Esta chave de idempotência já foi usada para outra operação.')
    return (key,digest),bool(old)


def salvar_operacao(cur,salon,kind,ref,operation):
    if operation:cur.execute('INSERT INTO GESTAO_OPERACAO(ID_BARBEARIA,CHAVE,TIPO,ID_REFERENCIA,HASH_PEDIDO) VALUES(?,?,?,?,?)',(salon,operation[0],kind,ref,operation[1]))


def estado_recebimentos(cur,salon,row):
    financial=[f for f in financeiro_reservas(cur,salon) if id_descricao(f[3])==row[0] and f[2] in PAGOS]
    received=sum((dinheiro(f[4]) for f in financial),ZERO);total=dinheiro(row[7]) if row[7] is not None else None
    from taxa_plataforma import resumo_registrado
    resumo=resumo_registrado(cur,'agendamento',row[0],total,status=row[6])
    if resumo:total=dinheiro(resumo['valor_total_cliente'])
    cur.execute('''SELECT ID_RECEBIMENTO,ID_FINANCEIRO,FORMA,VALOR,DATA_PAGAMENTO,OBSERVACAO FROM GESTAO_RECEBIMENTO
        WHERE ID_BARBEARIA=? AND ID_AGENDAMENTO=? ORDER BY DATA_PAGAMENTO,ID_RECEBIMENTO''',(salon,row[0]));local=cur.fetchall()
    local_ids={r[1] for r in local}
    payments=[dict(id_recebimento=r[0],id_financeiro=r[1],forma=r[2],valor=float(r[3]),data_pagamento=iso(r[4]),observacao=r[5] or '') for r in local]
    payments.extend(dict(id_recebimento=None,id_financeiro=f[0],forma='legado',valor=float(f[4]),data_pagamento=iso(f[5]),observacao=f[2]) for f in financial if f[0] not in local_ids)
    return dict(id_agendamento=row[0],valor_total=float(total) if total is not None else None,valor_recebido=float(received),saldo=float(max(ZERO,total-received)) if total is not None else None,pagamentos=payments,resumo=resumo)


@app.get('/gestao/taxas-plataforma')
@protegido()
def taxas_plataforma(user,salon,cur,con):
    a,b=periodo(False)
    cur.execute('''SELECT T.TIPO,T.ID_OPERACAO,T.ID_ATOR,T.ID_CLIENTE,T.VALOR_BASE,T.FRETE,
        T.PERCENTUAL,T.VALOR_TAXA,T.PAGADOR,T.TOTAL_CLIENTE,T.LIQUIDO_BARBEARIA,T.TERMOS_VERSAO,
        T.CRIADO_EM,A.STATUS,P.STATUS,P.PAGAMENTO_STATUS
        FROM PLATAFORMA_TAXA T
        LEFT JOIN AGENDAMENTO A ON T.TIPO='agendamento' AND A.ID_AGENDAMENTO=T.ID_OPERACAO
        LEFT JOIN MP_PEDIDO P ON T.TIPO='pedido' AND P.ID_PEDIDO=T.ID_OPERACAO
        WHERE T.ID_BARBEARIA=? ORDER BY T.CRIADO_EM DESC,T.ID_OPERACAO DESC''',(salon,))
    rows=cur.fetchall();items=[]
    for row in rows:
        if a and not a<=row[12].date()<=b:continue
        status=row[13] if row[0]=='agendamento' else row[14]
        applicable=status not in ('cancelado','faltou')
        item=dict(tipo=row[0],id_operacao=row[1],id_ator=row[2],id_cliente=row[3],valor_base=float(row[4]),
            frete=float(row[5]),taxa_percentual=float(row[6]),taxa_valor=float(row[7]),taxa_pagador=row[8],
            valor_total_cliente=float(row[9]),valor_liquido_barbearia=float(row[10]),termos_versao=row[11],
            criado_em=iso(row[12]),status=status,taxa_devida=float(row[7]) if applicable else 0.,
            repasse_automatico=False,repasse_confirmado=False)
        if row[0]=='pedido':paid=row[15]=='pago'
        else:
            booking=reserva(cur,salon,row[1])
            state=estado_recebimentos(cur,salon,booking) if booking else None
            paid=bool(state and state['valor_total'] is not None and state['valor_recebido']>=state['valor_total'])
        item.update(pagamento_cliente_confirmado=paid,
            situacao='anulada' if not applicable else 'aguardando_pagamento_cliente' if not paid else 'repasse_pendente')
        items.append(item)
    return jsonify(taxas=items,totais={'registradas':float(sum((dinheiro(i['taxa_valor']) for i in items),ZERO)),
        'previstas':float(sum((dinheiro(i['taxa_devida']) for i in items),ZERO)),
        'repasse_pendente':float(sum((dinheiro(i['taxa_devida']) for i in items if i['situacao']=='repasse_pendente'),ZERO))},
        repasse_automatico=False,informacao='Valores registrados para conferência. Nenhum repasse à plataforma é executado ou confirmado por este relatório.')


@app.route('/gestao/agendamentos/<int:id_agendamento>/recebimentos',methods=['GET','POST'])
@protegido()
def recebimentos(user,salon,cur,con,id_agendamento):
    row=reserva(cur,salon,id_agendamento,request.method=='POST')
    if not row:return erro('Agendamento não encontrado nesta barbearia.',404)
    if request.method=='GET':return jsonify(estado_recebimentos(cur,salon,row))
    data=request.get_json(silent=True) or {};operation,repeated=repetir_operacao(cur,salon,'recebimento',row[0],data)
    if repeated:return jsonify(estado_recebimentos(cur,salon,row))
    if row[6] in ('cancelado','faltou'):raise ValueError('Atendimento cancelado ou com falta não aceita recebimento.')
    if row[7] is None:raise ValueError('O atendimento não possui valor histórico. Informe o valor realizado pelo fluxo de atendimento.')
    dinheiro(row[7],True)
    paid_date=dia(data.get('data_pagamento'),date.today());note=texto(data.get('observacao'),500,'Observação')
    if paid_date>date.today():raise ValueError('Data de recebimento não pode estar no futuro.')
    entries=data.get('pagamentos')
    if not isinstance(entries,list) or not 1<=len(entries)<=10:raise ValueError('Informe de 1 a 10 formas de pagamento.')
    values=[]
    for entry in entries:
        if not isinstance(entry,dict) or entry.get('forma') not in ('dinheiro','cartao','pix_manual'):raise ValueError('Forma de pagamento inválida.')
        values.append((entry['forma'],dinheiro(entry.get('valor'),True)))
    state=estado_recebimentos(cur,salon,row);amount=sum((v for _,v in values),ZERO)
    if amount>dinheiro(state['saldo']):raise Conflito('O recebimento excede o saldo do atendimento.')
    ids=[];fin_ids=[]
    for form,value in values:
        cur.execute('SELECT NEXT VALUE FOR SEQ_GESTAO_RECEBIMENTO FROM RDB$DATABASE');id_=cur.fetchone()[0]
        description=f'ag#{row[0]}|gestao|{form}|{id_}'
        cur.execute('''INSERT INTO FINANCEIRO(ID_FINANCEIRO,ID_USUARIO,TIPO,DESCRICAO,VALOR,DATA_TRANSACAO)
            VALUES(NEXT VALUE FOR SEQ_FINANCEIRO,?,'na_hora',?,?,?) RETURNING ID_FINANCEIRO''',(row[1],description,value,datetime.combine(paid_date,time.min)));fin_id=cur.fetchone()[0]
        cur.execute('''INSERT INTO GESTAO_RECEBIMENTO(ID_RECEBIMENTO,ID_AGENDAMENTO,ID_BARBEARIA,ID_FINANCEIRO,FORMA,VALOR,DATA_PAGAMENTO,OBSERVACAO,ID_USUARIO_RESPONSAVEL)
            VALUES(?,?,?,?,?,?,?,?,?)''',(id_,row[0],salon,fin_id,form,value,paid_date,note,user['id_usuario']));ids.append(id_);fin_ids.append(fin_id)
    salvar_operacao(cur,salon,'recebimento',row[0],operation);con.commit()
    for id_ in ids:auditar(cur,user,'INSERT','GESTAO_RECEBIMENTO','ID_RECEBIMENTO',id_)
    for id_ in fin_ids:auditar(cur,user,'INSERT','FINANCEIRO','ID_FINANCEIRO',id_)
    return jsonify(estado_recebimentos(cur,salon,row)),201


def estado_comissoes(cur,salon,a=None,b=None):
    cur.execute('''SELECT C.ID_AGENDAMENTO,C.ID_FUNCIONARIO,F.NOME,C.VALOR_COMISSAO,A.INICIO_EM FROM COMISSAO_ATENDIMENTO C
        JOIN AGENDAMENTO A ON A.ID_AGENDAMENTO=C.ID_AGENDAMENTO LEFT JOIN FUNCIONARIO F ON F.ID_FUNCIONARIO=C.ID_FUNCIONARIO
        WHERE C.ID_BARBEARIA=? AND A.ID_BARBEARIA=? ORDER BY A.INICIO_EM DESC''',(salon,salon));ledgers=cur.fetchall()
    cur.execute('''SELECT P.ID_PAGAMENTO,P.ID_AGENDAMENTO,C.ID_FUNCIONARIO,F.NOME,P.VALOR,P.DATA_PAGAMENTO,P.OBSERVACAO,P.ID_LANCAMENTO
        FROM GESTAO_COMISSAO_PAGAMENTO P JOIN COMISSAO_ATENDIMENTO C ON C.ID_AGENDAMENTO=P.ID_AGENDAMENTO
        JOIN AGENDAMENTO A ON A.ID_AGENDAMENTO=C.ID_AGENDAMENTO LEFT JOIN FUNCIONARIO F ON F.ID_FUNCIONARIO=C.ID_FUNCIONARIO
        WHERE P.ID_BARBEARIA=? AND C.ID_BARBEARIA=? AND A.ID_BARBEARIA=? ORDER BY P.DATA_PAGAMENTO DESC,P.ID_PAGAMENTO DESC''',(salon,salon,salon));rows=cur.fetchall()
    sums=defaultdict(lambda:ZERO)
    for row in rows:sums[row[1]]+=dinheiro(row[4])
    commissions=[dict(id_agendamento=r[0],id_funcionario=r[1],nome_funcionario=r[2] or 'Profissional histórico',valor_comissao=float(r[3]),valor_pago=float(sums[r[0]]),saldo=float(max(ZERO,dinheiro(r[3])-sums[r[0]])),inicio_em=iso(r[4])) for r in ledgers if not a or a<=r[4].date()<=b]
    ids={c['id_agendamento'] for c in commissions}
    payments=[dict(id_pagamento=r[0],id_agendamento=r[1],id_funcionario=r[2],nome_funcionario=r[3],valor=float(r[4]),data_pagamento=iso(r[5]),observacao=r[6] or '',id_lancamento=r[7]) for r in rows if r[1] in ids]
    totals={k:float(sum((dinheiro(c[source]) for c in commissions),ZERO)) for k,source in (('valor_comissao','valor_comissao'),('valor_pago','valor_pago'),('saldo','saldo'))}
    return dict(pagamentos=payments,comissoes=commissions,totais=totals)


@app.route('/gestao/comissoes/pagamentos',methods=['GET','POST'])
@protegido()
def pagamentos_comissao(user,salon,cur,con):
    if request.method=='GET':
        a,b=periodo(False);return jsonify(estado_comissoes(cur,salon,a,b))
    data=request.get_json(silent=True) or {};id_=inteiro(data.get('id_agendamento'),'Agendamento')
    row=reserva(cur,salon,id_,True)
    if not row:return erro('Atendimento não encontrado nesta barbearia.',404)
    operation,repeated=repetir_operacao(cur,salon,'comissao',id_,data)
    if repeated:return jsonify(estado_comissoes(cur,salon))
    if row[6]!='concluido':raise ValueError('Somente atendimentos concluídos aceitam pagamento de comissão.')
    cur.execute('SELECT VALOR_COMISSAO,ID_FUNCIONARIO FROM COMISSAO_ATENDIMENTO WHERE ID_AGENDAMENTO=? AND ID_BARBEARIA=?',(id_,salon));ledger=cur.fetchone()
    if not ledger:return erro('Este atendimento não possui comissão registrada.',404)
    if ledger[1]!=row[3]:raise Conflito('O profissional atual difere do registro histórico de comissão.')
    value=dinheiro(data.get('valor'),True);paid_date=dia(data.get('data_pagamento'),date.today());note=texto(data.get('observacao'),500,'Observação')
    if paid_date>date.today():raise ValueError('Data de pagamento não pode estar no futuro.')
    cur.execute('SELECT COALESCE(SUM(VALOR),0) FROM GESTAO_COMISSAO_PAGAMENTO WHERE ID_AGENDAMENTO=? AND ID_BARBEARIA=?',(id_,salon));paid=dinheiro(cur.fetchone()[0])
    if value>dinheiro(ledger[0])-paid:raise Conflito('O pagamento excede a comissão pendente.')
    cur.execute('''INSERT INTO GESTAO_LANCAMENTO(ID_LANCAMENTO,ID_BARBEARIA,TIPO,DESCRICAO,VALOR,VENCIMENTO,STATUS,DATA_PAGAMENTO)
        VALUES(NEXT VALUE FOR SEQ_GESTAO_LANCAMENTO,?,'saida',?,?,?,'pago',?) RETURNING ID_LANCAMENTO''',(salon,f'Pagamento manual de comissão do atendimento #{id_}',value,paid_date,paid_date));expense_id=cur.fetchone()[0]
    cur.execute('''INSERT INTO GESTAO_COMISSAO_PAGAMENTO(ID_PAGAMENTO,ID_AGENDAMENTO,ID_BARBEARIA,ID_LANCAMENTO,VALOR,DATA_PAGAMENTO,OBSERVACAO,ID_USUARIO_RESPONSAVEL)
        VALUES(NEXT VALUE FOR SEQ_GESTAO_COMISSAO_PAG,?,?,?,?,?,?,?) RETURNING ID_PAGAMENTO''',(id_,salon,expense_id,value,paid_date,note,user['id_usuario']));payment_id=cur.fetchone()[0]
    salvar_operacao(cur,salon,'comissao',id_,operation);con.commit()
    auditar(cur,user,'INSERT','GESTAO_COMISSAO_PAGAMENTO','ID_PAGAMENTO',payment_id);auditar(cur,user,'INSERT','GESTAO_LANCAMENTO','ID_LANCAMENTO',expense_id)
    return jsonify(estado_comissoes(cur,salon)),201
