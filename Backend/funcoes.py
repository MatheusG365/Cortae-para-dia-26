import os
import re
import secrets
import datetime
import jwt
import smtplib

from flask import (
    request,
    render_template,
    current_app
)

from flask_bcrypt import Bcrypt
from email.mime.text import MIMEText

from application import app


# ==========================================================
# BCRYPT
# ==========================================================

bcrypt = Bcrypt(app)


# ==========================================================
# SENHA FORTE
# ==========================================================

def verificar_senha_forte(senha):

    if not isinstance(senha, str) or not senha:
        return False, "Senha é obrigatória e deve ser texto."

    if len(senha.encode('utf-8')) > 72:
        return False, "A senha deve ter no máximo 72 bytes em UTF-8."

    if len(senha) < 8:
        return False, "A senha deve ter no mínimo 8 caracteres."

    if not re.search(r"[A-Z]", senha):
        return False, "A senha deve possuir uma letra maiúscula."

    if not re.search(r"[a-z]", senha):
        return False, "A senha deve possuir uma letra minúscula."

    if not re.search(r"[0-9]", senha):
        return False, "A senha deve possuir um número."

    if not re.search(r"[^A-Za-z0-9]", senha):
        return False, "A senha deve possuir um caractere especial."

    return True, "Senha válida."


# ==========================================================
# CRIPTOGRAFAR SENHA
# ==========================================================

def criptografar_senha(senha):

    return bcrypt.generate_password_hash(
        senha
    ).decode("utf-8")


# ==========================================================
# VERIFICAR SENHA
# ==========================================================

def verificar_senha(senha, senha_hash):
    if not isinstance(senha, str) or len(senha.encode('utf-8')) > 72:
        return False
    try:
        return bcrypt.check_password_hash(senha_hash, senha)
    except (TypeError, ValueError):
        return False


# ==========================================================
# GERAR CÓDIGO
# ==========================================================

def gerar_codigo_verificacao():

    return str(
        100000 + secrets.randbelow(900000)
    )


# ==========================================================
# ENVIAR EMAIL
# ==========================================================

def enviando_email(
        destinatario,
        assunto,
        mensagem,
        nome,
        codigo=None,
        mensagem_secundaria=None
):

    # Um aviso administrativo não possui código. Mantemos a mesma função para
    # todos os e-mails, mas enviamos ao template uma flag explícita para ele
    # não reservar a caixa laranja para textos como "—".
    codigo_texto = str(codigo or '').strip()
    exibir_codigo = bool(re.fullmatch(r'\d{6}', codigo_texto))

    user = current_app.config['MAIL_USER']
    senha = current_app.config['MAIL_PASSWORD']

    try:

        html = render_template(
            "ativacao.html",
            nome=nome,
            mensagem=mensagem,
            codigo=codigo_texto,
            mensagem_secundaria=mensagem_secundaria or '',
            exibir_codigo=exibir_codigo
        )

        msg = MIMEText(
            html,
            "html",
            "utf-8"
        )

        msg["Subject"] = assunto
        msg["From"] = user
        msg["To"] = destinatario

        with smtplib.SMTP_SSL(
            current_app.config.get('MAIL_SERVER', 'smtp.gmail.com'),
            current_app.config.get('MAIL_PORT', 465), timeout=60
        ) as server:
            server.login(user, senha)
            server.send_message(msg)

        return True

    except Exception as erro:

        print(
            "ERRO AO ENVIAR EMAIL:",
            erro
        )

        return False


# ==========================================================
# E-MAIL DE AVISO
# ==========================================================

def enviar_aviso_email(destinatario, nome, assunto, mensagem, remetente='Cortaê'):
    """Envia um comunicado textual sem reaproveitar o layout de código.

    Esta função é a base para futuros avisos enviados por uma barbearia. Ela
    centraliza a apresentação, evita HTML montado a partir de texto do usuário
    e preserva a função principal de envio em um único lugar.
    """
    return enviando_email(
        destinatario=destinatario,
        assunto=assunto,
        mensagem=mensagem,
        nome=nome,
        codigo=None,
        mensagem_secundaria=f'Enviado por: {remetente}'
    )


# ==========================================================
# GERAR TOKEN
# ==========================================================



# ==========================================================
# DECODIFICAR TOKEN
# ==========================================================

def gerar_token(
        tipo,
        id_usuario,
        email=None,
        minutos=120
):

    payload = {

        'id_usuario':
            id_usuario,

        'tipo':
            tipo,

        'email':
            email,

        'exp':
            datetime.datetime.utcnow()
            + datetime.timedelta(
                minutes=minutos
            )
    }

    return jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )



def decodificar_token():

    try:

        token = request.cookies.get(
            'access_token'
        )

        if not token:

            token = request.cookies.get(
                'acess_token'
            )

        if not token:

            authorization = request.headers.get(
                'Authorization'
            )

            if (
                    authorization
                    and authorization.startswith(
                'Bearer '
            )
            ):

                token = authorization[7:]

        if not token:

            return None

        payload = jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256']
        )

        # Reload account state so blocking/deleting users and role changes
        # apply immediately rather than waiting for JWT expiry.
        from database import conectar_banco
        con = cursor = None
        try:
            id_usuario = payload.get('id_usuario')
            if isinstance(id_usuario, bool) or not isinstance(id_usuario, int) or id_usuario <= 0:
                return None
            con = conectar_banco()
            cursor = con.cursor()
            cursor.execute('SELECT TIPO, ATIVO, EMAIL_CONFIRMADO FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
            usuario = cursor.fetchone()
            if not usuario or int(usuario[1] or 0) != 1 or int(usuario[2] or 0) != 1:
                return None
            if int(usuario[0]) == 3:
                from agenda_equipe import funcionario_logado
                if not funcionario_logado(cursor, {'tipo': 3, 'id_usuario': id_usuario}): return None
            payload['tipo'] = int(usuario[0])
            return payload
        finally:
            if cursor is not None:
                cursor.close()
            if con is not None:
                con.close()

    except jwt.ExpiredSignatureError:

        print(
            "TOKEN EXPIRADO."
        )

        return None

    except jwt.InvalidTokenError:

        print(
            "TOKEN INVÁLIDO."
        )

        return None

    except Exception as erro:

        print(
            "ERRO AO DECODIFICAR TOKEN:",
            erro
        )

        return None


# ==========================================================
# PASTA DE FOTOS
# ==========================================================

PASTA_FOTOS_PERFIL = app.config[
    'PERFIL_FOLDER'
]


# ==========================================================
# EXTENSÕES PERMITIDAS
# ==========================================================

EXTENSOES_IMAGEM = {

    '.jpg',
    '.jpeg',
    '.png',
    '.webp'

}


# ==========================================================
# BUSCAR FOTO DE PERFIL
# ==========================================================

def buscar_foto_perfil(id_usuario, cursor=None):
    """Resolve the database image reference before checking legacy local files."""
    from image_storage import slot_state
    managed, image = slot_state('perfil', int(id_usuario), 'profile', cursor=cursor)
    if managed:
        return image.url if image else None
    if current_app.config.get('IMAGE_STORAGE_PROVIDER', 'google_drive') != 'local':
        return None
    folder = current_app.config.get('PERFIL_FOLDER', PASTA_FOTOS_PERFIL)
    for extension in sorted(EXTENSOES_IMAGEM):
        filename = f'{int(id_usuario)}{extension}'
        if os.path.isfile(os.path.join(folder, filename)):
            return f'/fotos-perfil/{filename}'
    return None


def salvar_foto_perfil(arquivo, id_usuario, batch):
    """Decode and store a profile image in the caller's business transaction."""
    if arquivo is None or not arquivo.filename:
        raise ValueError('Nenhuma foto foi enviada.')
    return batch.save(arquivo, 'perfil', owner_id=int(id_usuario), slot='profile').url


# ==========================================================
# EXCLUIR FOTO DE PERFIL
# ==========================================================

