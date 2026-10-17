"""Additive and repeatable team/booking migration. Run only after DB backup."""
from application import conectar_banco
from schema_utils import criar_tabela, criar_sequence, criar_coluna


def migrar_agenda():
    con = conectar_banco(); cur = con.cursor()
    try:
        for name, kind in [('ID_BARBEARIA', 'INTEGER'), ('ID_USUARIO_LOGIN', 'INTEGER'),
                           ('EMAIL', 'VARCHAR(254)'), ('TELEFONE', 'VARCHAR(30)'),
                           ('ATIVO', 'SMALLINT DEFAULT 1'), ('COMISSAO_PERCENTUAL', 'DECIMAL(5,2) DEFAULT 0')]:
            criar_coluna(cur, 'FUNCIONARIO', name, kind, con)
        for name, kind in [('VALOR_TOTAL', 'DECIMAL(12,2)'), ('DURACAO_MINUTOS', 'INTEGER'),
                           ('SERVICOS_SNAPSHOT', 'BLOB SUB_TYPE TEXT')]:
            criar_coluna(cur, 'AGENDAMENTO', name, kind, con)
        for name, kind in [('ID_FUNCIONARIO', 'INTEGER'), ('INICIO_ANTES', 'TIMESTAMP'), ('FIM_ANTES', 'TIMESTAMP'),
                           ('INICIO_DEPOIS', 'TIMESTAMP'), ('FIM_DEPOIS', 'TIMESTAMP')]:
            criar_coluna(cur, 'AGENDAMENTO_HISTORICO', name, kind, con)
        criar_tabela(cur, 'BARBEIRO_CONVITE', '''CREATE TABLE BARBEIRO_CONVITE (
            ID_CONVITE INTEGER NOT NULL PRIMARY KEY, ID_FUNCIONARIO INTEGER NOT NULL,
            TOKEN_HASH CHAR(64) NOT NULL UNIQUE, EXPIRA_EM TIMESTAMP NOT NULL,
            UTILIZADO_EM TIMESTAMP, CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)''', con)
        criar_tabela(cur, 'COMISSAO_ATENDIMENTO', '''CREATE TABLE COMISSAO_ATENDIMENTO (
            ID_AGENDAMENTO INTEGER NOT NULL PRIMARY KEY, ID_FUNCIONARIO INTEGER NOT NULL,
            ID_BARBEARIA INTEGER NOT NULL, VALOR_BASE DECIMAL(12,2) NOT NULL,
            PERCENTUAL DECIMAL(5,2) NOT NULL, VALOR_COMISSAO DECIMAL(12,2) NOT NULL,
            REGISTRADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)''', con)
        criar_tabela(cur, 'LISTA_ESPERA', '''CREATE TABLE LISTA_ESPERA (
            ID_ESPERA INTEGER NOT NULL PRIMARY KEY, ID_USUARIO INTEGER NOT NULL,
            ID_BARBEARIA INTEGER NOT NULL, ID_FUNCIONARIO INTEGER, INICIO_EM TIMESTAMP NOT NULL,
            FIM_EM TIMESTAMP NOT NULL, SERVICOS_JSON BLOB SUB_TYPE TEXT NOT NULL,
            ID_CORTE INTEGER, ID_VISAGISMO INTEGER, STATUS VARCHAR(20) DEFAULT 'aguardando' NOT NULL,
            CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL, NOTIFICADO_EM TIMESTAMP)''', con)
        criar_tabela(cur, 'EMAIL_OUTBOX', '''CREATE TABLE EMAIL_OUTBOX (
            ID_EMAIL INTEGER NOT NULL PRIMARY KEY, CHAVE VARCHAR(100) NOT NULL UNIQUE,
            ID_ESPERA INTEGER, DESTINATARIO VARCHAR(254) NOT NULL, NOME VARCHAR(100),
            ASSUNTO VARCHAR(180) NOT NULL, MENSAGEM BLOB SUB_TYPE TEXT NOT NULL,
            ESTADO VARCHAR(20) DEFAULT 'pendente' NOT NULL, TENTATIVAS INTEGER DEFAULT 0 NOT NULL,
            PROXIMA_TENTATIVA TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            ENVIADO_EM TIMESTAMP, CRIADO_EM TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL)''', con)
        for seq in ['SEQ_BARBEIRO_CONVITE', 'SEQ_LISTA_ESPERA', 'SEQ_EMAIL_OUTBOX']:
            criar_sequence(cur, seq, con)
        # Existing staff gain explicit ownership without changing IDs or bookings.
        cur.execute('''UPDATE FUNCIONARIO F SET ID_BARBEARIA=(
            SELECT MIN(D.ID_USUARIO) FROM FUNCIONARIO_DIA FD JOIN DIAS_DE_SERVICO D ON D.ID_DIA=FD.ID_DIA
            WHERE FD.ID_FUNCIONARIO=F.ID_FUNCIONARIO) WHERE ID_BARBEARIA IS NULL''')
        cur.execute('UPDATE FUNCIONARIO SET ATIVO=1 WHERE ATIVO IS NULL')
        cur.execute('UPDATE FUNCIONARIO SET COMISSAO_PERCENTUAL=0 WHERE COMISSAO_PERCENTUAL IS NULL')
        # Historical booking price cannot be reconstructed reliably: keep NULL,
        # dashboard states this explicitly instead of inventing earned revenue.
        con.commit()
    except Exception:
        con.rollback(); raise
    finally:
        cur.close(); con.close()


def migrar_gestao_agenda():
    """Add individual schedules and durable notifications without rewriting history."""
    con = conectar_banco(); cur = con.cursor()
    try:
        for tabela, nome, tipo in [
            ('AGENDAMENTO','ESCOLHA_CORTE','VARCHAR(20)'),
            ('LISTA_ESPERA','ESCOLHA_CORTE','VARCHAR(20)'),
            ('SERVICO','ATIVO','SMALLINT DEFAULT 1 NOT NULL'),
            ('FUNCIONARIO','COMISSAO_TIPO',"VARCHAR(12) DEFAULT 'percentual' NOT NULL"),
            ('FUNCIONARIO','COMISSAO_VALOR','DECIMAL(12,2) DEFAULT 0 NOT NULL'),
            ('FUNCIONARIO','HORARIOS_CONFIGURADOS','SMALLINT DEFAULT 0 NOT NULL'),
            ('COMISSAO_ATENDIMENTO','TIPO',"VARCHAR(12) DEFAULT 'percentual' NOT NULL"),
            ('COMISSAO_ATENDIMENTO','VALOR_CONFIGURADO','DECIMAL(12,2)'),
            ('EMAIL_OUTBOX','ID_AGENDAMENTO','INTEGER'),
            ('EMAIL_OUTBOX','EVENTO','VARCHAR(20)'),
            ('EMAIL_OUTBOX','INICIO_REFERENCIA','TIMESTAMP')]:
            criar_coluna(cur, tabela, nome, tipo, con)
        tabelas = {
            'AGENDA_CONFIG': '''CREATE TABLE AGENDA_CONFIG (ID_BARBEARIA INTEGER NOT NULL PRIMARY KEY,
                CANCELAMENTO_HORAS INTEGER DEFAULT 0 NOT NULL, REAGENDAMENTO_HORAS INTEGER DEFAULT 0 NOT NULL,
                LEMBRETE_HORAS INTEGER DEFAULT 24 NOT NULL)''',
            'FUNCIONARIO_HORARIO': '''CREATE TABLE FUNCIONARIO_HORARIO (ID_HORARIO INTEGER NOT NULL PRIMARY KEY,
                ID_FUNCIONARIO INTEGER NOT NULL, DIA VARCHAR(15) NOT NULL, INICIO TIME NOT NULL, FIM TIME NOT NULL)''',
            'FUNCIONARIO_PRECO': '''CREATE TABLE FUNCIONARIO_PRECO (ID_FUNCIONARIO INTEGER NOT NULL,
                ID_SERVICO INTEGER NOT NULL, PRECO DECIMAL(12,2) NOT NULL, PRIMARY KEY(ID_FUNCIONARIO,ID_SERVICO))''',
            'AGENDA_BLOQUEIO': '''CREATE TABLE AGENDA_BLOQUEIO (ID_BLOQUEIO INTEGER NOT NULL PRIMARY KEY,
                ID_BARBEARIA INTEGER NOT NULL, ID_FUNCIONARIO INTEGER, INICIO_EM TIMESTAMP NOT NULL,
                FIM_EM TIMESTAMP NOT NULL, MOTIVO VARCHAR(200) NOT NULL)'''}
        for nome, ddl in tabelas.items():
            criar_tabela(cur, nome, ddl, con)
        for nome in ('SEQ_FUNCIONARIO_HORARIO','SEQ_AGENDA_BLOQUEIO'):
            criar_sequence(cur, nome, con)
        con.commit()
    except Exception:
        con.rollback(); raise
    finally:
        cur.close(); con.close()


if __name__ == '__main__':
    from application import app
    with app.app_context():
        migrar_agenda()
        migrar_gestao_agenda()
    print('Migração da agenda aplicada.')
