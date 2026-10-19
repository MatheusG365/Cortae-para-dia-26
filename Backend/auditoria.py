"""Funções centralizadas para auditoria em banco Firebird separado.

A tabela de destino esperada é LOG_ALTERACAO, com a estrutura informada no
projeto. Cada campo efetivamente alterado gera uma linha de histórico.
"""

import datetime
import decimal
import json
import re

from flask import current_app, has_request_context, request


_IDENTIFICADOR = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

# O log deve registrar que um campo sensível mudou, mas nunca copiar o segredo.
_CAMPOS_SENSIVEIS = {
    "SENHA",
    "SENHA_HASH",
    "SENHA2",
    "SENHA3",
    "PASSWORD",
    "PASSWORD_HASH",
    "CODIGO_VERIFICACAO",
    "TOKEN",
    "ACCESS_TOKEN",
    "REFRESH_TOKEN",
    "CHAVE_API",
    "API_KEY",
    "CLIENT_SECRET",
    "CHAVE_PIX",
    "NUMERO_CARTAO",
    "CARD_NUMBER",
    "PAN",
    "CVV",
    "CVC",
    "PIN",
}


# Limites exatos da tabela LOG_ALTERACAO.
_LIMITE_IP = 45
_LIMITE_ACAO = 20
_LIMITE_TABELA = 100
_LIMITE_CAMPO = 100
_LIMITE_VALOR = 1000


def _nome_seguro(nome):
    """Valida identificadores usados em SELECTs do banco principal."""
    nome = str(nome or "").strip().upper()
    if not _IDENTIFICADOR.fullmatch(nome):
        raise ValueError(f"Identificador SQL inválido para auditoria: {nome!r}")
    return nome


def _texto_limitado(valor, limite):
    if valor is None:
        return None
    texto = str(valor)
    if len(texto) <= limite:
        return texto

    sufixo = "...[CORTADO]"
    return texto[: max(0, limite - len(sufixo))] + sufixo


def conectar_banco_log():
    """Abre uma conexão independente com o novo banco Firebird de LOG."""
    from database import conectar_banco
    return conectar_banco(log=True)


def _obter_ip_cliente():
    """Obtém o IP da requisição e garante o limite VARCHAR(45)."""
    if not has_request_context():
        return "SISTEMA"

    # X-Forwarded-For é útil quando a aplicação está atrás de proxy reverso.
    encaminhado = request.headers.get("X-Forwarded-For", "")
    if encaminhado:
        return _texto_limitado(encaminhado.split(",", 1)[0].strip(), _LIMITE_IP)

    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        return _texto_limitado(real_ip.strip(), _LIMITE_IP)

    return _texto_limitado(request.remote_addr or "DESCONHECIDO", _LIMITE_IP)


def _obter_id_usuario_token():
    """Lê o ID do usuário autenticado pelo cookie/Bearer JWT."""
    if not has_request_context():
        return None
    from funcoes import decodificar_token
    dados = decodificar_token()
    return dados.get('id_usuario') if dados else None


def _redigir_cartao_aninhado(valor):
    if isinstance(valor, dict):
        return {key: ('[PROTEGIDO]' if str(key).upper() in _CAMPOS_SENSIVEIS
                      else _redigir_cartao_aninhado(item)) for key, item in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [_redigir_cartao_aninhado(item) for item in valor]
    return valor


def _valor_para_texto(valor, campo=None):
    """Converte valores para VARCHAR(1000), protegendo dados sensíveis."""
    campo = str(campo or "").upper()

    if (
        campo in _CAMPOS_SENSIVEIS
        or any(
            fragmento in campo
            for fragmento in (
                "SENHA",
                "PASSWORD",
                "SECRET",
                "TOKEN",
                "CODIGO_VERIFICACAO",
                "API_KEY",
            )
        )
    ):
        return "[PROTEGIDO]" if valor is not None else None

    if valor is None:
        return None

    if isinstance(valor, datetime.datetime):
        texto = valor.isoformat(sep=" ")
    elif isinstance(valor, (datetime.date, datetime.time)):
        texto = valor.isoformat()
    elif isinstance(valor, decimal.Decimal):
        texto = format(valor, "f")
    elif isinstance(valor, bytes):
        texto = f"[BINARIO {len(valor)} bytes]"
    elif isinstance(valor, (dict, list, tuple, set)):
        try:
            if isinstance(valor, set):
                valor = sorted(valor)
            valor = _redigir_cartao_aninhado(valor)
            texto = json.dumps(valor, ensure_ascii=False, default=str)
        except Exception:
            texto = str(valor)
    else:
        texto = str(valor)

    return _texto_limitado(texto, _LIMITE_VALOR)


def capturar_registro(cursor, tabela, coluna_id, id_registro):
    """Captura um registro do banco principal como dict coluna -> valor.

    Use antes de UPDATE/DELETE para preservar o estado anterior e, quando
    necessário, depois da operação para obter o estado final.
    """
    tabela = _nome_seguro(tabela)
    coluna_id = _nome_seguro(coluna_id)

    cursor.execute(
        f"SELECT * FROM {tabela} WHERE {coluna_id} = ?",
        (id_registro,),
    )
    linha = cursor.fetchone()
    if linha is None:
        return None

    colunas = [str(desc[0]).strip().upper() for desc in cursor.description]
    return dict(zip(colunas, linha))


def _normalizar_id_inteiro(valor, nome, permitir_nulo=True):
    if valor is None and permitir_nulo:
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{nome} precisa ser INTEGER para o banco de LOG.")


def _inserir_linha_log(cursor, tabela_log, dados):
    """INSERT exato de acordo com a estrutura real da LOG_ALTERACAO."""
    sql = f"""
        INSERT INTO {tabela_log} (
            MAQUINA_IP,
            ID_USUARIO,
            ACAO,
            TABELA_ALTERADA,
            ID_REGISTRO_ALTERADO,
            CAMPO_ALTERADO,
            VALOR_ANTES,
            VALOR_DEPOIS
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    cursor.execute(
        sql,
        (
            dados["maquina"],
            dados["usuario"],
            dados["acao"],
            dados["tabela"],
            dados["registro"],
            dados["campo"],
            dados["antes"],
            dados["depois"],
        ),
    )
    # DATA_HORA usa DEFAULT CURRENT_TIMESTAMP e ID_LOG usa IDENTITY.


def registrar_log(
    acao,
    tabela,
    id_registro=None,
    dados_antes=None,
    dados_depois=None,
    id_usuario=None,
    campo=None,
    valor_antes=None,
    valor_depois=None,
):
    """Registra a auditoria no banco separado.

    - UPDATE: grava somente os campos cujo valor realmente mudou.
    - INSERT: grava os valores criados.
    - DELETE: grava os valores existentes antes da exclusão.
    - LOGIN/LOGOUT e eventos similares podem informar ``campo`` diretamente.

    Uma linha é criada por campo. Retorna a quantidade de linhas gravadas.
    """
    tabela_log = _nome_seguro(
        current_app.config.get("LOG_DB_TABLE", "LOG_ALTERACAO")
    )

    acao = _texto_limitado(str(acao or "").strip().upper(), _LIMITE_ACAO)
    tabela = _texto_limitado(str(tabela or "").strip().upper(), _LIMITE_TABELA)

    if not acao:
        raise ValueError("A ação do LOG não pode ser vazia.")
    if not tabela:
        raise ValueError("A tabela alterada do LOG não pode ser vazia.")

    if id_usuario is None:
        id_usuario = _obter_id_usuario_token()

    if id_usuario is None:
        mensagem = "Não foi possível identificar o ID do usuário para o LOG."
        current_app.logger.warning("Auditoria sem usuário identificado.")
        if current_app.config.get("LOG_OBRIGATORIO", False):
            raise ValueError(mensagem)
        return 0

    antes = {str(k).upper(): v for k, v in (dados_antes or {}).items()}
    depois = {str(k).upper(): v for k, v in (dados_depois or {}).items()}

    mudancas = []
    if campo is not None:
        nome_campo = _texto_limitado(str(campo).strip().upper(), _LIMITE_CAMPO)
        if valor_antes != valor_depois or acao not in {"UPDATE"}:
            mudancas.append((nome_campo, valor_antes, valor_depois))
    else:
        campos = sorted(set(antes) | set(depois))
        for nome_campo in campos:
            valor_a = antes.get(nome_campo)
            valor_d = depois.get(nome_campo)
            if valor_a != valor_d:
                mudancas.append(
                    (
                        _texto_limitado(nome_campo, _LIMITE_CAMPO),
                        valor_a,
                        valor_d,
                    )
                )

    # Se nada mudou, não cria linhas desnecessárias.
    if not mudancas:
        return 0

    con_log = None
    cursor_log = None

    try:
        usuario_inteiro = _normalizar_id_inteiro(
            id_usuario,
            "ID_USUARIO",
            permitir_nulo=False,
        )
        registro_inteiro = _normalizar_id_inteiro(
            id_registro,
            "ID_REGISTRO_ALTERADO",
            permitir_nulo=True,
        )

        con_log = conectar_banco_log()
        cursor_log = con_log.cursor()

        maquina = _obter_ip_cliente()
        gravados = 0

        for nome_campo, valor_a, valor_d in mudancas:
            _inserir_linha_log(
                cursor_log,
                tabela_log,
                {
                    "maquina": maquina,
                    "usuario": usuario_inteiro,
                    "acao": acao,
                    "tabela": tabela,
                    "registro": registro_inteiro,
                    "campo": nome_campo,
                    "antes": _valor_para_texto(valor_a, nome_campo),
                    "depois": _valor_para_texto(valor_d, nome_campo),
                },
            )
            gravados += 1

        con_log.commit()
        return gravados

    except Exception as erro:
        if con_log:
            try:
                con_log.rollback()
            except Exception:
                pass

        current_app.logger.error("Falha de auditoria [%s %s]: %s", acao, tabela, type(erro).__name__)
        if current_app.config.get("LOG_OBRIGATORIO", False):
            raise
        return 0

    finally:
        if cursor_log:
            try:
                cursor_log.close()
            except Exception:
                pass
        if con_log:
            try:
                con_log.close()
            except Exception:
                pass


def registrar_registro(
    cursor,
    acao,
    tabela,
    coluna_id,
    id_registro,
    dados_antes=None,
    id_usuario=None,
):
    """Atalho usado pelas rotas para evitar repetição de código."""
    acao_normalizada = str(acao or "").strip().upper()

    dados_depois = None
    if acao_normalizada != "DELETE":
        dados_depois = capturar_registro(
            cursor,
            tabela,
            coluna_id,
            id_registro,
        )

    return registrar_log(
        acao=acao_normalizada,
        tabela=tabela,
        id_registro=id_registro,
        dados_antes=dados_antes,
        dados_depois=dados_depois,
        id_usuario=id_usuario,
    )
