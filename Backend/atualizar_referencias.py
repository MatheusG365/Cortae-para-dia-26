"""Apply reviewed catalog URLs, preserving a rollback journal outside the project.

Preview: python atualizar_referencias.py
Apply: python atualizar_referencias.py --aplicar --backup-dir C:\\path\\backups
This script changes only IMAGEM_ROTA and never downloads image files.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from application import app, conectar_banco


def atualizar(manifesto, aplicar=False, backup_dir=None):
    referencias = json.loads(Path(manifesto).read_text(encoding='utf-8'))
    if not isinstance(referencias, list) or not referencias:
        raise ValueError('O manifesto deve conter referências revisadas.')
    ids = [item['id_corte'] for item in referencias]
    if len(ids) != len(set(ids)):
        raise ValueError('O manifesto contém IDs repetidos.')
    from visagismo import validar_url_imagem
    con = conectar_banco()
    cursor = con.cursor()
    try:
        alteracoes = []
        for item in referencias:
            url = item['imagem_url']
            if not isinstance(url, str) or len(url) > 255:
                raise ValueError('A URL deve caber no campo IMAGEM_ROTA (255 caracteres).')
            validar_url_imagem(url)
            cursor.execute('SELECT NOME, IMAGEM_ROTA, ATIVO FROM CORTE_VISAGISMO WHERE ID_CORTE=?', (item['id_corte'],))
            atual = cursor.fetchone()
            if atual is None or atual[0] != item['nome'] or not atual[2]:
                raise ValueError(f"O corte {item['id_corte']} não corresponde ao catálogo revisado.")
            if atual[1] == url:
                continue
            # Existing working references are deliberate user data. Do not replace them.
            antiga = atual[1]
            if antiga and (str(antiga).startswith(('http://', 'https://'))
                           or (Path(app.config['VISAGISMO_CORTES_FOLDER']) / antiga).is_file()):
                raise ValueError(f"O corte {item['id_corte']} já possui referência. Revise antes de substituir.")
            alteracoes.append({'id_corte': item['id_corte'], 'nome': atual[0],
                               'imagem_antes': antiga, 'imagem_depois': url,
                               'fonte_url': item['fonte_url']})
        if not aplicar or not alteracoes:
            return {'alteracoes': len(alteracoes), 'aplicado': False, 'backup': None}
        if not backup_dir:
            raise ValueError('Informe --backup-dir para preservar os valores anteriores.')
        pasta_backup = Path(backup_dir).resolve()
        projeto = Path(__file__).resolve().parent.parent
        if pasta_backup == projeto or projeto in pasta_backup.parents:
            raise ValueError('Guarde o backup fora do projeto.')
        pasta_backup.mkdir(parents=True, exist_ok=True)
        instante = datetime.now(timezone.utc)
        backup = pasta_backup / f"referencias-cortes-{instante.strftime('%Y%m%d-%H%M%S-%f')}.json"
        registro = {'criado_em_utc': instante.isoformat(),
                    'operacao': 'Atualização autorizada de referências ausentes do catálogo',
                    'estado': 'preparado', 'alteracoes': alteracoes}
        with backup.open('x', encoding='utf-8') as arquivo:
            json.dump(registro, arquivo, ensure_ascii=False, indent=2)
        for item in alteracoes:
            parametros = [item['imagem_depois'], item['id_corte'], item['nome']]
            condicao = 'IMAGEM_ROTA IS NULL'
            if item['imagem_antes'] is not None:
                condicao = 'IMAGEM_ROTA=?'
                parametros.append(item['imagem_antes'])
            cursor.execute('UPDATE CORTE_VISAGISMO SET IMAGEM_ROTA=? '
                           f'WHERE ID_CORTE=? AND NOME=? AND ATIVO=1 AND {condicao}', parametros)
            if cursor.rowcount != 1:
                raise ValueError('O catálogo mudou durante a atualização. Nenhum valor foi aplicado.')
        con.commit()
        registro['estado'] = 'aplicado'
        backup.write_text(json.dumps(registro, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        return {'alteracoes': len(alteracoes), 'aplicado': True, 'backup': str(backup)}
    except Exception:
        con.rollback()
        raise
    finally:
        cursor.close()
        con.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifesto', default=str(Path(__file__).with_name('catalogo_referencias.json')))
    parser.add_argument('--aplicar', action='store_true')
    parser.add_argument('--backup-dir')
    args = parser.parse_args()
    with app.app_context():
        print(json.dumps(atualizar(args.manifesto, args.aplicar, args.backup_dir), ensure_ascii=False))
