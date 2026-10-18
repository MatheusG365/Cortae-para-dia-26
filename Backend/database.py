"""Database connections, locks and read-only readiness checks."""
import firebirdsql as fdb
import json
from pathlib import Path
from flask import current_app

ESTRUTURA_ESPERADA = json.loads((Path(__file__).parent / 'migrations' / 'estrutura.json').read_text(encoding='utf-8'))


def pendencias_estrutura(cursor):
    """Detecta campos ausentes sem alterar tabelas, sequences ou dados."""
    cursor.execute('SELECT TRIM(RDB$RELATION_NAME),TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS')
    existentes = set(cursor.fetchall())
    pendencias = [f'{tabela}.{campo}' for tabela, campos in ESTRUTURA_ESPERADA.items()
                  for campo in campos if (tabela, campo) not in existentes]
    cursor.execute("""SELECT F.RDB$CHARACTER_LENGTH FROM RDB$RELATION_FIELDS RF
        JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME=RF.RDB$FIELD_SOURCE
        WHERE TRIM(RF.RDB$RELATION_NAME)='FINANCEIRO_SNAPSHOT'
          AND TRIM(RF.RDB$FIELD_NAME)='FONTE'""")
    fonte = cursor.fetchone()
    if fonte and fonte[0] is not None and fonte[0] < 32:
        pendencias.append('FINANCEIRO_SNAPSHOT.FONTE: mínimo 32 caracteres')
    return pendencias


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
        return log or not pendencias_estrutura(cursor)
    except Exception:
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if con is not None:
            con.close()
