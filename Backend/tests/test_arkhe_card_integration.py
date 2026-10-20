"""Independent financial QA: real disposable Firebird locks/commits; fake card transport.

Opt in with RUN_FIREBIRD_CARD_TESTS=1. Prepare metadata-only MAIN/LOG backups in
ARKHE_CARD_QA_ROOT first. Never opens, modifies or copies application data rows.
"""
import os
os.environ['WAITLIST_WORKER']='false'
import contextlib
import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import struct
import subprocess
import tempfile
from threading import Event, Lock
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import firebirdsql
import jwt
import main
import pagamento
import marketplace
import arkhe
import arkhe_cartao as cards
from migrations import arkhe_cartao_schema

PAN='4000000000000082'
CVV='082'
CARD={'numero_cartao':PAN,'validade':'09/2031','cvv':CVV,'tipo':'CREDITO','parcelas':1}
QA_ROOT=Path(os.environ.get('ARKHE_CARD_QA_ROOT',r'C:\Users\mathe\Documents\Backups-Cortae\arkhe-card-20261019')).resolve()
GBAK=Path(os.environ.get('ARKHE_TEST_GBAK', str(Path(os.environ.get('CORTAE_FIREBIRD_HOME') or
    str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Cortae'/'runtimes'/'Firebird-4.0.4.3010-Win32'))/'gbak.exe')))


class FakeResponse:
    def __init__(self,data,status=201):
        self.status=status
        self.raw=data if isinstance(data,bytes) else json.dumps(data).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,limit=None):return self.raw if limit is None else self.raw[:limit]


class FailCommitConnection:
    """Fail before the second commit; keep the first reservation truly durable."""
    def __init__(self,connection,fail_at=2,after_commit=False):
        self.real=connection;self.commits=0;self.fail_at=fail_at;self.after_commit=after_commit
    def __getattr__(self,name):return getattr(self.real,name)
    def commit(self):
        self.commits+=1
        if self.commits==self.fail_at:
            if self.after_commit:self.real.commit()
            raise RuntimeError('synthetic local commit failure')
        return self.real.commit()


@unittest.skipUnless(os.environ.get('RUN_FIREBIRD_CARD_TESTS')=='1','isolated card Firebird opt-in')
class CardFirebirdIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if struct.calcsize('P')*8!=32:raise AssertionError('QA must run in Python 32 bits')
        if not GBAK.is_file() or not all((QA_ROOT/f'SCHEMA-{label}.fbk').is_file() for label in ('MAIN','LOG')):
            raise unittest.SkipTest('Prepare external metadata-only schema backups before opt-in')
        project=Path(__file__).resolve().parents[2]
        if QA_ROOT.is_relative_to(project):raise AssertionError('QA files must stay outside project')

    def setUp(self):
        self.directory=Path(tempfile.mkdtemp(prefix='card-case-',dir=QA_ROOT)).resolve()
        self.options={}
        for label,prefix in (('MAIN','DB_'),('LOG','LOG_DB_')):
            path=self.directory/f'{label}.FDB'
            opts=dict(host='127.0.0.1',port=int(main.app.config[prefix+'PORT']),
                user=main.app.config[prefix+'USER'],password=main.app.config[prefix+'PASSWORD'],
                database=str(path),charset='UTF8')
            restored=subprocess.run([str(GBAK),'-c','-user',opts['user'],'-password',opts['password'],
                str(QA_ROOT/f'SCHEMA-{label}.fbk'),f"127.0.0.1/{opts['port']}:{path}"],capture_output=True)
            self.assertEqual(restored.returncode,0,'Disposable metadata restore failed; credentials withheld')
            self.options[label]=opts
        self.addCleanup(self.drop_databases)
        settings={'SECRET_KEY':'synthetic-card-qa-key','ARKHE_BASE_URL':'https://arkhe-qa.example.invalid',
            'WAITLIST_WORKER':False,'LOG_OBRIGATORIO':True,'OPENAI_API_KEY':'','IMAGE_STORAGE_PROVIDER':'local'}
        for label,prefix in (('MAIN','DB_'),('LOG','LOG_DB_')):
            for suffix in ('HOST','PORT','NAME','USER','PASSWORD'):
                settings[prefix+suffix]=self.options[label][{'HOST':'host','PORT':'port','NAME':'database','USER':'user','PASSWORD':'password'}[suffix]]
        config_patch=patch.dict(main.app.config,settings);config_patch.start();self.addCleanup(config_patch.stop)
        for target in ('pagamento.urlopen','arkhe.urllib.request.urlopen','smtplib.SMTP','smtplib.SMTP_SSL','requests.sessions.Session.request'):
            blocker=patch(target,side_effect=AssertionError('QA forbids real external provider, email or uploads'))
            blocker.start();self.addCleanup(blocker.stop)
        self.client=main.app.test_client();self.next_id=1000;self.provider_id=100000;self.provider_lock=Lock()
        self.assertEqual(self.sql('SELECT COUNT(*) FROM USUARIO')[0][0],0,'Metadata fixture must have no source data')
        with main.app.app_context():arkhe_cartao_schema.migrar_cartao();arkhe_cartao_schema.migrar_cartao()
        for uid,role in ((10,2),(11,2),(20,1),(21,1)):
            self.sql("INSERT INTO USUARIO(ID_USUARIO,NOME,EMAIL,TIPO,SENHA_HASH,ATIVO,EMAIL_CONFIRMADO,TENTATIVA) VALUES(?,?,?,?,'synthetic-not-a-real-login',1,1,0)",
                (uid,f'Card QA {uid}',f'card-qa-{uid}@example.invalid',role),True)
        for sid in (10,11):
            self.sql('INSERT INTO PERSONALIZACAO(ID_PERSONALIZACAO,ID_USUARIO,ARKHE_CLIENT_ID,ARKHE_CLIENT_SECRET) VALUES(?,?,?,?)',
                (sid,sid,f'qa-client-{sid}',f'qa-secret-{sid}'),True)
        self.sql("INSERT INTO FUNCIONARIO(ID_FUNCIONARIO,NOME,ID_BARBEARIA,ATIVO) VALUES(100,'Card QA',10,1)",commit=True)
        self.sql("INSERT INTO FUNCIONARIO(ID_FUNCIONARIO,NOME,ID_BARBEARIA,ATIVO) VALUES(101,'Other Card QA',11,1)",commit=True)

    def connect(self,log=False):return firebirdsql.connect(**self.options['LOG' if log else 'MAIN'])
    def sql(self,query,args=(),commit=False,log=False):
        con=self.connect(log);cur=con.cursor()
        try:
            cur.execute(query,args);rows=cur.fetchall() if cur.description else []
            if commit:con.commit()
            return rows
        finally:cur.close();con.close()
    def drop_databases(self):
        self.assertTrue(self.directory.is_relative_to(QA_ROOT))
        for opts in self.options.values():
            con=firebirdsql.connect(**opts)
            try:con.drop_database()
            finally:con.close()
        self.directory.rmdir()
    def headers(self,uid=20):
        token=jwt.encode({'id_usuario':uid,'tipo':2 if uid in (10,11) else 1,
            'exp':datetime.now(UTC)+timedelta(hours=1)},main.app.config['SECRET_KEY'],algorithm='HS256')
        return {'Authorization':'Bearer '+token}
    def new_target(self,kind='agendamento',total='100.00',salon=10):
        self.next_id+=1;id_=self.next_id
        if kind=='agendamento':
            start=datetime(2030,10,19,10,0)
            self.sql('''INSERT INTO AGENDAMENTO(ID_AGENDAMENTO,ID_USUARIO,ID_BARBEARIA,ID_FUNCIONARIO,INICIO_EM,FIM_EM,
                SERVICOS_JSON,SERVICOS_SNAPSHOT,STATUS,VALOR_TOTAL,DURACAO_MINUTOS,ESCOLHA_CORTE)
                VALUES(?,20,?,?,?,?,'[]','[]','agendado',?,30,'na_hora')''',(id_,salon,100 if salon==10 else 101,start,start+timedelta(minutes=30),Decimal(total)),True)
        else:
            self.sql('''INSERT INTO MP_PEDIDO(ID_PEDIDO,ID_USUARIO,ID_BARBEARIA,CHAVE,HASH_PEDIDO,STATUS,SUBTOTAL,FRETE,TOTAL,RETIRADA,ENDERECO,ITENS)
                VALUES(?,20,?,?,?,'aguardando_pagamento',?,0,?,1,'{}','[]')''',
                (id_,salon,f'qa-card-{id_}','0'*64,Decimal(total),Decimal(total)),True)
        return kind,id_
    def post(self,target,data=None,uid=20,client=None):
        kind,id_=target
        path='/pagamentos/cartao' if kind=='agendamento' else f'/marketplace/pedidos/{id_}/cartao'
        payload=dict(CARD if data is None else data)
        if kind=='agendamento':payload['id_agendamento']=id_
        return (client or self.client).post(path,headers=self.headers(uid),json=payload)
    def attempt(self,target):
        rows=self.sql('SELECT ESTADO,VALOR,TIPO,PARCELAS,RESULTADO FROM PAGAMENTO_CARTAO WHERE TIPO_ALVO=? AND ID_ALVO=?',target)
        return rows[0] if rows else None
    def approval(self,request,**kwargs):
        payload=json.loads(request.data)
        with self.provider_lock:
            self.provider_id+=1;identifier=self.provider_id
        gross=Decimal(str(payload['valor']));net=(gross*(Decimal('.95') if payload['tipo']=='CREDITO' else 1)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        return FakeResponse({'aprovado':True,'id_compra':identifier,'id_movimentacao':identifier+500000,
            'valor':float(gross),'valor_recebido':float(net),'taxa':float(gross-net),
            'tipo':payload['tipo'],'parcelas':payload['parcelas'],'final_cartao':payload['numero_cartao'][-4:],
            'data_compra':'2026-10-19T14:00:00','numero_cartao':PAN,'cvv':CVV,
            'private_debug':'must not be persisted or returned'})
    def assert_safe(self,response):
        text=response.get_data(as_text=True)
        self.assertNotIn(PAN,text);self.assertNotIn('"'+CVV+'"',text);self.assertNotIn('must not be persisted',text)
        for query,log in (("SELECT RESULTADO FROM PAGAMENTO_CARTAO",False),
                          ("SELECT DESCRICAO FROM FINANCEIRO",False),
                          ("SELECT PAGAMENTO_DADOS FROM MP_PEDIDO",False),
                          ("SELECT VALOR_ANTES,VALOR_DEPOIS FROM LOG_ALTERACAO",True)):
            for row in self.sql(query,log=log):
                for value in row:
                    if value is not None:
                        self.assertNotIn(PAN,str(value));self.assertNotIn('"'+CVV+'"',str(value));self.assertNotIn('must not be persisted',str(value))

    def test_credit_one_and_fifteen_installments_gross_not_merchant_net(self):
        for kind in ('agendamento','pedido'):
            for count in (1,15):
                with self.subTest(kind=kind,parcelas=count):
                    target=self.new_target(kind)
                    with patch.object(cards,'urlopen',side_effect=self.approval) as provider:
                        response=self.post(target,CARD|{'parcelas':count,'valor':0.01})
                    self.assertEqual(response.status_code,201,response.get_json());self.assertEqual(provider.call_count,1)
                    request=provider.call_args.args[0];sent=json.loads(request.data)
                    self.assertTrue(request.full_url.endswith('/api/v1/vendas/cartao'))
                    self.assertEqual((sent['valor'],sent['parcelas'],sent['cvv']),(100.0,count,CVV))
                    self.assertEqual(response.get_json()['cartao_estado'],'aprovado')
                    saved=json.loads(self.attempt(target)[4]);self.assertEqual((saved['valor'],saved['valor_recebido'],saved['taxa']),(100,95,5))
                    if kind=='agendamento':
                        values=self.sql("SELECT VALOR FROM FINANCEIRO WHERE DESCRICAO CONTAINING ? AND TIPO='cartao_pago'",(f'ag#{target[1]}|',))
                        self.assertEqual(values,[(Decimal('100.00'),)])
                    else:self.assertEqual(self.sql('SELECT TOTAL,PAGAMENTO_STATUS FROM MP_PEDIDO WHERE ID_PEDIDO=?',(target[1],)),[(Decimal('100.00'),'pago')])
                    self.assert_safe(response)

    def test_debit_one_installment_full_receipt_and_replay_never_resends(self):
        for kind in ('agendamento','pedido'):
            target=self.new_target(kind)
            with patch.object(cards,'urlopen',side_effect=self.approval) as provider:
                response=self.post(target,CARD|{'tipo':'DEBITO'});again=self.post(target,CARD|{'tipo':'DEBITO'})
            self.assertEqual(response.status_code,201,response.get_json());self.assertEqual(again.status_code,200,again.get_json())
            self.assertEqual(provider.call_count,1)
            saved=json.loads(self.attempt(target)[4]);self.assertEqual((saved['valor'],saved['valor_recebido'],saved['taxa']),(100,100,0))

    def test_invalid_card_fields_installments_and_pin_never_reach_provider(self):
        invalid=({'numero_cartao':'4'*15},{'numero_cartao':'4'*17},{'numero_cartao':4000000000000082},
            {'numero_cartao':'x'*16},{'cvv':'82'},{'cvv':82},{'cvv':True},{'validade':'13/2031'},
            {'validade':'09/2025'},{'validade':'09/31'},{'parcelas':True},{'parcelas':1.0},
            {'parcelas':0},{'parcelas':16},{'tipo':'DEBITO','parcelas':2},{'pin':'never-send'})
        for kind in ('agendamento','pedido'):
            for extra in invalid:
                with self.subTest(kind=kind,invalid=list(extra)):
                    target=self.new_target(kind)
                    with patch.object(cards,'urlopen') as provider:response=self.post(target,CARD|extra)
                    self.assertEqual(response.status_code,400,response.get_json());provider.assert_not_called()
                    self.assertIsNone(self.attempt(target));self.assert_safe(response)

    def test_minimum_one_cent_per_installment(self):
        for kind in ('agendamento','pedido'):
            with patch.object(cards,'urlopen',side_effect=self.approval) as provider:
                bad=self.post(self.new_target(kind,'0.14'),CARD|{'parcelas':15})
                good=self.post(self.new_target(kind,'0.15'),CARD|{'parcelas':15})
            self.assertEqual(bad.status_code,400,bad.get_json());self.assertEqual(good.status_code,201,good.get_json())
            self.assertEqual(provider.call_count,1)

    def test_merchant_credentials_are_selected_per_target_not_caller(self):
        for kind in ('agendamento','pedido'):
            for salon in (10,11):
                target=self.new_target(kind,salon=salon)
                with patch.object(cards,'urlopen',side_effect=self.approval) as provider:response=self.post(target)
                self.assertEqual(response.status_code,201,response.get_json())
                headers={key.lower():value for key,value in provider.call_args.args[0].headers.items()}
                self.assertEqual(headers['x-client-id'],f'qa-client-{salon}');self.assertEqual(headers['x-client-secret'],f'qa-secret-{salon}')

    def test_reservation_is_visible_to_independent_connection_before_post(self):
        for kind in ('agendamento','pedido'):
            target=self.new_target(kind)
            def provider(request,**kwargs):
                row=self.attempt(target)
                self.assertIsNotNone(row);self.assertEqual(row[0],'processando')
                self.assertEqual(row[1],Decimal('100.00'))
                return self.approval(request,**kwargs)
            with patch.object(cards,'urlopen',side_effect=provider):response=self.post(target)
            self.assertEqual(response.status_code,201,response.get_json())

    def test_concurrent_duplicate_returns_before_provider_finishes_and_posts_once(self):
        for kind in ('agendamento','pedido'):
            target=self.new_target(kind);started=Event();release=Event()
            def provider(request,**kwargs):
                self.assertEqual(self.attempt(target)[0],'processando');started.set()
                self.assertTrue(release.wait(10),'QA provider wait expired')
                return self.approval(request,**kwargs)
            with patch.object(cards,'urlopen',side_effect=provider) as network,ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(self.post,target,None,20,main.app.test_client())
                try:
                    self.assertTrue(started.wait(5),'No durable reservation reached provider')
                    second=pool.submit(self.post,target,None,20,main.app.test_client())
                    blocked=second.result(timeout=5)
                    self.assertEqual(blocked.status_code,409,blocked.get_json())
                finally:release.set()
                approved=first.result(timeout=10)
            self.assertEqual(approved.status_code,201,approved.get_json());self.assertEqual(network.call_count,1)

    def assert_other_methods_blocked(self,target):
        kind,id_=target
        paths=[('/pagamentos/pix',{'id_agendamento':id_},20),('/pagamentos/na-hora',{'id_agendamento':id_},20),
            ('/pagamentos/na-hora',{'id_agendamento':id_},10),('/pagamentos/boleto',{'id_agendamento':id_},20),
            (f'/gestao/agendamentos/{id_}/recebimentos',{'chave_idempotencia':f'qa-other-{id_}',
                'pagamentos':[{'forma':'dinheiro','valor':100}]},10)] if kind=='agendamento' else [
            (f'/marketplace/pedidos/{id_}/pix',{},20)]
        with patch.object(pagamento,'_chamar') as legacy,patch.object(arkhe,'_chamar_arkhe') as pix:
            for path,body,uid in paths:
                response=self.client.post(path,headers=self.headers(uid),json=body)
                self.assertEqual(response.status_code,409,(path,response.get_json()))
            legacy.assert_not_called();pix.assert_not_called()

    def test_uncertain_timeout_409_and_malformed_block_all_other_methods(self):
        for kind in ('agendamento','pedido'):
            for failure in ('timeout','409','malformed','wrong-net'):
                with self.subTest(kind=kind,failure=failure):
                    target=self.new_target(kind)
                    def provider(request,**kwargs):
                        if failure=='timeout':raise TimeoutError('must not be persisted '+PAN+' '+CVV)
                        if failure=='409':raise HTTPError(request.full_url,409,'provider secret body',{},io.BytesIO((PAN+' '+CVV).encode()))
                        if failure=='malformed':return FakeResponse(b'not-json '+PAN.encode()+b' '+CVV.encode())
                        response=self.approval(request)
                        data=json.loads(response.raw)
                        if failure=='wrong-net':data['valor_recebido']=100
                        return FakeResponse(data)
                    output=io.StringIO()
                    with patch.object(cards,'urlopen',side_effect=provider) as network,contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
                        response=self.post(target);again=self.post(target)
                    self.assertGreaterEqual(response.status_code,400,response.get_json());self.assertEqual(again.status_code,409,again.get_json())
                    self.assertEqual(network.call_count,1);self.assertIn(self.attempt(target)[0],('incerto','processando'))
                    self.assertNotIn(PAN,output.getvalue());self.assertNotIn(CVV,output.getvalue())
                    self.assert_safe(response);self.assert_safe(again);self.assert_other_methods_blocked(target)

    def test_deterministic_http_refusal_allows_only_explicit_new_attempt(self):
        for kind in ('agendamento','pedido'):
            target=self.new_target(kind)
            with patch.object(cards,'urlopen',side_effect=HTTPError('https://arkhe-qa.example.invalid',400,'refused',{},io.BytesIO((PAN+' '+CVV).encode()))) as network:
                refused=self.post(target)
            self.assertEqual(refused.status_code,400,refused.get_json());self.assertEqual(network.call_count,1)
            self.assertEqual(self.attempt(target)[0],'recusado');self.assert_safe(refused)
            with patch.object(cards,'urlopen',side_effect=self.approval) as network:approved=self.post(target)
            self.assertEqual(approved.status_code,201,approved.get_json());self.assertEqual(network.call_count,1)

    def test_explicit_false_approval_is_refusal_and_can_be_retried_explicitly(self):
        for kind in ('agendamento','pedido'):
            target=self.new_target(kind)
            with patch.object(cards,'urlopen',return_value=FakeResponse({'aprovado':False,'mensagem':'must not be persisted '+PAN+' '+CVV})) as provider:
                refused=self.post(target)
            self.assertEqual(refused.status_code,400,refused.get_json());self.assertEqual(provider.call_count,1)
            self.assertEqual(self.attempt(target)[0],'recusado');self.assert_safe(refused)
            with patch.object(cards,'urlopen',side_effect=self.approval) as provider:approved=self.post(target)
            self.assertEqual(approved.status_code,201,approved.get_json());self.assertEqual(provider.call_count,1)

    def test_local_commit_failure_after_external_approval_never_resends(self):
        for kind,module in (('agendamento',pagamento),('pedido',marketplace)):
            target=self.new_target(kind)
            with patch.object(module,'conectar_banco',side_effect=lambda:FailCommitConnection(self.connect())),patch.object(cards,'urlopen',side_effect=self.approval) as network:
                response=self.post(target)
            self.assertGreaterEqual(response.status_code,400,response.get_json());self.assertEqual(network.call_count,1)
            self.assertIn(self.attempt(target)[0],('incerto','processando'));self.assert_safe(response)
            with patch.object(cards,'urlopen') as network:again=self.post(target)
            self.assertEqual(again.status_code,409,again.get_json());network.assert_not_called()
            self.assert_other_methods_blocked(target)

    def test_failed_reservation_commit_never_calls_provider(self):
        for kind,module in (('agendamento',pagamento),('pedido',marketplace)):
            target=self.new_target(kind)
            with patch.object(module,'conectar_banco',side_effect=lambda:FailCommitConnection(self.connect(),fail_at=1)),patch.object(cards,'urlopen') as network:
                response=self.post(target)
            self.assertGreaterEqual(response.status_code,400,response.get_json());network.assert_not_called()

    def test_lost_final_commit_acknowledgement_never_creates_second_charge(self):
        for kind,module in (('agendamento',pagamento),('pedido',marketplace)):
            target=self.new_target(kind)
            with patch.object(module,'conectar_banco',side_effect=lambda:FailCommitConnection(self.connect(),after_commit=True)),patch.object(cards,'urlopen',side_effect=self.approval) as network:
                response=self.post(target)
            self.assertGreaterEqual(response.status_code,400,response.get_json());self.assertEqual(network.call_count,1)
            with patch.object(cards,'urlopen') as network:again=self.post(target)
            self.assertEqual(again.status_code,409,again.get_json());network.assert_not_called()
            self.assert_other_methods_blocked(target);self.assert_safe(response)

    def test_status_queries_are_local_and_do_not_expose_pan_or_cvv(self):
        for kind in ('agendamento','pedido'):
            target=self.new_target(kind)
            with patch.object(cards,'urlopen',side_effect=self.approval):self.assertEqual(self.post(target).status_code,201)
            path=f'/pagamentos/agendamento/{target[1]}' if kind=='agendamento' else f'/marketplace/pedidos/{target[1]}/pagamento'
            with patch.object(cards,'urlopen') as network,patch.object(pagamento,'_chamar') as legacy,patch.object(arkhe,'_chamar_arkhe') as pix:
                response=self.client.get(path,headers=self.headers())
            self.assertEqual(response.status_code,200,response.get_json());network.assert_not_called();legacy.assert_not_called();pix.assert_not_called();self.assert_safe(response)
            data=response.get_json()
            if kind=='agendamento':
                self.assertEqual(data['cartao_estado'],'aprovado');self.assertEqual(data['cartao_resultado']['valor_recebido'],95)
                self.assertEqual(data['cartao_resultado']['metodo'],'cartao');self.assertEqual(data['cartao_resultado']['status'],1)
                saved=self.attempt(target)[4]
                self.sql("UPDATE PAGAMENTO_CARTAO SET ESTADO='incerto' WHERE TIPO_ALVO=? AND ID_ALVO=?",target,True)
                with patch.object(cards,'urlopen') as network,patch.object(pagamento,'_chamar') as legacy,patch.object(arkhe,'_chamar_arkhe') as pix:
                    uncertain=self.client.get(path,headers=self.headers())
                self.assertEqual(uncertain.status_code,200,uncertain.get_json())
                self.assertEqual(uncertain.get_json()['cartao_estado'],'incerto')
                self.assertIsNone(uncertain.get_json()['cartao_resultado'])
                self.assertEqual(self.attempt(target)[4],saved,'Read-only status must preserve safe reconciliation metadata')
                network.assert_not_called();legacy.assert_not_called();pix.assert_not_called();self.assert_safe(uncertain)
            else:self.assertEqual(data['pagamento']['metodo'],'cartao')

    def test_missing_migration_fails_without_route_ddl_or_post(self):
        target=self.new_target();self.sql('DROP TABLE PAGAMENTO_CARTAO',commit=True)
        with patch.object(cards,'urlopen') as network,patch.object(arkhe_cartao_schema,'migrar_cartao',side_effect=AssertionError('DDL must be manual')):
            response=self.post(target)
        self.assertEqual(response.status_code,503,response.get_json());network.assert_not_called()
        self.assertEqual(self.sql("SELECT COUNT(*) FROM RDB$RELATIONS WHERE RDB$RELATION_NAME='PAGAMENTO_CARTAO'"),[(0,)])

    def test_foreign_customer_cannot_charge_any_target(self):
        for kind in ('agendamento','pedido'):
            target=self.new_target(kind)
            with patch.object(cards,'urlopen') as network:response=self.post(target,uid=21)
            self.assertIn(response.status_code,(400,403,404));network.assert_not_called();self.assertIsNone(self.attempt(target))

    def test_duplicate_provider_ids_cannot_credit_two_orders_for_same_merchant(self):
        first=self.new_target('agendamento',salon=10)
        duplicate=self.new_target('pedido',salon=10)
        independent=self.new_target('agendamento',salon=11)
        def provider(request,**kwargs):
            data=json.loads(self.approval(request).raw)
            data['id_compra']=700001;data['id_movimentacao']=800001
            return FakeResponse(data)
        with patch.object(cards,'urlopen',side_effect=provider) as network:
            accepted=self.post(first);blocked=self.post(duplicate);other_merchant=self.post(independent)
        self.assertEqual(accepted.status_code,201,accepted.get_json())
        self.assertGreaterEqual(blocked.status_code,400,blocked.get_json())
        self.assertIn(self.attempt(duplicate)[0],('incerto','processando'))
        self.assertEqual(other_merchant.status_code,201,other_merchant.get_json())
        self.assertEqual(network.call_count,3)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM PAGAMENTO_CARTAO WHERE ID_BARBEARIA=10 AND ESTADO='aprovado'"),[(1,)])
        self.assertEqual(self.sql('SELECT PAGAMENTO_STATUS FROM MP_PEDIDO WHERE ID_PEDIDO=?',(duplicate[1],)),[('incerto',)])


@unittest.skipUnless(os.name=='nt' and os.environ.get('RUN_FIREBIRD_CARD_TESTS')=='1'
    and os.environ.get('ARKHE_CARD_ODS13_RAW'),'explicit detached legacy ODS 13.0 archive required')
class LegacyODSCardMigration(unittest.TestCase):
    def test_cold_raw_ods130_copy_migration_nullable_uniqueness_and_idempotency(self):
        source=Path(os.environ['ARKHE_CARD_ODS13_RAW']).resolve()
        project=Path(__file__).resolve().parents[2]
        self.assertFalse(source.is_relative_to(project),'Never copy an active project database')
        self.assertFalse(source.is_symlink())
        directory=Path(tempfile.mkdtemp(prefix='legacy-ods130-',dir=QA_ROOT)).resolve()
        target=directory/'LEGACY-PRIVATE-QA.FDB'
        source_ps=str(source).replace("'","''");target_ps=str(target).replace("'","''")
        # A detached archive must permit an exclusive read. Never attach it to
        # Firebird: even a read transaction can change database header metadata.
        script=("$ErrorActionPreference='Stop';"
            f"$src=[IO.File]::Open('{source_ps}',[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None);"
            "try { "
            f"$dst=[IO.File]::Open('{target_ps}',[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);"
            "try {$src.CopyTo($dst)} finally {$dst.Dispose()};"
            "$src.Position=0;$hash=[Security.Cryptography.SHA256]::Create();"
            "try {[BitConverter]::ToString($hash.ComputeHash($src)).Replace('-','').ToLowerInvariant()} finally {$hash.Dispose()}"
            "} finally {$src.Dispose()}")
        copied=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=30)
        self.assertEqual(copied.returncode,0,'Detached archive must allow FileShare.None; no active file may be copied')
        source_hash=copied.stdout.strip()
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),source_hash)
        options=dict(host='127.0.0.1',port=main.app.config['DB_PORT'],database=str(target),
            user=main.app.config['DB_USER'],password=main.app.config['DB_PASSWORD'],charset='UTF8')
        def connect():return firebirdsql.connect(**options)
        def cleanup():
            self.assertTrue(target.is_relative_to(QA_ROOT))
            con=connect()
            try:con.drop_database()
            finally:con.close()
            directory.rmdir()
        self.addCleanup(cleanup)
        def sql(query,args=(),commit=False):
            con=connect();cur=con.cursor()
            try:
                cur.execute(query,args);rows=cur.fetchall() if cur.description else []
                if commit:con.commit()
                return rows
            finally:cur.close();con.close()
        self.assertEqual(sql('SELECT MON$ODS_MAJOR,MON$ODS_MINOR FROM MON$DATABASE'),[(13,0)])
        self.assertEqual(sql("SELECT COUNT(*) FROM RDB$RELATION_FIELDS WHERE RDB$RELATION_NAME='RDB$INDICES' AND RDB$FIELD_NAME='RDB$CONDITION_SOURCE'"),[(0,)])
        with patch.object(arkhe_cartao_schema,'conectar_banco',side_effect=connect):arkhe_cartao_schema.migrar_cartao()
        indices=sql("SELECT TRIM(RDB$INDEX_NAME),RDB$INDEX_ID,RDB$EXPRESSION_SOURCE FROM RDB$INDICES WHERE RDB$INDEX_NAME IN ('UQ_CARTAO_COMPRA','UQ_CARTAO_MOVIMENTACAO') ORDER BY RDB$INDEX_NAME")
        self.assertEqual(len(indices),2);self.assertTrue(all(row[2] and 'CASE' in str(row[2]).upper() for row in indices))
        statements=[]
        class TraceCursor:
            def __init__(self,cur):self.real=cur
            def __getattr__(self,key):return getattr(self.real,key)
            def execute(self,query,*args):statements.append(query.strip().upper());return self.real.execute(query,*args)
        class TraceConnection:
            def __init__(self):self.real=connect()
            def __getattr__(self,key):return getattr(self.real,key)
            def cursor(self):return TraceCursor(self.real.cursor())
        with patch.object(arkhe_cartao_schema,'conectar_banco',side_effect=TraceConnection):arkhe_cartao_schema.migrar_cartao()
        self.assertFalse(any(query.startswith(('CREATE ','DROP ','ALTER ')) for query in statements),'Reapplying migration must not rebuild correct indexes')
        self.assertFalse(any('CONDITION_SOURCE' in query for query in statements))
        self.assertEqual(sql("SELECT TRIM(RDB$INDEX_NAME),RDB$INDEX_ID,RDB$EXPRESSION_SOURCE FROM RDB$INDICES WHERE RDB$INDEX_NAME IN ('UQ_CARTAO_COMPRA','UQ_CARTAO_MOVIMENTACAO') ORDER BY RDB$INDEX_NAME"),indices)
        for uid,role in ((2000000001,2),(2000000002,1),(2000000003,2)):
            sql("INSERT INTO USUARIO(ID_USUARIO,NOME,EMAIL,TIPO,SENHA_HASH,ATIVO,EMAIL_CONFIRMADO,TENTATIVA) VALUES(?, 'Legacy ODS QA',?,?,'synthetic-not-login',1,1,0)",
                (uid,f'legacy-ods13-{uid}@example.invalid',role),True)
        def insert(kind,id_,salon=2000000001,purchase=None,movement=None):
            sql("INSERT INTO PAGAMENTO_CARTAO(TIPO_ALVO,ID_ALVO,ID_USUARIO,ID_BARBEARIA,ESTADO,VALOR,TIPO,PARCELAS,ID_COMPRA,ID_MOVIMENTACAO) VALUES(?,?,2000000002,?,'processando',100,'CREDITO',1,?,?)",
                (kind,id_,salon,purchase,movement),True)
        insert('agendamento',1);insert('pedido',1)
        self.assertEqual(sql('SELECT COUNT(*) FROM PAGAMENTO_CARTAO WHERE ID_BARBEARIA=2000000001 AND ID_COMPRA IS NULL AND ID_MOVIMENTACAO IS NULL'),[(2,)])
        sql("UPDATE PAGAMENTO_CARTAO SET ESTADO='aprovado',ID_COMPRA=700001,ID_MOVIMENTACAO=800001 WHERE TIPO_ALVO='agendamento' AND ID_ALVO=1",commit=True)
        # Firebird's expression-index duplicate is classified as OperationalError
        # by this driver, while constraint duplicates can be IntegrityError.
        with self.assertRaises(firebirdsql.DatabaseError) as purchase_error:insert('pedido',2,purchase=700001,movement=800002)
        self.assertIn('UQ_CARTAO_COMPRA',str(purchase_error.exception));self.assertIn('duplicate',str(purchase_error.exception).lower())
        with self.assertRaises(firebirdsql.DatabaseError) as movement_error:insert('pedido',3,purchase=700002,movement=800001)
        self.assertIn('UQ_CARTAO_MOVIMENTACAO',str(movement_error.exception));self.assertIn('duplicate',str(movement_error.exception).lower())
        insert('agendamento',2,salon=2000000003,purchase=700001,movement=800001)
        self.assertEqual(sql('SELECT MON$ODS_MAJOR,MON$ODS_MINOR FROM MON$DATABASE'),[(13,0)])
        unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
        self.assertTrue(unchanged,'Pristine detached archive must remain byte-identical')
        (QA_ROOT/'legacy-ods130-proof.json').write_text(json.dumps({'runtime_bits':struct.calcsize('P')*8,
            'fixture_method':'exclusive cold raw copy; no gbak restore; original never attached',
            'ods_before':[13,0],'ods_after':[13,0],'condition_source_absent':True,
            'computed_unique_indexes':2,'second_migration_ddl_count':0,
            'same_merchant_two_null_attempts':True,'duplicate_purchase_rejected':True,
            'duplicate_movement_rejected':True,'other_merchant_same_ids_allowed':True,
            'original_archive_hash_unchanged':unchanged,'network_provider_calls':0},indent=2),encoding='utf8')


if __name__=='__main__':unittest.main()
