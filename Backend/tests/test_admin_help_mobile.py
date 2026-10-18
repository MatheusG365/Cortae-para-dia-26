"""Catálogo mobile real, documentação de consulta e limites de leitura de fontes."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import re
import stat
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import main
import admin_help as help_api
from mobile_help import TELAS, caminho_router, _paginas


class HelpMobileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = help_api._catalogo()
        cls.telas = [r for r in cls.catalogo['rotas'] if r['origem'] == 'mobile']

    def test_exactly_matches_real_expo_router_pages_and_curated_current_map(self):
        pasta = help_api.RAIZ / 'Cortae_mobile-main/src/app'
        arquivos = {p for p in pasta.rglob('*.tsx') if p.stem != '_layout'}
        self.assertEqual(len(self.telas), len(arquivos))
        self.assertEqual({r['rota'] for r in self.telas}, {caminho_router(p, pasta) for p in arquivos})
        self.assertEqual({r['rota'] for r in self.telas}, set(TELAS))
        self.assertEqual(self.catalogo['total']['mobile'], len(arquivos))
        self.assertEqual(len({r['id'] for r in self.telas}), len(arquivos))
        self.assertFalse(any('configuracao' in r['rota'] or '/admin' in r['rota'] for r in self.telas))
        for rota in self.telas:
            with self.subTest(rota=rota['rota']):
                self.assertIn(rota['area'], ('publico', 'cliente', 'barbearia'))
                self.assertEqual(rota['metodos'], ['NAVEGAÇÃO'])
                self.assertTrue(rota['titulo']); self.assertTrue(rota['descricao'])
                self.assertGreaterEqual(len(rota['como_funciona']), 3)
                self.assertEqual(rota['arquivos'][0]['caminho'], 'Cortae_mobile-main/src/app/' + rota['endpoint'])

    def test_layouts_and_typescript_implementations_are_code_dependencies_not_pages(self):
        booking = next(r for r in self.telas if r['rota'] == '/cliente/agendar')
        paths = {f['caminho'] for f in booking['arquivos']}
        for esperado in ('src/app/_layout.tsx', 'src/app/cliente/_layout.tsx',
                         'src/features/client/Booking.tsx', 'src/features/client/clientRules.ts',
                         'src/lib/session.tsx', 'src/lib/api.ts', 'src/lib/apiAddress.ts',
                         'src/lib/dialogs.tsx', 'src/lib/dialogQueue.ts', 'src/ui.tsx'):
            self.assertIn('Cortae_mobile-main/' + esperado, paths)
        self.assertTrue(all('_layout' not in r['rota'] for r in self.telas))
        for rota in self.telas:
            for fonte in rota['arquivos']:
                self.assertRegex(fonte['id'], r'^[a-f0-9]{32}$')
                self.assertIn(Path(fonte['caminho']).suffix, ('.ts', '.tsx', '.js', '.jsx'))

    def test_all_linked_api_ids_are_current_registered_handlers(self):
        backend = {r['id']: r for r in self.catalogo['rotas'] if r['origem'] == 'backend'}
        for rota in self.telas:
            for relacionada in rota['api_relacionada']:
                self.assertIn(relacionada['id'], backend)
                self.assertEqual(relacionada, {k: backend[relacionada['id']][k] for k in ('id', 'rota', 'metodos', 'titulo')})
        atual = {re.sub(r'<(?:\w+:)?[^>]+>', ':id', r['rota']) for r in backend.values()}
        for caminho, dados in TELAS.items():
            with self.subTest(caminho=caminho):
                self.assertTrue(set(dados['api']) <= atual, set(dados['api']) - atual)

    def test_api_links_select_the_handler_used_by_each_screen(self):
        casos = [('/cliente/visagismo', '/visagismo/cortes', 'GET'),
                 ('/cliente/servicos', '/barbearia/servicos', 'GET'),
                 ('/cliente/agendamentos', '/agendamentos', 'GET'),
                 ('/cliente/agendar', '/agendamentos', 'POST'),
                 ('/cliente/pedidos', '/marketplace/pedidos', 'GET'),
                 ('/cliente/checkout', '/marketplace/pedidos', 'POST')]
        for caminho, api, metodo in casos:
            with self.subTest(caminho=caminho):
                rota = next(r for r in self.telas if r['rota'] == caminho)
                links = [r for r in rota['api_relacionada'] if r['rota'] == api]
                self.assertTrue(links)
                self.assertTrue(all(metodo in r['metodos'] for r in links))

    def test_future_source_page_is_documented_with_fallback_not_a_phantom_curated_route(self):
        from mobile_help import catalogo_mobile
        with tempfile.TemporaryDirectory() as directory:
            raiz = Path(directory)
            app = raiz / 'Cortae_mobile-main/src/app'
            nova = app / 'cliente/futura.tsx'
            nova.parent.mkdir(parents=True)
            nova.write_text('export default function Futura() { return null; }', encoding='utf-8')
            with patch.object(help_api, 'RAIZ', raiz):
                telas, info = catalogo_mobile(raiz, {'imports': {}, 'fechos': {}}, [],
                    help_api._permitido, help_api._ler, help_api._dependencias, help_api._metadado)
            self.assertEqual([r['id'] for r in telas], ['mobile:/cliente/futura'])
            self.assertIn('encontrada no Expo Router', telas[0]['descricao'])
            self.assertTrue(all(not fluxo['rotas'] for fluxo in info['fluxos']))

    def test_overview_flows_only_reference_existing_native_screens_and_explain_limits(self):
        ids = {r['id'] for r in self.telas}
        info = self.catalogo['mobile']
        self.assertEqual(len(info['fluxos']), 6)
        self.assertTrue(info['funcionamento'])
        self.assertIn('Não existe tela nem botão', ' '.join(info['funcionamento']))
        self.assertIn('WhatsApp', ' '.join(info['observacoes']))
        self.assertIn('administrador', info['descricao'])
        for fluxo in info['fluxos']:
            self.assertTrue(fluxo['etapas']); self.assertTrue(fluxo['rotas'])
            self.assertTrue(set(fluxo['rotas']) <= ids)

    def test_read_only_catalog_never_calls_database_business_or_external_integrations(self):
        with patch.object(help_api, 'decodificar_token', return_value={'tipo': 0}), \
                patch('application.conectar_banco', side_effect=AssertionError('Sem banco de negócio')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('Sem rede externa')), \
                patch('smtplib.SMTP', side_effect=AssertionError('Sem e-mail')), \
                patch('smtplib.SMTP_SSL', side_effect=AssertionError('Sem e-mail')):
            resposta = main.app.test_client().get('/admin/help/catalogo')
        self.assertEqual(resposta.status_code, 200)
        self.assertGreater(resposta.json['total']['mobile'], 0)
        self.assertEqual(resposta.headers['Cache-Control'], 'private, no-store')
        self.assertNotIn('conteudo', resposta.json)

    def test_mobile_sources_require_admin_and_registered_opaque_id(self):
        arquivo = help_api.RAIZ / 'Cortae_mobile-main/src/lib/apiAddress.ts'
        endereco = '/admin/help/codigo/' + help_api._id(arquivo)
        client = main.app.test_client()
        for usuario, status in ((None, 401), ({'tipo': 1}, 403), ({'tipo': 2}, 403), ({'tipo': 3}, 403)):
            with patch.object(help_api, 'decodificar_token', return_value=usuario), patch.object(help_api, '_ler') as ler:
                self.assertEqual(client.get(endereco).status_code, status)
                ler.assert_not_called()
        with patch.object(help_api, 'decodificar_token', return_value={'tipo': 0}):
            resposta = client.get(endereco)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json['linguagem'], 'typescript')
        self.assertIn('resolveAutomaticApiUrl', resposta.json['conteudo'])
        self.assertEqual(resposta.headers['Cache-Control'], 'private, no-store')

    def test_mobile_only_own_source_is_allowed(self):
        raiz = help_api.RAIZ / 'Cortae_mobile-main'
        for nome in ('.env', '.env.example', 'app.json', 'package.json', 'README.md',
                     'assets/icon.png', 'tests/session-race.test.cjs', 'node_modules/expo/package.json',
                     'src/lib/api.py', 'src/lib/styles.css', 'src/.private.ts', 'src/config.py'):
            with self.subTest(nome=nome):
                self.assertFalse(help_api._permitido(raiz / nome))
        self.assertTrue(help_api._permitido(raiz / 'src/lib/api.ts'))

    def test_typescript_index_reexports_expand_without_following_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            raiz = Path(directory)
            src = raiz / 'Cortae_mobile-main/src'
            page = src / 'app/cliente/index.tsx'
            index = src / 'features/catalog/index.ts'
            impl = index.parent / 'List.tsx'
            page.parent.mkdir(parents=True); index.parent.mkdir(parents=True)
            page.write_text("export { default } from '../../features/catalog';", encoding='utf-8')
            index.write_text("export { default } from './List';", encoding='utf-8')
            impl.write_text('export default function List() { return null; }', encoding='utf-8')
            with patch.object(help_api, 'RAIZ', raiz):
                self.assertEqual(help_api._resolver(page.parent, '../../features/catalog'), index)
                self.assertEqual(set(help_api._dependencias(page, {'imports': {}, 'fechos': {}})), {page, index, impl})
                self.assertIsNone(help_api._resolver(page.parent, '../../../../.env'))

    def test_typed_multiline_credentials_and_comments_are_hidden_without_line_shift(self):
        fixtures = [
            'const secret: string = "HIDDEN_SENTINEL";\n',
            'const clientSecret:\n string =\n "HIDDEN_SENTINEL";\n',
            'const secret: string = // fallback\n "HIDDEN_SENTINEL";\n',
            'const apiKey: string = /* fallback\n */ "HIDDEN_SENTINEL";\n',
            'const secret: string = flag\n ? "HIDDEN_SENTINEL"\n : "OTHER_SECRET";\n',
            'class Config { private readonly secret: string =\n "HIDDEN_SENTINEL"; }\n',
            'const values = { "client_secret": /* hint */\n `HIDDEN_SENTINEL\nMORE` };\n',
        ]
        for texto in fixtures:
            for linguagem in ('typescript', 'tsx'):
                with self.subTest(texto=texto, linguagem=linguagem):
                    seguro, avisos = help_api._sanitizar(texto, linguagem)
                    self.assertNotIn('HIDDEN_SENTINEL', seguro)
                    self.assertTrue(avisos)
                    self.assertEqual(len(seguro.splitlines()), len(texto.splitlines()))

    def test_scanner_rejects_windows_reparse_directories_and_hardlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            raiz = Path(directory); app = raiz / 'Cortae_mobile-main/src/app'
            client = app / 'cliente'; client.mkdir(parents=True)
            first = app / 'index.tsx'; first.write_text('export default 1;', encoding='utf-8')
            linked = client / 'index.tsx'; linked.write_text('export default 2;', encoding='utf-8')
            real_lstat = Path.lstat
            def reparse(path, *args, **kwargs):
                if path == client:
                    return types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                return real_lstat(path, *args, **kwargs)
            with patch.object(help_api, 'RAIZ', raiz), patch.object(Path, 'lstat', reparse):
                self.assertEqual(_paginas(app, help_api._permitido), [first])
                self.assertFalse(help_api._permitido(linked))
            forbidden = raiz / 'secrets.ts'; forbidden.write_text('secret="sentinel"', encoding='utf-8')
            hardlink = app / 'hard.ts'; os.link(forbidden, hardlink)
            with patch.object(help_api, 'RAIZ', raiz), self.assertRaises(ValueError):
                help_api._ler(hardlink)


if __name__ == '__main__':
    unittest.main()
