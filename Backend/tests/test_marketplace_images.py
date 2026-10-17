"""Product image ownership, multipart validation and transaction regressions."""
import os
os.environ['STARTUP_MIGRATIONS']='false'
import io
import json
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
from flask import Response
import main
import marketplace as mp
from tests.test_marketplace import PRODUCT
from tests.test_visagismo import PNG

NAME='a'*32+'.webp'
URL='/uploads/marketplace/'+NAME

class MarketplaceImages(unittest.TestCase):
    def setUp(self):
        self.app=main.app
        self.client=self.app.test_client()
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.con=MagicMock();self.cur=self.con.cursor.return_value
        self.batch=MagicMock();self.batch.save.return_value=SimpleNamespace(url=URL,filename=NAME)
        self.factory=self.stack.enter_context(patch.object(mp,'ImageBatch',return_value=self.batch))
        self.stack.enter_context(patch.object(mp,'lock_user'))
        self.stack.enter_context(patch.object(mp,'next_id',return_value=99))
        self.stack.enter_context(patch.object(mp,'stock_move'))
        self.stack.enter_context(patch.object(mp.comercial,'save_metadata'))
        self.stack.enter_context(patch.object(mp,'get_product',return_value=('existing',)))
        self.stack.enter_context(patch.object(mp,'serialize_product',return_value={'id_produto':99,'imagens':[URL]}))

    def call_save(self,data=None,files=None,edit=False):
        values=PRODUCT.copy() if data is None else data
        if files is None:context=self.app.test_request_context('/gestao/marketplace/produtos',method='PUT' if edit else 'POST',json=values)
        else:context=self.app.test_request_context('/gestao/marketplace/produtos',method='PUT' if edit else 'POST',data={
            'dados':json.dumps(values),'imagens':[(io.BytesIO(content),name) for content,name in files]},content_type='multipart/form-data')
        with context:
            args=({'id_usuario':8,'tipo':2},8,self.cur,self.con)
            return mp.edit_product.__wrapped__(*args,99) if edit else mp.owner_products.__wrapped__(*args)

    def test_registered_photo_requires_same_salon(self):
        with patch.object(mp,'find_image',return_value=SimpleNamespace(owner_id=8,active=1)) as lookup:
            self.assertEqual(mp.image_url(URL,self.cur,8),URL)
            lookup.assert_called_once_with('marketplace',NAME,cursor=self.cur)
        for asset in (None,SimpleNamespace(owner_id=9,active=1),SimpleNamespace(owner_id=8,active=0)):
            with patch.object(mp,'find_image',return_value=asset),self.assertRaises(ValueError):mp.image_url(URL,self.cur,8)

    def test_managed_path_cannot_reference_private_images_or_traversal(self):
        for url in ('/uploads/visagismo/fotos/'+NAME,'/uploads/marketplace/../fotos/'+NAME,
                    '/uploads/marketplace/'+NAME+'?owner=8','/uploads/marketplace/'+NAME.upper(),'/uploads/marketplace/nope.png'):
            with self.subTest(url=url),patch.object(mp,'find_image') as lookup,self.assertRaises(ValueError):
                mp.image_url(url,self.cur,8)
            lookup.assert_not_called()

    def test_managed_reference_without_database_context_is_rejected(self):
        with self.assertRaises(ValueError):mp.image_url(URL)

    def test_multipart_files_and_links_committed_together(self):
        order=[];self.con.commit.side_effect=lambda:order.append('database');self.batch.commit.side_effect=lambda:order.append('images')
        response,status=self.call_save(files=[(PNG,'product.png')])
        self.assertEqual(status,201);self.assertEqual(response.json['produto']['imagens'],[URL])
        self.assertEqual(order,['database','images'])
        self.batch.save.assert_called_once();self.assertEqual(self.batch.save.call_args.args[1],'marketplace')
        self.assertEqual(self.batch.save.call_args.kwargs,{'owner_id':8})
        insert=next(call for call in self.cur.execute.call_args_list if 'INSERT INTO MP_PRODUTO' in call.args[0])
        image_json=next(value for value in insert.args[1] if isinstance(value,str) and URL in value)
        self.assertEqual(json.loads(image_json),PRODUCT['imagens']+[URL]);self.batch.abort.assert_not_called()

    def test_real_batch_compresses_product_photo_before_mock_drive_upload(self):
        import image_storage
        provider=MagicMock();provider.name='google_drive';provider.put.return_value='private-drive-file'
        with patch.object(mp,'ImageBatch',image_storage.ImageBatch),patch.object(image_storage,'_provider',return_value=provider),patch.object(image_storage,'_table_exists',return_value=True):
            self.call_save(files=[(PNG,'product.png')])
        area,filename,content=provider.put.call_args.args
        self.assertEqual(area,'marketplace');self.assertTrue(filename.endswith('.webp'))
        self.assertEqual(content[:4],b'RIFF');self.assertEqual(content[8:12],b'WEBP')
        from PIL import Image
        image=Image.open(io.BytesIO(content));self.assertEqual(image.format,'WEBP');self.assertEqual(image.size,(32,32))
        metadata=next(call for call in self.cur.execute.call_args_list if 'INSERT INTO IMAGE_ASSET' in call.args[0])
        self.assertEqual(metadata.args[1][3],'private-drive-file');self.assertEqual(metadata.args[1][4],8)
        provider.delete.assert_not_called()

    def test_real_batch_failed_business_commit_deletes_only_new_drive_object(self):
        import image_storage
        provider=MagicMock();provider.name='google_drive';provider.put.return_value='new-private-file'
        self.con.commit.side_effect=RuntimeError('database failure')
        with patch.object(mp,'ImageBatch',image_storage.ImageBatch),patch.object(image_storage,'_provider',return_value=provider),patch.object(image_storage,'_table_exists',return_value=True):
            with self.assertRaises(RuntimeError):self.call_save(files=[(PNG,'product.png')])
        provider.delete.assert_called_once_with('new-private-file')
        self.con.rollback.assert_called_once()

    def test_files_count_includes_existing_urls(self):
        with self.assertRaises(ValueError):self.call_save(data=PRODUCT|{'imagens':['https://example.com/photo.png']*8},files=[(PNG,'extra.png')])
        self.factory.assert_not_called()
        self.batch.save.assert_not_called()

    def test_invalid_second_file_never_creates_first_remote_asset(self):
        with self.assertRaises(mp.ImageStorageError):self.call_save(files=[(PNG,'good.png'),(b'not image','bad.png')])
        self.batch.save.assert_not_called();self.factory.assert_not_called()

    def test_database_failure_aborts_new_photos(self):
        self.con.commit.side_effect=RuntimeError('database failure')
        with self.assertRaises(RuntimeError):self.call_save(files=[(PNG,'photo.png')])
        self.con.rollback.assert_called_once();self.batch.abort.assert_called_once();self.batch.commit.assert_not_called()

    def test_edit_does_not_upload_for_missing_or_foreign_product(self):
        with patch.object(mp,'get_product',return_value=None):response,status=self.call_save(files=[(PNG,'photo.png')],edit=True)
        self.assertEqual(status,404);self.batch.save.assert_not_called()

    def test_legacy_json_https_product_save_remains_compatible(self):
        response,status=self.call_save()
        self.assertEqual(status,201);self.assertEqual(response.json['produto']['id_produto'],99)
        self.batch.save.assert_not_called();self.con.commit.assert_called_once()

    def test_edit_failure_preserves_old_reference(self):
        with patch.object(mp,'find_image',return_value=SimpleNamespace(owner_id=8,active=1)):
            self.con.commit.side_effect=RuntimeError('database failure')
            with self.assertRaises(RuntimeError):self.call_save(data=PRODUCT|{'imagens':[URL]},files=[(PNG,'new.png')],edit=True)
        self.batch.abort.assert_called_once();self.batch.commit.assert_not_called()
        self.assertEqual(self.batch.save.call_count,1)

    def test_unauthenticated_multipart_never_decodes_or_uploads(self):
        with patch.object(mp,'obter_usuario_logado',return_value=None),patch.object(mp,'compress_image') as compress:
            response=self.client.post('/gestao/marketplace/produtos',data={'dados':'{}','imagens':(io.BytesIO(PNG),'photo.png')})
        self.assertEqual(response.status_code,401);compress.assert_not_called();self.batch.save.assert_not_called()

    def test_media_url_rejects_invalid_names_before_provider(self):
        with patch.object(mp,'serve_image') as serve:
            for filename in ('a.png','nested/'+NAME,'..%2F'+NAME):
                self.assertEqual(self.client.get('/uploads/marketplace/'+filename).status_code,404)
            serve.assert_not_called()

    def test_public_media_uses_only_marketplace_area(self):
        with patch.object(mp,'serve_image',return_value=Response(PNG,mimetype='image/webp')) as serve:
            self.assertEqual(self.client.get(URL).status_code,200)
            serve.assert_called_once_with('marketplace',NAME)

    def test_malformed_multipart_json_never_uploads(self):
        with self.app.test_request_context('/gestao/marketplace/produtos',method='POST',data={'dados':'[]','imagens':(io.BytesIO(PNG),'photo.png')}):
            with self.assertRaises(ValueError):mp.product_body()
        self.batch.save.assert_not_called()

if __name__=='__main__':unittest.main()
