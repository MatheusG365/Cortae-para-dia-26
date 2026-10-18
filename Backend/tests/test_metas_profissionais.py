"""Target validation, authorization and revenue derived only from historical visits."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import main
import agenda_gestao
import metas_profissionais as metas

META = {'id_funcionario': 1, 'tipo': 'atendimentos', 'alvo': 10, 'inicio': '2026-10-01', 'fim': '2026-10-31'}


class RegrasMetas(unittest.TestCase):
    def setUp(self): self.client = main.app.test_client()

    def test_target_types_and_positive_finite_money(self):
        self.assertEqual(metas.validar_meta(META | {'tipo': 'faturamento', 'alvo': '500.25'})[2], Decimal('500.25'))
        for valor in (True, False, None, [], -1, 0, 'NaN', 'Infinity', '1.001', '1000000000000'):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                metas.validar_meta(META | {'tipo': 'faturamento', 'alvo': valor})

    def test_integer_counts_and_ids_never_coerce_invalid_types(self):
        for field, value in [('alvo', 1.5), ('alvo', '1.5'), ('alvo', 1000001), ('id_funcionario', True),
                             ('id_funcionario', 1.0), ('id_funcionario', '1'), ('id_funcionario', 0),
                             ('tipo', 'recebimentos'), ('ativo', 1), ('ativo', 'false')]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): metas.validar_meta(META | {field: value})

    def test_periods_inclusive_366_day_bound_and_strict_dates(self):
        self.assertEqual(metas.periodo_metas({'inicio': '2024-01-01', 'fim': '2024-12-31'}), (date(2024, 1, 1), date(2024, 12, 31)))
        for periodo in ({'inicio': '2024-01-01', 'fim': '2025-01-01'}, {'inicio': '2026-11-01', 'fim': '2026-10-31'},
                        {'inicio': True}, {'inicio': '20261001'}, {'inicio': '2026-02-30'},
                        {'inicio': '9999-12-31', 'fim': '9999-12-31'}):
            with self.subTest(periodo=periodo), self.assertRaises(ValueError): metas.periodo_metas(periodo)

    def test_default_period_is_complete_current_month(self):
        inicio, fim = metas.periodo_metas({})
        self.assertEqual(inicio.day, 1); self.assertEqual(fim.year, inicio.year); self.assertEqual(fim.month, inicio.month)

    def test_progress_exact_decimal_zero_missing_and_exceeded(self):
        result = metas.calcular_progresso('faturamento', Decimal('0.30'), [Decimal('.10'), Decimal('.20'), None])
        self.assertEqual(result['realizado'], .3); self.assertEqual(result['percentual'], 100)
        self.assertTrue(result['atingida']); self.assertEqual(result['sem_valor_historico'], 1); self.assertIsNotNone(result['aviso'])
        exceeded = metas.calcular_progresso('atendimentos', 2, [None, Decimal(50), Decimal(100)])
        self.assertEqual((exceeded['realizado'], exceeded['percentual'], exceeded['restante']), (3, 150, 0))
        zero = metas.calcular_progresso('faturamento', 100, [])
        self.assertEqual((zero['realizado'], zero['percentual'], zero['restante']), (0, 0, 100)); self.assertFalse(zero['atingida'])

    def test_anonymous_denied_before_database(self):
        for path, method in [('/gestao/metas', 'get'), ('/gestao/metas', 'post'), ('/gestao/metas/1', 'put'),
                             ('/gestao/metas/1', 'patch'), ('/painel-barbeiro/metas', 'get')]:
            with patch.object(agenda_gestao, 'decodificar_token', return_value=None), patch.object(agenda_gestao, 'conectar_banco') as con:
                result = getattr(self.client, method)(path, json=META)
            self.assertEqual(result.status_code, 401); con.assert_not_called()

    def test_client_staff_denied_team_and_owner_cross_salon(self):
        for tipo, path, method in [(1, '/gestao/metas', 'get'), (3, '/gestao/metas', 'get'),
                                   (3, '/gestao/metas', 'post'), (3, '/gestao/metas/1', 'patch'),
                                   (2, '/gestao/metas?id_barbearia=11', 'get')]:
            con = MagicMock()
            with patch.object(agenda_gestao, 'decodificar_token', return_value={'id_usuario': 10, 'tipo': tipo}), \
                 patch.object(agenda_gestao, 'conectar_banco', return_value=con):
                result = getattr(self.client, method)(path, json=META)
            self.assertEqual(result.status_code, 403); con.cursor.return_value.execute.assert_not_called()

    def test_progress_sql_uses_scope_completed_actual_finish_and_snapshot_only(self):
        cur = MagicMock(); cur.fetchall.return_value = [(Decimal('25.50'),), (None,)]
        now = datetime.now(); row = (1, 2, 'Ana', 'faturamento', Decimal('100'), date(2026, 10, 1), date(2026, 10, 31), 0, now, now)
        result = metas.serializar_meta(cur, 10, row)
        sql, params = cur.execute.call_args.args
        self.assertIn("STATUS='concluido'", sql); self.assertIn('FIM_EM<=?', sql); self.assertIn('VALOR_TOTAL', sql)
        self.assertNotIn('SERVICO', sql); self.assertEqual(params[:4], (10, 2, datetime(2026, 10, 1), datetime(2026, 11, 1)))
        self.assertEqual(result['realizado'], 25.5); self.assertFalse(result['ativo'])

    def test_staff_filter_for_other_professional_never_reads_goals(self):
        cur = MagicMock()
        with main.app.test_request_context('/painel-barbeiro/metas?id_funcionario=2'), self.assertRaises(ValueError) as err:
            metas.listar_metas(cur, 10, profissional=1)
        self.assertEqual(err.exception.status, 403); cur.execute.assert_not_called()

    def test_oversized_resource_id_never_reaches_firebird_integer(self):
        with patch.object(agenda_gestao, 'conectar_banco') as con:
            for method in ('put', 'patch'):
                for id_ in ('0', '2147483648', '9999999999999999999999'):
                    self.assertEqual(getattr(self.client, method)('/gestao/metas/'+id_, json=META).status_code, 404)
        con.assert_not_called()


if __name__ == '__main__': unittest.main()
