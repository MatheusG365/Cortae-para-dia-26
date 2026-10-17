from responses import mensagem_json
from flask import jsonify, request, make_response
import jwt
from datetime import datetime, timedelta

from application import app, conectar_banco

from funcoes import (
    verificar_senha,
    gerar_codigo_verificacao,
    enviando_email
)
from auditoria import capturar_registro, registrar_registro, registrar_log


# ==========================================================
# LOGIN
# ==========================================================

@app.route('/login', methods=['POST'])
def login():

    con = None
    cursor = None

    try:

        # ==================================================
        # RECEBER JSON
        # ==================================================

        dados = request.get_json(silent=True)

        if not dados:

            return mensagem_json('Dados não enviados.', 'erro'), 400


        # ==================================================
        # PEGAR DADOS
        # ==================================================

        email = dados.get('email')
        senha = dados.get('senha')


        if isinstance(email, str):

            email = (
                email
                .strip()
                .replace(' ', '')
            )


        # ==================================================
        # VALIDAR EMAIL
        # ==================================================

        if not email:

            return mensagem_json('O email é obrigatório.', 'erro'), 400


        # ==================================================
        # VALIDAR SENHA
        # ==================================================

        if not senha:

            return mensagem_json('A senha é obrigatória.', 'erro'), 400


        # ==================================================
        # CONECTAR AO BANCO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()


        # ==================================================
        # BUSCAR USUÁRIO
        # ==================================================

        cursor.execute("""
            SELECT
                ID_USUARIO,
                NOME,
                EMAIL,
                TELEFONE,
                SENHA_HASH,
                TIPO,
                ATIVO,
                EMAIL_CONFIRMADO,
                TENTATIVA,
                GENERO
            FROM USUARIO
            WHERE EMAIL = ?
        """, (
            email,
        ))


        usuario = cursor.fetchone()


        # ==================================================
        # USUÁRIO NÃO ENCONTRADO
        # ==================================================

        if not usuario:

            return mensagem_json('Email ou senha incorretos.', 'erro'), 401


        # ==================================================
        # DADOS DO USUÁRIO
        # ==================================================

        id_usuario = usuario[0]
        nome = usuario[1]
        email_banco = usuario[2]
        telefone = usuario[3]
        senha_hash = usuario[4]
        tipo = usuario[5]
        ativo = usuario[6]
        email_confirmado = usuario[7]
        tentativas = usuario[8] or 0

        dados_usuario_log = capturar_registro(
            cursor, 'USUARIO', 'ID_USUARIO', id_usuario
        )


        # ==================================================
        # VERIFICAR EMAIL
        # ==================================================

        if int(tipo) == 3 and email_confirmado != 1:
            return mensagem_json('Ative seu acesso pelo convite enviado pela barbearia.', 'aviso'), 403

        if email_confirmado != 1:

            codigo = gerar_codigo_verificacao()


            # ==================================================
            # SALVAR CÓDIGO
            # ==================================================

            cursor.execute("""
                UPDATE USUARIO
                SET CODIGO_VERIFICACAO = ?
                WHERE ID_USUARIO = ?
            """, (
                codigo,
                id_usuario
            ))

            con.commit()
            registrar_registro(
                cursor, 'UPDATE', 'USUARIO', 'ID_USUARIO', id_usuario,
                dados_antes=dados_usuario_log, id_usuario=id_usuario
            )


            # ==================================================
            # ENVIAR EMAIL
            # ==================================================

            email_enviado = enviando_email(
                destinatario=email_banco,
                assunto='Confirmação de cadastro - Cortaê',
                mensagem='Seu cadastro foi realizado com sucesso!',
                codigo=codigo,
                nome=nome,
                mensagem_secundaria=(
                    'Utilize o código abaixo para confirmar '
                    'seu endereço de e-mail.'
                )
            )


            if not email_enviado:

                return mensagem_json('Seu e-mail ainda não foi confirmado, mas não foi possível enviar o código de verificação.', 'erro'), 500


            return jsonify({

                'mensagem': {
                    'informacao': (
                        'Seu e-mail ainda não foi confirmado. '
                        'Um novo código de verificação foi enviado '
                        'para seu e-mail.'
                    ),
                    'tipo': 'aviso'
                },

                'email_confirmacao': True

            }), 403


        # ==================================================
        # VERIFICAR USUÁRIO BLOQUEADO
        # ==================================================

        if ativo == 2:

            return mensagem_json('Usuário bloqueado após exceder o limite de tentativas de login.', 'erro'), 403


        # ==================================================
        # VERIFICAR USUÁRIO INATIVO
        # ==================================================

        if ativo != 1:

            return mensagem_json('Usuário inativo.', 'erro'), 403


        # ==================================================
        # VERIFICAR SENHA
        # ==================================================

        if int(tipo) == 3:
            from agenda_equipe import funcionario_logado
            if not funcionario_logado(cursor, {'tipo': 3, 'id_usuario': id_usuario}):
                return mensagem_json('Acesso do barbeiro desativado.', 'erro'), 403

        senha_correta = verificar_senha(
            senha,
            senha_hash
        )


        # ==================================================
        # SENHA INCORRETA
        # ==================================================

        if not senha_correta:

            novas_tentativas = tentativas + 1


            # ==================================================
            # BLOQUEAR APÓS 3 TENTATIVAS
            # ==================================================

            if novas_tentativas >= 3:

                cursor.execute("""
                    UPDATE USUARIO
                    SET
                        TENTATIVA = ?,
                        ATIVO = 2
                    WHERE ID_USUARIO = ?
                """, (
                    novas_tentativas,
                    id_usuario
                ))

                con.commit()
                registrar_registro(
                    cursor, 'UPDATE', 'USUARIO', 'ID_USUARIO', id_usuario,
                    dados_antes=dados_usuario_log, id_usuario=id_usuario
                )


                return mensagem_json('Usuário bloqueado após 3 tentativas de login incorretas.', 'erro'), 403


            # ==================================================
            # SALVAR TENTATIVA
            # ==================================================

            cursor.execute("""
                UPDATE USUARIO
                SET TENTATIVA = ?
                WHERE ID_USUARIO = ?
            """, (
                novas_tentativas,
                id_usuario
            ))

            con.commit()
            registrar_registro(
                cursor, 'UPDATE', 'USUARIO', 'ID_USUARIO', id_usuario,
                dados_antes=dados_usuario_log, id_usuario=id_usuario
            )


            restantes = 3 - novas_tentativas


            return mensagem_json(f'Email ou senha incorretos. Você possui {restantes} tentativa(s) restante(s).', 'erro'), 401


        # O aplicativo nativo usa Bearer em vez de cookies do navegador.
        # O cabeçalho seleciona apenas o formato; senha e estado da conta
        # continuam sendo verificados antes da emissão do mesmo JWT.
        cliente_mobile = request.headers.get('X-Cortae-Client', '').strip().lower() == 'mobile'
        if cliente_mobile and int(tipo) not in (1, 2):
            return mensagem_json('O aplicativo está disponível para clientes e barbearias. Acesse os outros perfis pelo site.', 'erro'), 403

        # ==================================================
        # SENHA CORRETA
        # ==================================================

        cursor.execute("""
            UPDATE USUARIO
            SET TENTATIVA = 0
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))

        con.commit()
        registrar_registro(
            cursor, 'UPDATE', 'USUARIO', 'ID_USUARIO', id_usuario,
            dados_antes=dados_usuario_log, id_usuario=id_usuario
        )


        # ==================================================
        # GERAR JWT
        # ==================================================

        token = jwt.encode(

            {
                'id_usuario': id_usuario,
                'email': email_banco,
                'tipo': tipo,
                'exp': (
                    datetime.utcnow()
                    + timedelta(hours=2)
                )
            },

            app.config['SECRET_KEY'],

            algorithm='HS256'
        )


        # ==================================================
        # RESPOSTA
        # ==================================================

        dados_resposta = {

            'mensagem': {
                'informacao': 'Login realizado com sucesso.',
                'tipo': 'sucesso'
            },

            'usuario': {

                'id_usuario': id_usuario,

                'id': id_usuario,

                'nome': nome,

                'email': email_banco,

                'telefone': telefone,

                'tipo': tipo,

                'genero': usuario[9] if len(usuario) > 9 else None
            }
        }
        if cliente_mobile:
            dados_resposta['access_token'] = token
            dados_resposta['token_type'] = 'Bearer'
            dados_resposta['expires_in'] = 7200
        resposta = jsonify(dados_resposta)
        resposta.headers['Cache-Control'] = 'no-store'

        # ==========================================================
        # SALVAR JWT NO COOKIE
        # ==========================================================

        if not cliente_mobile:
            resposta.set_cookie(
                key='access_token',
                value=token,
                max_age=7200,
                httponly=True,
                secure=False,
                samesite='Lax',
                path='/'
            )

        registrar_log(
            'LOGIN',
            'USUARIO',
            id_registro=id_usuario,
            id_usuario=id_usuario,
            campo='SESSAO',
            valor_antes='DESLOGADO',
            valor_depois='LOGADO'
        )


        return resposta, 200


    # ======================================================
    # ERRO
    # ======================================================

    except Exception as erro:

        if con:

            try:
                con.rollback()
            except Exception:
                pass


        print(
            'ERRO NO LOGIN:',
            erro
        )


        return jsonify({

            'mensagem': {
                'informacao': 'Erro interno no servidor.',
                'tipo': 'erro'
            },

            'detalhes': 'Consulte o registro do servidor.'

        }), 500


    # ======================================================
    # FECHAR BANCO
    # ======================================================

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
# LOGOUT
# ==========================================================

@app.route('/logout', methods=['POST'])
def logout():

    registrar_log(
        'LOGOUT',
        'USUARIO',
        campo='SESSAO',
        valor_antes='LOGADO',
        valor_depois='DESLOGADO'
    )

    resposta = make_response(
        mensagem_json('Logout realizado com sucesso!', 'sucesso'),
        200
    )

    resposta.delete_cookie(
        'access_token',
        path='/'
    )

    resposta.delete_cookie(
        'acess_token',
        path='/'
    )

    return resposta
