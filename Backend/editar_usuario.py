from responses import mensagem_json
from contact_utils import digitos_telefone
import os

from flask import (
    request,
    jsonify,
    send_from_directory,
    current_app
)

from application import (
    app,
    conectar_banco
)

from funcoes import (
    verificar_senha_forte,
    criptografar_senha,
    decodificar_token,
    salvar_foto_perfil,
    buscar_foto_perfil
)
from auditoria import capturar_registro, registrar_registro, registrar_log
from image_storage import ImageBatch, ImageStorageError, serve_image, slot_state


# ==========================================================
# BUSCAR DADOS DO PERFIL
# ==========================================================

@app.route(
    '/dados-perfil/<int:id_usuario>',
    methods=['GET']
)
def dados_perfil(id_usuario):

    con = None
    cursor = None

    try:
        # ==================================================
        # VERIFICAR TOKEN
        # ==================================================

        token_data = decodificar_token()

        if not token_data:

            return mensagem_json('Token necessário. Faça login novamente.', 'erro'), 401

        # ==================================================
        # ID DO TOKEN
        # ==================================================

        try:

            id_token = int(
                token_data.get(
                    'id_usuario'
                )
            )

        except Exception:

            return mensagem_json('Token inválido.', 'erro'), 401

        # ==================================================
        # TIPO DO USUÁRIO
        # ==================================================

        try:

            tipo_token = int(
                token_data.get(
                    'tipo',
                    1
                )
            )

        except Exception:

            tipo_token = 1

        # ==================================================
        # VERIFICAR PERMISSÃO
        # ==================================================

        if (
                id_token != id_usuario
                and tipo_token != 0
        ):

            return mensagem_json('Você não pode acessar este perfil.', 'erro'), 403

        # ==================================================
        # CONECTAR BANCO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()

        # ==================================================
        # BUSCAR USUÁRIO
        # ==================================================

        cursor.execute(
            '''
            SELECT
                ID_USUARIO,
                NOME,
                EMAIL,
                TELEFONE,
                TIPO,
                GENERO
            FROM USUARIO
            WHERE ID_USUARIO = ?
            ''',
            (
                id_usuario,
            )
        )

        usuario = cursor.fetchone()

        # ==================================================
        # USUÁRIO NÃO ENCONTRADO
        # ==================================================

        if not usuario:

            return mensagem_json('Usuário não encontrado.', 'erro'), 404

        # ==================================================
        # BUSCAR FOTO
        # ==================================================

        foto_perfil = buscar_foto_perfil(
            id_usuario, cursor=cursor
        )

        # ==================================================
        # RESPOSTA
        # ==================================================

        resposta = {

            'usuario': {

                'id_usuario':
                    usuario[0],

                'id':
                    usuario[0],

                'nome':
                    usuario[1] or '',

                'email':
                    usuario[2] or '',

                'telefone':
                    usuario[3] or '',

                'tipo':
                    int(usuario[4] or 0),

                'genero':
                    usuario[5] or '',

                'foto_perfil':
                    foto_perfil

            }

        }

        return jsonify(
            resposta
        ), 200

    except Exception as erro:

        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao buscar dados do perfil.',

                'tipo':
                    'erro'

            },

            'detalhes':
                str(erro)

        }), 500

    finally:

        if cursor:

            try:

                cursor.close()

            except Exception:

                pass

        if con:

            try:

                con.close()

            except Exception:

                pass


# ==========================================================
# EDITAR USUÁRIO
# ==========================================================

@app.route(
    '/editar-usuario/<int:id_usuario>',
    methods=['PUT']
)
def editar_usuario(id_usuario):

    con = None
    cursor = None
    image_batch = None

    try:

        # ==================================================
        # VERIFICAR TOKEN
        # ==================================================

        token_data = decodificar_token()

        if not token_data:

            return mensagem_json('Token necessário. Faça login novamente.', 'erro'), 401

        # ==================================================
        # ID DO TOKEN
        # ==================================================

        try:

            id_token = int(
                token_data.get(
                    'id_usuario'
                )
            )

        except Exception:

            return mensagem_json('Token inválido.', 'erro'), 401

        # ==================================================
        # TIPO DO TOKEN
        # ==================================================

        try:

            tipo_token = int(
                token_data.get(
                    'tipo',
                    1
                )
            )

        except Exception:

            tipo_token = 1

        # ==================================================
        # VERIFICAR PERMISSÃO
        # ==================================================

        if (
                id_token != id_usuario
                and tipo_token != 0
        ):

            return mensagem_json('Você só pode editar seu próprio perfil.', 'erro'), 403

        # ==================================================
        # RECEBER DADOS
        # ==================================================

        nome = request.form.get(
            'nome'
        )

        email = request.form.get(
            'email'
        )

        telefone = request.form.get(
            'telefone'
        )

        senha = request.form.get(
            'senha'
        )

        foto = request.files.get(
            'foto'
        )

        genero = request.form.get(
            'genero'
        )

        # ==================================================
        # CONECTAR BANCO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()

        # ==================================================
        # BUSCAR USUÁRIO
        # ==================================================

        cursor.execute(
            '''
            SELECT
                ID_USUARIO,
                NOME,
                EMAIL,
                TELEFONE,
                SENHA_HASH,
                TIPO,
                GENERO
            FROM USUARIO
            WHERE ID_USUARIO = ?
            ''',
            (
                id_usuario,
            )
        )

        usuario = cursor.fetchone()

        # ==================================================
        # VERIFICAR USUÁRIO
        # ==================================================

        if not usuario:

            return mensagem_json('Usuário não encontrado.', 'erro'), 404

        # ==================================================
        # DADOS ANTIGOS
        # ==================================================

        nome_antigo = usuario[1]

        email_antigo = usuario[2]

        telefone_antigo = usuario[3]

        senha_hash = usuario[4]
        tipo_usuario = int(usuario[5] or -1)
        genero_atual = usuario[6]

        # Gênero é uma informação do perfil de cliente. Para os demais
        # perfis, preservamos o valor já salvo independentemente do formulário.
        if tipo_usuario == 1:
            genero = str(genero or '').strip().lower()
            if genero not in ('', 'masculino', 'feminino', 'outro'):
                return mensagem_json('Gênero inválido.', 'erro'), 400
        else:
            genero = genero_atual

        # ==================================================
        # MANTER DADOS ANTIGOS
        # ==================================================

        if (
                nome is None
                or not str(nome).strip()
        ):

            nome = nome_antigo

        if (
                email is None
                or not str(email).strip()
        ):

            email = email_antigo

        if (
                telefone is None
                or not str(telefone).strip()
        ):

            telefone = telefone_antigo

        # ==================================================
        # LIMPAR NOME
        # ==================================================

        nome = ' '.join(
            str(nome)
            .strip()
            .split()
        )

        # ==================================================
        # LIMPAR EMAIL
        # ==================================================

        email = (
            str(email)
            .strip()
            .replace(
                ' ',
                ''
            )
            .lower()
        )

        # ==================================================
        # LIMPAR TELEFONE
        # ==================================================

        telefone = str(
            telefone
        ).strip()

        telefone_numeros = digitos_telefone(telefone)

        # ==================================================
        # VALIDAR NOME
        # ==================================================

        if not nome:

            return mensagem_json('Nome é obrigatório.', 'erro'), 400

        # ==================================================
        # VALIDAR EMAIL
        # ==================================================

        if not email:

            return mensagem_json('E-mail é obrigatório.', 'erro'), 400

        # ==================================================
        # VALIDAR TELEFONE
        # ==================================================

        if len(telefone_numeros) not in (
                10,
                11
        ):

            return mensagem_json('Telefone inválido.', 'erro'), 400

        # ==================================================
        # VERIFICAR EMAIL DUPLICADO
        # ==================================================

        if email.lower() != str(
                email_antigo
        ).lower():

            cursor.execute(
                '''
                SELECT
                    ID_USUARIO
                FROM USUARIO
                WHERE LOWER(EMAIL) = ?
                  AND ID_USUARIO <> ?
                ''',
                (
                    email.lower(),
                    id_usuario
                )
            )

            email_existente = (
                cursor.fetchone()
            )

            if email_existente:

                return mensagem_json('Este e-mail já está cadastrado.', 'erro'), 409

        # ==================================================
        # ALTERAR SENHA
        # ==================================================

        if (
                senha
                and senha.strip()
        ):

            senha = senha.strip()

            senha_valida, mensagem_senha = (
                verificar_senha_forte(
                    senha
                )
            )

            if not senha_valida:

                return mensagem_json(mensagem_senha, 'erro'), 400

            senha_hash = (
                criptografar_senha(
                    senha
                )
            )

        # ==================================================
        # ATUALIZAR BANCO
        # ==================================================

        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (id_usuario,))
        cursor.fetchone()
        dados_antes_log = capturar_registro(
            cursor, 'USUARIO', 'ID_USUARIO', id_usuario
        )
        foto_perfil_antiga = buscar_foto_perfil(id_usuario, cursor=cursor)

        cursor.execute(
            '''
            UPDATE USUARIO
            SET
                NOME = ?,
                EMAIL = ?,
                TELEFONE = ?,
                SENHA_HASH = ?,
                GENERO = ?
            WHERE ID_USUARIO = ?
            ''',
            (
                nome,
                email,
                telefone_numeros,
                senha_hash,
                genero if genero else None,
                id_usuario
            )
        )

        # ==================================================
        # SALVAR FOTO
        # ==================================================

        if foto:

            image_batch = ImageBatch(cursor)
            salvar_foto_perfil(foto, id_usuario, image_batch)

        # ==================================================
        # COMMIT
        # ==================================================

        con.commit()
        if image_batch:
            image_batch.commit()

        registrar_registro(
            cursor,
            'UPDATE',
            'USUARIO',
            'ID_USUARIO',
            id_usuario,
            dados_antes=dados_antes_log,
            id_usuario=id_token
        )

        # ==================================================
        # BUSCAR FOTO ATUAL
        # ==================================================

        foto_perfil = buscar_foto_perfil(
            id_usuario, cursor=cursor
        )

        if foto and foto_perfil_antiga != foto_perfil:
            registrar_log(
                'UPDATE',
                'USUARIO',
                id_registro=id_usuario,
                id_usuario=id_token,
                campo='FOTO_PERFIL',
                valor_antes=foto_perfil_antiga,
                valor_depois=foto_perfil
            )

        # ==================================================
        # RESPOSTA
        # ==================================================

        resposta = {

            'mensagem': {

                'informacao':
                    'Usuário editado com sucesso!',

                'tipo':
                    'sucesso'

            },

            'usuario': {

                'id_usuario':
                    id_usuario,

                'id':
                    id_usuario,

                'nome':
                    nome,

                'email':
                    email,

                'telefone':
                    telefone_numeros,

                'tipo':
                    tipo_usuario,

                'genero':
                    genero if tipo_usuario == 1 else None,

                'foto_perfil':
                    foto_perfil

            }

        }

        return jsonify(
            resposta
        ), 200

    # ======================================================
    # ERRO DE VALIDAÇÃO
    # ======================================================

    except ImageStorageError as erro:
        if con:
            con.rollback()
        return mensagem_json(str(erro), 'erro'), erro.status

    except ValueError as erro:

        if con:

            try:

                con.rollback()

            except Exception:

                pass

        return mensagem_json(str(erro), 'erro'), 400

    # ======================================================
    # ERRO GERAL
    # ======================================================

    except Exception as erro:

        if con:

            try:

                con.rollback()

            except Exception:

                pass

        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao editar usuário.',

                'tipo':
                    'erro'

            },

            'detalhes':
                str(erro)

        }), 500

    finally:
        if image_batch:
            image_batch.abort()

        if cursor:

            try:

                cursor.close()

            except Exception:

                pass

        if con:

            try:

                con.close()

            except Exception:

                pass


# ==========================================================
# SERVIR FOTOS DE PERFIL
# ==========================================================
#
# Estrutura:
#
# uploads/
# └── perfil/
#     ├── 1.jpg
#     ├── 2.png
#     └── 3.webp
#
# URL:
#
# /uploads/perfil/1.jpg
#
# ==========================================================

@app.route(
    '/uploads/perfil/<path:nome_arquivo>',
    methods=['GET']
)
def servir_foto_perfil(nome_arquivo):
    return servir_imagem_perfil(nome_arquivo)


def servir_imagem_perfil(nome_arquivo):
    """Keep both legacy public profile URLs and the new database proxy usable."""
    import re
    if os.path.basename(nome_arquivo) != nome_arquivo:
        return mensagem_json('Nome de arquivo inválido.', 'erro'), 400
    legacy = re.fullmatch(r'(\d+)\.(?:jpg|jpeg|png|webp)', nome_arquivo, re.I)
    if legacy:
        managed, image = slot_state('perfil', int(legacy.group(1)), 'profile')
        if managed:
            if not image:
                return mensagem_json('Foto não encontrada.', 'erro'), 404
            nome_arquivo = image.filename
    return serve_image('perfil', nome_arquivo,
                       legacy_folder=current_app.config.get('PERFIL_FOLDER'))


# ==========================================================
# EXCLUIR FOTO DE PERFIL
# ==========================================================

@app.route(
    '/excluir-foto-perfil/<int:id_usuario>',
    methods=['DELETE']
)
def excluir_foto_perfil(id_usuario):
    con = cursor = image_batch = None
    try:
        token_data = decodificar_token()
        if not token_data:
            return mensagem_json('Token necessário. Faça login novamente.', 'erro'), 401
        try:
            id_token = int(token_data.get('id_usuario'))
            tipo_token = int(token_data.get('tipo', 1))
        except (TypeError, ValueError):
            return mensagem_json('Token inválido.', 'erro'), 401
        if id_token != id_usuario and tipo_token != 0:
            return mensagem_json('Você só pode excluir sua própria foto.', 'erro'), 403
        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (id_usuario,))
        if not cursor.fetchone():
            return mensagem_json('Usuário não encontrado.', 'erro'), 404
        previous = buscar_foto_perfil(id_usuario, cursor=cursor)
        if not previous:
            return jsonify({'mensagem': {'informacao': 'Este usuário não possui uma foto de perfil.',
                                        'tipo': 'erro'},
                            'usuario': {'id_usuario': id_usuario, 'foto_perfil': None}}), 404
        image_batch = ImageBatch(cursor)
        image_batch.delete('perfil', id_usuario, 'profile')
        con.commit()
        image_batch.commit()
        registrar_log('DELETE', 'USUARIO', id_registro=id_usuario, id_usuario=id_token,
                      campo='FOTO_PERFIL', valor_antes=previous, valor_depois=None)
        return jsonify({'mensagem': {'informacao': 'Foto de perfil excluída com sucesso!', 'tipo': 'sucesso'},
                        'usuario': {'id_usuario': id_usuario, 'id': id_usuario, 'foto_perfil': None}}), 200
    except ImageStorageError as erro:
        if con:
            con.rollback()
        return mensagem_json(str(erro), 'erro'), erro.status
    except Exception:
        if con:
            con.rollback()
        current_app.logger.exception('Erro ao excluir foto de perfil.')
        return mensagem_json('Erro ao excluir foto de perfil.', 'erro'), 500
    finally:
        if image_batch:
            image_batch.abort()
        if cursor:
            cursor.close()
        if con:
            con.close()
