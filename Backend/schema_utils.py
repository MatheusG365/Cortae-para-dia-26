"""DDL idempotente para identificadores internos; sem conexões ou commits implícitos.

As rotinas de migração escolhem quando confirmar cada alteração. Nunca chamar
estes auxiliares com nomes SQL vindos de uma requisição.
"""


def objeto_existe(cursor, tipo, nome):
    catalogos = {
        'tabela': ('RDB$RELATIONS', 'RDB$RELATION_NAME'),
        'sequence': ('RDB$GENERATORS', 'RDB$GENERATOR_NAME'),
    }
    if tipo not in catalogos:
        raise ValueError(f'Tipo de objeto inválido: {tipo}')
    tabela, coluna = catalogos[tipo]
    cursor.execute(f'SELECT 1 FROM {tabela} WHERE TRIM({coluna})=?', (str(nome).upper(),))
    return cursor.fetchone() is not None


def coluna_existe(cursor, tabela, nome):
    cursor.execute('SELECT 1 FROM RDB$RELATION_FIELDS WHERE TRIM(RDB$RELATION_NAME)=? AND TRIM(RDB$FIELD_NAME)=?', (tabela, nome))
    return cursor.fetchone() is not None


def _executar_ddl(cursor, sql, conexao):
    cursor.execute(sql)
    if conexao is not None:
        conexao.commit()


def criar_tabela(cursor, nome, sql, conexao=None):
    if not objeto_existe(cursor, 'tabela', nome):
        _executar_ddl(cursor, sql, conexao)


def criar_sequence(cursor, nome, conexao=None):
    if not objeto_existe(cursor, 'sequence', nome):
        _executar_ddl(cursor, f'CREATE SEQUENCE {nome}', conexao)


def criar_coluna(cursor, tabela, nome, tipo, conexao=None):
    if not coluna_existe(cursor, tabela, nome):
        _executar_ddl(cursor, f'ALTER TABLE {tabela} ADD {nome} {tipo}', conexao)
