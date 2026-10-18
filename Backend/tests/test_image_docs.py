"""Image documentation stays descriptive, private to ADM and free of integration I/O."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
from contextlib import ExitStack
import json
import unittest
from unittest.mock import patch

import main
import admin_help
import api_docs
from image_docs import MEDIA_PATHS, normalizar


class ImageDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ExitStack() as stack:
            stack.enter_context(patch.object(admin_help, 'decodificar_token', return_value={'tipo': 0}))
            for target in ('application.conectar_banco', 'database.conectar_banco',
                           'image_storage.conectar_banco', 'image_storage._provider',
                           'visagismo.carregar_referencia_corte', 'requests.sessions.Session.request'):
                stack.enter_context(patch(target, side_effect=AssertionError('Documentation must not call services')))
            stack.enter_context(patch.dict(main.app.config, {
                'GOOGLE_DRIVE_CREDENTIALS_FILE': 'PRIVATE_CONFIG_SENTINEL',
                'GOOGLE_DRIVE_FOLDER_IDS_FILE': 'PRIVATE_FOLDER_SENTINEL'}))
            response = main.app.test_client().get('/admin/help/catalogo')
            if response.status_code != 200:
                raise AssertionError(response.get_data(as_text=True))
            cls.catalog = response.json
            cls.headers = response.headers
        cls.paths = api_docs.contrato_atual()['paths']

    def test_help_image_payload_has_pure_flow_and_registered_api_ids(self):
        images = self.catalog['imagens']
        self.assertEqual(set(images), {'titulo', 'descricao', 'etapas', 'tipos', 'observacoes', 'apis', 'arquivos'})
        self.assertGreaterEqual(len(images['etapas']), 6)
        backend = {r['id']: r for r in self.catalog['rotas'] if r['origem'] == 'backend'}
        for api in images['apis']:
            self.assertEqual(api, {key: backend[api['id']][key] for key in ('id', 'rota', 'titulo', 'metodos')})
        media = {normalizar(api['rota']) for api in images['apis']}
        self.assertTrue(MEDIA_PATHS <= media)
        all_sources = {source['id'] for route in backend.values() for source in route['arquivos']}
        self.assertTrue(images['arquivos'])
        self.assertTrue(all(source['id'] in all_sources for source in images['arquivos']))
        text = json.dumps(images, ensure_ascii=False)
        for term in ('10 MB', '24 megapixels', '512 px', '1600 px', 'WebP', 'EXIF', 'Firebird',
                     'Drive', 'oito', 'seis', 'não há fallback', 'sete dias', 'tenta limpar'):
            self.assertIn(term, text)
        for forbidden in ('PRIVATE_CONFIG_SENTINEL', 'PRIVATE_FOLDER_SENTINEL', 'apps.googleusercontent.com',
                          'authorized_user.json', 'folders.json', 'FILE_ID=', 'GOCSPX-', str(admin_help.RAIZ)):
            self.assertNotIn(forbidden, text)
        self.assertEqual(self.headers['Cache-Control'], 'private, no-store')

    def test_media_success_is_binary_webp_with_public_or_conditional_access(self):
        for path in MEDIA_PATHS:
            contract = self.paths[path]['get']
            self.assertEqual(set(contract['responses']['200']['content']), {'image/webp'})
            self.assertEqual(contract['responses']['200']['content']['image/webp']['schema'],
                             {'type': 'string', 'format': 'binary'})
            self.assertNotIn('security', contract)  # cortes in the conditional route remains public
            for code in ('404', '503'):
                self.assertIn(code, contract['responses'])
        private = self.paths['/uploads/visagismo/{tipo}/{nome}']['get']
        for term in ('cliente dono', 'barbearia responsável', 'profissional vinculado', 'ADM', 'antes', '403'):
            self.assertIn(term, private['description'])
        kind = next(p for p in private['parameters'] if p['name'] == 'tipo')
        self.assertEqual(kind['schema']['enum'], ['cortes', 'fotos', 'resultados'])

    def test_actual_multipart_gallery_and_product_fields(self):
        salon = self.paths['/barbearia/personalizacao']['post']['requestBody']['content']['multipart/form-data']
        self.assertTrue({'logo', 'foto1', 'foto2', 'foto3', 'foto4', 'foto5'} <= salon['schema']['properties'].keys())
        self.assertNotIn('fotos', salon['schema']['properties'])
        for field in ('logo', 'foto1', 'foto5'):
            self.assertEqual(salon['schema']['properties'][field]['format'], 'binary')
            self.assertEqual(salon['schema']['properties'][field]['description'].count('JPEG, PNG, WebP ou GIF estático'), 1)
            self.assertIn('image/gif', salon['encoding'][field]['contentType'])
        for path, method in (('/gestao/marketplace/produtos', 'post'),
                             ('/gestao/marketplace/produtos/{id_produto}', 'put')):
            content = self.paths[path][method]['requestBody']['content']
            self.assertIn('application/json', content)
            multipart = content['multipart/form-data']['schema']
            self.assertEqual(multipart['required'], ['dados'])
            self.assertEqual(multipart['properties']['imagens']['maxItems'], 8)
            self.assertEqual(multipart['properties']['imagens']['items']['format'], 'binary')

    def test_help_searchable_routes_have_semantic_bytes_and_form_inputs(self):
        backend = [r for r in self.catalog['rotas'] if r['origem'] == 'backend']
        for route in backend:
            if normalizar(route['rota']) in MEDIA_PATHS:
                self.assertIn('Bytes: image/webp (imagem binária; não JSON).', route['saida'])
                searchable = json.dumps([route['titulo'], route['descricao'], route['como_funciona']], ensure_ascii=False).lower()
                for term in ('imagem', 'drive', 'webp'):
                    self.assertIn(term, searchable)
        salon = next(r for r in backend if r['rota'] == '/barbearia/personalizacao' and 'POST' in r['metodos'])
        for field in ('logo', 'foto1', 'foto5'):
            self.assertIn('Form: ' + field, salon['entrada'])
        product = next(r for r in backend if r['rota'] == '/gestao/marketplace/produtos' and 'POST' in r['metodos'])
        self.assertTrue({'Form: dados', 'Form: imagens'} <= set(product['entrada']))

    def test_mobile_flow_documents_content_vs_build_assets_and_native_permissions(self):
        mobile = self.catalog['mobile']
        flow = next(f for f in mobile['fluxos'] if f['id'] == 'imagens')
        self.assertTrue({'mobile:/cliente/perfil', 'mobile:/cliente/visagismo', 'mobile:/barbearia/produto'} <= set(flow['rotas']))
        text = json.dumps(mobile, ensure_ascii=False)
        for term in ('/midia/mobile/<nome>', 'seis', 'sem fallback', 'Drive'):
            self.assertIn(term, text)
        self.assertNotIn('PRIVATE_CONFIG_SENTINEL', text)

    def test_no_role_gains_access_to_help_or_schema(self):
        client = main.app.test_client()
        for role, expected in ((None, 401), (1, 403), (2, 403), (3, 403)):
            user = None if role is None else {'tipo': role}
            with patch.object(admin_help, 'decodificar_token', return_value=user), \
                 patch.object(api_docs, 'decodificar_token', return_value=user), \
                 patch.object(admin_help, '_catalogo', side_effect=AssertionError('No catalog before auth')):
                for path in ('/admin/help/catalogo', '/docs', '/openapi.json'):
                    response = client.get(path)
                    self.assertEqual(response.status_code, expected)
                    self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
                    self.assertNotIn('WebP', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
