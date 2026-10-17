"""Opt-in production SQL tests, using a newly created disposable database only."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ['STARTUP_MIGRATIONS'] = 'false'
os.environ['WAITLIST_WORKER'] = 'false'
import firebirdsql
from PIL import Image
from application import app
import image_storage as storage
import image_storage_schema as schema


@unittest.skipUnless(os.environ.get('RUN_FIREBIRD_IMAGE_TESTS') == '1', 'isolated Firebird opt-in')
class ImageStorageFirebird(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix='cortae-images-')).resolve()
        self.db = self.folder / 'IMAGES-QA.FDB'
        self.options = dict(host='127.0.0.1', port=int(os.getenv('IMAGE_TEST_FIREBIRD_PORT', '3050')),
                            user=os.getenv('IMAGE_TEST_FIREBIRD_USER', 'SYSDBA'),
                            password=os.environ.get('IMAGE_TEST_FIREBIRD_PASSWORD', os.environ.get('DB_PASSWORD', app.config['DB_PASSWORD'])),
                            database=str(self.db), charset='UTF8')
        con = firebirdsql.create_database(**self.options); con.close(); self.addCleanup(self.drop)
        with patch.object(schema, 'conectar_banco', side_effect=self.connect):
            schema.migrar_imagens(); schema.migrar_imagens()
        self.context = app.app_context(); self.context.push(); self.addCleanup(self.context.pop)
        self.config = patch.dict(app.config, IMAGE_STORAGE_PROVIDER='local', IMAGE_LOCAL_FOLDER=str(self.folder / 'media'))
        self.config.start(); self.addCleanup(self.config.stop)
        image = Image.new('RGB', (160, 90), 'orange'); raw = io.BytesIO(); image.save(raw, 'PNG'); self.picture = raw.getvalue()

    def connect(self):
        return firebirdsql.connect(**self.options)

    def drop(self):
        if self.db.exists():
            con = self.connect(); con.drop_database(); con.close()
        # Remove only this test's known UUID images and newly created directories.
        media = self.folder / 'media'
        if media.exists():
            for entry in media.rglob('*.webp'):
                if entry.resolve().is_relative_to(media.resolve()) and storage.MANAGED_NAME.fullmatch(entry.name):
                    entry.unlink()
            for directory in sorted((p for p in media.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                directory.rmdir()
            media.rmdir()
        self.folder.rmdir()

    def test_real_migration_write_slot_and_binary_not_in_schema(self):
        con = self.connect(); cur = con.cursor()
        try:
            batch = storage.ImageBatch(cur); asset = batch.save(self.picture, 'perfil', 7, 'profile')
            con.commit(); batch.commit()
            self.assertEqual(storage.slot_state('perfil', 7, 'profile', cur)[1].filename, asset.filename)
            self.assertEqual(storage.read_image('perfil', asset.filename, cursor=cur), asset.content)
            cur.execute("SELECT F.RDB$FIELD_TYPE FROM RDB$RELATION_FIELDS R JOIN RDB$FIELDS F "
                        "ON R.RDB$FIELD_SOURCE=F.RDB$FIELD_NAME WHERE TRIM(R.RDB$RELATION_NAME)='IMAGE_ASSET'")
            self.assertNotIn(261, [row[0] for row in cur.fetchall()])
        finally:
            cur.close(); con.close()

    def test_real_rollback_and_delete_tombstone(self):
        con = self.connect(); cur = con.cursor()
        try:
            first = storage.ImageBatch(cur); old = first.save(self.picture, 'barbearia', 11, 'logo')
            con.commit(); first.commit()
            second = storage.ImageBatch(cur); new = second.save(self.picture, 'barbearia', 11, 'logo')
            con.rollback(); second.abort()
            self.assertEqual(storage.latest_image('barbearia', 11, 'logo', cur).filename, old.filename)
            self.assertIsNone(storage.find_image('barbearia', new.filename, cur))
            delete = storage.ImageBatch(cur); delete.delete('barbearia', 11, 'logo'); con.commit(); delete.commit()
            self.assertEqual(storage.slot_state('barbearia', 11, 'logo', cur), (True, None))
            with self.assertRaises(FileNotFoundError):
                storage.read_image('barbearia', old.filename, cursor=cur)
        finally:
            cur.close(); con.close()

    def test_real_migration_preserves_shared_legacy_session_references(self):
        import migrar_imagens_drive as migration
        con = self.connect(); cur = con.cursor()
        try:
            cur.execute('CREATE TABLE USUARIO(ID_USUARIO INTEGER PRIMARY KEY,TIPO INTEGER)')
            cur.execute('CREATE TABLE VISAGISMO_SESSAO(ID_VISAGISMO INTEGER PRIMARY KEY,ID_USUARIO INTEGER,'
                        'FOTO_ROTA VARCHAR(255),RESULTADO_ROTA VARCHAR(255))'); con.commit()
            for owner in (7, 8):
                cur.execute('INSERT INTO USUARIO VALUES(?,1)', (owner,))
                cur.execute("INSERT INTO VISAGISMO_SESSAO VALUES(?,?,'shared.jpg',NULL)", (owner, owner))
            con.commit()
            with tempfile.TemporaryDirectory(prefix='cortae-legacy-images-') as folder:
                root = Path(folder); original = root / 'visagismo/fotos/shared.jpg'
                original.parent.mkdir(parents=True); original.write_bytes(self.picture)
                config = dict(UPLOAD_FOLDER=str(root), PERFIL_FOLDER=str(root / 'perfil'))
                items, _ = migration.inventory(cur, config)
                self.assertEqual(len(items), 1)
                self.assertEqual(migration.migrate_item(items[0], self.connect), 'migrada')
                con.rollback()  # Refresh this separate read transaction after another connection's commit.
                self.assertEqual(original.read_bytes(), self.picture)
                cur.execute('SELECT FOTO_ROTA FROM VISAGISMO_SESSAO ORDER BY ID_VISAGISMO')
                self.assertEqual(cur.fetchall(), [('shared.jpg',), ('shared.jpg',)])
                self.assertEqual(storage.find_image('visagismo/fotos', 'shared.jpg', cur).mime, 'image/webp')
                self.assertEqual(migration.inventory(cur, config)[0], [])
        finally:
            cur.close(); con.close()


if __name__ == '__main__':
    unittest.main()
