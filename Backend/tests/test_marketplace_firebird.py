"""Disposable Firebird marketplace integration tests; never opens existing application databases."""
import os
os.environ['STARTUP_MIGRATIONS']='false'
os.environ['WAITLIST_WORKER']='false'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import firebirdsql
import main
import marketplace as mp
import marketplace_schema
import termos_schema
import termos
from test_marketplace import PRODUCT,ADDRESS

@unittest.skipUnless(os.environ.get('RUN_FIREBIRD_MARKETPLACE_TESTS')=='1','isolated Firebird opt-in')
class MarketplaceFirebird(unittest.TestCase):
    def setUp(self):
        self.directory=Path(tempfile.mkdtemp(prefix='cortae-marketplace-')).resolve();self.db=self.directory/'MARKETPLACE-QA.FDB'
        self.options=dict(host='127.0.0.1',port=3050,user=os.environ.get('MARKETPLACE_TEST_FIREBIRD_USER','SYSDBA'),password=os.environ.get('MARKETPLACE_TEST_FIREBIRD_PASSWORD', os.environ.get('DB_PASSWORD', main.app.config['DB_PASSWORD'])),database=str(self.db),charset='UTF8')
        con=firebirdsql.create_database(**self.options);cur=con.cursor();self.addCleanup(self.drop)
        try:
            cur.execute('CREATE TABLE USUARIO(ID_USUARIO INTEGER PRIMARY KEY,TIPO SMALLINT,NOME VARCHAR(100),ATIVO SMALLINT,EMAIL_CONFIRMADO SMALLINT)');con.commit()
            for row in ((10,2,'Salão QA',1,1),(11,2,'Outro QA',1,1),(20,1,'Cliente QA',1,1),(21,1,'Outro cliente QA',1,1),(30,0,'Admin QA',1,1)):
                cur.execute('INSERT INTO USUARIO VALUES(?,?,?,?,?)',row)
            con.commit()
        finally:cur.close();con.close()
        with patch.object(marketplace_schema,'conectar_banco',side_effect=self.connect):marketplace_schema.migrar_marketplace();marketplace_schema.migrar_marketplace()
        with patch.object(termos_schema,'conectar_banco',side_effect=self.connect):termos_schema.migrar_termos_taxa();termos_schema.migrar_termos_taxa()
        self.addCleanup(patch.stopall);patch.object(mp,'conectar_banco',side_effect=self.connect).start();patch.object(mp,'registrar_log').start()
        self.client=main.app.test_client()
        with self.as_user(10,2):response=self.client.post('/gestao/marketplace/produtos',json=PRODUCT)
        self.assertEqual(response.status_code,201,response.get_json());self.pid=response.get_json()['produto']['id_produto']
    def connect(self):return firebirdsql.connect(**self.options)
    def drop(self):
        if self.db.exists():
            con=self.connect();con.drop_database();con.close()
    def as_user(self,id_,role):return patch.object(mp,'obter_usuario_logado',return_value={'id_usuario':id_,'tipo':role})
    def purchase(self,key='order_test_12345678'):
        self.assertEqual(self.client.put(f'/marketplace/carrinho/{self.pid}',json={'quantidade':2}).status_code,200)
        return self.client.post('/marketplace/pedidos',json={'id_barbearia':10,'retirada':True,'endereco':ADDRESS,'chave_idempotencia':key})
    def test_store_route_scope_overrides_query_and_filters_categories(self):
        with self.as_user(10,2):
            a2=self.client.post('/gestao/marketplace/produtos',json=PRODUCT|{'nome':'Shampoo A','categoria':'Shampoo'}).get_json()['produto']
            self.client.post('/gestao/marketplace/produtos',json=PRODUCT|{'nome':'Oculto A','categoria':'Oculta','ativo':False})
        with self.as_user(11,2):
            b=self.client.post('/gestao/marketplace/produtos',json=PRODUCT|{'nome':'Exclusivo B','categoria':'Somente B'}).get_json()['produto']
        for path in ('/marketplace/barbearias/10','/marketplace/barbearias/10?id_barbearia=11','/marketplace/barbearias/10?id_barbearia=invalido'):
            result=self.client.get(path);self.assertEqual(result.status_code,200,result.get_json());data=result.get_json()
            self.assertEqual(data['barbearia'],{'id_barbearia':10,'nome':'Salão QA'});self.assertEqual({p['id_produto'] for p in data['produtos']},{self.pid,a2['id_produto']});self.assertEqual(set(data['categorias']),{'Cabelo','Shampoo'})
        data=self.client.get('/marketplace/barbearias/11?id_barbearia=10').get_json();self.assertEqual({p['id_produto'] for p in data['produtos']},{b['id_produto']})
        data=self.client.get('/marketplace/barbearias/10?categoria=Somente%20B').get_json();self.assertEqual(data['produtos'],[])
        data=self.client.get('/marketplace/barbearias/10?busca=shampoo&ordem=preco_desc').get_json();self.assertEqual([p['id_produto'] for p in data['produtos']],[a2['id_produto']])
        general=self.client.get('/marketplace/produtos').get_json();self.assertEqual({p['id_barbearia'] for p in general['produtos']},{10,11})
    def test_store_empty_exists_but_blocked_invalid_and_customer_do_not(self):
        data=self.client.get('/marketplace/barbearias/11').get_json();self.assertEqual(data['barbearia']['id_barbearia'],11);self.assertEqual((data['produtos'],data['categorias'],data['total']),([],[],0))
        for id_ in (0,20,99999):self.assertEqual(self.client.get(f'/marketplace/barbearias/{id_}').status_code,404)
        con=self.connect();cur=con.cursor();cur.execute('UPDATE USUARIO SET ATIVO=0 WHERE ID_USUARIO=11');con.commit();cur.close();con.close()
        self.assertEqual(self.client.get('/marketplace/barbearias/11').status_code,404)
        con=self.connect();cur=con.cursor();cur.execute('UPDATE USUARIO SET ATIVO=1,EMAIL_CONFIRMADO=0 WHERE ID_USUARIO=11');con.commit();cur.close();con.close()
        self.assertEqual(self.client.get('/marketplace/barbearias/11').status_code,404)
    def test_owner_isolation_active_visibility_and_stock_ledger(self):
        with self.as_user(11,2):self.assertEqual(self.client.patch(f'/gestao/marketplace/produtos/{self.pid}/ativo',json={'ativo':False}).status_code,404)
        with self.as_user(10,2):
            self.assertEqual(self.client.patch(f'/gestao/marketplace/produtos/{self.pid}/ativo',json={'ativo':False}).status_code,200)
            stock=self.client.get(f'/gestao/marketplace/produtos/{self.pid}/estoque').get_json()['movimentacoes'];self.assertEqual(stock[0]['quantidade'],10)
        self.assertEqual(self.client.get('/marketplace/produtos').get_json()['total'],0)
    def test_checkout_snapshot_replay_cancel_exact_once(self):
        with self.as_user(20,1):
            response=self.purchase();self.assertEqual(response.status_code,201,response.get_json());order=response.get_json()['pedido'];id_=order['id_pedido'];self.assertEqual(order['total'],51.98)
            replay=self.client.post('/marketplace/pedidos',json={'id_barbearia':10,'retirada':True,'endereco':ADDRESS,'chave_idempotencia':'order_test_12345678'});self.assertEqual(replay.status_code,200)
            changed=self.client.post('/marketplace/pedidos',json={'id_barbearia':10,'retirada':True,'endereco':ADDRESS|{'numero':'11'},'chave_idempotencia':'order_test_12345678'});self.assertEqual(changed.status_code,409)
            for _ in range(2):self.assertEqual(self.client.post(f'/marketplace/pedidos/{id_}/cancelar',json={}).status_code,200)
        self.assertEqual(self.client.get(f'/marketplace/produtos/{self.pid}').get_json()['produto']['estoque'],10)
        with self.as_user(21,1):self.assertEqual(self.client.get(f'/marketplace/pedidos/{id_}').status_code,404)
    def test_cart_increment_and_client_isolation(self):
        with self.as_user(20,1):
            for _ in range(2):self.assertEqual(self.client.put(f'/marketplace/carrinho/{self.pid}',json={'quantidade':1,'adicionar':True}).status_code,200)
            self.assertEqual(self.client.get('/marketplace/carrinho').get_json()['itens'][0]['quantidade'],2)
        with self.as_user(21,1):self.assertEqual(self.client.get('/marketplace/carrinho').get_json()['itens'],[])
    def test_pending_pix_cannot_cancel_or_review_or_mark_delivered(self):
        with self.as_user(20,1):
            response=self.purchase();id_=response.get_json()['pedido']['id_pedido']
            con=self.connect();cur=con.cursor();cur.execute("UPDATE MP_PEDIDO SET PAGAMENTO_STATUS='pendente' WHERE ID_PEDIDO=?",(id_,));con.commit();cur.close();con.close()
            self.assertEqual(self.client.post(f'/marketplace/pedidos/{id_}/cancelar',json={}).status_code,409)
            self.assertEqual(self.client.put(f'/marketplace/produtos/{self.pid}/avaliacao',json={'nota':5}).status_code,403)
        with self.as_user(10,2):self.assertEqual(self.client.patch(f'/gestao/marketplace/pedidos/{id_}/status',json={'status':'entregue'}).status_code,409)
    def test_manual_shipping_owner_declaration_tracking_and_duplicate_protection(self):
        with self.as_user(20,1):
            response=self.purchase();id_=response.get_json()['pedido']['id_pedido']
            response2=self.purchase('order_second_123456');id2=response2.get_json()['pedido']['id_pedido']
        con=self.connect();cur=con.cursor();cur.execute("UPDATE MP_PEDIDO SET RETIRADA=0,PAGAMENTO_STATUS='pago',STATUS='pago' WHERE ID_PEDIDO IN (?,?)",(id_,id2));con.commit();cur.close();con.close()
        provider_id='6448a012-2a76-419f-b1fd-5b6728d384fd'
        payload={'id_envio':provider_id,'confirmar_vinculo':True}
        with self.as_user(11,2),patch.object(mp.melhor_envio,'chamar') as network:
            self.assertEqual(self.client.post(f'/gestao/marketplace/pedidos/{id_}/vincular-envio',json=payload).status_code,404);network.assert_not_called()
        with self.as_user(10,2),patch.object(mp.melhor_envio,'chamar',return_value={provider_id:{'status':'released','tracking':'QA001'}}) as network,patch.object(mp,'registrar_log') as audit:
            result=self.client.post(f'/gestao/marketplace/pedidos/{id_}/vincular-envio',json=payload)
            self.assertEqual(result.status_code,200,result.get_json());self.assertEqual(result.get_json()['pedido']['entrega']['status'],'vinculada');self.assertTrue(result.get_json()['pedido']['entrega']['declaracao_responsavel']);audit.assert_called_once()
            self.assertEqual(self.client.post(f'/gestao/marketplace/pedidos/{id2}/vincular-envio',json=payload).status_code,409);self.assertEqual(network.call_count,1)
        for entry in ({'status':'delivered','id':'wrong-id'},{'status':'made-up'},{'status':'delivered','error':True}):
            with self.as_user(10,2),patch.object(mp.melhor_envio,'chamar',return_value={provider_id:entry}):
                tracked=self.client.post(f'/gestao/marketplace/pedidos/{id_}/rastreio',json={});self.assertEqual(tracked.status_code,502)
                unchanged=self.client.get(f'/gestao/marketplace/pedidos/{id_}').get_json()['pedido'];self.assertEqual((unchanged['status'],unchanged['entrega']['status']),('pago','vinculada'))
        with self.as_user(10,2),patch.object(mp.melhor_envio,'chamar',return_value={provider_id:{'status':'posted','tracking':'QA001'}}):
            tracked=self.client.post(f'/gestao/marketplace/pedidos/{id_}/rastreio',json={});self.assertEqual(tracked.status_code,200);self.assertEqual(tracked.get_json()['pedido']['status'],'enviado')
        with self.as_user(10,2),patch.object(mp.melhor_envio,'chamar',return_value={provider_id:{'status':'delivered','tracking':'QA001'}}):
            tracked=self.client.post(f'/gestao/marketplace/pedidos/{id_}/rastreio',json={});self.assertEqual(tracked.status_code,200);self.assertEqual(tracked.get_json()['pedido']['status'],'entregue')
        with self.as_user(10,2),patch.object(mp.melhor_envio,'chamar',return_value={provider_id:{'status':'posted','tracking':'QA001'}}):
            tracked=self.client.post(f'/gestao/marketplace/pedidos/{id_}/rastreio',json={});self.assertEqual(tracked.get_json()['pedido']['status'],'entregue')
    def test_concurrent_cart_additions_do_not_lose_quantity(self):
        barrier=Barrier(2)
        def add():barrier.wait(timeout=10);return main.app.test_client().put(f'/marketplace/carrinho/{self.pid}',json={'quantidade':1,'adicionar':True}).status_code
        with self.as_user(20,1),ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(add);b=pool.submit(add);self.assertEqual([a.result(timeout=20),b.result(timeout=20)],[200,200])
        with self.as_user(20,1):self.assertEqual(self.client.get('/marketplace/carrinho').get_json()['itens'][0]['quantidade'],2)

    def fee_policy(self,payer):
        return patch.dict(main.app.config,{'TERMOS_RESPONSAVEL_NOME':'Operador QA',
            'TERMOS_RESPONSAVEL_DOCUMENTO':'QA','TERMOS_RESPONSAVEL_CONTATO':'qa@example.invalid',
            'TERMOS_RESPONSAVEL_ENDERECO':'QA','PLATAFORMA_TAXA_PAGADOR':payer})

    def accept_user(self,id_):
        con=self.connect();cur=con.cursor()
        try:
            with main.app.app_context():termos.registrar_aceite(cur,id_,termos.versao_atual(),True)
            con.commit()
        finally:cur.close();con.close()

    def test_fee_customer_preview_reprice_consent_retry_cancel_snapshot(self):
        with main.app.app_context(),self.fee_policy('cliente'),self.as_user(20,1):
            self.client.put(f'/marketplace/carrinho/{self.pid}',json={'quantidade':2})
            data={'id_barbearia':10,'retirada':True,'endereco':ADDRESS,'chave_idempotencia':'fee_order_test_12345678'}
            preview=self.client.post('/marketplace/pedidos/resumo',json=data).get_json()['resumo']
            self.assertEqual((preview['valor_base'],preview['taxa_valor'],preview['valor_total_cliente']),(51.98,.78,52.76))
            data['confirmacao_resumo']=preview['confirmacao_resumo']
            self.assertEqual(self.client.post('/marketplace/pedidos',json=data).status_code,428)
            self.accept_user(20)
            con=self.connect();cur=con.cursor();cur.execute('UPDATE MP_PRODUTO SET PRECO=30 WHERE ID_PRODUTO=?',(self.pid,));con.commit();cur.close();con.close()
            self.assertEqual(self.client.post('/marketplace/pedidos',json=data).status_code,409)
            preview=self.client.post('/marketplace/pedidos/resumo',json=data).get_json()['resumo'];data['confirmacao_resumo']=preview['confirmacao_resumo']
            created=self.client.post('/marketplace/pedidos',json=data);self.assertEqual(created.status_code,201,created.get_json())
            order=created.get_json()['pedido'];self.assertEqual(order['total'],60.9)
            self.assertEqual(order['resumo']['valor_base'],60)
            replay=self.client.post('/marketplace/pedidos',json=data);self.assertEqual(replay.status_code,200)
            cancelled=self.client.post(f"/marketplace/pedidos/{order['id_pedido']}/cancelar",json={}).get_json()['pedido']
            self.assertEqual(cancelled['resumo']['taxa_devida'],0)
            con=self.connect();cur=con.cursor();cur.execute('SELECT COUNT(*) FROM PLATAFORMA_TAXA');self.assertEqual(cur.fetchone()[0],1);cur.close();con.close()

    def test_fee_merchant_actual_owner_acceptance_no_customer_increment(self):
        with main.app.app_context(),self.fee_policy('barbearia'),self.as_user(20,1):
            self.client.put(f'/marketplace/carrinho/{self.pid}',json={'quantidade':2})
            self.accept_user(20)
            data={'id_barbearia':10,'retirada':True,'endereco':ADDRESS,'chave_idempotencia':'fee_merchant_12345678'}
            preview=self.client.post('/marketplace/pedidos/resumo',json=data).get_json()['resumo'];data['confirmacao_resumo']=preview['confirmacao_resumo']
            self.assertEqual(self.client.post('/marketplace/pedidos',json=data).status_code,428)
            self.accept_user(10)
            response=self.client.post('/marketplace/pedidos',json=data);self.assertEqual(response.status_code,201,response.get_json())
            order=response.get_json()['pedido'];self.assertEqual(order['total'],51.98)
            self.assertEqual(order['resumo']['valor_liquido_barbearia'],51.20)
            self.assertFalse(order['resumo']['repasse_automatico'])

if __name__=='__main__':unittest.main()
