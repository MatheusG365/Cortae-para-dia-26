"""Migração manual do snapshot financeiro, separada das transações de atendimento."""
import time
from firebirdsql import DatabaseError
from firebirdsql.fbcore import Cursor, Transaction
from application import conectar_banco


def _garantir_snapshot(cursor):
    # Use the existing attachment, but keep schema commits/rollbacks separate
    # from any pending work in the caller's transaction.
    for tentativa in range(3):
        transacao = Transaction(cursor.transaction.connection)
        esquema = Cursor(transacao)
        try:
            _preparar_snapshot_esquema(esquema)
            transacao.commit()
            return
        except DatabaseError as erro:
            transacao.rollback()
            conflito = (
                # Firebird 5 can omit the legacy SQL code (driver reports 0).
                erro.sql_code in (0, -913, -607)
                and 335544351 in erro.gds_codes  # unsuccessful metadata update
                and bool(erro.gds_codes & {335544336, 335544451})
            )
            if not conflito or tentativa == 2:
                raise
        except Exception:
            transacao.rollback()
            raise
        finally:
            esquema.close()
        # A competing preparation may have committed the migration already.
        # Retry the metadata checks in a fresh transaction before any DELETE.
        time.sleep(0.05 * (tentativa + 1))


def _preparar_snapshot_esquema(cursor):
    cursor.execute(
        """
        SELECT 1
        FROM RDB$RELATIONS
        WHERE TRIM(RDB$RELATION_NAME)
                  = 'FINANCEIRO_SNAPSHOT'
        """
    )

    if cursor.fetchone() is None:
        cursor.execute(
            """
            CREATE TABLE FINANCEIRO_SNAPSHOT (
                                                 ID_SNAPSHOT INTEGER NOT NULL PRIMARY KEY,
                                                 ID_BARBEARIA INTEGER NOT NULL,
                                                 DATA_MOV DATE NOT NULL,
                                                 TIPO VARCHAR(10) NOT NULL,
                                                 ORIGEM VARCHAR(30),
                                                 DESCRICAO VARCHAR(255),
                                                 VALOR NUMERIC(12,2)
                                                     DEFAULT 0 NOT NULL,
                                                 FONTE VARCHAR(32),
                                                 ATUALIZADO_EM TIMESTAMP
                                                     DEFAULT CURRENT_TIMESTAMP
                                                     NOT NULL
            )
            """
        )
        cursor.transaction.commit()

    # Older databases used VARCHAR(10), but the combined statement source is
    # 'arkhe+na_hora' (13 characters). Widen before any snapshot replacement.
    # Keep existing values and leave schemas that are already wider untouched.
    cursor.execute(
        """
        SELECT F.RDB$CHARACTER_LENGTH
        FROM RDB$RELATION_FIELDS RF
        JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME = RF.RDB$FIELD_SOURCE
        WHERE TRIM(RF.RDB$RELATION_NAME) = 'FINANCEIRO_SNAPSHOT'
          AND TRIM(RF.RDB$FIELD_NAME) = 'FONTE'
        """
    )
    fonte = cursor.fetchone()
    if fonte and fonte[0] is not None and fonte[0] < 32:
        cursor.execute('ALTER TABLE FINANCEIRO_SNAPSHOT ALTER FONTE TYPE VARCHAR(32)')
        cursor.transaction.commit()

    cursor.execute(
        """
        SELECT 1
        FROM RDB$GENERATORS
        WHERE TRIM(RDB$GENERATOR_NAME)
                  = 'SEQ_FINANCEIRO_SNAPSHOT'
        """
    )

    if cursor.fetchone() is None:
        cursor.execute(
            'CREATE SEQUENCE '
            'SEQ_FINANCEIRO_SNAPSHOT'
        )
        cursor.transaction.commit()

    cursor.execute(
        """
        SELECT 1
        FROM RDB$INDICES
        WHERE TRIM(RDB$INDEX_NAME)
                  = 'IDX_FINSNAP_BARB_DATA'
        """
    )

    if cursor.fetchone() is None:
        cursor.execute(
            """
            CREATE INDEX IDX_FINSNAP_BARB_DATA
                ON FINANCEIRO_SNAPSHOT
                    (ID_BARBEARIA, DATA_MOV)
            """
        )
        cursor.transaction.commit()


def migrar_financeiro():
    con = conectar_banco()
    cursor = con.cursor()
    try:
        _garantir_snapshot(cursor)
    finally:
        cursor.close()
        con.close()
