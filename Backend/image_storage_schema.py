"""Image references only; binary image data stays in the configured provider."""
from application import conectar_banco
from schema_utils import criar_tabela


TABLES = {
    'IMAGE_ASSET': '''CREATE TABLE IMAGE_ASSET (
        NOME VARCHAR(100) NOT NULL, AREA VARCHAR(40) NOT NULL,
        PROVIDER VARCHAR(20) NOT NULL, FILE_ID VARCHAR(200) NOT NULL,
        OWNER_ID INTEGER, SLOT VARCHAR(80), MIME VARCHAR(40) NOT NULL,
        LARGURA INTEGER NOT NULL, ALTURA INTEGER NOT NULL,
        TAMANHO INTEGER NOT NULL, SHA256 CHAR(64) NOT NULL,
        ATIVO SMALLINT DEFAULT 1 NOT NULL,
        CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (AREA,NOME))''',
    'IMAGE_SLOT': '''CREATE TABLE IMAGE_SLOT (
        AREA VARCHAR(40) NOT NULL, OWNER_ID INTEGER NOT NULL,
        SLOT VARCHAR(80) NOT NULL, NOME VARCHAR(100),
        PRIMARY KEY (AREA,OWNER_ID,SLOT))''',
}


def migrar_imagens():
    con = conectar_banco(); cur = con.cursor()
    try:
        for name, ddl in TABLES.items():
            criar_tabela(cur, name, ddl, con)
        con.commit()
    except Exception:
        con.rollback(); raise
    finally:
        cur.close(); con.close()
