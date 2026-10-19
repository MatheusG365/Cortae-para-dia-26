from responses import mensagem_json
from contact_utils import email_sem_espacos, digitos_telefone
from flask import request, jsonify
import re


from application import app, conectar_banco

from funcoes import (
    verificar_senha_forte,
    criptografar_senha,
    gerar_codigo_verificacao,
    enviando_email,
    decodificar_token
)
from auditoria import capturar_registro, registrar_registro
from termos import registrar_aceite, versao_atual, documento_termos


# ==========================================
# CADASTRO
# ==========================================

@app.route('/cadastro', methods=['POST'])
def cadastro():

    con = None

    try:

        dados = request.get_json(silent=True)

        if not dados:
            return mensagem_json('Envie os dados em formato JSON.', 'erro'), 400

        nome = str(dados.get('nome') or '').strip()
        email = email_sem_espacos(str(dados.get('email') or ''))
        telefone = str(dados.get('telefone') or '').strip()
        senha = dados.get('senha')
        confirmar_senha = dados.get('confirmarSenha')
        tipo = dados.get('tipo')
        genero = str(dados.get('genero') or '').strip().lower()

        # ==========================================
        # CAMPOS OBRIGATÓRIOS
        # ==========================================

        if not nome:
            return mensagem_json('Nome é obrigatório.', 'erro'), 400

        if not email:
            return mensagem_json('E-mail é obrigatório.', 'erro'), 400

        if not telefone:
            return mensagem_json('Telefone é obrigatório.', 'erro'), 400

        if not re.match(r'^[A-Za-zÀ-ÿ ]+$', nome):
            return mensagem_json('O nome deve conter apenas letras e espaços.', 'erro'), 400

        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return mensagem_json('E-mail inválido.', 'erro'), 400

        telefone_numeros = digitos_telefone(telefone)
        if len(telefone_numeros) not in (10, 11):
            return mensagem_json('Telefone inválido.', 'erro'), 400


        if not senha:
            return mensagem_json('Senha é obrigatória.', 'erro'), 400

        if not confirmar_senha:
            return mensagem_json('Confirmação de senha é obrigatória.', 'erro'), 400

        if tipo is None:
            return mensagem_json('Tipo de usuário é obrigatório.', 'erro'), 400

        # ==========================================
        # CONFIRMAR SENHA
        # ==========================================

        if senha != confirmar_senha:

            return mensagem_json('As senhas não coincidem.', 'erro'), 400

        # ==========================================
        # VERIFICAR SENHA FORTE
        # ==========================================

        senha_valida, mensagem_senha = verificar_senha_forte(
            senha
        )

        if not senha_valida:

            return mensagem_json(mensagem_senha, 'erro'), 400

        # ==========================================
        # VALIDAR TIPO
        # ==========================================

        try:

            tipo = int(tipo)

        except (ValueError, TypeError):

            return mensagem_json('Tipo de usuário inválido.', 'erro'), 400

        if tipo not in [0, 1, 2]:

            return mensagem_json('Tipo de usuário inválido.', 'erro'), 400

        ator_cadastro = decodificar_token()
        por_administrador = bool(ator_cadastro and ator_cadastro.get('tipo') == 0)
        if tipo in (0, 2) and not por_administrador:
            perfil = 'administradores' if tipo == 0 else 'barbearias'
            return mensagem_json(f'Somente administradores podem cadastrar {perfil}.', 'erro'), 403

        if genero and genero not in ['masculino', 'feminino', 'outro']:
            return mensagem_json('Gênero inválido. Use: masculino, feminino ou outro.', 'erro'), 400

        termos_habilitados = documento_termos()['aceite_habilitado']
        if termos_habilitados and not por_administrador and (dados.get('termos_aceitos') is not True or dados.get('termos_versao') != versao_atual()):
            return jsonify(mensagem={'informacao': 'Leia e aceite a versão atual dos termos de uso.', 'tipo': 'erro'},
                           codigo='termos_aceite_pendente', termos_versao=versao_atual()), 428

        # ==========================================
        # CONECTAR BANCO
        # ==========================================

        con = conectar_banco()

        cursor = con.cursor()

        # ==========================================
        # VERIFICAR SE EMAIL JÁ EXISTE
        # ==========================================

        cursor.execute(
            '''
            SELECT ID_USUARIO
            FROM USUARIO
            WHERE EMAIL = ?
            ''',
            (email,)
        )

        usuario_existente = cursor.fetchone()

        if usuario_existente:

            return mensagem_json('Este e-mail já está cadastrado.', 'erro'), 409

        # ==========================================
        # GERAR ID (usando sequence do Firebird)
        # ==========================================

        cursor.execute('SELECT NEXT VALUE FOR SEQ_USUARIO FROM RDB$DATABASE')
        id_usuario = cursor.fetchone()[0]

        # ==========================================
        # CRIPTOGRAFAR SENHA
        # ==========================================

        senha_hash = criptografar_senha(
            senha
        )

        # ==========================================
        # GERAR CÓDIGO
        # ==========================================

        codigo = gerar_codigo_verificacao()

        # ==========================================
        # CADASTRAR USUÁRIO
        # ==========================================

        cursor.execute(
            '''
            INSERT INTO USUARIO
            (
                ID_USUARIO,
                NOME,
                EMAIL,
                TELEFONE,
                SENHA_HASH,
                TIPO,
                TENTATIVA,
                ATIVO,
                CODIGO_VERIFICACAO,
                GENERO
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?,
                0,
                0,
                ?,
                ?
            )
            ''',
            (
                id_usuario,
                nome,
                email,
                telefone_numeros,
                senha_hash,
                tipo,
                codigo,
                genero if genero else None
            )
        )

        # ==========================================
        # SALVAR NO BANCO
        # ==========================================

        if termos_habilitados and not por_administrador:
            registrar_aceite(cursor, id_usuario, dados.get('termos_versao'), dados.get('termos_aceitos'))
        con.commit()

        registrar_registro(
            cursor,
            'INSERT',
            'USUARIO',
            'ID_USUARIO',
            id_usuario,
            id_usuario=id_usuario
        )

        cursor.close()
        con.close()

        con = None

        # ==========================================
        # ENVIAR EMAIL
        # ==========================================

        email_enviado = enviando_email(
            destinatario=email,
            assunto='Confirmação de cadastro - Cortaê',
            mensagem='Seu cadastro foi realizado com sucesso!',
            codigo=codigo,
            nome=nome,
            mensagem_secundaria=(
                'Utilize o código abaixo para confirmar '
                'seu endereço de e-mail.'
            )
        )

        # ==========================================
        # VERIFICAR ENVIO
        # ==========================================

        if not email_enviado:
            return mensagem_json('Cadastro realizado, mas não foi possível enviar o e-mail de confirmação.', 'erro'), 500

        # ==========================================
        # SUCESSO
        # ==========================================

        return mensagem_json('Cadastro realizado com sucesso! Um código de confirmação foi enviado para seu e-mail.', 'sucesso'), 201

    except Exception as erro:

        if con:

            con.rollback()

        return jsonify({
            'mensagem': {"informacao":'Erro ao realizar cadastro.',"tipo":"erro"},
            'detalhes': 'Consulte o registro do servidor.'
        }), 500

    finally:

        if con:

            con.close()


# ==========================================
# VERIFICAR CÓDIGO
# ==========================================

@app.route('/verificar-codigo', methods=['POST'])
def verificar_codigo():

    con = None

    try:

        dados = request.get_json(silent=True)

        if not dados:
            return mensagem_json('Envie os dados em formato JSON.', 'erro'), 400

        email = dados.get('email')
        codigo = dados.get('codigo')

        if not email:
            return mensagem_json('E-mail é obrigatório.', 'erro'), 400

        if not codigo:
            return mensagem_json('Código de ativação é obrigatório.', 'erro'), 400

        email = str(email).strip()
        codigo = str(codigo).strip()

        con = conectar_banco()
        cursor = con.cursor()

        cursor.execute(
            '''
            SELECT
                ID_USUARIO,
                CODIGO_VERIFICACAO,
                ATIVO,
                TIPO
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
        ativo = usuario[2]
        if len(usuario) > 3 and int(usuario[3]) == 3:
            return mensagem_json('Use o convite da barbearia para ativar o acesso de barbeiro.', 'erro'), 403

        if int(ativo or 0) == 1:

            return mensagem_json('Esta conta já está ativada.', 'sucesso'), 200

        # ==========================================
        # CÓDIGO NÃO EXISTE
        # ==========================================

        if codigo_banco is None:

            return mensagem_json('Código de ativação não encontrado.', 'erro'), 400

        # ==========================================
        # COMPARAR CÓDIGO
        # ==========================================

        if codigo != str(codigo_banco).strip():

            return mensagem_json('Código de verificação inválido.', 'erro'), 400

        # ==========================================
        # ATIVAR USUÁRIO
        # ==========================================

        dados_antes_log = capturar_registro(
            cursor, 'USUARIO', 'ID_USUARIO', id_usuario
        )

        cursor.execute(
            '''
            UPDATE USUARIO
            SET
                ATIVO = 1,
                EMAIL_CONFIRMADO = 1,
                CODIGO_VERIFICACAO = NULL
            WHERE ID_USUARIO = ?
            ''',
            (id_usuario,)
        )

        con.commit()

        registrar_registro(
            cursor,
            'UPDATE',
            'USUARIO',
            'ID_USUARIO',
            id_usuario,
            dados_antes=dados_antes_log,
            id_usuario=id_usuario
        )

        return mensagem_json('E-mail confirmado com sucesso! Sua conta foi ativada.', 'sucesso'), 200

    except Exception as erro:

        if con:
            con.rollback()

        return jsonify({
            'mensagem': {
                'informacao': 'Erro ao verificar código.',
                'tipo': 'erro'
            },
            'detalhes': 'Consulte o registro do servidor.'
        }), 500

    finally:

        if con:
            con.close()

