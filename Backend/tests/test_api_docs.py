"""Documentation never discloses contracts/HTML before current ADM authorization."""
import os
os.environ['WAITLIST_WORKER'] = 'false'

from datetime import datetime, timedelta, timezone
import re
import unittest
from unittest.mock import MagicMock, patch

import jwt
import main
import api_docs
import admin_help


class ApiDocsTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()

    def token(self, payload=None, secret=None):
        return jwt.encode(payload or {'id_usuario': 98765, 'tipo': 0},
                          secret or main.app.config['SECRET_KEY'], algorithm='HS256')

    def private_headers(self, response):
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(set(response.headers['Vary'].split(', ')), {'Cookie', 'Authorization'})

    def test_anonymous_and_other_roles_do_not_construct_schema_or_html(self):
        for role, status in ((None, 401), (1, 403), (2, 403), (3, 403)):
            for path in ('/docs', '/openapi.json'):
                for method in ('GET', 'HEAD'):
                    with self.subTest(role=role, path=path, method=method), \
                            patch.object(api_docs, 'decodificar_token', return_value=None if role is None else {'tipo': role}), \
                            patch.object(api_docs, 'contrato_atual') as schema, \
                            patch.object(api_docs, 'render_template_string') as render:
                        response = self.client.open(path, method=method)
                    self.assertEqual(response.status_code, status)
                    self.private_headers(response)
                    self.assertNotIn('openapi', response.get_data(as_text=True))
                    self.assertNotIn('SwaggerUIBundle', response.get_data(as_text=True))
                    schema.assert_not_called(); render.assert_not_called()

    def test_real_jwt_reloads_role_block_confirmation_and_missing_account_each_request(self):
        con = MagicMock()
        token = self.token()
        self.client.set_cookie('access_token', token)
        states = [((0, 1, 1), 200), ((1, 1, 1), 403), ((2, 1, 1), 403),
                  ((3, 1, 1), 403), ((0, 0, 1), 401), ((0, 1, 0), 401), (None, 401)]
        with patch('database.conectar_banco', return_value=con), \
                patch('agenda_equipe.funcionario_logado', return_value=(1, 2)):
            for row, status in states:
                con.cursor.return_value.fetchone.return_value = row
                for path in ('/docs', '/openapi.json'):
                    for method in ('GET', 'HEAD'):
                        with self.subTest(row=row, path=path, method=method):
                            response = self.client.open(path, method=method)
                            self.assertEqual(response.status_code, status)
                            self.private_headers(response)
                            if status != 200:
                                self.assertNotIn('SwaggerUIBundle', response.get_data(as_text=True))
                                self.assertNotIn('paths', response.get_data(as_text=True))
        self.assertEqual(con.cursor.return_value.execute.call_count, len(states)*4)
        self.assertEqual(con.cursor.return_value.close.call_count, len(states)*4)
        self.assertEqual(con.close.call_count, len(states)*4)

    def test_invalid_forged_expired_and_malformed_subject_never_query_accounts(self):
        expired = {'id_usuario': 98765, 'tipo': 0, 'exp': datetime.now(timezone.utc)-timedelta(seconds=1)}
        tokens = ['broken', self.token(secret='forged-only-test'), self.token(expired),
                  self.token({'id_usuario': True, 'tipo': 0}), self.token({'id_usuario': '98765', 'tipo': 0})]
        with patch('database.conectar_banco') as connect:
            for token in tokens:
                for path in ('/docs', '/openapi.json'):
                    with self.subTest(token=token, path=path):
                        response = self.client.get(path, headers={'Authorization': 'Bearer '+token})
                        self.assertEqual(response.status_code, 401)
                        self.private_headers(response)
            connect.assert_not_called()

    def test_database_outage_fails_closed(self):
        with patch('database.conectar_banco', side_effect=RuntimeError('account unavailable')):
            for path in ('/docs', '/openapi.json'):
                response = self.client.get(path, headers={'Authorization': 'Bearer '+self.token()})
                self.assertEqual(response.status_code, 401)
                self.assertNotIn('account unavailable', response.get_data(as_text=True))
                self.private_headers(response)

    def test_administrator_document_has_exact_live_methods_path_parameters_and_unique_ids(self):
        with patch.object(api_docs, 'decodificar_token', return_value={'tipo': 0}):
            response = self.client.get('/openapi.json')
        self.assertEqual(response.status_code, 200)
        self.private_headers(response)
        document = response.json
        expected = {(re.sub(r'<(?:\w+:)?([^>]+)>', r'{\1}', rule.rule), method.lower())
                    for rule in main.app.url_map.iter_rules() for method in rule.methods-{'HEAD', 'OPTIONS'}}
        actual = {(path, method) for path, methods in document['paths'].items() for method in methods}
        self.assertEqual(actual, expected)
        ids = []
        for path, methods in document['paths'].items():
            for contract in methods.values():
                ids.append(contract['operationId'])
                self.assertTrue(contract['summary']); self.assertTrue(contract['description'])
                self.assertIn('responses', contract)
                parameters = {p['name'] for p in contract.get('parameters', []) if p['in'] == 'path' and p['required']}
                self.assertEqual(parameters, set(re.findall(r'\{([^}]+)\}', path)))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(document['servers'][0]['url'], '.')

    def test_swagger_uses_current_origin_prefix_session_without_persisting_credentials(self):
        with patch.object(api_docs, 'decodificar_token', return_value={'tipo': 0}):
            response = self.client.get('/docs')
            head = self.client.head('/docs')
        self.assertEqual(response.status_code, 200); self.assertEqual(head.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("location.pathname.replace(/\\/docs\\/?$/, '')", html)
        self.assertIn("prefix+'/openapi.json'", html)
        self.assertIn("credentials:'include'", html)
        self.assertIn("spec.servers=[{url:prefix||'/'}]", html)
        self.assertIn('persistAuthorization:false', html)
        self.assertNotIn('localStorage', html)
        self.assertEqual(head.data, b'')
        self.private_headers(response); self.private_headers(head)

    def test_commercial_contracts_preserve_checkout_privacy_and_provider_limits(self):
        paths = api_docs.contrato_atual()['paths']
        product = paths['/gestao/marketplace/produtos']['post']['requestBody']['content']['application/json']['schema']
        self.assertTrue({'custo_compra', 'id_fornecedor', 'promocao_preco', 'lancamento_ate'} <= product['properties'].keys())
        checkout = paths['/marketplace/pedidos']['post']['requestBody']['content']['application/json']['schema']['properties']
        self.assertIn('confirmacao_resumo', checkout)
        self.assertNotIn('resumo_assinatura', checkout)
        self.assertIn('sem filtros', paths['/marketplace/pedidos']['get']['description'])
        self.assertIn('inclusive para GET', paths['/agendamentos/{id_agendamento}/avaliacao']['get']['description'])
        self.assertIn('desconto', paths['/gestao/marketplace/relatorios']['get']['description'])
        self.assertIn('nunca no frete', paths['/gestao/marketplace/cupons']['post']['description'])
        self.assertIn('403', paths['/gestao/marketplace/pedidos/{id_pedido}/etiqueta']['post']['description'])
        for path in ('/docs', '/openapi.json', '/admin/help/catalogo', '/admin/help/codigo/{codigo_id}'):
            self.assertIn('Exclusivo ADM', paths[path]['get']['description'])

    def test_help_describes_all_new_modules_and_get_post_contracts_without_business_calls(self):
        with patch.object(admin_help, 'decodificar_token', return_value={'tipo': 0}), \
                patch('database.conectar_banco', side_effect=AssertionError('read-only docs')):
            response = self.client.get('/admin/help/catalogo')
        self.assertEqual(response.status_code, 200)
        routes = {r['rota']: r for r in response.json['rotas'] if r['origem'] == 'backend'}
        pages = {r['rota']: r for r in response.json['rotas'] if r['origem'] == 'frontend'}
        self.assertIn('integrada', pages['/estabelecimento']['titulo'].lower())
        self.assertIn('independente', pages['/marketplace/lista-desejos']['titulo'].lower())
        self.assertIn('metas', pages['/gestao']['descricao'])
        self.assertIn('fornecedores', pages['/gestao-marketplace']['descricao'])
        pedido_routes = [r for r in response.json['rotas'] if r['origem'] == 'backend' and r['rota'] == '/marketplace/pedidos']
        self.assertIn('GET:', ' '.join(step for r in pedido_routes for step in r['como_funciona']))
        self.assertIn('POST:', ' '.join(step for r in pedido_routes for step in r['como_funciona']))
        self.assertIn('JSON: confirmacao_resumo', [field for r in pedido_routes for field in r['entrada']])
        self.assertIn('Query: agrupamento', routes['/gestao/marketplace/relatorios']['entrada'])
        self.assertIn('Somente administrador', routes['/docs']['acesso'])
        self.assertIn('Backend/docs_contracts.py', {f['caminho'] for f in routes['/docs']['arquivos']})


if __name__ == '__main__':
    unittest.main()
