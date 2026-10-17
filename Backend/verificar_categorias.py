"""Consulta manual de categorias usando a configuração privada do backend."""
import firebirdsql
import config


def main():
    con = firebirdsql.connect(
        host=config.DB_HOST, port=config.DB_PORT, database=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASSWORD, charset='UTF8')
    cur = None
    try:
        cur = con.cursor()
        print("=== CATEGORIAS DOS CORTES ===")
        cur.execute("SELECT CATEGORIA, COUNT(*) FROM CORTE_VISAGISMO GROUP BY CATEGORIA ORDER BY CATEGORIA")
        for categoria, quantidade in cur.fetchall():
            print(f"  {categoria}: {quantidade}")
    finally:
        if cur is not None:
            cur.close()
        con.close()


if __name__ == '__main__':
    main()
