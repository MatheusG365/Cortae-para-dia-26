"""Independent payment regressions: all provider, credential and DB calls mocked."""
import os
os.environ['STARTUP_MIGRATIONS']='false'
os.environ['WAITLIST_WORKER']='false'
import unittest,json
from datetime import datetime,timedelta
from decimal import Decimal
from unittest.mock import MagicMock,patch
import main,pagamento

class PaymentBehavior(unittest.TestCase):
    def setUp(self):
        self.context=main.app.app_context();self.context.push();self.addCleanup(self.context.pop)
        self.client=main.app.test_client();self.now=datetime.now()
        self.row=(91,7,8,11,self.now,self.now+timedelta(minutes=30),'[3]',None,None,'agendado',self.now)
        self.user={'id_usuario':7,'tipo':1}
        self.booking_lock=patch('agenda_equipe.travar_agendamento',return_value=self.row)
        self.booking_lock.start();self.addCleanup(self.booking_lock.stop)

    def connection(self,value=Decimal('23.55')):
        con=MagicMock();cur=con.cursor.return_value
        last={'sql':''}
        cur.execute.side_effect=lambda sql,*args:last.update(sql=sql)
        cur.fetchone.side_effect=lambda:None if 'PLATAFORMA_TAXA' in last['sql'] else (value,)
        return con,cur

    def test_payment_value_reads_booking_snapshot(self):
        con,cur=self.connection()
        cur.fetchall.return_value=[(Decimal('999.00'),)]
        total=pagamento._valor_do_agendamento(cur,self.row)
        self.assertEqual(Decimal(str(total)),Decimal('23.55'))
        self.assertFalse(any('FROM SERVICO' in c.args[0] for c in cur.execute.call_args_list))

    def test_unknown_legacy_booking_value_is_not_reconstructed(self):
        con,cur=self.connection(None);cur.fetchall.return_value=[(999,)]
        with self.assertRaises(ValueError):pagamento._valor_do_agendamento(cur,self.row)
        self.assertFalse(any('FROM SERVICO' in c.args[0] for c in cur.execute.call_args_list))

    def test_invalid_or_nonpositive_snapshot_not_payable(self):
        for value in (Decimal('NaN'),Decimal('Infinity'),Decimal('-1.00'),Decimal('0')):
            con,cur=self.connection(value)
            with self.subTest(value=str(value)),patch.object(pagamento,'buscar_agendamento',return_value=self.row),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None):
                try:result,error=pagamento._agendamento_pagavel(cur,self.user,91)
                except ValueError:continue
                self.assertIsNone(result);self.assertTrue(error)

    def test_pix_sends_snapshot_not_current_service_or_client_amount(self):
        con,cur=self.connection();cur.fetchall.return_value=[(Decimal('999.00'),)]
        with patch.object(pagamento,'obter_usuario_logado',return_value=self.user),patch.object(pagamento,'conectar_banco',return_value=con),patch.object(pagamento,'buscar_agendamento',return_value=self.row),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'_chamar',return_value={'id_cobranca':'qa-pix','codigo_pagamento':'synthetic','status':0}) as provider,patch.object(pagamento,'registrar_log'):
            response=self.client.post('/pagamentos/pix',json={'id_agendamento':91,'valor':0.01})
        self.assertEqual(response.status_code,201)
        self.assertEqual(Decimal(str(provider.call_args.args[2]['valor'])),Decimal('23.55'))
        self.assertEqual(provider.call_args.kwargs['id_barbearia'],8)
        insert=next(c for c in cur.execute.call_args_list if 'INSERT INTO FINANCEIRO' in c.args[0])
        self.assertEqual(Decimal(str(insert.args[1][-1])),Decimal('23.55'))
        self.assertIn('pix_pendente',insert.args[0]);con.commit.assert_called_once()

    def test_legacy_payment_routes_return400_without_provider_or_commit(self):
        for path in ('/pagamentos/pix','/pagamentos/boleto','/pagamentos/cartao','/pagamentos/na-hora'):
            con,cur=self.connection(None)
            with self.subTest(path=path),patch.object(pagamento,'obter_usuario_logado',return_value=self.user),patch.object(pagamento,'conectar_banco',return_value=con),patch.object(pagamento,'buscar_agendamento',return_value=self.row),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'_chamar') as provider,patch.object(pagamento,'registrar_log'):
                response=self.client.post(path,json={'id_agendamento':91})
            self.assertEqual(response.status_code,400);provider.assert_not_called();con.commit.assert_not_called()

    def test_staff_cannot_create_or_confirm_any_payment(self):
        staff={'id_usuario':50,'tipo':3}
        for path in ('/pagamentos/pix','/pagamentos/boleto','/pagamentos/cartao','/pagamentos/na-hora'):
            con,cur=self.connection()
            with self.subTest(path=path),patch.object(pagamento,'obter_usuario_logado',return_value=staff),patch.object(pagamento,'conectar_banco',return_value=con),patch.object(pagamento,'buscar_agendamento',return_value=self.row),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'_chamar') as provider,patch.object(pagamento,'registrar_log'):
                response=self.client.post(path,json={'id_agendamento':91})
            self.assertEqual(response.status_code,403);provider.assert_not_called();con.commit.assert_not_called()

    def test_staff_cannot_query_own_payments_even_when_booking_access_granted(self):
        for path in ('/pagamentos/pix/qa-pix','/pagamentos/agendamento/91'):
            con,cur=self.connection()
            with self.subTest(path=path),patch.object(pagamento,'obter_usuario_logado',return_value={'id_usuario':50,'tipo':3}),patch.object(pagamento,'conectar_banco',return_value=con),patch.object(pagamento,'buscar_agendamento',return_value=self.row),patch.object(pagamento,'_barbearia_da_cobranca',return_value=(8,self.row)),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'_chamar') as provider:
                response=self.client.get(path)
            self.assertEqual(response.status_code,403);provider.assert_not_called();con.commit.assert_not_called()

    def test_pending_pix_status_does_not_claim_paid_or_change_finance(self):
        for status in (0,'0','pendente','pending',False):
            con,cur=self.connection()
            with self.subTest(status=status),patch.object(pagamento,'obter_usuario_logado',return_value=self.user),patch.object(pagamento,'conectar_banco',return_value=con),patch.object(pagamento,'_barbearia_da_cobranca',return_value=(8,self.row)),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'_chamar',return_value={'id_cobranca':'qa-pix','status':status,'valor':23.55}),patch.object(pagamento,'registrar_log') as audit:
                response=self.client.get('/pagamentos/pix/qa-pix')
            self.assertEqual(response.status_code,200);self.assertFalse(response.get_json()['pago']);con.commit.assert_not_called();audit.assert_not_called()
            self.assertFalse(any('UPDATE FINANCEIRO' in c.args[0] for c in cur.execute.call_args_list))

    def test_confirmed_provider_status_marks_paid(self):
        con,cur=self.connection()
        with patch.object(pagamento,'obter_usuario_logado',return_value=self.user),patch.object(pagamento,'conectar_banco',return_value=con),patch.object(pagamento,'_barbearia_da_cobranca',return_value=(8,self.row)),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'_chamar',return_value={'id_cobranca':'qa-pix','status':1,'valor':23.55}),patch.object(pagamento,'registrar_log'):
            response=self.client.get('/pagamentos/pix/qa-pix')
        self.assertEqual(response.status_code,200);self.assertTrue(response.get_json()['pago']);con.commit.assert_called_once()
        self.assertTrue(any("TIPO = 'pix_pago'" in c.args[0] for c in cur.execute.call_args_list))

    def test_payment_provider_failure_never_creates_fake_checkout_or_finance(self):
        for path in ('/pagamentos/pix','/pagamentos/boleto','/pagamentos/cartao'):
            con,cur=self.connection()
            with self.subTest(path=path),patch.object(pagamento,'obter_usuario_logado',return_value=self.user),patch.object(pagamento,'conectar_banco',return_value=con),patch.object(pagamento,'buscar_agendamento',return_value=self.row),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'_chamar',side_effect=RuntimeError('provider unavailable')),patch.object(pagamento,'registrar_log'):
                response=self.client.post(path,json={'id_agendamento':91})
            self.assertGreaterEqual(response.status_code,500);con.commit.assert_not_called()
            self.assertFalse(any('INSERT INTO FINANCEIRO' in c.args[0] for c in cur.execute.call_args_list))

    def test_transport_serializes_numeric_amount_without_real_request(self):
        provider=MagicMock();provider.__enter__.return_value.read.return_value=b'{"id_cobranca":"qa-pix"}'
        with patch.dict(main.app.config,ARKHE_BASE_URL='https://example.invalid'),patch.object(pagamento,'_cabecalhos',return_value={'Content-Type':'application/json'}),patch.object(pagamento,'urlopen',return_value=provider) as request:
            result=pagamento._chamar('POST','/api/v1/cobrancas/pix',{'valor':23.55},id_barbearia=8)
        self.assertEqual(result['id_cobranca'],'qa-pix');self.assertEqual(json.loads(request.call_args.args[0].data),{'valor':23.55})

if __name__=='__main__':unittest.main()
