"""Preparação manual das estruturas de visagismo e agendamento."""
from application import conectar_banco
from .schema_utils import criar_tabela, criar_sequence, criar_coluna


def migrar_visagismo():
    con = conectar_banco()
    cursor = con.cursor()

    try:
        criar_tabela(cursor, 'CORTE_VISAGISMO', '''
                                                               CREATE TABLE CORTE_VISAGISMO (
                                                                                                ID_CORTE INTEGER NOT NULL PRIMARY KEY,
                                                                                                ID_USUARIO INTEGER,
                                                                                                NOME VARCHAR(150) NOT NULL,
                                                                                                DESCRICAO BLOB SUB_TYPE TEXT,
                                                                                                CATEGORIA VARCHAR(30) NOT NULL,
                                                                                                IMAGEM_ROTA VARCHAR(255),
                                                                                                ATIVO SMALLINT DEFAULT 1 NOT NULL,
                                                                                                CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                                                               )
                                                               ''')

        criar_tabela(cursor, 'VISAGISMO_SESSAO', '''
                                                                CREATE TABLE VISAGISMO_SESSAO (
                                                                                                  ID_VISAGISMO INTEGER NOT NULL PRIMARY KEY,
                                                                                                  ID_USUARIO INTEGER NOT NULL,
                                                                                                  ID_BARBEARIA INTEGER,
                                                                                                  SERVICOS_JSON BLOB SUB_TYPE TEXT,
                                                                                                  FOTO_ROTA VARCHAR(255),
                                                                                                  ANALISE_JSON BLOB SUB_TYPE TEXT,
                                                                                                  CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                                                                )
                                                                ''')

        criar_tabela(cursor, 'AGENDAMENTO', '''
                                                           CREATE TABLE AGENDAMENTO (
                                                                                        ID_AGENDAMENTO INTEGER NOT NULL PRIMARY KEY,
                                                                                        ID_USUARIO INTEGER NOT NULL,
                                                                                        ID_BARBEARIA INTEGER NOT NULL,
                                                                                        ID_FUNCIONARIO INTEGER,
                                                                                        INICIO_EM TIMESTAMP NOT NULL,
                                                                                        FIM_EM TIMESTAMP NOT NULL,
                                                                                        SERVICOS_JSON BLOB SUB_TYPE TEXT,
                                                                                        ID_CORTE INTEGER,
                                                                                        ID_VISAGISMO INTEGER,
                                                                                        STATUS VARCHAR(20) DEFAULT 'agendado' NOT NULL,
                                                                                        CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                                                           )
                                                           ''')

        criar_tabela(cursor, 'AGENDAMENTO_HISTORICO', '''
                                                                      CREATE TABLE AGENDAMENTO_HISTORICO (
                                                                          ID_HISTORICO INTEGER NOT NULL PRIMARY KEY,
                                                                          ID_AGENDAMENTO INTEGER NOT NULL,
                                                                          STATUS VARCHAR(20) NOT NULL,
                                                                          ID_USUARIO_RESPONSAVEL INTEGER,
                                                                          REGISTRADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                                                                      )
                                                                      ''')

        for sequencia in (
                'SEQ_CORTE_VISAGISMO',
                'SEQ_VISAGISMO_SESSAO',
                'SEQ_AGENDAMENTO',
                'SEQ_AGENDAMENTO_HISTORICO'
        ):
            criar_sequence(cursor, sequencia)

        # Migração: bancos criados antes da escolha de barbeiro não têm a coluna.
        criar_coluna(cursor, 'AGENDAMENTO', 'ID_FUNCIONARIO', 'INTEGER')

        # A simulação gerada por IA fica registrada na sessão para o agendamento exibir.
        for coluna, tipo_col in (('ID_CORTE_SIMULADO', 'INTEGER'), ('RESULTADO_ROTA', 'VARCHAR(255)')):
            criar_coluna(cursor, 'VISAGISMO_SESSAO', coluna, tipo_col)

        # Campo GENERO na tabela USUARIO para filtro de cortes por gênero
        criar_coluna(cursor, 'USUARIO', 'GENERO', 'VARCHAR(10)')

        # Campo GENERO na tabela CORTE_VISAGISMO para filtro de cortes por gênero
        criar_coluna(cursor, 'CORTE_VISAGISMO', 'GENERO', 'VARCHAR(10)')

        # Campos PIX/Arkhe na tabela PERSONALIZACAO
        for coluna, tipo_col in (('CHAVE_PIX', 'VARCHAR(100)'), ('ARKHE_CLIENT_ID', 'VARCHAR(100)'), ('ARKHE_CLIENT_SECRET', 'VARCHAR(200)')):
            criar_coluna(cursor, 'PERSONALIZACAO', coluna, tipo_col)

        con.commit()

    except Exception:
        con.rollback()
        raise

    finally:
        cursor.close()
        con.close()
