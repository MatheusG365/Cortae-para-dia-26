"""Regression checks without email, payment, AI calls or live DB writes."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import jwt
import main
import auditoria
import database
from migrations import database_schema
import funcoes
import visagismo


class Regressions(unittest.TestCase):
    def setUp(self):
        self.app = main.app
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.client = self.app.test_client()

    def connection(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        return connection, cursor

    def token(self, **extra):
        payload = dict(id_usuario=7, tipo=0, exp=datetime.now(timezone.utc) + timedelta(minutes=5))
        payload.update(extra)
        return jwt.encode(payload, self.app.config['SECRET_KEY'], algorithm='HS256')

    def test_unchanged_audit_does_not_connect(self):
        with patch.object(auditoria, 'conectar_banco_log') as connect:
            self.assertEqual(auditoria.registrar_log('UPDATE', 'USUARIO', 7,
                dados_antes={'NOME': 'A'}, dados_depois={'NOME': 'A'}, id_usuario=7), 0)
            connect.assert_not_called()

    def test_changed_audit_masks_secrets(self):
        con, cursor = self.connection()
        with patch.object(auditoria, 'conectar_banco_log', return_value=con):
            count = auditoria.registrar_log('UPDATE', 'USUARIO', 7,
                dados_antes={'NOME': 'A', 'SENHA_HASH': 'old-secret', 'EMAIL': 'same'},
                dados_depois={'NOME': 'B', 'SENHA_HASH': 'new-secret', 'EMAIL': 'same'}, id_usuario=7)
        self.assertEqual(count, 2)
        fields = [call.args[1][5] for call in cursor.execute.call_args_list]
        self.assertEqual(fields, ['NOME', 'SENHA_HASH'])
        self.assertEqual(cursor.execute.call_args_list[1].args[1][6:], ('[PROTEGIDO]', '[PROTEGIDO]'))
        con.commit.assert_called_once()
        cursor.close.assert_called_once()
        con.close.assert_called_once()

    def test_failed_audit_rolls_back_all_rows(self):
        con, cursor = self.connection()
        cursor.execute.side_effect = RuntimeError('simulated write failure')
        with patch.object(auditoria, 'conectar_banco_log', return_value=con), patch.dict(self.app.config, LOG_OBRIGATORIO=False):
            self.assertEqual(auditoria.registrar_log('UPDATE', 'USUARIO', 7, id_usuario=7,
                campo='NOME', valor_antes='A', valor_depois='B'), 0)
        con.rollback.assert_called_once()
        con.commit.assert_not_called()
        con.close.assert_called_once()

    def test_required_audit_propagates_failure(self):
        con, cursor = self.connection()
        cursor.execute.side_effect = RuntimeError('simulated')
        with patch.object(auditoria, 'conectar_banco_log', return_value=con), patch.dict(self.app.config, LOG_OBRIGATORIO=True):
            with self.assertRaises(RuntimeError):
                auditoria.registrar_log('DELETE', 'USUARIO', 7, id_usuario=7, dados_antes={'NOME': 'A'})
        con.rollback.assert_called_once()

    def test_sql_identifiers_reject_injection(self):
        with self.assertRaises(ValueError):
            auditoria.capturar_registro(MagicMock(), 'USUARIO;DROP TABLE USUARIO', 'ID_USUARIO', 7)

    def test_audit_token_uses_verified_current_user(self):
        auth_con, auth_cursor = self.connection()
        auth_cursor.fetchone.return_value = (1, 1, 1)
        log_con, log_cursor = self.connection()
        with self.app.test_request_context(headers={'Authorization': 'Bearer ' + self.token()}):
            with patch.object(database, 'conectar_banco', return_value=auth_con), patch.object(auditoria, 'conectar_banco_log', return_value=log_con):
                auditoria.registrar_log('LOGIN', 'USUARIO', 7, campo='ACESSO', valor_depois='ENTROU')
        self.assertEqual(log_cursor.execute.call_args.args[1][1], 7)

    def test_invalid_token_has_no_audit_provenance(self):
        with self.app.test_request_context(headers={'Authorization': 'Bearer invalid'}):
            self.assertIsNone(auditoria._obter_id_usuario_token())

    def test_disabled_user_loses_existing_token(self):
        con, cursor = self.connection()
        cursor.fetchone.return_value = (0, 0, 1)
        with self.app.test_request_context(headers={'Authorization': 'Bearer ' + self.token()}), patch.object(database, 'conectar_banco', return_value=con):
            self.assertIsNone(funcoes.decodificar_token())

    def test_token_role_reflects_current_account(self):
        con, cursor = self.connection()
        cursor.fetchone.return_value = (1, 1, 1)
        with self.app.test_request_context(headers={'Authorization': 'Bearer ' + self.token()}), patch.object(database, 'conectar_banco', return_value=con):
            self.assertEqual(funcoes.decodificar_token()['tipo'], 1)

    def test_startup_never_lowers_advanced_sequence(self):
        con, cursor = self.connection()
        cursor.fetchone.side_effect = [(1,), (8,), (20,)]
        database_schema.alinhar_sequence(con, cursor, 'SEQ_USUARIO', 'USUARIO', 'ID_USUARIO')
        self.assertEqual(cursor.execute.call_count, 3)
        self.assertFalse(any('SET GENERATOR' in call.args[0] for call in cursor.execute.call_args_list))

    def test_startup_commits_new_sequence_then_raises(self):
        con, cursor = self.connection()
        cursor.fetchone.side_effect = [None, (8,), (0,), (8,)]
        database_schema.alinhar_sequence(con, cursor, 'SEQ_USUARIO', 'USUARIO', 'ID_USUARIO')
        con.commit.assert_called_once()
        self.assertIn('CAST(? AS BIGINT)', cursor.execute.call_args.args[0])
        self.assertEqual(cursor.execute.call_args.args[1], (8,))

    def test_malformed_or_nonobject_json_is_bad_request(self):
        for raw in ('[1]', '"text"', 'true', 'null', '{broken'):
            with self.subTest(raw=raw):
                response = self.client.post('/login', data=raw, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['mensagem']['tipo'], 'erro')

    def test_nonstring_password_rejected_before_database(self):
        with patch('login.conectar_banco') as connect:
            response = self.client.post('/login', json={'email': 'a@b.test', 'senha': ['invalid']})
            self.assertEqual(response.status_code, 400)
            connect.assert_not_called()

    def test_public_cannot_register_admin(self):
        response = self.client.post('/cadastro', json={'nome': 'Teste', 'email': 'test@example.com',
            'telefone': '11999999999', 'senha': 'Strong123!', 'confirmarSenha': 'Strong123!', 'tipo': 0})
        self.assertEqual(response.status_code, 403)

    def test_health_readiness_without_credentials(self):
        with patch('application.verificar_banco', side_effect=[True, True]):
            response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['banco_log'])
        self.assertNotIn('password', response.get_data(as_text=True).lower())

    def test_health_fails_when_required_log_unavailable(self):
        with patch.dict(self.app.config, LOG_OBRIGATORIO=True), patch('application.verificar_banco', side_effect=[True, False]):
            response = self.client.get('/health')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json['pronto'])

    def test_http_errors_share_json_format(self):
        self.assertEqual(self.client.get('/missing-resource').json['mensagem']['tipo'], 'erro')
        self.assertEqual(self.client.get('/login').status_code, 405)

    def test_password_bcrypt_limit_in_utf8_bytes(self):
        senha = 'Aa1!' + 'é' * 35
        self.assertFalse(funcoes.verificar_senha_forte(senha)[0])
        self.assertFalse(funcoes.verificar_senha(senha, 'invalid-hash'))

    def test_invalid_stored_hash_returns_false(self):
        self.assertFalse(funcoes.verificar_senha('Good123!', 'invalid-hash'))

    def test_smtp_resource_closed_on_delivery_failure(self):
        with patch('funcoes.smtplib.SMTP_SSL') as smtp:
            smtp.return_value.__enter__.return_value.send_message.side_effect = RuntimeError('simulated')
            self.assertFalse(funcoes.enviando_email('test@example.com', 'Test', 'Test', 'Test'))
            smtp.return_value.__exit__.assert_called_once()

    def test_remote_image_rejects_private_addresses(self):
        for address in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '::1'):
            with self.subTest(address=address), patch('visagismo.socket.getaddrinfo', return_value=[(2, 1, 6, '', (address, 443))]):
                with self.assertRaises(ValueError):
                    visagismo.validar_url_imagem('https://example.com/image.png')

    def test_remote_image_rejects_redirect_to_private_host(self):
        with patch('visagismo.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError):
                visagismo.RedirecionamentoImagem().redirect_request(None, None, 302, '', {}, 'https://localhost/image.png')

    def test_remote_image_rejects_url_credentials_and_http(self):
        for url in ('http://example.com/a', 'https://user:pass@example.com/a', 'https://example.com:8080/a'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                visagismo.validar_url_imagem(url)

    def test_remote_image_connection_pins_validated_ip(self):
        with patch('visagismo.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))]):
            connection = visagismo.ConexaoImagemFixa('example.com')
        with patch('visagismo.socket.create_connection') as connect:
            connection._create_connection(('example.com', 443), timeout=20)
        self.assertEqual(connect.call_args.args[0], ('93.184.216.34', 443))
        self.assertEqual(connection.host, 'example.com')

    def test_image_transport_uses_pinned_tls_connection(self):
        handler = visagismo.TransporteImagem()
        with patch.object(handler, 'do_open') as do_open:
            handler.https_open(MagicMock())
        self.assertIs(do_open.call_args.args[0], visagismo.ConexaoImagemFixa)
        self.assertTrue(do_open.call_args.kwargs['context'].check_hostname)


if __name__ == '__main__':
    unittest.main()
