"""Payload de mensagem compartilhado; cada rota preserva seu status HTTP."""
from flask import jsonify


def mensagem_json(informacao, tipo):
    return jsonify(mensagem={'informacao': informacao, 'tipo': tipo})
