"""Drive setup is an explicit server CLI with no business DB or live Google calls."""
import contextlib
import http.client
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

import configurar_drive as setup
from google_auth_oauthlib.flow import InstalledAppFlow

ROOT_ID = 'root_folder_12345'
AREA_IDS = {area: 'area_folder_'+str(index)+'_12345' for index, area in enumerate(setup.AREAS)}


class DriveSetupTests(unittest.TestCase):
    def client_info(self):
        return {'installed': {'client_id': '123456.apps.googleusercontent.com',
                              'client_secret': 'synthetic-client-secret',
                              'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                              'token_uri': 'https://oauth2.googleapis.com/token',
                              'redirect_uris': ['http://localhost']}}

    def provider(self, *, outside=False, writable=True):
        provider = MagicMock()
        provider.folders = dict(AREA_IDS, root=ROOT_ID)
        def metadata(method, url, **kwargs):
            self.assertEqual(method, 'GET')
            identifier = url.rsplit('/', 1)[1]
            parent = 'outside_folder_12345' if outside else ROOT_ID
            return json.dumps({'id': identifier, 'mimeType': setup.FOLDER_MIME,
                               'trashed': False, 'parents': [] if identifier in {ROOT_ID, 'outside_folder_12345'} else [parent],
                               'capabilities': {'canAddChildren': writable}}).encode()
        provider._request.side_effect = metadata
        return provider

    def test_help_and_import_never_load_app_or_open_business_database(self):
        backend = Path(setup.__file__).parent
        result = subprocess.run([sys.executable, '-c',
                                 "import configurar_drive,sys; assert 'main' not in sys.modules; assert 'application' not in sys.modules; configurar_drive.main(['--help'])"],
                                cwd=backend, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--autorizar', result.stdout)
        self.assertIn('--teste-envio', result.stdout)

    def test_credentials_inside_project_or_relative_paths_are_rejected(self):
        for path in (setup.PROJECT/'private-token.json', Path('token.json')):
            with self.subTest(path=path), self.assertRaises(setup.SetupError):
                setup.external_path(path)

    def test_private_atomic_save_does_not_overwrite_existing_credentials(self):
        with TemporaryDirectory() as directory:
            target = Path(directory)/'token.json'
            saved = setup.save_credentials(target, {'type': 'authorized_user', 'refresh_token': 'synthetic-only'})
            self.assertEqual(saved, target.resolve())
            self.assertEqual(json.loads(target.read_text())['refresh_token'], 'synthetic-only')
            with self.assertRaises(setup.SetupError):
                setup.save_credentials(target, {'refresh_token': 'replacement'})
            self.assertEqual(json.loads(target.read_text())['refresh_token'], 'synthetic-only')
            self.assertEqual(list(Path(directory).glob('.cortae-oauth-*.tmp')), [])

    def test_oauth_rejects_web_clients_and_external_token_endpoints_before_browser(self):
        with TemporaryDirectory() as directory:
            client = Path(directory)/'client.json'
            target = Path(directory)/'token.json'
            for info in ({'web': self.client_info()['installed']},
                         {'installed': dict(self.client_info()['installed'], token_uri='https://external.example/token')}):
                client.write_text(json.dumps(info))
                with patch.object(setup.webbrowser, 'open') as browser, self.assertRaises(setup.SetupError):
                    setup.authorize(client, target)
                browser.assert_not_called()
                self.assertFalse(target.exists())

    def test_credential_permissions_remove_extra_explicit_access_before_writing(self):
        with TemporaryDirectory() as directory:
            target = Path(directory)/'private-token.json'
            setup.save_credentials(target, {'refresh_token':'synthetic-only'})
            if sys.platform == 'win32':
                acl = subprocess.run(['icacls',str(target)], capture_output=True,
                                     text=True,check=True).stdout
                self.assertNotIn('(I)', acl)
                self.assertEqual(acl.count('(F)'), 2)
            else:
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            before = target.read_bytes()
            with self.assertRaises(setup.SetupError):
                setup._restrict_file(target)
            self.assertEqual(target.read_bytes(), before)

    def oauth(self, *, full_access=False, refresh=True, granted=True):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        client = Path(temporary.name)/'client.json'
        target = Path(temporary.name)/'token.json'
        client.write_text(json.dumps(self.client_info()))
        observations = {}
        callbacks = []
        def browser(url, **kwargs):
            query = parse_qs(urlsplit(url).query)
            observations.update(query)
            redirect = urlsplit(query['redirect_uri'][0])
            self.assertEqual(redirect.hostname, '127.0.0.1')
            self.assertNotIn(redirect.port, (None, 0))
            def callback():
                for state in ('invalid-state', query['state'][0]):
                    connection = http.client.HTTPConnection(redirect.hostname, redirect.port, timeout=5)
                    connection.request('GET', '/?'+urlencode({'state': state, 'code': 'synthetic-code'}))
                    response = connection.getresponse()
                    callbacks.append((response.status, response.read()))
                    connection.close()
            thread = threading.Thread(target=callback, daemon=True)
            thread.start()
            observations['thread'] = thread
            return True
        def token(flow, **kwargs):
            observations['exchange'] = kwargs
            self.assertEqual(kwargs['code'], 'synthetic-code')
            self.assertGreaterEqual(len(flow.code_verifier), 43)
            token = {'access_token': 'synthetic-access', 'token_type': 'Bearer', 'expires_in': 3600, 'expires_at': time.time()+3600}
            if refresh:
                token['refresh_token'] = 'synthetic-refresh'
            if granted:
                token['scope'] = setup.FULL_SCOPE if full_access else setup.SCOPE
            else:
                token['scope'] = 'openid'
            flow.oauth2session.token = token
        output = io.StringIO()
        with patch.object(setup.webbrowser, 'open', side_effect=browser), \
             patch.object(InstalledAppFlow, 'fetch_token', token), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            if refresh and granted:
                result = setup.authorize(client, target, full_access=full_access, timeout=5)
            else:
                with self.assertRaises(setup.SetupError):
                    setup.authorize(client, target, full_access=full_access, timeout=5)
                result = None
        observations['thread'].join(timeout=3)
        for secret in ('synthetic-code', 'synthetic-access', 'synthetic-refresh', 'synthetic-client-secret'):
            self.assertNotIn(secret, output.getvalue())
        self.assertEqual([status for status, _ in callbacks], [400, 200])
        self.assertTrue(all(b'synthetic-code' not in body for _, body in callbacks))
        return result, target, observations

    def test_oauth_desktop_uses_pkce_state_loopback_and_default_drive_file_scope(self):
        result, target, observed = self.oauth()
        self.assertEqual(result, target.resolve())
        self.assertEqual(observed['scope'], [setup.SCOPE])
        self.assertEqual(observed['code_challenge_method'], ['S256'])
        self.assertTrue(observed['code_challenge'][0])
        self.assertEqual(observed['access_type'], ['offline'])
        self.assertEqual(observed['exchange']['allow_redirects'], False)
        stored = json.loads(target.read_text())
        self.assertEqual(stored['type'], 'authorized_user')
        self.assertEqual(stored['scopes'], [setup.SCOPE])

    def test_full_scope_requires_explicit_flag(self):
        _, target, observed = self.oauth(full_access=True)
        self.assertEqual(observed['scope'], [setup.FULL_SCOPE])
        self.assertEqual(json.loads(target.read_text())['scopes'], [setup.FULL_SCOPE])

    def test_missing_refresh_token_or_ungranted_scope_is_never_saved(self):
        for options in ({'refresh': False}, {'granted': False}):
            with self.subTest(options=options):
                _, target, _ = self.oauth(**options)
                self.assertFalse(target.exists())

    def test_verify_reads_all_eight_folder_areas_without_writing(self):
        provider = self.provider()
        with patch.object(setup, 'GoogleDriveStorage', return_value=provider):
            self.assertIs(setup.verify_storage({}), provider)
        self.assertEqual(provider._request.call_count, len(setup.AREAS) + 1)
        provider.put.assert_not_called()
        provider.delete.assert_not_called()
        provider.trash.assert_not_called()

    def test_verify_rejects_folders_outside_root_or_without_write_permission(self):
        for options in ({'outside': True}, {'writable': False}):
            with self.subTest(options=options), patch.object(setup, 'GoogleDriveStorage', return_value=self.provider(**options)), \
                 self.assertRaises(setup.SetupError):
                setup.verify_storage({})

    def test_verify_rejects_reusing_same_folder_for_multiple_areas(self):
        provider = self.provider()
        provider.folders['perfil'] = provider.folders['marketplace']
        with patch.object(setup, 'GoogleDriveStorage', return_value=provider), self.assertRaises(setup.SetupError):
            setup.verify_storage({})
        provider._request.assert_not_called()

    def test_synthetic_upload_checks_bytes_and_trashes_only_the_created_file(self):
        provider = MagicMock()
        provider.put.return_value = 'created_file_12345'
        provider.get.side_effect = lambda identifier, size: provider.put.call_args.args[2]
        with patch.object(setup, 'verify_storage', return_value=provider):
            self.assertTrue(setup.test_upload({}))
        area, name, content = provider.put.call_args.args
        self.assertEqual(area, 'perfil')
        self.assertTrue(name.startswith('cortae-teste-'))
        self.assertIn(b'WEBP', content[:16])
        provider.trash.assert_called_once_with('created_file_12345')
        provider.delete.assert_not_called()

    def test_synthetic_upload_failure_still_trashes_the_created_file(self):
        provider = MagicMock()
        provider.put.return_value = 'created_file_12345'
        provider.get.return_value = b'corrupted'
        with patch.object(setup, 'verify_storage', return_value=provider), self.assertRaises(setup.SetupError):
            setup.test_upload({})
        provider.trash.assert_called_once_with('created_file_12345')
        provider.delete.assert_not_called()

    def test_failed_synthetic_creation_never_deletes_existing_files(self):
        provider = MagicMock()
        provider.put.side_effect = setup.DriveError('indisponível')
        with patch.object(setup, 'verify_storage', return_value=provider), self.assertRaises(setup.DriveError):
            setup.test_upload({})
        provider.trash.assert_not_called()
        provider.delete.assert_not_called()


if __name__ == '__main__':
    unittest.main()
