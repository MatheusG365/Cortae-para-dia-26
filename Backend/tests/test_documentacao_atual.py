"""Recent features are described without running business operations."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
from contextlib import ExitStack
import unittest
from unittest.mock import patch

import main
import api_docs
import admin_help


class CurrentDocumentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ExitStack() as stack:
            stack.enter_context(patch.object(admin_help, 'decodificar_token', return_value={'tipo': 0}))
            for target in ('application.conectar_banco', 'database.conectar_banco',
                           'requests.sessions.Session.request'):
                stack.enter_context(patch(target, side_effect=AssertionError('Docs must be read-only')))
            cls.document = api_docs.contrato_atual()
            response = main.app.test_client().get('/admin/help/catalogo')
            if response.status_code != 200:
                raise AssertionError(response.status_code)
            cls.catalog = response.json

    def test_booking_accepts_optional_staff_and_describes_signed_confirmation(self):
        paths = self.document['paths']
        booking = paths['/agendamentos']['post']
        schema = booking['requestBody']['content']['application/json']['schema']
        self.assertNotIn('id_funcionario', schema['required'])
        self.assertTrue(schema['properties']['id_funcionario']['nullable'])
        self.assertIn('confirmacao_resumo', schema['properties'])
        self.assertEqual(schema['properties']['escolha_corte']['enum'], ['catalogo', 'na_hora', 'profissional'])
        self.assertNotIn('Profissional obrigatório', booking['description'])
        self.assertIn('428', booking['responses'])
        summary = paths['/agendamentos/resumo']['post']['requestBody']['content']['application/json']['schema']
        self.assertTrue(summary['properties']['id_funcionario']['nullable'])

    def test_postal_and_saved_address_envelopes_match_backend(self):
        paths = self.document['paths']
        for path in ('/marketplace/cep/{postal_code}', '/gestao/marketplace/cep/{postal_code}'):
            operation = paths[path]['get']
            self.assertTrue(operation['security'])
            parameter = next(p for p in operation['parameters'] if p['name'] == 'postal_code')
            self.assertEqual(parameter['schema']['pattern'], '^[0-9]{5}-?[0-9]{3}$')
            schema = operation['responses']['200']['content']['application/json']['schema']
            self.assertEqual(set(schema['properties']['endereco']['properties']), {'cep', 'logradouro', 'bairro', 'cidade', 'uf'})
        listing = paths['/marketplace/enderecos']['get']['responses']['200']['content']['application/json']['schema']
        saved = listing['properties']['enderecos']['items']
        self.assertEqual(set(saved['properties']), {'id_endereco', 'apelido', 'padrao', 'dados'})
        self.assertIn('201', paths['/marketplace/enderecos']['post']['responses'])
        self.assertNotIn('200', paths['/marketplace/enderecos']['post']['responses'])

    def test_response_customization_does_not_change_unrelated_contracts(self):
        first = api_docs.operacao('A', 'A')
        second = api_docs.operacao('B', 'B')
        first['responses']['200']['description'] = 'only A'
        self.assertNotEqual(second['responses']['200']['description'], 'only A')
        self.assertNotIn('content', self.document['paths']['/health']['get']['responses']['200'])
        self.assertNotIn('content', api_docs.RESPOSTAS_PADRAO['200'])

    def test_help_explains_ficha_checkout_and_manual_database_maintenance(self):
        pages = {r['rota']: r for r in self.catalog['rotas'] if r['origem'] == 'frontend'}
        self.assertIn('PDF', pages['/gestao']['descricao'])
        self.assertIn('Salvar endereço', pages['/marketplace/carrinho']['descricao'])
        self.assertIn('Sem profissional definido', pages['/agendamento']['descricao'])
        steps = ' '.join(self.catalog['ajuda']['passos'])
        self.assertIn('python -m migrations', steps)
        self.assertIn('não criam tabelas', steps)
        self.assertIn('428', self.document['paths']['/termos-uso/aceite']['post']['responses'])
