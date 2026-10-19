"""Rotas de catálogo, visagismo e agenda do Cortaê.

O módulo não depende do script experimental em ``Teste-main``: ele mantém os
dados no Firebird, protege as rotas pelo cookie já usado pelo projeto e deixa a
integração com OpenAI opcional até uma chave ser configurada no servidor.
"""

from responses import mensagem_json
import base64
import ipaddress
import socket
import http.client
import json
import os
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler, ProxyHandler

from flask import jsonify, request
from image_storage import ImageBatch, ImageStorageError, read_image, serve_image, find_image

from application import app, conectar_banco
from barbearia import obter_usuario_logado, pegar_id_barbearia_alvo
from funcoes import enviar_aviso_email
from auditoria import capturar_registro, registrar_registro, registrar_log
from agenda_equipe import (travar_agendamento, acesso_agendamento, registrar_evento,
    salvar_snapshot, registrar_comissao, enfileirar_liberacao, funcionario_logado,dinheiro,validar_escolha_corte,nome_escolha_corte,generos_servicos)
from visagismo_ia import (ErroVisagismoIA, mime_imagem, esquema_analise,
                         validar_analise, prompt_analise, parametros_edicao,
                         prompt_simulacao)

try:
    from openai import OpenAI
except ImportError:  # Permite iniciar a API antes de instalar a dependência.
    OpenAI = None


DIAS_SEMANA = ('segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo')


def resposta_erro(texto, status=400):
    return mensagem_json(texto, 'erro'), status


def json_seguro(valor, padrao=None):
    if valor is None:
        return padrao if padrao is not None else {}
    if isinstance(valor, (dict, list)):
        return valor
    try:
        return json.loads(str(valor))
    except (TypeError, ValueError, json.JSONDecodeError):
        return padrao if padrao is not None else {}


def normalizar(valor):
    return re.sub(r'[^a-z0-9]+', ' ', str(valor or '').lower()).strip()


def encerrar_transacao_imagens(con, cursor, batch, persistido):
    """Release new remote assets if the business transaction did not commit."""
    try:
        if not persistido:
            try:
                con.rollback()
            finally:
                batch.abort()
    finally:
        try:
            cursor.close()
        finally:
            con.close()


def ids_servicos_da_requisicao(dados):
    valor = dados.get('ids_servicos') or dados.get('servicos') or []
    if isinstance(valor, str):
        decodificado = json_seguro(valor, None)
        valor = decodificado if isinstance(decodificado, list) else [item for item in valor.split(',') if item.strip()]
    if not isinstance(valor, list):
        return []
    try:
        return sorted({int(item) for item in valor})
    except (TypeError, ValueError):
        return []


def carregar_servicos(cursor, id_barbearia, ids_servicos):
    if not ids_servicos:
        return []
    marcadores = ','.join('?' for _ in ids_servicos)
    cursor.execute(f'''
        SELECT ID_SERVICO, NOME_SERVICO, DURACAO, GENERO
        FROM SERVICO
        WHERE ID_USUARIO = ? AND ATIVO=1 AND ID_SERVICO IN ({marcadores})
        AND EXISTS(SELECT 1 FROM USUARIO U WHERE U.ID_USUARIO=SERVICO.ID_USUARIO AND U.TIPO=2 AND U.ATIVO=1)
    ''', [id_barbearia, *ids_servicos])
    encontrados = cursor.fetchall()
    if len(encontrados) != len(ids_servicos):
        return []
    return [
        {'id_servico': linha[0], 'nome': linha[1], 'duracao': int(linha[2] or 0),
         'genero': str(linha[3] or 'unissex').strip().lower()}
        for linha in encontrados
    ]


def servico_indica_corte_de_cabelo(nome):
    """Distingue corte de cabelo de um simples corte de barba."""
    nome = normalizar(nome)
    if any(palavra in nome for palavra in ('cabelo', 'pezinho', 'lavagem', 'degrade')):
        return True
    if 'corte' not in nome:
        return False
    if 'barba' not in nome and 'bigode' not in nome:
        return True
    # Serviço único como "corte e barba" também cobre cabelo e barba.
    return bool(re.search(r'\bcorte\s+(e|com)\s+(a\s+)?barba\b', nome))


def categoria_para_servicos(servicos):
    nomes = ' '.join(normalizar(servico['nome']) for servico in servicos)
    tem_barba = 'barba' in nomes or 'bigode' in nomes
    tem_cabelo = any(palavra in nomes for palavra in ('cabelo', 'pezinho', 'lavagem', 'degrade'))
    tem_corte_cabelo = any(servico_indica_corte_de_cabelo(servico['nome']) for servico in servicos)
    tem_pintar = 'pintar' in nomes or 'color' in nomes or 'tinta' in nomes
    # Tratamentos que precisam de visagismo mas não são "corte"
    tem_tratamento_cabelo = any(palavra in nomes for palavra in ('progressiva', 'alisamento', 'mega hair', 'mega-hair', 'mega', 'hidratacao', 'cauterizacao', 'botox', 'reconstrucao', 'selagem', 'escova'))
    
    if tem_barba and (tem_cabelo or tem_corte_cabelo or tem_tratamento_cabelo):
        return 'barba_cabelo'
    if tem_barba:
        return 'barba'
    if tem_pintar and tem_corte_cabelo:
        return 'corte_pintura'
    if tem_pintar:
        return 'pintura'
    # Se tem tratamento de cabelo, usa categoria 'cabelo' para buscar cortes
    if tem_tratamento_cabelo or tem_cabelo or tem_corte_cabelo:
        return 'cabelo'
    return 'cabelo'


def generos_para_filtro_servicos(servicos):
    """Retorna os públicos explícitos dos serviços selecionados.

    O filtro usa o campo ``SERVICO.GENERO``, e nunca palavras no nome: uma
    pessoa pode dar qualquer nome comercial ao serviço sem alterar o catálogo.
    Serviços unissex não restringem os cortes disponíveis.
    """
    generos = {
        str(servico.get('genero') or 'unissex').strip().lower()
        for servico in servicos
    }
    return tuple(genero for genero in ('masculino', 'feminino') if genero in generos)


def categorias_catalogo_para_servicos(servicos):
    """Resolve as categorias reais usadas no catálogo de cortes.

    O serviço de cabelo é genérico, porém o catálogo atual guarda seus cortes
    nas categorias ``masculino`` e ``feminino``. Por isso não podemos buscar
    apenas a categoria ``cabelo``: ela faria o catálogo voltar vazio mesmo
    quando há cortes disponíveis.
    """
    generos = generos_para_filtro_servicos(servicos)
    categorias_cabelo = generos or ('masculino', 'feminino', 'cabelo')
    categoria = categoria_para_servicos(servicos)

    # Combinações de serviços não podem depender de uma categoria especial
    # existir no catálogo. Por exemplo, "corte + pintar cabelo" deve exibir
    # os cortes de cabelo normais mesmo quando não houver item cadastrado em
    # ``corte_pintura``. Para barba + cabelo, mantemos também os estilos
    # específicos de barba/cabelo, quando existirem.
    if categoria in ('barba_cabelo', 'corte_pintura'):
        return tuple(dict.fromkeys((categoria, *categorias_cabelo)))
    if categoria == 'pintura':
        return categorias_cabelo
    if categoria == 'cabelo':
        return categorias_cabelo
    return (categoria,)


def _resolver_url_imagem(url):
    destino = urlparse(str(url or ''))
    if (destino.scheme != 'https' or not destino.hostname or destino.username
            or destino.password or destino.port not in (None, 443)):
        raise ValueError('A URL da imagem deve usar HTTPS público na porta 443.')
    try:
        enderecos = socket.getaddrinfo(destino.hostname, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise ValueError('Não foi possível localizar o servidor da imagem.') from None
    if not enderecos or any(not ipaddress.ip_address(item[4][0]).is_global for item in enderecos):
        raise ValueError('A URL da imagem não pode acessar endereços internos.')
    return destino.geturl(), enderecos[0][4][0]


def validar_url_imagem(url):
    return _resolver_url_imagem(url)[0]


class ConexaoImagemFixa(http.client.HTTPSConnection):
    """Connect to the validated IP, retaining original TLS hostname and Host."""
    def __init__(self, host, **kwargs):
        super().__init__(host, **kwargs)
        _, ip_validado = _resolver_url_imagem('https://' + host)

        def conectar_ip(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                        source_address=None):
            return socket.create_connection((ip_validado, 443), timeout, source_address)

        # HTTPSConnection wraps this socket using self.host for certificate
        # checks, but cannot perform a second DNS lookup after validation.
        self._create_connection = conectar_ip


class TransporteImagem(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(ConexaoImagemFixa, req, context=self._context)


class RedirecionamentoImagem(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validar_url_imagem(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def url_corte(nome, cursor=None):
    if not nome:
        return None
    # Se for uma URL externa (http/https), retornar diretamente
    if nome.startswith('http://') or nome.startswith('https://'):
        return nome
    if os.path.basename(nome) != nome:
        return None
    try:
        asset = find_image('visagismo/cortes', nome, cursor=cursor)
    except FileNotFoundError:
        return None
    if asset:
        return asset.url
    if (app.config.get('IMAGE_STORAGE_PROVIDER', 'google_drive') != 'local'
            or not os.path.isfile(os.path.join(app.config['VISAGISMO_CORTES_FOLDER'], nome))):
        return None
    return f'/uploads/visagismo/cortes/{nome}'


def serializar_corte(linha, cursor=None):
    return {
        'id_corte': linha[0], 'nome': linha[1], 'descricao': str(linha[2] or ''),
        'categoria': linha[3], 'imagem_url': url_corte(linha[4], cursor=cursor), 'ativo': bool(linha[5]),
        'genero': linha[6] if len(linha) > 6 else None
    }


def pode_gerenciar_catalogo(usuario):
    return usuario and int(usuario.get('tipo', -1)) in (0, 2)


@app.route('/visagismo/cortes', methods=['GET'])
def listar_cortes_visagismo():
    try:
        id_barbearia = request.args.get('id_barbearia', type=int)
        ids_servicos = ids_servicos_da_requisicao(request.args)
        categoria = request.args.get('categoria')
        con = conectar_banco(); cursor = con.cursor()
        try:
            servicos = carregar_servicos(cursor, id_barbearia, ids_servicos) if id_barbearia else []
            if id_barbearia and ids_servicos and not servicos:
                return resposta_erro('Serviços inválidos para esta barbearia.', 400)
            
            categorias = (categoria,) if categoria else (categorias_catalogo_para_servicos(servicos) if servicos else ())
            generos_servico = generos_para_filtro_servicos(servicos)
            
            # Busca todos os cortes ativos, filtrando por gênero se necessário
            sql = "SELECT ID_CORTE, NOME, DESCRICAO, CATEGORIA, IMAGEM_ROTA, ATIVO, GENERO"
            sql += " FROM CORTE_VISAGISMO WHERE ATIVO = 1"
            parametros = []
            
            # Um serviço de cabelo pode corresponder às categorias masculina,
            # feminina ou à categoria legada genérica ``cabelo``.
            if categorias:
                marcadores = ','.join('?' for _ in categorias)
                sql += f" AND CATEGORIA IN ({marcadores})"
                parametros.extend(categorias)
            
            # Filtra pelo serviço escolhido, nunca pelo gênero do usuário logado.
            if generos_servico:
                marcadores = ','.join('?' for _ in generos_servico)
                # Para barba, não aceitamos itens sem gênero definido: esses
                # estilos são exclusivos do catálogo masculino.
                if categoria_para_servicos(servicos) in ('barba', 'barba_cabelo'):
                    sql += f" AND GENERO IN ({marcadores})"
                else:
                    sql += f" AND (GENERO IN ({marcadores}) OR GENERO IS NULL)"
                parametros.extend(generos_servico)
            
            sql += " ORDER BY NOME"
            cursor.execute(sql, parametros)
            cortes = [serializar_corte(linha, cursor=cursor) for linha in cursor.fetchall()]
            
            return jsonify({'mensagem': {'informacao': 'Cortes listados.', 'tipo': 'sucesso'},
                            'categoria': categoria or (categorias[0] if len(categorias) == 1 else 'cabelo'),
                            'cortes': cortes,'generos_servico':generos_servicos(servicos)})
        finally:
            cursor.close(); con.close()
    except Exception as erro:
        return resposta_erro(f'Erro ao listar cortes: {erro}', 500)


@app.route('/visagismo/cortes', methods=['POST'])
def criar_corte_visagismo():
    usuario = obter_usuario_logado()
    if not pode_gerenciar_catalogo(usuario):
        return resposta_erro('Apenas administradores ou barbearias podem administrar cortes.', 403)
    try:
        dados = request.form if request.form else (request.get_json(silent=True) or {})
        nome = str(dados.get('nome', '')).strip()
        descricao = str(dados.get('descricao', '')).strip()
        categoria = str(dados.get('categoria', '')).strip().lower()
        genero = str(dados.get('genero', '')).strip().lower()
        if genero and genero not in ['masculino', 'feminino', 'unissex']:
            return resposta_erro('Gênero inválido. Use: masculino, feminino ou unissex.')
        if not nome or categoria not in {'cabelo', 'masculino', 'feminino', 'barba', 'barba_cabelo', 'corte_pintura', 'pintura'}:
            return resposta_erro('Informe nome e uma categoria válida: cabelo, barba, barba_cabelo, corte_pintura ou pintura.')
        imagem = request.files.get('imagem')
        imagem_url = dados.get('imagem_url')
        if imagem:
            arquivo = None
        elif imagem_url:
            arquivo = validar_url_imagem(imagem_url)
            if len(arquivo) > 255:
                return resposta_erro('A URL da referência deve ter até 255 caracteres.')
        else:
            return resposta_erro('Envie a imagem de exemplo ou uma imagem_url HTTPS.')
        con = conectar_banco(); cursor = con.cursor()
        batch = ImageBatch(cursor)
        persistido = False
        try:
            # Verificar se já existe um corte com o mesmo nome
            cursor.execute('SELECT ID_CORTE FROM CORTE_VISAGISMO WHERE LOWER(TRIM(NOME)) = ?', (nome.lower(),))
            if cursor.fetchone():
                return resposta_erro('Já existe um corte com este nome.')
            if imagem:
                arquivo = batch.save(imagem, 'visagismo/cortes', owner_id=usuario['id_usuario']).filename
            
            cursor.execute('''INSERT INTO CORTE_VISAGISMO
                                  (ID_CORTE, ID_USUARIO, NOME, DESCRICAO, CATEGORIA, IMAGEM_ROTA, GENERO)
                              VALUES (NEXT VALUE FOR SEQ_CORTE_VISAGISMO, ?, ?, ?, ?, ?, ?)
                              RETURNING ID_CORTE''',
                           (usuario['id_usuario'], nome, descricao, categoria, arquivo, genero if genero else None))
            id_corte = cursor.fetchone()[0]
            con.commit()
            persistido = True
            batch.commit()
            registrar_registro(
                cursor, 'INSERT', 'CORTE_VISAGISMO', 'ID_CORTE', id_corte,
                id_usuario=usuario['id_usuario']
            )
            return jsonify({'mensagem': {'informacao': 'Corte adicionado.', 'tipo': 'sucesso'},
                            'corte': {'id_corte': id_corte, 'nome': nome, 'descricao': descricao,
                                      'categoria': categoria, 'imagem_url': url_corte(arquivo, cursor=cursor)}}), 201
        finally:
            encerrar_transacao_imagens(con, cursor, batch, persistido)
    except ImageStorageError as erro:
        return resposta_erro(str(erro), erro.status)
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Erro ao criar corte: {erro}', 500)


@app.route('/visagismo/cortes/<int:id_corte>', methods=['PUT'])
def editar_corte_visagismo(id_corte):
    usuario = obter_usuario_logado()
    if not pode_gerenciar_catalogo(usuario):
        return resposta_erro('Sem permissão para editar cortes.', 403)
    try:
        dados = request.form if request.form else (request.get_json(silent=True) or {})
        nome = str(dados.get('nome', '')).strip(); descricao = str(dados.get('descricao', '')).strip()
        categoria = str(dados.get('categoria', '')).strip().lower()
        genero = str(dados.get('genero', '')).strip().lower()
        if genero and genero not in ['masculino', 'feminino', 'unissex']:
            return resposta_erro('Gênero inválido. Use: masculino, feminino ou unissex.')
        if not nome or categoria not in {'cabelo', 'masculino', 'feminino', 'barba', 'barba_cabelo', 'corte_pintura', 'pintura'}:
            return resposta_erro('Informe nome e categoria válida: cabelo, barba, barba_cabelo, corte_pintura ou pintura.')
        con = conectar_banco(); cursor = con.cursor()
        batch = ImageBatch(cursor)
        persistido = False
        try:
            # Verificar se já existe outro corte com o mesmo nome
            cursor.execute('SELECT ID_CORTE FROM CORTE_VISAGISMO WHERE LOWER(TRIM(NOME)) = ? AND ID_CORTE <> ?', (nome.lower(), id_corte))
            if cursor.fetchone():
                return resposta_erro('Já existe outro corte com este nome.')
            
            cursor.execute('SELECT IMAGEM_ROTA FROM CORTE_VISAGISMO WHERE ID_CORTE = ?', (id_corte,))
            anterior = cursor.fetchone()
            if not anterior:
                return resposta_erro('Corte não encontrado.', 404)
            imagem_nome = anterior[0]
            dados_antes_log = capturar_registro(
                cursor, 'CORTE_VISAGISMO', 'ID_CORTE', id_corte
            )
            if request.files.get('imagem'):
                imagem_nome = batch.save(request.files['imagem'], 'visagismo/cortes', owner_id=usuario['id_usuario']).filename
            elif dados.get('imagem_url'):
                imagem_nome = validar_url_imagem(dados['imagem_url'])
                if len(imagem_nome) > 255:
                    return resposta_erro('A URL da referência deve ter até 255 caracteres.')
            cursor.execute('''UPDATE CORTE_VISAGISMO SET NOME=?, DESCRICAO=?, CATEGORIA=?, IMAGEM_ROTA=?, GENERO=?
                              WHERE ID_CORTE=?''', (nome, descricao, categoria, imagem_nome, genero if genero else None, id_corte))
            con.commit()
            persistido = True
            batch.commit()
            registrar_registro(
                cursor, 'UPDATE', 'CORTE_VISAGISMO', 'ID_CORTE', id_corte,
                dados_antes=dados_antes_log, id_usuario=usuario['id_usuario']
            )
            return mensagem_json('Corte atualizado.', 'sucesso')
        finally:
            encerrar_transacao_imagens(con, cursor, batch, persistido)
    except ImageStorageError as erro:
        return resposta_erro(str(erro), erro.status)
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Erro ao editar corte: {erro}', 500)


@app.route('/visagismo/cortes/<int:id_corte>', methods=['DELETE'])
def excluir_corte_visagismo(id_corte):
    usuario = obter_usuario_logado()
    if not pode_gerenciar_catalogo(usuario):
        return resposta_erro('Sem permissão para excluir cortes.', 403)
    try:
        con = conectar_banco(); cursor = con.cursor()
        try:
            cursor.execute('SELECT IMAGEM_ROTA FROM CORTE_VISAGISMO WHERE ID_CORTE=?', (id_corte,))
            corte = cursor.fetchone()
            if not corte: return resposta_erro('Corte não encontrado.', 404)
            dados_antes_log = capturar_registro(
                cursor, 'CORTE_VISAGISMO', 'ID_CORTE', id_corte
            )
            # Exclusão lógica preserva escolhas e agendamentos antigos.
            cursor.execute('UPDATE CORTE_VISAGISMO SET ATIVO = 0 WHERE ID_CORTE=?', (id_corte,))
            con.commit()
            dados_depois_log = capturar_registro(
                cursor, 'CORTE_VISAGISMO', 'ID_CORTE', id_corte
            )
            registrar_log(
                'DELETE', 'CORTE_VISAGISMO', id_registro=id_corte,
                dados_antes=dados_antes_log, dados_depois=dados_depois_log,
                id_usuario=usuario['id_usuario']
            )
            return mensagem_json('Corte removido do catálogo.', 'sucesso')
        finally:
            cursor.close(); con.close()
    except Exception as erro:
        return resposta_erro(f'Erro ao excluir corte: {erro}', 500)


def motivo_sem_ia():
    """Explica por que a análise caiu no modo sem IA (sem vazar a chave)."""
    if OpenAI is None:
        return 'Biblioteca openai não instalada no servidor. Rode: pip install -r requirements.txt'
    if not (app.config.get('OPENAI_API_KEY') or '').strip():
        return 'OPENAI_API_KEY ausente no servidor. Confira Backend/.env e reinicie o Flask.'
    return ''


def traduzir_erro_openai(erro):
    texto = f'{getattr(erro, "status_code", "")} {erro}'.lower()
    if 'expired' in texto:
        return 'Chave da OpenAI expirada (a própria API retornou expired_secret_key). Gere uma nova em platform.openai.com > API keys e troque no Backend/.env.'
    if '401' in texto or 'incorrect api key' in texto or 'invalid api key' in texto:
        return 'Chave da OpenAI rejeitada (401). Confira se a OPENAI_API_KEY é válida e não é uma chave de teste.'
    if '404' in texto or 'model_not_found' in texto or 'model not found' in texto:
        return (f'Modelo não encontrado na OpenAI. Modelo pedido: '
                f'{app.config.get("VISAGISMO_ANALYSIS_MODEL")}/{app.config.get("VISAGISMO_IMAGE_MODEL")}. '
                'Ajuste VISAGISMO_ANALYSIS_MODEL (ex: gpt-4o-mini) e VISAGISMO_IMAGE_MODEL (ex: gpt-image-1).')
    if '429' in texto or 'quota' in texto or 'insufficient_quota' in texto:
        return 'Cota da OpenAI esgotada ou limite excedido (429). Verifique billing/limites da chave.'
    return 'Não foi possível concluir a operação na OpenAI. Tente novamente mais tarde.'


def analisar_com_ia(conteudo, cortes, categoria):
    """Analyze the actual photo with a strict schema and exactly one valid ID."""
    if motivo_sem_ia():
        raise ErroVisagismoIA('A análise por IA está indisponível. Configure a integração no servidor.', 503)
    if not conteudo or len(conteudo) > app.config['MAX_VISAGISMO_IMAGE_BYTES']:
        raise ValueError('A imagem deve ter até 10 MB.')
    mime = mime_imagem(conteudo)
    imagem_b64 = base64.b64encode(conteudo).decode('ascii')
    try:
        resposta = OpenAI(api_key=app.config['OPENAI_API_KEY']).responses.create(
            model=app.config['VISAGISMO_ANALYSIS_MODEL'],
            text={'format': {'type': 'json_schema', 'name': 'analise_visagismo',
                             'strict': True, 'schema': esquema_analise(cortes)}},
            input=[{'role': 'user', 'content': [
                {'type': 'input_text', 'text': prompt_analise(cortes, categoria)},
                {'type': 'input_image', 'image_url': f'data:{mime};base64,{imagem_b64}'}
            ]}]
        )
    except ErroVisagismoIA:
        raise
    except Exception as erro:
        raise ErroVisagismoIA(traduzir_erro_openai(erro), 502) from erro
    try:
        texto = resposta.output_text
        if not isinstance(texto, str) or not texto.strip():
            raise ValueError('empty/refused response')
        analise = json.loads(texto)
    except (ValueError, TypeError, AttributeError):
        raise ErroVisagismoIA('A IA não retornou uma análise válida. Tente novamente.', 502) from None
    return validar_analise(analise, cortes)


@app.route('/visagismo/status', methods=['GET'])
def status_visagismo():
    """Diagnóstico rápido: mostra se a chave chega na rota, sem expor a chave."""
    chave = (app.config.get('OPENAI_API_KEY') or '').strip()
    return jsonify({
        'mensagem': {'informacao': 'Diagnóstico do visagismo.', 'tipo': 'sucesso'},
        'openai_key_configurada': bool(chave),
        'openai_lib_ok': OpenAI is not None,
        'analysis_model': app.config.get('VISAGISMO_ANALYSIS_MODEL'),
        'image_model': app.config.get('VISAGISMO_IMAGE_MODEL'),
        'motivo_sem_ia': motivo_sem_ia() or None,
    })


@app.route('/visagismo/analisar', methods=['POST'])
def analisar_visagismo():
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para usar o visagismo.', 401)
    persistido = False
    try:
        id_barbearia = request.form.get('id_barbearia', type=int)
        ids_servicos = ids_servicos_da_requisicao(request.form)
        if not id_barbearia or not ids_servicos:
            return resposta_erro('Escolha a barbearia e ao menos um serviço.')
        con = conectar_banco(); cursor = con.cursor()
        batch = ImageBatch(cursor)
        try:
            servicos = carregar_servicos(cursor, id_barbearia, ids_servicos)
            if not servicos: return resposta_erro('Serviços inválidos para a barbearia.', 400)
            categoria = categoria_para_servicos(servicos)
            categorias = categorias_catalogo_para_servicos(servicos)
            generos_servico = generos_para_filtro_servicos(servicos)
            marcadores = ','.join('?' for _ in categorias)
            sql = 'SELECT ID_CORTE, NOME, DESCRICAO, CATEGORIA, IMAGEM_ROTA, ATIVO, GENERO FROM CORTE_VISAGISMO WHERE ATIVO=1 AND CATEGORIA IN (' + marcadores + ')'
            parametros = list(categorias)
            if generos_servico:
                if categoria in ('barba', 'barba_cabelo'):
                    sql += ' AND GENERO IN (' + ','.join('?' for _ in generos_servico) + ')'
                else:
                    sql += ' AND (GENERO IN (' + ','.join('?' for _ in generos_servico) + ') OR GENERO IS NULL)'
                parametros.extend(generos_servico)
            cursor.execute(sql + ' ORDER BY NOME', parametros)
            cortes = [serializar_corte(linha, cursor=cursor) for linha in cursor.fetchall()]
            if not cortes: return resposta_erro('Não há cortes cadastrados compatíveis com este serviço.', 404)
            imagem = batch.save(request.files.get('imagem'), 'visagismo/fotos', owner_id=usuario['id_usuario'])
            foto_nome = imagem.filename
            analise_ia = analisar_com_ia(imagem.content, cortes, categoria)
            item = analise_ia['recomendacoes'][0]
            escolhido = next(c for c in cortes if c['id_corte'] == item['id_corte'])
            analise = {**analise_ia, 'categoria': categoria, 'versao_analise': 2,
                       'modo': 'analise', 'recomendacoes': [{**escolhido, **item}]}
            cursor.execute("""INSERT INTO VISAGISMO_SESSAO
                (ID_VISAGISMO, ID_USUARIO, ID_BARBEARIA, SERVICOS_JSON, FOTO_ROTA, ANALISE_JSON)
                VALUES (NEXT VALUE FOR SEQ_VISAGISMO_SESSAO, ?, ?, ?, ?, ?) RETURNING ID_VISAGISMO""",
                (usuario['id_usuario'], id_barbearia, json.dumps(ids_servicos), foto_nome,
                 json.dumps(analise, ensure_ascii=False)))
            id_visagismo = cursor.fetchone()[0]
            con.commit()
            persistido = True
            batch.commit()
            registrar_registro(cursor, 'INSERT', 'VISAGISMO_SESSAO', 'ID_VISAGISMO', id_visagismo,
                               id_usuario=usuario['id_usuario'])
            return jsonify({'mensagem': {'informacao': 'Análise de visagismo concluída.', 'tipo': 'sucesso'},
                            'id_visagismo': id_visagismo, 'foto_url': f'/uploads/visagismo/fotos/{foto_nome}', **analise})
        finally:
            encerrar_transacao_imagens(con, cursor, batch, persistido)
    except ErroVisagismoIA as erro:
        return resposta_erro(str(erro), erro.status)
    except ImageStorageError as erro:
        return resposta_erro(str(erro), erro.status)
    except ValueError as erro:
        return resposta_erro(str(erro), 400)
    except Exception:
        app.logger.exception('Falha ao analisar visagismo.')
        return resposta_erro('Não foi possível analisar a foto. Tente novamente.', 500)


@app.route('/visagismo/salvar-foto', methods=['POST'])
def salvar_foto_visagismo():
    """Salva a foto do cliente para uso posterior (simulação de cor) sem fazer análise de visagismo."""
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para usar o visagismo.', 401)
    persistido = False
    try:
        id_barbearia = request.form.get('id_barbearia', type=int)
        ids_servicos = ids_servicos_da_requisicao(request.form)
        if not id_barbearia or not ids_servicos: return resposta_erro('Escolha a barbearia e ao menos um serviço.')
        con = conectar_banco(); cursor = con.cursor()
        batch = ImageBatch(cursor)
        try:
            servicos = carregar_servicos(cursor, id_barbearia, ids_servicos)
            if not servicos: return resposta_erro('Serviços inválidos para a barbearia.', 400)
            imagem = batch.save(request.files.get('imagem'), 'visagismo/fotos', owner_id=usuario['id_usuario'])
            foto_nome = imagem.filename
            cursor.execute('''INSERT INTO VISAGISMO_SESSAO
                              (ID_VISAGISMO, ID_USUARIO, ID_BARBEARIA, SERVICOS_JSON, FOTO_ROTA, ANALISE_JSON)
                              VALUES (NEXT VALUE FOR SEQ_VISAGISMO_SESSAO, ?, ?, ?, ?, ?)
                              RETURNING ID_VISAGISMO''', 
                           (usuario['id_usuario'], id_barbearia,
                            json.dumps(ids_servicos), foto_nome, json.dumps({'categoria': categoria_para_servicos(servicos), 'apenas_cor': servicos_somente_cor(servicos), 'modo': 'cor' if servicos_somente_cor(servicos) else 'manual'}, ensure_ascii=False)))
            id_visagismo = cursor.fetchone()[0]
            con.commit()
            persistido = True
            batch.commit()
            registrar_registro(
                cursor, 'INSERT', 'VISAGISMO_SESSAO', 'ID_VISAGISMO', id_visagismo,
                id_usuario=usuario['id_usuario']
            )
            return jsonify({'mensagem': {'informacao': 'Foto salva com sucesso.', 'tipo': 'sucesso'},
                            'id_visagismo': id_visagismo, 'foto_url': f'/uploads/visagismo/fotos/{foto_nome}'})
        finally:
            encerrar_transacao_imagens(con, cursor, batch, persistido)
    except ImageStorageError as erro:
        return resposta_erro(str(erro), erro.status)
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Não foi possível salvar a foto: {erro}', 500)


def servicos_somente_cor(servicos):
    if not servicos:
        return False
    for servico in servicos:
        nome = normalizar(servico['nome'])
        if not any(palavra in nome for palavra in ('pintar', 'color', 'tinta')):
            return False
        if any(palavra in nome for palavra in ('corte', 'degrade', 'pezinho')):
            return False
    return True


def corte_compativel_servicos(corte, servicos):
    if not corte.get('ativo') or corte.get('categoria') not in categorias_catalogo_para_servicos(servicos):
        return False
    generos = generos_para_filtro_servicos(servicos)
    if not generos:
        return True
    genero = corte.get('genero')
    if categoria_para_servicos(servicos) in ('barba', 'barba_cabelo'):
        return genero in generos
    return genero is None or genero in generos


def carregar_referencia_corte(rota, cursor=None):
    """Return reference bytes/MIME from local catalog or public HTTPS, no disk download."""
    if not rota:
        return None
    if str(rota).startswith(('https://', 'http://')):
        url = validar_url_imagem(rota)
        opener = build_opener(ProxyHandler({}), TransporteImagem(), RedirecionamentoImagem())
        with opener.open(Request(url, headers={'User-Agent': 'Cortae/1.0'}), timeout=20) as resposta:
            validar_url_imagem(resposta.geturl())
            conteudo = resposta.read(app.config['MAX_VISAGISMO_IMAGE_BYTES'] + 1)
    else:
        if os.path.basename(rota) != rota:
            return None
        try:
            conteudo = read_image('visagismo/cortes', rota, legacy_folder=app.config['VISAGISMO_CORTES_FOLDER'], cursor=cursor)
        except FileNotFoundError:
            return None
    if not conteudo or len(conteudo) > app.config['MAX_VISAGISMO_IMAGE_BYTES']:
        raise ValueError('Referência vazia ou maior que 10 MB.')
    return conteudo, mime_imagem(conteudo)


def imagem_para_edicao(nome, conteudo):
    mime = mime_imagem(conteudo)
    extensao = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}[mime]
    return (f'{nome}.{extensao}', conteudo, mime)


@app.route('/visagismo/<int:id_visagismo>/simular', methods=['POST'])
def simular_visagismo(id_visagismo):
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para gerar a simulação.', 401)
    persistido = False
    try:
        dados = request.get_json(silent=True) or {}
        id_corte = dados.get('id_corte')
        if id_corte is not None:
            if isinstance(id_corte, bool) or not re.fullmatch(r'[1-9]\d*', str(id_corte)):
                return resposta_erro('Informe um ID de corte válido.')
            id_corte = int(id_corte)
        cor = dados.get('cor')
        if cor is not None:
            if not isinstance(cor, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}|[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ -]{0,39}', cor.strip()):
                return resposta_erro('Informe uma cor válida, por nome ou código hexadecimal.')
            cor = cor.strip()
        if not id_corte and not cor:
            return resposta_erro('Selecione um corte ou uma cor.')
        con = conectar_banco(); cursor = con.cursor()
        batch = ImageBatch(cursor)
        try:
            cursor.execute('SELECT FOTO_ROTA, ANALISE_JSON, ID_BARBEARIA, SERVICOS_JSON FROM VISAGISMO_SESSAO WHERE ID_VISAGISMO=? AND ID_USUARIO=?',
                           (id_visagismo, usuario['id_usuario']))
            sessao = cursor.fetchone()
            if not sessao: return resposta_erro('Análise de visagismo não encontrada.', 404)
            analise = json_seguro(sessao[1])
            if not isinstance(analise, dict):
                return resposta_erro('Esta análise é antiga ou inválida. Analise a foto novamente.', 409)
            ids_servicos = json_seguro(sessao[3], [])
            if not isinstance(ids_servicos, list) or not ids_servicos:
                return resposta_erro('A sessão não possui serviços válidos. Reinicie o visagismo.', 409)
            servicos = carregar_servicos(cursor, sessao[2], ids_servicos)
            if not servicos: return resposta_erro('Os serviços desta sessão não estão mais disponíveis.', 409)
            categoria = categoria_para_servicos(servicos)
            permitidos = {'barba'} if categoria == 'barba' else ({'cabelo', 'barba', 'ambos'} if categoria == 'barba_cabelo' else {'cabelo'})
            alvo_padrao = 'ambos' if categoria == 'barba_cabelo' else ('barba' if categoria == 'barba' else 'cabelo')
            alvo = str(dados.get('alvo') or alvo_padrao).strip().lower()
            if cor and alvo not in permitidos:
                return resposta_erro('A cor só pode ser aplicada à área coberta pelos serviços escolhidos.', 400)
            if alvo not in ('cabelo', 'barba', 'ambos'):
                return resposta_erro('Informe uma área de coloração válida.')
            corte = None
            referencia_rota = None
            if id_corte:
                if servicos_somente_cor(servicos):
                    return resposta_erro('Esta sessão permite somente coloração, sem mudança de corte.', 400)
                cursor.execute('SELECT ID_CORTE, NOME, DESCRICAO, CATEGORIA, IMAGEM_ROTA, ATIVO, GENERO FROM CORTE_VISAGISMO WHERE ID_CORTE=? AND ATIVO=1', (id_corte,))
                linha_corte = cursor.fetchone()
                if not linha_corte: return resposta_erro('Corte ativo não encontrado.', 404)
                corte = serializar_corte(linha_corte, cursor=cursor)
                referencia_rota = linha_corte[4]
                if not corte['ativo']:
                    return resposta_erro('Corte ativo não encontrado.', 404)
                if not corte_compativel_servicos(corte, servicos):
                    return resposta_erro('O corte não é compatível com os serviços desta sessão.', 400)
                recomendacoes = analise.get('recomendacoes') or []
                modo_manual = analise.get('modo') == 'manual' or (analise.get('apenas_cor') and not recomendacoes)
                if not modo_manual:
                    if analise.get('versao_analise') != 2 or len(recomendacoes) != 1:
                        return resposta_erro('Esta análise é antiga. Analise a foto novamente para receber uma recomendação única.', 409)
                    recomendado = recomendacoes[0]
                    if recomendado.get('id_corte') != id_corte:
                        return resposta_erro('Use somente o corte recomendado nesta análise.', 400)
                    if recomendado.get('compativel_com_cabelo_existente') is not True:
                        return resposta_erro('Este corte não é viável com o cabelo visível. Analise a foto novamente.', 422)
                    if recomendado.get('nome') != corte['nome']:
                        return resposta_erro('O corte recomendado foi alterado no catálogo. Analise a foto novamente.', 409)
                    if not isinstance(analise.get('caracteristicas'), dict):
                        return resposta_erro('As características da análise estão incompletas. Analise novamente.', 409)
            elif not servicos_somente_cor(servicos):
                return resposta_erro('Selecione o corte recomendado ou use o fluxo de coloração.', 400)
            if motivo_sem_ia():
                return resposta_erro('A simulação por IA está indisponível. Configure a integração no servidor.', 503)
            foto_nome = sessao[0]
            if not isinstance(foto_nome, str) or os.path.basename(foto_nome) != foto_nome:
                return resposta_erro('A foto desta sessão não está disponível. Envie uma nova foto.', 409)
            try:
                foto = read_image('visagismo/fotos', foto_nome, legacy_folder=app.config['VISAGISMO_FOTOS_FOLDER'], cursor=cursor)
            except FileNotFoundError:
                return resposta_erro('A foto desta sessão não está disponível. Envie uma nova foto.', 409)
            if not foto or len(foto) > app.config['MAX_VISAGISMO_IMAGE_BYTES']:
                return resposta_erro('A foto deve ter até 10 MB.', 400)
            imagens = [imagem_para_edicao('cliente', foto)]
            if corte and modo_manual:
                # Manual catalog selection remains available, but must be checked
                # against the actual photograph before editing an impossible cut.
                analise_nova = analisar_com_ia(foto, [corte], categoria)
                analise = {**analise_nova, 'modo': 'manual', 'categoria': categoria,
                           'versao_analise': 2, 'recomendacoes': [{**corte, **analise_nova['recomendacoes'][0]}]}
            referencia_utilizada = False
            aviso = None
            if corte:
                try:
                    referencia = carregar_referencia_corte(referencia_rota, cursor=cursor)
                except (ValueError, OSError):
                    referencia = None
                if referencia:
                    imagens.append(imagem_para_edicao('referencia_catalogo', referencia[0]))
                    referencia_utilizada = True
                else:
                    aviso = 'A referência visual do catálogo está indisponível. A simulação usa o nome e a descrição do corte; a fidelidade à imagem de referência não foi verificada.'
            prompt = prompt_simulacao(corte, categoria, analise, cor, alvo, referencia_utilizada)
            try:
                resposta = OpenAI(api_key=app.config['OPENAI_API_KEY']).images.edit(
                    image=imagens, prompt=prompt,
                    **parametros_edicao(app.config['VISAGISMO_IMAGE_MODEL'], app.config.get('VISAGISMO_IMAGE_QUALITY', 'medium')))
            except Exception as erro:
                return resposta_erro(traduzir_erro_openai(erro), 502)
            try:
                dados_imagem = base64.b64decode(resposta.data[0].b64_json, validate=True)
                mime_imagem(dados_imagem)
                if len(dados_imagem) > app.config['MAX_VISAGISMO_IMAGE_BYTES']:
                    raise ValueError('oversized result')
            except (ValueError, TypeError, AttributeError, IndexError):
                return resposta_erro('A IA não retornou uma imagem válida. Tente novamente.', 502)
            imagem = batch.save(dados_imagem, 'visagismo/resultados', owner_id=usuario['id_usuario'])
            nome = imagem.filename
            dados_antes_log = capturar_registro(cursor, 'VISAGISMO_SESSAO', 'ID_VISAGISMO', id_visagismo)
            cursor.execute('UPDATE VISAGISMO_SESSAO SET ID_CORTE_SIMULADO = ?, RESULTADO_ROTA = ?, ANALISE_JSON = ? WHERE ID_VISAGISMO = ?',
                           (id_corte, nome, json.dumps(analise, ensure_ascii=False), id_visagismo))
            con.commit()
            persistido = True
            batch.commit()
            registrar_registro(cursor, 'UPDATE', 'VISAGISMO_SESSAO', 'ID_VISAGISMO', id_visagismo,
                               dados_antes=dados_antes_log, id_usuario=usuario['id_usuario'])
            return jsonify({'mensagem': {'informacao': 'Simulação gerada.', 'tipo': 'sucesso'},
                            'imagem_url': f'/uploads/visagismo/resultados/{nome}',
                            'referencia_utilizada': referencia_utilizada, 'aviso': aviso})
        finally:
            encerrar_transacao_imagens(con, cursor, batch, persistido)
    except ErroVisagismoIA as erro:
        return resposta_erro(str(erro), erro.status)
    except ImageStorageError as erro:
        return resposta_erro(str(erro), erro.status)
    except ValueError as erro:
        return resposta_erro(str(erro), 400)
    except Exception:
        app.logger.exception('Falha ao simular visagismo.')
        return resposta_erro('Não foi possível gerar a simulação. Tente novamente.', 500)


def parse_data(texto):
    try: return datetime.strptime(str(texto), '%Y-%m-%d').date()
    except ValueError: raise ValueError('Data inválida. Use AAAA-MM-DD.')


def intervalos_do_dia(cursor, id_barbearia, dia):
    cursor.execute('''SELECT ENTRADA_MANHA, SAIDA_MANHA, ENTRADA_TARDE, SAIDA_TARDE
                      FROM DIAS_DE_SERVICO WHERE ID_USUARIO=? AND DIAS=?''',
                   (id_barbearia, DIAS_SEMANA[dia.weekday()]))
    linha = cursor.fetchone()
    if not linha: return []
    resultado = []
    for inicio, fim in ((linha[0], linha[1]), (linha[2], linha[3])):
        if inicio and fim:
            resultado.append((datetime.combine(dia, inicio), datetime.combine(dia, fim)))
    return resultado


def buscar_funcionario(cursor, id_barbearia, id_funcionario):
    """Valida que o profissional está ativo e pertence à barbearia."""
    cursor.execute('SELECT ID_FUNCIONARIO,NOME,DESCRICAO FROM FUNCIONARIO WHERE ID_BARBEARIA=? AND ID_FUNCIONARIO=? AND ATIVO=1',(id_barbearia,id_funcionario))
    linha = cursor.fetchone()
    if not linha:
        return None
    return {'id_funcionario': linha[0], 'nome': linha[1], 'descricao': linha[2]}


def profissional_opcional(valor):
    """Ausência explícita usa a agenda do salão; IDs fornecidos devem ser válidos."""
    if valor is None or valor == '':
        return None
    if isinstance(valor, bool) or not re.fullmatch(r'[1-9]\d*', str(valor)):
        raise ValueError('Profissional inválido.')
    resultado = int(valor)
    if resultado > 2147483647:
        raise ValueError('Profissional inválido.')
    return resultado


def servicos_do_funcionario(cursor, id_barbearia, id_funcionario):
    cursor.execute('''SELECT SPF.ID_SERVICO
                      FROM SERVICO_POR_FUNCIONARIO SPF
                      INNER JOIN SERVICO S ON S.ID_SERVICO = SPF.ID_SERVICO
                      WHERE SPF.ID_FUNCIONARIO = ? AND S.ID_USUARIO = ? AND S.ATIVO=1''',
                   (id_funcionario, id_barbearia))
    return {linha[0] for linha in cursor.fetchall()}


def dias_semana_do_funcionario(cursor, id_funcionario):
    cursor.execute('SELECT HORARIOS_CONFIGURADOS FROM FUNCIONARIO WHERE ID_FUNCIONARIO=?',(id_funcionario,))
    configurado=cursor.fetchone()
    if configurado and configurado[0]:
        cursor.execute('SELECT DISTINCT DIA FROM FUNCIONARIO_HORARIO WHERE ID_FUNCIONARIO=?',(id_funcionario,))
        return {str(r[0]).strip().lower() for r in cursor.fetchall()}
    cursor.execute('''SELECT DISTINCT D.DIAS
                      FROM FUNCIONARIO_DIA FD
                      INNER JOIN DIAS_DE_SERVICO D ON D.ID_DIA = FD.ID_DIA
                      WHERE FD.ID_FUNCIONARIO = ?''', (id_funcionario,))
    return {str(linha[0]).strip().lower() for linha in cursor.fetchall() if linha[0]}


def horarios_disponiveis(cursor, id_barbearia, dia, duracao_minutos, id_funcionario=None):
    if duracao_minutos <= 0: return []
    # Com barbeiro escolhido, a ocupação é só a agenda dele; sem escolha, a da barbearia toda.
    # Agendamentos concluídos ou cancelados não bloqueiam novos horários.
    if id_funcionario:
        cursor.execute('''SELECT INICIO_EM, FIM_EM FROM AGENDAMENTO
                          WHERE (ID_FUNCIONARIO=? OR (ID_BARBEARIA=? AND ID_FUNCIONARIO IS NULL)) AND STATUS IN ('agendado', 'confirmado')
                            AND INICIO_EM < ? AND FIM_EM > ?''',
                       (id_funcionario, id_barbearia, datetime.combine(dia + timedelta(days=1), time.min), datetime.combine(dia, time.min)))
    else:
        cursor.execute('''SELECT INICIO_EM, FIM_EM FROM AGENDAMENTO
                          WHERE ID_BARBEARIA=? AND STATUS IN ('agendado', 'confirmado')
                            AND INICIO_EM < ? AND FIM_EM > ?''',
                       (id_barbearia, datetime.combine(dia + timedelta(days=1), time.min), datetime.combine(dia, time.min)))
    ocupados = cursor.fetchall(); agora = datetime.now(); disponiveis = []
    from agenda_gestao import intervalos_profissional, bloqueios_intervalo
    intervalos = intervalos_profissional(cursor, id_barbearia, dia, id_funcionario)
    bloqueios = bloqueios_intervalo(cursor,id_barbearia,id_funcionario,datetime.combine(dia,time.min),datetime.combine(dia+timedelta(days=1),time.min))
    # O passo acompanha a duração total dos serviços escolhidos, por isso
    # horários quebrados (ex.: 08:40 para um serviço de 40 min) aparecem.
    passo = max(5, int(duracao_minutos))
    for inicio_turno, fim_turno in intervalos:
        candidato = inicio_turno
        while candidato + timedelta(minutes=duracao_minutos) <= fim_turno:
            fim = candidato + timedelta(minutes=duracao_minutos)
            ocupado = any(candidato < fim_ocupado and fim > inicio_ocupado for inicio_ocupado, fim_ocupado in ocupados)
            bloqueado = any(candidato<b and fim>a for a,b in bloqueios)
            livre = candidato >= agora and not ocupado and not bloqueado
            disponiveis.append({'horario': candidato.strftime('%H:%M'), 'fim': fim.strftime('%H:%M'), 'disponivel': livre, 'lista_espera_disponivel': candidato > agora and ocupado and not bloqueado})
            candidato += timedelta(minutes=passo)
    return disponiveis


@app.route('/agendamentos/horarios', methods=['GET'])
def listar_horarios_agendamento():
    try:
        id_barbearia = request.args.get('id_barbearia', type=int); ids = ids_servicos_da_requisicao(request.args)
        dia = parse_data(request.args.get('data'))
        id_funcionario = profissional_opcional(request.args.get('id_funcionario'))
        if not id_barbearia or not ids: return resposta_erro('Informe barbearia e serviços.')
        if dia < date.today(): return resposta_erro('Não é possível agendar em data anterior à atual.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            servicos = carregar_servicos(cursor, id_barbearia, ids)
            if not servicos: return resposta_erro('Serviços inválidos para esta barbearia.', 400)
            funcionario = None
            if id_funcionario:
                funcionario = buscar_funcionario(cursor, id_barbearia, id_funcionario)
                if not funcionario: return resposta_erro('Profissional não encontrado nesta barbearia.', 404)
                if not set(ids) <= servicos_do_funcionario(cursor, id_barbearia, id_funcionario):
                    return resposta_erro('Este profissional não atende todos os serviços escolhidos.', 400)
            duracao = sum(servico['duracao'] for servico in servicos)
            from agenda_gestao import precos_servicos
            precificados=precos_servicos(cursor,servicos,id_funcionario)
            return jsonify({'mensagem': {'informacao': 'Horários consultados.', 'tipo': 'sucesso'},
                            'data': dia.isoformat(), 'duracao_minutos': duracao,
                            'funcionario': funcionario,'servicos':precificados,'generos_servico':generos_servicos(servicos),'valor_total':float(sum((dinheiro(s['preco']) for s in precificados),Decimal('0.00'))),
                            'horarios': horarios_disponiveis(cursor, id_barbearia, dia, duracao, id_funcionario)})
        finally:
            cursor.close(); con.close()
    except ValueError as erro: return resposta_erro(str(erro))
    except Exception as erro: return resposta_erro(f'Erro ao consultar horários: {erro}', 500)


@app.route('/agendamentos', methods=['POST'])
def criar_agendamento():
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para agendar.', 401)
    if int(usuario.get('tipo', -1)) not in (0,1,2,3): return resposta_erro('Sem permissão para criar agendamentos.', 403)
    try:
        dados = request.get_json(silent=True) or {}
        id_barbearia = dados.get('id_barbearia'); ids = ids_servicos_da_requisicao(dados)
        if int(usuario.get('tipo',-1)) == 2: id_barbearia=usuario['id_usuario']
        if int(usuario.get('tipo',-1)) == 0: id_barbearia=request.args.get('id_barbearia') or id_barbearia
        id_funcionario = profissional_opcional(dados.get('id_funcionario'))
        dia = parse_data(dados.get('data')); horario = str(dados.get('horario', ''))
        try: inicio = datetime.combine(dia, datetime.strptime(horario, '%H:%M').time())
        except ValueError: return resposta_erro('Horário inválido.')
        if dia < date.today() or inicio < datetime.now(): return resposta_erro('Não é possível agendar no passado.')
        if not ids: return resposta_erro('Informe os serviços.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            tipo=int(usuario.get('tipo',-1))
            from termos import exigir_aceite
            exigir_aceite(cursor,usuario['id_usuario'])
            id_cliente=usuario['id_usuario'] if tipo==1 else int(dados.get('id_cliente') or 0)
            if tipo in (0,2,3):
                from agenda_gestao import escopo
                id_barbearia=escopo(cursor,usuario,True,True)
                if tipo==3:
                    fun=funcionario_logado(cursor,usuario)
                    if id_funcionario and id_funcionario!=fun[0]: return resposta_erro('Só é possível reservar a própria agenda.',403)
                    id_funcionario=fun[0]
                if not id_cliente: return resposta_erro('Selecione o cliente.')
            if not id_barbearia: return resposta_erro('Informe a barbearia.')
            if tipo!=1:
                cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=1 AND ATIVO=1',(id_cliente,))
                if not cursor.fetchone(): return resposta_erro('Cliente não disponível.',404)
            servicos = carregar_servicos(cursor, int(id_barbearia), ids)
            if not servicos: return resposta_erro('Serviços inválidos para a barbearia.', 400)
            escolha=validar_escolha_corte(cursor,dados,id_cliente,int(id_barbearia),servicos)
            funcionario = None
            if id_funcionario:
                funcionario = buscar_funcionario(cursor, int(id_barbearia), id_funcionario)
                if not funcionario: return resposta_erro('Profissional não encontrado nesta barbearia.', 404)
                if not set(ids) <= servicos_do_funcionario(cursor, int(id_barbearia), id_funcionario):
                    return resposta_erro('Este profissional não atende todos os serviços escolhidos.', 400)
            fim = inicio + timedelta(minutes=sum(servico['duracao'] for servico in servicos))
            from agenda_gestao import validar_expediente
            validar_expediente(cursor,int(id_barbearia),id_funcionario,inicio,fim)
            # Trava a barbearia durante a validação. Isso serializa tentativas
            # concorrentes inclusive quando ainda não existe agendamento no dia.
            cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1 WITH LOCK', (int(id_barbearia),))
            if not cursor.fetchone(): return resposta_erro('Barbearia não encontrada.', 404)
            if inicio < datetime.now(): return resposta_erro('Não é possível agendar no passado.')
            servicos_atuais=carregar_servicos(cursor,int(id_barbearia),ids)
            if not servicos_atuais: return resposta_erro('Os serviços não estão mais disponíveis.',409)
            if id_funcionario and (not buscar_funcionario(cursor,int(id_barbearia),id_funcionario) or not set(ids)<=servicos_do_funcionario(cursor,int(id_barbearia),id_funcionario)):
                return resposta_erro('O profissional não está mais disponível para estes serviços.',409)
            servicos=servicos_atuais
            escolha=validar_escolha_corte(cursor,dados,id_cliente,int(id_barbearia),servicos)
            fim=inicio+timedelta(minutes=sum(s['duracao'] for s in servicos))
            validar_expediente(cursor,int(id_barbearia),id_funcionario,inicio,fim)
            # O lock + verificação no mesmo commit impede duas reservas simultâneas no mesmo intervalo.
            # Agendamentos ativos bloqueiam o horário; apenas os cancelados e
            # finalizados o liberam.
            if id_funcionario:
                cursor.execute('''SELECT ID_AGENDAMENTO FROM AGENDAMENTO
                                  WHERE ID_BARBEARIA=? AND (ID_FUNCIONARIO=? OR ID_FUNCIONARIO IS NULL) AND STATUS IN ('agendado', 'confirmado') AND INICIO_EM < ? AND FIM_EM > ?
                                      WITH LOCK''', (int(id_barbearia), id_funcionario, fim, inicio))
            else:
                cursor.execute('''SELECT ID_AGENDAMENTO FROM AGENDAMENTO
                                  WHERE ID_BARBEARIA=? AND STATUS IN ('agendado', 'confirmado') AND INICIO_EM < ? AND FIM_EM > ?
                                      WITH LOCK''', (int(id_barbearia), fim, inicio))
            if cursor.fetchone(): return resposta_erro('Este horário acabou de ser reservado. Escolha outro.', 409)
            from taxa_plataforma import resumo_servicos,confirmar_resumo,exigir_aceites,registrar_taxa
            exigir_aceites(cursor,usuario['id_usuario'],id_cliente,int(id_barbearia))
            resumo_previo=resumo_servicos(cursor,int(id_barbearia),id_funcionario,servicos,usuario['id_usuario'],id_cliente)
            confirmar_resumo(dados,resumo_previo)
            cursor.execute('''INSERT INTO AGENDAMENTO
                              (ID_AGENDAMENTO, ID_USUARIO, ID_BARBEARIA, ID_FUNCIONARIO, INICIO_EM, FIM_EM, SERVICOS_JSON, ID_CORTE, ID_VISAGISMO, STATUS,ESCOLHA_CORTE)
                              VALUES (NEXT VALUE FOR SEQ_AGENDAMENTO, ?, ?, ?, ?, ?, ?, ?, ?, 'agendado',?)
                              RETURNING ID_AGENDAMENTO''',
                           (id_cliente, int(id_barbearia), id_funcionario, inicio, fim, json.dumps(ids),
                            dados.get('id_corte'), dados.get('id_visagismo'),escolha))
            id_agendamento = cursor.fetchone()[0]
            valor_total = float(salvar_snapshot(cursor, id_agendamento, servicos, inicio, fim,id_funcionario,resumo_previo['precos_servicos']))
            # Persist exactly the confirmed price even if an administrator changes
            # a catalog price between the independent reads of READ COMMITTED.
            if valor_total != resumo_previo['valor_base']:
                from taxa_plataforma import ResumoAlterado
                raise ResumoAlterado('Os preços mudaram. Confira o novo resumo antes de confirmar.')
            resumo=registrar_taxa(cursor,'agendamento',id_agendamento,valor_total,0,usuario['id_usuario'],id_cliente,int(id_barbearia))
            from agenda_gestao import enfileirar_evento
            nova=buscar_agendamento(cursor,id_agendamento)
            enfileirar_evento(cursor,nova,'confirmacao')
            enfileirar_evento(cursor,nova,'lembrete')
            con.commit()
            registrar_registro(
                cursor, 'INSERT', 'AGENDAMENTO', 'ID_AGENDAMENTO', id_agendamento,
                id_usuario=usuario['id_usuario']
            )
            return jsonify({'mensagem': {'informacao': 'Agendamento realizado!', 'tipo': 'sucesso'},
                            'agendamento': {'id_agendamento': id_agendamento, 'inicio_em': inicio.isoformat(), 'fim_em': fim.isoformat(),
                                            'id_funcionario': id_funcionario, 'valor_servicos':valor_total,
                                            'valor_total': resumo['valor_total_cliente'],'resumo':resumo,
                                            'status': 'agendado','escolha_corte':escolha,'corte_nome':nome_escolha_corte(escolha,servicos)}}), 201
        except Exception:
            con.rollback();raise
        finally:
            cursor.close(); con.close()
    except ValueError as erro: return resposta_erro(str(erro),getattr(erro,'status',400))
    except Exception as erro: return resposta_erro(f'Não foi possível criar o agendamento: {erro}', 500)


COLUNAS_AGENDAMENTO = ('ID_AGENDAMENTO, ID_USUARIO, ID_BARBEARIA, ID_FUNCIONARIO, INICIO_EM, '
                       'FIM_EM, SERVICOS_JSON, ID_CORTE, ID_VISAGISMO, STATUS, CRIADO_EM,ESCOLHA_CORTE')


def email_do_cliente(cursor, id_usuario):
    cursor.execute('SELECT NOME, EMAIL FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
    linha = cursor.fetchone()
    return {'nome': linha[0], 'email': linha[1]} if linha else {'nome': '', 'email': ''}


def email_da_barbearia(cursor, id_barbearia):
    cursor.execute('SELECT NOME, EMAIL FROM USUARIO WHERE ID_USUARIO = ?', (id_barbearia,))
    usuario = cursor.fetchone()
    cursor.execute('SELECT CONTATO_EMAIL FROM PERSONALIZACAO WHERE ID_USUARIO = ?', (id_barbearia,))
    contato = cursor.fetchone()
    email = (contato[0] if contato and contato[0] else (usuario[1] if usuario else ''))
    return {'nome': usuario[0] if usuario else 'Barbearia', 'email': (email or '').strip()}


def serializar_agendamento(cursor, linha, usuario=None):
    ag = {'id_agendamento': linha[0], 'id_usuario': linha[1], 'id_barbearia': linha[2],
          'id_funcionario': linha[3], 'inicio_em': linha[4].isoformat(), 'fim_em': linha[5].isoformat(),
          'servicos': json_seguro(linha[6], []), 'id_corte': linha[7], 'id_visagismo': linha[8],
          'status': linha[9],'escolha_corte':linha[11] if len(linha)>11 else None}
    cliente = email_do_cliente(cursor, linha[1])
    barbearia = email_da_barbearia(cursor, linha[2])
    ag['cliente_nome'] = cliente['nome']
    ag['barbearia_nome'] = barbearia['nome']
    if linha[3]:
        cursor.execute('SELECT NOME FROM FUNCIONARIO WHERE ID_FUNCIONARIO = ?', (linha[3],))
        func = cursor.fetchone()
        ag['funcionario_nome'] = func[0] if func else None
    if ag['servicos']:
        marcadores = ','.join('?' for _ in ag['servicos'])
        cursor.execute(f'SELECT NOME_SERVICO FROM SERVICO WHERE ID_SERVICO IN ({marcadores})', list(ag['servicos']))
        ag['servicos_nomes'] = [l[0] for l in cursor.fetchall()]
        cursor.execute(f'SELECT PRECO FROM SERVICO WHERE ID_SERVICO IN ({marcadores})', list(ag['servicos']))
        ag['valor_total'] = round(float(sum(float(l[0] or 0) for l in cursor.fetchall())), 2)
    else:
        ag['valor_total'] = 0.0
    if linha[7]:
        cursor.execute('SELECT NOME, IMAGEM_ROTA FROM CORTE_VISAGISMO WHERE ID_CORTE = ?', (linha[7],))
        corte = cursor.fetchone()
        ag['corte_nome'] = corte[0] if corte else None
        ag['corte_imagem_url'] = url_corte(corte[1], cursor=cursor) if corte else None
    if linha[8]:
        cursor.execute('SELECT FOTO_ROTA, RESULTADO_ROTA FROM VISAGISMO_SESSAO WHERE ID_VISAGISMO = ?', (linha[8],))
        sessao = cursor.fetchone()
        ag['visagismo_foto_url'] = f'/uploads/visagismo/fotos/{sessao[0]}' if sessao and sessao[0] else None
        # A foto do corte é a simulação gerada por IA; sem simulação, usa a referência do catálogo.
        if sessao and sessao[1]:
            ag['corte_imagem_url'] = f'/uploads/visagismo/resultados/{sessao[1]}'
    cursor.execute('''SELECT H.ID_HISTORICO, H.STATUS, H.REGISTRADO_EM, U.NOME
                      FROM AGENDAMENTO_HISTORICO H
                      LEFT JOIN USUARIO U ON U.ID_USUARIO = H.ID_USUARIO_RESPONSAVEL
                      WHERE H.ID_AGENDAMENTO = ?
                      ORDER BY H.REGISTRADO_EM DESC, H.ID_HISTORICO DESC''', (linha[0],))
    ag['historico_atendimento'] = [
        {
            'id_historico': historico[0],
            'status': historico[1],
            'registrado_em': historico[2].isoformat() if historico[2] else None,
            'responsavel_nome': historico[3] or 'Barbearia'
        }
        for historico in cursor.fetchall()
    ]
    cursor.execute('SELECT VALOR_TOTAL,DURACAO_MINUTOS,SERVICOS_SNAPSHOT FROM AGENDAMENTO WHERE ID_AGENDAMENTO=?', (linha[0],))
    snapshot = cursor.fetchone()
    if snapshot and len(snapshot) != 3: snapshot = None
    ag['valor_historico_disponivel'] = bool(snapshot and snapshot[0] is not None)
    ag['valor_total'] = float(snapshot[0]) if snapshot and snapshot[0] is not None else None
    from taxa_plataforma import resumo_registrado
    ag['valor_servicos']=ag['valor_total']
    ag['resumo']=resumo_registrado(cursor,'agendamento',linha[0],ag['valor_total'],status=linha[9])
    if ag['resumo']:ag['valor_total']=ag['resumo']['valor_total_cliente']
    if snapshot and snapshot[2]:
        ag['servicos_snapshot'] = json_seguro(snapshot[2], [])
        ag['servicos_nomes'] = [item['nome'] for item in ag['servicos_snapshot']]
    if ag['escolha_corte'] in ('na_hora','profissional'):
        genero_snapshot=ag.get('servicos_snapshot',[])
        if not genero_snapshot or any('genero' not in s for s in genero_snapshot):
            ids=ag['servicos'];marcadores=','.join('?' for _ in ids)
            cursor.execute(f'SELECT GENERO FROM SERVICO WHERE ID_USUARIO=? AND ID_SERVICO IN ({marcadores})',[linha[2],*ids])
            genero_snapshot=[{'genero':r[0]} for r in cursor.fetchall()]
        ag['corte_nome']=nome_escolha_corte(ag['escolha_corte'],genero_snapshot)
        ag['corte_imagem_url']=None
    ag['permite_cancelar'] = linha[9] in ('agendado','confirmado')
    ag['permite_reagendar'] = linha[9] in ('agendado','confirmado')
    from ranking_avaliacoes import dados_avaliacao
    ag.update(dados_avaliacao(cursor, linha))
    ag['pode_avaliar'] = bool(ag['pode_avaliar'] and usuario
                             and int(usuario.get('tipo', -1)) == 1
                             and int(usuario['id_usuario']) == int(linha[1]))
    return ag


def buscar_agendamento(cursor, id_agendamento):
    cursor.execute(f'SELECT {COLUNAS_AGENDAMENTO} FROM AGENDAMENTO WHERE ID_AGENDAMENTO = ?', (id_agendamento,))
    return cursor.fetchone()


def pode_ver_agendamento(usuario, linha, id_barbearia_alvo=None):
    tipo = int(usuario.get('tipo', -1))
    if tipo == 0:
        return True
    if tipo == 1:
        return int(linha[1]) == int(usuario['id_usuario'])
    if tipo != 2: return False
    return int(linha[2]) == int(id_barbearia_alvo or usuario['id_usuario'])


def notificar(destino, assunto, texto, remetente='Cortaê'):
    if not destino.get('email'):
        return False
    try:
        return bool(enviar_aviso_email(destino['email'], destino['nome'] or 'cliente', assunto, texto, remetente))
    except Exception:
        return False


@app.route('/agendamentos', methods=['GET'])
def listar_agendamentos():
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para ver agendamentos.', 401)
    try:
        tipo = int(usuario.get('tipo', -1))
        status = request.args.get('status')
        data = request.args.get('data')
        con = conectar_banco(); cursor = con.cursor()
        try:
            sql = f'SELECT {COLUNAS_AGENDAMENTO} FROM AGENDAMENTO WHERE 1 = 1'
            params = []
            if tipo == 1:
                sql += ' AND ID_USUARIO = ?'
                params.append(usuario['id_usuario'])
            elif tipo == 3:
                fun = funcionario_logado(cursor, usuario)
                if not fun: return resposta_erro('Acesso do barbeiro desativado.', 403)
                sql += ' AND ID_FUNCIONARIO = ? AND ID_BARBEARIA = ?'
                params.extend([fun[0], fun[1]])
            elif tipo == 2:
                alvo = pegar_id_barbearia_alvo() or usuario['id_usuario']
                sql += ' AND ID_BARBEARIA = ?'
                params.append(alvo)
            else:
                if request.args.get('id_barbearia', type=int):
                    sql += ' AND ID_BARBEARIA = ?'
                    params.append(request.args.get('id_barbearia', type=int))
                if request.args.get('id_usuario', type=int):
                    sql += ' AND ID_USUARIO = ?'
                    params.append(request.args.get('id_usuario', type=int))
            if status:
                sql += ' AND STATUS = ?'
                params.append(status)
            if data:
                sql += ' AND CAST(INICIO_EM AS DATE) = ?'
                params.append(parse_data(data))
            sql += ' ORDER BY INICIO_EM'
            cursor.execute(sql, params)
            return jsonify({'mensagem': {'informacao': 'Agendamentos listados.', 'tipo': 'sucesso'},
                            'agendamentos': [serializar_agendamento(cursor, linha, usuario) for linha in cursor.fetchall()]})
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Não foi possível listar agendamentos: {erro}', 500)


@app.route('/agendamentos/<int:id_agendamento>/cancelar', methods=['PUT'])
def cancelar_agendamento(id_agendamento):
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para cancelar.', 401)
    try:
        con = conectar_banco(); cursor = con.cursor()
        try:
            linha = travar_agendamento(cursor, id_agendamento)
            if not linha: return resposta_erro('Agendamento não encontrado.', 404)
            if not acesso_agendamento(cursor, usuario, linha):
                return resposta_erro('Sem permissão para cancelar este agendamento.', 403)
            from arkhe_cartao import obter_tentativa, CartaoErro, resposta_erro as erro_cartao
            try:
                tentativa = obter_tentativa(cursor, 'agendamento', id_agendamento)
                if tentativa and tentativa['estado'] in ('processando', 'incerto'):
                    return erro_cartao(CartaoErro('Confira o recebimento do cartão na Arkhé antes de cancelar.', 409, tentativa['estado']))
            except CartaoErro as exc:
                return erro_cartao(exc)
            if linha[9] in ('concluido', 'faltou'):
                return resposta_erro('Atendimento finalizado não pode ser cancelado.', 400)
            from agenda_gestao import validar_prazo,enfileirar_evento
            if linha[9] == 'cancelado':
                return mensagem_json('Agendamento já estava cancelado.', 'aviso')
            validar_prazo(cursor,usuario,linha,'cancelamento')
            dados_antes_log = capturar_registro(
                cursor, 'AGENDAMENTO', 'ID_AGENDAMENTO', id_agendamento
            )
            cursor.execute("UPDATE AGENDAMENTO SET STATUS = 'cancelado' WHERE ID_AGENDAMENTO = ?", (id_agendamento,))
            evento_id=registrar_evento(cursor, linha, 'cancelado', usuario['id_usuario'])
            cursor.execute("UPDATE EMAIL_OUTBOX SET ESTADO='cancelado' WHERE ID_AGENDAMENTO=? AND ESTADO='pendente' AND EVENTO IN ('confirmacao','reagendamento','lembrete')",(id_agendamento,))
            enfileirar_evento(cursor,linha,'cancelamento',evento_id)
            enfileirar_liberacao(cursor, linha)
            con.commit()
            registrar_registro(
                cursor, 'UPDATE', 'AGENDAMENTO', 'ID_AGENDAMENTO', id_agendamento,
                dados_antes=dados_antes_log, id_usuario=usuario['id_usuario']
            )
            return jsonify(mensagem={'informacao':'Agendamento cancelado. Aviso por e-mail agendado.','tipo':'sucesso'},email_agendado=True)
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Não foi possível cancelar: {erro}', 500)


@app.route('/agendamentos/<int:id_agendamento>/reagendar', methods=['PUT'])
def reagendar_agendamento(id_agendamento):
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para reagendar.', 401)
    try:
        dados = request.get_json(silent=True) or {}
        dia = parse_data(dados.get('data')); horario = str(dados.get('horario', ''))
        try: inicio = datetime.combine(dia, datetime.strptime(horario, '%H:%M').time())
        except ValueError: return resposta_erro('Horário inválido.')
        if dia < date.today() or inicio < datetime.now(): return resposta_erro('Não é possível agendar no passado.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            linha = travar_agendamento(cursor, id_agendamento)
            if not linha: return resposta_erro('Agendamento não encontrado.', 404)
            if not acesso_agendamento(cursor, usuario, linha):
                return resposta_erro('Sem permissão para reagendar.', 403)
            if linha[9] in ('concluido', 'faltou'):
                return resposta_erro('Atendimento finalizado não pode ser reagendado.', 400)
            if linha[9] == 'cancelado': return resposta_erro('Agendamento cancelado não pode ser reagendado.')
            from agenda_gestao import validar_prazo,enfileirar_evento,validar_expediente
            validar_prazo(cursor,usuario,linha,'reagendamento')
            ids = json_seguro(linha[6], [])
            # A disabled service remains part of an existing booking snapshot.
            cursor.execute('SELECT SERVICOS_SNAPSHOT FROM AGENDAMENTO WHERE ID_AGENDAMENTO=?',(id_agendamento,))
            snapshot=json_seguro(cursor.fetchone()[0],[])
            servicos = snapshot or carregar_servicos(cursor, linha[2], ids)
            if not servicos: return resposta_erro('Serviços do agendamento inválidos.', 400)
            try: id_func = int(dados.get('id_funcionario')) if dados.get('id_funcionario') not in (None, '') else linha[3]
            except (TypeError, ValueError): return resposta_erro('Profissional inválido.')
            if int(usuario.get('tipo', -1)) == 3 and id_func != linha[3]:
                return resposta_erro('O barbeiro não pode transferir este atendimento para outro profissional.', 403)
            if inicio == linha[4] and id_func == linha[3]:
                return jsonify(mensagem={'informacao': 'Este agendamento já está neste horário.', 'tipo': 'aviso'}, agendamento={'id_agendamento': id_agendamento, 'inicio_em': linha[4].isoformat(), 'fim_em': linha[5].isoformat()})
            if id_func and (not buscar_funcionario(cursor, linha[2], id_func)
                            or (id_func!=linha[3] and not set(ids) <= servicos_do_funcionario(cursor, linha[2], id_func))):
                return resposta_erro('Profissional inválido para estes serviços.', 400)
            fim = inicio + (linha[5] - linha[4])
            validar_expediente(cursor,linha[2],id_func,inicio,fim)
            cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (linha[2],))
            if id_func:
                cursor.execute('''SELECT ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_BARBEARIA=? AND (ID_FUNCIONARIO=? OR ID_FUNCIONARIO IS NULL)
                                  AND STATUS IN ('agendado', 'confirmado') AND INICIO_EM < ? AND FIM_EM > ?
                                  AND ID_AGENDAMENTO <> ? WITH LOCK''', (linha[2], id_func, fim, inicio, id_agendamento))
            else:
                cursor.execute('''SELECT ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_BARBEARIA=?
                                  AND STATUS IN ('agendado', 'confirmado') AND INICIO_EM < ? AND FIM_EM > ?
                                  AND ID_AGENDAMENTO <> ? WITH LOCK''', (linha[2], fim, inicio, id_agendamento))
            if cursor.fetchone(): return resposta_erro('Este horário está ocupado. Escolha outro.', 409)
            dados_antes_log = capturar_registro(
                cursor, 'AGENDAMENTO', 'ID_AGENDAMENTO', id_agendamento
            )
            cursor.execute('''UPDATE AGENDAMENTO SET INICIO_EM=?, FIM_EM=?, ID_FUNCIONARIO=?, STATUS='agendado'
                              WHERE ID_AGENDAMENTO=?''', (inicio, fim, id_func, id_agendamento))
            evento_id=registrar_evento(cursor, linha, 'remarcado', usuario['id_usuario'], inicio, fim)
            cursor.execute("UPDATE EMAIL_OUTBOX SET ESTADO='cancelado' WHERE ID_AGENDAMENTO=? AND ESTADO='pendente' AND EVENTO IN ('confirmacao','reagendamento','lembrete')",(id_agendamento,))
            nova=list(linha);nova[3]=id_func;nova[4]=inicio;nova[5]=fim
            enfileirar_evento(cursor,nova,'reagendamento',evento_id)
            enfileirar_evento(cursor,nova,'lembrete')
            enfileirar_liberacao(cursor, linha)
            con.commit()
            registrar_registro(
                cursor, 'UPDATE', 'AGENDAMENTO', 'ID_AGENDAMENTO', id_agendamento,
                dados_antes=dados_antes_log, id_usuario=usuario['id_usuario']
            )
            return jsonify(mensagem={'informacao':'Agendamento reagendado. Aviso por e-mail agendado.','tipo':'sucesso'},email_agendado=True,agendamento={'id_agendamento':id_agendamento,'inicio_em':inicio.isoformat(),'fim_em':fim.isoformat()})
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Não foi possível reagendar: {erro}', 500)


@app.route('/agendamentos/<int:id_agendamento>/status-atendimento', methods=['PUT'])
def registrar_status_atendimento(id_agendamento):
    """Registra manualmente se o cliente foi atendido ou não compareceu."""
    usuario = obter_usuario_logado()
    if not usuario:
        return resposta_erro('Faça login para registrar o atendimento.', 401)
    if int(usuario.get('tipo', -1)) not in (0, 2, 3):
        return resposta_erro('Apenas a barbearia pode registrar o atendimento.', 403)

    dados = request.get_json(silent=True) or {}
    status = str(dados.get('status', '')).strip().lower()
    if status not in ('concluido', 'faltou'):
        return resposta_erro("Informe o status 'concluido' ou 'faltou'.")

    try:
        con = conectar_banco(); cursor = con.cursor()
        try:
            linha = travar_agendamento(cursor, id_agendamento)
            if not linha:
                return resposta_erro('Agendamento não encontrado.', 404)
            if not acesso_agendamento(cursor, usuario, linha):
                return resposta_erro('Sem permissão para registrar este atendimento.', 403)
            if status == 'faltou':
                from arkhe_cartao import obter_tentativa, CartaoErro, resposta_erro as erro_cartao
                try:
                    tentativa = obter_tentativa(cursor, 'agendamento', id_agendamento)
                    if tentativa and tentativa['estado'] in ('processando', 'incerto'):
                        return erro_cartao(CartaoErro('Confira o recebimento do cartão na Arkhé antes de registrar falta.', 409, tentativa['estado']))
                except CartaoErro as exc:
                    return erro_cartao(exc)
            if linha[9] not in ('agendado', 'confirmado'):
                return resposta_erro('Este agendamento já foi finalizado ou cancelado.', 400)
            if linha[5] > datetime.now():
                return resposta_erro('O atendimento só pode ser registrado após o horário agendado.', 400)

            dados_antes_log = capturar_registro(
                cursor, 'AGENDAMENTO', 'ID_AGENDAMENTO', id_agendamento
            )
            if status == 'concluido' and dados.get('valor_realizado') is not None:
                if int(usuario.get('tipo', -1)) not in (0, 2):
                    return resposta_erro('Apenas a barbearia pode informar o valor histórico.', 403)
                from agenda_equipe import dinheiro
                valor_realizado = dinheiro(dados['valor_realizado'])
                if valor_realizado < 0 or valor_realizado > 9999999999: return resposta_erro('Valor realizado inválido.')
                cursor.execute('UPDATE AGENDAMENTO SET VALOR_TOTAL=? WHERE ID_AGENDAMENTO=? AND VALOR_TOTAL IS NULL', (valor_realizado, id_agendamento))
            cursor.execute('UPDATE AGENDAMENTO SET STATUS = ? WHERE ID_AGENDAMENTO = ?',
                           (status, id_agendamento))
            id_historico_log = registrar_evento(cursor, linha, status, usuario['id_usuario'])
            if status == 'concluido': registrar_comissao(cursor, linha)
            con.commit()
            registrar_registro(
                cursor, 'UPDATE', 'AGENDAMENTO', 'ID_AGENDAMENTO', id_agendamento,
                dados_antes=dados_antes_log, id_usuario=usuario['id_usuario']
            )
            registrar_registro(
                cursor, 'INSERT', 'AGENDAMENTO_HISTORICO', 'ID_HISTORICO',
                id_historico_log, id_usuario=usuario['id_usuario']
            )
            if status == 'concluido' and linha[3]:
                registrar_registro(cursor, 'INSERT', 'COMISSAO_ATENDIMENTO', 'ID_AGENDAMENTO', id_agendamento, id_usuario=usuario['id_usuario'])
            descricao = 'Atendimento concluído.' if status == 'concluido' else 'Falta do cliente registrada.'
            return jsonify({'mensagem': {'informacao': descricao, 'tipo': 'sucesso'},
                            'agendamento': {'id_agendamento': id_agendamento, 'status': status}})
        finally:
            cursor.close(); con.close()
    except ValueError as erro:
        return resposta_erro(str(erro))
    except Exception as erro:
        return resposta_erro(f'Não foi possível registrar o atendimento: {erro}', 500)


@app.route('/agendamentos/<int:id_agendamento>/avisar', methods=['POST'])
def avisar_cliente(id_agendamento):
    usuario = obter_usuario_logado()
    if not usuario: return resposta_erro('Faça login para enviar avisos.', 401)
    if int(usuario.get('tipo', -1)) not in (0, 2):
        return resposta_erro('Apenas a barbearia pode enviar avisos.', 403)
    try:
        texto = str((request.get_json(silent=True) or {}).get('texto', '')).strip()
        if not texto: return resposta_erro('Escreva o texto do aviso.')
        if len(texto) > 500: return resposta_erro('O aviso deve ter até 500 caracteres.')
        con = conectar_banco(); cursor = con.cursor()
        try:
            linha = buscar_agendamento(cursor, id_agendamento)
            if not linha: return resposta_erro('Agendamento não encontrado.', 404)
            if not pode_ver_agendamento(usuario, linha, pegar_id_barbearia_alvo()):
                return resposta_erro('Sem permissão para avisar este cliente.', 403)
            cursor.execute('INSERT INTO AVISO (ID_AVISO, ID_USUARIO, TEXTO, DATA_POSTAGEM) VALUES (NEXT VALUE FOR SEQ_AVISO, ?, ?, CURRENT_TIMESTAMP) RETURNING ID_AVISO',
                           (linha[1], texto))
            id_aviso = cursor.fetchone()[0]
            con.commit()
            registrar_registro(
                cursor, 'INSERT', 'AVISO', 'ID_AVISO', id_aviso,
                id_usuario=usuario['id_usuario']
            )
            cliente = email_do_cliente(cursor, linha[1])
            barbearia = email_da_barbearia(cursor, linha[2])
            email_ok = notificar(cliente, f"Aviso da {barbearia['nome']} (agendamento #{id_agendamento})",
                                 texto, barbearia['nome'])
            return jsonify({'mensagem': {'informacao': 'Aviso enviado.' + ('' if email_ok else ' (e-mail não enviado)'),
                                         'tipo': 'sucesso'}, 'email_enviado': email_ok}), 201
        finally:
            cursor.close(); con.close()
    except Exception as erro:
        return resposta_erro(f'Não foi possível enviar o aviso: {erro}', 500)


@app.route('/uploads/visagismo/<tipo>/<path:nome>', methods=['GET'])
def servir_upload_visagismo(tipo, nome):
    pastas = {'cortes': app.config['VISAGISMO_CORTES_FOLDER'], 'fotos': app.config['VISAGISMO_FOTOS_FOLDER'],
              'resultados': app.config['VISAGISMO_RESULTADOS_FOLDER']}
    if tipo not in pastas or not nome or '/' in nome or '\\' in nome or nome in {'.', '..'}:
        return resposta_erro('Arquivo não encontrado.', 404)
    # Drive objects stay private. Application ACL is checked before any byte fetch;
    # neither a guessed filename nor the old cliente_<id> prefix grants access.
    if tipo in {'fotos', 'resultados'}:
        usuario = obter_usuario_logado()
        if not usuario:
            return resposta_erro('Sem permissão para acessar esta imagem.', 403)
        tipo_usuario = int(usuario.get('tipo', -1))
        if tipo_usuario != 0:
            con = conectar_banco(); cursor = con.cursor()
            try:
                campo = 'FOTO_ROTA' if tipo == 'fotos' else 'RESULTADO_ROTA'
                if tipo_usuario == 3:
                    fun = funcionario_logado(cursor, usuario)
                    if not fun:
                        return resposta_erro('Sem permissão para acessar esta imagem.', 403)
                    cursor.execute(f'''SELECT FIRST 1 A.ID_AGENDAMENTO FROM AGENDAMENTO A
                        JOIN VISAGISMO_SESSAO V ON V.ID_VISAGISMO=A.ID_VISAGISMO
                        WHERE A.ID_FUNCIONARIO=? AND A.ID_BARBEARIA=? AND V.{campo}=?''', (fun[0], fun[1], nome))
                elif tipo_usuario == 2:
                    cursor.execute(f'SELECT FIRST 1 ID_VISAGISMO FROM VISAGISMO_SESSAO WHERE {campo}=? AND ID_BARBEARIA=?',
                                   (nome, usuario['id_usuario']))
                else:
                    cursor.execute(f'SELECT FIRST 1 ID_VISAGISMO FROM VISAGISMO_SESSAO WHERE {campo}=? AND ID_USUARIO=?',
                                   (nome, usuario['id_usuario']))
                if not cursor.fetchone():
                    return resposta_erro('Sem permissão para acessar esta imagem.', 403)
            finally:
                cursor.close(); con.close()
    return serve_image(f'visagismo/{tipo}', nome, legacy_folder=pastas[tipo])
