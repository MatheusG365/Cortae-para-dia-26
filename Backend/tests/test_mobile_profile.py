"""Owner public profile patch contract without production DB writes."""
import os
os.environ['STARTUP_MIGRATIONS'] = 'false'
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
import main
import barbearia


class MobileProfileTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()
        self.owner = {'tipo': 2, 'id_usuario': 17}
        self.row = (4, '#101010', '#191919', '#FF8800', '#FFFFFF', '#A9A9A9', 'História', 'Rua exemplo', '11999999999', 'contato@example.invalid', '@salao')

    def invoke(self, method='PATCH', data=None, user=True, rows=None):
        con = MagicMock()
        con.cursor.return_value.fetchone.side_effect = rows or [(17,), self.row, self.row]
        with ExitStack() as stack:
            stack.enter_context(patch('barbearia.obter_usuario_logado', return_value=self.owner if user is True else user))
            stack.enter_context(patch('barbearia.conectar_banco', return_value=con))
            audit = stack.enter_context(patch('auditoria.registrar_log'))
            response = self.client.open('/barbearia/perfil', method=method, json=data)
        return response, con, audit

    def test_get_returns_only_public_fields(self):
        response, con, _ = self.invoke('GET')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['personalizacao']['id_usuario'], 17)
        self.assertEqual(response.json['personalizacao']['historia'], 'História')
        self.assertNotIn('arkhe', response.get_data(as_text=True).lower())
        self.assertNotIn('pix', response.get_data(as_text=True).lower())
        con.commit.assert_not_called()
        self.assert_safe_sql(con)

    def test_patch_changes_only_requested_fields_of_authenticated_owner(self):
        response, con, audit = self.invoke(data={'historia': 'Nova história', 'contato_telefone': '(11) 99999-9999'})
        self.assertEqual(response.status_code, 200)
        update = [c for c in con.cursor.return_value.execute.call_args_list if c.args[0].startswith('UPDATE')]
        self.assertEqual(len(update), 1)
        sql, values = update[0].args
        fields = sql.split(' SET ')[1].split(' WHERE ')[0].split(',')
        self.assertEqual(dict(zip(fields, values[:-1])), {'TEXTO=?': 'Nova história', 'CONTATO_TELEFONE=?': '11999999999'})
        self.assertEqual(values[-1], 17)
        self.assertIn('WITH LOCK', con.cursor.return_value.execute.call_args_list[0].args[0])
        con.commit.assert_called_once()
        audit.assert_called_once()
        self.assert_safe_sql(con)

    def test_first_patch_creates_public_profile_without_payment_or_team_changes(self):
        response, con, _ = self.invoke(data={'localizacao': 'Rua nova'}, rows=[(17,), None, self.row])
        self.assertEqual(response.status_code, 200)
        inserts = [c for c in con.cursor.return_value.execute.call_args_list if c.args[0].startswith('INSERT')]
        self.assertEqual(len(inserts), 1)
        self.assertIn('NUM_FUNCIONARIOS', inserts[0].args[0])
        self.assertIn('Rua nova', inserts[0].args[1])
        self.assertEqual(len(inserts[0].args[1]), 11)
        count_update = [c for c in con.cursor.return_value.execute.call_args_list if c.args[0].startswith('UPDATE PERSONALIZACAO SET NUM_FUNCIONARIOS')]
        self.assertEqual(len(count_update), 1)
        self.assertEqual(count_update[0].args[1], (17, 17))
        self.assert_safe_sql(con)

    def test_get_absent_profile_is_explicit_and_does_not_create(self):
        response, con, _ = self.invoke('GET', rows=[(17,), None])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'personalizado': False, 'personalizacao': None})
        self.assertFalse(any(c.args[0].startswith('INSERT') for c in con.cursor.return_value.execute.call_args_list))

    def test_no_session_and_other_roles_are_rejected_before_db(self):
        for user, expected in ((None, 401), ({'tipo': 0, 'id_usuario': 1}, 403), ({'tipo': 1, 'id_usuario': 1}, 403), ({'tipo': 3, 'id_usuario': 1}, 403)):
            with self.subTest(user=user):
                response, con, _ = self.invoke(data={'historia': 'x'}, user=user)
                self.assertEqual(response.status_code, expected)
                con.cursor.assert_not_called()

    def test_unknown_fields_secrets_invalid_types_and_lengths_are_rejected(self):
        for data in ({'arkhe_client_secret': 'secret'}, {'chave_pix': 'pix'}, {'id_usuario': 99}, {'num_funcionarios': 0},
                     {'historia': 'a' * 1001}, {'instagram': 'a' * 101}, {'cor_primaria': 'red'}, {'cor_primaria': '#ABC'},
                     {'contato_email': 'invalid'}, {'contato_telefone': '123'}, {'historia': None}, {'historia': ['x']}, {}):
            with self.subTest(data=data):
                response, con, _ = self.invoke(data=data)
                self.assertEqual(response.status_code, 400)
                con.cursor.assert_not_called()

    def test_account_state_is_checked_again_before_write(self):
        response, con, _ = self.invoke(data={'historia': 'x'}, rows=[None])
        self.assertEqual(response.status_code, 401)
        con.commit.assert_not_called()

    def assert_safe_sql(self, con):
        sql = ' '.join(c.args[0] for c in con.cursor.return_value.execute.call_args_list).upper()
        for forbidden in ('ARKHE', 'CHAVE_PIX', 'UPDATE FUNCIONARIO', 'DELETE', 'DIAS_DE_SERVICO'):
            self.assertNotIn(forbidden, sql)


if __name__ == '__main__':
    unittest.main()
