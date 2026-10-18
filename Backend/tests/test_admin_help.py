"""Help is read-only, covers live routes and never discloses configuration."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import re
import stat
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import main
import admin_help as help_api


class HelpAdminTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()

    def test_anonymous_and_non_admin_never_read_sources(self):
        for payload, status in ((None, 401), ({'tipo': 1}, 403), ({'tipo': 2}, 403), ({'tipo': 3}, 403)):
            for endpoint in ('/admin/help/catalogo', '/admin/help/codigo/' + 'a'*32):
                with self.subTest(payload=payload, endpoint=endpoint), \
                        patch.object(help_api, 'decodificar_token', return_value=payload), \
                        patch.object(help_api, '_catalogo') as catalog, patch.object(help_api, '_ler') as read:
                    result = self.client.get(endpoint)
                    self.assertEqual(result.status_code, status)
                    self.assertEqual(result.headers['Cache-Control'], 'private, no-store')
                    self.assertIn('Authorization', result.headers['Vary'])
                    catalog.assert_not_called(); read.assert_not_called()

    def test_role_is_reloaded_from_database_for_every_request(self):
        token = jwt.encode({'id_usuario': 12345, 'tipo': 0}, main.app.config['SECRET_KEY'], algorithm='HS256')
        con = MagicMock(); con.cursor.return_value.fetchone.return_value = (0, 1, 1)
        with patch('database.conectar_banco', return_value=con), patch.object(help_api, '_catalogo', return_value={'rotas': []}):
            first = self.client.get('/admin/help/catalogo', headers={'Authorization': 'Bearer ' + token})
            self.assertEqual(first.status_code, 200)
            con.cursor.return_value.fetchone.return_value = (1, 1, 1)
            self.assertEqual(self.client.get('/admin/help/catalogo', headers={'Authorization': 'Bearer ' + token}).status_code, 403)
            con.cursor.return_value.fetchone.return_value = (0, 0, 1)
            self.assertEqual(self.client.get('/admin/help/catalogo', headers={'Authorization': 'Bearer ' + token}).status_code, 401)
        self.assertEqual(con.cursor.return_value.execute.call_count, 3)

    def test_catalog_covers_all_flask_rules_and_front_routes(self):
        with patch.object(help_api, 'decodificar_token', return_value={'tipo': 0}), \
                patch('application.conectar_banco', side_effect=AssertionError('No business operation allowed')):
            response = self.client.get('/admin/help/catalogo')
        self.assertEqual(response.status_code, 200)
        body = response.json
        self.assertEqual({r['rota'] for r in body['rotas'] if r['origem'] == 'backend'},
                         {r.rule for r in main.app.url_map.iter_rules()})
        source = help_api._ler(help_api.RAIZ/'Frontend/src/App.jsx')
        self.assertEqual({r['rota'] for r in body['rotas'] if r['origem'] == 'frontend'},
                         set(re.findall(r'\bpath=[\'\"]([^\'\"]+)', source)))
        self.assertTrue(any(r['rota'] == '/help' for r in body['rotas']))
        self.assertTrue(any(r['rota'] == '/admin/help/codigo/<codigo_id>' for r in body['rotas']))
        for route in body['rotas']:
            self.assertTrue(route['titulo']); self.assertTrue(route['descricao']); self.assertTrue(route['como_funciona'])
        static = next(r for r in body['rotas'] if r['endpoint'] == 'static')
        self.assertEqual(static['arquivos'], [])
        self.assertIn('infraestrutura externa', ' '.join(static['como_funciona']))
        paths = {f['caminho'] for r in body['rotas'] for f in r['arquivos']}
        self.assertIn('Frontend/src/pages/HelpAdmin/HelpAdmin.jsx', paths)
        self.assertIn('Backend/admin_help.py', paths)
        self.assertIn('Frontend/src/components/Select/Select.jsx', paths)
        self.assertIn('Frontend/src/services/api.js', paths)
        self.assertNotIn('Backend/config.py', paths)
        self.assertNotIn('Backend/database.py', paths)
        self.assertNotIn('conteudo', response.get_data(as_text=True))

    def test_unknown_path_or_file_id_is_not_opened(self):
        for ident in ('..', 'config.py', 'C:%5CWindows%5Cwin.ini', 'a'*32, '%2e%2e%2f.env', '%2fetc%2fpasswd'):
            with self.subTest(ident=ident), patch.object(help_api, 'decodificar_token', return_value={'tipo': 0}):
                response = self.client.get('/admin/help/codigo/' + ident)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(str(help_api.RAIZ), response.get_data(as_text=True))

    def test_relative_imports_expand_local_dependencies_without_allowing_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            top = Path(directory); root = top/'project'
            page = root/'Frontend/src/pages/HelpAdmin/HelpAdmin.jsx'
            component = root/'Frontend/src/components/Select/Select.jsx'
            helper = component.parent/'selectState.js'
            page.parent.mkdir(parents=True); component.parent.mkdir(parents=True)
            page.write_text("import Select from '../../components/Select/Select';", encoding='utf-8')
            component.write_text("import { estado } from './selectState';", encoding='utf-8')
            helper.write_text('export const estado = 1;', encoding='utf-8')
            outside = top/'outside.py'; outside.write_text('value = 1', encoding='utf-8')
            with patch.object(help_api, 'RAIZ', root):
                resolved = help_api._resolver(page.parent, '../../components/Select/Select')
                self.assertEqual(resolved, component)
                self.assertNotIn('..', resolved.parts)
                closure = help_api._dependencias(page, {'fechos': {}, 'imports': {}})
                self.assertEqual(set(closure), {page, component, helper})
                self.assertIsNone(help_api._resolver(page.parent, '../../../../../outside'))
                self.assertFalse(help_api._permitido(outside))

    def test_relative_import_does_not_follow_a_source_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'Frontend/src'
            base = source/'pages/HelpAdmin'; base.mkdir(parents=True)
            ordinary = source/'ordinary.js'; ordinary.write_text('export const x = 1;', encoding='utf-8')
            link = source/'linked.js'
            try:
                link.symlink_to(ordinary)
            except OSError:
                self.skipTest('Este Windows não permite criar links simbólicos para o teste.')
            with patch.object(help_api, 'RAIZ', root):
                self.assertIsNone(help_api._resolver(base, '../../linked.js'))
                self.assertEqual(help_api._resolver(base, '../../ordinary.js'), ordinary)

    def test_normalized_relative_import_rejects_link_and_windows_reparse_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'Frontend/src'
            base = source/'pages/HelpAdmin'; base.mkdir(parents=True)
            linked = source/'linked.js'; linked.write_text('export const x = 1;', encoding='utf-8')
            real_lstat = Path.lstat
            for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFREG, 0x400)):
                def flagged_lstat(path, *args, **kwargs):
                    if path == linked:
                        return types.SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                    return real_lstat(path, *args, **kwargs)
                with self.subTest(mode=mode, attributes=attributes), patch.object(help_api, 'RAIZ', root), patch.object(Path, 'lstat', flagged_lstat):
                    self.assertIsNone(help_api._resolver(base, '../../linked.js'))

    def test_code_is_current_and_only_read_by_registered_id(self):
        path = help_api.RAIZ/'Backend/admin_help.py'
        with patch.object(help_api, 'decodificar_token', return_value={'tipo': 0}):
            response = self.client.get('/admin/help/codigo/' + help_api._id(path))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['caminho'], 'Backend/admin_help.py')
        self.assertIn('def catalogo_help', response.json['conteudo'])
        self.assertEqual(response.json['linha_inicio'], 1)
        self.assertEqual(response.json['total_linhas'], len(response.json['conteudo'].splitlines()))
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')

    def test_python_multiline_credentials_and_comments_are_redacted(self):
        fixtures = [
            "API_KEY = (\n  'HIDDEN_SENTINEL'\n)\n",
            "value = {'client_secret':\n 'HIDDEN_SENTINEL'}\n",
            "connect(password=(\n 'HIDDEN_SENTINEL'\n))\n",
            "secret = 'HIDDEN_SENTINEL' # app.config\n",
            "secret = os.getenv('SECRET', 'HIDDEN_SENTINEL')\n",
            "# password: HIDDEN_SENTINEL\nvalue=1\n",
        ]
        for value in fixtures:
            with self.subTest(value=value):
                clean, notices = help_api._sanitizar(value)
                self.assertNotIn('HIDDEN_SENTINEL', clean)
                self.assertTrue(notices)
                self.assertEqual(len(clean.splitlines()), len(value.splitlines()))

    def test_javascript_multiline_credentials_are_redacted(self):
        for value in ('const secret =\n "HIDDEN_SENTINEL";\n',
                      'const x={client_secret:\n `HIDDEN_SENTINEL\nMORE`};\n',
                      'const token = [\n "HIDDEN_SENTINEL"\n];\n',
                      'const secret = flag\n ? "HIDDEN_SENTINEL"\n : "OTHER_SECRET";\n',
                      'const password = {a:\n "HIDDEN_SENTINEL"};\n',
                      '/* password\n HIDDEN_SENTINEL\n*/\nconst x=1;\n',
                      '// password HIDDEN_SENTINEL\nconst x=1;\n'):
            with self.subTest(value=value):
                clean, notices = help_api._sanitizar(value, 'jsx')
                self.assertNotIn('HIDDEN_SENTINEL', clean)
                self.assertTrue(notices)
                self.assertEqual(len(clean.splitlines()), len(value.splitlines()))

    def test_environment_values_are_never_read(self):
        with patch.dict(os.environ, {'HELP_ENV_SECRET': 'HIDDEN_ENV_SENTINEL'}), \
                patch.object(help_api, 'decodificar_token', return_value={'tipo': 0}):
            catalog = self.client.get('/admin/help/catalogo').get_data(as_text=True)
            code = self.client.get('/admin/help/codigo/' + help_api._id(help_api.RAIZ/'Backend/admin_help.py')).get_data(as_text=True)
        self.assertNotIn('HIDDEN_ENV_SENTINEL', catalog + code)

    def test_deny_config_links_hardlinks_and_oversized_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); backend = root/'Backend'; backend.mkdir()
            ordinary = backend/'route.py'; ordinary.write_text('value=1', encoding='utf-8')
            config = backend/'config.py'; config.write_text('secret="sentinel"', encoding='utf-8')
            with patch.object(help_api, 'RAIZ', root):
                self.assertEqual(help_api._ler(ordinary), 'value=1')
                self.assertFalse(help_api._permitido(config))
                ordinary.write_text('x'*100, encoding='utf-8')
                with patch.object(help_api, 'LIMITE_CODIGO', 10), self.assertRaises(ValueError): help_api._ler(ordinary)
                hardlink = backend/'hard.py'
                os.link(config, hardlink)
                with self.assertRaises(ValueError): help_api._ler(hardlink)
                link = backend/'link.py'
                try:
                    link.symlink_to(config)
                except OSError:
                    return  # Windows may require developer mode for symlink creation.
                self.assertFalse(help_api._permitido(link))

    def test_file_replacement_during_open_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); backend = root/'Backend'; backend.mkdir()
            ordinary = backend/'route.py'; ordinary.write_text('value=1', encoding='utf-8')
            replacement = backend/'replacement.py'; replacement.write_text('secret="sentinel"', encoding='utf-8')
            real_open = Path.open
            def replaced_open(path, *args, **kwargs):
                descriptor = real_open(path, *args, **kwargs)
                if path == ordinary and args and args[0] == 'rb':
                    # Windows denies replacing an already open file; changing its
                    # size still exercises the identity/metadata consistency check.
                    with real_open(ordinary, 'wb') as writer:
                        writer.write(b'value=999999999')
                return descriptor
            with patch.object(help_api, 'RAIZ', root), patch.object(Path, 'open', replaced_open):
                with self.assertRaises((ValueError, OSError)): help_api._ler(ordinary)

    def test_route_metadata_uses_current_handler_name_after_line_shift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); backend = root/'Backend'; backend.mkdir()
            path = backend/'shifted_handler.py'
            original = 'def handler():\n    """Doc correto do handler."""\n    return primeira()\n'
            path.write_text(original, encoding='utf-8')
            module = types.ModuleType('shifted_handler'); module.__file__ = str(path)
            exec(compile(original, str(path), 'exec'), module.__dict__)
            edited = ('def outro():\n    """Doc errado de outro handler."""\n    return diferente()\n\n\n'
                      'def handler():\n    """Doc atual do handler."""\n    return atual()\n')
            path.write_text(edited, encoding='utf-8')
            with patch.object(help_api, 'RAIZ', root), patch.dict('sys.modules', {'shifted_handler': module}):
                node, found_path, line = help_api._funcao_atual(module.handler)
                _, _, calls, description = help_api._analise(node)
            self.assertEqual(found_path, path)
            self.assertEqual(line, 6)
            self.assertEqual(description, 'Doc atual do handler.')
            self.assertEqual(calls, ['atual'])


if __name__ == '__main__': unittest.main()
