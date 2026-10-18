"""Commercial rules and isolated Firebird checkout tests; providers never called."""
import os
os.environ['WAITLIST_WORKER']='false'
import unittest
from datetime import date,timedelta
from decimal import Decimal
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from flask import request
import main
import marketplace as mp
import marketplace_comercial as cm
from test_marketplace import PRODUCT,ADDRESS
import test_marketplace_firebird as fixture


class CommercialRules(unittest.TestCase):
    def test_margin_uses_revenue_not_cost_and_unknown_is_unknown(self):
        self.assertEqual(cm.margin(100,60),40)
        self.assertEqual(cm.margin(100,120),-20)
        self.assertIsNone(cm.margin(100,None))
        self.assertEqual(cm.margin(100,0),100)
        for invalid in (-1,True,'NaN'):
            with self.assertRaises(ValueError):cm.cost(invalid)

    def test_promotion_dates_and_variant_ratio_rounding(self):
        meta={'promocao_preco':Decimal('80'),'promocao_inicio':date(2026,1,1),'promocao_fim':date(2026,1,31)}
        self.assertEqual(cm.effective_price(100,meta,today=date(2026,1,1)),80)
        self.assertEqual(cm.effective_price(150,meta,100,date(2026,1,31)),120)
        self.assertEqual(cm.effective_price(150,meta,100,date(2026,2,1)),150)

    def test_coupon_positive_pix_total_and_percent_limits(self):
        self.assertEqual(cm.discount(10,'percentual',100),Decimal('9.99'))
        self.assertEqual(cm.discount(10,'fixo',1000),Decimal('9.99'))
        self.assertEqual(cm.discount('.01','fixo',2),0)
        self.assertEqual(cm.discount('25.99','percentual',10),Decimal('2.60'))
        for kind,value in (('percentual',101),('fixed',5),('fixo',-1),('fixo',True)):
            with self.assertRaises(ValueError):cm.discount(100,kind,value)

    def test_variation_identity_changes_quote_hash(self):
        item=dict(id_produto=1,id_barbearia=2,preco=10,quantidade=1,produto=dict(peso=1,largura=1,altura=1,comprimento=1))
        self.assertNotEqual(mp.cart_hash([item|{'id_variacao':1}]),mp.cart_hash([item|{'id_variacao':2}]))

    def test_csv_and_dates_reject_unsafe_input(self):
        for value in ('=SUM(A1)','  +cmd','@evil','-2','\tformula'):
            self.assertTrue(cm.csv_cell(value).startswith("'"))
        self.assertEqual(cm.csv_cell('Shampoo'),'Shampoo')
        for value in ('2026-2-1','2026-02-30','bad',True):
            with self.assertRaises(ValueError):cm.day(value)

    def test_discount_allocation_preserves_cents_on_many_small_lines(self):
        for totals,rebate in (([Decimal(1)]*5,Decimal('.03')),([Decimal('.01')]*100,Decimal('.49')),([Decimal('.01'),Decimal('10')],Decimal('9.99'))):
            allocation=cm.allocate_discount(totals,rebate)
            self.assertEqual(sum(allocation),rebate)
            self.assertTrue(all(0<=a<=total for a,total in zip(allocation,totals)))


@unittest.skipUnless(os.environ.get('RUN_FIREBIRD_MARKETPLACE_TESTS')=='1','isolated Firebird opt-in')
class CommercialFirebird(unittest.TestCase):
    setUp=fixture.MarketplaceFirebird.setUp
    connect=fixture.MarketplaceFirebird.connect
    drop=fixture.MarketplaceFirebird.drop
    as_user=fixture.MarketplaceFirebird.as_user
    fee_policy=fixture.MarketplaceFirebird.fee_policy
    accept_user=fixture.MarketplaceFirebird.accept_user

    def supplier(self,salon=10,**extra):
        with self.as_user(salon,2):
            response=self.client.post('/gestao/marketplace/fornecedores',json={'nome':'Fornecedor QA','email':'qa@example.invalid',**extra})
        self.assertEqual(response.status_code,201,response.get_json());return response.get_json()['fornecedor']

    def edit(self,**extra):
        with self.as_user(10,2):
            response=self.client.put(f'/gestao/marketplace/produtos/{self.pid}',json=PRODUCT|extra)
        self.assertEqual(response.status_code,200,response.get_json());return response.get_json()['produto']

    def variant(self,**extra):
        with self.as_user(10,2):
            response=self.client.post(f'/gestao/marketplace/produtos/{self.pid}/variacoes',json={'nome':'Azul 100ml','sku':'AZ100','cor':'Azul','volume':'100ml','preco':30,'custo_compra':10,'estoque':3,**extra})
        self.assertEqual(response.status_code,201,response.get_json());return response.get_json()['variacao']

    def coupon(self,**extra):
        today=date.today()
        with self.as_user(10,2):
            response=self.client.post('/gestao/marketplace/cupons',json={'codigo':'BEMVINDO','tipo':'percentual','valor':10,'inicio':today.isoformat(),'fim':(today+timedelta(days=3)).isoformat(),'limite_usos':1,**extra})
        self.assertEqual(response.status_code,201,response.get_json());return response.get_json()['cupom']

    def add(self,uid=20,vid=None,amount=1):
        with self.as_user(uid,1):
            response=self.client.put(f'/marketplace/carrinho/{self.pid}',json={'quantidade':amount,'id_variacao':vid})
        self.assertEqual(response.status_code,200,response.get_json())

    def purchase(self,uid=20,**extra):
        data={'id_barbearia':10,'retirada':True,'endereco':ADDRESS,'chave_idempotencia':'commercial_order_1234567',**extra}
        with self.as_user(uid,1):response=self.client.post('/marketplace/pedidos',json=data)
        return response

    def sql(self,query,params=()):
        con=self.connect();cur=con.cursor()
        try:
            cur.execute(query,params)
            result=cur.fetchall() if query.startswith('SELECT') else None
            con.commit();return result
        finally:cur.close();con.close()

    def test_supplier_isolation_private_cost_and_owner_margin(self):
        supplier=self.supplier();other=self.supplier(11)
        product=self.edit(id_fornecedor=supplier['id_fornecedor'],custo_compra=10)
        self.assertEqual(product['fornecedor'],'Fornecedor QA');self.assertEqual(product['margem_lucro_percentual'],61.52)
        public=self.client.get(f'/marketplace/produtos/{self.pid}').get_json()['produto']
        self.assertFalse({'custo_compra','id_fornecedor','fornecedor','margem_lucro_percentual'} & public.keys())
        with self.as_user(10,2):
            invalid=self.client.put(f'/gestao/marketplace/produtos/{self.pid}',json=PRODUCT|{'id_fornecedor':other['id_fornecedor']});self.assertEqual(invalid.status_code,400)
        with self.as_user(11,2):
            self.assertEqual(self.client.put('/gestao/marketplace/fornecedores/'+str(supplier['id_fornecedor']),json={'nome':'Hack'}).status_code,404)
        self.assertEqual(self.sql('SELECT ID_FORNECEDOR FROM MP_COMERCIAL WHERE ID_PRODUTO=?',(self.pid,))[0][0],supplier['id_fornecedor'])

    def test_wishlist_independent_from_favorite_and_customer(self):
        with self.as_user(20,1):
            self.assertEqual(self.client.put(f'/marketplace/lista-desejos/{self.pid}',json={'desejado':True}).status_code,200)
            self.assertEqual(len(self.client.get('/marketplace/lista-desejos').get_json()['produtos']),1)
            self.assertEqual(self.client.get('/marketplace/favoritos').get_json()['produtos'],[])
            self.assertTrue(self.client.get(f'/marketplace/produtos/{self.pid}').get_json()['produto']['desejado'])
        with self.as_user(21,1):self.assertEqual(self.client.get('/marketplace/lista-desejos').get_json()['produtos'],[])

    def test_inactive_supplier_can_be_preserved_but_not_newly_associated(self):
        current=self.supplier(nome='Fornecedor atual')
        other=self.supplier(nome='Outro fornecedor')
        self.edit(id_fornecedor=current['id_fornecedor'],custo_compra=10)
        with self.as_user(10,2):
            for supplier in (current,other):
                result=self.client.patch(f"/gestao/marketplace/fornecedores/{supplier['id_fornecedor']}/ativo",json={'ativo':False})
                self.assertEqual(result.status_code,200,result.get_json())
        edited=self.edit(id_fornecedor=current['id_fornecedor'],descricao='Descrição atualizada',preco=30,custo_compra=12)
        self.assertEqual((edited['id_fornecedor'],edited['descricao'],edited['preco_cadastro']), (current['id_fornecedor'],'Descrição atualizada',30))
        with self.as_user(10,2):
            changed=self.client.put(f'/gestao/marketplace/produtos/{self.pid}',json=PRODUCT|{'id_fornecedor':other['id_fornecedor']})
            created=self.client.post('/gestao/marketplace/produtos',json=PRODUCT|{'id_fornecedor':current['id_fornecedor']})
            self.assertEqual(changed.status_code,400,changed.get_json())
            self.assertEqual(created.status_code,400,created.get_json())
        self.assertEqual(self.sql('SELECT ID_FORNECEDOR FROM MP_COMERCIAL WHERE ID_PRODUTO=?',(self.pid,))[0][0],current['id_fornecedor'])
        self.assertEqual(self.sql('SELECT DESCRICAO,PRECO FROM MP_PRODUTO WHERE ID_PRODUTO=?',(self.pid,))[0],('Descrição atualizada',Decimal('30.00')))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM MP_PRODUTO')[0][0],1)

    def test_variant_cart_requires_selection_and_independent_stock(self):
        self.add();v1=self.variant();v2=self.variant(nome='Grande',sku='AZ200',preco=40,estoque=2)
        with self.as_user(20,1):
            cart=self.client.get('/marketplace/carrinho').get_json();self.assertFalse(cart['itens'][0]['disponivel'])
            self.assertEqual(self.client.put(f'/marketplace/carrinho/{self.pid}',json={'quantidade':1}).status_code,400)
            self.client.put(f'/marketplace/carrinho/{self.pid}',json={'quantidade':0})
        self.add(vid=v1['id_variacao'],amount=2);self.add(vid=v2['id_variacao'])
        with self.as_user(20,1):
            items=self.client.get('/marketplace/carrinho').get_json()['itens'];self.assertEqual(len(items),2)
            self.assertEqual(len({i['chave_item'] for i in items}),2)
            self.assertNotIn('custo_compra',items[0]['variacao']);self.assertNotIn('custo_compra',items[0]['produto'])
        response=self.purchase();self.assertEqual(response.status_code,201,response.get_json());order=response.get_json()['pedido']
        self.assertEqual(order['subtotal'],100);self.assertNotIn('custo_compra',order['itens'][0]['variacao'])
        self.assertEqual(self.sql('SELECT ESTOQUE FROM MP_PRODUTO WHERE ID_PRODUTO=?',(self.pid,))[0][0],10)
        self.assertEqual([r[0] for r in self.sql('SELECT ESTOQUE FROM MP_VARIACAO ORDER BY ID_VARIACAO')],[1,1])
        with self.as_user(20,1):
            for _ in range(2):self.assertEqual(self.client.post(f"/marketplace/pedidos/{order['id_pedido']}/cancelar").status_code,200)
        self.assertEqual([r[0] for r in self.sql('SELECT ESTOQUE FROM MP_VARIACAO ORDER BY ID_VARIACAO')],[3,2])

    def test_variation_stock_idempotency_and_history(self):
        v=self.variant();path=f"/gestao/marketplace/produtos/{self.pid}/variacoes/{v['id_variacao']}/estoque"
        payload={'quantidade':2,'observacao':'Compra QA','chave_idempotencia':'variation_stock_1234567'}
        with self.as_user(10,2):
            for _ in range(2):self.assertEqual(self.client.post(path,json=payload).get_json()['variacao']['estoque'],5)
            self.assertEqual(self.client.post(path,json=payload|{'quantidade':3}).status_code,409)
            self.assertEqual(len(self.client.get(path).get_json()['movimentacoes']),2)
            self.assertEqual(self.client.post(f'/gestao/marketplace/produtos/{self.pid}/estoque',json=payload).status_code,409)
        with self.as_user(11,2):self.assertEqual(self.client.get(path).status_code,404)

    def test_promotion_coupon_fee_snapshot_and_cancel_release(self):
        today=date.today();self.edit(preco=100,custo_compra=60,promocao_preco=80,promocao_inicio=today.isoformat(),promocao_fim=(today+timedelta(days=3)).isoformat(),lancamento_ate=today.isoformat())
        self.coupon();self.add()
        with main.app.app_context(),self.fee_policy('cliente'),self.as_user(20,1):
            self.accept_user(20)
            data={'id_barbearia':10,'retirada':True,'endereco':ADDRESS,'cupom':'bemvindo','chave_idempotencia':'promotion_coupon_1234567'}
            summary=self.client.post('/marketplace/pedidos/resumo',json=data).get_json()['resumo']
            self.assertEqual((summary['subtotal_original'],summary['desconto'],summary['valor_base'],summary['taxa_valor']), (80,8,72,1.08))
            data['confirmacao_resumo']=summary['confirmacao_resumo']
            response=self.client.post('/marketplace/pedidos',json=data);self.assertEqual(response.status_code,201,response.get_json());order=response.get_json()['pedido']
            self.assertEqual(order['total'],73.08);self.assertEqual(order['cupom'],'BEMVINDO')
            self.assertEqual(self.client.post('/marketplace/pedidos',json=data).status_code,200)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM MP_CUPOM_USO WHERE ATIVO=1')[0][0],1)
        self.add(uid=21)
        self.assertEqual(self.purchase(uid=21,cupom='BEMVINDO',chave_idempotencia='other_customer_1234567').status_code,409)
        self.edit(preco=120,custo_compra=90,promocao_preco=None)
        with self.as_user(20,1):
            for _ in range(2):self.client.post(f"/marketplace/pedidos/{order['id_pedido']}/cancelar")
        self.assertEqual(self.sql('SELECT COUNT(*) FROM MP_CUPOM_USO WHERE ATIVO=1')[0][0],0)
        self.assertEqual(self.sql('SELECT CUSTOS FROM MP_PEDIDO_COMERCIAL')[0][0],'["60.00"]')
        with self.as_user(20,1):
            historical=self.client.get(f"/marketplace/pedidos/{order['id_pedido']}").get_json()['pedido'];self.assertEqual(historical['itens'][0]['preco'],80)

    def test_coupon_cross_salon_dates_and_report_extreme_rejected(self):
        self.coupon();self.add()
        with self.as_user(11,2):self.assertEqual(self.client.get('/gestao/marketplace/cupons').get_json()['cupons'],[])
        with self.as_user(10,2):
            self.assertEqual(self.client.get('/gestao/marketplace/relatorios?inicio=9999-12-31&fim=9999-12-31').status_code,400)
            self.client.patch('/gestao/marketplace/cupons/1/ativo',json={'ativo':False})
        self.assertEqual(self.purchase(cupom='BEMVINDO').status_code,400)

    def test_paid_only_report_private_historical_cost_and_safe_csv(self):
        self.edit(nome='=CMD',preco=100,custo_compra=60);self.coupon(valor=10,tipo='fixo',limite_usos=10);self.add(amount=2)
        response=self.purchase(cupom='BEMVINDO');self.assertEqual(response.status_code,201,response.get_json());order=response.get_json()['pedido']
        with self.as_user(10,2):self.assertEqual(self.client.get('/gestao/marketplace/relatorios').get_json()['indicadores']['faturamento'],0)
        self.sql("UPDATE MP_PEDIDO SET PAGAMENTO_STATUS='pago',STATUS='pago' WHERE ID_PEDIDO=?",(order['id_pedido'],));self.edit(preco=150,custo_compra=100)
        with self.as_user(10,2):
            report=self.client.get('/gestao/marketplace/relatorios').get_json();i=report['indicadores']
            self.assertEqual((i['faturamento'],i['custo_produtos'],i['lucro_bruto'],i['descontos'],i['ticket_medio']),(190,120,70,10,190))
            self.assertEqual(report['produtos'][0]['faturamento'],190)
            csv=self.client.get('/gestao/marketplace/relatorios.csv').get_data(as_text=True);self.assertIn("'=CMD",csv)
        with self.as_user(11,2):self.assertEqual(self.client.get('/gestao/marketplace/relatorios').get_json()['indicadores']['faturamento'],0)

    def test_report_centavo_allocation_matches_paid_net_and_missing_cost(self):
        self.edit(preco=1)
        with self.as_user(10,2):
            others=[self.client.post('/gestao/marketplace/produtos',json=PRODUCT|{'preco':1,'nome':f'Item {i}'}).get_json()['produto']['id_produto'] for i in range(4)]
        with self.as_user(20,1):
            for pid in [self.pid,*others]:self.client.put(f'/marketplace/carrinho/{pid}',json={'quantidade':1})
        self.coupon(tipo='fixo',valor='.03');response=self.purchase(cupom='BEMVINDO');order=response.get_json()['pedido']
        self.sql("UPDATE MP_PEDIDO SET PAGAMENTO_STATUS='pago',STATUS='pago' WHERE ID_PEDIDO=?",(order['id_pedido'],))
        with self.as_user(10,2):report=self.client.get('/gestao/marketplace/relatorios').get_json()
        self.assertEqual(sum(Decimal(str(p['faturamento'])) for p in report['produtos']),Decimal('4.97'))
        self.assertEqual(report['indicadores']['faturamento'],4.97);self.assertIsNone(report['indicadores']['lucro_bruto']);self.assertTrue(report['indicadores']['custos_incompletos'])

    def test_concurrent_coupon_last_use_and_variant_last_unit(self):
        v=self.variant(estoque=1);self.coupon();self.add(uid=20,vid=v['id_variacao']);self.add(uid=21,vid=v['id_variacao'])
        barrier=Barrier(2)
        def buy(uid):
            barrier.wait(timeout=10)
            return main.app.test_client().post('/marketplace/pedidos',headers={'X-QA-User':str(uid)},json={'id_barbearia':10,'retirada':True,'endereco':ADDRESS,'cupom':'BEMVINDO','chave_idempotencia':f'concurrent_order_{uid}_1234'}).status_code
        with patch.object(mp,'obter_usuario_logado',side_effect=lambda:{'id_usuario':int(request.headers['X-QA-User']),'tipo':1}),ThreadPoolExecutor(max_workers=2) as pool:
            a,b=pool.submit(buy,20),pool.submit(buy,21);codes=sorted([a.result(timeout=30),b.result(timeout=30)])
        self.assertEqual(codes,[201,409]);self.assertEqual(self.sql('SELECT ESTOQUE FROM MP_VARIACAO')[0][0],0)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM MP_CUPOM_USO WHERE ATIVO=1')[0][0],1)


if __name__=='__main__':unittest.main()
