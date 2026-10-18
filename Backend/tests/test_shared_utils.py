"""Refactoring regressions: transaction ownership and original text boundaries."""
import unittest
from unittest.mock import MagicMock

from contact_utils import digitos_telefone, email_sem_espacos
from financial_reference import id_agendamento_descricao
from migrations.schema_utils import criar_coluna, criar_sequence, criar_tabela, objeto_existe


class SharedUtilityContracts(unittest.TestCase):
    def test_missing_schema_objects_do_not_commit_callers_transaction(self):
        cursor=MagicMock();cursor.fetchone.return_value=None
        connection=cursor.connection
        criar_tabela(cursor, 'QA_TEST', 'CREATE TABLE QA_TEST (ID INTEGER)')
        criar_sequence(cursor, 'SEQ_QA_TEST')
        criar_coluna(cursor, 'QA_TEST', 'NOME', 'VARCHAR(50)')
        self.assertEqual(sum(call.args[0].startswith(('CREATE ', 'ALTER ')) for call in cursor.execute.call_args_list),3)
        connection.commit.assert_not_called()
        cursor.connection.commit.assert_not_called()

    def test_existing_schema_objects_never_execute_ddl_or_commit(self):
        cursor=MagicMock();cursor.fetchone.return_value=(1,)
        connection=MagicMock()
        criar_tabela(cursor, 'QA_TEST', 'CREATE TABLE QA_TEST (ID INTEGER)', connection)
        criar_sequence(cursor, 'SEQ_QA_TEST', connection)
        criar_coluna(cursor, 'QA_TEST', 'NOME', 'VARCHAR(50)', connection)
        self.assertTrue(all(call.args[0].startswith('SELECT ') for call in cursor.execute.call_args_list))
        connection.commit.assert_not_called()

    def test_explicit_commit_occurs_after_each_successful_ddl_only(self):
        cursor=MagicMock();cursor.fetchone.return_value=None
        connection=MagicMock()
        criar_tabela(cursor, 'QA_TEST', 'CREATE TABLE QA_TEST (ID INTEGER)', connection)
        criar_sequence(cursor, 'SEQ_QA_TEST', connection)
        criar_coluna(cursor, 'QA_TEST', 'NOME', 'VARCHAR(50)', connection)
        self.assertEqual(connection.commit.call_count,3)
        def fail_ddl(sql, *args):
            if sql.startswith('CREATE '):raise RuntimeError('DDL failure')
        cursor.execute.side_effect=fail_ddl
        with self.assertRaises(RuntimeError):criar_sequence(cursor, 'SEQ_FAIL', connection)
        self.assertEqual(connection.commit.call_count,3)

    def test_unknown_catalog_type_is_rejected_before_sql(self):
        cursor=MagicMock()
        with self.assertRaises(ValueError):objeto_existe(cursor, 'unknown', 'QA_TEST')
        cursor.execute.assert_not_called()

    def test_financial_markers_keep_exact_appointment_boundaries(self):
        for source in ('ag#10|na_hora', 'ARKHE:id ag#10', 'ag#10 pix_pago'):
            self.assertEqual(id_agendamento_descricao(source),10)
        for source in (None, '', 'myag#10|na_hora', 'ag#10x|na_hora'):
            self.assertIsNone(id_agendamento_descricao(source))

    def test_contact_normalisation_preserves_original_unicode_digit_policy(self):
        self.assertEqual(digitos_telefone('(11) 99999-0000'),'11999990000')
        self.assertEqual(digitos_telefone('² ١'),'²١')
        self.assertEqual(email_sem_espacos('  name @example.com  '),'name@example.com')
        self.assertEqual(email_sem_espacos('name\t@example.com'),'name\t@example.com')
