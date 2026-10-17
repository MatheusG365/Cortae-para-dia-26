"""Native authentication contract; all DB and audit writes are isolated mocks."""
import os
os.environ['STARTUP_MIGRATIONS'] = 'false'
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
import jwt
import main


class MobileLoginTests(unittest.TestCase):
    def request_login(self, role=1, mobile=True, password_ok=True, active=1):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = (
            10, 'Teste', 'test@example.invalid', '11999999999', 'hash', role,
            active, 1, 0, 'masculino')
        with ExitStack() as stack:
            stack.enter_context(patch('login.conectar_banco', return_value=connection))
            stack.enter_context(patch('login.verificar_senha', return_value=password_ok))
            stack.enter_context(patch('login.capturar_registro', return_value={}))
            stack.enter_context(patch('login.registrar_registro'))
            stack.enter_context(patch('login.registrar_log'))
            stack.enter_context(patch('agenda_equipe.funcionario_logado', return_value={'id_funcionario': 5}))
            response = main.app.test_client().post('/login', json={
                'email': 'test@example.invalid', 'senha': 'TesteSenha123!'},
                headers={'X-Cortae-Client': 'mobile'} if mobile else {})
        return response, connection

    def test_native_clients_and_owners_receive_valid_bearer_without_cookie(self):
        for role in (1, 2):
            with self.subTest(role=role):
                response, _ = self.request_login(role=role)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['token_type'], 'Bearer')
                self.assertEqual(response.json['expires_in'], 7200)
                payload = jwt.decode(response.json['access_token'], main.app.config['SECRET_KEY'], algorithms=['HS256'])
                self.assertEqual(payload['tipo'], role)
                self.assertEqual(payload['id_usuario'], 10)
                self.assertFalse(response.headers.getlist('Set-Cookie'))
                self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_web_keeps_httponly_cookie_and_never_exposes_token(self):
        response, _ = self.request_login(mobile=False)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('access_token', response.json)
        cookie = response.headers['Set-Cookie']
        self.assertIn('access_token=', cookie)
        self.assertIn('HttpOnly', cookie)

    def test_mobile_does_not_add_admin_or_professional_access(self):
        for role in (0, 3):
            with self.subTest(role=role):
                response, connection = self.request_login(role=role)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn('access_token', response.json)
                self.assertFalse(response.headers.getlist('Set-Cookie'))
                connection.commit.assert_not_called()

    def test_native_header_never_bypasses_password_or_inactive_account(self):
        for args in ({'password_ok': False}, {'active': 0}, {'active': 2}):
            with self.subTest(args=args):
                response, _ = self.request_login(**args)
                self.assertIn(response.status_code, (401, 403))
                self.assertNotIn('access_token', response.json)
                self.assertFalse(response.headers.getlist('Set-Cookie'))


if __name__ == '__main__':
    unittest.main()
