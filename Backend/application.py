"""Shared Flask application, input checks and service readiness."""
from runtime_check import require_supported_python

require_supported_python()

from responses import mensagem_json
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from database import conectar_banco, verificar_banco

app = Flask(__name__)
app.config.from_pyfile('config.py')
app.json.ensure_ascii = False
if not app.config.get('SECRET_KEY'):
    raise RuntimeError('Configure SECRET_KEY em Backend/.env.')

CORS(app, supports_credentials=True, resources={r'/*': {
    'origins': '*', 'methods': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    'allow_headers': ['Content-Type', 'Authorization', 'X-Cortae-Client']}})

if app.config.get('IMAGE_STORAGE_PROVIDER', 'google_drive') == 'local':
    for key in ('UPLOAD_FOLDER', 'PERFIL_FOLDER', 'VISAGISMO_CORTES_FOLDER',
                'VISAGISMO_FOTOS_FOLDER', 'VISAGISMO_RESULTADOS_FOLDER'):
        os.makedirs(app.config[key], exist_ok=True)


def erro_json(texto, status):
    return mensagem_json(texto, 'erro'), status


@app.before_request
def validar_json():
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.is_json:
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict):
            return erro_json('Envie um objeto JSON válido.', 400)
        for campo in ('nome', 'email', 'senha', 'confirmarSenha', 'telefone',
                      'genero', 'motivo', 'codigo'):
            if campo in dados and dados[campo] is not None and not isinstance(dados[campo], str):
                return erro_json(f'O campo {campo} deve ser texto.', 400)


@app.errorhandler(HTTPException)
def erro_http(erro):
    mensagens = {404: 'Recurso não encontrado.', 405: 'Método não permitido.',
                 413: 'Arquivo ou requisição excede o tamanho permitido.',
                 415: 'Formato de requisição não suportado.', 400: 'Requisição inválida.'}
    return erro_json(mensagens.get(erro.code, 'Não foi possível processar a requisição.'), erro.code)


@app.errorhandler(Exception)
def erro_interno(erro):
    app.logger.exception('Falha ao processar %s %s', request.method, request.path)
    return erro_json('Erro interno ao processar a requisição.', 500)


@app.get('/health')
def health():
    principal = verificar_banco()
    auditoria = verificar_banco(log=True)
    pronto = principal and (auditoria or not app.config['LOG_OBRIGATORIO'])
    return jsonify(status='ok' if principal and auditoria else 'degradado',
                   pronto=pronto, banco_principal=principal, banco_log=auditoria,
                   auditoria_obrigatoria=app.config['LOG_OBRIGATORIO']), 200 if pronto else 503
