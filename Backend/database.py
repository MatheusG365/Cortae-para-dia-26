"""Database connections and repeatable Firebird startup preparation."""
import firebirdsql as fdb
from flask import current_app
from schema_utils import criar_sequence, criar_coluna

SEQUENCES = (
    ('SEQ_FINANCEIRO', 'FINANCEIRO', 'ID_FINANCEIRO'),
    ('SEQ_USUARIO', 'USUARIO', 'ID_USUARIO'),
    ('SEQ_AGENDAMENTO', 'AGENDAMENTO', 'ID_AGENDAMENTO'),
    ('SEQ_AGENDAMENTO_HISTORICO', 'AGENDAMENTO_HISTORICO', 'ID_HISTORICO'),
    ('SEQ_CORTE_VISAGISMO', 'CORTE_VISAGISMO', 'ID_CORTE'),
    ('SEQ_VISAGISMO_SESSAO', 'VISAGISMO_SESSAO', 'ID_VISAGISMO'),
    ('SEQ_PERSONALIZACAO', 'PERSONALIZACAO', 'ID_PERSONALIZACAO'),
    ('SEQ_DIA', 'DIAS_DE_SERVICO', 'ID_DIA'),
    ('SEQ_FUNCIONARIO', 'FUNCIONARIO', 'ID_FUNCIONARIO'),
    ('SEQ_FUNCIONARIO_DIA', 'FUNCIONARIO_DIA', 'ID_FUNCIONARIO_DIA'),
    ('SEQ_SERVICO', 'SERVICO', 'ID_SERVICO'),
    ('SEQ_SERVICO_POR_FUNCIONARIO', 'SERVICO_POR_FUNCIONARIO', 'ID_SERVI_FUNCI'),
    ('SEQ_FINANCEIRO_SNAPSHOT', 'FINANCEIRO_SNAPSHOT', 'ID_SNAPSHOT'),
    ('SEQ_AVISO', 'AVISO', 'ID_AVISO'),
)


def conectar_banco(log=False):
    config = current_app.config
    prefixo = 'LOG_DB_' if log else 'DB_'
    return fdb.connect(host=config[prefixo + 'HOST'], port=config[prefixo + 'PORT'],
                       database=config[prefixo + 'NAME'], user=config[prefixo + 'USER'],
                       password=config[prefixo + 'PASSWORD'], charset='UTF8',
                       timeout=config['DB_TIMEOUT'])


def travar_usuario(cursor, id_usuario):
    """Serializa operações da mesma conta na transação aberta pelo chamador."""
    cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (id_usuario,))
    cursor.fetchone()


def verificar_banco(log=False):
    con = cursor = None
    try:
        con = conectar_banco(log=log)
        cursor = con.cursor()
        if log:
            from auditoria import _nome_seguro
            tabela = _nome_seguro(current_app.config['LOG_DB_TABLE'])
            cursor.execute(f'SELECT FIRST 1 ID_LOG FROM {tabela}')
        else:
            cursor.execute('SELECT FIRST 1 ID_USUARIO FROM USUARIO')
        cursor.fetchone()
        return True
    except Exception:
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if con is not None:
            con.close()


def alinhar_sequence(con, cursor, sequence, tabela, coluna):
    # Identifiers are internal constants, never user input.
    criar_sequence(cursor, sequence, con)
    cursor.execute(f'SELECT COALESCE(MAX({coluna}), 0) FROM {tabela}')
    maior = int(cursor.fetchone()[0] or 0)
    cursor.execute(f'SELECT GEN_ID({sequence}, 0) FROM RDB$DATABASE')
    atual = int(cursor.fetchone()[0] or 0)
    if maior > atual:
        # GEN_ID increments atomically; this never lowers a live sequence.
        cursor.execute(f'SELECT GEN_ID({sequence}, CAST(? AS BIGINT)) FROM RDB$DATABASE', (maior - atual,))
        cursor.fetchone()


def inicializar_banco():
    con = cursor = None
    try:
        con = conectar_banco()
        cursor = con.cursor()
        for sequence, tabela, coluna in SEQUENCES:
            alinhar_sequence(con, cursor, sequence, tabela, coluna)
        for tabela, coluna, tipo in (('USUARIO', 'JA_BLOQUEADO', 'SMALLINT DEFAULT 0'),
                                     ('SERVICO', 'GENERO', 'VARCHAR(10)')):
            criar_coluna(cursor, tabela, coluna, tipo, con)
        cursor.execute("""UPDATE SERVICO SET GENERO = CASE
            WHEN LOWER(NOME_SERVICO) SIMILAR TO '%(feminino|feminina|femenino|mulher|noiva|madrinha)%' THEN 'feminino'
            WHEN LOWER(NOME_SERVICO) SIMILAR TO '%(masculino|masculina|homem|noivo|padrinho|barba|bigode)%' THEN 'masculino'
            ELSE 'unissex' END WHERE GENERO IS NULL OR TRIM(GENERO) = ''""")
        con.commit()
    except Exception:
        if con is not None:
            con.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if con is not None:
            con.close()
