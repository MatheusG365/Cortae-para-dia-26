"""Management regressions. No live database or external provider calls."""
import os
os.environ['STARTUP_MIGRATIONS']='false'
os.environ['WAITLIST_WORKER']='false'
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch,MagicMock
import main,gestao,pagamento


class GestaoBehavior(unittest.TestCase):
    def setUp(self):
        self.client=main.app.test_client()

    def test_invalid_money_rejected_and_rounding_decimal(self):
        for value in ('NaN','Infinity','-Infinity',True,None,'bad','10000000000'):
            with self.subTest(value=value),self.assertRaises(ValueError):gestao.dinheiro(value)
        self.assertEqual(gestao.dinheiro('1.005'),Decimal('1.01'))
        for value in (0,-1):
            with self.assertRaises(ValueError):gestao.dinheiro(value,True)

    def test_exact_booking_description_does_not_mix_adjacent_ids(self):
        for text in ('ag#1|na_hora','Booking ag#1 pix','ag#1'):
            self.assertEqual(gestao.id_descricao(text),1)
        self.assertEqual(gestao.id_descricao('ag#10|na_hora'),10)
        self.assertIsNone(gestao.id_descricao('myag#1|na_hora'))
        self.assertIsNone(gestao.id_descricao('ag#1x|na_hora'))

    def test_historical_logs_mask_secret_fields_and_nested_objects(self):
        self.assertEqual(gestao.valor_log_seguro('historical secret','SENHA_HASH'),'[PROTEGIDO]')
        self.assertEqual(gestao.valor_log_seguro('historical client id','ARKHE_CLIENT_ID'),'[PROTEGIDO]')
        value=gestao.valor_log_seguro('{"nome":"teste","nested":{"refresh_token":"secret","api_key":"key"}}','DETALHES')
        self.assertNotIn('secret',value);self.assertNotIn('"key"',value);self.assertIn('teste',value)

    def test_staff_and_client_denied_before_database(self):
        for role in (1,3):
            for path in ('/gestao/clientes','/gestao/financeiro/resumo','/gestao/comissoes/pagamentos','/gestao/logs'):
                with patch.object(gestao,'obter_usuario_logado',return_value={'id_usuario':8,'tipo':role}),patch.object(gestao,'conectar_banco') as db:
                    self.assertEqual(self.client.get(path).status_code,403);db.assert_not_called()

    def test_owner_cannot_override_salon_admin_requires_target(self):
        with patch.object(gestao,'obter_usuario_logado',return_value={'id_usuario':8,'tipo':2}),patch.object(gestao,'conectar_banco') as db:
            self.assertEqual(self.client.get('/gestao/clientes?id_barbearia=9').status_code,403);db.assert_not_called()
        with patch.object(gestao,'obter_usuario_logado',return_value={'id_usuario':1,'tipo':0}),patch.object(gestao,'conectar_banco') as db:
            self.assertEqual(self.client.get('/gestao/clientes').status_code,400);db.assert_not_called()

    def test_owner_never_reads_admin_logs(self):
        with patch.object(gestao,'obter_usuario_logado',return_value={'id_usuario':8,'tipo':2}),patch.object(gestao,'conectar_banco') as db:
            self.assertEqual(self.client.get('/gestao/logs').status_code,403);db.assert_not_called()

    def test_unauthenticated_rejected(self):
        with patch.object(gestao,'obter_usuario_logado',return_value=None),patch.object(gestao,'conectar_banco') as db:
            self.assertEqual(self.client.get('/gestao/clientes').status_code,401);db.assert_not_called()

    def test_summary_uses_paid_dates_pending_due_and_ignores_cancelled(self):
        items=[{'status':'pago','data_pagamento':'2026-10-10','vencimento':'2026-09-01','tipo':'entrada','valor':100},
               {'status':'pago','data_pagamento':'2026-10-10','vencimento':'2026-09-01','tipo':'saida','valor':20},
               {'status':'pendente','data_pagamento':None,'vencimento':'2026-10-10','tipo':'entrada','valor':30},
               {'status':'cancelado','data_pagamento':None,'vencimento':'2026-10-10','tipo':'saida','valor':99}]
        totals,selected=gestao.totais_financeiro(items,date(2026,10,10),date(2026,10,10))
        self.assertEqual(totals,{'receitas':100.,'despesas':20.,'lucro':80.,'pendentes':30.,'pendentes_receber':30.,'pendentes_pagar':0.})
        self.assertEqual(len(selected),3)

    def test_idempotency_same_key_cannot_change_payload(self):
        cur=MagicMock();cur.fetchone.return_value=None
        op,repeated=gestao.repetir_operacao(cur,8,'recebimento',1,{'chave_idempotencia':'abc','valor':10})
        cur.fetchone.return_value=('recebimento',1,op[1])
        self.assertTrue(gestao.repetir_operacao(cur,8,'recebimento',1,{'chave_idempotencia':'abc','valor':10})[1])
        with self.assertRaises(gestao.Conflito):gestao.repetir_operacao(cur,8,'recebimento',1,{'chave_idempotencia':'abc','valor':20})

    def test_invalid_period_rejected_before_business_queries(self):
        with main.app.test_request_context('/?inicio=2026-10-10&fim=2026-09-09'),self.assertRaises(ValueError):gestao.periodo()
        with main.app.test_request_context('/?inicio=2026-10-10'),self.assertRaises(ValueError):gestao.periodo(False)

    def test_legacy_payment_indicator_distinguishes_partial_and_full_receipt(self):
        from datetime import datetime,timedelta
        begin=datetime.now();row=(91,7,8,11,begin,begin+timedelta(minutes=30),'[3]',None,None,'concluido',begin)
        for received,paid in ((Decimal('30.00'),False),(Decimal('100.00'),True)):
            con=MagicMock();cur=con.cursor.return_value;cur.fetchone.return_value=(Decimal('100.00'),)
            last_sql={'sql':''}
            cur.execute.side_effect=lambda sql,*args:last_sql.update(sql=sql)
            cur.fetchone.side_effect=lambda:None if 'PLATAFORMA_TAXA' in last_sql['sql'] else (Decimal('100.00'),)
            cur.fetchall.return_value=[(1,'na_hora','ag#91|gestao|dinheiro|1',received,begin),(2,'na_hora','ag#910|qa',999,begin),(3,'na_hora_pendente','ag#91|na_hora',100,begin)]
            with patch.object(pagamento,'obter_usuario_logado',return_value={'id_usuario':8,'tipo':2}),patch.object(pagamento,'conectar_banco',return_value=con),patch.object(pagamento,'buscar_agendamento',return_value=row),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'_chamar') as provider:
                response=self.client.get('/pagamentos/agendamento/91')
            data=response.get_json();self.assertEqual(response.status_code,200)
            self.assertEqual(data['valor_recebido'],float(received));self.assertEqual(data['saldo'],float(100-received))
            self.assertEqual(data['quitado'],paid);self.assertEqual(data['parcial'],not paid)
            self.assertEqual(data['na_hora_confirmado'],paid);provider.assert_not_called()

    def test_legacy_cash_confirmation_updates_only_remaining_balance(self):
        from datetime import datetime,timedelta
        begin=datetime.now();row=(91,7,8,11,begin,begin+timedelta(minutes=30),'[3]',None,None,'concluido',begin)
        con=MagicMock();cur=con.cursor.return_value;cur.fetchone.return_value=(Decimal('100.00'),)
        last_sql={'sql':''}
        cur.execute.side_effect=lambda sql,*args:last_sql.update(sql=sql)
        cur.fetchone.side_effect=lambda:None if 'PLATAFORMA_TAXA' in last_sql['sql'] else (Decimal('100.00'),)
        cur.fetchall.return_value=[(1,'na_hora','ag#91|gestao|cartao|1',Decimal('30.00')),(2,'na_hora_pendente','ag#91|na_hora',Decimal('100.00'))]
        with patch.object(pagamento,'obter_usuario_logado',return_value={'id_usuario':8,'tipo':2}),patch.object(pagamento,'conectar_banco',return_value=con),patch('agenda_equipe.travar_agendamento',return_value=row),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'registrar_log'),patch.object(pagamento,'_chamar') as provider:
            response=self.client.post('/pagamentos/na-hora',json={'id_agendamento':91})
        self.assertEqual(response.status_code,201)
        update=next(c for c in cur.execute.call_args_list if c.args[0].startswith('UPDATE FINANCEIRO'))
        self.assertEqual(update.args[1],('na_hora',Decimal('70.00'),2));provider.assert_not_called()
        self.assertEqual(response.get_json()['valor'],70.)

    def test_pending_cash_choice_does_not_confirm_partial_remainder(self):
        from datetime import datetime,timedelta
        begin=datetime.now();row=(91,7,8,11,begin,begin+timedelta(minutes=30),'[3]',None,None,'agendado',begin)
        con=MagicMock();cur=con.cursor.return_value;cur.fetchone.return_value=(Decimal('100.00'),)
        last_sql={'sql':''}
        cur.execute.side_effect=lambda sql,*args:last_sql.update(sql=sql)
        cur.fetchone.side_effect=lambda:None if 'PLATAFORMA_TAXA' in last_sql['sql'] else (Decimal('100.00'),)
        cur.fetchall.return_value=[(1,'na_hora','ag#91|gestao|dinheiro|1',Decimal('40.00')),(2,'na_hora_pendente','ag#91|na_hora',100)]
        with patch.object(pagamento,'obter_usuario_logado',return_value={'id_usuario':7,'tipo':1}),patch.object(pagamento,'conectar_banco',return_value=con),patch('agenda_equipe.travar_agendamento',return_value=row),patch.object(pagamento,'pode_ver_agendamento',return_value=True),patch.object(pagamento,'pegar_id_barbearia_alvo',return_value=None),patch.object(pagamento,'registrar_log') as audit:
            response=self.client.post('/pagamentos/na-hora',json={'id_agendamento':91})
        self.assertEqual(response.status_code,200);self.assertEqual(response.get_json()['valor'],60.)
        self.assertFalse(response.get_json()['confirmado']);con.commit.assert_not_called();audit.assert_not_called()


if __name__=='__main__':unittest.main()
