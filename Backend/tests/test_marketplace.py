"""Marketplace validation/financial response tests. Provider operations always mocked."""
import os
os.environ['STARTUP_MIGRATIONS']='false'
os.environ['WAITLIST_WORKER']='false'
import unittest
from decimal import Decimal
from unittest.mock import patch,MagicMock
import main
import marketplace as mp
import melhor_envio

ADDRESS={'nome':'Cliente QA','email':'cliente@example.invalid','telefone':'11912345678','documento':'12345678901','cep':'01001000','logradouro':'Praça QA','numero':'10','bairro':'Centro','cidade':'São Paulo','uf':'SP'}
PRODUCT={'nome':'Pomada QA','descricao':'Pomada de teste','detalhes':'Fosca','categoria':'Cabelo','marca':'QA','preco':'25.99','estoque':10,'estoque_minimo':2,'peso':'.2','largura':10,'altura':5,'comprimento':10,'imagens':['https://example.com/product.png']}

class MarketplaceValidation(unittest.TestCase):
    def test_store_invalid_integer_range_never_opens_database(self):
        client=main.app.test_client()
        for id_ in ('0','2147483648','9999999999999999999999999'):
            with self.subTest(id_=id_),patch.object(mp,'conectar_banco') as connect:
                response=client.get('/marketplace/barbearias/'+id_)
                self.assertEqual(response.status_code,404);connect.assert_not_called()
    def test_price_decimal_and_no_float_stock_coercion(self):
        result=mp.product_data(PRODUCT,True);self.assertEqual(result['preco'],Decimal('25.99'))
        for amount in (True,1.5,'2',-1,None):
            with self.subTest(amount=amount),self.assertRaises(ValueError):mp.qty(amount,True)
    def test_product_missing_dimensions_invalid_price_never_accepted(self):
        for field,value in (('peso',0),('altura',True),('largura','NaN'),('comprimento',None),('preco',-2),('preco','Infinity')):
            with self.subTest(field=field),self.assertRaises(ValueError):mp.product_data(PRODUCT|{field:value},True)
    def test_images_https_and_private_host_blocked(self):
        for url in ('http://example.com/x','https://localhost/x','https://127.0.0.1/x','https://192.168.0.1/x','https://user:password@example.com/x','data:image/png;base64,xxx'):
            with self.subTest(url=url),self.assertRaises(ValueError):mp.image_url(url)
        self.assertEqual(mp.image_url('https://example.com/x'),'https://example.com/x')
    def test_provider_never_fetches_images(self):
        with patch('urllib.request.urlopen') as urlopen:mp.product_data(PRODUCT,True)
        urlopen.assert_not_called()
    def test_address_normalizes_and_rejects_invalid(self):
        result=mp.address(ADDRESS|{'cep':'01001-000','uf':'sp'});self.assertEqual(result['cep'],'01001000');self.assertEqual(result['uf'],'SP')
        for data in (ADDRESS|{'documento':''},ADDRESS|{'cep':'123'},ADDRESS|{'email':'bad'},[] ):
            with self.assertRaises(ValueError):mp.address(data)
    def test_quote_hash_includes_package_and_sender(self):
        item={'id_produto':1,'id_barbearia':2,'preco':25.99,'quantidade':2,'produto':dict(peso=.2,largura=10,altura=5,comprimento=10)}
        a=mp.cart_hash([item],ADDRESS);b=mp.cart_hash([item|{'produto':item['produto']|{'peso':.5}}],ADDRESS);c=mp.cart_hash([item],ADDRESS|{'cep':'22222222'})
        self.assertNotEqual(a,b);self.assertNotEqual(a,c)
    def test_idempotency_hash_binds_all_payload(self):
        a=mp.fingerprint({'quantidade':1,'observacao':'A'});b=mp.fingerprint({'quantidade':2,'observacao':'A'});self.assertNotEqual(a,b)
        self.assertEqual(mp.fingerprint({'a':1,'b':2}),mp.fingerprint({'b':2,'a':1}))
    def test_pix_response_strict_matches_id_amount_and_status(self):
        data={'id':'charge_1','valor':'51.98','status':1,'pix':'code'}
        self.assertEqual(mp.pix_response(data,Decimal('51.98'),'charge_1')['status'],1)
        for field,value in (('id','../other'),('id','charge_2'),('valor','1'),('status','approved'),('status',True),('status',2),('status',None)):
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):mp.pix_response(data|{field:value},Decimal('51.98'),'charge_1')
    def test_label_urls_only_provider_https(self):
        self.assertEqual(mp.safe_label_url('https://melhorenvio.com.br/print/a'),'https://melhorenvio.com.br/print/a')
        for value in ('http://melhorenvio.com.br/x','https://evil.test/x','https://melhorenvio.com.br.evil.test/x','https://secret@melhorenvio.com.br/x'):self.assertIsNone(mp.safe_label_url(value))
    def test_anonymous_every_private_route_no_db_calls(self):
        client=main.app.test_client()
        routes=[('get','/marketplace/carrinho'),('put','/marketplace/carrinho/1'),('get','/marketplace/favoritos'),('post','/marketplace/frete'),('post','/marketplace/pedidos'),('get','/marketplace/pedidos/1'),('post','/marketplace/pedidos/1/pix'),('get','/marketplace/pedidos/1/pagamento'),('post','/marketplace/pedidos/1/cancelar'),('put','/marketplace/produtos/1/avaliacao'),('get','/gestao/marketplace/produtos'),('post','/gestao/marketplace/pedidos/1/etiqueta')]
        for method,path in routes:
            with self.subTest(path=path),patch.object(mp,'obter_usuario_logado',return_value=None),patch.object(mp,'conectar_banco') as connect:
                self.assertEqual(getattr(client,method)(path,json={}).status_code,401);connect.assert_not_called()
    def test_database_role_reload_rejects_stale_token_owner(self):
        con=MagicMock();con.cursor.return_value.fetchone.return_value=(1,1)
        with patch.object(mp,'obter_usuario_logado',return_value={'id_usuario':1,'tipo':2}),patch.object(mp,'conectar_banco',return_value=con):
            response=main.app.test_client().get('/gestao/marketplace/produtos')
        self.assertEqual(response.status_code,403)
    def test_provider_missing_token_explicit_503_never_network(self):
        with main.app.app_context(),patch.dict(main.app.config,{'MELHOR_ENVIO_TOKEN':None}),patch('urllib.request.urlopen') as network:
            with self.assertRaises(melhor_envio.EntregaErro) as error:melhor_envio.calcular('01001000','22222222',[])
            self.assertEqual(error.exception.status,503);network.assert_not_called()
    def test_tracking_validates_provider_id_and_documented_states(self):
        id_='6448a012-2a76-419f-b1fd-5b6728d384fd'
        self.assertEqual(mp.tracking_entry({id_:{'id':id_,'status':'posted','tracking':'BR001'}},id_)['status'],'posted')
        for response in ({},{id_:{'status':'invented'}},{id_:{'status':'delivered','id':'other'}},{id_:{'status':'posted','error':True}}):
            with self.assertRaises(melhor_envio.EntregaErro):mp.tracking_entry(response,id_)
    def test_write_labels_disabled_before_network(self):
        con=MagicMock();con.cursor.return_value.fetchone.side_effect=[(2,2),(2,)]
        with patch.object(mp,'obter_usuario_logado',return_value={'id_usuario':2,'tipo':2}),patch.object(mp,'conectar_banco',return_value=con),patch.dict(main.app.config,{'MELHOR_ENVIO_EMITIR_ETIQUETAS':False}),patch.object(melhor_envio,'chamar') as network:
            response=main.app.test_client().post('/gestao/marketplace/pedidos/1/etiqueta',json={'acao':'comprar','confirmar_custo':True})
        self.assertEqual(response.status_code,403);network.assert_not_called()
    def test_adapter_cart_exact_path_authorization_not_payload(self):
        context=MagicMock();context.__enter__.return_value.read.return_value=b'{"id":"shipment"}'
        with main.app.app_context(),patch.dict(main.app.config,{'MELHOR_ENVIO_TOKEN':'qa-token','MELHOR_ENVIO_SANDBOX':True,'MELHOR_ENVIO_USER_AGENT':'QA (qa@example.invalid)'}),patch('urllib.request.urlopen',return_value=context) as network:
            melhor_envio.chamar('POST','/api/v2/me/cart',{'service':1})
        req=network.call_args.args[0];self.assertEqual(req.full_url,'https://sandbox.melhorenvio.com.br/api/v2/me/cart');self.assertNotIn(b'qa-token',req.data)

if __name__=='__main__':unittest.main()
