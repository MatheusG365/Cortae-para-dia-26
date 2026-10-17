"""Static artwork roundtrip, scope boundaries and migration restart safety."""
import argparse
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from application import app
import main
import image_storage as storage
import migrar_imagens_drive as migration
import midia
import visagismo
from google_drive_storage import DriveError
from tests.test_image_storage import Provider, picture
from tests.test_migrar_imagens_drive import MigrationCursor, Connection


class PublicArtworkTests(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context(); self.context.push()
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.con = sqlite3.connect(':memory:')
        self.con.executescript('''CREATE TABLE IMAGE_ASSET(NOME TEXT,AREA TEXT,PROVIDER TEXT,FILE_ID TEXT,
          OWNER_ID INTEGER,SLOT TEXT,MIME TEXT,LARGURA INTEGER,ALTURA INTEGER,TAMANHO INTEGER,SHA256 TEXT,
          ATIVO INTEGER,CRIADO_EM TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(AREA,NOME));
          CREATE TABLE IMAGE_SLOT(AREA TEXT,OWNER_ID INTEGER,SLOT TEXT,NOME TEXT,PRIMARY KEY(AREA,OWNER_ID,SLOT));''')
        self.cur = MigrationCursor(self.con); self.provider = Provider()
        self.provider_patch = patch.object(storage, '_provider', return_value=self.provider)
        self.provider_patch.start()
        self.client = app.test_client()

    def tearDown(self):
        self.provider_patch.stop(); self.cur.close(); self.con.close(); self.temp.cleanup(); self.context.pop()

    @contextmanager
    def cursor(self, unused=None):
        yield self.cur

    def save(self, area, alias):
        batch = storage.ImageBatch(self.cur)
        asset = batch.save(picture('RGBA'), area, legacy_filename=alias)
        self.con.commit(); batch.commit()
        return asset

    def test_public_roundtrip_actual_webp_and_no_drive_identifier_in_headers(self):
        for area in ('site', 'mobile'):
            asset = self.save(area, 'logo.png')
            self.assertEqual(asset.url, f'/midia/{area}/logo.png')
            with patch.object(storage, '_cursor', self.cursor):
                response = self.client.get(asset.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'image/webp')
            self.assertEqual(response.data, asset.content)
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
            self.assertNotIn(asset.file_id, str(response.headers))

    def test_unknown_or_private_area_and_unregistered_name_never_fetch_provider(self):
        with patch.object(storage, '_cursor', self.cursor), patch.object(self.provider, 'get') as get:
            for url in ('/midia/perfil/7.jpg', '/midia/visagismo/fotos/a.jpg', '/midia/site/missing.png',
                        '/midia/mobile/a..jpg'):
                self.assertEqual(self.client.get(url).status_code, 404)
            get.assert_not_called()

    def test_google_mode_never_uses_local_legacy_file_for_missing_metadata(self):
        (self.root/'7.jpg').write_bytes(picture())
        with patch.dict(app.config, IMAGE_STORAGE_PROVIDER='google_drive'):
            with self.assertRaises(FileNotFoundError):
                storage.read_image('perfil', '7.jpg', self.root, self.cur)

    def test_public_provider_failure_is_503_and_does_not_cache_error(self):
        asset = self.save('site', 'banner.png')
        with patch.object(storage, '_cursor', self.cursor), \
             patch.object(self.provider, 'get', side_effect=DriveError('Drive indisponível.')):
            response = self.client.get(asset.url)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_cut_catalog_resolves_registered_drive_asset_without_local_file(self):
        asset = self.save('visagismo/cortes', 'catalog.png')
        with patch.object(storage, '_cursor', self.cursor), \
             patch.object(visagismo.os.path, 'isfile', side_effect=AssertionError('Local fallback')):
            self.assertEqual(visagismo.url_corte('catalog.png'), asset.url)
            self.assertIsNone(visagismo.url_corte('missing.png'))

    def test_static_manifest_import_is_idempotent_preserves_originals_and_native_build_files(self):
        site = self.root/'public'; mobile = self.root/'mobile'; site.mkdir(); mobile.mkdir()
        raw = picture()
        for name in migration.SITE_IMAGES:
            (site/name).write_bytes(raw)
        for source, alias in migration.MOBILE_IMAGES:
            (mobile/source).write_bytes(raw)
        native = mobile/'icon.png'; native.write_bytes(b'KEEP NATIVE')
        items, managed = migration.static_inventory(self.cur, site, mobile)
        self.assertEqual((len(items), managed), (19, 0))
        self.assertIn(('mobile', 'banner-1.png'), {(i.area, i.filename) for i in items})
        for item in items:
            self.assertEqual(migration.migrate_item(item, lambda: Connection(self.con)), 'migrada')
            self.assertEqual(item.path.read_bytes(), raw)
            self.assertTrue(storage.read_image(item.area, item.filename, cursor=self.cur).startswith(b'RIFF'))
        self.assertEqual(migration.static_inventory(self.cur, site, mobile), ([], 19))
        self.assertEqual(native.read_bytes(), b'KEEP NATIVE')

    def test_deleted_static_source_cannot_be_silently_omitted(self):
        with self.assertRaises(ValueError):
            migration.static_inventory(self.cur, self.root, self.root)


if __name__ == '__main__':
    unittest.main()
