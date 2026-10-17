# ==========================================================
# IMPORTADOR CENTRAL DAS ROTAS
# ==========================================================

from cadastro import *
from login import *
from recuperar_senha import *
from editar_usuario import *
from barbearia import *
from visagismo import *
from pagamento import *
from api_docs import *
from agenda_equipe import *


# ==========================================================
# SERVIR FOTOS DE PERFIL
# ==========================================================

import os

from flask import (
    send_from_directory,
    current_app
)


@app.route(
    '/fotos-perfil/<nome_arquivo>',
    methods=['GET']
)
def fotos_perfil(nome_arquivo):
    return servir_imagem_perfil(nome_arquivo)
