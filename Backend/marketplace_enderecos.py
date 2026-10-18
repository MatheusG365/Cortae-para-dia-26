"""Customer-owned delivery address book; orders keep their own snapshots."""
from flask import jsonify, request

from application import app
from gestao import erro, texto
import cep
import marketplace as mp


def _endereco(row):
    return {'id_endereco': row[0], 'apelido': row[1],
            'padrao': bool(row[2]), 'dados': mp.loads(row[3], {})}


@app.get('/marketplace/cep/<postal_code>')
@mp.protected()
def marketplace_cep(user, salon, cur, con, postal_code):
    return jsonify(endereco=cep.consultar(postal_code))


@app.get('/gestao/marketplace/cep/<postal_code>')
@mp.protected('owner')
def marketplace_cep_remetente(user, salon, cur, con, postal_code):
    return jsonify(endereco=cep.consultar(postal_code))


@app.get('/marketplace/enderecos')
@mp.protected()
def marketplace_enderecos(user, salon, cur, con):
    cur.execute('SELECT ID_ENDERECO,APELIDO,PADRAO,DADOS FROM MP_ENDERECO '
                'WHERE ID_USUARIO=? ORDER BY PADRAO DESC,ATUALIZADO_EM DESC,ID_ENDERECO DESC',
                (user['id_usuario'],))
    return jsonify(enderecos=[_endereco(row) for row in cur.fetchall()])


def _salvar(user, cur, con, id_endereco=None):
    raw = mp.body()
    data = mp.address(raw.get('endereco'))
    # Match lookup input constraints and reject nonexistent Brazilian states.
    cep.normalizar(raw['endereco'].get('cep'))
    if data['uf'] not in cep.UFS:
        raise ValueError('UF inválida.')
    nickname = texto(raw.get('apelido'), 80, 'Apelido')
    uid = user['id_usuario']
    mp.lock_user(cur, uid)
    cur.execute('SELECT ID_ENDERECO,PADRAO FROM MP_ENDERECO WHERE ID_USUARIO=? ORDER BY ID_ENDERECO', (uid,))
    rows = cur.fetchall()
    existing = next((row for row in rows if row[0] == id_endereco), None)
    if id_endereco is not None and existing is None:
        return erro('Endereço não encontrado.', 404)
    default = mp.boolean(raw.get('padrao', bool(existing and existing[1])))
    if not rows or len(rows) == 1 and existing:
        default = True
    elif not any(row[1] for row in rows):
        default = True
    if default:
        cur.execute('UPDATE MP_ENDERECO SET PADRAO=0 WHERE ID_USUARIO=? AND PADRAO=1', (uid,))
    elif existing and existing[1]:
        # Moving the default away from an edited address retains one default.
        replacement = next(row[0] for row in rows if row[0] != id_endereco)
        cur.execute('UPDATE MP_ENDERECO SET PADRAO=1 WHERE ID_ENDERECO=? AND ID_USUARIO=?', (replacement, uid))
    if id_endereco is None:
        id_endereco = mp.next_id(cur, 'SEQ_MP_ENDERECO')
        cur.execute('INSERT INTO MP_ENDERECO(ID_ENDERECO,ID_USUARIO,APELIDO,PADRAO,DADOS) VALUES(?,?,?,?,?)',
                    (id_endereco, uid, nickname, int(default), mp.dumps(data)))
        status = 201
    else:
        cur.execute('UPDATE MP_ENDERECO SET APELIDO=?,PADRAO=?,DADOS=?,ATUALIZADO_EM=CURRENT_TIMESTAMP '
                    'WHERE ID_ENDERECO=? AND ID_USUARIO=?',
                    (nickname, int(default), mp.dumps(data), id_endereco, uid))
        status = 200
    con.commit()
    return jsonify(endereco=_endereco((id_endereco, nickname, default, mp.dumps(data)))), status


@app.post('/marketplace/enderecos')
@mp.protected()
def marketplace_endereco_criar(user, salon, cur, con):
    return _salvar(user, cur, con)


@app.put('/marketplace/enderecos/<int:id_endereco>')
@mp.protected()
def marketplace_endereco_editar(user, salon, cur, con, id_endereco):
    return _salvar(user, cur, con, id_endereco)
