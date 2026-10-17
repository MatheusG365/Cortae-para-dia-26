"""Anonymous storefront presentation never reads or writes private account data."""
import os
os.environ['STARTUP_MIGRATIONS'] = 'false'
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import main
import marketplace as mp
from marketplace_perfil import business_images, PROFILE_FIELDS
import test_marketplace_firebird as fixture


class StoreProfileValidation(unittest.TestCase):
    def test_invalid_ids_and_write_methods_do_not_open_database(self):
        client = main.app.test_client()
        with patch.object(mp, 'conectar_banco') as connect:
            for id_ in ('0', '2147483648', '99999999999999999999999'):
                self.assertEqual(client.get('/marketplace/barbearias/'+id_+'/perfil').status_code, 404)
            for method in ('post', 'put', 'patch', 'delete'):
                self.assertEqual(getattr(client, method)('/marketplace/barbearias/10/perfil', json={}).status_code, 405)
        connect.assert_not_called()

    def test_profile_request_has_no_authentication_or_commit_and_closes_connection(self):
        con = MagicMock()
        with patch.object(mp, 'conectar_banco', return_value=con), \
             patch.object(mp, 'obter_usuario_logado', side_effect=AssertionError('Public route must not read session')), \
             patch('marketplace_perfil.public_profile', return_value={'nome_barbearia':'QA'}) as profile:
            response = main.app.test_client().get('/marketplace/barbearias/10/perfil?id_usuario=11')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile.call_args.args[1], 10)
        con.commit.assert_not_called(); con.cursor.return_value.close.assert_called_once(); con.close.assert_called_once()

    def test_missing_assets_folder_is_not_created_and_only_business_names_are_read(self):
        with TemporaryDirectory() as directory, main.app.app_context(), \
             patch.dict(main.app.config, IMAGE_STORAGE_PROVIDER='local'):
            self.assertEqual(business_images(directory, 10), (None, []))
            folder = Path(directory)/'barbearia'; self.assertFalse(folder.exists())
            folder.mkdir()
            (folder/'10.png').write_bytes(b'qa'); (folder/'10_2.webp').write_bytes(b'qa')
            (folder/'11.jpg').write_bytes(b'other'); (folder/'10_private.png').write_bytes(b'private')
            self.assertEqual(business_images(directory, 10), ('/uploads/barbearia/10.png', [{'numero':2,'url':'/uploads/barbearia/10_2.webp'}]))


@unittest.skipUnless(os.environ.get('RUN_FIREBIRD_MARKETPLACE_TESTS') == '1', 'isolated Firebird opt-in')
class StoreProfileFirebird(unittest.TestCase):
    connect = fixture.MarketplaceFirebird.connect
    drop = fixture.MarketplaceFirebird.drop
    as_user = fixture.MarketplaceFirebird.as_user

    def setUp(self):
        fixture.MarketplaceFirebird.setUp(self)
        con = self.connect(); cur = con.cursor()
        try:
            for sql in (
                'ALTER TABLE USUARIO ADD EMAIL VARCHAR(100)',
                'ALTER TABLE USUARIO ADD SENHA VARCHAR(100)',
                'ALTER TABLE USUARIO ADD TELEFONE VARCHAR(30)',
                '''CREATE TABLE PERSONALIZACAO(ID_USUARIO INTEGER, COR_PRIMARIA VARCHAR(20),COR_SECUNDARIA VARCHAR(20),
                    COR_TERCIARIA VARCHAR(20),COR_TEXTO_PRIMARIO VARCHAR(20),COR_TEXTO_SECUNDARIO VARCHAR(20),TEXTO BLOB SUB_TYPE TEXT,
                    LOCALIZACAO VARCHAR(200),CONTATO_TELEFONE VARCHAR(30),CONTATO_EMAIL VARCHAR(100),INSTAGRAM VARCHAR(100),
                    NUM_FUNCIONARIOS INTEGER,CHAVE_PIX VARCHAR(100),ARKHE_CLIENT_ID VARCHAR(100),ARKHE_CLIENT_SECRET VARCHAR(100))''',
                '''CREATE TABLE SERVICO(ID_SERVICO INTEGER,NOME_SERVICO VARCHAR(100),PRECO DECIMAL(12,2),DURACAO INTEGER,
                    DESCRICAO_BREVE VARCHAR(100),GENERO VARCHAR(20),ID_USUARIO INTEGER,ATIVO SMALLINT)''',
                '''CREATE TABLE DIAS_DE_SERVICO(ID_DIA INTEGER,DIAS VARCHAR(20),ENTRADA_MANHA TIME,SAIDA_MANHA TIME,
                    ENTRADA_TARDE TIME,SAIDA_TARDE TIME,ID_USUARIO INTEGER)''',
                '''CREATE TABLE FUNCIONARIO(ID_FUNCIONARIO INTEGER,ID_BARBEARIA INTEGER,NOME VARCHAR(100),DESCRICAO VARCHAR(100),
                    ATIVO SMALLINT,EMAIL VARCHAR(100),TELEFONE VARCHAR(100),COMISSAO_PERCENTUAL DECIMAL(5,2),ID_USUARIO_LOGIN INTEGER)''',
                'CREATE TABLE SERVICO_POR_FUNCIONARIO(ID_SERVI_FUNCI INTEGER,ID_FUNCIONARIO INTEGER,ID_SERVICO INTEGER)',
                'CREATE TABLE FUNCIONARIO_DIA(ID_FUNCIONARIO INTEGER,ID_DIA INTEGER)',
            ):
                cur.execute(sql); con.commit()
            cur.execute("UPDATE USUARIO SET EMAIL='private-login@example.invalid',SENHA='private-password',TELEFONE='private-phone'")
            cur.execute("""INSERT INTO PERSONALIZACAO VALUES(10,'#112233','#ddeeff','#456789','#123456','#654321',
                'História pública','Rua pública','11999999999','business@example.invalid','salao',99,'private-pix','private-client','private-secret')""")
            for row in ((1,'Corte',25,30,'Corte público','unissex',10,1), (2,'Inativo',10,10,'Oculto','unissex',10,0), (3,'Outro salão',15,10,'Outro','unissex',11,1)):
                cur.execute('INSERT INTO SERVICO VALUES(?,?,?,?,?,?,?,?)', row)
            for salon in (10,11):
                cur.execute("INSERT INTO DIAS_DE_SERVICO VALUES(?,'segunda','08:00','12:00','13:00','18:00',?)", (salon,salon))
            for row in ((1,10,'Ana','Especialista',1), (2,10,'Inativa','Oculta',0), (3,11,'Outra','Outro salão',1)):
                cur.execute('''INSERT INTO FUNCIONARIO VALUES(?,?,?,?,?, 'private-staff@example.invalid','private-staff-phone',55,900)''',row)
            for service in (1,2,3):
                cur.execute('INSERT INTO SERVICO_POR_FUNCIONARIO VALUES(?,?,?)',(service,1,service))
            for salon in (10,11):
                cur.execute('INSERT INTO FUNCIONARIO_DIA VALUES(1,?)',(salon,))
            con.commit()
        finally:
            cur.close(); con.close()

    def snapshot(self):
        con=self.connect(); cur=con.cursor()
        try:
            result={}
            for table in ('USUARIO','PERSONALIZACAO','SERVICO','FUNCIONARIO','DIAS_DE_SERVICO','SERVICO_POR_FUNCIONARIO','FUNCIONARIO_DIA'):
                cur.execute('SELECT * FROM '+table); result[table]=cur.fetchall()
            return result
        finally:
            cur.close(); con.close()

    def test_anonymous_profile_whitelist_scope_and_unchanged_database(self):
        before=self.snapshot()
        with patch.object(mp,'obter_usuario_logado',side_effect=AssertionError('No session read')):
            response=self.client.get('/marketplace/barbearias/10/perfil?id_usuario=11&id_barbearia=11')
        self.assertEqual(response.status_code,200,response.get_json()); data=response.get_json()
        self.assertEqual(set(data),{'nome_barbearia','personalizado','personalizacao','servicos','funcionarios','dias_servico','logo','fotos'})
        self.assertEqual(data['nome_barbearia'],'Salão QA'); self.assertTrue(data['personalizado'])
        self.assertEqual(set(data['personalizacao']),set(PROFILE_FIELDS))
        self.assertEqual(data['personalizacao']['historia'],'História pública')
        self.assertEqual(data['personalizacao']['contato_email'],'business@example.invalid')
        self.assertEqual(data['personalizacao']['num_funcionarios'],1)
        self.assertEqual([s['id_servico'] for s in data['servicos']],[1])
        self.assertEqual([d['id_dia'] for d in data['dias_servico']],[10])
        self.assertEqual(data['funcionarios'],[{'id_funcionario':1,'nome':'Ana','descricao':'Especialista','servicos':[1],'dias':[10]}])
        self.assertNotIn('private-',response.get_data(as_text=True))
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.client.get('/barbearia/personalizacao?id_usuario=10').status_code,401)

    def test_unconfigured_shop_exists_without_private_account_data(self):
        response=self.client.get('/marketplace/barbearias/11/perfil')
        self.assertEqual(response.status_code,200); data=response.get_json()
        self.assertEqual(data['nome_barbearia'],'Outro QA'); self.assertFalse(data['personalizado'])
        self.assertIsNone(data['personalizacao']); self.assertEqual(data['funcionarios'],[]); self.assertEqual(data['servicos'],[])
        self.assertNotIn('private-',response.get_data(as_text=True))

    def test_only_confirmed_active_business_accounts_are_public(self):
        for id_ in (0,20,30,99999):
            self.assertEqual(self.client.get(f'/marketplace/barbearias/{id_}/perfil').status_code,404)
        con=self.connect(); cur=con.cursor()
        try:
            for column in ('ATIVO','EMAIL_CONFIRMADO'):
                cur.execute(f'UPDATE USUARIO SET {column}=0 WHERE ID_USUARIO=10'); con.commit()
                self.assertEqual(self.client.get('/marketplace/barbearias/10/perfil').status_code,404)
                cur.execute(f'UPDATE USUARIO SET {column}=1 WHERE ID_USUARIO=10'); con.commit()
        finally:
            cur.close(); con.close()


if __name__ == '__main__': unittest.main()
