"""Rating ownership, historical ranking rules and optional isolated Firebird SQL.

RUN_FIREBIRD_RANKING_TESTS=1 creates disposable databases; never opens production.
"""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest.mock import MagicMock, patch

import firebirdsql
import main
import agenda_gestao
import ranking_avaliacoes as rankings
from migrations import ranking_schema
import visagismo


def booking(id_agendamento=1, cliente=20, salon=10, funcionario=1, status='concluido', futuro=False):
    inicio = datetime.now()+timedelta(days=2) if futuro else datetime.now()-timedelta(days=2)
    return (id_agendamento, cliente, salon, funcionario, inicio, inicio+timedelta(minutes=30),
            '[]', None, None, status, inicio, None)


class RegrasRankingAvaliacao(unittest.TestCase):
    def setUp(self): self.client = main.app.test_client()

    def test_invalid_notes_never_coerce_into_votes(self):
        for nota in (True, False, 0, 6, 3.0, '5', None):
            with self.subTest(nota=nota), self.assertRaises(ValueError):
                rankings.validar_avaliacao({'nota': nota})

    def test_comment_boundary_trim_and_type(self):
        self.assertEqual(rankings.validar_avaliacao({'nota': 4, 'comentario': '  Bom  '}), (4, 'Bom'))
        self.assertEqual(len(rankings.validar_avaliacao({'nota': 5, 'comentario': 'á'*1000})[1]), 1000)
        for comentario in ('x'*1001, None, [], {}):
            with self.subTest(comentario=type(comentario)), self.assertRaises(ValueError):
                rankings.validar_avaliacao({'nota': 5, 'comentario': comentario})

    def test_only_concluded_past_visits_are_eligible(self):
        self.assertTrue(rankings.atendimento_avaliavel(booking()))
        self.assertFalse(rankings.atendimento_avaliavel(booking(futuro=True)))
        for status in ('faltou', 'cancelado', 'agendado', 'confirmado', 'remarcado'):
            self.assertFalse(rankings.atendimento_avaliavel(booking(status=status)))

    def test_non_completed_serialization_does_not_query_votes(self):
        cur = MagicMock()
        self.assertEqual(rankings.dados_avaliacao(cur, booking(status='cancelado')),
                         {'avaliacao': None, 'pode_avaliar': False})
        cur.execute.assert_not_called()

    def test_anonymous_never_connects_to_any_rating_route(self):
        for method in ('get', 'put'):
            with patch.object(rankings, 'decodificar_token', return_value=None), patch.object(rankings, 'conectar_banco') as connect:
                result = getattr(self.client, method)('/agendamentos/1/avaliacao', json={'nota': 5})
            self.assertEqual(result.status_code, 401); connect.assert_not_called()

    def test_staff_owner_admin_cannot_vote(self):
        for tipo in (0, 2, 3):
            with patch.object(rankings, 'decodificar_token', return_value={'id_usuario': 20, 'tipo': tipo}), patch.object(rankings, 'conectar_banco') as connect:
                response = self.client.put('/agendamentos/1/avaliacao', json={'nota': 5})
            self.assertEqual(response.status_code, 403); connect.assert_not_called()

    def test_other_customer_cannot_read_or_change_a_visit(self):
        for method in ('get', 'put'):
            con = MagicMock()
            with patch.object(rankings, 'decodificar_token', return_value={'id_usuario': 21, 'tipo': 1}), \
                 patch.object(rankings, 'conectar_banco', return_value=con), \
                 patch.object(rankings, 'travar_agendamento', return_value=booking()), \
                 patch('visagismo.buscar_agendamento', return_value=booking()):
                response = getattr(self.client, method)('/agendamentos/1/avaliacao', json={'nota': 5})
            self.assertEqual(response.status_code, 404); con.commit.assert_not_called()
            con.cursor.return_value.execute.assert_not_called()

    def test_future_or_unfinished_visit_cannot_be_rated(self):
        for row in (booking(futuro=True), booking(status='faltou'), booking(status='cancelado')):
            con = MagicMock()
            with patch.object(rankings, 'decodificar_token', return_value={'id_usuario': 20, 'tipo': 1}), \
                 patch.object(rankings, 'conectar_banco', return_value=con), patch.object(rankings, 'travar_agendamento', return_value=row):
                response = self.client.put('/agendamentos/1/avaliacao', json={'nota': 5})
            self.assertEqual(response.status_code, 409); con.commit.assert_not_called()

    def test_edit_preserves_creation_timestamp_and_audits_after_commit(self):
        con = MagicMock(); events = []; now = datetime.now()
        old = {'nota': 2, 'comentario': 'Antes', 'criado_em': now.isoformat(), 'atualizado_em': now.isoformat()}
        new = {**old, 'nota': 5, 'comentario': 'Depois'}
        con.commit.side_effect = lambda: events.append('commit')
        with patch.object(rankings, 'decodificar_token', return_value={'id_usuario': 20, 'tipo': 1}), \
             patch.object(rankings, 'conectar_banco', return_value=con), patch.object(rankings, 'travar_agendamento', return_value=booking()), \
             patch.object(rankings, 'obter_avaliacao', side_effect=[old, new]), \
             patch.object(rankings, 'registrar_log', side_effect=lambda *args, **kwargs: events.append('audit')):
            response = self.client.put('/agendamentos/1/avaliacao', json={'nota': 5, 'comentario': 'Depois'})
        self.assertEqual(response.status_code, 200); self.assertEqual(events, ['commit', 'audit'])
        sql = con.cursor.return_value.execute.call_args.args[0]
        self.assertNotIn('CRIADO_EM=', sql); self.assertIn('ATUALIZADO_EM=', sql)

    def test_ranking_retains_inactive_zeros_and_missing_historical_values(self):
        profissionais = [(2, 'Bia', 0), (1, 'Ana', 1), (3, 'Carla', 1)]
        resumo, result = rankings.calcular_ranking(profissionais,
            [(1, Decimal('50.10'), 3), (1, None, 5), (2, Decimal('100.00'), 5), (None, Decimal('10.10'), None)], 'faturamento')
        self.assertEqual([r['id_funcionario'] for r in result], [2, 1, 3])
        self.assertFalse(result[0]['ativo']); self.assertEqual(result[1]['sem_valor_historico'], 1)
        self.assertEqual(result[1]['media_nota'], 4); self.assertIsNone(result[2]['media_nota'])
        self.assertEqual(resumo['faturamento'], 160.2)
        self.assertEqual(resumo['sem_profissional']['faturamento'], 10.1)
        self.assertEqual(resumo['atendimentos_realizados'], 4)

    def test_equal_scores_have_competition_positions_and_deterministic_name_order(self):
        _, result = rankings.calcular_ranking([(2, 'Bia', 1), (1, 'Ana', 1), (3, 'Carla', 1)],
            [(2, 20, None), (1, 20, None), (3, 10, None)], 'faturamento')
        self.assertEqual([(r['nome'], r['posicao']) for r in result], [('Ana', 1), ('Bia', 1), ('Carla', 3)])

    def test_rating_sort_uses_average_not_sum_and_unrated_is_null(self):
        _, result = rankings.calcular_ranking([(1, 'Ana', 1), (2, 'Bia', 1), (3, 'Carla', 1)],
            [(1, 1, 3), (1, 1, 4), (2, 1, 5)], 'avaliacao')
        self.assertEqual([r['id_funcionario'] for r in result], [2, 1, 3]); self.assertIsNone(result[-1]['media_nota'])

    def test_count_ranking_ignores_monetary_order(self):
        _, result = rankings.calcular_ranking([(1, 'Ana', 1), (2, 'Bia', 1)],
            [(1, 1, None), (1, 1, None), (2, 500, None)], 'atendimentos')
        self.assertEqual(result[0]['id_funcionario'], 1)

    def test_client_and_staff_cannot_see_team_reports(self):
        for tipo in (1, 3):
            for path in ('/gestao/ranking', '/gestao/avaliacoes'):
                con = MagicMock()
                with patch.object(agenda_gestao, 'decodificar_token', return_value={'id_usuario': 20, 'tipo': tipo}), \
                     patch.object(agenda_gestao, 'conectar_banco', return_value=con):
                    response = self.client.get(path)
                self.assertEqual(response.status_code, 403); con.cursor.return_value.execute.assert_not_called()

    def test_owner_cannot_request_another_salon(self):
        con = MagicMock()
        with patch.object(agenda_gestao, 'decodificar_token', return_value={'id_usuario': 10, 'tipo': 2}), \
             patch.object(agenda_gestao, 'conectar_banco', return_value=con):
            response = self.client.get('/gestao/ranking?id_barbearia=11')
        self.assertEqual(response.status_code, 403)

    def test_period_rejects_reverse_invalid_and_unbounded_dates(self):
        for query in ('inicio=2026-10-12&fim=2026-10-11', 'inicio=not-a-date', 'inicio=2020-01-01&fim=2026-01-01',
                      'inicio=9999-12-31&fim=9999-12-31'):
            with main.app.test_request_context('/?'+query), self.assertRaises(ValueError): rankings.periodo_solicitado()

    def test_staff_rating_summary_query_is_scoped_to_own_salon_and_professional(self):
        cur = MagicMock(); cur.fetchone.return_value = (2, Decimal('4.5000')); a = datetime(2026, 10, 1); b = datetime(2026, 11, 1)
        result = rankings.resumo_avaliacoes(cur, 10, 2, a, b)
        self.assertEqual(result, {'total_avaliacoes': 2, 'media_nota': 4.5})
        self.assertEqual(cur.execute.call_args.args[1][:4], (10, 2, a, b))

    def test_booking_eligibility_is_only_exposed_to_its_customer(self):
        for usuario, esperado in (({'tipo': 1, 'id_usuario': 20}, True),
                                  ({'tipo': 1, 'id_usuario': 21}, False),
                                  ({'tipo': 2, 'id_usuario': 10}, False),
                                  ({'tipo': 0, 'id_usuario': 99}, False),
                                  ({'tipo': 3, 'id_usuario': 30}, False), (None, False)):
            cur = MagicMock(); cur.fetchone.return_value = None; cur.fetchall.return_value = []
            with patch.object(visagismo, 'email_do_cliente', return_value={'nome': 'Cliente'}), \
                 patch.object(visagismo, 'email_da_barbearia', return_value={'nome': 'Salão'}), \
                 patch.object(rankings, 'dados_avaliacao', return_value={'avaliacao': None, 'pode_avaliar': True}):
                payload = visagismo.serializar_agendamento(cur, booking(funcionario=None), usuario)
            self.assertEqual(payload['pode_avaliar'], esperado)


@unittest.skipUnless(os.environ.get('RUN_FIREBIRD_RANKING_TESTS') == '1', 'isolated Firebird opt-in')
class RankingFirebirdIsolado(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix='cortae-ranking-')).resolve()
        self.database = self.directory / 'RANKING-AVALIACOES-QA.FDB'
        self.options = dict(host='127.0.0.1', port=int(os.environ.get('RANKING_TEST_FIREBIRD_PORT', main.app.config['DB_PORT'])),
            user=os.environ.get('RANKING_TEST_FIREBIRD_USER', 'SYSDBA'),
            password=os.environ.get('RANKING_TEST_FIREBIRD_PASSWORD', os.environ.get('DB_PASSWORD', main.app.config['DB_PASSWORD'])), database=str(self.database), charset='UTF8')
        con = firebirdsql.create_database(**self.options); cur = con.cursor()
        self.addCleanup(self.drop_created_database)
        try:
            for ddl in ('''CREATE TABLE USUARIO(ID_USUARIO INTEGER PRIMARY KEY,NOME VARCHAR(100),TIPO INTEGER,ATIVO INTEGER)''',
                '''CREATE TABLE FUNCIONARIO(ID_FUNCIONARIO INTEGER PRIMARY KEY,ID_BARBEARIA INTEGER,NOME VARCHAR(100),ATIVO INTEGER)''',
                '''CREATE TABLE AGENDAMENTO(ID_AGENDAMENTO INTEGER PRIMARY KEY,ID_USUARIO INTEGER,ID_BARBEARIA INTEGER,
                ID_FUNCIONARIO INTEGER,INICIO_EM TIMESTAMP,FIM_EM TIMESTAMP,SERVICOS_JSON VARCHAR(100),ID_CORTE INTEGER,
                ID_VISAGISMO INTEGER,STATUS VARCHAR(20),CRIADO_EM TIMESTAMP,ESCOLHA_CORTE VARCHAR(20),VALOR_TOTAL DECIMAL(12,2))'''):
                cur.execute(ddl)
            con.commit()
            for row in [(10, 'Salão Um', 2, 1), (11, 'Salão Dois', 2, 1), (20, 'Cliente Um', 1, 1), (21, 'Cliente Dois', 1, 1)]:
                cur.execute('INSERT INTO USUARIO VALUES(?,?,?,?)', row)
            for row in [(1, 10, 'Ana', 1), (2, 10, 'Bia', 0), (3, 11, 'Outro salão', 1), (4, 10, 'Sem visitas', 1)]:
                cur.execute('INSERT INTO FUNCIONARIO VALUES(?,?,?,?)', row)
            for row, total in [(booking(1), 100), (booking(2), None), (booking(3, funcionario=2), 100),
                (booking(4, status='cancelado'), 100), (booking(5, futuro=True), 100),
                (booking(6, status='agendado'), 200), (booking(7, salon=11, funcionario=3), 999),
                (booking(8, funcionario=None), 25), (booking(9, cliente=21), 10), (booking(10), 5)]:
                cur.execute('INSERT INTO AGENDAMENTO VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (*row, total))
            con.commit()
            cur.execute('SELECT * FROM AGENDAMENTO ORDER BY ID_AGENDAMENTO'); self.original = cur.fetchall()
        finally: cur.close(); con.close()
        with patch.object(ranking_schema, 'conectar_banco', side_effect=self.connect):
            ranking_schema.migrar_ranking_avaliacoes(); ranking_schema.migrar_ranking_avaliacoes()
        con = self.connect(); cur = con.cursor()
        try:
            cur.execute('SELECT * FROM AGENDAMENTO ORDER BY ID_AGENDAMENTO'); self.assertEqual(cur.fetchall(), self.original)
            for id_agendamento, nota in [(1, 3), (2, 5), (3, 5), (4, 1), (5, 1), (7, 5)]:
                cur.execute('INSERT INTO AGENDAMENTO_AVALIACAO(ID_AGENDAMENTO,NOTA,COMENTARIO) VALUES(?,?,?)', (id_agendamento, nota, 'Teste fictício'))
            con.commit()
        finally: cur.close(); con.close()
        self.client = main.app.test_client()
        self.addCleanup(patch.stopall)
        patch.object(rankings, 'conectar_banco', side_effect=self.connect).start()
        patch.object(agenda_gestao, 'conectar_banco', side_effect=self.connect).start()
        patch.object(rankings, 'registrar_log').start()

    def connect(self): return firebirdsql.connect(**self.options)

    def drop_created_database(self):
        if self.database.exists():
            con = self.connect(); con.drop_database(); con.close()

    def test_real_sql_rank_and_comments_exclude_future_cancelled_foreign_salon(self):
        inicio = (datetime.now()-timedelta(days=3)).date().isoformat(); fim = (datetime.now()+timedelta(days=3)).date().isoformat()
        with patch.object(agenda_gestao, 'decodificar_token', return_value={'id_usuario': 10, 'tipo': 2}):
            response = self.client.get(f'/gestao/ranking?inicio={inicio}&fim={fim}&ordenar=avaliacao')
            comments = self.client.get(f'/gestao/avaliacoes?inicio={inicio}&fim={fim}')
        self.assertEqual(response.status_code, 200); self.assertEqual(comments.status_code, 200)
        payload = response.get_json(); self.assertEqual(payload['resumo']['faturamento'], 240)
        self.assertEqual(payload['resumo']['atendimentos_realizados'], 6)
        self.assertEqual(payload['resumo']['sem_valor_historico'], 1)
        self.assertEqual(payload['profissionais'][0]['id_funcionario'], 2)
        self.assertFalse(payload['profissionais'][0]['ativo'])
        self.assertEqual({r['id_agendamento'] for r in comments.get_json()['avaliacoes']}, {1, 2, 3})
        self.assertEqual(payload['resumo']['total_avaliacoes'], 3)

    def test_real_edit_is_one_vote_and_preserves_created_time(self):
        with patch.object(rankings, 'decodificar_token', return_value={'id_usuario': 20, 'tipo': 1}):
            before = self.client.get('/agendamentos/1/avaliacao').get_json()['avaliacao']
            first = self.client.put('/agendamentos/1/avaliacao', json={'nota': 4, 'comentario': '  Revisado  '})
            second = self.client.put('/agendamentos/1/avaliacao', json={'nota': 5})
        self.assertEqual(first.status_code, 200); self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()['avaliacao']['criado_em'], before['criado_em'])
        con = self.connect(); cur = con.cursor()
        try:
            cur.execute('SELECT COUNT(*),MIN(NOTA) FROM AGENDAMENTO_AVALIACAO WHERE ID_AGENDAMENTO=1')
            self.assertEqual(cur.fetchone(), (1, 5))
        finally: cur.close(); con.close()

    def test_real_customer_isolation_and_completion_check(self):
        with patch.object(rankings, 'decodificar_token', return_value={'id_usuario': 20, 'tipo': 1}):
            self.assertEqual(self.client.get('/agendamentos/9/avaliacao').status_code, 404)
            self.assertEqual(self.client.put('/agendamentos/9/avaliacao', json={'nota': 5}).status_code, 404)
            self.assertEqual(self.client.put('/agendamentos/4/avaliacao', json={'nota': 5}).status_code, 409)
            self.assertEqual(self.client.put('/agendamentos/5/avaliacao', json={'nota': 5}).status_code, 409)

    def test_concurrent_first_votes_never_duplicate_or_return_500(self):
        barrier = Barrier(2)
        def vote(nota):
            barrier.wait(timeout=10)
            return main.app.test_client().put('/agendamentos/10/avaliacao', json={'nota': nota}).status_code
        with patch.object(rankings, 'decodificar_token', return_value={'id_usuario': 20, 'tipo': 1}), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(vote, 4); second = pool.submit(vote, 5)
            statuses = [first.result(timeout=20), second.result(timeout=20)]
        self.assertTrue(all(code in (200, 409) for code in statuses), statuses); self.assertIn(200, statuses)
        con = self.connect(); cur = con.cursor()
        try:
            cur.execute('SELECT COUNT(*) FROM AGENDAMENTO_AVALIACAO WHERE ID_AGENDAMENTO=10'); self.assertEqual(cur.fetchone()[0], 1)
        finally: cur.close(); con.close()

    def test_foreign_professional_filter_is_denied_and_comments_are_paginated(self):
        with patch.object(agenda_gestao, 'decodificar_token', return_value={'id_usuario': 10, 'tipo': 2}):
            self.assertEqual(self.client.get('/gestao/avaliacoes?id_funcionario=3').status_code, 404)
            self.assertEqual(self.client.get('/gestao/avaliacoes?pagina=0').status_code, 400)
            response = self.client.get('/gestao/avaliacoes?pagina=2')
        self.assertEqual(response.status_code, 200); self.assertEqual(response.get_json()['avaliacoes'], [])


if __name__ == '__main__': unittest.main()
