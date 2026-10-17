"""Publishing must not embed database credentials or make imports open a database."""
import ast
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = ('test_arkhe_snapshot.py', 'test_image_storage_firebird.py',
            'test_marketplace_firebird.py', 'test_metas_firebird.py', 'test_ranking_avaliacoes.py')


class PrivateDatabaseConfigTests(unittest.TestCase):
    def test_disposable_fixture_passwords_use_scoped_environment_then_common_environment_then_config(self):
        app = SimpleNamespace(config={'DB_PASSWORD': 'synthetic-config-value'})
        for name in FIXTURES:
            tree = ast.parse((BACKEND / 'tests' / name).read_text(encoding='utf-8-sig'))
            values = [keyword.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                      for keyword in node.keywords if keyword.arg == 'password']
            self.assertEqual(len(values), 1, name)
            value = values[0]
            keys = [node.value for node in ast.walk(value) if isinstance(node, ast.Constant)
                    and isinstance(node.value, str) and node.value.endswith('_TEST_FIREBIRD_PASSWORD')]
            self.assertEqual(len(keys), 1, name)
            expression = compile(ast.Expression(value), name, 'eval')
            for environment, expected in (
                ({keys[0]: 'synthetic-scoped-value', 'DB_PASSWORD': 'synthetic-common-value'}, 'synthetic-scoped-value'),
                ({'DB_PASSWORD': 'synthetic-common-value'}, 'synthetic-common-value'),
                ({}, 'synthetic-config-value')):
                with self.subTest(fixture=name, source=expected), patch.dict(os.environ, environment, clear=True):
                    self.assertEqual(eval(expression, {'os': os, 'main': SimpleNamespace(app=app), 'app': app}), expected)

    def load_script(self, name):
        connection = MagicMock()
        driver = SimpleNamespace(connect=MagicMock(return_value=connection))
        settings = SimpleNamespace(DB_HOST='synthetic-host', DB_PORT=3051, DB_NAME='synthetic-database',
                                   DB_USER='synthetic-user', DB_PASSWORD='synthetic-private-value')
        with patch.dict('sys.modules', {'config': settings, 'firebirdsql': driver}):
            namespace = runpy.run_path(str(BACKEND / name))
        driver.connect.assert_not_called()
        return namespace, driver, settings, connection

    def test_diagnostic_import_is_read_only_and_explicit_run_uses_all_configured_connection_fields(self):
        for name in ('verificar_categorias.py', 'verificar_servicos.py'):
            with self.subTest(script=name):
                namespace, driver, settings, connection = self.load_script(name)
                connection.cursor.return_value.fetchall.return_value = []
                connection.cursor.return_value.fetchone.return_value = (0,)
                with redirect_stdout(io.StringIO()) as output:
                    namespace['main']()
                driver.connect.assert_called_once_with(host=settings.DB_HOST, port=settings.DB_PORT,
                    database=settings.DB_NAME, user=settings.DB_USER, password=settings.DB_PASSWORD, charset='UTF8')
                self.assertNotIn(settings.DB_PASSWORD, output.getvalue())
                connection.cursor.return_value.close.assert_called_once()
                connection.close.assert_called_once()

    def test_diagnostic_query_failure_closes_resources(self):
        for name in ('verificar_categorias.py', 'verificar_servicos.py'):
            with self.subTest(script=name):
                namespace, driver, settings, connection = self.load_script(name)
                connection.cursor.return_value.execute.side_effect = RuntimeError('synthetic query error')
                with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                    namespace['main']()
                connection.cursor.return_value.close.assert_called_once()
                connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
