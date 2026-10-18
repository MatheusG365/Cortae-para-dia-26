"""Optional salon bookings: isolated cursor fixtures, no live database or messages."""
import os
os.environ['WAITLIST_WORKER'] = 'false'

from contextlib import ExitStack
from datetime import datetime, time, timedelta
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

import main
import barbearia
import database
import visagismo
import agenda_gestao
import taxa_plataforma as taxa


class BookingOptionalStaff(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(main.app.app_context())
        self.stack.enter_context(patch.object(database, 'conectar_banco', side_effect=AssertionError('Live DB forbidden')))
        self.client = main.app.test_client()
        self.day = (datetime.now() + timedelta(days=2)).date()
        self.start = datetime.combine(self.day, time(9))
        self.services = [{'id_servico': 3, 'nome': 'Corte', 'duracao': 30, 'preco': 50, 'genero': 'unissex'}]
        self.staff = {11: {3}, 12: {99}}  # An active, ineligible professional is present too.
        self.bookings = []
        self.blocks = []
        self.intervals = [(time(9), time(12), time(14), time(17))]
        self.con = MagicMock()
        self.cur = self.con.cursor.return_value
        self.cur.execute.side_effect = self.execute
        self.stack.enter_context(patch.object(visagismo, 'conectar_banco', return_value=self.con))
        self.stack.enter_context(patch.object(barbearia, 'conectar_banco', return_value=self.con))
        self.stack.enter_context(patch.object(taxa, 'conectar_banco', return_value=self.con))
        self.stack.enter_context(patch.object(visagismo, 'carregar_servicos', return_value=self.services))
        self.stack.enter_context(patch.object(visagismo, 'obter_usuario_logado', return_value={'id_usuario': 7, 'tipo': 1}))
        self.stack.enter_context(patch.object(taxa, 'decodificar_token', return_value={'id_usuario': 7, 'tipo': 1}))
        self.stack.enter_context(patch.object(taxa, 'documento_termos', return_value={
            'taxa': {'ativa': False, 'pagador': 'pendente'}, 'aceite_habilitado': False}))
        self.stack.enter_context(patch('termos.exigir_aceite'))
        self.stack.enter_context(patch.object(visagismo, 'validar_escolha_corte', return_value='nao_se_aplica'))
        self.stack.enter_context(patch.object(visagismo, 'nome_escolha_corte', return_value=None))
        self.snapshot = self.stack.enter_context(patch.object(visagismo, 'salvar_snapshot', return_value=Decimal('50.00')))
        self.stack.enter_context(patch.object(visagismo, 'buscar_agendamento', return_value=(91, 7, 8, None, self.start, self.start + timedelta(minutes=30))))
        self.stack.enter_context(patch.object(agenda_gestao, 'enfileirar_evento'))
        self.stack.enter_context(patch.object(visagismo, 'registrar_registro'))

    def execute(self, sql, params=()):
        """Small relational fixture; unexpected queries fail instead of reaching a DB."""
        statement = ' '.join(sql.upper().split())
        rows = []
        if 'FROM USUARIO' in statement:
            rows = [(params[0],)] if 'SELECT ID_USUARIO' in statement else [(2,)]
        elif 'FROM DIAS_DE_SERVICO' in statement:
            rows = [(visagismo.DIAS_SEMANA[self.day.weekday()],)] if 'GROUP BY' in statement else self.intervals
        elif 'FROM SERVICO_POR_FUNCIONARIO' in statement:
            rows = [(service,) for service in self.staff.get(params[0], set())]
        elif 'FROM FUNCIONARIO_DIA' in statement:
            rows = [(visagismo.DIAS_SEMANA[self.day.weekday()],)]
        elif 'FROM FUNCIONARIO ' in statement:
            if 'SELECT HORARIOS_CONFIGURADOS' in statement:
                rows = [(0,)]
            elif 'AND ID_FUNCIONARIO=?' in statement:
                rows = [(params[1], 'Profissional', '')] if params[1] in self.staff else []
            else:
                rows = [(id_, 'Profissional', '') for id_ in self.staff]
        elif 'FROM SERVICO ' in statement:
            rows = [(3, Decimal('50.00'))]
        elif 'FROM FUNCIONARIO_PRECO' in statement:
            rows = [(3, Decimal('65.00'))]
        elif 'FROM AGENDA_BLOQUEIO' in statement:
            _, end, start, staff, _ = params
            rows = [(a, b) for owner, a, b in self.blocks if a < end and b > start and (staff is None or owner is None or owner == staff)]
        elif 'FROM AGENDAMENTO' in statement:
            if 'SELECT INICIO_EM' in statement:
                staff = params[0] if 'ID_FUNCIONARIO=?' in statement else None
                end, start = params[-2:]
                rows = [(a, b) for _, owner, a, b in self.bookings if a < end and b > start and (staff is None or owner is None or owner == staff)]
            else:
                staff = params[1] if 'ID_FUNCIONARIO=?' in statement else None
                end, start = params[-2:]
                rows = [(id_,) for id_, owner, a, b in self.bookings if a < end and b > start and (staff is None or owner is None or owner == staff)]
        elif 'INSERT INTO AGENDAMENTO' in statement:
            rows = [(91,)]
        else:
            raise AssertionError(f'Unexpected isolated query: {statement}')
        self.cur.fetchone.return_value = rows[0] if rows else None
        self.cur.fetchall.return_value = rows

    def payload(self, **extra):
        return {'id_barbearia': 8, 'ids_servicos': [3], 'data': self.day.isoformat(), 'horario': '09:00', **extra}

    def slots(self, **extra):
        query = {'id_barbearia': 8, 'servicos': '3', 'data': self.day.isoformat(), **extra}
        return self.client.get('/agendamentos/horarios', query_string=query)

    def inserts(self):
        return [call.args for call in self.cur.execute.call_args_list if 'INSERT INTO AGENDAMENTO' in call.args[0]]

    def test_salon_slots_without_staff_even_when_eligible_staff_exists(self):
        response = self.slots()
        self.assertEqual(response.status_code, 200, response.json)
        self.assertIsNone(response.json['funcionario'])
        self.assertEqual(response.json['valor_total'], 50)
        self.assertTrue(response.json['horarios'][0]['disponivel'])
        self.assertFalse(any('SELECT FIRST 1 ID_FUNCIONARIO' in call.args[0] for call in self.cur.execute.call_args_list))

    def test_salon_slots_available_when_only_ineligible_staff_exists(self):
        self.staff = {12: {99}}
        self.assertEqual(self.slots().status_code, 200)

    def test_null_and_omitted_staff_book_salon_without_assigning_commission_owner(self):
        for extra in ({}, {'id_funcionario': None}):
            with self.subTest(extra=extra):
                response = self.client.post('/agendamentos', json=self.payload(**extra))
                self.assertEqual(response.status_code, 201, response.json)
                self.assertIsNone(response.json['agendamento']['id_funcionario'])
                self.assertIsNone(self.inserts()[-1][1][2])
                self.assertIsNone(self.snapshot.call_args.args[5])
                self.assertEqual(response.json['agendamento']['valor_total'], 50)

    def test_selected_staff_gets_individual_price(self):
        response = self.slots(id_funcionario=11)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['funcionario']['id_funcionario'], 11)
        self.assertEqual(response.json['valor_total'], 65)

    def test_staff_must_be_active_in_this_salon_and_cover_all_services(self):
        for staff, code in ((12, 400), (999, 404)):
            with self.subTest(staff=staff):
                self.assertEqual(self.slots(id_funcionario=staff).status_code, code)
                response = self.client.post('/agendamentos', json=self.payload(id_funcionario=staff))
                self.assertEqual(response.status_code, code, response.json)
        self.assertEqual(self.inserts(), [])

    def test_staff_covering_only_one_of_two_services_is_refused(self):
        self.services.append({'id_servico': 4, 'nome': 'Barba', 'duracao': 30, 'preco': 30})
        response = self.client.get('/agendamentos/horarios', query_string={
            'id_barbearia': 8, 'servicos': '3,4', 'data': self.day.isoformat(), 'id_funcionario': 11})
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/agendamentos', json=self.payload(ids_servicos=[3, 4], id_funcionario=11))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.inserts(), [])

    def test_provided_invalid_staff_is_never_treated_as_unassigned(self):
        for staff in (0, -1, 'wrong', '1.5', True, 2147483648):
            with self.subTest(staff=staff):
                self.assertEqual(self.slots(id_funcionario=staff).status_code, 400)
                self.assertEqual(self.client.post('/agendamentos', json=self.payload(id_funcionario=staff)).status_code, 400)
                self.assertEqual(self.client.post('/agendamentos/resumo', json=self.payload(id_funcionario=staff)).status_code, 400)
        self.assertEqual(self.inserts(), [])

    def test_unassigned_slot_conflicts_with_every_staff_booking(self):
        for owner in (None, 11, 12):
            with self.subTest(owner=owner):
                self.bookings = [(80, owner, self.start, self.start + timedelta(minutes=30))]
                response = self.slots()
                self.assertFalse(response.json['horarios'][0]['disponivel'])
                response = self.client.post('/agendamentos', json=self.payload())
                self.assertEqual(response.status_code, 409, response.json)
        self.assertEqual(self.inserts(), [])

    def test_unassigned_booking_uses_salon_lock_and_global_conflict_query(self):
        response = self.client.post('/agendamentos', json=self.payload())
        self.assertEqual(response.status_code, 201, response.json)
        sql = [' '.join(call.args[0].split()) for call in self.cur.execute.call_args_list]
        lock_index = next(i for i, query in enumerate(sql) if 'TIPO=2 AND ATIVO=1 WITH LOCK' in query)
        conflict_index = next(i for i, query in enumerate(sql) if 'SELECT ID_AGENDAMENTO FROM AGENDAMENTO' in query)
        self.assertLess(lock_index, conflict_index)
        self.assertIn('WITH LOCK', sql[conflict_index])
        self.assertNotIn('ID_FUNCIONARIO', sql[conflict_index])

    def test_staff_booking_conflicts_with_unassigned_but_not_other_staff(self):
        for owner, code in ((None, 409), (12, 201)):
            with self.subTest(owner=owner):
                self.bookings = [(80, owner, self.start, self.start + timedelta(minutes=30))]
                self.snapshot.return_value = Decimal('65.00')
                response = self.client.post('/agendamentos', json=self.payload(id_funcionario=11))
                self.assertEqual(response.status_code, code, response.json)

    def test_salon_and_individual_blocks_prevent_unassigned_booking(self):
        for owner in (None, 12):
            with self.subTest(owner=owner):
                self.blocks = [(owner, self.start, self.start + timedelta(minutes=30))]
                self.assertFalse(self.slots().json['horarios'][0]['disponivel'])
                response = self.client.post('/agendamentos', json=self.payload())
                self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(self.inserts(), [])

    def test_lunch_closed_days_and_full_duration_are_enforced(self):
        for time_, intervals in (('12:00', self.intervals), ('11:45', self.intervals), ('09:00', [])):
            with self.subTest(time=time_, intervals=intervals):
                self.intervals = intervals
                response = self.client.post('/agendamentos', json=self.payload(horario=time_))
                self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(self.inserts(), [])

    def test_past_booking_refused_before_database(self):
        response = self.client.post('/agendamentos', json=self.payload(data=(self.day - timedelta(days=4)).isoformat()))
        self.assertEqual(response.status_code, 400)
        self.cur.execute.assert_not_called()

    def test_booking_that_passes_while_waiting_for_lock_is_refused(self):
        with patch.object(visagismo, 'datetime', wraps=datetime) as clock:
            clock.now.side_effect = [self.start - timedelta(minutes=1), self.start + timedelta(minutes=1)]
            response = self.client.post('/agendamentos', json=self.payload())
        self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(self.inserts(), [])

    def test_validation_repeated_after_salon_lock(self):
        with patch.object(agenda_gestao, 'validar_expediente', side_effect=[None, ValueError('Horário bloqueado.')]) as validate:
            response = self.client.post('/agendamentos', json=self.payload())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(validate.call_count, 2)
        self.assertEqual(self.inserts(), [])

    def test_staff_eligibility_rechecked_under_lock(self):
        with patch.object(visagismo, 'servicos_do_funcionario', side_effect=[{3}, set()]):
            response = self.client.post('/agendamentos', json=self.payload(id_funcionario=11))
        self.assertEqual(response.status_code, 409, response.json)
        self.assertEqual(self.inserts(), [])

    def test_public_staff_days_use_firebird_valid_grouped_order(self):
        response = self.client.get('/barbearias/8/funcionarios?servicos=3')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual([item['id_funcionario'] for item in response.json['funcionarios']], [11])
        query = next(call.args[0] for call in self.cur.execute.call_args_list if 'GROUP BY DIAS' in call.args[0])
        self.assertIn('ORDER BY MIN(ID_DIA)', query)
        self.assertNotIn('DISTINCT', query)

    def test_staff_database_error_is_a_500_and_is_logged(self):
        self.cur.execute.side_effect = RuntimeError('isolated database error')
        with patch.object(main.app.logger, 'exception') as logged:
            response = self.client.get('/barbearias/8/funcionarios?servicos=3')
        self.assertEqual(response.status_code, 500)
        logged.assert_called_once()
        self.assertNotIn('funcionarios', response.json)

    def test_client_preview_uses_authenticated_client_and_unassigned_base_price(self):
        with patch.object(taxa, 'resumo_servicos', wraps=taxa.resumo_servicos) as summarize:
            response = self.client.post('/agendamentos/resumo', json=self.payload(id_cliente=999, id_funcionario=None))
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(summarize.call_args.args[4:], (7, 7))
        self.assertIsNone(summarize.call_args.args[2])
        self.assertEqual(response.json['resumo']['valor_base'], 50)

    def test_nonclient_preview_requires_explicit_client(self):
        for role in (0, 2, 3):
            with self.subTest(role=role), patch.object(taxa, 'decodificar_token', return_value={'id_usuario': 8, 'tipo': role}):
                response = self.client.post('/agendamentos/resumo', json=self.payload())
                self.assertEqual(response.status_code, 400)
                self.assertIn('Cliente', response.json['mensagem']['informacao'])

    def test_owner_preview_cannot_use_another_salon(self):
        with patch.object(taxa, 'decodificar_token', return_value={'id_usuario': 9, 'tipo': 2}):
            response = self.client.post('/agendamentos/resumo', json=self.payload(id_cliente=7))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Barbearia inválida', response.json['mensagem']['informacao'])

    def test_unassigned_preview_confirmation_still_binds_staff_and_actor(self):
        with patch.object(taxa, 'documento_termos', return_value={
            'taxa': {'ativa': True, 'pagador': 'cliente'}, 'aceite_habilitado': False}), patch.object(taxa, 'versao_atual', return_value='test-v1'):
            preview = self.client.post('/agendamentos/resumo', json=self.payload()).json['resumo']
            changed = taxa.resumo_servicos(self.cur, 8, 11, self.services, 7, 7)
            with self.assertRaises(taxa.ResumoAlterado):
                taxa.confirmar_resumo({'confirmacao_resumo': preview['confirmacao_resumo']}, changed)
            changed_actor = taxa.resumo_servicos(self.cur, 8, None, self.services, 99, 7)
            with self.assertRaises(taxa.ResumoAlterado):
                taxa.confirmar_resumo({'confirmacao_resumo': preview['confirmacao_resumo']}, changed_actor)

    def test_unassigned_booking_still_requires_active_fee_confirmation(self):
        with patch.object(taxa, 'documento_termos', return_value={
            'taxa': {'ativa': True, 'pagador': 'cliente'}, 'aceite_habilitado': False}), patch.object(taxa, 'versao_atual', return_value='test-v1'):
            response = self.client.post('/agendamentos', json=self.payload())
        self.assertEqual(response.status_code, 409, response.json)
        self.assertEqual(self.inserts(), [])
        self.con.commit.assert_not_called()

    def test_unassigned_booking_still_requires_published_terms_acceptance(self):
        from termos import AceitePendente
        with patch('termos.exigir_aceite', side_effect=AceitePendente('Aceite a versão publicada.')):
            response = self.client.post('/agendamentos', json=self.payload())
        self.assertEqual(response.status_code, 428, response.json)
        self.assertEqual(self.inserts(), [])
        self.con.commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
