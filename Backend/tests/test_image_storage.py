"""Storage contract, real Pillow decoding and isolated transactional metadata."""
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

os.environ['WAITLIST_WORKER'] = 'false'
from application import app
import image_storage as storage
import google_drive_storage as drive
from PIL import Image


def picture(mode='RGB', size=(240, 160), fmt='PNG', **save):
    image = Image.new(mode, size, (100, 50, 30, 80) if mode == 'RGBA' else (100, 50, 30))
    stream = io.BytesIO(); image.save(stream, fmt, **save)
    return stream.getvalue()


class Cursor:
    """Execute production DML against SQLite, translating two Firebird constructs."""
    def __init__(self, con):
        self.cursor = con.cursor(); self.sql = []

    def execute(self, sql, args=()):
        self.sql.append((sql, args))
        if 'RDB$RELATIONS' in sql:
            return self.cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", args)
        if sql.startswith('UPDATE OR INSERT INTO IMAGE_SLOT'):
            sql = re.sub(r'^UPDATE OR INSERT', 'INSERT', sql)
            sql = sql.split(' MATCHING')[0] + ' ON CONFLICT(AREA,OWNER_ID,SLOT) DO UPDATE SET NOME=excluded.NOME'
        sql = sql.replace('SELECT FIRST 1 ', 'SELECT ')
        return self.cursor.execute(sql, args)

    def fetchone(self):
        return self.cursor.fetchone()

    def close(self):
        self.cursor.close()


class Provider:
    name = 'google_drive'
    def __init__(self):
        self.files = {}; self.deleted = []; self.trashed = []
    def put(self, area, filename, data):
        identifier = 'private-' + filename; self.files[identifier] = data; return identifier
    def get(self, identifier, limit):
        return self.files[identifier]
    def delete(self, identifier):
        self.deleted.append(identifier); self.files.pop(identifier, None)
    def trash(self, identifier):
        self.trashed.append(identifier); self.files.pop(identifier, None)


class CompressionTests(unittest.TestCase):
    def test_actual_decoder_not_filename_or_claimed_mime(self):
        for content in (b'', b'<svg>bad</svg>', b'not an image', b'RIFFfakeWEBP'):
            with self.subTest(content=content):
                with self.assertRaises(storage.ImageStorageError) as error:
                    storage.compress_image(content)
                self.assertEqual(error.exception.status, 400)

    def test_jpeg_png_webp_static_gif_decode_to_webp(self):
        for fmt in ('JPEG', 'PNG', 'WEBP', 'GIF'):
            data, width, height = storage.compress_image(picture(fmt=fmt))
            self.assertTrue(data.startswith(b'RIFF')); self.assertEqual(data[8:12], b'WEBP')
            self.assertEqual((width, height), (240, 160))

    def test_resizes_and_preserves_alpha(self):
        raw = picture('RGBA', (2400, 1200))
        data, w, h = storage.compress_image(io.BytesIO(raw), 512)
        self.assertEqual((w, h), (512, 256))
        with Image.open(io.BytesIO(data)) as result:
            self.assertEqual(result.mode, 'RGBA'); self.assertLess(result.getpixel((0, 0))[3], 255)

    def test_exif_orientation_is_applied_and_metadata_removed(self):
        exif = Image.Exif(); exif[274] = 6; exif[270] = 'private GPS metadata'
        data, w, h = storage.compress_image(picture(fmt='JPEG', exif=exif))
        self.assertEqual((w, h), (160, 240))
        with Image.open(io.BytesIO(data)) as result:
            self.assertEqual(dict(result.getexif()), {}); self.assertNotIn('icc_profile', result.info)
        self.assertNotIn(b'private GPS metadata', data)

    def test_input_and_pixel_limits(self):
        with self.assertRaises(storage.ImageStorageError) as error:
            storage.compress_image(b'x' * (storage.MAX_INPUT + 1))
        self.assertEqual(error.exception.status, 413)
        with patch.object(storage, 'MAX_PIXELS', 100):
            with self.assertRaises(storage.ImageStorageError) as error:
                storage.compress_image(picture())
        self.assertEqual(error.exception.status, 413)

    def test_animation_rejected_instead_of_silently_losing_frames(self):
        first = Image.new('RGB', (20, 20), 'red'); second = Image.new('RGB', (20, 20), 'blue')
        stream = io.BytesIO(); first.save(stream, 'GIF', save_all=True, append_images=[second])
        with self.assertRaises(storage.ImageStorageError) as error:
            storage.compress_image(stream.getvalue())
        self.assertEqual(error.exception.status, 400)

    def test_truncated_image_rejected(self):
        with self.assertRaises(storage.ImageStorageError):
            storage.compress_image(picture()[:60])

    def test_patterned_png_uses_smaller_lossless_webp_candidate(self):
        source = Image.new('RGB', (1100, 700))
        source.putdata([((x * 7) % 256, (x // 70) % 256, (x // 256) % 256)
                        for x in range(1100 * 700)])
        buffer = io.BytesIO(); source.save(buffer, 'PNG'); original = buffer.getvalue()
        output, _, _ = storage.compress_image(original)
        self.assertLess(len(output), len(original))


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context(); self.context.push()
        self.con = sqlite3.connect(':memory:')
        self.con.executescript('''CREATE TABLE IMAGE_ASSET (NOME TEXT,AREA TEXT,PROVIDER TEXT,FILE_ID TEXT,
          OWNER_ID INTEGER,SLOT TEXT,MIME TEXT,LARGURA INTEGER,ALTURA INTEGER,TAMANHO INTEGER,SHA256 TEXT,
          ATIVO INTEGER,CRIADO_EM TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(AREA,NOME));
          CREATE TABLE IMAGE_SLOT (AREA TEXT,OWNER_ID INTEGER,SLOT TEXT,NOME TEXT,PRIMARY KEY(AREA,OWNER_ID,SLOT));''')
        self.cur = Cursor(self.con); self.provider = Provider()
        self.provider_patch = patch.object(storage, '_provider', return_value=self.provider); self.provider_patch.start()

    def tearDown(self):
        self.provider_patch.stop(); self.cur.close(); self.con.close(); self.context.pop()

    def test_metadata_only_and_same_transaction(self):
        batch = storage.ImageBatch(self.cur)
        asset = batch.save(picture(), 'perfil', 7, 'profile')
        self.assertRegex(asset.filename, r'^[a-f0-9]{32}\.webp$')
        self.assertEqual(asset.url, '/uploads/perfil/' + asset.filename)
        self.assertIsNotNone(asset.content)
        self.assertEqual(storage.slot_state('perfil', 7, 'profile', self.cur)[1].filename, asset.filename)
        for _, args in self.cur.sql:
            self.assertFalse(any(isinstance(value, bytes) for value in args))
        self.con.commit(); batch.commit()
        self.assertEqual(storage.read_image('perfil', asset.filename, cursor=self.cur), asset.content)

    def test_rollback_deletes_new_upload_preserves_old_reference(self):
        first = storage.ImageBatch(self.cur); old = first.save(picture(), 'barbearia', 11, 'logo')
        self.con.commit(); first.commit()
        second = storage.ImageBatch(self.cur); new = second.save(picture(), 'barbearia', 11, 'logo')
        self.assertEqual(storage.latest_image('barbearia', 11, 'logo', self.cur).filename, new.filename)
        self.con.rollback(); second.abort()
        self.assertIn(new.file_id, self.provider.deleted)
        self.assertNotIn(old.file_id, self.provider.trashed)
        self.assertEqual(storage.latest_image('barbearia', 11, 'logo', self.cur).filename, old.filename)

    def test_slot_tombstone_prevents_previous_photo_resurrecting(self):
        first = storage.ImageBatch(self.cur); old = first.save(picture(), 'perfil', 7, 'profile')
        self.con.commit(); first.commit()
        second = storage.ImageBatch(self.cur); second.delete('perfil', 7, 'profile')
        self.con.commit(); second.commit()
        self.assertEqual(storage.slot_state('perfil', 7, 'profile', self.cur), (True, None))
        self.assertIsNone(storage.find_image('perfil', old.filename, self.cur))
        self.assertIn(old.file_id, self.provider.trashed)
        with self.assertRaises(FileNotFoundError):
            storage.read_image('perfil', old.filename, cursor=self.cur)

    def test_missing_schema_still_reads_legacy_and_blocks_new_save(self):
        self.con.execute('DROP TABLE IMAGE_SLOT'); self.con.execute('DROP TABLE IMAGE_ASSET')
        self.assertEqual(storage.slot_state('perfil', 7, 'profile', self.cur), (False, None))
        with tempfile.TemporaryDirectory() as root, patch.dict(app.config, IMAGE_STORAGE_PROVIDER='local'):
            Path(root, '7.jpg').write_bytes(picture(fmt='JPEG'))
            self.assertTrue(storage.read_image('perfil', '7.jpg', root, self.cur).startswith(b'\xff\xd8'))
        batch = storage.ImageBatch(self.cur)
        with self.assertRaises(storage.ImageStorageError):
            batch.save(picture(), 'perfil', 7, 'profile')
        self.assertEqual(len(self.provider.deleted), 1)

    def test_unregistered_managed_filename_never_reads_local(self):
        with tempfile.TemporaryDirectory() as root:
            name = 'a' * 32 + '.webp'; Path(root, name).write_bytes(picture(fmt='WEBP'))
            with self.assertRaises(FileNotFoundError):
                storage.read_image('perfil', name, root, self.cur)

    def test_integrity_verification_rejects_changed_remote_content(self):
        batch = storage.ImageBatch(self.cur); asset = batch.save(picture(), 'marketplace', 11)
        self.con.commit(); batch.commit()
        self.provider.files[asset.file_id] = b'corruption'
        with self.assertRaises(storage.ImageStorageError):
            storage.read_image('marketplace', asset.filename, cursor=self.cur)

    def test_legacy_alias_keeps_url_but_serves_actual_webp_mime(self):
        batch = storage.ImageBatch(self.cur)
        image = batch.save(picture(), 'perfil', 7, 'profile', legacy_filename='7.jpg')
        self.con.commit(); batch.commit()
        self.assertEqual(image.filename, '7.jpg')
        self.assertTrue(image.file_id.endswith('.webp'))
        self.assertEqual(storage.slot_state('perfil', 7, 'profile', self.cur)[1].filename, '7.jpg')
        with app.test_request_context('/'):
            response = storage.serve_image('perfil', '7.jpg', cursor=self.cur)
        self.assertEqual(response.mimetype, 'image/webp')

    def test_media_response_returns_safe_503_when_provider_is_unavailable(self):
        batch = storage.ImageBatch(self.cur); image = batch.save(picture(), 'perfil', 7)
        self.con.commit(); batch.commit()
        with patch.object(self.provider, 'get', side_effect=drive.DriveError('Google Drive indisponível.')):
            with app.test_request_context('/'):
                response, code = storage.serve_image('perfil', image.filename, cursor=self.cur)
        self.assertEqual(code, 503)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('secret', json.dumps(response.get_json()))

    def test_area_and_path_validation(self):
        for area, filename in [('financeiro', 'a.jpg'), ('perfil', '../secret'), ('perfil', 'a/b.jpg')]:
            with self.assertRaises((storage.ImageStorageError, FileNotFoundError)):
                storage.read_image(area, filename, cursor=self.cur)

    def test_provider_missing_credentials_is_503_without_local_fallback(self):
        self.provider_patch.stop()
        try:
            with patch.dict(app.config, IMAGE_STORAGE_PROVIDER='google_drive', GOOGLE_DRIVE_CREDENTIALS_FILE=''):
                with self.assertRaises(storage.ImageStorageError) as error:
                    storage.ImageBatch(self.cur).save(picture(), 'perfil', 7, 'profile')
                self.assertEqual(error.exception.status, 503)
                self.assertNotIn('secret', str(error.exception).lower())
        finally:
            self.provider_patch.start()

    def test_batch_without_upload_is_lazy_and_idempotent(self):
        batch = storage.ImageBatch(self.cur); batch.commit(); batch.commit(); batch.abort()
        self.provider_patch.target._provider.assert_not_called()


class DriveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.path = Path(self.temp.name, 'oauth.json')
        self.path.write_text(json.dumps({'type': 'authorized_user', 'client_id': 'id', 'client_secret': 'secret',
                                         'refresh_token': 'refresh', 'scopes': [drive.SCOPE]}))
        self.config = {'GOOGLE_DRIVE_CREDENTIALS_FILE': str(self.path),
                       'GOOGLE_DRIVE_FOLDER_IDS': {'perfil': 'folder_123456'}}
        drive._CREDENTIALS.clear()

    def tearDown(self):
        drive._CREDENTIALS.clear(); self.temp.cleanup()

    def test_private_upload_contract_never_requests_sharing_or_public_url(self):
        provider = drive.GoogleDriveStorage(self.config)
        with patch.object(provider, '_request', return_value=b'{"id":"image_123456789"}') as call:
            self.assertEqual(provider.put('perfil', 'a.webp', b'WEBP'), 'image_123456789')
        args, kwargs = call.call_args
        self.assertEqual(args, ('POST', drive.UPLOAD))
        self.assertIn(b'"parents":["folder_123456"]', kwargs['data'])
        self.assertNotIn(b'anyone', kwargs['data']); self.assertNotIn(b'permissions', kwargs['data'])

    def test_credentials_cache_reuses_refreshed_credentials_and_lock(self):
        first = drive.GoogleDriveStorage(self.config); second = drive.GoogleDriveStorage(self.config)
        self.assertIs(first.credentials, second.credentials)
        self.assertIs(first.credentials_lock, second.credentials_lock)

    def test_missing_upload_folder_is_service_unavailable_but_missing_media_stays_404(self):
        provider = drive.GoogleDriveStorage(self.config)
        with patch.object(provider, '_request', side_effect=FileNotFoundError('provider-private-detail')):
            with self.assertRaises(drive.DriveError) as error:
                provider.put('perfil', 'a.webp', b'WEBP')
            self.assertNotIn('provider-private-detail', str(error.exception))
            with self.assertRaises(FileNotFoundError):
                provider.get('image_123456789', 100)
            provider.delete('image_123456789')

    def test_non_google_auth_endpoint_and_personal_service_account_are_rejected(self):
        info = json.loads(self.path.read_text()); info['token_uri'] = 'https://evil.invalid/token'
        self.path.write_text(json.dumps(info))
        with self.assertRaises(drive.DriveError):
            drive.GoogleDriveStorage(self.config)
        info['token_uri'] = 'https://oauth2.googleapis.com/token'; info['type'] = 'service_account'
        self.path.write_text(json.dumps(info))
        with self.assertRaises(drive.DriveError):
            drive.GoogleDriveStorage(self.config)

    def test_existing_explicit_full_scope_is_preserved(self):
        info = json.loads(self.path.read_text()); info['scopes'] = ['https://www.googleapis.com/auth/drive']
        self.path.write_text(json.dumps(info))
        provider = drive.GoogleDriveStorage(self.config)
        self.assertEqual(provider.credentials.scopes, info['scopes'])

    def test_transport_has_timeouts_no_redirects_and_bounded_download(self):
        provider = drive.GoogleDriveStorage(self.config)
        provider.credentials = Mock(); provider.credentials_lock = threading.RLock()
        response = Mock(status_code=200, headers={}); response.iter_content.return_value = [b'123', b'456']
        response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        provider.session.request = Mock(return_value=response)
        with self.assertRaises(drive.DriveError):
            provider.get('image_123456789', 5)
        kwargs = provider.session.request.call_args.kwargs
        self.assertFalse(kwargs['allow_redirects']); self.assertEqual(kwargs['timeout'], (10, 30))
        self.assertFalse(provider.session.trust_env)

    def test_redirect_and_provider_error_messages_do_not_leak_provider_content(self):
        provider = drive.GoogleDriveStorage(self.config)
        provider.credentials = Mock(); provider.credentials_lock = threading.RLock()
        response = Mock(status_code=302, headers={'Location': 'https://evil.invalid/secret'})
        response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        provider.session.request = Mock(return_value=response)
        with self.assertRaises(drive.DriveError) as error:
            provider.get('image_123456789', 500)
        self.assertNotIn('evil', str(error.exception)); self.assertNotIn('secret', str(error.exception))

    def test_arbitrary_file_identifier_is_rejected_before_network(self):
        provider = drive.GoogleDriveStorage(self.config)
        with patch.object(provider, '_request') as request:
            with self.assertRaises(drive.DriveError):
                provider.get('../other-file', 100)
            request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
