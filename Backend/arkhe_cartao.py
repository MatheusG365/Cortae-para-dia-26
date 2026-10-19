"""Virtual-card sales: durable local reservation and strictly safe provider results.

No PAN, CVV, PIN, provider error body or complete request enters persistence or logs.
Callers hold the target row lock before reserving. There is no automatic retry.
"""
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

from flask import current_app, jsonify


MANUAL = 'Confira manualmente o recebimento na Arkhé antes de qualquer nova cobrança. A operação não será repetida automaticamente.'
SAFE_FIELDS = ('aprovado', 'id_compra', 'id_movimentacao', 'valor', 'valor_recebido',
               'taxa', 'tipo', 'parcelas', 'final_cartao', 'data_compra')


class CartaoErro(ValueError):
    def __init__(self, mensagem, status=400, estado=None):
        super().__init__(mensagem)
        self.status = status
        self.estado = estado


class _SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# A dedicated opener neither retries POST nor forwards credentials through redirects.
urlopen = build_opener(ProxyHandler({}), _SemRedirecionamento()).open


def _moeda(value, positivo=False):
    try:
        if isinstance(value, bool):
            raise ValueError()
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > Decimal('9999999999.99'):
            raise ValueError()
        rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if amount != rounded or (positivo and rounded <= 0):
            raise ValueError()
        return rounded
    except (ValueError, TypeError, InvalidOperation):
        raise CartaoErro('Valor de pagamento inválido.') from None


def validar_cartao(dados, valor):
    if not isinstance(dados, dict):
        raise CartaoErro('Envie um objeto JSON válido.')
    # Reject rather than accidentally forwarding PIN or unsupported authentication.
    if any(str(key).lower() in ('pin', 'senha', 'password') for key in dados):
        raise CartaoErro('Não envie PIN nem senha pessoal do cartão.')
    pan, expiry, cvv = (dados.get(field) for field in ('numero_cartao', 'validade', 'cvv'))
    if not isinstance(pan, str) or not re.fullmatch(r'[0-9]{16}', pan):
        raise CartaoErro('Número do cartão deve conter 16 dígitos como texto.')
    if not isinstance(cvv, str) or not re.fullmatch(r'[0-9]{3}', cvv):
        raise CartaoErro('CVV deve conter 3 dígitos como texto.')
    if not isinstance(expiry, str) or not re.fullmatch(r'(0[1-9]|1[0-2])/[0-9]{4}', expiry):
        raise CartaoErro('Validade deve estar no formato MM/YYYY.')
    month, year = map(int, expiry.split('/'))
    today = date.today()
    if (year, month) < (today.year, today.month):
        raise CartaoErro('Cartão vencido.')
    kind, count = dados.get('tipo', 'DEBITO'), dados.get('parcelas', 1)
    if kind not in ('DEBITO', 'CREDITO'):
        raise CartaoErro('Tipo deve ser DEBITO ou CREDITO.')
    if type(count) is not int or not 1 <= count <= (1 if kind == 'DEBITO' else 15):
        raise CartaoErro('Débito aceita uma parcela; crédito aceita de 1 a 15 parcelas.')
    gross = _moeda(valor, True)
    if gross < Decimal(count) / 100:
        raise CartaoErro('Cada parcela deve ter pelo menos um centavo.')
    return dict(numero_cartao=pan, validade=expiry, cvv=cvv, tipo=kind,
                parcelas=count, valor=float(gross))


def validar_resultado(data, payload):
    """Only a complete, coherent approval is proof. Never return provider extras."""
    try:
        if not isinstance(data, dict) or data.get('aprovado') is not True:
            raise ValueError()
        for field in ('id_compra', 'id_movimentacao'):
            if type(data.get(field)) is not int or not 1 <= data[field] <= 2147483647:
                raise ValueError()
        gross = _moeda(payload['valor'], True)
        net = _moeda(data.get('valor_recebido'))
        fee = _moeda(data.get('taxa'))
        if payload['tipo'] == 'CREDITO':
            # The API does not specify which side rounds a half-cent. Accept
            # only these two deterministic 5% allocations, never a tolerance.
            fee_candidates = {
                (gross * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                gross - (gross * Decimal('0.95')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            }
        else:
            fee_candidates = {Decimal('0.00')}
        if (_moeda(data.get('valor'), True) != gross or
                net + fee != gross or fee not in fee_candidates or
                data.get('tipo') != payload['tipo'] or type(data.get('parcelas')) is not int or
                data['parcelas'] != payload['parcelas'] or
                data.get('final_cartao') != payload['numero_cartao'][-4:]):
            raise ValueError()
        stamp = data.get('data_compra')
        if not isinstance(stamp, str) or len(stamp) > 40 or 'T' not in stamp:
            raise ValueError()
        datetime.fromisoformat(stamp)
        return {field: data[field] for field in SAFE_FIELDS}
    except Exception:
        raise CartaoErro('Resultado do cartão não pôde ser confirmado. ' + MANUAL, 502, 'incerto') from None


def preparar_conexao(credenciais):
    base = (current_app.config.get('ARKHE_BASE_URL') or '').strip().rstrip('/')
    parsed = urlsplit(base)
    if not parsed.netloc or parsed.scheme != 'https' or parsed.username or parsed.password:
        raise CartaoErro('Configure ARKHE_BASE_URL HTTPS no servidor.', 503)
    if not credenciais or len(credenciais) != 2 or not all(credenciais):
        raise CartaoErro('Conta Arkhé da barbearia não configurada.', 503)
    return base


def vender_cartao(payload, credenciais):
    base = preparar_conexao(credenciais)
    try:
        req = Request(base + '/api/v1/vendas/cartao',
                      data=json.dumps(payload).encode('utf-8'), method='POST',
                      headers={'X-Client-ID': credenciais[0], 'X-Client-Secret': credenciais[1],
                               'Content-Type': 'application/json', 'Accept': 'application/json'})
        with urlopen(req, timeout=20) as response:
            if response.status not in (200, 201):
                raise CartaoErro('Resposta não confirmada. ' + MANUAL, 502, 'incerto')
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError()
            result = json.loads(raw.decode('utf-8'))
        if isinstance(result, dict) and result.get('aprovado') is False:
            raise CartaoErro('Venda recusada pela Arkhé. Confira os dados antes de tentar novamente.', 400, 'recusado')
        return validar_resultado(result, payload)
    except HTTPError as exc:
        # Do not read or interpolate an error body: it may echo card credentials.
        if exc.code in (400, 401, 403, 404, 422):
            raise CartaoErro('Venda recusada pela Arkhé. Confira os dados e a integração antes de tentar novamente.', 400, 'recusado') from None
        raise CartaoErro('Não foi possível confirmar a venda. ' + MANUAL, 502, 'incerto') from None
    except CartaoErro:
        raise
    except Exception:
        raise CartaoErro('Não foi possível confirmar a venda. ' + MANUAL, 502, 'incerto') from None


def obter_tentativa(cur, tipo_alvo, id_alvo):
    try:
        cur.execute('SELECT ESTADO,RESULTADO,VALOR,TIPO,PARCELAS FROM PAGAMENTO_CARTAO WHERE TIPO_ALVO=? AND ID_ALVO=?', (tipo_alvo, id_alvo))
        row = cur.fetchone()
        if not row:
            return None
        return dict(estado=row[0], resultado=json.loads(str(row[1])) if row[1] else None,
                    valor=row[2], tipo=row[3], parcelas=row[4])
    except Exception:
        raise CartaoErro('Estrutura de pagamentos indisponível. Execute a migração manual após backup.', 503) from None


def bloquear_outro_pagamento(cur, tipo_alvo, id_alvo):
    attempt = obter_tentativa(cur, tipo_alvo, id_alvo)
    if attempt and attempt['estado'] in ('processando', 'incerto', 'aprovado'):
        raise CartaoErro('Este pedido já possui uma tentativa de cartão. ' + MANUAL, 409, attempt['estado'])
    return attempt


def reservar_tentativa(cur, tipo_alvo, id_alvo, usuario, barbearia, payload):
    prior = obter_tentativa(cur, tipo_alvo, id_alvo)
    if prior and prior['estado'] == 'aprovado':
        return prior['resultado']
    if prior and prior['estado'] != 'recusado':
        raise CartaoErro('Tentativa de cartão em processamento ou sem confirmação. ' + MANUAL, 409, prior['estado'])
    if prior:
        cur.execute("UPDATE PAGAMENTO_CARTAO SET ESTADO='processando',RESULTADO=NULL,ID_COMPRA=NULL,ID_MOVIMENTACAO=NULL,VALOR=?,TIPO=?,PARCELAS=?,ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE TIPO_ALVO=? AND ID_ALVO=?",
                    (payload['valor'], payload['tipo'], payload['parcelas'], tipo_alvo, id_alvo))
    else:
        cur.execute("INSERT INTO PAGAMENTO_CARTAO(TIPO_ALVO,ID_ALVO,ID_USUARIO,ID_BARBEARIA,ESTADO,VALOR,TIPO,PARCELAS) VALUES(?,?,?,?,'processando',?,?,?)",
                    (tipo_alvo, id_alvo, usuario, barbearia, payload['valor'], payload['tipo'], payload['parcelas']))
    return None


def finalizar_tentativa(cur, tipo_alvo, id_alvo, estado, resultado=None):
    safe = {key: resultado[key] for key in SAFE_FIELDS} if resultado else None
    cur.execute('UPDATE PAGAMENTO_CARTAO SET ESTADO=?,RESULTADO=?,ID_COMPRA=?,ID_MOVIMENTACAO=?,ATUALIZADO_EM=CURRENT_TIMESTAMP WHERE TIPO_ALVO=? AND ID_ALVO=?',
                (estado, json.dumps(safe, separators=(',', ':')) if safe else None,
                 safe['id_compra'] if safe else None, safe['id_movimentacao'] if safe else None,
                 tipo_alvo, id_alvo))


def executar_venda(cur, con, tipo_alvo, id_alvo, usuario, barbearia, payload, credenciais, confirmar):
    preparar_conexao(credenciais)
    prior = reservar_tentativa(cur, tipo_alvo, id_alvo, usuario, barbearia, payload)
    if prior:
        return prior
    # If this commit fails, do not send anything. If its outcome is ambiguous,
    # the persisted processando marker still prevents another card POST.
    try:
        con.commit()
    except Exception:
        con.rollback()
        raise CartaoErro('Não foi possível confirmar a reserva local. ' + MANUAL, 503, 'incerto') from None
    result = None
    try:
        result = vender_cartao(payload, credenciais)
        confirmar(result)
        finalizar_tentativa(cur, tipo_alvo, id_alvo, 'aprovado', result)
        con.commit()
        return result
    except Exception as exc:
        con.rollback()
        state = exc.estado if isinstance(exc, CartaoErro) and exc.estado in ('recusado', 'incerto') else 'incerto'
        # No financial record survives a failed finalization. Keep reservation
        # durable even if this best-effort state annotation cannot be committed.
        try:
            # Retain any proven provider IDs even when the local commit outcome
            # is uncertain. Clearing them could release uniqueness after a
            # successful-but-unacknowledged commit.
            finalizar_tentativa(cur, tipo_alvo, id_alvo, state, result)
            con.commit()
        except Exception:
            con.rollback()
        message = str(exc) if isinstance(exc, CartaoErro) else 'Venda sem confirmação local. ' + MANUAL
        raise CartaoErro(message, exc.status if isinstance(exc, CartaoErro) else 502, state) from None


def recibo(resultado):
    return {**{key: resultado[key] for key in SAFE_FIELDS}, 'metodo': 'cartao',
            'status': 1, 'cartao_estado': 'aprovado'}


def resposta_erro(exc):
    return jsonify(mensagem={'informacao': str(exc), 'tipo': 'erro'},
                   cartao_estado=exc.estado), exc.status
