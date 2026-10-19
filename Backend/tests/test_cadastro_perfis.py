"""Registration roles enforced server-side, without production data or e-mails."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from unittest.mock import MagicMock, patch

import main
import cadastro

PAYLOAD = dict(nome='Cliente Teste', email='qa@example.invalid', telefone='11912345678',
               senha='Ficticio123!', confirmarSenha='Ficticio123!', tipo=1)


class CadastroPerfisTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()

    def test_only_admin_can_create_establishment_or_admin_before_db_or_email(self):
        for actor in (None, {'tipo': 1}, {'tipo': 2}, {'tipo': 3}):
            for role in (0, 2):
                for headers in ({}, {'X-Cortae-Client': 'mobile'}):
                    with self.subTest(actor=actor, role=role, headers=headers), \
                            patch.object(cadastro, 'decodificar_token', return_value=actor), \
                            patch.object(cadastro, 'conectar_banco') as database, \
                            patch.object(cadastro, 'enviando_email') as mail:
                        result = self.client.post('/cadastro', json=PAYLOAD | {'tipo': role}, headers=headers)
                    self.assertEqual(result.status_code, 403)
                    database.assert_not_called()
                    mail.assert_not_called()

    def invoke_allowed(self, role, actor):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [None, (100,)]
        with patch.object(cadastro, 'decodificar_token', return_value=actor), \
                patch.object(cadastro, 'conectar_banco', return_value=connection), \
                patch.object(cadastro, 'documento_termos', return_value={'aceite_habilitado': False}), \
                patch.object(cadastro, 'criptografar_senha', return_value='fictional-hash'), \
                patch.object(cadastro, 'registrar_registro'), \
                patch.object(cadastro, 'enviando_email', return_value=True) as mail:
            result = self.client.post('/cadastro', json=PAYLOAD | {'tipo': role})
        self.assertEqual(result.status_code, 201, result.json)
        insert = next(call for call in cursor.execute.call_args_list if 'INSERT INTO USUARIO' in call.args[0])
        self.assertEqual(insert.args[1][5], role)
        connection.commit.assert_called_once()
        mail.assert_called_once()

    def test_public_customer_registration_remains_available(self):
        self.invoke_allowed(1, None)

    def test_admin_web_can_still_create_establishment_and_admin(self):
        for role in (0, 2):
            with self.subTest(role=role):
                self.invoke_allowed(role, {'tipo': 0, 'id_usuario': 10})


if __name__ == '__main__':
    unittest.main()
