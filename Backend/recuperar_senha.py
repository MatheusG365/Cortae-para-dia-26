from responses import mensagem_json
from contact_utils import email_sem_espacos
from flask import request, jsonify


from application import app, conectar_banco

from funcoes import (
    verificar_senha_forte,
    criptografar_senha,
    gerar_codigo_verificacao,
    enviando_email,
)
from auditoria import capturar_registro, registrar_registro


# ==========================================
# RECUPERAR SENHA
# ==========================================

@app.route('/recuperar-senha', methods=['POST'])
def recuperar_senha():

    con = None

    try:

        dados = request.get_json(
            silent=True
        )

        if not dados:

            return mensagem_json('Envie os dados em formato JSON.', 'erro'), 400

        # ==========================================
        # PEGAR ETAPA
        # ==========================================

        etapa = dados.get('etapa')

        if etapa is None:

            return mensagem_json('A etapa é obrigatória.', 'erro'), 400

        try:

            etapa = int(etapa)

        except (ValueError, TypeError):

            return mensagem_json('Etapa inválida.', 'erro'), 400

        if etapa not in [1, 2, 3]:

            return mensagem_json('A etapa deve ser 1, 2 ou 3.', 'erro'), 400


        # ==================================================
        # ETAPA 1
        # INFORMAR EMAIL E ENVIAR CÓDIGO
        # ==================================================

        if etapa == 1:

            email = dados.get('email')
            if isinstance(email, str):
                email = email_sem_espacos(email)

            if not email:

                return mensagem_json('E-mail é obrigatório.', 'erro'), 400

            con = conectar_banco()

            cursor = con.cursor()

            cursor.execute(
                '''
                SELECT
                    ID_USUARIO,
                    NOME,
                    ATIVO
                FROM USUARIO
                WHERE EMAIL = ?
                ''',
                (email,)
            )

            usuario = cursor.fetchone()

            if not usuario:

                return mensagem_json('E-mail não encontrado.', 'erro'), 404

            id_usuario = usuario[0]
            nome = usuario[1]
            ativo = usuario[2]

            # ==========================================
            # GERAR CÓDIGO
            # ==========================================

            codigo = gerar_codigo_verificacao()

            # ==========================================
            # SALVAR CÓDIGO
            # ==========================================

            dados_antes_log = capturar_registro(
                cursor, 'USUARIO', 'ID_USUARIO', id_usuario
            )

            cursor.execute(
                '''
                UPDATE USUARIO
                SET CODIGO_VERIFICACAO = ?
                WHERE ID_USUARIO = ?
                ''',
                (
                    codigo,
                    id_usuario
                )
            )

            con.commit()
            registrar_registro(
                cursor, 'UPDATE', 'USUARIO', 'ID_USUARIO', id_usuario,
                dados_antes=dados_antes_log, id_usuario=id_usuario
            )

            cursor.close()
            con.close()

            con = None

            # ==========================================
            # ENVIAR EMAIL
            # ==========================================

            email_enviado = enviando_email(
                destinatario=email,
                assunto='Recuperação de senha - Cortaê',
                mensagem=(
                    'Recebemos uma solicitação '
                    'para recuperar sua senha.'
                ),
                codigo=codigo,
                nome=nome,
                mensagem_secundaria=(
                    'Use o código abaixo para continuar '
                    'a recuperação da sua senha.'
                )
            )

            if not email_enviado:

                return mensagem_json('Não foi possível enviar o código para o e-mail.', 'erro'), 500

            return jsonify({
                'mensagem':
                    {"informacao":'Código enviado para o seu e-mail.',"tipo":"sucesso"},
                'etapa':
                    2
            }), 200


        # ==================================================
        # ETAPA 2
        # VERIFICAR CÓDIGO
        # ==================================================

        if etapa == 2:

            email = dados.get('email')
            codigo = dados.get('codigo')
            if isinstance(email, str):
                email = email_sem_espacos(email)
            if codigo is not None:
                codigo = str(codigo).strip()

            if not email:

                return mensagem_json('E-mail é obrigatório.', 'erro'), 400

            if not codigo:

                return mensagem_json('Código é obrigatório.', 'erro'), 400

            con = conectar_banco()

            cursor = con.cursor()

            cursor.execute(
                '''
                SELECT
                    ID_USUARIO,
                    CODIGO_VERIFICACAO
                FROM USUARIO
                WHERE EMAIL = ?
                ''',
                (email,)
            )

            usuario = cursor.fetchone()

            if not usuario:

                return mensagem_json('Usuário não encontrado.', 'erro'), 404

            id_usuario = usuario[0]
            codigo_banco = usuario[1]

            # ==========================================
            # COMPARAR CÓDIGO
            # ==========================================

            if str(codigo) != str(codigo_banco):

                return mensagem_json('Código de recuperação inválido.', 'erro'), 400

            # ==========================================
            # CÓDIGO CORRETO
            # ==========================================

            return jsonify({
                'mensagem':
                    'Código confirmado com sucesso.',
                'etapa':
                    3
            }), 200


        # ==================================================
        # ETAPA 3
        # NOVA SENHA
        # ==================================================

        if etapa == 3:

            email = dados.get('email')
            codigo = dados.get('codigo')
            senha = dados.get('senha')
            if isinstance(email, str):
                email = email_sem_espacos(email)
            if codigo is not None:
                codigo = str(codigo).strip()
            confirmar_senha = dados.get(
                'confirmarSenha'
            )

            # ==========================================
            # VALIDAR CAMPOS
            # ==========================================

            if not email:

                return mensagem_json('E-mail é obrigatório.', 'erro'), 400

            if not codigo:

                return mensagem_json('Código é obrigatório.', 'erro'), 400

            if not senha:

                return mensagem_json('Nova senha é obrigatória.', 'erro'), 400

            if not confirmar_senha:

                return mensagem_json('Confirmação da senha é obrigatória.', 'erro'), 400

            # ==========================================
            # CONFIRMAR SENHAS
            # ==========================================

            if senha != confirmar_senha:

                return mensagem_json('As senhas não coincidem.', 'erro'), 400

            # ==========================================
            # VERIFICAR SENHA FORTE
            # ==========================================

            senha_valida, mensagem_senha = (
                verificar_senha_forte(senha)
            )

            if not senha_valida:

                return jsonify({
                    'erro':
                        mensagem_senha
                }), 400

            # ==========================================
            # CONECTAR BANCO
            # ==========================================

            con = conectar_banco()

            cursor = con.cursor()

            # ==========================================
            # BUSCAR USUÁRIO
            # ==========================================

            cursor.execute(
                '''
                SELECT
                    ID_USUARIO,
                    SENHA_HASH,
                    CODIGO_VERIFICACAO
                FROM USUARIO
                WHERE EMAIL = ?
                ''',
                (email,)
            )

            usuario = cursor.fetchone()

            if not usuario:

                return mensagem_json('Usuário não encontrado.', 'erro'), 404

            id_usuario = usuario[0]
            senha_atual = usuario[1]
            codigo_banco = usuario[2]

            # ==========================================
            # VALIDAR CÓDIGO NOVAMENTE
            # ==========================================

            if str(codigo) != str(codigo_banco):

                return mensagem_json('Código de recuperação inválido.', 'erro'), 400

            # ==========================================
            # CRIPTOGRAFAR NOVA SENHA
            # ==========================================

            nova_senha_hash = criptografar_senha(
                senha
            )

            dados_antes_log = capturar_registro(
                cursor, 'USUARIO', 'ID_USUARIO', id_usuario
            )

            # ==========================================
            # HISTÓRICO DE SENHAS
            #
            # SENHA_HASH atual -> SENHA_2
            # SENHA_2 antiga   -> SENHA_3
            # ==========================================

            cursor.execute(
                '''
                UPDATE USUARIO
                SET
                    SENHA3 = SENHA2,
                    SENHA2 = SENHA_HASH,
                    SENHA_HASH = ?,
                    CODIGO_VERIFICACAO = NULL
                WHERE ID_USUARIO = ?
                ''',
                (
                    nova_senha_hash,
                    id_usuario
                )
            )

            con.commit()
            registrar_registro(
                cursor, 'UPDATE', 'USUARIO', 'ID_USUARIO', id_usuario,
                dados_antes=dados_antes_log, id_usuario=id_usuario
            )

            return jsonify({
                'mensagem':
                    'Senha alterada com sucesso!',
                'etapa':
                    3
            }), 200


    except Exception as erro:

        if con:

            con.rollback()

        print(
            'ERRO AO RECUPERAR SENHA:',
            erro
        )

        return jsonify({
            'mensagem': {'informacao': 'Erro interno no servidor.', 'tipo': 'erro'},
            'detalhes':
                str(erro)
        }), 500

    finally:

        if con:

            con.close()
