"""Conferência sem escrita; --aplicar executa as atualizações explicitamente."""
import argparse
from application import app, conectar_banco
from database import pendencias_estrutura


def conferir():
    con = conectar_banco()
    cur = con.cursor()
    try:
        pendencias = pendencias_estrutura(cur)
        if pendencias:
            print('Estrutura pendente: ' + ', '.join(pendencias))
            print('Restaure o banco base ou aplique as atualizações após fazer backup.')
            return 1
        print('Estrutura conferida. Nenhuma alteração realizada.')
        return 0
    finally:
        cur.close()
        con.close()


def aplicar():
    # DDL só é importado na manutenção solicitada pelo operador.
    from .visagismo_schema import migrar_visagismo
    from .financeiro_schema import migrar_financeiro
    from .database_schema import inicializar_banco
    from .agenda_schema import migrar_agenda, migrar_gestao_agenda
    from .gestao_schema import migrar_gestao
    from .ranking_schema import migrar_ranking_avaliacoes
    from .metas_schema import migrar_metas
    from .marketplace_schema import migrar_marketplace
    from .termos_schema import migrar_termos_taxa
    from .image_storage_schema import migrar_imagens
    from .arkhe_cartao_schema import migrar_cartao
    for atualizar in (migrar_visagismo, migrar_financeiro, inicializar_banco,
                      migrar_agenda, migrar_gestao_agenda, migrar_gestao,
                      migrar_ranking_avaliacoes, migrar_metas, migrar_marketplace,
                      migrar_termos_taxa, migrar_imagens, migrar_cartao):
        atualizar()
    return conferir()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Conferir o banco existente; não cria tabelas por padrão.')
    parser.add_argument('--aplicar', action='store_true', help='Aplicar atualizações no banco existente. Faça backup antes.')
    args = parser.parse_args(argv)
    with app.app_context():
        return aplicar() if args.aplicar else conferir()


if __name__ == '__main__':
    raise SystemExit(main())
