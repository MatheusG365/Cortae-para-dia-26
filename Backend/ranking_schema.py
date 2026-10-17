"""Additive, repeatable appointment rating schema. Run after a verified backup."""
from application import conectar_banco
from schema_utils import criar_tabela


def migrar_ranking_avaliacoes():
    con = conectar_banco(); cur = con.cursor()
    try:
        criar_tabela(cur, 'AGENDAMENTO_AVALIACAO', '''CREATE TABLE AGENDAMENTO_AVALIACAO (
                ID_AGENDAMENTO INTEGER NOT NULL PRIMARY KEY REFERENCES AGENDAMENTO(ID_AGENDAMENTO),
                NOTA SMALLINT NOT NULL CHECK(NOTA BETWEEN 1 AND 5),
                COMENTARIO VARCHAR(1000),
                CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                ATUALIZADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)''')
        con.commit()
    except Exception:
        con.rollback(); raise
    finally:
        cur.close(); con.close()


if __name__ == '__main__':
    from application import app
    with app.app_context(): migrar_ranking_avaliacoes()
