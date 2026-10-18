"""Address-book persistence uses isolated SQLite; ViaCEP is always mocked."""
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ['WAITLIST_WORKER'] = 'false'

import main
import cep
import marketplace as mp
from migrations import marketplace_schema
ADDRESS = {'nome': 'Cliente QA', 'email': 'cliente@example.invalid',
           'telefone': '(11) 91234-5678', 'documento': '123.456.789-01',
           'cep': '01001-000', 'logradouro': ' Praça da Sé ', 'numero': '10',
           'complemento': 'Sala 2', 'bairro': 'Sé', 'cidade': 'São Paulo', 'uf': 'sp'}
PROVIDER = {'cep': '01001-000', 'logradouro': 'Praça da Sé', 'bairro': 'Sé',
            'localidade': 'São Paulo', 'uf': 'SP', 'ibge': '3550308'}


class Cursor:
    def __init__(self, database):
        self.cursor = database.cursor()

    def execute(self, sql, params=()):
        if sql == 'SELECT NEXT VALUE FOR SEQ_MP_ENDERECO FROM RDB$DATABASE':
            sql = 'SELECT COALESCE(MAX(ID_ENDERECO),0)+1 FROM MP_ENDERECO'
        self.cursor.execute(sql.replace(' WITH LOCK', ''), params)
        return self

    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()
    def close(self): self.cursor.close()


class Connection:
    def __init__(self, path): self.database = sqlite3.connect(path)
    def cursor(self): return Cursor(self.database)
    def commit(self): self.database.commit()
    def rollback(self): self.database.rollback()
    def close(self): self.database.close()


class AddressBook(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'addresses.sqlite')
        with sqlite3.connect(self.path) as database:
            database.executescript('''
                CREATE TABLE USUARIO(ID_USUARIO INTEGER PRIMARY KEY,TIPO INTEGER,ATIVO INTEGER,EMAIL_CONFIRMADO INTEGER);
                INSERT INTO USUARIO VALUES(1,1,1,1),(2,1,1,1),(3,2,1,1),(4,0,1,1),(5,1,0,1),(6,1,1,0);
                CREATE TABLE MP_ENDERECO(ID_ENDERECO INTEGER PRIMARY KEY,ID_USUARIO INTEGER REFERENCES USUARIO,
                    APELIDO TEXT,PADRAO INTEGER NOT NULL CHECK(PADRAO IN(0,1)),DADOS TEXT NOT NULL,
                    CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP,ATUALIZADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            ''')
        database.close()
        self.stack = ExitStack()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.stack.close)
        self.user = 1
        self.stack.enter_context(patch.object(mp, 'conectar_banco', side_effect=lambda: Connection(self.path)))
        self.stack.enter_context(patch.object(mp, 'obter_usuario_logado', side_effect=lambda: {'id_usuario': self.user} if self.user else None))
        self.audit = self.stack.enter_context(patch.object(mp, 'registrar_log'))
        self.client = main.app.test_client()

    def save(self, nickname='Casa', default=False, address=None, id_=None):
        return getattr(self.client, 'put' if id_ else 'post')(
            '/marketplace/enderecos' + ('/' + str(id_) if id_ else ''),
            json={'apelido': nickname, 'padrao': default, 'endereco': address or ADDRESS})

    def list(self): return self.client.get('/marketplace/enderecos').get_json()['enderecos']

    def test_create_edit_roundtrip_normalizes_without_provider_or_financial_effects(self):
        with patch.object(cep, 'consultar') as lookup, patch.object(mp.melhor_envio, 'calcular') as shipping:
            response = self.save()
            self.assertEqual(response.status_code, 201, response.get_json())
            saved = response.get_json()['endereco']
            self.assertTrue(saved['padrao'])
            self.assertEqual(saved['dados']['cep'], '01001000')
            self.assertEqual(saved['dados']['telefone'], '11912345678')
            self.assertEqual(saved['dados']['documento'], '12345678901')
            self.assertEqual(saved['dados']['uf'], 'SP')
            self.assertEqual(saved['dados']['logradouro'], 'Praça da Sé')
            self.assertEqual(self.list(), [saved])
            edited = self.save('Trabalho', address=ADDRESS | {'numero': '20'}, id_=saved['id_endereco'])
            self.assertEqual(edited.status_code, 200)
            self.assertEqual(self.list()[0]['dados']['numero'], '20')
            self.assertEqual(self.list()[0]['apelido'], 'Trabalho')
            lookup.assert_not_called(); shipping.assert_not_called()
        self.assertNotIn('cliente@example.invalid', str(self.audit.call_args_list))
        self.assertNotIn('12345678901', str(self.audit.call_args_list))

    def test_multiple_addresses_keep_exactly_one_selected_default(self):
        first = self.save().get_json()['endereco']
        second = self.save('Trabalho').get_json()['endereco']
        self.assertFalse(second['padrao'])
        self.assertEqual(self.list()[0]['id_endereco'], first['id_endereco'])
        self.save('Trabalho', True, id_=second['id_endereco'])
        self.assertEqual(self.list()[0]['id_endereco'], second['id_endereco'])
        self.assertEqual(sum(row['padrao'] for row in self.list()), 1)
        self.save('Trabalho', False, id_=second['id_endereco'])
        self.assertEqual(self.list()[0]['id_endereco'], first['id_endereco'])
        self.assertEqual(sum(row['padrao'] for row in self.list()), 1)

    def test_other_customer_cannot_read_or_edit_address_even_with_spoofed_ids(self):
        saved = self.save().get_json()['endereco']
        self.user = 2
        self.assertEqual(self.client.get('/marketplace/enderecos?id_usuario=1').get_json(), {'enderecos': []})
        response = self.client.put('/marketplace/enderecos/' + str(saved['id_endereco']),
                                   json={'id_usuario': 1, 'endereco': ADDRESS, 'padrao': True})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.save(id_=999).status_code, 404)
        self.user = 1
        self.assertEqual(self.list(), [saved])

    def test_customer_auth_checks_role_active_and_confirmed_account(self):
        for user, expected in ((None, 401), (3, 403), (4, 403), (5, 401), (6, 401), (999, 401)):
            self.user = user
            for method, route in (('get', '/marketplace/enderecos'), ('post', '/marketplace/enderecos'),
                                  ('put', '/marketplace/enderecos/1'), ('get', '/marketplace/cep/01001000')):
                with self.subTest(user=user, route=route), patch.object(cep, 'consultar') as lookup:
                    self.assertEqual(getattr(self.client, method)(route, json={}).status_code, expected)
                    lookup.assert_not_called()

    def test_invalid_address_default_and_json_never_persist(self):
        for address in (ADDRESS | {'cep': 'abc01001000'}, ADDRESS | {'uf': 'ZZ'},
                        ADDRESS | {'nome': ''}, ADDRESS | {'email': 'bad'},
                        ADDRESS | {'documento': '123'}, ADDRESS | {'telefone': ''}):
            with self.subTest(address=address): self.assertEqual(self.save(address=address).status_code, 400)
        for body in ([], {}, {'endereco': ADDRESS, 'padrao': 'true'}, {'endereco': ADDRESS, 'apelido': 'x'*81}):
            self.assertEqual(self.client.post('/marketplace/enderecos', json=body).status_code, 400)
        self.assertEqual(self.list(), [])

    def test_cep_route_status_and_response_contract(self):
        with patch.object(cep, 'consultar', return_value={'cep': '01001000', 'logradouro': 'Praça da Sé', 'bairro': 'Sé', 'cidade': 'São Paulo', 'uf': 'SP'}) as lookup:
            response = self.client.get('/marketplace/cep/01001-000')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.get_json()['endereco']), {'cep', 'logradouro', 'bairro', 'cidade', 'uf'})
        lookup.assert_called_once_with('01001-000')
        for status in (400, 404, 503):
            with patch.object(cep, 'consultar', side_effect=cep.CepErro('Falha segura.', status)):
                self.assertEqual(self.client.get('/marketplace/cep/01001000').status_code, status)

    def test_sender_postal_lookup_requires_owner_or_admin_of_valid_salon(self):
        for user, path, expected in ((1, '/gestao/marketplace/cep/01001000', 403),
                                     (3, '/gestao/marketplace/cep/01001000', 200),
                                     (4, '/gestao/marketplace/cep/01001000?id_barbearia=3', 200),
                                     (3, '/gestao/marketplace/cep/01001000?id_barbearia=9', 403)):
            self.user = user
            with self.subTest(user=user, path=path),patch.object(cep, 'consultar', return_value=PROVIDER) as lookup:
                response = self.client.get(path)
                self.assertEqual(response.status_code, expected)
                self.assertEqual(lookup.call_count, int(expected == 200))


class PostalLookup(unittest.TestCase):
    def setUp(self):
        cep._cache.clear()
        self.addCleanup(cep._cache.clear)

    def request(self, data=PROVIDER, status=200, chunks=None):
        session = MagicMock()
        response = session.__enter__.return_value.get.return_value.__enter__.return_value
        response.status_code = status
        response.iter_content.return_value = chunks if chunks is not None else [json.dumps(data).encode('utf-8')]
        return session

    def test_only_ascii_cep_reaches_fixed_https_host_no_redirect_proxy_credentials_or_pii(self):
        session = self.request()
        with patch.object(cep.requests, 'Session', return_value=session):
            result = cep.consultar('01001-000')
        client = session.__enter__.return_value
        self.assertFalse(client.trust_env)
        self.assertEqual(client.get.call_args.args, ('https://viacep.com.br/ws/01001000/json/',))
        self.assertEqual(client.get.call_args.kwargs, {'timeout': (3, 5), 'allow_redirects': False,
                                                      'stream': True, 'headers': {'Accept': 'application/json'}})
        self.assertEqual(result, {'cep': '01001000', 'logradouro': 'Praça da Sé', 'bairro': 'Sé', 'cidade': 'São Paulo', 'uf': 'SP'})

    def test_invalid_input_never_opens_network(self):
        for value in ('123', '123456789', '01001 000', ' 01001000', 'https://evil.test', '１２３４５６７８', 1001000, None):
            with self.subTest(value=value), patch.object(cep.requests, 'Session') as network:
                with self.assertRaises(cep.CepErro) as caught: cep.consultar(value)
                self.assertEqual(caught.exception.status, 400)
                network.assert_not_called()

    def test_not_found_and_provider_failures_are_safe_and_bounded(self):
        scenarios = (({'erro': True}, 200, None, 404), (PROVIDER, 302, None, 503),
                     (PROVIDER, 503, None, 503), (PROVIDER | {'uf': 'ZZ'}, 200, None, 503),
                     (PROVIDER | {'cep': '02002000'}, 200, None, 503),
                     (PROVIDER | {'cep': 'invalid'}, 200, None, 503),
                     (PROVIDER | {'localidade': ''}, 200, None, 503),
                     ([], 200, None, 503), (PROVIDER, 200, [b'bad-json'], 503),
                     (PROVIDER, 200, [b'x' * (cep.MAX_RESPONSE_BYTES + 1)], 503))
        for data, status, chunks, expected in scenarios:
            with self.subTest(data=data, status=status), patch.object(cep.requests, 'Session', return_value=self.request(data, status, chunks)):
                with self.assertRaises(cep.CepErro) as caught: cep.consultar('01001000')
                self.assertEqual(caught.exception.status, expected)
        session = self.request()
        session.__enter__.return_value.get.side_effect = cep.requests.Timeout('secret provider internal details')
        with patch.object(cep.requests, 'Session', return_value=session):
            with self.assertRaises(cep.CepErro) as caught: cep.consultar('01001000')
        self.assertEqual(caught.exception.status, 503)
        self.assertNotIn('secret', str(caught.exception))

    def test_city_level_postal_code_can_have_blank_street_and_neighborhood(self):
        with patch.object(cep.requests, 'Session', return_value=self.request(PROVIDER | {'logradouro': '', 'bairro': ''})):
            self.assertEqual(cep.consultar('01001000')['logradouro'], '')

    def test_cache_has_ttl_size_limit_and_returns_copies(self):
        session = self.request()
        with patch.object(cep.requests, 'Session', return_value=session) as network, patch.object(cep.time, 'monotonic', return_value=10):
            result = cep.consultar('01001000')
            result['cidade'] = 'mutated'
            self.assertEqual(cep.consultar('01001000')['cidade'], 'São Paulo')
            self.assertEqual(network.call_count, 1)
        with patch.object(cep.requests, 'Session', return_value=self.request()) as network, patch.object(cep.time, 'monotonic', return_value=10 + cep.CACHE_TTL + 1):
            cep.consultar('01001000')
            network.assert_called_once()
        for index in range(cep.CACHE_SIZE + 10): cep._cache[str(index)] = (999999999999, {})
        with patch.object(cep.requests, 'Session', return_value=self.request(PROVIDER | {'cep': '02002-000'})):
            cep.consultar('02002000')
        self.assertEqual(len(cep._cache), cep.CACHE_SIZE)


class AddressSchema(unittest.TestCase):
    def test_additive_address_table_and_sequence_are_idempotent(self):
        objects = {'tabela': set(), 'sequence': set()}
        cursor = MagicMock()
        state = {'row': None}
        created = []

        def execute(sql, params=()):
            if sql.startswith('SELECT 1 FROM RDB$'):
                kind = 'tabela' if 'RDB$RELATIONS' in sql else 'sequence'
                state['row'] = (1,) if params[0] in objects[kind] else None
            elif sql.startswith('CREATE TABLE ') or sql.startswith('CREATE SEQUENCE '):
                kind = 'tabela' if sql.startswith('CREATE TABLE ') else 'sequence'
                name = sql.split()[2]
                objects[kind].add(name); created.append(name)
            elif sql.startswith('SELECT ID FROM MP_INTEGRACAO'):
                state['row'] = (1,)

        cursor.execute.side_effect = execute
        cursor.fetchone.side_effect = lambda: state['row']
        connection = MagicMock(); connection.cursor.return_value = cursor
        with patch.object(marketplace_schema, 'conectar_banco', return_value=connection), \
             patch('migrations.marketplace_comercial_schema.migrar_comercial'):
            marketplace_schema.migrar_marketplace()
            marketplace_schema.migrar_marketplace()
        self.assertEqual(created.count('MP_ENDERECO'), 1)
        self.assertEqual(created.count('SEQ_MP_ENDERECO'), 1)
        self.assertIn('REFERENCES USUARIO(ID_USUARIO)', marketplace_schema.TABLES['MP_ENDERECO'])


if __name__ == '__main__': unittest.main()
