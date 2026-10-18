"""Runtime detects missing structure; only an explicit maintenance command writes DDL."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ['WAITLIST_WORKER'] = 'false'
import main
import database
from migrations import __main__ as maintenance

BACKEND = Path(__file__).resolve().parents[1]


class DatabaseLifecycle(unittest.TestCase):
    def test_importing_api_never_connects_to_database_or_loads_schema_writers(self):
        script = '''
import os,sys
os.environ['WAITLIST_WORKER']='false'
from unittest.mock import patch
import database
with patch.object(database,'conectar_banco',side_effect=AssertionError('unexpected database access')) as connect:
    import main
    connect.assert_not_called()
assert not any(name.startswith('migrations.') for name in sys.modules)
print('ok')
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=BACKEND,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'ok')

    def test_missing_structure_is_reported_with_selects_only(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [('USUARIO', 'ID_USUARIO')]
        cursor.fetchone.return_value = (10,)
        with patch.object(database, 'ESTRUTURA_ESPERADA', {'USUARIO': ['ID_USUARIO', 'NOME'], 'MP_ENDERECO': ['DADOS']}):
            missing = database.pendencias_estrutura(cursor)
        self.assertEqual(missing, ['USUARIO.NOME', 'MP_ENDERECO.DADOS', 'FINANCEIRO_SNAPSHOT.FONTE: mínimo 32 caracteres'])
        self.assertTrue(all(call.args[0].lstrip().startswith('SELECT ') for call in cursor.execute.call_args_list))
        cursor.connection.commit.assert_not_called()

    def test_ready_schema_does_not_backfill_or_commit(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchall.return_value = [('USUARIO', 'ID_USUARIO')]
        cursor.fetchone.return_value = (64,)
        with main.app.app_context(), patch.object(database, 'conectar_banco', return_value=connection), patch.object(database, 'ESTRUTURA_ESPERADA', {'USUARIO': ['ID_USUARIO']}):
            self.assertTrue(database.verificar_banco())
        self.assertTrue(all(call.args[0].lstrip().startswith('SELECT ') for call in cursor.execute.call_args_list))
        connection.commit.assert_not_called()
        cursor.close.assert_called_once()
        connection.close.assert_called_once()

    def test_unavailable_structure_fails_readiness_without_modifying_it(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None
        with main.app.app_context(), patch.object(database, 'conectar_banco', return_value=connection), patch.object(database, 'ESTRUTURA_ESPERADA', {'USUARIO': ['ID_USUARIO']}):
            self.assertFalse(database.verificar_banco())
        connection.commit.assert_not_called()

    def test_default_maintenance_is_read_only_and_apply_requires_flag(self):
        with patch.object(maintenance, 'conferir', return_value=0) as check, patch.object(maintenance, 'aplicar', return_value=0) as apply:
            self.assertEqual(maintenance.main([]), 0)
            check.assert_called_once()
            apply.assert_not_called()
            self.assertEqual(maintenance.main(['--aplicar']), 0)
            apply.assert_called_once()

    def test_request_and_connection_modules_contain_no_ddl(self):
        for name in ('main.py', 'database.py', 'visagismo.py', 'arkhe.py'):
            with self.subTest(module=name):
                tree = ast.parse((BACKEND / name).read_text(encoding='utf-8-sig'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        self.assertNotRegex(node.value.lstrip().upper(), r'^(CREATE|ALTER|DROP)\s+(TABLE|SEQUENCE|INDEX)\b')
