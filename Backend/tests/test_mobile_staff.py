"""Scoped staff creation/state changes; email and database fully isolated."""
import os
os.environ['STARTUP_MIGRATIONS'] = 'false'
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
import main


class MobileStaffTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()
        self.owner = {'tipo': 2, 'id_usuario': 17}
        self.data = {'nome': 'Thiago', 'descricao': 'Profissional', 'email': 'thiago@example.invalid',
                     'telefone': '11999999999', 'comissao_percentual': 30}

    def invoke(self, path='/barbearia/funcionarios', method='POST', data=None, rows=None, user=True, delivered=True, fetchall=None):
        con = MagicMock()
        cur = con.cursor.return_value
        cur.fetchone.side_effect = rows if rows is not None else [(17,), (22,), (None, None, 'Thiago'), None, (31,)]
        if fetchall is not None:
            cur.fetchall.side_effect = fetchall
        def send(invites):
            con.commit.assert_called_once()
            return [{**invite, 'email_enviado': delivered} for invite in invites]
        with ExitStack() as stack:
            stack.enter_context(patch('barbearia.obter_usuario_logado', return_value=self.owner if user is True else user))
            stack.enter_context(patch('barbearia.conectar_banco', return_value=con))
            stack.enter_context(patch('agenda_equipe.criptografar_senha', return_value='mock-password-hash'))
            audit = stack.enter_context(patch('auditoria.registrar_log'))
            mail = stack.enter_context(patch('agenda_equipe.enviar_convites', side_effect=send))
            response = self.client.open(path, method=method, json=self.data if data is None else data)
        return response, con, audit, mail

    def test_create_reuses_native_invitation_flow_and_sends_only_after_commit(self):
        response, con, audit, mail = self.invoke()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['funcionario'], {'id_funcionario': 22, 'nome': 'Thiago', 'ativo': True, 'ids_servicos': []})
        self.assertTrue(response.json['convite_email_enviado'])
        self.assertTrue(response.json['configuracao_pendente'])
        raw = response.get_data(as_text=True).lower()
        for forbidden in ('token', 'link_ativacao', 'senha', 'arkhe', 'secret'):
            self.assertNotIn(forbidden, raw)
        sql = ' '.join(c.args[0] for c in con.cursor.return_value.execute.call_args_list)
        self.assertIn('BARBEIRO_CONVITE', sql)
        self.assertIn('NUM_FUNCIONARIOS=(SELECT COUNT(*)', sql)
        mail.assert_called_once(); audit.assert_called_once()

    def test_mail_failure_reports_persisted_staff_and_recoverable_invitation(self):
        response, con, _, _ = self.invoke(delivered=False)
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json['convite_email_enviado'])
        con.commit.assert_called_once()

    def test_existing_email_rolls_back_staff_insertion_and_never_sends_email(self):
        response, con, _, mail = self.invoke(rows=[(17,), (22,), (None, None, 'Thiago'), (999,)])
        self.assertEqual(response.status_code, 400)
        con.rollback.assert_called_once(); con.commit.assert_not_called(); mail.assert_not_called()

    def test_invalid_contact_is_rolled_back_by_existing_helper(self):
        for changes in ({'email': 'invalid'}, {'telefone': '123'}):
            with self.subTest(changes=changes):
                response, con, _, mail = self.invoke(data={**self.data, **changes}, rows=[(17,), (22,)])
                self.assertEqual(response.status_code, 400)
                con.rollback.assert_called_once(); con.commit.assert_not_called(); mail.assert_not_called()

    def test_invalid_payloads_rejected_before_database(self):
        for changes in ({'id_barbearia': 99}, {'arkhe_client_secret': 'secret'}, {'nome': ''}, {'nome': 'x' * 101},
                        {'comissao_percentual': True}, {'comissao_percentual': 'NaN'}, {'comissao_percentual': 101}, {'comissao_percentual': -1}):
            with self.subTest(changes=changes):
                response, con, _, mail = self.invoke(data={**self.data, **changes})
                self.assertEqual(response.status_code, 400)
                con.cursor.assert_not_called(); mail.assert_not_called()

    def test_scope_is_always_authenticated_owner_and_role_checked(self):
        for user in (None, {'tipo': 0, 'id_usuario': 1}, {'tipo': 1, 'id_usuario': 1}, {'tipo': 3, 'id_usuario': 1}):
            for path, method, data in (('/barbearia/funcionarios', 'POST', self.data), ('/barbearia/funcionarios/22/estado', 'PATCH', {'ativo': False})):
                with self.subTest(user=user, method=method):
                    response, con, _, mail = self.invoke(path, method, data, user=user)
                    self.assertEqual(response.status_code, 401 if user is None else 403)
                    con.cursor.assert_not_called(); mail.assert_not_called()

    def test_deactivate_future_booking_is_blocked_without_writes(self):
        response, con, _, mail = self.invoke('/barbearia/funcionarios/22/estado', 'PATCH', {'ativo': False}, [(17,), (22, 'Thiago', 1), (55,)])
        self.assertEqual(response.status_code, 409)
        self.assertFalse(any(c.args[0].startswith('UPDATE') for c in con.cursor.return_value.execute.call_args_list))
        con.commit.assert_not_called(); mail.assert_not_called()

    def test_deactivate_and_reactivate_preserve_user_login_state_and_history(self):
        for active, rows in ((False, [(17,), (22, 'Thiago', 1), None]), (True, [(17,), (22, 'Thiago', 0)])):
            with self.subTest(active=active):
                response, con, _, mail = self.invoke('/barbearia/funcionarios/22/estado', 'PATCH', {'ativo': active}, rows)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['funcionario']['ativo'], active)
                updates = [c for c in con.cursor.return_value.execute.call_args_list if c.args[0].startswith('UPDATE FUNCIONARIO')]
                self.assertEqual(updates[0].args[1], (int(active), 22, 17))
                sql = ' '.join(c.args[0] for c in con.cursor.return_value.execute.call_args_list)
                self.assertNotIn('UPDATE USUARIO', sql); self.assertNotIn('DELETE', sql)
                con.commit.assert_called_once(); mail.assert_not_called()

    def test_foreign_staff_not_found_and_never_modified(self):
        response, con, _, _ = self.invoke('/barbearia/funcionarios/99/estado', 'PATCH', {'ativo': False}, [(17,), None])
        self.assertEqual(response.status_code, 404)
        con.commit.assert_not_called()
        self.assertEqual(con.cursor.return_value.execute.call_args.args[1], (99, 17))

    def test_state_requires_actual_boolean_and_only_one_field(self):
        for data in ({'ativo': 0}, {'ativo': 'false'}, {'ativo': None}, {'ativo': False, 'id_usuario': 99}, {}):
            with self.subTest(data=data):
                response, con, _, _ = self.invoke('/barbearia/funcionarios/22/estado', 'PATCH', data)
                self.assertEqual(response.status_code, 400)
                con.cursor.assert_not_called()

    def test_new_professional_can_link_valid_own_active_services(self):
        response, con, _, _ = self.invoke(data={**self.data, 'ids_servicos': [3, 1, 3]}, fetchall=[[(1,), (3,)], []])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['funcionario']['ids_servicos'], [1, 3])
        inserts = [c.args[1] for c in con.cursor.return_value.execute.call_args_list if c.args[0].startswith('INSERT INTO SERVICO_POR_FUNCIONARIO')]
        self.assertEqual(inserts, [(22, 1), (22, 3)])

    def test_service_replacement_preserves_existing_prices_and_appointment_history(self):
        response, con, _, _ = self.invoke('/barbearia/funcionarios/22/servicos', 'PUT', {'ids_servicos': [3, 1, 3]},
                                          [(17,), (22,)], fetchall=[[(1,), (3,)], [(1,), (2,)]])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['ids_servicos'], [1, 3])
        calls = con.cursor.return_value.execute.call_args_list
        deletes = [c for c in calls if c.args[0].startswith('DELETE')]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0].args[1], (22, 2))
        inserts = [c.args[1] for c in calls if c.args[0].startswith('INSERT')]
        self.assertEqual(inserts, [(22, 3)])
        sql = ' '.join(c.args[0] for c in calls)
        self.assertNotIn('FUNCIONARIO_PRECO', sql)
        self.assertNotIn('AGENDAMENTO', sql)
        con.commit.assert_called_once()

    def test_services_from_other_salon_or_inactive_are_rejected(self):
        for path, method, data, rows in (
            ('/barbearia/funcionarios', 'POST', {**self.data, 'ids_servicos': [999]}, [(17,)]),
            ('/barbearia/funcionarios/22/servicos', 'PUT', {'ids_servicos': [999]}, [(17,), (22,)])):
            with self.subTest(path=path):
                response, con, _, mail = self.invoke(path, method, data, rows, fetchall=[[]])
                self.assertEqual(response.status_code, 400)
                con.commit.assert_not_called(); mail.assert_not_called()
                self.assertFalse(any(c.args[0].startswith(('INSERT', 'DELETE', 'UPDATE')) for c in con.cursor.return_value.execute.call_args_list))

    def test_service_ids_must_be_positive_integers_and_whitelisted(self):
        for ids in ([True], [0], [-1], ['1'], '1', None):
            for path, method, data in (
                ('/barbearia/funcionarios', 'POST', {**self.data, 'ids_servicos': ids}),
                ('/barbearia/funcionarios/22/servicos', 'PUT', {'ids_servicos': ids})):
                with self.subTest(ids=ids, method=method):
                    response, con, _, _ = self.invoke(path, method, data)
                    self.assertEqual(response.status_code, 400)
                    con.cursor.assert_not_called()

    def test_clear_services_keeps_prices_and_history(self):
        response, con, _, _ = self.invoke('/barbearia/funcionarios/22/servicos', 'PUT', {'ids_servicos': []},
                                          [(17,), (22,)], fetchall=[[(1,), (2,)]])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['ids_servicos'], [])
        sql = ' '.join(c.args[0] for c in con.cursor.return_value.execute.call_args_list)
        self.assertNotIn('FUNCIONARIO_PRECO', sql)
        self.assertNotIn('AGENDAMENTO', sql)


if __name__ == '__main__':
    unittest.main()
