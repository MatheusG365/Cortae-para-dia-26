"""Schedule authorization and immutable financial rules; no production connections."""
import os
os.environ['STARTUP_MIGRATIONS']='false'
os.environ['WAITLIST_WORKER']='false'
import unittest
from datetime import datetime,timedelta
from decimal import Decimal
from unittest.mock import MagicMock,patch
import main
import agenda_gestao as gestao
import agenda_equipe as equipe


class AgendaGestaoRegras(unittest.TestCase):
    def setUp(self):
        self.client=main.app.test_client()

    def test_anonymous_management_never_connects(self):
        with patch.object(gestao,'decodificar_token',return_value=None),patch.object(gestao,'conectar_banco') as connect:
            response=self.client.get('/gestao/agenda/config')
        self.assertEqual(response.status_code,401);connect.assert_not_called()

    def test_client_cannot_change_configuration(self):
        con=MagicMock()
        with patch.object(gestao,'decodificar_token',return_value={'id_usuario':7,'tipo':1}),patch.object(gestao,'conectar_banco',return_value=con):
            response=self.client.put('/gestao/agenda/config',json={'cancelamento_horas':0,'reagendamento_horas':0,'lembrete_horas':0})
        self.assertEqual(response.status_code,403);con.commit.assert_not_called()
        self.assertFalse(any('UPDATE' in c.args[0] for c in con.cursor.return_value.execute.call_args_list))

    def test_audit_is_emitted_after_successful_commit(self):
        con=MagicMock();con.cursor.return_value.fetchone.return_value=(2,);events=[]
        con.commit.side_effect=lambda:events.append('commit')
        with main.app.test_request_context('/'),patch.object(gestao,'decodificar_token',return_value={'id_usuario':2,'tipo':2}),patch.object(gestao,'conectar_banco',return_value=con),patch.object(gestao,'registrar_log',side_effect=lambda *a,**kw:events.append('audit')):
            def handler(cur,salon,user):
                gestao._auditar('UPDATE','AGENDA_CONFIG',id_registro=salon);return {'ok':True}
            gestao._executar(handler,True)
        self.assertEqual(events,['commit','audit'])

    def test_rollback_never_emits_staged_audit(self):
        con=MagicMock();con.cursor.return_value.fetchone.return_value=(2,)
        with main.app.test_request_context('/'),patch.object(gestao,'decodificar_token',return_value={'id_usuario':2,'tipo':2}),patch.object(gestao,'conectar_banco',return_value=con),patch.object(gestao,'registrar_log') as audit:
            def handler(cur,salon,user):
                gestao._auditar('UPDATE','AGENDA_CONFIG',id_registro=salon);raise ValueError('invalid booking')
            response=gestao._executar(handler,True)
        self.assertEqual(response[1],400);con.commit.assert_not_called();audit.assert_not_called()

    def test_fixed_commission_does_not_multiply_booking_amount(self):
        now=datetime.now();booking=(51,7,2,8,now,now+timedelta(minutes=30))
        cur=MagicMock();cur.fetchone.side_effect=[(Decimal('300.00'),),(Decimal('80.00'),'fixa',Decimal('12.34')),None]
        value=equipe.registrar_comissao(cur,booking)
        self.assertEqual(value,Decimal('12.34'))
        self.assertEqual(cur.execute.call_args.args[1][-4:],(Decimal('0.00'),Decimal('12.34'),'fixa',Decimal('12.34')))

    def test_override_price_is_snapshotted_as_decimal(self):
        now=datetime.now();cur=MagicMock();cur.fetchall.side_effect=[[(3,Decimal('100.00'))],[(3,Decimal('45.55'))]]
        total=equipe.salvar_snapshot(cur,51,[{'id_servico':3,'nome':'Corte','duracao':30}],now,now+timedelta(minutes=30),8)
        self.assertEqual(total,Decimal('45.55'))
        self.assertIn('"preco": "45.55"',cur.execute.call_args.args[1][2])

    def test_adjacent_turns_allowed_but_overlap_refused(self):
        adjacent=[{'dia':'segunda','inicio':'08:00','fim':'12:00'},{'dia':'segunda','inicio':'12:00','fim':'16:00'}]
        self.assertEqual(len(gestao.validar_turnos(adjacent)),2)
        overlapping=[adjacent[0],{'dia':'segunda','inicio':'11:59','fim':'16:00'}]
        with self.assertRaises(ValueError):gestao.validar_turnos(overlapping)

    def test_owner_overrides_deadline_but_client_cannot(self):
        now=datetime.now();booking=(51,7,2,8,now+timedelta(hours=1))
        cur=MagicMock();cur.fetchone.return_value=(24,24,24)
        with self.assertRaises(ValueError):gestao.validar_prazo(cur,{'tipo':1},booking,'cancelamento')
        gestao.validar_prazo(cur,{'tipo':2},booking,'cancelamento')


if __name__=='__main__':unittest.main()
