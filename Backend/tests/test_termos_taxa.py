"""Explicit consent regressions, no provider access or live database migrations."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
import main
import termos
import taxa_plataforma as taxa
from decimal import Decimal


class TermosBehavior(unittest.TestCase):
    def setUp(self):
        baseline = patch.dict(main.app.config, {
            'TERMOS_RESPONSAVEL_NOME': '', 'TERMOS_RESPONSAVEL_DOCUMENTO': '',
            'TERMOS_RESPONSAVEL_CONTATO': '', 'TERMOS_RESPONSAVEL_ENDERECO': '',
            'PLATAFORMA_TAXA_PAGADOR': ''})
        baseline.start(); self.addCleanup(baseline.stop)
        self.context = main.app.app_context(); self.context.push()
        self.addCleanup(self.context.pop)
        self.client = main.app.test_client()

    def publicar(self):
        config = patch.dict(main.app.config, {'TERMOS_RESPONSAVEL_NOME': 'Operador QA',
            'TERMOS_RESPONSAVEL_CONTATO': 'qa@example.invalid', 'PLATAFORMA_TAXA_PAGADOR': 'cliente'})
        config.start(); self.addCleanup(config.stop)

    def test_public_document_no_database_or_invented_identity(self):
        with patch.object(termos, 'conectar_banco') as db:
            response = self.client.get('/termos-uso')
        self.assertEqual(response.status_code, 200); db.assert_not_called()
        data = response.get_json()
        self.assertEqual(data['taxa']['percentual'], 1.5)
        self.assertTrue(data['identificacao_pendente'])
        self.assertEqual(data['estado_publicacao'], 'rascunho')
        self.assertEqual(data['responsavel']['documento'], '')

    def test_name_contact_and_valid_payer_publish_without_optional_identity(self):
        self.publicar()
        for payer in ('cliente', 'barbearia'):
            with self.subTest(payer=payer), patch.dict(main.app.config, {'PLATAFORMA_TAXA_PAGADOR': payer}):
                data = self.client.get('/termos-uso').get_json()
                self.assertEqual(data['estado_publicacao'], 'publicado')
                self.assertTrue(data['aceite_habilitado']); self.assertTrue(data['taxa']['ativa'])
                self.assertFalse(data['identificacao_pendente'])
                self.assertEqual(data['responsavel'], {'nome': 'Operador QA',
                    'contato': 'qa@example.invalid', 'documento': '', 'endereco': ''})

    def test_missing_required_publication_field_keeps_draft(self):
        self.publicar()
        for config, value in (('TERMOS_RESPONSAVEL_NOME', '  '),
                              ('TERMOS_RESPONSAVEL_CONTATO', ''),
                              ('PLATAFORMA_TAXA_PAGADOR', ''),
                              ('PLATAFORMA_TAXA_PAGADOR', 'outro')):
            with self.subTest(config=config, value=value), patch.dict(main.app.config, {config: value}):
                document = termos.documento_termos()
                self.assertEqual(document['estado_publicacao'], 'rascunho')
                self.assertFalse(document['aceite_habilitado']); self.assertFalse(document['taxa']['ativa'])
                self.assertEqual(document['identificacao_pendente'], config != 'PLATAFORMA_TAXA_PAGADOR')
                cur = MagicMock()
                termos.exigir_aceite(cur, 10)
                with self.assertRaises(termos.AceitePendente):
                    termos.registrar_aceite(cur, 10, termos.versao_atual(), True)
                cur.execute.assert_not_called()

    def test_optional_identity_update_requires_new_account_acceptance_and_summary(self):
        self.publicar()
        old_version = termos.versao_atual()
        old_document = termos.texto_documento()
        old_hash = termos.hashlib.sha256(old_document.encode()).hexdigest()
        old_summary = taxa.resumo_confirmavel(100, 25, {'staff': 3})
        for config, value in (('TERMOS_RESPONSAVEL_DOCUMENTO', 'Documento informado depois'),
                              ('TERMOS_RESPONSAVEL_ENDERECO', 'Endereço informado depois')):
            with self.subTest(config=config), patch.dict(main.app.config, {config: value}):
                self.assertNotEqual(termos.versao_atual(), old_version)
                self.assertTrue(termos.documento_termos()['aceite_habilitado'])
                cur = MagicMock(); cur.fetchone.return_value = None
                self.assertFalse(termos.estado_aceite(cur, 10)['aceito'])
                self.assertEqual(cur.execute.call_args.args[1], (10, termos.versao_atual()))
                with self.assertRaises(termos.AceitePendente):
                    termos.exigir_aceite(cur, 10)
                with self.assertRaises(termos.AceitePendente):
                    termos.registrar_aceite(cur, 10, old_version, True)
                cur.fetchone.return_value = (datetime.now(), old_hash)
                self.assertFalse(termos.estado_aceite(cur, 10)['aceito'])
                new_summary = taxa.resumo_confirmavel(100, 25, {'staff': 3})
                with self.assertRaises(taxa.ResumoAlterado):
                    taxa.confirmar_resumo({'confirmacao_resumo': old_summary['confirmacao_resumo']}, new_summary)
                self.assertFalse(any('UPDATE' in call.args[0] or 'INSERT' in call.args[0]
                                     for call in cur.execute.call_args_list))

    def test_published_accept_endpoint_requires_explicit_true_checkbox(self):
        self.publicar()
        for payload in ({'versao': termos.versao_atual()},
                        {'versao': termos.versao_atual(), 'aceito': False},
                        {'versao': termos.versao_atual(), 'aceito': 'true'}):
            con = MagicMock(); cur = con.cursor.return_value; cur.fetchone.return_value = (10,)
            with self.subTest(payload=payload), patch.object(termos, 'decodificar_token', return_value={'id_usuario': 10}), \
                    patch.object(termos, 'conectar_banco', return_value=con):
                response = self.client.post('/termos-uso/aceite', json=payload)
            self.assertEqual(response.status_code, 428)
            con.commit.assert_not_called(); con.rollback.assert_called_once()
            self.assertFalse(any('INSERT' in call.args[0] for call in cur.execute.call_args_list))

    def test_version_changes_on_content_or_identity(self):
        initial = termos.versao_atual()
        with patch.dict(main.app.config, {'TERMOS_RESPONSAVEL_NOME': 'Identidade QA'}):
            self.assertNotEqual(termos.versao_atual(), initial)

    def test_accept_endpoint_requires_authenticated_account(self):
        with patch.object(termos, 'decodificar_token', return_value=None), patch.object(termos, 'conectar_banco') as db:
            self.assertEqual(self.client.post('/termos-uso/aceite', json={'versao': termos.versao_atual(), 'aceito': True}).status_code, 401)
        db.assert_not_called()

    def test_acceptance_strict_boolean_and_current_version(self):
        self.publicar()
        for value in (False, 'true', 1, None):
            cur = MagicMock()
            with self.subTest(value=value), self.assertRaises(termos.AceitePendente):
                termos.registrar_aceite(cur, 10, termos.versao_atual(), value)
            cur.execute.assert_not_called()
        with self.assertRaises(termos.AceitePendente):
            termos.registrar_aceite(MagicMock(), 10, 'old-version', True)

    def test_acceptance_content_snapshot_is_immutable_and_idempotent(self):
        self.publicar()
        cur = MagicMock(); cur.fetchone.side_effect = [(10,), None]
        termos.registrar_aceite(cur, 10, termos.versao_atual(), True)
        sql, values = cur.execute.call_args.args
        self.assertIn('INSERT INTO TERMO_ACEITE', sql)
        self.assertEqual(values[0], 10); self.assertIn('Termos de uso', values[3])
        cur = MagicMock(); cur.fetchone.side_effect = [(10,), (termos.versao_atual(),)]
        termos.registrar_aceite(cur, 10, termos.versao_atual(), True)
        self.assertFalse(any('INSERT' in call.args[0] or 'UPDATE' in call.args[0] for call in cur.execute.call_args_list))

    def test_missing_or_wrong_document_hash_requires_real_acceptance(self):
        self.publicar()
        for row in (None, (datetime.now(), 'wrong')):
            cur = MagicMock(); cur.fetchone.return_value = row
            self.assertFalse(termos.estado_aceite(cur, 10)['aceito'])
            with self.assertRaises(termos.AceitePendente): termos.exigir_aceite(cur, 10)

    def test_draft_never_blocks_operations_or_collects_contract_acceptance(self):
        cur = MagicMock(); termos.exigir_aceite(cur, 10); cur.execute.assert_not_called()
        with self.assertRaises(termos.AceitePendente): termos.registrar_aceite(cur, 10, termos.versao_atual(), True)
        cur.execute.assert_not_called()

    def test_pending_policy_never_creates_financial_obligation(self):
        cur=MagicMock();summary=taxa.registrar_taxa(cur,'pedido',1,100,25,10,10,20)
        self.assertEqual(summary['taxa_valor'],0);self.assertEqual(summary['valor_total_cliente'],125)
        self.assertFalse(summary['ativa']);cur.execute.assert_not_called()

    def test_customer_additional_fee_and_shipping_excluded(self):
        self.publicar();result=taxa.calcular('100',25)
        self.assertEqual((result['taxa_valor'],result['valor_total_cliente'],result['valor_liquido_barbearia']),(1.5,126.5,100.))
        self.assertFalse(result['repasse_automatico'])

    def test_merchant_deduction_does_not_increase_customer_total(self):
        self.publicar()
        with patch.dict(main.app.config,{'PLATAFORMA_TAXA_PAGADOR':'barbearia'}):result=taxa.calcular(100,25)
        self.assertEqual((result['taxa_valor'],result['valor_total_cliente'],result['valor_liquido_barbearia']),(1.5,125.,98.5))

    def test_decimal_rounding_is_once_per_operation_and_nonfinite_rejected(self):
        self.publicar();self.assertEqual(taxa.calcular(1)['taxa_valor'],.02)
        self.assertEqual(taxa.calcular(100.33)['taxa_valor'],1.50)
        for value in ('NaN','Infinity',True,-1):
            with self.subTest(value=value),self.assertRaises(ValueError):taxa.calcular(value)

    def test_historical_transaction_never_gets_fee_from_current_policy(self):
        self.publicar();cur=MagicMock();cur.fetchone.return_value=None
        result=taxa.resumo_registrado(cur,'agendamento',1,100)
        self.assertEqual(result['taxa_valor'],0);self.assertEqual(result['valor_total_cliente'],100)

    def test_repricing_policy_change_or_tampered_summary_requires_reconfirmation(self):
        self.publicar();summary=taxa.resumo_confirmavel(100,0,{'staff':3})
        taxa.confirmar_resumo({'confirmacao_resumo':summary['confirmacao_resumo']},summary)
        for changed in (taxa.resumo_confirmavel(101,0,{'staff':3}),taxa.resumo_confirmavel(100,0,{'staff':4})):
            with self.assertRaises(taxa.ResumoAlterado):taxa.confirmar_resumo({'confirmacao_resumo':summary['confirmacao_resumo']},changed)
        with self.assertRaises(taxa.ResumoAlterado):taxa.confirmar_resumo({},summary)

    def test_payer_and_actor_need_actual_acceptance_not_client_payload(self):
        self.publicar();cur=MagicMock()
        with patch.object(taxa,'exigir_aceite') as accept:
            taxa.exigir_aceites(cur,3,10,20)
        self.assertEqual([call.args[1] for call in accept.call_args_list],[3,10])
        with patch.dict(main.app.config,{'PLATAFORMA_TAXA_PAGADOR':'barbearia'}),patch.object(taxa,'exigir_aceite') as accept:
            taxa.exigir_aceites(cur,3,10,20)
        self.assertEqual([call.args[1] for call in accept.call_args_list],[3,20])

    def test_cancellation_preserves_snapshot_but_no_active_obligation(self):
        self.publicar();cur=MagicMock();cur.fetchone.return_value=(Decimal('100'),Decimal('25'),Decimal('1.5'),Decimal('1.5'),'cliente',Decimal('126.5'),Decimal('100'),'historic-version')
        result=taxa.resumo_registrado(cur,'pedido',1,999,status='cancelado')
        self.assertEqual(result['valor_total_cliente'],126.5);self.assertEqual(result['termos_versao'],'historic-version')
        self.assertFalse(result['ativa']);self.assertEqual(result['taxa_devida'],0)


if __name__ == '__main__':
    unittest.main()
