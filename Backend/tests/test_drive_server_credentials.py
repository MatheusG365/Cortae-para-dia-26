"""Portable server credentials; no network, app imports or business databases."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import configurar_drive
import google_drive_storage as drive


class ServerCredentialsTests(unittest.TestCase):
    def setUp(self):
        drive._CREDENTIALS.clear()
        self.info = {'type': 'authorized_user', 'client_id': 'synthetic-client',
                     'client_secret': 'synthetic-secret', 'refresh_token': 'synthetic-refresh',
                     'scopes': [drive.SCOPE]}
        self.settings = {'GOOGLE_DRIVE_CREDENTIALS_JSON': json.dumps(self.info),
                         'GOOGLE_DRIVE_FOLDER_IDS': {'perfil': 'folder_123456'}}

    def tearDown(self):
        drive._CREDENTIALS.clear()

    def test_server_json_works_without_any_local_credentials_file(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('No local secret file')):
            provider = drive.GoogleDriveStorage(self.settings)
        self.assertEqual(provider.credentials.client_id, self.info['client_id'])
        self.assertEqual(provider.folders['perfil'], 'folder_123456')

    def test_json_takes_precedence_over_old_or_missing_file(self):
        self.settings['GOOGLE_DRIVE_CREDENTIALS_FILE'] = 'missing-deleted-client.json'
        self.assertEqual(drive.GoogleDriveStorage(self.settings).credentials.client_id, 'synthetic-client')

    def test_invalid_json_fails_closed_even_with_valid_legacy_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'private.json')
            path.write_text(json.dumps(self.info), encoding='utf-8')
            self.settings['GOOGLE_DRIVE_CREDENTIALS_FILE'] = str(path)
            for raw in ('{broken', '[]', '{"private":"' + 'x' * 65536 + '"}', {'bad': 'type'}):
                with self.subTest(kind=type(raw).__name__):
                    self.settings['GOOGLE_DRIVE_CREDENTIALS_JSON'] = raw
                    with self.assertRaises(drive.DriveError) as caught:
                        drive.GoogleDriveStorage(self.settings)
                    self.assertNotIn('synthetic', str(caught.exception))

    def test_cached_credentials_are_reused_but_refresh_token_rotation_invalidates(self):
        first = drive.GoogleDriveStorage(self.settings)
        second = drive.GoogleDriveStorage(self.settings)
        self.assertIs(first.credentials, second.credentials)
        self.assertIs(first.credentials_lock, second.credentials_lock)
        self.info['refresh_token'] = 'rotated-synthetic-refresh'
        self.settings['GOOGLE_DRIVE_CREDENTIALS_JSON'] = json.dumps(self.info)
        rotated = drive.GoogleDriveStorage(self.settings)
        self.assertIsNot(first.credentials, rotated.credentials)
        cache_keys = repr(list(drive._CREDENTIALS))
        self.assertNotIn('synthetic', cache_keys)
        self.assertNotIn('refresh_token', cache_keys)

    def test_environment_credentials_keep_provider_and_scope_constraints(self):
        for field, value in (('token_uri', 'https://external.invalid/token'),
                             ('universe_domain', 'external.invalid'),
                             ('scopes', ['email']), ('type', 'installed')):
            with self.subTest(field=field):
                self.settings['GOOGLE_DRIVE_CREDENTIALS_JSON'] = json.dumps(dict(self.info, **{field: value}))
                with self.assertRaises(drive.DriveError):
                    drive.GoogleDriveStorage(self.settings)

    def test_explicit_cli_credentials_override_server_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'private.json')
            path.write_text(json.dumps(self.info), encoding='utf-8')
            with patch('config.GOOGLE_DRIVE_CREDENTIALS_JSON', 'server-secret'):
                settings = configurar_drive.load_config(credentials=str(path))
                self.assertEqual(settings['GOOGLE_DRIVE_CREDENTIALS_JSON'], '')
                self.assertEqual(settings['GOOGLE_DRIVE_CREDENTIALS_FILE'], str(path.resolve()))
                self.assertEqual(configurar_drive.load_config()['GOOGLE_DRIVE_CREDENTIALS_JSON'], 'server-secret')

    def test_shipped_folder_map_covers_all_image_areas(self):
        folders = json.loads(Path(drive.__file__).with_name('google_drive_folders.json').read_text())
        self.assertEqual(folders['root'], '1B_htSTsfkCvcsECFlCzcyMeDC5b8aCgJ')
        self.assertTrue(set(configurar_drive.AREAS) <= folders.keys())
        self.assertEqual(len({folders[area] for area in configurar_drive.AREAS}), 8)
        self.assertTrue(all(drive.FILE_ID.fullmatch(value) for value in folders.values()))


if __name__ == '__main__':
    unittest.main()
