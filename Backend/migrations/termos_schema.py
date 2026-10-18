"""Additive terms acceptance records; never fabricate acceptance for old accounts."""
from application import conectar_banco
from .schema_utils import criar_tabela


def migrar_termos_taxa():
    con = conectar_banco(); cur = con.cursor()
    try:
        criar_tabela(cur, 'TERMO_ACEITE', '''CREATE TABLE TERMO_ACEITE (
                ID_USUARIO INTEGER NOT NULL REFERENCES USUARIO(ID_USUARIO),
                VERSAO VARCHAR(60) NOT NULL, DOCUMENTO_HASH CHAR(64) NOT NULL,
                DOCUMENTO BLOB SUB_TYPE TEXT NOT NULL,
                ACEITO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                PRIMARY KEY(ID_USUARIO,VERSAO))''', con)
        criar_tabela(cur, 'PLATAFORMA_TAXA', '''CREATE TABLE PLATAFORMA_TAXA (
                TIPO VARCHAR(15) NOT NULL, ID_OPERACAO INTEGER NOT NULL,
                ID_ATOR INTEGER NOT NULL REFERENCES USUARIO(ID_USUARIO),
                ID_CLIENTE INTEGER NOT NULL REFERENCES USUARIO(ID_USUARIO),
                ID_BARBEARIA INTEGER NOT NULL REFERENCES USUARIO(ID_USUARIO),
                VALOR_BASE DECIMAL(12,2) NOT NULL,FRETE DECIMAL(12,2) NOT NULL,
                PERCENTUAL DECIMAL(5,2) NOT NULL,VALOR_TAXA DECIMAL(12,2) NOT NULL,
                PAGADOR VARCHAR(15) NOT NULL,TOTAL_CLIENTE DECIMAL(12,2) NOT NULL,
                LIQUIDO_BARBEARIA DECIMAL(12,2) NOT NULL,TERMOS_VERSAO VARCHAR(60) NOT NULL,
                CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                PRIMARY KEY(TIPO,ID_OPERACAO))''', con)
    except Exception:
        con.rollback(); raise
    finally:
        cur.close(); con.close()
