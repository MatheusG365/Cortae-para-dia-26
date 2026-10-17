"""Pagamentos vinculados aos agendamentos usando a API Arkhé.

Cada barbearia utiliza o seu próprio Client ID e Client Secret da Arkhé,
armazenados na tabela PERSONALIZACAO.

As credenciais nunca são enviadas para o frontend.
"""

from responses import mensagem_json
from financial_reference import id_agendamento_descricao
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import jsonify, request

from application import app, conectar_banco
from barbearia import obter_usuario_logado, pegar_id_barbearia_alvo
from visagismo import buscar_agendamento, pode_ver_agendamento
from auditoria import registrar_log


TIMEOUT_ARKHE = 20


# ============================================================
# RESPOSTAS
# ============================================================

def resposta_erro(texto, status=400):
    return mensagem_json(texto, 'erro'), status


# ============================================================
# CREDENCIAIS ARKHÉ
# ============================================================

def _credenciais_da_barbearia(id_barbearia):
    """
    Busca Client ID e Client Secret da Arkhé da barbearia.

    PERSONALIZACAO.ID_USUARIO corresponde ao ID da barbearia.
    """

    if not id_barbearia:
        raise RuntimeError(
            'Não foi possível identificar a barbearia do agendamento.'
        )

    con = conectar_banco()
    cursor = con.cursor()

    try:
        cursor.execute(
            """
            SELECT
                ARKHE_CLIENT_ID,
                ARKHE_CLIENT_SECRET
            FROM PERSONALIZACAO
            WHERE ID_USUARIO = ?
            """,
            (int(id_barbearia),)
        )

        linha = cursor.fetchone()

    finally:
        cursor.close()
        con.close()

    if not linha:
        raise RuntimeError(
            'A barbearia ainda não possui personalização cadastrada.'
        )

    client_id = str(linha[0] or '').strip()
    client_secret = str(linha[1] or '').strip()

    if not client_id or not client_secret:
        raise RuntimeError(
            'A barbearia não configurou a integração com a Arkhé. '
            'Cadastre o Client ID e o Client Secret.'
        )

    return client_id, client_secret


def _cabecalhos(id_barbearia):
    """
    Monta os headers utilizando as credenciais da barbearia
    responsável pelo agendamento.
    """

    client_id, client_secret = _credenciais_da_barbearia(
        id_barbearia
    )

    return {
        'X-Client-ID': client_id,
        'X-Client-Secret': client_secret,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


# ============================================================
# CLIENTE HTTP ARKHÉ
# ============================================================

def _chamar(
        metodo,
        caminho,
        corpo=None,
        id_barbearia=None
):
    base_url = (
            app.config.get('ARKHE_BASE_URL') or ''
    ).strip().rstrip('/')

    if not base_url:
        raise RuntimeError(
            'ARKHE_BASE_URL não está configurada no servidor.'
        )

    url = base_url + caminho

    dados = None

    if corpo is not None:
        dados = json.dumps(corpo).encode('utf-8')

    headers = _cabecalhos(id_barbearia)

    requisicao = Request(
        url,
        data=dados,
        method=metodo,
        headers=headers
    )

    try:
        with urlopen(
                requisicao,
                timeout=TIMEOUT_ARKHE
        ) as resposta:

            texto = resposta.read().decode('utf-8')

            if not texto:
                return {}

            try:
                return json.loads(texto)
            except ValueError:
                raise RuntimeError(
                    'A Arkhé retornou uma resposta inválida.'
                )

    except HTTPError as erro:

        try:
            texto = erro.read().decode(
                'utf-8',
                errors='replace'
            )
        except Exception:
            texto = ''

        try:
            detalhe = json.loads(texto) if texto else {}
        except ValueError:
            detalhe = {}

        print(
            'ERRO ARKHÉ:',
            erro.code,
            texto
        )

        mensagem_api = None

        if isinstance(detalhe, dict):
            mensagem_api = (
                    detalhe.get('mensagem')
                    or detalhe.get('message')
                    or detalhe.get('detail')
                    or detalhe.get('erro')
                    or detalhe.get('error')
            )

        mensagens = {
            400: 'A Arkhé recusou os dados enviados.',
            401: (
                'Client ID ou Client Secret da Arkhé '
                'estão incorretos.'
            ),
            403: (
                'A integração da Arkhé não possui permissão '
                'ou está desativada.'
            ),
            404: (
                'O recurso solicitado não foi encontrado '
                'na Arkhé.'
            ),
            500: 'A Arkhé apresentou um erro interno.'
        }

        raise RuntimeError(
            mensagem_api
            or mensagens.get(
                erro.code,
                f'Arkhé retornou HTTP {erro.code}.'
            )
        )

    except URLError as erro:
        print('ERRO DE CONEXÃO ARKHÉ:', erro)

        raise RuntimeError(
            f'Não foi possível conectar à Arkhé: '
            f'{getattr(erro, "reason", erro)}'
        )

    except RuntimeError:
        raise

    except Exception as erro:
        print('ERRO INESPERADO ARKHÉ:', erro)

        raise RuntimeError(
            f'Não foi possível falar com a Arkhé: {erro}'
        )


# ============================================================
# FINANCEIRO
# ============================================================



# ============================================================
# VALOR DO AGENDAMENTO
# ============================================================

def _perfil_financeiro_permitido(usuario):
    try:
        return int(usuario.get('tipo', -1)) in (0, 1, 2)
    except (TypeError, ValueError):
        return False


def _id_agendamento_descricao(descricao):
    return id_agendamento_descricao(descricao)


def _valor_do_agendamento(cursor, linha):
    """Only the price accepted at booking; current catalog is not historical evidence."""
    cursor.execute('SELECT VALOR_TOTAL FROM AGENDAMENTO WHERE ID_AGENDAMENTO=?', (linha[0],))
    registro = cursor.fetchone()
    if not registro or registro[0] is None:
        raise ValueError('Este agendamento não possui valor histórico. Solicite à barbearia que informe o valor realizado; os preços atuais não serão usados.')
    try:
        valor = Decimal(str(registro[0]))
        if not valor.is_finite() or valor <= 0 or valor > Decimal('1000000'):
            raise ValueError('O valor histórico deve ser maior que zero e até R$ 1.000.000,00.')
        valor = valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if valor <= 0: raise ValueError('O valor histórico deve ser maior que zero.')
        from taxa_plataforma import resumo_registrado
        resumo=resumo_registrado(cursor,'agendamento',linha[0],valor,status=linha[9] if len(linha)>9 else None)
        return Decimal(str(resumo['valor_total_cliente'])) if resumo else valor
    except InvalidOperation as exc:
        raise ValueError('Valor histórico inválido.') from exc


# ============================================================
# VALIDAÇÃO DO AGENDAMENTO
# ============================================================

def _agendamento_pagavel(
        cursor,
        usuario,
        id_agendamento,
        permitir_concluido=False
):

    if not _perfil_financeiro_permitido(usuario):
        return None, 'Perfil sem permissão para operações financeiras.'
    try:
        id_agendamento = int(id_agendamento)

    except (TypeError, ValueError):
        return None, 'Agendamento inválido.'

    linha = buscar_agendamento(
        cursor,
        id_agendamento
    )

    if not linha:
        return None, 'Agendamento não encontrado.'

    if not pode_ver_agendamento(
            usuario,
            linha,
            pegar_id_barbearia_alvo()
    ):
        return None, (
            'Sem permissão para pagar este agendamento.'
        )

    if linha[9] in ('cancelado', 'faltou'):
        return None, (
            'Agendamento cancelado não pode ser pago.'
        )

    if linha[9] == 'concluido' and not permitir_concluido:
        return None, (
            'Agendamento concluído não pode ser pago.'
        )

    try:
        valor = _valor_do_agendamento(cursor, linha)
    except ValueError as exc:
        return None, str(exc)

    if valor <= 0:
        return None, (
            'Não foi possível calcular o valor '
            'deste agendamento.'
        )

    return (linha, valor), None


# ============================================================
# DESCOBRIR BARBEARIA DE UMA COBRANÇA
# ============================================================

def _barbearia_da_cobranca(cursor, id_cobranca):
    """
    Localiza a cobrança no FINANCEIRO, pega o agendamento
    relacionado e retorna a barbearia responsável.
    """

    cursor.execute(
        """
        SELECT DESCRICAO
        FROM FINANCEIRO
        WHERE DESCRICAO STARTING WITH ?
        """,
        (f'ARKHE:{id_cobranca} ',)
    )

    registro = cursor.fetchone()

    if not registro:
        raise RuntimeError(
            'Cobrança não encontrada no financeiro.'
        )

    descricao = str(registro[0] or '')

    marcador = 'ag#'

    if marcador not in descricao:
        raise RuntimeError(
            'Não foi possível identificar o agendamento '
            'desta cobrança.'
        )

    try:
        id_agendamento = int(
            descricao.split(marcador, 1)[1]
            .split()[0]
            .split('|')[0]
        )

    except (ValueError, IndexError):
        raise RuntimeError(
            'Identificador de agendamento inválido '
            'na cobrança.'
        )

    linha = buscar_agendamento(
        cursor,
        id_agendamento
    )

    if not linha:
        raise RuntimeError(
            'Agendamento da cobrança não encontrado.'
        )

    # buscar_agendamento:
    #
    # 0 = ID_AGENDAMENTO
    # 1 = ID_USUARIO
    # 2 = ID_BARBEARIA
    #
    return linha[2], linha


# ============================================================
# PIX - CRIAR
# ============================================================

@app.route('/pagamentos/pix', methods=['POST'])
def criar_cobranca_pix():

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login para pagar.',
            401
        )

    if not _perfil_financeiro_permitido(usuario):
        return resposta_erro('Perfil sem permissão para operações financeiras.', 403)

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        if not dados.get('id_agendamento'):
            return resposta_erro(
                'Informe o agendamento.'
            )

        con = conectar_banco()
        cursor = con.cursor()

        try:

            resultado, erro = _agendamento_pagavel(
                cursor,
                usuario,
                dados['id_agendamento']
            )

            if erro:
                return resposta_erro(
                    erro,
                    400
                )

            linha, valor_calculado = resultado

            # ------------------------------------------------
            # ID DA BARBEARIA
            # ------------------------------------------------

            id_barbearia = linha[2]

            if not id_barbearia:
                return resposta_erro(
                    'O agendamento não possui '
                    'uma barbearia vinculada.',
                    400
                )

            # ------------------------------------------------
            # VALOR
            # ------------------------------------------------

            # Preferimos sempre o valor calculado pelo servidor.
            # Isso impede o cliente de alterar o valor pelo frontend.
            valor = valor_calculado

            if valor <= 0:
                return resposta_erro(
                    'Não foi possível calcular '
                    'o valor do agendamento.'
                )

            print(
                'ARKHE PIX:',
                'agendamento=',
                linha[0],
                'barbearia=',
                id_barbearia,
                'valor=',
                valor
            )

            # ------------------------------------------------
            # CRIAR COBRANÇA NA CONTA DA BARBEARIA
            # ------------------------------------------------

            cobranca = _chamar(
                'POST',
                '/api/v1/cobrancas/pix',
                {
                    'valor': round(
                        float(valor),
                        2
                    )
                },
                id_barbearia=id_barbearia
            )

            if not isinstance(cobranca, dict):
                raise RuntimeError(
                    'Resposta inválida ao criar cobrança.'
                )

            id_cobranca = (
                    cobranca.get('id_cobranca')
                    or cobranca.get('id')
            )

            codigo_pagamento = (
                    cobranca.get('codigo_pagamento')
                    or cobranca.get('pix_copia_cola')
                    or cobranca.get('pix')
                    or cobranca.get('codigo_pix')
            )

            if not id_cobranca:
                raise RuntimeError(
                    'A Arkhé não retornou o ID '
                    'da cobrança.'
                )

            # ------------------------------------------------
            # SALVAR
            # ------------------------------------------------

            cursor.execute(
                """
                INSERT INTO FINANCEIRO
                (
                    ID_FINANCEIRO,
                    ID_USUARIO,
                    TIPO,
                    DESCRICAO,
                    VALOR,
                    DATA_TRANSACAO
                )
                VALUES
                    (
                        NEXT VALUE FOR SEQ_FINANCEIRO,
                             ?,
                             'pix_pendente',
                             ?,
                             ?,
                             CURRENT_TIMESTAMP
                    )
                """,
                (
                    linha[1],
                    (
                        f'ARKHE:{id_cobranca} '
                        f'ag#{linha[0]}'
                    ),
                    round(float(valor), 2)
                )
            )

            con.commit()
            registrar_log(
                'INSERT', 'FINANCEIRO', id_usuario=usuario['id_usuario'],
                dados_depois={
                    'ID_USUARIO': linha[1],
                    'TIPO': 'pix_pendente',
                    'DESCRICAO': f'ARKHE:{id_cobranca} ag#{linha[0]}',
                    'VALOR': round(float(valor), 2)
                }
            )

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Cobrança Pix gerada com sucesso.',
                    'tipo': 'sucesso'
                },

                'id_cobranca': id_cobranca,

                'codigo_pagamento':
                    codigo_pagamento,

                'valor': cobranca.get(
                    'valor',
                    round(float(valor), 2)
                ),

                'status': cobranca.get(
                    'status',
                    0
                )

            }), 201

        finally:
            cursor.close()
            con.close()

    except RuntimeError as erro:
        print(
            'ERRO PAGAMENTO PIX:',
            erro
        )

        return resposta_erro(
            str(erro),
            502
        )

    except Exception as erro:
        print(
            'ERRO INTERNO PIX:',
            erro
        )

        return resposta_erro(
            f'Não foi possível gerar a cobrança: {erro}',
            500
        )


# ============================================================
# PIX - CONSULTAR
# ============================================================

@app.route(
    '/pagamentos/pix/<string:id_cobranca>',
    methods=['GET']
)
def consultar_cobranca_pix(id_cobranca):

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login para consultar.',
            401
        )

    if not _perfil_financeiro_permitido(usuario):
        return resposta_erro('Perfil sem permissão para operações financeiras.', 403)

    try:

        con = conectar_banco()
        cursor = con.cursor()

        try:

            id_barbearia, linha = _barbearia_da_cobranca(
                cursor,
                id_cobranca
            )

            from agenda_equipe import travar_agendamento
            linha = travar_agendamento(cursor, linha[0])
            if not linha: return resposta_erro('Agendamento não encontrado.', 404)

            # Verifica se o usuário pode acessar
            # o agendamento relacionado.
            if not pode_ver_agendamento(
                    usuario,
                    linha,
                    pegar_id_barbearia_alvo()
            ):
                return resposta_erro(
                    'Sem permissão para consultar '
                    'esta cobrança.',
                    403
                )

            cobranca = _chamar(
                'GET',
                f'/api/v1/cobrancas/pix/{id_cobranca}',
                id_barbearia=id_barbearia
            )

            # Reconciliation must match both the external identifier and the
            # historical charge amount; status alone is never proof of payment.
            if not isinstance(cobranca, dict):
                raise RuntimeError('A Arkhé retornou uma cobrança inválida.')
            id_retornado = cobranca.get('id_cobranca', cobranca.get('id'))
            if isinstance(id_retornado, bool) or str(id_retornado or '').strip() != str(id_cobranca):
                raise RuntimeError('A cobrança retornada pela Arkhé não corresponde à solicitada.')
            descricao_financeiro = f'ARKHE:{id_cobranca} ag#{linha[0]}'
            cursor.execute("SELECT VALOR FROM FINANCEIRO WHERE ID_USUARIO=? AND DESCRICAO=? AND TIPO IN ('pix_pendente','pix_pago') WITH LOCK",
                           (linha[1], descricao_financeiro))
            registro = cursor.fetchone()
            if not registro:
                raise RuntimeError('O valor histórico desta cobrança não foi encontrado.')
            try:
                if isinstance(cobranca.get('valor'), bool):
                    raise ValueError('Valor inválido.')
                esperado = Decimal(str(registro[0]))
                recebido = Decimal(str(cobranca.get('valor')))
                if not esperado.is_finite() or not recebido.is_finite() or esperado <= 0 or recebido != esperado:
                    raise ValueError('Valor divergente.')
            except (InvalidOperation, ValueError, TypeError):
                raise RuntimeError('O valor retornado pela Arkhé não corresponde ao registrado.')
            codigo = next((valor.strip() for valor in (
                cobranca.get('codigo_pagamento'), cobranca.get('codigo_pix'),
                cobranca.get('pix_copia_cola'), cobranca.get('pix'))
                if isinstance(valor, str) and valor.strip()), None)

            status_bruto = cobranca.get(
                'status',
                0
            )

            pago = (
                    status_bruto == 1
                    or str(status_bruto).lower()
                    in (
                        '1',
                        'pago',
                        'paid',
                        'aprovado',
                        'approved',
                        'confirmado',
                        'confirmed'
                    )
            )

            if pago:

                cursor.execute(
                    """
                    UPDATE FINANCEIRO
                    SET TIPO = 'pix_pago'
                    WHERE ID_USUARIO=? AND DESCRICAO=? AND TIPO='pix_pendente'
                    """,
                    (
                        linha[1], descricao_financeiro,
                    )
                )

                con.commit()
                registrar_log(
                    'UPDATE', 'FINANCEIRO', id_usuario=usuario['id_usuario'],
                    campo='TIPO', valor_antes='pix_pendente', valor_depois='pix_pago'
                )

                return jsonify({
                    'mensagem': {
                        'informacao':
                            'Pagamento confirmado!',
                        'tipo': 'sucesso'
                    },

                    'id_cobranca':
                        cobranca.get(
                            'id_cobranca',
                            id_cobranca
                        ),

                    'valor':
                        cobranca.get('valor'),

                    'status': status_bruto,

                    'pago': True,
                    **({'codigo_pagamento': codigo, 'codigo_pix': codigo} if codigo else {})
                })

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Pagamento ainda pendente.',
                    'tipo': 'aviso'
                },

                'id_cobranca':
                    cobranca.get(
                        'id_cobranca',
                        id_cobranca
                    ),

                'valor':
                    cobranca.get('valor'),

                'status':
                    status_bruto,

                'pago': False,
                **({'codigo_pagamento': codigo, 'codigo_pix': codigo} if codigo else {})
            })

        finally:
            cursor.close()
            con.close()

    except RuntimeError as erro:

        return resposta_erro(
            str(erro),
            502
        )

    except Exception as erro:

        print(
            'ERRO CONSULTAR PIX:',
            erro
        )

        return resposta_erro(
            f'Não foi possível consultar: {erro}',
            500
        )


# ============================================================
# BOLETO
# ============================================================

@app.route('/pagamentos/boleto', methods=['POST'])
def criar_cobranca_boleto():

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login para pagar.',
            401
        )

    if not _perfil_financeiro_permitido(usuario):
        return resposta_erro('Perfil sem permissão para operações financeiras.', 403)

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        if not dados.get('id_agendamento'):
            return resposta_erro(
                'Informe o agendamento.'
            )

        con = conectar_banco()
        cursor = con.cursor()

        try:

            resultado, erro = _agendamento_pagavel(
                cursor,
                usuario,
                dados['id_agendamento']
            )

            if erro:
                return resposta_erro(
                    erro,
                    400
                )

            linha, valor = resultado

            id_barbearia = linha[2]

            try:

                cobranca = _chamar(
                    'POST',
                    '/api/v1/cobrancas/boleto',
                    {
                        'valor': round(
                            float(valor),
                            2
                        )
                    },
                    id_barbearia=id_barbearia
                )

                boleto = {
                    'id_cobranca':
                        cobranca.get(
                            'id_cobranca'
                        ),

                    'codigo_pagamento':
                        cobranca.get(
                            'codigo_pagamento'
                        ),

                    'url_boleto':
                        cobranca.get(
                            'url_boleto'
                        ),

                    'valor':
                        cobranca.get(
                            'valor',
                            round(float(valor), 2)
                        ),

                    'status':
                        cobranca.get(
                            'status',
                            0
                        )
                }

            except RuntimeError as erro_arkhe:
                # Não mascara falhas reais da Arkhé com uma cobrança simulada.
                raise RuntimeError(f'Falha ao gerar boleto na Arkhé: {erro_arkhe}')

            cursor.execute(
                """
                INSERT INTO FINANCEIRO
                (
                    ID_FINANCEIRO,
                    ID_USUARIO,
                    TIPO,
                    DESCRICAO,
                    VALOR,
                    DATA_TRANSACAO
                )
                VALUES
                    (
                        NEXT VALUE FOR SEQ_FINANCEIRO,
                             ?,
                             'boleto_pendente',
                             ?,
                             ?,
                             CURRENT_TIMESTAMP
                    )
                """,
                (
                    linha[1],
                    (
                        f'ag#{linha[0]}|boleto|'
                        f'{boleto.get("codigo_pagamento")}'
                    ),
                    round(float(valor), 2)
                )
            )

            con.commit()
            registrar_log(
                'INSERT', 'FINANCEIRO', id_usuario=usuario['id_usuario'],
                dados_depois={
                    'ID_USUARIO': linha[1],
                    'TIPO': 'boleto_pendente',
                    'DESCRICAO': f'ag#{linha[0]}|boleto|{boleto.get("codigo_pagamento")}',
                    'VALOR': round(float(valor), 2)
                }
            )

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Boleto gerado.',
                    'tipo': 'sucesso'
                },

                'metodo': 'boleto',

                **boleto
            }), 201

        finally:
            cursor.close()
            con.close()

    except Exception as erro:

        print(
            'ERRO BOLETO:',
            erro
        )

        return resposta_erro(
            f'Não foi possível gerar o boleto: {erro}',
            500
        )


# ============================================================
# CARTÃO
# ============================================================

@app.route('/pagamentos/cartao', methods=['POST'])
def criar_cobranca_cartao():

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login para pagar.',
            401
        )

    if not _perfil_financeiro_permitido(usuario):
        return resposta_erro('Perfil sem permissão para operações financeiras.', 403)

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        if not dados.get('id_agendamento'):
            return resposta_erro(
                'Informe o agendamento.'
            )

        con = conectar_banco()
        cursor = con.cursor()

        try:

            resultado, erro = _agendamento_pagavel(
                cursor,
                usuario,
                dados['id_agendamento']
            )

            if erro:
                return resposta_erro(
                    erro,
                    400
                )

            linha, valor = resultado

            id_barbearia = linha[2]

            try:

                cobranca = _chamar(
                    'POST',
                    '/api/v1/cobrancas/cartao',
                    {
                        'valor': round(
                            float(valor),
                            2
                        )
                    },
                    id_barbearia=id_barbearia
                )

                cartao = {
                    'id_cobranca':
                        cobranca.get(
                            'id_cobranca'
                        ),

                    'url_checkout':
                        cobranca.get(
                            'url_checkout'
                        ),

                    'valor':
                        cobranca.get(
                            'valor',
                            round(float(valor), 2)
                        ),

                    'status':
                        cobranca.get(
                            'status',
                            0
                        )
                }

            except RuntimeError as erro_arkhe:
                # Não cria URL/checkout fictício quando a API falha.
                raise RuntimeError(f'Falha ao gerar checkout na Arkhé: {erro_arkhe}')

            cursor.execute(
                """
                INSERT INTO FINANCEIRO
                (
                    ID_FINANCEIRO,
                    ID_USUARIO,
                    TIPO,
                    DESCRICAO,
                    VALOR,
                    DATA_TRANSACAO
                )
                VALUES
                    (
                        NEXT VALUE FOR SEQ_FINANCEIRO,
                             ?,
                             'cartao_pendente',
                             ?,
                             ?,
                             CURRENT_TIMESTAMP
                    )
                """,
                (
                    linha[1],
                    f'ag#{linha[0]}|cartao',
                    round(float(valor), 2)
                )
            )

            con.commit()
            registrar_log(
                'INSERT', 'FINANCEIRO', id_usuario=usuario['id_usuario'],
                dados_depois={
                    'ID_USUARIO': linha[1],
                    'TIPO': 'cartao_pendente',
                    'DESCRICAO': f'ag#{linha[0]}|cartao',
                    'VALOR': round(float(valor), 2)
                }
            )

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Checkout gerado.',
                    'tipo': 'sucesso'
                },

                'metodo': 'cartao',

                **cartao
            }), 201

        finally:
            cursor.close()
            con.close()

    except Exception as erro:

        print(
            'ERRO CARTÃO:',
            erro
        )

        return resposta_erro(
            f'Não foi possível gerar o checkout: {erro}',
            500
        )


# ============================================================
# PAGAMENTO NA HORA
# ============================================================

@app.route('/pagamentos/na-hora', methods=['POST'])
def confirmar_pagamento_na_hora():
    usuario = obter_usuario_logado()
    if not usuario:
        return resposta_erro('Faça login para confirmar.', 401)
    if not _perfil_financeiro_permitido(usuario):
        return resposta_erro('Perfil sem permissão para operações financeiras.', 403)
    dados = request.get_json(silent=True) or {}
    try:
        id_agendamento = int(dados.get('id_agendamento') or 0)
        if id_agendamento <= 0: raise ValueError('Informe o agendamento.')
    except (TypeError, ValueError):
        return resposta_erro('Informe um agendamento válido.')
    con = conectar_banco(); cursor = con.cursor()
    try:
        from agenda_equipe import travar_agendamento
        linha = travar_agendamento(cursor, id_agendamento)
        if not linha:
            return resposta_erro('Agendamento não encontrado.', 404)
        if not pode_ver_agendamento(usuario, linha, pegar_id_barbearia_alvo()):
            return resposta_erro('Sem permissão para este agendamento.', 403)
        if linha[9] in ('cancelado', 'faltou'):
            return resposta_erro('Agendamento cancelado ou com falta não aceita novo recebimento.')
        # Completed bookings can be settled by the salon after the appointment.
        confirmar = int(usuario['tipo']) in (0, 2)
        try:
            valor = _valor_do_agendamento(cursor, linha)
        except ValueError as exc:
            return resposta_erro(str(exc))
        descricao = f'ag#{linha[0]}|na_hora'
        cursor.execute("""SELECT ID_FINANCEIRO,TIPO,DESCRICAO,VALOR FROM FINANCEIRO
            WHERE ID_USUARIO=? AND DESCRICAO CONTAINING ? ORDER BY ID_FINANCEIRO""", (linha[1],f'ag#{linha[0]}'))
        registros = [row for row in cursor.fetchall() if _id_agendamento_descricao(row[2]) == linha[0]]
        pagos=[row for row in registros if row[1] in ('na_hora','pix_pago','cartao_pago','boleto_pago')]
        recebido=sum((Decimal(str(row[3] or 0)) for row in pagos),Decimal('0.00'))
        saldo=max(Decimal('0.00'),valor-recebido)
        existente_pago = next((row for row in registros if row[1] == 'na_hora'), None)
        outro_pago = next((row for row in registros if row[1] in ('pix_pago','cartao_pago','boleto_pago')), None)
        if outro_pago and not saldo:
            return resposta_erro('Este agendamento já possui pagamento confirmado por outro método.', 409)
        if existente_pago and not saldo:
            return _resposta_na_hora(existente_pago[0], recebido, True, False)
        valor=saldo
        pendente = next((row for row in registros if row[1] == 'na_hora_pendente'), None)
        if pendente and not confirmar:
            return _resposta_na_hora(pendente[0], valor, False, False)
        tipo = 'na_hora' if confirmar else 'na_hora_pendente'
        if pendente:
            id_financeiro = pendente[0]
            cursor.execute('UPDATE FINANCEIRO SET TIPO=?,VALOR=?,DATA_TRANSACAO=CURRENT_TIMESTAMP WHERE ID_FINANCEIRO=?', (tipo,valor,id_financeiro))
            acao = 'UPDATE'
        else:
            cursor.execute("""INSERT INTO FINANCEIRO(ID_FINANCEIRO,ID_USUARIO,TIPO,DESCRICAO,VALOR,DATA_TRANSACAO)
                VALUES(NEXT VALUE FOR SEQ_FINANCEIRO,?,?,?,?,CURRENT_TIMESTAMP) RETURNING ID_FINANCEIRO""",
                (linha[1],tipo,descricao,valor))
            id_financeiro = cursor.fetchone()[0];acao = 'INSERT'
        con.commit()
        registrar_log(acao,'FINANCEIRO',id_registro=id_financeiro,id_usuario=usuario['id_usuario'],
            dados_antes={'TIPO':'na_hora_pendente','VALOR':str(pendente[3])} if pendente else None,
            dados_depois={'ID_USUARIO':linha[1],'TIPO':tipo,'DESCRICAO':descricao,'VALOR':str(valor)})
        return _resposta_na_hora(id_financeiro, valor, confirmar, True)
    finally:
        cursor.close();con.close()


def _resposta_na_hora(id_financeiro, valor, confirmado, alterado):
    return jsonify(mensagem={'informacao':'Recebimento confirmado pela barbearia.' if confirmado else 'Pagamento na hora escolhido. O recebimento será confirmado pela barbearia.', 'tipo':'sucesso'},
        metodo='na_hora',tipo='na_hora' if confirmado else 'na_hora_pendente',valor=float(valor),
        id_financeiro=id_financeiro,status=1 if confirmado else 0,confirmado=confirmado,pendente=not confirmado), 201 if alterado else 200


# ============================================================
# COBRANÇAS DO AGENDAMENTO
# ============================================================

@app.route(
    '/pagamentos/agendamento/<int:id_agendamento>',
    methods=['GET']
)
def cobrancas_do_agendamento(id_agendamento):

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login.',
            401
        )

    if not _perfil_financeiro_permitido(usuario):
        return resposta_erro('Perfil sem permissão para operações financeiras.', 403)

    try:

        con = conectar_banco()
        cursor = con.cursor()

        try:

            linha = buscar_agendamento(
                cursor,
                id_agendamento
            )

            if not linha:
                return resposta_erro(
                    'Agendamento não encontrado.',
                    404
                )

            if not pode_ver_agendamento(
                    usuario,
                    linha,
                    pegar_id_barbearia_alvo()
            ):
                return resposta_erro(
                    'Sem permissão.',
                    403
                )

            cursor.execute(
                """
                SELECT
                    ID_FINANCEIRO,
                    TIPO,
                    DESCRICAO,
                    VALOR,
                    DATA_TRANSACAO
                FROM FINANCEIRO
                WHERE ID_USUARIO=? AND DESCRICAO CONTAINING ?
                ORDER BY DATA_TRANSACAO
                """,
                (
                    linha[1], f'ag#{id_agendamento}',
                )
            )

            cobrancas = []

            for registro in cursor.fetchall():
                if _id_agendamento_descricao(registro[2]) != id_agendamento: continue

                data = registro[4]

                cobrancas.append({
                    'status': 1 if registro[1] in ('na_hora','pix_pago','boleto_pago','cartao_pago') else 0,
                    'confirmado': registro[1] in ('na_hora','pix_pago','boleto_pago','cartao_pago'),
                    'pendente': str(registro[1]).endswith('_pendente'),
                    'id_financeiro':
                        registro[0],

                    'tipo':
                        registro[1],

                    'descricao':
                        registro[2],

                    'valor':
                        float(
                            registro[3] or 0
                        ),

                    'data':
                        data.isoformat()
                        if data
                        else None
                })

            cursor.execute('SELECT VALOR_TOTAL FROM AGENDAMENTO WHERE ID_AGENDAMENTO=? AND ID_BARBEARIA=?',(linha[0],linha[2]))
            snapshot=cursor.fetchone()
            total=Decimal(str(snapshot[0])) if snapshot and snapshot[0] is not None else None
            if total is not None:
                from taxa_plataforma import resumo_registrado
                resumo=resumo_registrado(cursor,'agendamento',linha[0],total,status=linha[9])
                total=Decimal(str(resumo['valor_total_cliente'])) if resumo else total
            recebido=sum((Decimal(str(item['valor'])) for item in cobrancas if item['confirmado']),Decimal('0.00'))
            saldo=max(Decimal('0.00'),total-recebido) if total is not None else None
            quitado=total is not None and total>0 and saldo==0

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Cobranças listadas.',
                    'tipo': 'sucesso'
                },

                'valor_total':float(total) if total is not None else None,
                'valor_recebido':float(recebido),'saldo':float(saldo) if saldo is not None else None,
                'quitado':quitado,'parcial':recebido>0 and not quitado,
                'na_hora_pendente': not quitado and any(item['tipo'] == 'na_hora_pendente' for item in cobrancas),
                'na_hora_confirmado': quitado and any(item['tipo'] == 'na_hora' for item in cobrancas),
                'cobrancas':
                    cobrancas
            })

        finally:
            cursor.close()
            con.close()

    except Exception as erro:

        return resposta_erro(
            f'Não foi possível listar cobranças: {erro}',
            500
        )
