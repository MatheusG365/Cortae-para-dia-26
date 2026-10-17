"""Additive, repeatable professional goals schema; no changes to booking history."""
from application import conectar_banco
from schema_utils import criar_tabela, criar_sequence


def migrar_metas():
    con = conectar_banco(); cur = con.cursor()
    try:
        criar_sequence(cur, 'GEN_META_PROFISSIONAL', con)
        criar_tabela(cur, 'META_PROFISSIONAL', '''CREATE TABLE META_PROFISSIONAL (
            ID_META INTEGER NOT NULL PRIMARY KEY,
            ID_BARBEARIA INTEGER NOT NULL REFERENCES USUARIO(ID_USUARIO),
            ID_FUNCIONARIO INTEGER NOT NULL REFERENCES FUNCIONARIO(ID_FUNCIONARIO),
            TIPO VARCHAR(20) NOT NULL CHECK(TIPO IN ('atendimentos','faturamento')),
            ALVO DECIMAL(14,2) NOT NULL CHECK(ALVO > 0),
            INICIO DATE NOT NULL,
            FIM DATE NOT NULL CHECK(FIM >= INICIO),
            ATIVO SMALLINT DEFAULT 1 NOT NULL CHECK(ATIVO IN (0,1)),
            CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            ATUALIZADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)''', con)
        con.commit()
    except Exception:
        con.rollback(); raise
    finally:
        cur.close(); con.close()


if __name__ == '__main__':
    from application import app
    with app.app_context(): migrar_metas()
