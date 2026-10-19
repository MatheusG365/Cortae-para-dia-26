"""Guias privados devem descrever rotas reais sem executar serviços ou ler segredos."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
from contextlib import ExitStack
import json
import unittest
from unittest.mock import patch

import main
import admin_help
import api_docs
from request_docs import GUIAS


class RequestDocumentationTests(unittest.TestCase):
    def test_shared_guides_link_exact_registered_methods_and_are_pure(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(admin_help, 'decodificar_token', return_value={'tipo': 0}))
            stack.enter_context(patch.object(api_docs, 'decodificar_token', return_value={'tipo': 0}))
            for target in ('database.conectar_banco', 'auditoria.conectar_banco_log',
                           'cep.consultar', 'melhor_envio.chamar', 'visagismo.analisar_com_ia',
                           'image_storage._provider', 'requests.sessions.Session.request'):
                stack.enter_context(patch(target, side_effect=AssertionError('Documentation performed business I/O')))
            stack.enter_context(patch.dict(main.app.config, {
                'OPENAI_API_KEY': 'PRIVATE_DOC_SENTINEL',
                'MELHOR_ENVIO_TOKEN': 'PRIVATE_DELIVERY_SENTINEL',
                'GOOGLE_DRIVE_CREDENTIALS_FILE': 'PRIVATE_DRIVE_SENTINEL'}))
            client = main.app.test_client()
            help_response = client.get('/admin/help/catalogo')
            doc_response = client.get('/openapi.json')
        self.assertEqual(help_response.status_code, 200)
        self.assertEqual(doc_response.status_code, 200)
        catalog, spec = help_response.json, doc_response.json
        guias = catalog['requisicoes']['guias']
        self.assertEqual({g['id'] for g in guias}, {'logs', 'visagismo', 'agendamento', 'compras', 'entregas', 'cep'})
        self.assertEqual(spec['x-cortae-fluxos'], GUIAS)
        self.assertEqual(spec['info']['version'], '2.4.0')
        backend = {r['id']: r for r in catalog['rotas'] if r['origem'] == 'backend'}
        for guia in guias:
            self.assertIn(guia['titulo'], spec['info']['description'])
            for req in guia['requisicoes']:
                with self.subTest(guia=guia['id'], rota=req['rota'], metodo=req['metodo']):
                    self.assertIn('api_id', req)
                    actual = backend[req['api_id']]
                    self.assertIn(req['metodo'], actual['metodos'])
                    operation = spec['paths'][req['rota']][req['metodo'].lower()]
                    self.assertIn(guia['id'], operation['x-cortae-fluxos'])
        text = json.dumps([catalog['requisicoes'], spec], ensure_ascii=False)
        for secret in ('PRIVATE_DOC_SENTINEL', 'PRIVATE_DELIVERY_SENTINEL', 'PRIVATE_DRIVE_SENTINEL'):
            self.assertNotIn(secret, text)
        for response in (help_response, doc_response):
            self.assertEqual(response.headers['Cache-Control'], 'private, no-store')

    def test_non_admin_cannot_construct_or_receive_new_guides(self):
        for role, expected in ((None, 401), (1, 403), (2, 403), (3, 403)):
            actor = None if role is None else {'tipo': role}
            with patch.object(admin_help, 'decodificar_token', return_value=actor), \
                    patch.object(api_docs, 'decodificar_token', return_value=actor), \
                    patch('request_docs.catalogo_requisicoes') as build:
                for path in ('/admin/help/catalogo', '/openapi.json', '/docs'):
                    with self.subTest(role=role, path=path):
                        response = main.app.test_client().get(path)
                        self.assertEqual(response.status_code, expected)
                        self.assertNotIn('x-cortae-fluxos', response.get_data(as_text=True))
                build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
