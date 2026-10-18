"""Deferred haircut choices are metadata, never fake catalog/session identifiers."""
import os
os.environ['WAITLIST_WORKER']='false'
import unittest
from datetime import datetime,timedelta
from unittest.mock import MagicMock
import main
import agenda_equipe as equipe


class EscolhaCorteRegras(unittest.TestCase):
    def setUp(self):
        self.cur=MagicMock();self.cur.fetchone.return_value=(85,)
        self.service={'nome':'Corte','genero':'masculino'}

    def test_legacy_empty_context_remains_nullable(self):
        self.assertIsNone(equipe.validar_escolha_corte(self.cur,{},1,2,[self.service]))
        self.cur.execute.assert_not_called()

    def test_legacy_real_catalog_id_is_canonicalized_for_new_bookings(self):
        self.assertEqual(equipe.validar_escolha_corte(self.cur,{'id_corte':85},1,2,[self.service]),'catalogo')
        self.assertIn('ATIVO=1',self.cur.execute.call_args.args[0])

    def test_invalid_choice_and_empty_catalog_are_refused(self):
        for dados in ({'escolha_corte':'inventado'},{'escolha_corte':''},{'escolha_corte':42},{'escolha_corte':'catalogo'}):
            with self.subTest(dados=dados),self.assertRaises(ValueError):equipe.validar_escolha_corte(self.cur,dados,1,2,[self.service])

    def test_special_choices_never_accept_catalog_or_session_ids(self):
        for escolha in ('na_hora','profissional'):
            for campo in ('id_corte','id_visagismo'):
                for value in (0,85,'fake'):
                    with self.subTest(escolha=escolha,campo=campo,value=value),self.assertRaises(ValueError):
                        equipe.validar_escolha_corte(self.cur,{'escolha_corte':escolha,campo:value},1,2,[self.service])

    def test_special_choices_refuse_color_and_mixed_color_services(self):
        for nome in ('Pintar cabelo','Coloração','Aplicação de tinta','Corte e coloração'):
            for escolha in ('na_hora','profissional'):
                with self.subTest(nome=nome,escolha=escolha),self.assertRaises(ValueError):
                    equipe.validar_escolha_corte(self.cur,{'escolha_corte':escolha},1,2,[self.service,{'nome':nome,'genero':'feminino'}])

    def test_special_choices_do_not_require_simulation_or_fake_ids(self):
        for escolha in ('na_hora','profissional'):
            self.assertEqual(equipe.validar_escolha_corte(self.cur,{'escolha_corte':escolha,'id_corte':None,'id_visagismo':None},1,2,[self.service]),escolha)
        self.cur.execute.assert_not_called()

    def test_color_only_simulation_keeps_nullable_cut_choice(self):
        result=equipe.validar_escolha_corte(self.cur,{'escolha_corte':None,'id_visagismo':22},1,2,[{'nome':'Coloração','genero':'feminino'}])
        self.assertIsNone(result)
        self.assertEqual(self.cur.execute.call_args.args[1],(22,1,2))
        self.cur.fetchone.return_value=None
        with self.assertRaises(ValueError):
            equipe.validar_escolha_corte(self.cur,{'id_visagismo':22},1,2,[{'nome':'Coloração','genero':'feminino'}])

    def test_label_uses_service_audience_and_mixed_or_unisex_is_neutral(self):
        self.assertEqual(equipe.nome_escolha_corte('profissional',[{'genero':'feminino'}]),'A cabeleireira escolhe')
        self.assertEqual(equipe.nome_escolha_corte('profissional',[{'genero':'masculino'}]),'O barbeiro escolhe')
        for genres in (['feminino','masculino'],['unissex'],['feminino','unissex']):
            self.assertEqual(equipe.nome_escolha_corte('profissional',[{'genero':g} for g in genres]),'Profissional escolhe')
        self.assertEqual(equipe.nome_escolha_corte('na_hora',[]),'Escolho na hora')

    def test_waitlist_legacy_row_keeps_null_choice(self):
        now=datetime.now();row=(1,2,3,4,now,now+timedelta(minutes=30),'[5]',None,None,'aguardando',now,None)
        self.assertIsNone(equipe.serializar_espera(row)['escolha_corte'])


if __name__=='__main__':unittest.main()
