"""Snapshot regressions. Optional Firebird tests create disposable databases.

RUN_FIREBIRD_SNAPSHOT_TESTS=1 enables real SQL checks against a local Firebird
server. Provider/auth/audit calls are mocked; no production database is opened.
"""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import firebirdsql
import main
import arkhe
from migrations import financeiro_schema as snapshot_schema


class SnapshotSchemaBehavior(unittest.TestCase):
    def test_wider_existing_source_does_not_commit_callers_transaction(self):
        cursor = MagicMock()
        schema_cursor = MagicMock()
        schema_cursor.fetchone.side_effect = [(1,), (64,), (1,), (1,)]
        with patch.object(snapshot_schema, 'Transaction') as transaction, \
             patch.object(snapshot_schema, 'Cursor', return_value=schema_cursor):
            snapshot_schema._garantir_snapshot(cursor)
        transaction.assert_called_once_with(cursor.transaction.connection)
        cursor.transaction.commit.assert_not_called()
        cursor.transaction.rollback.assert_not_called()
        self.assertFalse(any('ALTER TABLE' in call.args[0] for call in schema_cursor.execute.call_args_list))

    def test_non_conflict_schema_failure_is_not_retried_or_hidden(self):
        cursor = MagicMock()
        error = firebirdsql.DatabaseError('Permission denied', {335544352}, -551)
        with patch.object(snapshot_schema, 'Transaction') as transaction, \
             patch.object(snapshot_schema, 'Cursor'), \
             patch.object(snapshot_schema, '_preparar_snapshot_esquema', side_effect=error) as prepare:
            with self.assertRaises(firebirdsql.DatabaseError) as raised:
                snapshot_schema._garantir_snapshot(cursor)
        self.assertIs(raised.exception, error)
        self.assertEqual(prepare.call_count, 1)
        transaction.return_value.rollback.assert_called_once()
        cursor.transaction.rollback.assert_not_called()

    def test_conflict_retries_are_bounded(self):
        cursor = MagicMock()
        error = firebirdsql.OperationalError('metadata update conflict', {335544351, 335544336, 335544451}, 0)
        with patch.object(snapshot_schema, 'Transaction') as transaction, \
             patch.object(snapshot_schema, 'Cursor'), \
             patch.object(snapshot_schema, 'time') as clock, \
             patch.object(snapshot_schema, '_preparar_snapshot_esquema', side_effect=error) as prepare:
            with self.assertRaises(firebirdsql.OperationalError):
                snapshot_schema._garantir_snapshot(cursor)
        self.assertEqual(prepare.call_count, 3)
        self.assertEqual(transaction.return_value.rollback.call_count, 3)
        self.assertEqual(clock.sleep.call_count, 2)
        cursor.transaction.rollback.assert_not_called()


@unittest.skipUnless(os.environ.get('RUN_FIREBIRD_SNAPSHOT_TESTS') == '1',
                     'Enable disposable local Firebird integration checks explicitly.')
class SnapshotFirebird(unittest.TestCase):
    def setUp(self):
        self.context = main.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.directory = Path(tempfile.mkdtemp(prefix='cortae-arkhe-snapshot-')).resolve()
        self.database = self.directory / 'ARKHE-SNAPSHOT-QA.FDB'
        self.connection_options = dict(host='127.0.0.1',
            port=int(os.environ.get('ARKHE_TEST_FIREBIRD_PORT', main.app.config['DB_PORT'])),
            user=os.environ.get('ARKHE_TEST_FIREBIRD_USER', 'SYSDBA'),
            password=os.environ.get('ARKHE_TEST_FIREBIRD_PASSWORD', os.environ.get('DB_PASSWORD', main.app.config['DB_PASSWORD'])),
            database=str(self.database), charset='UTF8')
        connection = firebirdsql.create_database(**self.connection_options)
        self.addCleanup(self.drop_created_database)
        try:
            cursor = connection.cursor()
            cursor.execute('''CREATE TABLE FINANCEIRO_SNAPSHOT (
                ID_SNAPSHOT INTEGER NOT NULL PRIMARY KEY, ID_BARBEARIA INTEGER NOT NULL,
                DATA_MOV DATE NOT NULL, TIPO VARCHAR(10) NOT NULL, ORIGEM VARCHAR(30),
                DESCRICAO VARCHAR(255), VALOR NUMERIC(12,2) DEFAULT 0 NOT NULL,
                FONTE VARCHAR(10), ATUALIZADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)''')
            cursor.execute('CREATE SEQUENCE SEQ_FINANCEIRO_SNAPSHOT')
            cursor.execute('CREATE INDEX IDX_FINSNAP_BARB_DATA ON FINANCEIRO_SNAPSHOT(ID_BARBEARIA, DATA_MOV)')
            connection.commit()
            for row in [(1, 42, date(2026, 9, 30), 'entrada', 'pix', 'Histórico anterior', 9.99, 'arkhe'),
                        (2, 42, date(2026, 10, 2), 'entrada', 'dinheiro', 'Snapshot anterior', 19.99, 'local'),
                        (3, 99, date(2026, 10, 5), 'saida', 'pix', 'Outro salão', 7.50, 'arkhe')]:
                cursor.execute('''INSERT INTO FINANCEIRO_SNAPSHOT
                    (ID_SNAPSHOT, ID_BARBEARIA, DATA_MOV, TIPO, ORIGEM, DESCRICAO, VALOR, FONTE)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', row)
            cursor.execute('SET GENERATOR SEQ_FINANCEIRO_SNAPSHOT TO 3')
            connection.commit()
            cursor.close()
        finally:
            connection.close()
        self.client = main.app.test_client()
        self.original_rows = self.rows()

    def connect(self):
        return firebirdsql.connect(**self.connection_options)

    def drop_created_database(self):
        # This path is generated here, never read from production configuration.
        if self.database.parent != self.directory or not self.directory.name.startswith('cortae-arkhe-snapshot-'):
            raise AssertionError('Unexpected disposable database path.')
        connection = self.connect()
        connection.drop_database()
        self.directory.rmdir()

    def rows(self):
        connection = self.connect()
        try:
            cursor = connection.cursor()
            cursor.execute('SELECT * FROM FINANCEIRO_SNAPSHOT ORDER BY ID_SNAPSHOT')
            return cursor.fetchall()
        finally:
            connection.close()

    def source_length(self, cursor):
        cursor.execute('''SELECT F.RDB$CHARACTER_LENGTH FROM RDB$RELATION_FIELDS RF
            JOIN RDB$FIELDS F ON F.RDB$FIELD_NAME = RF.RDB$FIELD_SOURCE
            WHERE TRIM(RF.RDB$RELATION_NAME) = 'FINANCEIRO_SNAPSHOT'
              AND TRIM(RF.RDB$FIELD_NAME) = 'FONTE' ''')
        return cursor.fetchone()[0]

    def request_mixed(self, route, preparar=True):
        # Fixture starts with legacy VARCHAR(10). Update explicitly, as an
        # operator now must do; the HTTP route never changes this structure.
        if preparar:
            connection = self.connect()
            try:
                snapshot_schema._garantir_snapshot(connection.cursor())
                connection.commit()
            finally:
                connection.close()
        provider_payload = [{'id': 'qa-provider', 'tipo': 'entrada', 'valor': 40.25,
            'data': '2026-10-05', 'origem': 'pix', 'descricao': 'Pagamento fictício'}]
        cash_payload = [{'id_movimentacao': 'qa-cash', 'tipo': 'entrada', 'valor': 59.75,
            'data_movimentacao': '2026-10-06', 'origem': 'na_hora', 'nome_contraparte': 'Dinheiro fictício'}]
        with patch.object(arkhe, '_autorizado', return_value=({'id_usuario': 42, 'tipo': 2}, None)), \
             patch.object(arkhe, '_contexto_financeiro', return_value=(42, ('qa-id', 'qa-secret'))), \
             patch.object(arkhe, '_chamar_arkhe', return_value=provider_payload) as provider, \
             patch.object(arkhe, '_movimentacoes_locais', return_value=cash_payload) as local, \
             patch.object(arkhe, 'conectar_banco', side_effect=self.connect), \
             patch.object(arkhe, '_auditar_snapshot'):
            response = self.client.get(route + '?data_inicio=2026-10-01&data_fim=2026-10-11')
        self.assertEqual(provider.call_args.args, ('GET', '/api/v1/movimentacoes'))
        self.assertEqual(local.call_args.kwargs['tipos'], ('na_hora',))
        return response

    def assert_preserved_history(self):
        rows = self.rows()
        unchanged = [row for row in rows if row[0] in (1, 3)]
        self.assertEqual(unchanged, [row for row in self.original_rows if row[0] in (1, 3)])
        fresh = [row for row in rows if row[1] == 42 and row[2].month == 10]
        self.assertEqual(len(fresh), 2)
        self.assertEqual({row[7] for row in fresh}, {'arkhe+na_hora'})
        self.assertEqual(sum(row[6] for row in fresh), 100)

    def test_migration_is_repeatable_and_preserves_all_existing_rows(self):
        connection = self.connect()
        try:
            cursor = connection.cursor()
            self.assertEqual(self.source_length(cursor), 10)
            snapshot_schema._garantir_snapshot(cursor)
            self.assertEqual(self.source_length(cursor), 32)
            snapshot_schema._garantir_snapshot(cursor)
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(self.rows(), self.original_rows)

    def test_new_snapshot_table_supports_mixed_source(self):
        connection = self.connect()
        try:
            cursor = connection.cursor()
            cursor.execute('DROP TABLE FINANCEIRO_SNAPSHOT')
            connection.commit()
            snapshot_schema._garantir_snapshot(cursor)
            self.assertEqual(self.source_length(cursor), 32)
        finally:
            connection.close()

    def test_widening_preserves_callers_unrelated_pending_changes(self):
        connection = self.connect()
        try:
            cursor = connection.cursor()
            cursor.execute('CREATE TABLE QA_PENDING(ID INTEGER PRIMARY KEY, VALOR INTEGER)')
            connection.commit()
            cursor.execute('INSERT INTO QA_PENDING VALUES(1,10)')
            connection.commit()
            cursor.execute('UPDATE QA_PENDING SET VALOR=99 WHERE ID=1')
            snapshot_schema._garantir_snapshot(cursor)
            self.assertEqual(self.source_length(cursor), 32)
            connection.rollback()
            cursor.execute('SELECT VALOR FROM QA_PENDING WHERE ID=1')
            self.assertEqual(cursor.fetchone()[0], 10)
        finally:
            connection.close()
        self.assertEqual(self.rows(), self.original_rows)

    def test_concurrent_preparations_retry_metadata_conflict_without_losing_history(self):
        # Synchronize both first ALTERs, guaranteeing they read VARCHAR(10)
        # before either migration commits. Retry uses the real driver/database.
        barrier = Barrier(2)
        driver_execute = snapshot_schema.Cursor.execute
        alterations = []
        conflicts = []

        def execute(cursor, query, params=None):
            if query == 'ALTER TABLE FINANCEIRO_SNAPSHOT ALTER FONTE TYPE VARCHAR(32)':
                alterations.append(query)
                if len(alterations) <= 2:
                    barrier.wait(timeout=10)
            try:
                return driver_execute(cursor, query, params)
            except firebirdsql.DatabaseError as error:
                conflicts.append(error.gds_codes)
                raise

        def prepare(_):
            connection = self.connect()
            try:
                cursor = connection.cursor()
                snapshot_schema._garantir_snapshot(cursor)
                connection.commit()
            finally:
                connection.close()

        with patch.object(snapshot_schema.Cursor, 'execute', execute), ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(prepare, range(2)))
        self.assertGreaterEqual(len(alterations), 2)
        self.assertTrue(any({335544351, 335544451} <= codes for codes in conflicts))
        connection = self.connect()
        try:
            self.assertEqual(self.source_length(connection.cursor()), 32)
        finally:
            connection.close()
        self.assertEqual(self.rows(), self.original_rows)

    def test_mixed_statement_request_preserves_full_source_and_unrelated_history(self):
        response = self.request_mixed('/financeiro/movimentacoes')
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.json['origem_dados'], 'arkhe+na_hora')
        self.assertEqual(response.json['total'], 2)
        self.assert_preserved_history()

    def test_mixed_chart_request_returns_svg_and_preserves_history(self):
        response = self.request_mixed('/financeiro/grafico')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/svg+xml')
        self.assertIn(b'<svg', response.data)
        self.assert_preserved_history()

    def test_unprepared_statement_fails_without_altering_schema_or_history(self):
        response = self.request_mixed('/financeiro/movimentacoes', preparar=False)
        self.assertEqual(response.status_code, 500)
        connection = self.connect()
        try:
            self.assertEqual(self.source_length(connection.cursor()), 10)
        finally:
            connection.close()
        self.assertEqual(self.rows(), self.original_rows)

    def test_failed_replacement_can_never_commit_partial_delete_or_insert(self):
        connection = self.connect()
        try:
            cursor = connection.cursor()
            snapshot_schema._garantir_snapshot(cursor)
            movements = [{'data_movimentacao': '2026-10-05', 'tipo': 'entrada', 'valor': 12.34},
                         {'data_movimentacao': '2026-10-06', 'tipo': 'invalid-too-long-for-type', 'valor': 9.87}]
            with self.assertRaises(firebirdsql.DatabaseError):
                arkhe._sincronizar_snapshot(cursor, 42, movements, '2026-10-01', '2026-10-11', 'arkhe+na_hora')
            # Simulates a caller mistakenly committing after the failed sync.
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(self.rows(), self.original_rows)


if __name__ == '__main__':
    unittest.main()
