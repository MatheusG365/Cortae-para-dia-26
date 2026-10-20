"""Real CRUD, scopes and historical measurements on disposable Firebird databases only."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import firebirdsql
import main
import agenda_gestao
from migrations import metas_schema
@unittest.skipUnless(os.environ.get('RUN_FIREBIRD_METAS_TESTS') == '1', 'isolated Firebird opt-in')
class MetasFirebird(unittest.TestCase):
    def setUp(self):
        self.db = Path(tempfile.mkdtemp(prefix='cortae-metas-')).resolve()/'METAS-QA.FDB'
        self.options = dict(host='127.0.0.1', port=int(os.environ.get('METAS_TEST_FIREBIRD_PORT', main.app.config['DB_PORT'])),
                            user=os.environ.get('METAS_TEST_FIREBIRD_USER', 'SYSDBA'),
                            password=os.environ.get('METAS_TEST_FIREBIRD_PASSWORD', os.environ.get('DB_PASSWORD', main.app.config['DB_PASSWORD'])), database=str(self.db), charset='UTF8')
        con = firebirdsql.create_database(**self.options); cur = con.cursor(); self.addCleanup(self.drop)
        try:
            cur.execute('CREATE TABLE USUARIO(ID_USUARIO INTEGER PRIMARY KEY,TIPO INTEGER,ATIVO INTEGER)')
            cur.execute('''CREATE TABLE FUNCIONARIO(ID_FUNCIONARIO INTEGER PRIMARY KEY,ID_BARBEARIA INTEGER,NOME VARCHAR(100),
                ATIVO INTEGER,ID_USUARIO_LOGIN INTEGER,EMAIL VARCHAR(100),TELEFONE VARCHAR(20),COMISSAO_PERCENTUAL DECIMAL(5,2),
                COMISSAO_TIPO VARCHAR(20),COMISSAO_VALOR DECIMAL(12,2))''')
            cur.execute('''CREATE TABLE AGENDAMENTO(ID_AGENDAMENTO INTEGER PRIMARY KEY,ID_BARBEARIA INTEGER,
                ID_FUNCIONARIO INTEGER,INICIO_EM TIMESTAMP,FIM_EM TIMESTAMP,STATUS VARCHAR(20),VALOR_TOTAL DECIMAL(12,2))''')
            con.commit()
            for row in ((10, 2, 1), (11, 2, 1), (20, 1, 1), (30, 3, 1), (31, 3, 1), (99, 0, 1)):
                cur.execute('INSERT INTO USUARIO VALUES(?,?,?)', row)
            for row in ((1, 10, 'Ana', 1, 30), (2, 10, 'Bia', 1, 31), (3, 11, 'Outro salão', 1, None), (4, 10, 'Inativa', 0, None)):
                cur.execute('INSERT INTO FUNCIONARIO(ID_FUNCIONARIO,ID_BARBEARIA,NOME,ATIVO,ID_USUARIO_LOGIN) VALUES(?,?,?,?,?)', row)
            past = datetime.now()-timedelta(days=2); future = datetime.now()+timedelta(days=2)
            for row in ((1, 10, 1, past, 'concluido', '100.10'), (2, 10, 1, past, 'concluido', None),
                        (3, 10, 1, past, 'cancelado', '999'), (4, 10, 1, past, 'faltou', '999'),
                        (5, 10, 1, past, 'remarcado', '999'), (6, 10, 1, future, 'concluido', '999'),
                        (7, 10, 2, past, 'concluido', '500'), (8, 11, 3, past, 'concluido', '999')):
                id_, salon, fun, start, status, total = row
                cur.execute('INSERT INTO AGENDAMENTO VALUES(?,?,?,?,?,?,?)', (id_, salon, fun, start, start+timedelta(minutes=30), status, total))
            con.commit()
            cur.execute('SELECT * FROM AGENDAMENTO ORDER BY ID_AGENDAMENTO'); self.original = cur.fetchall()
        finally: cur.close(); con.close()
        with patch.object(metas_schema, 'conectar_banco', side_effect=self.connect):
            metas_schema.migrar_metas(); metas_schema.migrar_metas()
        self.client = main.app.test_client()
        self.addCleanup(patch.stopall)
        patch.object(agenda_gestao, 'conectar_banco', side_effect=self.connect).start()
        patch.object(agenda_gestao, 'registrar_log').start()
        self.start = (date.today()-timedelta(days=3)).isoformat(); self.end = (date.today()+timedelta(days=3)).isoformat()
        self.query = f'?inicio={self.start}&fim={self.end}'

    def connect(self): return firebirdsql.connect(**self.options)
    def drop(self):
        if self.db.exists():
            con = self.connect(); con.drop_database(); con.close()
    def user(self, id_, role): return patch.object(agenda_gestao, 'decodificar_token', return_value={'id_usuario': id_, 'tipo': role})
    def data(self, **overrides): return {'id_funcionario': 1, 'tipo': 'faturamento', 'alvo': '200.20', 'inicio': self.start, 'fim': self.end} | overrides
    def create(self, **overrides):
        with self.user(10, 2): response = self.client.post('/gestao/metas', json=self.data(**overrides))
        self.assertEqual(response.status_code, 200, response.get_json()); return response.get_json()['meta']

    def test_repeated_migration_and_crud_preserve_bookings_history(self):
        meta = self.create(); id_ = meta['id_meta']
        self.assertEqual((meta['realizado'], meta['percentual'], meta['sem_valor_historico']), (100.1, 50, 1))
        with self.user(10, 2):
            response = self.client.put(f'/gestao/metas/{id_}', json=self.data(tipo='atendimentos', alvo=2))
            self.assertEqual(response.status_code, 200); changed = response.get_json()['meta']
            self.assertEqual(changed['realizado'], 2); self.assertTrue(changed['atingida'])
            self.assertEqual(changed['criado_em'], meta['criado_em'])
            for ativo in (False, True):
                result = self.client.patch(f'/gestao/metas/{id_}', json={'ativo': ativo})
                self.assertEqual(result.status_code, 200); self.assertEqual(result.get_json()['meta']['ativo'], ativo)
            result = self.client.get('/gestao/metas'+self.query).get_json()
            self.assertEqual(len(result['metas']), 1)
        con = self.connect(); cur = con.cursor()
        try:
            cur.execute('SELECT * FROM AGENDAMENTO ORDER BY ID_AGENDAMENTO'); self.assertEqual(cur.fetchall(), self.original)
        finally: cur.close(); con.close()

    def test_owner_admin_professional_isolation_and_write_denial(self):
        first = self.create(); self.create(id_funcionario=2)
        with self.user(11, 2):
            self.assertEqual(self.client.get('/gestao/metas'+self.query).get_json()['metas'], [])
            self.assertEqual(self.client.patch(f"/gestao/metas/{first['id_meta']}", json={'ativo': False}).status_code, 404)
        with self.user(10, 2):
            self.assertEqual(self.client.post('/gestao/metas', json=self.data(id_funcionario=3)).status_code, 404)
            self.assertEqual(self.client.get('/gestao/metas'+self.query+'&id_funcionario=3').status_code, 404)
        with self.user(99, 0):
            self.assertEqual(self.client.get('/gestao/metas').status_code, 400)
            self.assertEqual(len(self.client.get('/gestao/metas'+self.query+'&id_barbearia=10').get_json()['metas']), 2)
        with self.user(30, 3):
            own = self.client.get('/painel-barbeiro/metas'+self.query)
            self.assertEqual(own.status_code, 200); self.assertEqual([r['id_funcionario'] for r in own.get_json()['metas']], [1])
            self.assertEqual(self.client.get('/painel-barbeiro/metas'+self.query+'&id_funcionario=2').status_code, 403)
            self.assertEqual(self.client.get('/painel-barbeiro/metas'+self.query+'&id_barbearia=11').status_code, 403)
            self.assertEqual(self.client.post('/gestao/metas', json=self.data()).status_code, 403)
        with self.user(20, 1): self.assertEqual(self.client.get('/painel-barbeiro/metas').status_code, 403)

    def test_missing_totals_do_not_guess_revenue_and_zero_period(self):
        meta = self.create(tipo='atendimentos', alvo=4)
        self.assertEqual((meta['realizado'], meta['percentual']), (2, 50))
        empty = self.create(inicio=(date.today()+timedelta(days=40)).isoformat(), fim=(date.today()+timedelta(days=50)).isoformat())
        self.assertEqual((empty['realizado'], empty['percentual'], empty['sem_valor_historico']), (0, 0, 0))
        with self.user(10, 2):
            self.assertEqual(len(self.client.get('/gestao/metas'+self.query).get_json()['metas']), 1)

    def test_inactive_goal_visible_history_but_inactive_professional_cannot_reactivate(self):
        meta = self.create(); id_ = meta['id_meta']
        with self.user(10, 2): self.assertEqual(self.client.patch(f'/gestao/metas/{id_}', json={'ativo': False}).status_code, 200)
        con = self.connect(); cur = con.cursor()
        cur.execute('UPDATE FUNCIONARIO SET ATIVO=0 WHERE ID_FUNCIONARIO=1'); con.commit(); cur.close(); con.close()
        with self.user(10, 2):
            result = self.client.get('/gestao/metas'+self.query).get_json()['metas'][0]
            self.assertFalse(result['ativo']); self.assertEqual(result['realizado'], 100.1)
            self.assertEqual(self.client.patch(f'/gestao/metas/{id_}', json={'ativo': True}).status_code, 400)
            self.assertEqual(self.client.post('/gestao/metas', json=self.data(id_funcionario=4)).status_code, 400)
        with self.user(30, 3): self.assertEqual(self.client.get('/painel-barbeiro/metas').status_code, 403)

    def test_failed_write_rolls_back_without_partial_goal_or_audit(self):
        with self.user(10, 2), patch.object(agenda_gestao, 'registrar_log') as audit:
            response = self.client.post('/gestao/metas', json=self.data(alvo='NaN'))
            self.assertEqual(response.status_code, 400); audit.assert_not_called()
            self.assertEqual(self.client.get('/gestao/metas'+self.query).get_json()['metas'], [])


if __name__ == '__main__': unittest.main()
