"""ODS 13.0 catalog compatibility and repeatable, non-destructive index setup."""
import unittest
from unittest.mock import MagicMock, patch

from migrations import arkhe_cartao_schema as schema


class CardSchemaCompatibility(unittest.TestCase):
    def catalog(self, legacy=False):
        state = {'table': legacy, 'columns': {'ID_COMPRA', 'ID_MOVIMENTACAO'} if legacy else set(),
                 'indexes': {'UQ_CARTAO_COMPRA': None, 'UQ_CARTAO_MOVIMENTACAO': None} if legacy else {},
                 'row': None, 'ddl': []}
        con, cur = MagicMock(), MagicMock()
        con.cursor.return_value = cur

        def execute(sql, params=()):
            self.assertNotIn('RDB$CONDITION_', sql, 'ODS 13.0 has no partial-index catalog columns')
            if sql.startswith('SELECT 1 FROM RDB$RELATIONS'):
                state['row'] = (1,) if state['table'] else None
            elif sql.startswith('CREATE TABLE '):
                state['table'] = True
                state['columns'].update(('ID_COMPRA', 'ID_MOVIMENTACAO'))
                state['ddl'].append(sql)
            elif sql.startswith('SELECT 1 FROM RDB$RELATION_FIELDS'):
                state['row'] = (1,) if params[1] in state['columns'] else None
            elif sql.startswith('ALTER TABLE '):
                state['columns'].add(sql.split()[4])
                state['ddl'].append(sql)
            elif sql.startswith('SELECT RDB$EXPRESSION_SOURCE'):
                state['row'] = (state['indexes'][params[0]], 1, 0) if params[0] in state['indexes'] else None
            elif sql.startswith('CREATE UNIQUE INDEX '):
                name = sql.split()[3]
                self.assertIn(' COMPUTED BY (CASE WHEN ', sql)
                self.assertNotIn(' WHERE ', sql)
                state['indexes'][name] = sql.split(' COMPUTED BY ', 1)[1]
                state['ddl'].append(sql)
            elif sql.startswith('DROP INDEX '):
                del state['indexes'][sql.split()[2]]
                state['ddl'].append(sql)
            else:
                self.fail('Unexpected migration statement: ' + sql)

        cur.execute.side_effect = execute
        cur.fetchone.side_effect = lambda: state['row']
        return con, state

    def test_fresh_ods130_catalog_creates_computed_indexes_once(self):
        con, state = self.catalog()
        with patch.object(schema, 'conectar_banco', return_value=con):
            schema.migrar_cartao()
            first_ddl = list(state['ddl'])
            schema.migrar_cartao()
        self.assertEqual(state['ddl'], first_ddl, 'Second migration must preserve working indexes')
        self.assertEqual(sum(sql.startswith('CREATE UNIQUE INDEX ') for sql in first_ddl), 2)
        self.assertFalse(any(sql.startswith('DROP ') for sql in first_ddl))

    def test_existing_noncomputed_indexes_are_replaced_once(self):
        con, state = self.catalog(legacy=True)
        with patch.object(schema, 'conectar_banco', return_value=con):
            schema.migrar_cartao()
            first_ddl = list(state['ddl'])
            schema.migrar_cartao()
        self.assertEqual(state['ddl'], first_ddl)
        self.assertEqual(sum(sql.startswith('DROP INDEX ') for sql in first_ddl), 2)
        self.assertEqual(sum(sql.startswith('CREATE UNIQUE INDEX ') for sql in first_ddl), 2)


if __name__ == '__main__':
    unittest.main()
