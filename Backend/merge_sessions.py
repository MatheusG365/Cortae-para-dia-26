"""Preserve missing visagismo sessions from a retired database.

Usage: python merge_sessions.py SOURCE.FDB
Existing rows are checked byte-for-byte; conflicts abort the transaction.
"""
import argparse
import hashlib
import json
import firebirdsql
from application import app
from database import conectar_banco, alinhar_sequence


def fingerprint(rows):
    payload = json.dumps(rows, default=str, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def merge(source_path):
    src = dst = cs = cd = None
    try:
        src = firebirdsql.connect(host=app.config['DB_HOST'], port=app.config['DB_PORT'],
                                  database=source_path, user=app.config['DB_USER'],
                                  password=app.config['DB_PASSWORD'], charset='UTF8')
        dst = conectar_banco()
        cs, cd = src.cursor(), dst.cursor()
        cs.execute('SELECT * FROM VISAGISMO_SESSAO ORDER BY ID_VISAGISMO')
        columns = [column[0].strip() for column in cs.description]
        source_rows = cs.fetchall()
        cd.execute('SELECT * FROM VISAGISMO_SESSAO ORDER BY ID_VISAGISMO')
        if columns != [column[0].strip() for column in cd.description]:
            raise RuntimeError('Schemas differ; merge aborted.')
        target_rows = cd.fetchall()
        id_index = columns.index('ID_VISAGISMO')
        existing = {row[id_index]: row for row in target_rows}
        missing = []
        for row in source_rows:
            if row[id_index] in existing:
                if tuple(row) != tuple(existing[row[id_index]]):
                    raise RuntimeError('Conflicting session ID; merge aborted.')
            else:
                missing.append(row)
        sql = 'INSERT INTO VISAGISMO_SESSAO (' + ', '.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')'
        for row in missing:
            cd.execute(sql, row)
        cd.execute('SELECT * FROM VISAGISMO_SESSAO ORDER BY ID_VISAGISMO')
        after_rows = cd.fetchall()
        after = {row[id_index]: row for row in after_rows}
        if any(tuple(after[row[id_index]]) != tuple(row) for row in source_rows + target_rows):
            raise RuntimeError('Verification failed; merge aborted.')
        alinhar_sequence(dst, cd, 'SEQ_VISAGISMO_SESSAO', 'VISAGISMO_SESSAO', 'ID_VISAGISMO')
        dst.commit()
        return {'inserted': len(missing), 'total': len(after_rows),
                'source_sha256': fingerprint(source_rows), 'target_sha256': fingerprint(after_rows)}
    except Exception:
        if dst is not None:
            dst.rollback()
        raise
    finally:
        for cursor in (cs, cd):
            if cursor is not None:
                cursor.close()
        for con in (src, dst):
            if con is not None:
                con.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    args = parser.parse_args()
    with app.app_context():
        print(json.dumps(merge(args.source)))
