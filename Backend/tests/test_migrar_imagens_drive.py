"""Offline migration safety without real Drive credentials or application DB."""
import argparse
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from application import app
import migrar_imagens_drive as migration
import image_storage as storage
from tests.test_image_storage import Cursor, Provider


class MigrationCursor(Cursor):
    def fetchall(self):
        return self.cursor.fetchall()

    def execute(self, sql, args=()):
        if 'RDB$RELATION_FIELDS' in sql:
            table, column = args
            columns = self.cursor.execute('PRAGMA table_info(' + table + ')').fetchall()
            return self.cursor.execute('SELECT 1 WHERE ?', (int(any(c[1] == column for c in columns)),))
        return super().execute(sql.replace(' WITH LOCK', ''), args)


class Connection:
    def __init__(self, con): self.con = con
    def cursor(self): return MigrationCursor(self.con)
    def commit(self): self.con.commit()
    def rollback(self): self.con.rollback()
    def close(self): pass


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context(); self.context.push()
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.config = {'UPLOAD_FOLDER': str(self.root), 'PERFIL_FOLDER': str(self.root / 'perfil'),
                       'DB_NAME': str(self.root / 'ACTIVE.FDB'), 'IMAGE_STORAGE_PROVIDER': 'google_drive'}
        self.con = sqlite3.connect(':memory:')
        self.con.executescript('''CREATE TABLE USUARIO(ID_USUARIO INTEGER PRIMARY KEY,TIPO INTEGER);
          INSERT INTO USUARIO VALUES(7,1);INSERT INTO USUARIO VALUES(8,1);INSERT INTO USUARIO VALUES(11,2);
          CREATE TABLE CORTE_VISAGISMO(ID_CORTE INTEGER PRIMARY KEY,ID_USUARIO INTEGER,IMAGEM_ROTA TEXT);
          CREATE TABLE VISAGISMO_SESSAO(ID_VISAGISMO INTEGER PRIMARY KEY,ID_USUARIO INTEGER,FOTO_ROTA TEXT,RESULTADO_ROTA TEXT);
          CREATE TABLE IMAGE_ASSET(NOME TEXT,AREA TEXT,PROVIDER TEXT,FILE_ID TEXT,OWNER_ID INTEGER,SLOT TEXT,
            MIME TEXT,LARGURA INTEGER,ALTURA INTEGER,TAMANHO INTEGER,SHA256 TEXT,ATIVO INTEGER,
            CRIADO_EM TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(AREA,NOME));
          CREATE TABLE IMAGE_SLOT(AREA TEXT,OWNER_ID INTEGER,SLOT TEXT,NOME TEXT,PRIMARY KEY(AREA,OWNER_ID,SLOT));''')
        self.cur = MigrationCursor(self.con); self.provider = Provider()
        self.storage = patch.object(storage, '_provider', return_value=self.provider); self.storage.start()
        raw = io.BytesIO(); Image.new('RGB', (100, 80), 'blue').save(raw, 'PNG'); self.raw = raw.getvalue()

    def tearDown(self):
        self.storage.stop(); self.cur.close(); self.con.close(); self.temp.cleanup(); self.context.pop()

    def local(self, area, filename):
        folder = self.root / area; folder.mkdir(parents=True, exist_ok=True)
        path = folder / filename; path.write_bytes(self.raw); return path

    def plan(self): return migration.inventory(self.cur, self.config)
    def connect(self): return Connection(self.con)

    def test_default_inventory_does_not_upload_or_include_orphans_external_urls_assets(self):
        self.local('perfil', '7.jpg'); self.local('perfil', '999.jpg')
        self.local('barbearia', '11_2.png'); self.local('visagismo/fotos', 'orphan.png')
        self.local('visagismo/fotos', 'client.png')
        self.con.execute('INSERT INTO VISAGISMO_SESSAO VALUES(1,7,?,NULL)', ('client.png',))
        self.con.execute('INSERT INTO CORTE_VISAGISMO VALUES(1,11,?)', ('https://example.invalid/product.jpg',))
        self.con.commit()
        items, skipped = self.plan()
        self.assertEqual({(i.area, i.filename) for i in items},
                         {('perfil', '7.jpg'), ('barbearia', '11_2.png'), ('visagismo/fotos', 'client.png')})
        self.assertEqual(skipped['ausentes_ou_externas'], 1)
        self.assertEqual(self.provider.files, {})
        args = argparse.Namespace(aplicar=False, banco=None, backup=None)
        report = migration.run(args, self.config, self.connect)
        self.assertEqual(report['planejadas'], 3); self.assertEqual(report['migradas'], 0)
        self.assertNotIn('client.png', str(report)); self.assertTrue(report['originais_preservados'])

    def test_migrate_shared_session_reference_preserves_alias_acl_data_original_and_is_idempotent(self):
        original = self.local('visagismo/fotos', 'client.png')
        self.con.executemany('INSERT INTO VISAGISMO_SESSAO VALUES(?,?,?,NULL)',
                             [(1, 7, 'client.png'), (2, 8, 'client.png')]); self.con.commit()
        items, _ = self.plan(); self.assertEqual(len(items), 1); self.assertEqual(items[0].owners, {7, 8})
        self.assertEqual(migration.migrate_item(items[0], self.connect), 'migrada')
        asset = storage.find_image('visagismo/fotos', 'client.png', self.cur)
        self.assertIsNone(asset.owner_id); self.assertEqual(asset.mime, 'image/webp')
        self.assertEqual(original.read_bytes(), self.raw)
        self.assertEqual(self.con.execute('SELECT ID_USUARIO,FOTO_ROTA FROM VISAGISMO_SESSAO ORDER BY ID_VISAGISMO').fetchall(),
                         [(7, 'client.png'), (8, 'client.png')])
        self.assertTrue(storage.read_image('visagismo/fotos', 'client.png', cursor=self.cur).startswith(b'RIFF'))
        self.assertEqual(self.plan()[0], [])
        self.assertEqual(migration.migrate_item(items[0], self.connect), 'alterada_ou_gerenciada')
        self.assertEqual(len(self.provider.files), 1)

    def test_profile_slot_tombstone_and_existing_current_cloud_are_not_reimported(self):
        self.local('perfil', '7.jpg')
        batch = storage.ImageBatch(self.cur); batch.delete('perfil', 7, 'profile'); self.con.commit(); batch.commit()
        self.assertEqual(self.plan()[0], [])
        self.local('barbearia', '11.jpg')
        batch = storage.ImageBatch(self.cur); batch.save(self.raw, 'barbearia', 11, 'logo'); self.con.commit(); batch.commit()
        self.assertEqual(self.plan()[0], [])

    def test_changed_reference_between_plan_and_apply_does_not_upload(self):
        self.local('visagismo/fotos', 'old.png')
        self.con.execute('INSERT INTO VISAGISMO_SESSAO VALUES(1,7,?,NULL)', ('old.png',)); self.con.commit()
        item = self.plan()[0][0]
        self.con.execute("UPDATE VISAGISMO_SESSAO SET FOTO_ROTA='other.png' WHERE ID_VISAGISMO=1"); self.con.commit()
        self.assertEqual(migration.migrate_item(item, self.connect), 'alterada_ou_gerenciada')
        self.assertEqual(self.provider.files, {})

    def test_commit_failure_rolls_back_reference_and_deletes_only_new_remote_file(self):
        original = self.local('perfil', '7.jpg'); item = self.plan()[0][0]
        connection = self.connect(); connection.commit = Mock(side_effect=RuntimeError('commit failed'))
        with self.assertRaises(RuntimeError):
            migration.migrate_item(item, lambda: connection)
        self.assertEqual(self.provider.files, {}); self.assertEqual(len(self.provider.deleted), 1)
        self.assertEqual(storage.slot_state('perfil', 7, 'profile', self.cur), (False, None))
        self.assertEqual(original.read_bytes(), self.raw)

    def test_backup_and_database_identity_required_before_apply(self):
        active = Path(self.config['DB_NAME']); active.write_bytes(b'active')
        backup = self.root / 'BACKUP.FBK'; backup.write_bytes(b'isolated verified backup fixture')
        for database, candidate in [(None, None), (str(self.root / 'OTHER.FDB'), str(backup)),
                                    (str(active), str(active)), (str(active), str(self.root / 'missing.fbk'))]:
            with self.assertRaises(ValueError):
                migration.validate_backup(self.config, database, candidate)
        self.assertEqual(migration.validate_backup(self.config, str(active), str(backup)), backup.resolve())

    def test_reference_parser_does_not_accept_remote_url_path_traversal_or_other_area(self):
        for value in ('https://example.invalid/a.jpg', '../a.png', '/uploads/perfil/7.jpg', 'a/../b.jpg', 'x.svg'):
            self.assertIsNone(migration.reference_name(value, 'visagismo/fotos'))
        self.assertEqual(migration.reference_name('/uploads/visagismo/fotos/client.png', 'visagismo/fotos'), 'client.png')

    def test_registered_reference_without_original_is_managed_not_missing(self):
        batch = storage.ImageBatch(self.cur)
        batch.save(self.raw, 'visagismo/fotos', 7, legacy_filename='removed-original.png')
        self.con.execute("INSERT INTO VISAGISMO_SESSAO VALUES(1,7,'removed-original.png',NULL)")
        self.con.commit(); batch.commit()
        items, skipped = self.plan()
        self.assertEqual(items, [])
        self.assertEqual(skipped, {'gerenciadas': 1, 'ausentes_ou_externas': 0})

    def test_remote_catalog_download_then_atomic_reference_update_and_idempotence(self):
        url = 'https://public.example/cut.png'
        self.con.execute('INSERT INTO CORTE_VISAGISMO VALUES(1,11,?)', (url,)); self.con.commit()
        items, skipped = migration.inventory(self.cur, self.config, include_external=True)
        self.assertEqual(len(items), 1); self.assertIsInstance(items[0], migration.RemotePlanItem)
        order = []
        def download(value):
            order.append('download'); self.assertEqual(value, url); return self.raw, 'image/png'
        def connect():
            order.append('connect'); return self.connect()
        with patch('visagismo.carregar_referencia_corte', side_effect=download):
            self.assertEqual(migration.migrate_item(items[0], connect), 'migrada')
        self.assertEqual(order, ['download', 'connect'])
        alias = self.con.execute('SELECT IMAGEM_ROTA FROM CORTE_VISAGISMO').fetchone()[0]
        self.assertRegex(alias, r'^[a-f0-9]{32}\.webp$')
        asset = storage.find_image('visagismo/cortes', alias, self.cur)
        self.assertEqual(asset.owner_id, 11)
        self.assertEqual(storage.read_image('visagismo/cortes', alias, cursor=self.cur), self.provider.files[asset.file_id])
        self.assertEqual(migration.inventory(self.cur, self.config, include_external=True)[0], [])

    def test_remote_failure_changed_reference_and_commit_failure_preserve_catalog(self):
        url = 'https://public.example/cut.png'
        self.con.execute('INSERT INTO CORTE_VISAGISMO VALUES(1,11,?)', (url,)); self.con.commit()
        item = migration.inventory(self.cur, self.config, include_external=True)[0][0]
        connect = Mock(side_effect=AssertionError('No DB before download success'))
        with patch('visagismo.carregar_referencia_corte', side_effect=ValueError('remote unavailable')):
            with self.assertRaises(ValueError):
                migration.migrate_item(item, connect)
        connect.assert_not_called()
        self.assertEqual(self.con.execute('SELECT IMAGEM_ROTA FROM CORTE_VISAGISMO').fetchone()[0], url)
        self.con.execute("UPDATE CORTE_VISAGISMO SET IMAGEM_ROTA='changed'"); self.con.commit()
        with patch('visagismo.carregar_referencia_corte', return_value=(self.raw, 'image/png')):
            self.assertEqual(migration.migrate_item(item, self.connect), 'alterada_ou_gerenciada')
        self.assertEqual(self.provider.files, {})
        self.con.execute('UPDATE CORTE_VISAGISMO SET IMAGEM_ROTA=?', (url,)); self.con.commit()
        connection = self.connect(); connection.commit = Mock(side_effect=RuntimeError('commit failed'))
        with patch('visagismo.carregar_referencia_corte', return_value=(self.raw, 'image/png')):
            with self.assertRaises(RuntimeError):
                migration.migrate_item(item, lambda: connection)
        self.assertEqual(self.provider.files, {})
        self.assertEqual(self.con.execute('SELECT IMAGEM_ROTA FROM CORTE_VISAGISMO').fetchone()[0], url)


if __name__ == '__main__':
    unittest.main()
