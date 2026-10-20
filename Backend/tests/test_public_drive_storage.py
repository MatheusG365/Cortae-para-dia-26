"""Explicit public Drive reads and credential-free clone reproduction; no live network."""
import hashlib
import io
import json
import sqlite3
import unittest
from unittest.mock import Mock, patch

from application import app
import google_drive_storage as drive
import image_storage as storage
from tests.test_image_storage import Cursor, Provider, picture

FILE_ID = 'registered_public_123456789'


class Response:
    def __init__(self, status=200, headers=None, chunks=None):
        self.status_code = status
        self.headers = headers if headers is not None else {'Content-Type': 'image/webp'}
        self.chunks = chunks if chunks is not None else [b'RIFF1234WEBPdata']
    def __enter__(self): return self
    def __exit__(self, *unused): return False
    def iter_content(self, unused): return iter(self.chunks)


class PublicTransportTests(unittest.TestCase):
    def session(self, *responses):
        session = Mock()
        session.headers = {'Authorization': 'must-be-cleared'}
        session.auth = 'must-be-cleared'
        session.get.side_effect = responses
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        return session

    def test_anonymous_media_disables_credentials_environment_cookies_redirect_automation(self):
        session = self.session(Response())
        with patch.object(drive.requests, 'Session', return_value=session), \
             patch.object(drive.GoogleDriveStorage, '__init__', side_effect=AssertionError('No OAuth')):
            result = drive.PublicGoogleDriveStorage().get(FILE_ID, 100)
        self.assertEqual(result, b'RIFF1234WEBPdata')
        self.assertFalse(session.trust_env); self.assertIsNone(session.auth)
        self.assertEqual(session.headers, {})
        session.cookies.clear.assert_called_once()
        url = session.get.call_args.args[0]
        self.assertTrue(url.startswith('https://drive.usercontent.google.com/download?id='))
        options = session.get.call_args.kwargs
        self.assertEqual(options['timeout'], (10, 30))
        self.assertFalse(options['allow_redirects']); self.assertTrue(options['stream'])
        self.assertNotIn('Authorization', options['headers'])

    def test_manual_redirects_allow_only_exact_google_media_hosts_and_same_identifier(self):
        session = self.session(Response(303, {'Location': 'https://drive.google.com/uc?id='+FILE_ID+'&export=download'}), Response())
        with patch.object(drive.requests, 'Session', return_value=session):
            self.assertEqual(drive.PublicGoogleDriveStorage().get(FILE_ID, 100), b'RIFF1234WEBPdata')
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(session.cookies.clear.call_count, 2)

    def test_redirect_to_login_external_host_port_other_file_or_path_never_follows(self):
        locations = ['https://accounts.google.com/login', 'https://evil.invalid/secret',
            'http://drive.google.com/uc?id='+FILE_ID,
            'https://user:secret@drive.google.com/uc?id='+FILE_ID,
            'https://drive.google.com:444/uc?id='+FILE_ID,
            'https://drive.google.com/file/d/'+FILE_ID,
            'https://drive.usercontent.google.com.evil.invalid/download?id='+FILE_ID,
            'https://drive.usercontent.google.com/download?id=another_file_12345',
            'https://drive.usercontent.google.com/download?id='+FILE_ID+'#private',
            'https://drive.usercontent.google.com/download?id='+FILE_ID+'&id=other_file_12345']
        for location in locations:
            with self.subTest(location=location):
                session = self.session(Response(303, {'Location': location}))
                with patch.object(drive.requests, 'Session', return_value=session), self.assertRaises(drive.DriveError) as error:
                    drive.PublicGoogleDriveStorage().get(FILE_ID, 100)
                self.assertEqual(session.get.call_count, 1)
                self.assertNotIn('secret', str(error.exception)); self.assertNotIn('evil', str(error.exception))

    def test_identifier_and_byte_limits_reject_before_session(self):
        with patch.object(drive.requests, 'Session') as session:
            for identifier in ('../private', 'https://drive.google.com/uc?id='+FILE_ID, '', None):
                with self.assertRaises(drive.DriveError): drive.PublicGoogleDriveStorage().get(identifier, 100)
            for limit in (0, -1, True, '100', drive.PUBLIC_MAX_BYTES+1):
                with self.assertRaises(drive.DriveError): drive.PublicGoogleDriveStorage().get(FILE_ID, limit)
            session.assert_not_called()

    def test_large_invalid_length_stream_overflow_and_html_fail_closed(self):
        cases = [Response(headers={'Content-Type':'image/webp','Content-Length':str(101)}),
            Response(headers={'Content-Type':'image/webp','Content-Length':'-1'}),
            Response(headers={'Content-Type':'image/webp','Content-Length':'invalid'}),
            Response(headers={'Content-Type':'text/html'}, chunks=[b'<html>Login</html>']),
            Response(chunks=[b'x'*60,b'x'*41])]
        for response in cases:
            with self.subTest(headers=response.headers):
                with patch.object(drive.requests, 'Session', return_value=self.session(response)), self.assertRaises(drive.DriveError):
                    drive.PublicGoogleDriveStorage().get(FILE_ID, 100)

    def test_redirect_loop_and_limit_are_bounded(self):
        same = 'https://drive.usercontent.google.com/download?id='+FILE_ID+'&export=download'
        with patch.object(drive.requests, 'Session', return_value=self.session(Response(303, {'Location':same}))) as factory:
            with self.assertRaises(drive.DriveError): drive.PublicGoogleDriveStorage().get(FILE_ID, 100)
            self.assertEqual(factory.return_value.get.call_count, 1)
        responses = [Response(303, {'Location':same+'&step='+str(i)}) for i in range(4)]
        session = self.session(*responses)
        with patch.object(drive.requests, 'Session', return_value=session), self.assertRaises(drive.DriveError):
            drive.PublicGoogleDriveStorage().get(FILE_ID, 100)
        self.assertEqual(session.get.call_count, 4)

    def test_missing_private_or_unavailable_file_never_uses_oauth(self):
        for status, exception in ((404, FileNotFoundError), (403, drive.DriveError), (500, drive.DriveError)):
            with patch.object(drive.requests, 'Session', return_value=self.session(Response(status))), \
                 patch.object(drive.GoogleDriveStorage, '__init__', side_effect=AssertionError('No OAuth fallback')), \
                 self.assertRaises(exception):
                drive.PublicGoogleDriveStorage().get(FILE_ID, 100)


class CloneAndPublicationTests(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context(); self.context.push(); self.addCleanup(self.context.pop)
        self.con = sqlite3.connect(':memory:'); self.addCleanup(self.con.close)
        self.con.executescript('''CREATE TABLE IMAGE_ASSET(NOME TEXT,AREA TEXT,PROVIDER TEXT,FILE_ID TEXT,
          OWNER_ID INTEGER,SLOT TEXT,MIME TEXT,LARGURA INTEGER,ALTURA INTEGER,TAMANHO INTEGER,SHA256 TEXT,
          ATIVO INTEGER,CRIADO_EM TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(AREA,NOME));
          CREATE TABLE IMAGE_SLOT(AREA TEXT,OWNER_ID INTEGER,SLOT TEXT,NOME TEXT,PRIMARY KEY(AREA,OWNER_ID,SLOT));''')
        self.cur = Cursor(self.con); self.addCleanup(self.cur.close)
        self.content, self.width, self.height = storage.compress_image(picture())
        self.settings = patch.dict(app.config, GOOGLE_DRIVE_CREDENTIALS_JSON='', GOOGLE_DRIVE_CREDENTIALS_FILE='',
                                   GOOGLE_DRIVE_PUBLIC_AREAS=','.join(sorted(drive.PUBLIC_AREAS)))
        self.settings.start(); self.addCleanup(self.settings.stop)

    def insert(self, area='site', provider='google_drive', filename='logo.png', identifier=FILE_ID):
        values = (filename,area,provider,identifier,7,None,'image/webp',self.width,self.height,len(self.content),hashlib.sha256(self.content).hexdigest(),1)
        self.cur.execute('INSERT INTO IMAGE_ASSET ('+storage.COLUMNS+') VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',values)
        self.con.commit()

    def test_clone_reproduces_503_for_registered_private_provider_without_server_secret(self):
        self.insert()
        with app.test_request_context('/'):
            response, status = storage.serve_image('site','logo.png',cursor=self.cur)
        self.assertEqual(status,503); self.assertEqual(response.headers['Cache-Control'],'no-store')

    def test_explicit_public_asset_works_with_no_credentials_and_validates_hash_and_webp(self):
        self.insert(provider=drive.PUBLIC_PROVIDER)
        with patch.object(drive.PublicGoogleDriveStorage,'get',return_value=self.content) as get:
            self.assertEqual(storage.read_image('site','logo.png',cursor=self.cur),self.content)
        get.assert_called_once_with(FILE_ID,len(self.content))
        for content in (b'RIFF1234WEBPcorrupted', b'<html>not an image</html>'):
            with patch.object(drive.PublicGoogleDriveStorage,'get',return_value=content), self.assertRaises(storage.ImageStorageError):
                storage.read_image('site','logo.png',cursor=self.cur)

    def test_private_area_or_shared_private_reference_blocks_anonymous_transport(self):
        self.insert(area='visagismo/fotos',provider=drive.PUBLIC_PROVIDER)
        with patch.object(drive.PublicGoogleDriveStorage,'get') as get, self.assertRaises(storage.ImageStorageError):
            storage.read_image('visagismo/fotos','logo.png',cursor=self.cur)
        get.assert_not_called()
        self.insert(provider=drive.PUBLIC_PROVIDER)
        with patch.object(drive.PublicGoogleDriveStorage,'get') as get, self.assertRaises(storage.ImageStorageError):
            storage.read_image('site','logo.png',cursor=self.cur)
        get.assert_not_called()

    def test_public_upload_publishes_before_metadata_and_private_upload_never_publishes(self):
        provider=Provider()
        with patch.object(storage,'_provider',return_value=provider):
            batch=storage.ImageBatch(self.cur); asset=batch.save(picture(),'perfil',7,'profile')
            self.assertEqual(asset.provider,drive.PUBLIC_PROVIDER); self.assertEqual(provider.published,[asset.file_id])
            private=batch.save(picture(),'visagismo/fotos',7)
            self.assertEqual(private.provider,'google_drive'); self.assertEqual(provider.published,[asset.file_id])
            self.con.rollback(); batch.abort()
        self.assertIn(asset.file_id,provider.deleted); self.assertIn(private.file_id,provider.deleted)

    def test_acl_failure_removes_new_upload_and_preserves_old_slot(self):
        provider=Provider()
        with patch.object(storage,'_provider',return_value=provider):
            first=storage.ImageBatch(self.cur); old=first.save(picture(),'perfil',7,'profile'); self.con.commit(); first.commit()
            with patch.object(provider,'publish_public',side_effect=drive.DriveError('Publicação indisponível.')):
                failed=storage.ImageBatch(self.cur)
                with self.assertRaises(storage.ImageStorageError): failed.save(picture(),'perfil',7,'profile')
                self.con.rollback(); failed.abort()
            self.assertEqual(storage.slot_state('perfil',7,'profile',self.cur)[1].filename,old.filename)
        self.assertNotIn(old.file_id,provider.deleted); self.assertNotIn(old.file_id,provider.trashed)
        self.assertEqual(len(provider.deleted),1)

    def test_existing_private_identifier_is_neither_published_nor_deleted(self):
        self.insert(area='visagismo/resultados')
        provider=Provider(); provider.put=Mock(return_value=FILE_ID)
        with patch.object(storage,'_provider',return_value=provider):
            batch=storage.ImageBatch(self.cur)
            with self.assertRaises(storage.ImageStorageError): batch.save(picture(),'site')
            batch.abort()
        self.assertEqual(provider.published,[]); self.assertEqual(provider.deleted,[])

    def test_public_cleanup_uses_authenticated_provider_not_read_only_reader(self):
        provider=Provider()
        with patch.object(storage,'_provider',return_value=provider) as factory:
            first=storage.ImageBatch(self.cur); old=first.save(picture(),'perfil',7,'profile'); self.con.commit(); first.commit()
            second=storage.ImageBatch(self.cur); second.save(picture(),'perfil',7,'profile'); self.con.commit(); second.commit()
        self.assertIn(old.file_id,provider.trashed)
        self.assertTrue(any(call.args==('google_drive',) for call in factory.call_args_list))

    def test_upload_still_requires_oauth_and_invalid_public_config_cannot_publish_private_areas(self):
        with self.assertRaises(storage.ImageStorageError): storage.ImageBatch(self.cur).save(picture(),'perfil',7)
        provider=Provider()
        with patch.dict(app.config,GOOGLE_DRIVE_PUBLIC_AREAS='site,visagismo/fotos'), patch.object(storage,'_provider',return_value=provider):
            with self.assertRaises(storage.ImageStorageError): storage.ImageBatch(self.cur).save(picture(),'visagismo/fotos',7)
        self.assertEqual(provider.published,[])


if __name__ == '__main__': unittest.main()
