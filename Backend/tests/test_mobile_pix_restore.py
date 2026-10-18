"""Recover a native charge QR by GET, with strict reconciliation validation."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
import main


class NativePixRestoreTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()
        now = datetime.now()
        self.booking = (91, 7, 8, 11, now, now + timedelta(minutes=30), '[3]', None, None, 'agendado', now)

    def consult(self, response, allowed=True, user=True, value=Decimal('23.55')):
        con = MagicMock()
        con.cursor.return_value.fetchone.return_value = (value,) if value is not None else None
        with ExitStack() as stack:
            stack.enter_context(patch('pagamento.obter_usuario_logado', return_value={'id_usuario': 7, 'tipo': 1} if user is True else user))
            stack.enter_context(patch('pagamento.conectar_banco', return_value=con))
            stack.enter_context(patch('pagamento._barbearia_da_cobranca', return_value=(8, self.booking)))
            stack.enter_context(patch('agenda_equipe.travar_agendamento', return_value=self.booking))
            stack.enter_context(patch('pagamento.pode_ver_agendamento', return_value=allowed))
            stack.enter_context(patch('pagamento.pegar_id_barbearia_alvo', return_value=None))
            provider = stack.enter_context(patch('pagamento._chamar', return_value=response))
            audit = stack.enter_context(patch('pagamento.registrar_log'))
            result = self.client.get('/pagamentos/pix/162')
        return result, con, provider, audit

    def test_pending_charge_restores_exact_original_code_without_create_or_payment(self):
        response, con, provider, audit = self.consult({'id_cobranca': 162, 'valor': 23.55, 'status': 0, 'codigo_pagamento': 'ARKHEPIX:EXACT-CODE'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['codigo_pagamento'], 'ARKHEPIX:EXACT-CODE')
        self.assertEqual(response.json['codigo_pix'], 'ARKHEPIX:EXACT-CODE')
        self.assertFalse(response.json['pago'])
        self.assertEqual(provider.call_args.args[:2], ('GET', '/api/v1/cobrancas/pix/162'))
        con.commit.assert_not_called(); audit.assert_not_called()

    def test_matching_paid_charge_only_updates_its_local_financial_record(self):
        response, con, _, audit = self.consult({'id_cobranca': '162', 'valor': '23.550', 'status': 1, 'codigo_pix': ' CODE '})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['pago'])
        self.assertEqual(response.json['codigo_pagamento'], 'CODE')
        update = [c for c in con.cursor.return_value.execute.call_args_list if 'UPDATE FINANCEIRO' in c.args[0]]
        self.assertEqual(update[0].args[1], (7, 'ARKHE:162 ag#91'))
        self.assertIn("TIPO='pix_pendente'", update[0].args[0])
        con.commit.assert_called_once(); audit.assert_called_once()

    def test_mismatched_or_malformed_id_value_never_marks_paid(self):
        valid = {'id_cobranca': 162, 'valor': 23.55, 'status': 1}
        for changed in ({'id_cobranca': 999}, {'id_cobranca': None}, {'id_cobranca': True}, {'valor': 0.01},
                        {'valor': None}, {'valor': 'NaN'}, {'valor': 'Infinity'}, {'valor': True}, {'valor': '23.551'}):
            with self.subTest(changed=changed):
                response, con, _, audit = self.consult({**valid, **changed})
                self.assertEqual(response.status_code, 502)
                con.commit.assert_not_called(); audit.assert_not_called()
                self.assertFalse(any('UPDATE FINANCEIRO' in c.args[0] for c in con.cursor.return_value.execute.call_args_list))

    def test_missing_or_nonstring_code_is_never_fabricated(self):
        for code in (None, '', '   ', {'not': 'text'}, 123):
            with self.subTest(code=code):
                response, con, _, _ = self.consult({'id_cobranca': 162, 'valor': 23.55, 'status': 0, 'codigo_pagamento': code})
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('codigo_pagamento', response.json)
                self.assertNotIn('codigo_pix', response.json)
                con.commit.assert_not_called()

    def test_no_local_amount_never_reconciles(self):
        response, con, _, audit = self.consult({'id_cobranca': 162, 'valor': 23.55, 'status': 1}, value=None)
        self.assertEqual(response.status_code, 502)
        con.commit.assert_not_called(); audit.assert_not_called()

    def test_scope_is_checked_before_provider_and_code_disclosure(self):
        for user, allowed, status in ((None, True, 401), ({'tipo': 3, 'id_usuario': 9}, True, 403), (True, False, 403)):
            with self.subTest(user=user, allowed=allowed):
                response, con, provider, _ = self.consult({'id_cobranca': 162, 'valor': 23.55, 'status': 0, 'codigo_pix': 'SECRET-QR'}, user=user, allowed=allowed)
                self.assertEqual(response.status_code, status)
                provider.assert_not_called(); con.commit.assert_not_called()
                self.assertNotIn('SECRET-QR', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
