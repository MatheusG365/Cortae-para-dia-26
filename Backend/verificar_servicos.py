"""Consulta manual de serviços usando a configuração privada do backend."""
import firebirdsql
import config


def main():
    con = firebirdsql.connect(
        host=config.DB_HOST, port=config.DB_PORT, database=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASSWORD, charset='UTF8')
    cur = None
    try:
        cur = con.cursor()
        print("=== SERVIÇOS CADASTRADOS ===")
        cur.execute("SELECT ID_SERVICO, ID_USUARIO, NOME_SERVICO, PRECO, DURACAO FROM SERVICO ORDER BY ID_SERVICO")
        for row in cur.fetchall():
            print(f"  ID={row[0]}, Barbearia={row[1]}, Nome={row[2]}, Preço={row[3]}, Duração={row[4]}")
        print("\n=== CORTES CADASTRADOS ===")
        cur.execute("SELECT COUNT(*) FROM CORTE_VISAGISMO WHERE ATIVO = 1")
        print(f"Total de cortes ativos: {cur.fetchone()[0]}")
    finally:
        if cur is not None:
            cur.close()
        con.close()


if __name__ == '__main__':
    main()
