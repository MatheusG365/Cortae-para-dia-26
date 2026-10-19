"""Manual, additive card reservations. Never imported by HTTP route modules."""
from application import conectar_banco
from .schema_utils import criar_tabela, criar_coluna


def _normalizar_expressao(source):
    value = ''.join(str(source or '').upper().split())
    if value.startswith('(') and value.endswith(')'):
        value = value[1:-1]
    return value


def migrar_cartao():
    con = conectar_banco()
    cur = con.cursor()
    try:
        criar_tabela(cur, 'PAGAMENTO_CARTAO', '''CREATE TABLE PAGAMENTO_CARTAO (
            TIPO_ALVO VARCHAR(12) NOT NULL CHECK(TIPO_ALVO IN ('agendamento','pedido')),
            ID_ALVO INTEGER NOT NULL,
            ID_USUARIO INTEGER NOT NULL REFERENCES USUARIO(ID_USUARIO),
            ID_BARBEARIA INTEGER NOT NULL REFERENCES USUARIO(ID_USUARIO),
            ESTADO VARCHAR(15) NOT NULL CHECK(ESTADO IN ('processando','incerto','aprovado','recusado')),
            VALOR DECIMAL(12,2) NOT NULL CHECK(VALOR>0),
            TIPO VARCHAR(7) NOT NULL CHECK(TIPO IN ('DEBITO','CREDITO')),
            PARCELAS SMALLINT NOT NULL CHECK(PARCELAS BETWEEN 1 AND 15),
            RESULTADO BLOB SUB_TYPE TEXT,
            ID_COMPRA INTEGER,
            ID_MOVIMENTACAO INTEGER,
            CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            ATUALIZADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            PRIMARY KEY(TIPO_ALVO,ID_ALVO)
        )''', con)
        for column in ('ID_COMPRA', 'ID_MOVIMENTACAO'):
            criar_coluna(cur, 'PAGAMENTO_CARTAO', column, 'INTEGER', con)
        for name, column in (('UQ_CARTAO_COMPRA', 'ID_COMPRA'), ('UQ_CARTAO_MOVIMENTACAO', 'ID_MOVIMENTACAO')):
            # RDB$EXPRESSION_SOURCE and computed indexes also exist in ODS 13.0.
            # Partial indexes / CONDITION_SOURCE require the newer ODS 13.1.
            expression = (f'CASE WHEN {column} IS NULL THEN NULL ELSE '
                          f"CAST(ID_BARBEARIA AS VARCHAR(11)) || ':' || CAST({column} AS VARCHAR(11)) END")
            cur.execute('SELECT RDB$EXPRESSION_SOURCE,RDB$UNIQUE_FLAG,RDB$INDEX_INACTIVE FROM RDB$INDICES WHERE TRIM(RDB$INDEX_NAME)=?', (name,))
            index = cur.fetchone()
            if (index and index[1] == 1 and not index[2] and
                    _normalizar_expressao(index[0]) == _normalizar_expressao(expression)):
                continue
            if index:
                cur.execute(f'DROP INDEX {name}')
                con.commit()
            # A single entirely NULL key permits many unfinished attempts.
            # Non-NULL keys encode both integers without delimiter ambiguity.
            cur.execute(f'CREATE UNIQUE INDEX {name} ON PAGAMENTO_CARTAO COMPUTED BY ({expression})')
            con.commit()
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        cur.close()
        con.close()
