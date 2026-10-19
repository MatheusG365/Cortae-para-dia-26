"""Virtual card validation, safe transport and durable reservation boundaries."""
import io
import json
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from flask import Flask
import arkhe_cartao as card
from auditoria import _valor_para_texto


INPUT = dict(numero_cartao='2481000000000001', validade='12/2099', cvv='082',
             tipo='CREDITO', parcelas=3)


def approval(value=100, net=95, fee=5, **extra):
    return dict(aprovado=True, id_compra=456, id_movimentacao=789, valor=value,
                valor_recebido=net, taxa=fee, tipo='CREDITO', parcelas=3,
                final_cartao='0001', data_compra='2026-10-19T10:30:00', **extra)


class CardCoreTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['ARKHE_BASE_URL'] = 'https://example.invalid'
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)

    def test_payload_preserves_leading_zero_cvv_and_uses_server_amount(self):
        data = INPUT | {'valor': .01, 'unknown': 'never forwarded'}
        result = card.validar_cartao(data, Decimal('100.00'))
        self.assertEqual(result, INPUT | {'valor': 100.0})

    def test_rejects_invalid_fields_without_echoing_secrets(self):
        cases = [dict(numero_cartao=2481000000000001), dict(numero_cartao='bad'),
                 dict(cvv=82), dict(cvv='bad'), dict(validade='13/2099'),
                 dict(validade='01/2001'), dict(tipo='PIX'), dict(parcelas=True),
                 dict(parcelas='3'), dict(parcelas=16), dict(tipo='DEBITO', parcelas=2),
                 dict(pin='4321')]
        for change in cases:
            with self.subTest(fields=list(change)):
                with self.assertRaises(card.CartaoErro) as raised:
                    card.validar_cartao(INPUT | change, 100)
                self.assertNotIn(INPUT['numero_cartao'], str(raised.exception))
                self.assertNotIn('4321', str(raised.exception))

    def test_each_installment_requires_one_cent(self):
        with self.assertRaises(card.CartaoErro):
            card.validar_cartao(INPUT, .02)
        for value in (True, float('nan'), float('inf'), -1, 0, Decimal('1.001')):
            with self.subTest(value=str(value)), self.assertRaises(card.CartaoErro):
                card.validar_cartao(INPUT, value)

    def test_approval_whitelist_discards_sensitive_provider_extras(self):
        result = card.validar_resultado(approval(numero_cartao=INPUT['numero_cartao'], cvv=INPUT['cvv'], debug='private'),
                                       card.validar_cartao(INPUT, 100))
        self.assertEqual(set(result), set(card.SAFE_FIELDS))
        self.assertEqual(result['valor'], 100)
        self.assertEqual(result['valor_recebido'], 95)
        self.assertNotIn(INPUT['numero_cartao'], json.dumps(result))

    def test_only_two_documented_half_cent_allocations_are_accepted(self):
        payload = card.validar_cartao(INPUT, Decimal('23.50'))
        for net, fee in ((22.32, 1.18), (22.33, 1.17)):
            self.assertEqual(card.validar_resultado(approval(23.50, net, fee), payload)['valor_recebido'], net)
        for net, fee in ((22.31, 1.19), (22.34, 1.16), (22.32, 1.17)):
            with self.assertRaises(card.CartaoErro):
                card.validar_resultado(approval(23.50, net, fee), payload)

    def test_incoherent_approval_is_uncertain_not_paid(self):
        payload = card.validar_cartao(INPUT, 100)
        changes = [{'valor': 95}, {'valor_recebido': 100}, {'taxa': 0}, {'aprovado': 1},
                   {'parcelas': True}, {'parcelas': 4}, {'tipo': 'DEBITO'},
                   {'final_cartao': '9999'}, {'data_compra': 'private'}, {'id_compra': INPUT['numero_cartao']}]
        for change in changes:
            with self.subTest(fields=list(change)), self.assertRaises(card.CartaoErro) as raised:
                card.validar_resultado(approval() | change, payload)
            self.assertEqual(raised.exception.estado, 'incerto')

    def test_debit_requires_full_net_and_zero_fee(self):
        payload = card.validar_cartao(INPUT | {'tipo': 'DEBITO', 'parcelas': 1}, 100)
        data = approval(100, 100, 0) | {'tipo': 'DEBITO', 'parcelas': 1}
        self.assertEqual(card.validar_resultado(data, payload)['valor_recebido'], 100)
        with self.assertRaises(card.CartaoErro):
            card.validar_resultado(data | {'taxa': 5, 'valor_recebido': 95}, payload)

    def test_transport_uses_documented_route_and_no_sensitive_error_body(self):
        payload = card.validar_cartao(INPUT, 100)
        for status in (400, 401, 403, 404, 409, 429, 500, 503):
            body = io.BytesIO((INPUT['numero_cartao'] + ' ' + INPUT['cvv']).encode())
            failure = HTTPError('https://example.invalid', status, 'private', {}, body)
            with self.subTest(status=status), patch.object(card, 'urlopen', side_effect=failure) as provider:
                with self.assertRaises(card.CartaoErro) as raised:
                    card.vender_cartao(payload, ('id', 'secret'))
                self.assertEqual(body.tell(), 0)
                self.assertNotIn(INPUT['numero_cartao'], str(raised.exception))
                self.assertEqual(raised.exception.estado, 'recusado' if status in (400, 401, 403, 404) else 'incerto')
                provider.assert_called_once()
                self.assertEqual(provider.call_args.args[0].full_url, 'https://example.invalid/api/v1/vendas/cartao')

    def test_timeout_and_raw_exception_are_sanitized(self):
        for failure in (TimeoutError(INPUT['numero_cartao']), RuntimeError(INPUT['cvv'])):
            with patch.object(card, 'urlopen', side_effect=failure):
                with self.assertRaises(card.CartaoErro) as raised:
                    card.vender_cartao(card.validar_cartao(INPUT, 100), ('id', 'secret'))
                self.assertEqual(raised.exception.estado, 'incerto')
                self.assertNotIn(INPUT['numero_cartao'], str(raised.exception))
                self.assertNotIn(INPUT['cvv'], str(raised.exception))

    def test_first_commit_failure_never_calls_provider(self):
        con, cur = MagicMock(), MagicMock()
        con.commit.side_effect = RuntimeError('commit failed')
        with patch.object(card, 'reservar_tentativa', return_value=None), patch.object(card, 'vender_cartao') as provider:
            with self.assertRaises(card.CartaoErro):
                card.executar_venda(cur, con, 'pedido', 1, 2, 3, card.validar_cartao(INPUT, 100), ('id', 'secret'), MagicMock())
            provider.assert_not_called()

    def test_nested_audit_redaction_never_mutates_request(self):
        payload = {'pagamento': {'numero_cartao': INPUT['numero_cartao'], 'cvv': INPUT['cvv'], 'pin': '4321'}, 'valor': 100}
        rendered = _valor_para_texto(payload)
        for secret in (INPUT['numero_cartao'], INPUT['cvv'], '4321'):
            self.assertNotIn(secret, rendered)
        self.assertEqual(payload['pagamento']['cvv'], '082')
        self.assertEqual(json.loads(rendered)['valor'], 100)

    def test_ambiguous_final_commit_keeps_proven_provider_ids_reserved(self):
        con, cur = MagicMock(), MagicMock()
        con.commit.side_effect = [None, RuntimeError('acknowledgement lost'), None]
        safe = approval()
        with patch.object(card, 'reservar_tentativa', return_value=None), \
                patch.object(card, 'vender_cartao', return_value=safe), \
                patch.object(card, 'finalizar_tentativa') as finalize:
            with self.assertRaises(card.CartaoErro) as raised:
                card.executar_venda(cur, con, 'pedido', 1, 2, 3,
                    card.validar_cartao(INPUT, 100), ('id', 'secret'), MagicMock())
            self.assertEqual(raised.exception.estado, 'incerto')
            self.assertEqual(finalize.call_args.args[-2:], ('incerto', safe))


if __name__ == '__main__':
    unittest.main()
