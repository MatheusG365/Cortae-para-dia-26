"""Platform fee snapshots. No split, transfer or invented historical charge."""
from responses import mensagem_json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import hmac
import json
from flask import jsonify, request
from application import app, conectar_banco
from termos import documento_termos, versao_atual, exigir_aceite, AceitePendente
from funcoes import decodificar_token

PERCENTUAL = Decimal('1.50')


class ResumoAlterado(ValueError):
    status = 409


def resumo_confirmavel(base, frete, contexto):
    resumo = calcular(base,frete)
    material = json.dumps({'resumo':resumo,'contexto':contexto},sort_keys=True,separators=(',',':'),default=str)
    resumo['confirmacao_resumo'] = hmac.new(str(app.config['SECRET_KEY']).encode(),material.encode(),hashlib.sha256).hexdigest()
    return resumo


def confirmar_resumo(data, resumo):
    supplied = data.get('confirmacao_resumo')
    if (resumo['ativa'] or supplied is not None) and (not isinstance(supplied,str) or not hmac.compare_digest(supplied,resumo['confirmacao_resumo'])):
        raise ResumoAlterado('Os valores ou as condições mudaram. Confira o resumo atualizado antes de confirmar.')


def resumo_servicos(cur,salon,staff,services,ator=None,cliente=None):
    ids = sorted(service['id_servico'] for service in services)
    marks = ','.join('?' for _ in ids)
    cur.execute(f'SELECT ID_SERVICO,PRECO FROM SERVICO WHERE ID_USUARIO=? AND ID_SERVICO IN ({marks})',[salon,*ids])
    prices = {row[0]:monetario(row[1]) for row in cur.fetchall()}
    if len(prices)!=len(ids): raise ValueError('Preços dos serviços não disponíveis.')
    if staff:
        cur.execute(f'SELECT ID_SERVICO,PRECO FROM FUNCIONARIO_PRECO WHERE ID_FUNCIONARIO=? AND ID_SERVICO IN ({marks})',[staff,*ids])
        prices.update({row[0]:monetario(row[1]) for row in cur.fetchall()})
    result=resumo_confirmavel(sum(prices.values(),Decimal('0')),0,{
        'barbearia':salon,'funcionario':staff or None,'servicos':ids,'ator':ator,'cliente':cliente,
        'precos':[(id_,str(prices[id_])) for id_ in ids],
        'duracao':sum(service['duracao'] for service in services)})
    result['precos_servicos']=[{'id_servico':id_,'preco':float(prices[id_])} for id_ in ids]
    return result


def monetario(value):
    try:
        if isinstance(value, bool): raise ValueError('Valor monetário inválido.')
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal('9999999999.99'):
            raise ValueError('Valor monetário inválido.')
        return result.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Valor monetário inválido.') from exc


def calcular(base, frete=0, historico=False):
    base = monetario(base); frete = monetario(frete)
    policy = documento_termos(); active = bool(policy['taxa']['ativa'] and not historico)
    payer = policy['taxa']['pagador'] if active else 'pendente'
    fee = monetario(base * PERCENTUAL / 100) if active else Decimal('0.00')
    total = monetario(base + frete + (fee if payer == 'cliente' else 0))
    return {'valor_base': float(base), 'frete': float(frete), 'taxa_percentual': float(PERCENTUAL),
            'taxa_valor': float(fee), 'taxa_pagador': payer, 'valor_total_cliente': float(total),
            'valor_liquido_barbearia': float(base - (fee if payer == 'barbearia' else 0)),
            'ativa': active, 'termos_versao': versao_atual() if active else None,
            'repasse_automatico': False}


def exigir_aceites(cur, ator, cliente, barbearia):
    policy = documento_termos()
    if not policy['aceite_habilitado']: return
    exigir_aceite(cur, ator)
    payer = cliente if policy['taxa']['pagador'] == 'cliente' else barbearia
    try:
        exigir_aceite(cur, payer)
    except AceitePendente as exc:
        raise AceitePendente('O próprio cliente precisa aceitar os termos de uso antes de reservar em seu nome.'
            if policy['taxa']['pagador']=='cliente' else
            'O titular da barbearia precisa aceitar os termos de uso antes de receber operações com esta taxa.') from exc


def registrar_taxa(cur, tipo, id_, base, frete, ator, cliente, barbearia):
    resumo = calcular(base, frete)
    if not resumo['ativa']: return resumo
    exigir_aceites(cur, ator, cliente, barbearia)
    cur.execute('SELECT TIPO FROM PLATAFORMA_TAXA WHERE TIPO=? AND ID_OPERACAO=?', (tipo, id_))
    if cur.fetchone(): raise ValueError('A taxa desta operação já foi registrada.')
    cur.execute('''INSERT INTO PLATAFORMA_TAXA(TIPO,ID_OPERACAO,ID_ATOR,ID_CLIENTE,ID_BARBEARIA,
        VALOR_BASE,FRETE,PERCENTUAL,VALOR_TAXA,PAGADOR,TOTAL_CLIENTE,LIQUIDO_BARBEARIA,TERMOS_VERSAO)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (tipo,id_,ator,cliente,barbearia,monetario(base),monetario(frete),PERCENTUAL,
            monetario(resumo['taxa_valor']),resumo['taxa_pagador'],monetario(resumo['valor_total_cliente']),
            monetario(resumo['valor_liquido_barbearia']),resumo['termos_versao']))
    return resumo


def resumo_registrado(cur, tipo, id_, base, frete=0, status=None):
    cur.execute('''SELECT VALOR_BASE,FRETE,PERCENTUAL,VALOR_TAXA,PAGADOR,TOTAL_CLIENTE,
        LIQUIDO_BARBEARIA,TERMOS_VERSAO FROM PLATAFORMA_TAXA WHERE TIPO=? AND ID_OPERACAO=?''', (tipo,id_))
    row = cur.fetchone()
    if not row:
        return calcular(base,frete,historico=True) if base is not None else None
    result = dict(zip(('valor_base','frete','taxa_percentual','taxa_valor','taxa_pagador',
        'valor_total_cliente','valor_liquido_barbearia','termos_versao'),row))
    for field in ('valor_base','frete','taxa_percentual','taxa_valor','valor_total_cliente','valor_liquido_barbearia'):
        result[field] = float(result[field])
    void=status in ('cancelado','faltou')
    result.update(ativa=not void, repasse_automatico=False,
        taxa_devida=0.0 if void else result['taxa_valor'])
    return result


@app.post('/agendamentos/resumo')
def resumo_agendamento():
    user = decodificar_token()
    if not user: return mensagem_json('Faça login.', 'erro'),401
    con = conectar_banco(); cur = con.cursor()
    try:
        from visagismo import ids_servicos_da_requisicao, carregar_servicos, buscar_funcionario, servicos_do_funcionario
        data = request.get_json(silent=True) or {}
        from gestao import inteiro
        salon = inteiro(data.get('id_barbearia')); staff = inteiro(data.get('id_funcionario')) if data.get('id_funcionario') else None
        role_user=int(user['tipo'])
        if role_user not in (0,1,2,3):raise ValueError('Sem permissão.')
        cliente=user['id_usuario'] if role_user==1 else inteiro(data.get('id_cliente'),'Cliente')
        if role_user==2 and salon!=user['id_usuario']:raise ValueError('Barbearia inválida para a conta.')
        if role_user==3:
            from agenda_equipe import funcionario_logado
            fun=funcionario_logado(cur,user)
            if not fun or salon!=fun[1] or (staff and staff!=fun[0]):raise ValueError('Agenda não autorizada.')
            staff=fun[0]
        cur.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=1 AND ATIVO=1',(cliente,))
        if not cur.fetchone():raise ValueError('Cliente não disponível.')
        ids = ids_servicos_da_requisicao(data)
        cur.execute('SELECT TIPO FROM USUARIO WHERE ID_USUARIO=? AND ATIVO=1 AND EMAIL_CONFIRMADO=1',(salon,))
        role = cur.fetchone()
        if not role or role[0] != 2: raise ValueError('Barbearia não disponível.')
        services = carregar_servicos(cur,salon,ids)
        if not services: raise ValueError('Selecione serviços disponíveis.')
        if staff and (not buscar_funcionario(cur,salon,staff) or not set(ids) <= servicos_do_funcionario(cur,salon,staff)):
            raise ValueError('Profissional inválido para os serviços selecionados.')
        return jsonify(resumo=resumo_servicos(cur,salon,staff,services,user['id_usuario'],cliente))
    except (ValueError,TypeError):
        return mensagem_json('Não foi possível calcular: confira barbearia, profissional e serviços.', 'erro'),400
    finally:
        cur.close(); con.close()
