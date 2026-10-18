"""Publishing must not embed database credentials or make imports open a database."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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


if __name__ == '__main__':
    unittest.main()
