"""Independent team/booking regressions; never connect to production or send mail."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
import main
import agenda_equipe as equipe
import cadastro
import login
import visagismo


class AgendaEquipeBehavior(unittest.TestCase):
    def setUp(self):
        self.context = main.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.client = main.app.test_client()
        self.now = datetime.now()
        self.booking = (91, 7, 8, 11, self.now, self.now+timedelta(minutes=30), '[3]', None, None, 'agendado')

    def test_money_decimal_half_up(self):
        self.assertEqual(equipe.dinheiro('1.005'), Decimal('1.01'))
        self.assertEqual(equipe.dinheiro('0.1')+equipe.dinheiro('0.2'), Decimal('0.30'))

    def test_nonfinite_money_refused(self):
        for value in ('NaN', 'Infinity', '-Infinity', 'oops'):
            with self.subTest(value=value), self.assertRaises(ValueError): equipe.dinheiro(value)

    def test_commission_percentage_bounded(self):
        self.assertEqual(equipe.percentual('0'), Decimal('0.00'))
        self.assertEqual(equipe.percentual('100'), Decimal('100.00'))
        for value in ('-0.01','100.01','NaN'):
            with self.subTest(value=value), self.assertRaises(ValueError): equipe.percentual(value)

    def test_snapshot_uses_db_price_and_keeps_decimal(self):
        cursor=MagicMock();cursor.fetchall.return_value=[(3,Decimal('23.55'))]
        services=[{'id_servico':3,'nome':'Corte QA','duracao':30,'preco':999}]
        total=equipe.salvar_snapshot(cursor,91,services,self.now,self.now+timedelta(minutes=30))
        self.assertEqual(total,Decimal('23.55'))
        args=cursor.execute.call_args.args
        self.assertIn('VALOR_TOTAL IS NULL',args[0])
        self.assertEqual(args[1][:2],(Decimal('23.55'),30))
        self.assertIn('"preco": "23.55"',args[1][2])

    def test_snapshot_missing_service_refused_without_write(self):
        cursor=MagicMock();cursor.fetchall.return_value=[]
        with self.assertRaises(ValueError): equipe.salvar_snapshot(cursor,91,[{'id_servico':3}],self.now,self.now)
        self.assertEqual(cursor.execute.call_count,1)

    def test_commission_decimal_and_persisted_percent(self):
        cursor=MagicMock();cursor.fetchone.side_effect=[(Decimal('23.55'),),(Decimal('12.5'),),None]
        self.assertEqual(equipe.registrar_comissao(cursor,self.booking),Decimal('2.94'))
        self.assertEqual(cursor.execute.call_args.args[1],(91,11,8,Decimal('23.55'),Decimal('12.50'),Decimal('2.94'),'percentual',Decimal('12.50')))

    def test_commission_duplicate_not_inserted(self):
        cursor=MagicMock();cursor.fetchone.side_effect=[(Decimal('23.55'),),(Decimal('12.5'),),(91,)]
        self.assertIsNone(equipe.registrar_comissao(cursor,self.booking))
        self.assertFalse(any('INSERT' in c.args[0] for c in cursor.execute.call_args_list))

    def test_commission_legacy_price_not_invented(self):
        cursor=MagicMock();cursor.fetchone.return_value=(None,)
        with self.assertRaises(ValueError): equipe.registrar_comissao(cursor,self.booking)
        self.assertEqual(cursor.execute.call_count,1)

    def test_commission_without_professional_not_assigned(self):
        cursor=MagicMock();row=list(self.booking);row[3]=None
        self.assertIsNone(equipe.registrar_comissao(cursor,row));cursor.execute.assert_not_called()

    def test_staff_access_scoped_to_own_salon_and_staff(self):
        with patch.object(equipe,'funcionario_logado',return_value=(11,8)):
            self.assertTrue(equipe.acesso_agendamento(MagicMock(),{'id_usuario':50,'tipo':3},self.booking))
            for index,value in ((2,9),(3,12),(3,None)):
                row=list(self.booking);row[index]=value
                self.assertFalse(equipe.acesso_agendamento(MagicMock(),{'id_usuario':50,'tipo':3},row))

    def test_deactivated_staff_access_refused(self):
        with patch.object(equipe,'funcionario_logado',return_value=None):
            self.assertFalse(equipe.acesso_agendamento(MagicMock(),{'id_usuario':50,'tipo':3},self.booking))

    def test_staff_lookup_checks_owner_and_staff_active(self):
        cursor=MagicMock();equipe.funcionario_logado(cursor,{'id_usuario':50,'tipo':3})
        sql=cursor.execute.call_args.args[0]
        self.assertIn('F.ATIVO=1',sql);self.assertIn('U.ATIVO=1',sql);self.assertIn('U.TIPO=2',sql)

    def test_invitation_token_hashed_and_expires(self):
        cursor=MagicMock()
        with patch.object(equipe.secrets,'token_urlsafe',return_value='synthetic-token'):
            invitation=equipe.criar_convite(cursor,11,'qa@example.invalid')
        args=cursor.execute.call_args.args[1]
        self.assertNotEqual(args[1],'synthetic-token');self.assertEqual(len(args[1]),64)
        self.assertGreater(args[2],self.now+timedelta(hours=47))
        self.assertLess(args[2],self.now+timedelta(hours=49))
        self.assertIn('token=synthetic-token',invitation['link_ativacao'])
        self.assertIn('UTILIZADO_EM IS NULL',cursor.execute.call_args_list[0].args[0])

    def test_existing_email_never_hijacked(self):
        cursor=MagicMock();cursor.fetchone.side_effect=[(None,None,'QA'),(7,)]
        with self.assertRaises(ValueError): equipe.atualizar_acesso_funcionario(cursor,11,8,0,{'funcionarios[0][email]':'existing@example.invalid','funcionarios[0][telefone]':'11999999999'})
        self.assertFalse(any('INSERT INTO USUARIO' in c.args[0] for c in cursor.execute.call_args_list))

    def test_linked_staff_email_cannot_be_replaced(self):
        cursor=MagicMock();cursor.fetchone.return_value=(50,'old@example.invalid','QA')
        with self.assertRaises(ValueError): equipe.atualizar_acesso_funcionario(cursor,11,8,0,{'funcionarios[0][email]':'new@example.invalid','funcionarios[0][telefone]':'11999999999'})
        self.assertEqual(cursor.execute.call_count,1)

    def test_invitation_mail_failure_keeps_reviewable_link(self):
        invitations=[{'id_funcionario':11,'email':'qa@example.invalid','link_ativacao':'https://example.invalid/token'}]
        with patch.object(equipe,'enviar_aviso_email',side_effect=RuntimeError('SMTP unavailable')):
            result=equipe.enviar_convites(invitations)
        self.assertFalse(result[0]['email_enviado']);self.assertTrue(result[0]['link_ativacao'])

    def test_public_staff_registration_rejected(self):
        with patch('cadastro.conectar_banco') as connect:
            response=self.client.post('/cadastro',json={'nome':'QA','email':'qa@example.invalid','telefone':'11999999999','senha':'Review!123','confirmarSenha':'Review!123','tipo':3})
        self.assertEqual(response.status_code,400);connect.assert_not_called()

    def test_waitlist_role_restricted_before_database(self):
        for user,code in ((None,401),({'id_usuario':8,'tipo':2},403),({'id_usuario':50,'tipo':3},403)):
            with self.subTest(user=user),patch.object(equipe,'obter_usuario_logado',return_value=user),patch.object(equipe,'conectar_banco') as connect:
                response=self.client.post('/agendamentos/lista-espera',json={})
                self.assertEqual(response.status_code,code);connect.assert_not_called()

    def test_dashboard_role_restricted_before_database(self):
        for user,code in ((None,401),({'id_usuario':8,'tipo':2},403),({'id_usuario':7,'tipo':1},403)):
            with self.subTest(user=user),patch.object(equipe,'obter_usuario_logado',return_value=user),patch.object(equipe,'conectar_banco') as connect:
                response=self.client.get('/barbeiro/painel')
                self.assertEqual(response.status_code,code);connect.assert_not_called()

    def test_foreign_salon_invitation_refused(self):
        with patch.object(equipe,'obter_usuario_logado',return_value={'id_usuario':8,'tipo':2}),patch.object(equipe,'conectar_banco') as connect:
            response=self.client.post('/barbearias/9/funcionarios/11/convite',json={})
        self.assertEqual(response.status_code,403);connect.assert_not_called()

    def test_staff_cannot_issue_invitation(self):
        with patch.object(equipe,'obter_usuario_logado',return_value={'id_usuario':50,'tipo':3}),patch.object(equipe,'conectar_banco') as connect:
            response=self.client.post('/barbearias/8/funcionarios/11/convite',json={})
        self.assertEqual(response.status_code,403);connect.assert_not_called()

    def test_expired_used_or_unknown_invitation_not_activated(self):
        for invitation in (None,(1,11,self.now-timedelta(seconds=1),None),(1,11,self.now+timedelta(hours=1),self.now)):
            con=MagicMock();con.cursor.return_value.fetchone.return_value=invitation
            with self.subTest(invitation=invitation),patch.object(equipe,'conectar_banco',return_value=con):
                response=self.client.post('/barbeiros/ativar',json={'token':'synthetic','senha':'Review!123','confirmarSenha':'Review!123'})
            self.assertEqual(response.status_code,400);con.commit.assert_not_called()

    def test_weak_staff_activation_password_refused_before_db(self):
        for password in ('abcdefgh','Review123','A1!'+('é'*35)):
            with self.subTest(password=password),patch.object(equipe,'conectar_banco') as connect:
                response=self.client.post('/barbeiros/ativar',json={'token':'synthetic','senha':password,'confirmarSenha':password})
            self.assertEqual(response.status_code,400);connect.assert_not_called()

    def test_pending_staff_login_cannot_generate_public_activation_code(self):
        con=MagicMock();cursor=con.cursor.return_value
        cursor.fetchone.return_value=(50,'QA','qa@example.invalid','11999999999','hash',3,0,0,0,None)
        with patch.object(login,'conectar_banco',return_value=con),patch.object(login,'capturar_registro',return_value={}),patch.object(login,'enviando_email') as send:
            response=self.client.post('/login',json={'email':'qa@example.invalid','senha':'Review!123'})
        self.assertEqual(response.status_code,403);send.assert_not_called();con.commit.assert_not_called()
        self.assertFalse(any('UPDATE USUARIO' in c.args[0] for c in cursor.execute.call_args_list))

    def test_public_code_activation_cannot_activate_staff(self):
        con=MagicMock();cursor=con.cursor.return_value;cursor.fetchone.return_value=(50,'synthetic-code',0,3)
        with patch.object(cadastro,'conectar_banco',return_value=con):
            response=self.client.post('/verificar-codigo',json={'email':'qa@example.invalid','codigo':'synthetic-code'})
        self.assertEqual(response.status_code,403);con.commit.assert_not_called()
        self.assertFalse(any('UPDATE USUARIO' in c.args[0] for c in cursor.execute.call_args_list))

    def test_foreign_visagismo_session_refused_with_client_and_salon_bindings(self):
        cursor=MagicMock();cursor.fetchone.return_value=None
        with self.assertRaises(ValueError):equipe.validar_contexto_visagismo(cursor,{'id_visagismo':91},7,8)
        self.assertEqual(cursor.execute.call_args.args[1],(91,7,8))

    def test_booking_foreign_session_never_inserted(self):
        con=MagicMock();cursor=con.cursor.return_value;cursor.fetchone.return_value=None
        with patch('termos.exigir_aceite'),patch.object(visagismo,'obter_usuario_logado',return_value={'id_usuario':7,'tipo':1}),patch.object(visagismo,'conectar_banco',return_value=con),patch.object(visagismo,'carregar_servicos',return_value=[{'id_servico':3,'nome':'QA','duracao':30}]):
            response=self.client.post('/agendamentos',json={'id_barbearia':8,'ids_servicos':[3],'id_visagismo':91,'data':(self.now+timedelta(days=2)).date().isoformat(),'horario':'09:00'})
        self.assertEqual(response.status_code,400);con.commit.assert_not_called()
        self.assertFalse(any('INSERT INTO AGENDAMENTO' in c.args[0] for c in cursor.execute.call_args_list))

    def test_unavailable_cut_refused(self):
        cursor=MagicMock();cursor.fetchone.return_value=None
        with self.assertRaises(ValueError):equipe.validar_contexto_visagismo(cursor,{'id_corte':91},7,8)
        self.assertIn('ATIVO=1',cursor.execute.call_args.args[0])

    def test_waitlist_service_duration_changed_refuses_delivery(self):
        wait=(1,7,8,11,self.now+timedelta(days=2),self.now+timedelta(days=2,minutes=30),'[3]',None,None,'aguardando',self.now,None)
        with patch.object(visagismo,'carregar_servicos',return_value=[{'duracao':60}]):
            self.assertFalse(equipe.slot_disponivel(MagicMock(),wait))

    def test_release_does_not_queue_mail_if_full_interval_not_available(self):
        cursor=MagicMock();cursor.fetchall.return_value=[tuple(range(12))]
        with patch.object(equipe,'slot_disponivel',return_value=False):equipe.enfileirar_liberacao(cursor,self.booking)
        self.assertFalse(any('INSERT INTO EMAIL_OUTBOX' in c.args[0] for c in cursor.execute.call_args_list))

    def test_owner_commissions_restricts_nonowners_before_database(self):
        for user,code in ((None,401),({'id_usuario':7,'tipo':1},403),({'id_usuario':50,'tipo':3},403)):
            with self.subTest(user=user),patch.object(equipe,'obter_usuario_logado',return_value=user),patch.object(equipe,'conectar_banco') as connect:
                response=self.client.get('/barbearia/comissoes')
            self.assertEqual(response.status_code,code);connect.assert_not_called()

    def test_owner_commissions_cannot_select_foreign_salon(self):
        for key in ('id_usuario','id_barbearia','usuario'):
            with self.subTest(key=key),patch.object(equipe,'obter_usuario_logado',return_value={'id_usuario':8,'tipo':2}),patch.object(equipe,'conectar_banco') as connect:
                response=self.client.get('/barbearia/comissoes',query_string={key:9})
            self.assertEqual(response.status_code,403);connect.assert_not_called()

    def test_owner_commissions_period_limits_before_database(self):
        for period in ({'inicio':'2026-10-12','fim':'2026-10-11'},{'inicio':'2025-01-01','fim':'2026-10-11'},{'inicio':'invalid','fim':'2026-10-11'}):
            with self.subTest(period=period),patch.object(equipe,'obter_usuario_logado',return_value={'id_usuario':8,'tipo':2}),patch.object(equipe,'conectar_banco') as connect:
                response=self.client.get('/barbearia/comissoes',query_string=period)
            self.assertEqual(response.status_code,400);connect.assert_not_called()

    def test_admin_commissions_require_explicit_salon(self):
        with patch.object(equipe,'obter_usuario_logado',return_value={'id_usuario':7,'tipo':0}),patch('barbearia.pegar_id_barbearia_alvo',return_value=None),patch.object(equipe,'conectar_banco') as connect:
            response=self.client.get('/barbearia/comissoes')
        self.assertEqual(response.status_code,400);connect.assert_not_called()


if __name__=='__main__': unittest.main()
