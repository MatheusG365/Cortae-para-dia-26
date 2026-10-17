from responses import mensagem_json
import os
import math
import json
import re

from flask import jsonify, request, send_from_directory

from application import app, conectar_banco
from auditoria import capturar_registro, registrar_registro
from image_storage import ImageBatch, ImageStorageError, serve_image, slot_state
from marketplace_perfil import business_images


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

# Public profile fields only. Payment credentials and team configuration are
# intentionally absent from this endpoint's SQL and request allowlist.
CAMPOS_PERFIL_PUBLICO = {
    'cor_primaria': ('COR_PRIMARIA', 7),
    'cor_secundaria': ('COR_SECUNDARIA', 7),
    'cor_terciaria': ('COR_TERCIARIA', 7),
    'cor_texto_primario': ('COR_TEXTO_PRIMARIO', 7),
    'cor_texto_secundario': ('COR_TEXTO_SECUNDARIO', 7),
    'historia': ('TEXTO', 1000),
    'localizacao': ('LOCALIZACAO', 100),
    'contato_telefone': ('CONTATO_TELEFONE', 20),
    'contato_email': ('CONTATO_EMAIL', 100),
    'instagram': ('INSTAGRAM', 100),
}


def validar_perfil_publico(dados):
    if not isinstance(dados, dict) or not dados:
        raise ValueError('Informe ao menos um campo do perfil.')
    if set(dados) - set(CAMPOS_PERFIL_PUBLICO):
        raise ValueError('O perfil aceita somente os campos públicos de apresentação e contato.')
    result = {}
    for campo, valor in dados.items():
        if not isinstance(valor, str):
            raise ValueError(f'O campo {campo} deve ser texto.')
        valor = valor.strip()
        if len(valor) > CAMPOS_PERFIL_PUBLICO[campo][1]:
            raise ValueError(f'O campo {campo} excede o tamanho máximo de {CAMPOS_PERFIL_PUBLICO[campo][1]} caracteres.')
        if campo.startswith('cor_') and not re.fullmatch(r'#[0-9a-fA-F]{6}', valor):
            raise ValueError('Informe as cores no formato #RRGGBB.')
        if campo == 'contato_email' and valor and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', valor):
            raise ValueError('Informe um e-mail de contato válido.')
        if campo == 'contato_telefone' and valor:
            valor = re.sub(r'\D', '', valor)
            if len(valor) not in (10, 11):
                raise ValueError('O telefone de contato deve conter DDD e 10 ou 11 números.')
        result[campo] = valor
    return result


def selecionar_perfil_publico(cursor, id_usuario):
    cursor.execute('SELECT ID_PERSONALIZACAO,' + ','.join(c[0] for c in CAMPOS_PERFIL_PUBLICO.values()) +
                   ' FROM PERSONALIZACAO WHERE ID_USUARIO=?', (id_usuario,))
    row = cursor.fetchone()
    if not row:
        return None
    return {'id_personalizacao': row[0], 'id_usuario': id_usuario,
            **{key: row[index + 1] or '' for index, key in enumerate(CAMPOS_PERFIL_PUBLICO)}}


@app.route('/barbearia/perfil', methods=['GET', 'PATCH'])
def perfil_publico_barbearia():
    usuario = obter_usuario_logado()
    if not usuario:
        return mensagem_json('Faça login.', 'erro'), 401
    if int(usuario.get('tipo', -1)) != 2:
        return mensagem_json('Somente a barbearia pode editar seu próprio perfil.', 'erro'), 403
    alteracoes = None
    if request.method == 'PATCH':
        try:
            alteracoes = validar_perfil_publico(request.get_json(silent=True))
        except ValueError as exc:
            return mensagem_json(str(exc), 'erro'), 400
    con = cursor = None
    try:
        con = conectar_banco()
        cursor = con.cursor()
        id_usuario = usuario['id_usuario']
        # The account row serializes profile creation and simultaneous patches.
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1 AND EMAIL_CONFIRMADO=1' +
                       (' WITH LOCK' if alteracoes is not None else ''), (id_usuario,))
        if not cursor.fetchone():
            return mensagem_json('Faça login com uma conta de barbearia ativa.', 'erro'), 401
        antes = selecionar_perfil_publico(cursor, id_usuario)
        if alteracoes is not None:
            if not antes:
                defaults = {'cor_primaria': '#101010', 'cor_secundaria': '#191919', 'cor_terciaria': '#FF8800',
                            'cor_texto_primario': '#FFFFFF', 'cor_texto_secundario': '#A9A9A9',
                            'historia': '', 'localizacao': '', 'contato_telefone': '', 'contato_email': '', 'instagram': ''}
                defaults.update(alteracoes)
                cols = ','.join(c[0] for c in CAMPOS_PERFIL_PUBLICO.values())
                placeholders = ','.join('?' for _ in CAMPOS_PERFIL_PUBLICO)
                cursor.execute(f'INSERT INTO PERSONALIZACAO(ID_PERSONALIZACAO,ID_USUARIO,{cols},NUM_FUNCIONARIOS) '
                               f'VALUES(NEXT VALUE FOR SEQ_PERSONALIZACAO,?,{placeholders},0)',
                               (id_usuario, *defaults.values()))
                # Staff may be created before the first public profile.
                atualizar_contagem_equipe(cursor, id_usuario)
            else:
                assignments = ','.join(CAMPOS_PERFIL_PUBLICO[key][0] + '=?' for key in alteracoes)
                cursor.execute(f'UPDATE PERSONALIZACAO SET {assignments} WHERE ID_USUARIO=?',
                               (*alteracoes.values(), id_usuario))
            perfil = selecionar_perfil_publico(cursor, id_usuario)
            con.commit()
            from auditoria import registrar_log
            registrar_log('UPDATE' if antes else 'INSERT', 'PERSONALIZACAO', id_registro=perfil['id_personalizacao'],
                          id_usuario=id_usuario, dados_antes=antes or {}, dados_depois=perfil)
        else:
            perfil = antes
        return jsonify(personalizado=bool(perfil), personalizacao=perfil)
    except Exception:
        if con:
            con.rollback()
        app.logger.exception('Falha ao acessar o perfil público da barbearia.')
        return mensagem_json('Não foi possível salvar ou consultar o perfil da barbearia.', 'erro'), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


def atualizar_contagem_equipe(cursor, id_barbearia):
    cursor.execute('UPDATE PERSONALIZACAO SET NUM_FUNCIONARIOS=(SELECT COUNT(*) FROM FUNCIONARIO '
                   'WHERE ID_BARBEARIA=? AND ATIVO=1) WHERE ID_USUARIO=?', (id_barbearia, id_barbearia))


def validar_ids_servicos_individuais(ids):
    if not isinstance(ids, list) or len(ids) > 100 or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in ids):
        raise ValueError('Informe até 100 IDs inteiros positivos de serviços em uma lista.')
    return sorted(set(ids))


def validar_servicos_individuais(cursor, salon, ids):
    if not ids:
        return
    marks = ','.join('?' for _ in ids)
    cursor.execute(f'SELECT ID_SERVICO FROM SERVICO WHERE ID_USUARIO=? AND ATIVO=1 AND ID_SERVICO IN ({marks})', (salon, *ids))
    if {row[0] for row in cursor.fetchall()} != set(ids):
        raise ValueError('Selecione somente serviços ativos desta barbearia.')


def salvar_servicos_individuais(cursor, id_funcionario, ids):
    cursor.execute('SELECT ID_SERVICO FROM SERVICO_POR_FUNCIONARIO WHERE ID_FUNCIONARIO=?', (id_funcionario,))
    anteriores = {row[0] for row in cursor.fetchall()}
    removidos = sorted(anteriores - set(ids))
    if removidos:
        marks = ','.join('?' for _ in removidos)
        cursor.execute(f'DELETE FROM SERVICO_POR_FUNCIONARIO WHERE ID_FUNCIONARIO=? AND ID_SERVICO IN ({marks})', (id_funcionario, *removidos))
    for id_servico in sorted(set(ids) - anteriores):
        cursor.execute('INSERT INTO SERVICO_POR_FUNCIONARIO(ID_SERVI_FUNCI,ID_FUNCIONARIO,ID_SERVICO) '
                       'VALUES(NEXT VALUE FOR SEQ_SERVICO_POR_FUNCIONARIO,?,?)', (id_funcionario, id_servico))
    # Existing FUNCIONARIO_PRECO rows and appointment snapshots remain intact.
    # A new link uses SERVICO.PRECO until explicitly configured otherwise.
    return sorted(anteriores)


@app.put('/barbearia/funcionarios/<int:id_funcionario>/servicos')
def alterar_servicos_profissional_individual(id_funcionario):
    usuario = obter_usuario_logado()
    if not usuario:
        return mensagem_json('Faça login.', 'erro'), 401
    if int(usuario.get('tipo', -1)) != 2:
        return mensagem_json('Somente a barbearia pode alterar sua equipe.', 'erro'), 403
    dados = request.get_json(silent=True)
    try:
        if not isinstance(dados, dict) or set(dados) != {'ids_servicos'}:
            raise ValueError('Informe somente a lista ids_servicos.')
        ids = validar_ids_servicos_individuais(dados['ids_servicos'])
    except ValueError as exc:
        return mensagem_json(str(exc), 'erro'), 400
    con = cursor = None
    try:
        con = conectar_banco()
        cursor = con.cursor()
        salon = usuario['id_usuario']
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1 AND EMAIL_CONFIRMADO=1 WITH LOCK', (salon,))
        if not cursor.fetchone():
            return mensagem_json('Faça login com uma conta de barbearia ativa.', 'erro'), 401
        cursor.execute('SELECT ID_FUNCIONARIO FROM FUNCIONARIO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=? WITH LOCK', (id_funcionario, salon))
        if not cursor.fetchone():
            return mensagem_json('Profissional não encontrado nesta barbearia.', 'erro'), 404
        validar_servicos_individuais(cursor, salon, ids)
        anteriores = salvar_servicos_individuais(cursor, id_funcionario, ids)
        con.commit()
        from auditoria import registrar_log
        registrar_log('UPDATE', 'FUNCIONARIO', id_registro=id_funcionario, id_usuario=salon,
                      campo='SERVICOS', valor_antes=','.join(map(str, anteriores)), valor_depois=','.join(map(str, ids)))
        return jsonify(id_funcionario=id_funcionario, ids_servicos=ids,
                       mensagem={'informacao': 'Serviços do profissional atualizados. Configure os preços e horários quando necessário.', 'tipo': 'sucesso'})
    except ValueError as exc:
        if con:
            con.rollback()
        return mensagem_json(str(exc), 'erro'), 400
    except Exception:
        if con:
            con.rollback()
        app.logger.exception('Falha ao alterar serviços de profissional.')
        return mensagem_json('Não foi possível alterar os serviços do profissional.', 'erro'), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.post('/barbearia/funcionarios')
def cadastrar_profissional_individual():
    usuario = obter_usuario_logado()
    if not usuario:
        return mensagem_json('Faça login.', 'erro'), 401
    if int(usuario.get('tipo', -1)) != 2:
        return mensagem_json('Somente a barbearia pode cadastrar sua equipe.', 'erro'), 403
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict) or set(dados) - {'nome', 'descricao', 'email', 'telefone', 'comissao_percentual', 'ids_servicos'}:
        return mensagem_json('Informe somente nome, descrição, e-mail, telefone, comissão percentual e ids_servicos.', 'erro'), 400
    for key, limit in (('nome', 100), ('descricao', 500), ('email', 150), ('telefone', 20)):
        value = dados.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > limit or (key != 'descricao' and not value.strip()):
            return mensagem_json(f'Informe {key} válido (até {limit} caracteres).', 'erro'), 400
    from agenda_equipe import atualizar_acesso_funcionario, enviar_convites, percentual
    try:
        if isinstance(dados.get('comissao_percentual', 0), bool):
            raise ValueError('Informe uma comissão percentual válida.')
        pct = percentual(dados.get('comissao_percentual', 0))
        ids = validar_ids_servicos_individuais(dados.get('ids_servicos', []))
    except ValueError as exc:
        return mensagem_json(str(exc), 'erro'), 400
    con = cursor = None
    try:
        con = conectar_banco()
        cursor = con.cursor()
        salon = usuario['id_usuario']
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1 AND EMAIL_CONFIRMADO=1 WITH LOCK', (salon,))
        if not cursor.fetchone():
            return mensagem_json('Faça login com uma conta de barbearia ativa.', 'erro'), 401
        validar_servicos_individuais(cursor, salon, ids)
        nome = dados['nome'].strip()
        cursor.execute('INSERT INTO FUNCIONARIO(ID_FUNCIONARIO,NOME,DESCRICAO,ID_BARBEARIA,ATIVO) '
                       'VALUES(NEXT VALUE FOR SEQ_FUNCIONARIO,?,?,?,1) RETURNING ID_FUNCIONARIO',
                       (nome, dados.get('descricao', '').strip(), salon))
        id_funcionario = cursor.fetchone()[0]
        entrada = {f'funcionarios[0][{key}]': dados.get(key, '') for key in ('email', 'telefone')}
        entrada['funcionarios[0][comissao_percentual]'] = pct
        convite = atualizar_acesso_funcionario(cursor, id_funcionario, salon, 0, entrada)
        if ids:
            salvar_servicos_individuais(cursor, id_funcionario, ids)
        atualizar_contagem_equipe(cursor, salon)
        con.commit()
        from auditoria import registrar_log
        registrar_log('INSERT', 'FUNCIONARIO', id_registro=id_funcionario, id_usuario=salon,
                      dados_depois={'ID_FUNCIONARIO': id_funcionario, 'ID_BARBEARIA': salon, 'NOME': nome,
                                    'ATIVO': 1, 'COMISSAO_PERCENTUAL': str(pct)})
        enviados = enviar_convites([convite]) if convite else []
        email_enviado = bool(enviados and enviados[0].get('email_enviado'))
        return jsonify(funcionario={'id_funcionario': id_funcionario, 'nome': nome, 'ativo': True, 'ids_servicos': ids},
                       convite_email_enviado=email_enviado, configuracao_pendente=True,
                       mensagem={'informacao': 'Profissional cadastrado. Configure seus serviços, preços e horários antes de receber agendamentos.', 'tipo': 'sucesso'}), 201
    except ValueError as exc:
        if con:
            con.rollback()
        return mensagem_json(str(exc), 'erro'), 400
    except Exception:
        if con:
            con.rollback()
        app.logger.exception('Falha ao cadastrar profissional.')
        return mensagem_json('Não foi possível cadastrar o profissional.', 'erro'), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.patch('/barbearia/funcionarios/<int:id_funcionario>/estado')
def alterar_estado_profissional(id_funcionario):
    usuario = obter_usuario_logado()
    if not usuario:
        return mensagem_json('Faça login.', 'erro'), 401
    if int(usuario.get('tipo', -1)) != 2:
        return mensagem_json('Somente a barbearia pode alterar sua equipe.', 'erro'), 403
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict) or set(dados) != {'ativo'} or not isinstance(dados['ativo'], bool):
        return mensagem_json('Informe ativo como verdadeiro ou falso.', 'erro'), 400
    con = cursor = None
    try:
        con = conectar_banco()
        cursor = con.cursor()
        salon = usuario['id_usuario']
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2 AND ATIVO=1 AND EMAIL_CONFIRMADO=1 WITH LOCK', (salon,))
        if not cursor.fetchone():
            return mensagem_json('Faça login com uma conta de barbearia ativa.', 'erro'), 401
        cursor.execute('SELECT ID_FUNCIONARIO,NOME,ATIVO FROM FUNCIONARIO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=? WITH LOCK', (id_funcionario, salon))
        fun = cursor.fetchone()
        if not fun:
            return mensagem_json('Profissional não encontrado nesta barbearia.', 'erro'), 404
        if not dados['ativo']:
            cursor.execute("SELECT FIRST 1 ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=? AND INICIO_EM>CURRENT_TIMESTAMP AND STATUS IN ('agendado','confirmado')", (id_funcionario, salon))
            if cursor.fetchone():
                return mensagem_json('Este profissional possui agendamentos futuros. Redistribua ou cancele os atendimentos antes de desativá-lo.', 'erro'), 409
        cursor.execute('UPDATE FUNCIONARIO SET ATIVO=? WHERE ID_FUNCIONARIO=? AND ID_BARBEARIA=?', (int(dados['ativo']), id_funcionario, salon))
        atualizar_contagem_equipe(cursor, salon)
        con.commit()
        from auditoria import registrar_log
        registrar_log('UPDATE', 'FUNCIONARIO', id_registro=id_funcionario, id_usuario=salon,
                      campo='ATIVO', valor_antes=int(fun[2] or 0), valor_depois=int(dados['ativo']))
        return jsonify(funcionario={'id_funcionario': fun[0], 'nome': fun[1], 'ativo': dados['ativo']},
                       mensagem={'informacao': 'Profissional ativado.' if dados['ativo'] else 'Profissional desativado.', 'tipo': 'sucesso'})
    except Exception:
        if con:
            con.rollback()
        app.logger.exception('Falha ao alterar estado de profissional.')
        return mensagem_json('Não foi possível alterar o profissional.', 'erro'), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()

EXTENSOES_PERMITIDAS = {
    'jpg',
    'jpeg',
    'png',
    'webp'
}


# ==========================================================
# USUÁRIO LOGADO
# ==========================================================

def obter_usuario_logado():

    from funcoes import decodificar_token
    return decodificar_token()


# ==========================================================
# ID DO USUÁRIO
# ==========================================================



def pegar_id_barbearia_alvo():
    """Retorna exclusivamente o ID de uma conta do tipo barbearia.

    Em alterações administrativas, o alvo é obrigatório. Nunca há fallback
    para o ID do ADM, portanto todas as gravações operacionais ficam ligadas
    somente à barbearia que está sendo administrada.
    """
    usuario = obter_usuario_logado()
    if not usuario:
        return None

    id_logado = usuario.get('id_usuario')
    id_solicitado = (
        request.args.get('id_usuario') or request.args.get('usuario')
        or request.form.get('id_usuario') or request.form.get('usuario')
    )
    dados_json = request.get_json(silent=True) or {}
    id_solicitado = id_solicitado or dados_json.get('id_usuario') or dados_json.get('usuario')

    if not id_solicitado:
        # ADM não pode gravar dados operacionais em sua própria conta.
        if int(usuario.get('tipo', -1)) == 0:
            return None
        id_solicitado = id_logado

    try:
        id_solicitado = int(id_solicitado)
    except (ValueError, TypeError):
        return None

    # ADM pode editar qualquer barbearia
    if int(usuario.get('tipo', -1)) == 0:
        return id_solicitado

    if (
        id_solicitado != id_logado
        and request.method != 'GET'
    ):
        return None

    # Impede que um ID de cliente ou de ADM seja usado como uma barbearia.
    con = None
    cursor = None
    try:
        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute(
            'SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO = ? AND TIPO = 2',
            (id_solicitado,)
        )
        return id_solicitado if cursor.fetchone() else None
    except Exception:
        return None
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


# ==========================================================
# OBTER SERVIÇOS DO FUNCIONÁRIO
# ==========================================================
#
# IMPORTANTE:
#
# Os serviços DEVEM estar previamente cadastrados
# na tabela SERVICO.
#
# Esta função NÃO cadastra serviços.
#
# Ela somente recebe os IDs dos serviços enviados
# pelo frontend/Postman.
#
# Aceita:
#
# funcionarios[0][servicos] = 1,2,3
#
# funcionarios[0][servicos][] = 1
# funcionarios[0][servicos][] = 2
#
# funcionarios[0][servicos][0] = 1
# funcionarios[0][servicos][1] = 2
#
# funcionarios[0][servicos] = [1,2,3]
#
# ==========================================================

def obter_servicos_funcionario(indice):

    prefixo = (
        f'funcionarios[{indice}][servicos]'
    )

    valores = []


    # ======================================================
    # FORMATO:
    #
    # funcionarios[0][servicos] = 1,2,3
    # ======================================================

    valores_diretos = request.form.getlist(
        prefixo
    )

    for valor in valores_diretos:

        if valor is not None and str(valor).strip():

            valores.append(valor)


    # ======================================================
    # FORMATO:
    #
    # funcionarios[0][servicos][] = 1
    # funcionarios[0][servicos][] = 2
    #
    # OU:
    #
    # funcionarios[0][servicos][0] = 1
    # funcionarios[0][servicos][1] = 2
    # ======================================================

    for chave in request.form.keys():

        if chave.startswith(prefixo + '['):

            valores_chave = request.form.getlist(
                chave
            )

            for valor in valores_chave:

                if (
                    valor is not None
                    and str(valor).strip()
                ):

                    valores.append(valor)


    ids_servicos = []


    # ======================================================
    # PROCESSAR VALORES
    # ======================================================

    for valor in valores:

        if valor is None:
            continue


        valor = str(valor).strip()


        if not valor:
            continue


        # ==================================================
        # JSON
        #
        # Exemplo:
        #
        # [1,2,3]
        # ==================================================

        if (
            valor.startswith('[')
            and valor.endswith(']')
        ):

            try:

                lista_json = json.loads(
                    valor
                )


                if isinstance(
                    lista_json,
                    list
                ):

                    for item in lista_json:

                        try:

                            id_servico = int(
                                item
                            )

                        except (
                            ValueError,
                            TypeError
                        ):

                            continue


                        if (
                            id_servico
                            not in ids_servicos
                        ):

                            ids_servicos.append(
                                id_servico
                            )


                    continue


            except (
                json.JSONDecodeError,
                TypeError
            ):

                pass


        # ==================================================
        # VÍRGULA OU PONTO E VÍRGULA
        # ==================================================

        partes = re.split(
            r'[,;]',
            valor
        )


        for parte in partes:

            parte = parte.strip()


            if not parte:
                continue


            try:

                id_servico = int(
                    parte
                )

            except (
                ValueError,
                TypeError
            ):

                continue


            if (
                id_servico
                not in ids_servicos
            ):

                ids_servicos.append(
                    id_servico
                )


    return ids_servicos


# ==========================================================
# VINCULAR SERVIÇOS AO FUNCIONÁRIO
# ==========================================================
#
# IMPORTANTE:
#
# Esta função NÃO cria serviços.
#
# Ela verifica se cada ID_SERVICO:
#
# 1. Existe na tabela SERVICO
# 2. Pertence ao usuário logado
#
# Depois cria a relação:
#
# SERVICO_POR_FUNCIONARIO
#
# ==========================================================

def vincular_servicos_funcionario(
    cursor,
    id_funcionario,
    id_usuario,
    indice
):

    ids_servicos = obter_servicos_funcionario(
        indice
    )


    print(
        '========================================='
    )

    print(
        f'FUNCIONÁRIO ID: {id_funcionario}'
    )

    print(
        'SERVIÇOS RECEBIDOS:',
        ids_servicos
    )


    for id_servico in ids_servicos:

        # ==================================================
        # VERIFICAR SE O SERVIÇO EXISTE
        # E PERTENCE AO USUÁRIO
        # ==================================================

        cursor.execute("""
            SELECT
                ID_SERVICO
            FROM SERVICO
            WHERE
                ID_SERVICO = ?
                AND ID_USUARIO = ?
        """, (
            id_servico,
            id_usuario
        ))


        servico = cursor.fetchone()


        if not servico:

            print(
                f'SERVIÇO {id_servico} '
                f'NÃO EXISTE OU NÃO PERTENCE '
                f'AO USUÁRIO {id_usuario}'
            )

            continue


        # ==================================================
        # EVITAR DUPLICIDADE
        # ==================================================

        cursor.execute("""
            SELECT
                ID_SERVI_FUNCI
            FROM SERVICO_POR_FUNCIONARIO
            WHERE
                ID_FUNCIONARIO = ?
                AND ID_SERVICO = ?
        """, (
            id_funcionario,
            id_servico
        ))


        vinculo_existente = (
            cursor.fetchone()
        )


        if vinculo_existente:

            print(
                f'SERVIÇO {id_servico} '
                f'JÁ ESTÁ VINCULADO '
                f'AO FUNCIONÁRIO {id_funcionario}'
            )

            continue


        # ==================================================
        # CRIAR VÍNCULO
        # ==================================================

        cursor.execute("""
            INSERT INTO SERVICO_POR_FUNCIONARIO (
                ID_SERVI_FUNCI,
                ID_FUNCIONARIO,
                ID_SERVICO
            )
            VALUES (NEXT VALUE FOR SEQ_SERVICO_POR_FUNCIONARIO, ?, ?)
        """, (
            id_funcionario,
            id_servico
        ))


        print(
            f'SERVIÇO {id_servico} '
            f'VINCULADO AO FUNCIONÁRIO '
            f'{id_funcionario}'
        )


    print(
        '========================================='
    )


    return ids_servicos


def vincular_dias_funcionario(cursor, id_funcionario, ids_dias):
    """Salva a relação N:N entre o funcionário e todos os dias selecionados."""
    for id_dia in set(ids_dias):
        cursor.execute("""
            INSERT INTO FUNCIONARIO_DIA (ID_FUNCIONARIO_DIA, ID_FUNCIONARIO, ID_DIA)
            VALUES (NEXT VALUE FOR SEQ_FUNCIONARIO_DIA, ?, ?)
        """, (id_funcionario, id_dia))


# ==========================================================
# PASTA DA BARBEARIA
# ==========================================================

def criar_pasta_barbearia():

    pasta = os.path.join(
        app.config['UPLOAD_FOLDER'],
        'barbearia'
    )

    if app.config.get('IMAGE_STORAGE_PROVIDER', 'google_drive') == 'local':
        os.makedirs(pasta, exist_ok=True)

    return pasta


# ==========================================================
# EXTENSÃO DA IMAGEM
# ==========================================================

def extensao_permitida(nome):

    if not nome:
        return False

    if '.' not in nome:
        return False

    extensao = nome.rsplit(
        '.',
        1
    )[-1].lower()

    return (
        extensao
        in EXTENSOES_PERMITIDAS
    )


# ==========================================================
# SERVIÇOS DA BARBEARIA
# ==========================================================

@app.route('/barbearia/servicos', methods=['GET'])
def listar_servicos_barbearia():
    """Lista somente os serviços pertencentes à barbearia autenticada."""
    con = None
    cursor = None

    try:
        id_usuario = pegar_id_barbearia_alvo()
        if not id_usuario:
            return mensagem_json('Usuário não autenticado.', 'erro'), 401

        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute("""
            SELECT ID_SERVICO, NOME_SERVICO, PRECO, DURACAO, DESCRICAO_BREVE, GENERO,ATIVO
            FROM SERVICO
            WHERE ID_USUARIO = ? AND (ATIVO=1 OR ?=1)
            ORDER BY NOME_SERVICO
        """, (id_usuario,int(int((obter_usuario_logado() or {}).get('tipo',-1)) in (0,2))))

        return jsonify({'mensagem': {'informacao': 'Serviços listados.', 'tipo': 'sucesso'}, 'servicos': [
            {
                'id_servico': servico[0],
                'nome': servico[1],
                'preco': float(servico[2]) if servico[2] is not None else 0,
                'duracao': servico[3],
                'descricao': servico[4],
                'genero': servico[5] or 'unissex','ativo':bool(servico[6])
            }
            for servico in cursor.fetchall()
        ]}), 200
    except Exception as erro:
        return jsonify({'mensagem': {'informacao': 'Erro ao listar serviços.', 'tipo': 'erro'}, 'detalhes': 'Consulte o registro do servidor.'}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


# ==========================================================
# CATÁLOGO DE BARBEARIAS DISPONÍVEIS
# ==========================================================
# Esta rota alimenta a tela BarbeariasDisponiveis no frontend. Ela retorna
# todas as contas do tipo 2. As que ainda não finalizaram a personalização
# recebem o status "Em configuração" para que o ADM consiga encontrá-las.

@app.route('/barbearias-disponiveis', methods=['GET'])
def listar_barbearias_disponiveis():
    con = None
    cursor = None

    try:
        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute("""
            SELECT U.ID_USUARIO, U.NOME, P.LOCALIZACAO, P.ID_PERSONALIZACAO
            FROM USUARIO U
            LEFT JOIN PERSONALIZACAO P ON P.ID_USUARIO = U.ID_USUARIO
            WHERE U.TIPO = 2 AND U.ATIVO = 1
            ORDER BY U.NOME
        """)

        resultado = []
        for id_usuario, nome, localizacao, id_personalizacao in cursor.fetchall():
            # A logo cadastrada é usada como imagem do card.
            imagem, _ = business_images(app.config['UPLOAD_FOLDER'], id_usuario, cursor=cursor)

            # Os horários são salvos por dia; o card exibe um resumo curto.
            cursor.execute("""
                SELECT DIAS, ENTRADA_MANHA, SAIDA_TARDE
                FROM DIAS_DE_SERVICO
                WHERE ID_USUARIO = ?
                ORDER BY ID_DIA
            """, (id_usuario,))
            dias = cursor.fetchall()
            nomes_dias = [str(dia[0]).capitalize() for dia in dias if dia[0]]
            primeiro_horario = dias[0] if dias else None
            horario = (
                f'{str(primeiro_horario[1])[:5]} - {str(primeiro_horario[2])[:5]}'
                if primeiro_horario and primeiro_horario[1] and primeiro_horario[2]
                else 'Horário a consultar'
            )

            resultado.append({
                'id': id_usuario,
                'nome': nome,
                'endereco': localizacao,
                'imagem': imagem,
                'dias': ', '.join(nomes_dias) or 'Em configuração',
                'horario': horario,
                # O frontend usa este campo para não oferecer agendamento
                # antes de a barbearia informar serviços e horários.
                'personalizada': bool(id_personalizacao)
            })

        return jsonify({'mensagem': {'informacao': 'Barbearias listadas.', 'tipo': 'sucesso'}, 'barbearias': resultado}), 200
    except Exception as erro:
        return jsonify({
            'mensagem': {'informacao': 'Erro ao listar barbearias.', 'tipo': 'erro'},
            'detalhes': 'Consulte o registro do servidor.'
        }), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.route('/barbearias/<int:id_barbearia>/funcionarios', methods=['GET'])
def listar_funcionarios_barbearia(id_barbearia):
    """Lista os profissionais de uma barbearia para o cliente escolher o barbeiro.

    Query opcional `servicos=1,2` filtra só quem atende TODOS os serviços.
    """
    con = None
    cursor = None
    try:
        filtro = set()
        for parte in str(request.args.get('servicos', '')).split(','):
            parte = parte.strip()
            if parte:
                try:
                    filtro.add(int(parte))
                except (TypeError, ValueError):
                    pass
        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO = ? AND TIPO = 2 AND ATIVO=1',
                       (id_barbearia,))
        if not cursor.fetchone():
            return mensagem_json('Barbearia não encontrada.', 'erro'), 404
        # Dias em que a barbearia realmente funciona.
        cursor.execute("""
            SELECT DISTINCT DIAS
            FROM DIAS_DE_SERVICO
            WHERE ID_USUARIO = ?
            ORDER BY ID_DIA
        """, (id_barbearia,))
        dias_abertos = [str(linha[0]).strip().lower() for linha in cursor.fetchall() if linha[0]]

        cursor.execute('SELECT ID_FUNCIONARIO,NOME,DESCRICAO FROM FUNCIONARIO WHERE ID_BARBEARIA=? AND ATIVO=1 ORDER BY NOME',(id_barbearia,))
        resultado = []
        for id_func, nome, descricao in cursor.fetchall():
            cursor.execute("""
                SELECT SPF.ID_SERVICO
                FROM SERVICO_POR_FUNCIONARIO SPF
                INNER JOIN SERVICO S ON S.ID_SERVICO = SPF.ID_SERVICO
                WHERE SPF.ID_FUNCIONARIO = ? AND S.ID_USUARIO = ? AND S.ATIVO=1
            """, (id_func, id_barbearia))
            servicos = [linha[0] for linha in cursor.fetchall()]
            if filtro and not filtro <= set(servicos):
                continue
            from visagismo import dias_semana_do_funcionario
            dias=sorted(dias_semana_do_funcionario(cursor,id_func))
            resultado.append({
                'id_funcionario': id_func,
                'nome': nome,
                'descricao': descricao,
                'servicos': servicos,
                'dias': dias,
            })
        return jsonify({
            'mensagem': {'informacao': 'Profissionais listados.', 'tipo': 'sucesso'},
            'funcionarios': resultado,
            'dias_abertos': dias_abertos
        }), 200
    except Exception as erro:
        return jsonify({'mensagem': {'informacao': 'Erro ao listar profissionais.', 'tipo': 'erro'}, 'detalhes': 'Consulte o registro do servidor.'}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.route('/barbearia/servicos', methods=['POST'])
def criar_servico_barbearia():
    """Cria um serviço que poderá ser associado a um ou mais funcionários."""
    con = None
    cursor = None

    try:
        id_usuario = pegar_id_barbearia_alvo()
        if not id_usuario:
            return mensagem_json('Usuário não autenticado.', 'erro'), 401

        dados = request.get_json(silent=True) or request.form
        nome = str(dados.get('nome', '')).strip()
        descricao = str(dados.get('descricao', '')).strip() or None
        genero = str(dados.get('genero', '')).strip().lower()
        preco = dados.get('preco')
        duracao = dados.get('duracao')

        if not nome:
            return mensagem_json('Nome do serviço é obrigatório.', 'erro'), 400
        if genero not in ('masculino', 'feminino', 'unissex'):
            return mensagem_json('Selecione Masculino, Feminino ou Unissex para o serviço.', 'erro'), 400

        try:
            preco_texto = str(preco).strip()
            preco = float(
                preco_texto.replace('.', '').replace(',', '.')
                if ',' in preco_texto else preco_texto
            )
            duracao = int(duracao)
        except (TypeError, ValueError):
            return mensagem_json('Preço e duração válidos são obrigatórios.', 'erro'), 400

        if not math.isfinite(preco) or preco < 0 or preco>1000000 or duracao <= 0 or duracao>1440:
            return mensagem_json('Preço e duração devem ser positivos.', 'erro'), 400

        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK',(id_usuario,))
        cursor.fetchone()

        cursor.execute(
            '''
            SELECT NOME_SERVICO
            FROM SERVICO
            WHERE LOWER(TRIM(NOME_SERVICO)) = ? AND ID_USUARIO=?
            ''',
            (nome.lower(),id_usuario)
        )

        existe = cursor.fetchone()

        if existe:
            return mensagem_json('Esse serviço já existe e não pode ser cadastrado novamente.', 'erro'), 400

        cursor.execute("""
            INSERT INTO SERVICO (ID_SERVICO, ID_USUARIO, NOME_SERVICO, PRECO, DURACAO, DESCRICAO_BREVE, GENERO)
            VALUES (NEXT VALUE FOR SEQ_SERVICO, ?, ?, ?, ?, ?, ?)
            RETURNING ID_SERVICO
        """, (id_usuario, nome, preco, duracao, descricao, genero))
        id_servico = cursor.fetchone()[0]
        con.commit()
        registrar_registro(
            cursor, 'INSERT', 'SERVICO', 'ID_SERVICO', id_servico
        )

        return jsonify({
            'mensagem': {'informacao': 'Serviço adicionado com sucesso.', 'tipo': 'sucesso'},
            'servico': {'id_servico': id_servico, 'nome': nome, 'preco': preco, 'duracao': duracao, 'descricao': descricao, 'genero': genero}
        }), 201
    except Exception as erro:
        if con:
            con.rollback()
        return jsonify({'mensagem': {'informacao': 'Erro ao adicionar serviço.', 'tipo': 'erro'}, 'detalhes': 'Consulte o registro do servidor.'}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.route('/barbearia/servicos/<int:id_servico>', methods=['PUT'])
def editar_servico_barbearia(id_servico):
    con = None
    cursor = None
    try:
        id_usuario = pegar_id_barbearia_alvo()
        if not id_usuario:
            return mensagem_json('Usuário não autenticado.', 'erro'), 401
        dados = request.get_json(silent=True) or request.form
        nome = str(dados.get('nome', '')).strip()
        descricao = str(dados.get('descricao', '')).strip() or None
        genero = str(dados.get('genero', '')).strip().lower()
        preco = dados.get('preco')
        duracao = dados.get('duracao')
        if not nome:
            return mensagem_json('Nome do serviço é obrigatório.', 'erro'), 400
        if genero not in ('masculino', 'feminino', 'unissex'):
            return mensagem_json('Selecione Masculino, Feminino ou Unissex para o serviço.', 'erro'), 400
        try:
            preco_texto = str(preco).strip()
            preco = float(preco_texto.replace('.', '').replace(',', '.') if ',' in preco_texto else preco_texto)
            duracao = int(duracao)
        except (TypeError, ValueError):
            return mensagem_json('Preço e duração válidos são obrigatórios.', 'erro'), 400
        if not math.isfinite(preco) or preco < 0 or preco>1000000 or duracao <= 0 or duracao>1440:
            return mensagem_json('Preço e duração devem ser positivos.', 'erro'), 400
        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK',(id_usuario,))
        cursor.fetchone()
        cursor.execute('SELECT ID_SERVICO FROM SERVICO WHERE ID_SERVICO = ? AND ID_USUARIO = ?', (id_servico, id_usuario))
        if not cursor.fetchone():
            return mensagem_json('Serviço não encontrado.', 'erro'), 404
        cursor.execute('SELECT ID_SERVICO FROM SERVICO WHERE LOWER(TRIM(NOME_SERVICO)) = ? AND ID_SERVICO <> ? AND ID_USUARIO = ?', (nome.lower(), id_servico, id_usuario))
        if cursor.fetchone():
            return mensagem_json('Já existe outro serviço com esse nome.', 'erro'), 400
        dados_antes_log = capturar_registro(
            cursor, 'SERVICO', 'ID_SERVICO', id_servico
        )
        cursor.execute('UPDATE SERVICO SET NOME_SERVICO = ?, PRECO = ?, DURACAO = ?, DESCRICAO_BREVE = ?, GENERO = ? WHERE ID_SERVICO = ? AND ID_USUARIO = ?', (nome, preco, duracao, descricao, genero, id_servico, id_usuario))
        con.commit()
        registrar_registro(
            cursor, 'UPDATE', 'SERVICO', 'ID_SERVICO', id_servico,
            dados_antes=dados_antes_log
        )
        return jsonify({'mensagem': {'informacao': 'Serviço atualizado com sucesso.', 'tipo': 'sucesso'}, 'servico': {'id_servico': id_servico, 'nome': nome, 'preco': preco, 'duracao': duracao, 'descricao': descricao, 'genero': genero}}), 200
    except Exception as erro:
        if con:
            con.rollback()
        return jsonify({'mensagem': {'informacao': 'Erro ao editar serviço.', 'tipo': 'erro'}, 'detalhes': 'Consulte o registro do servidor.'}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.route('/barbearia/servicos/<int:id_servico>', methods=['DELETE'])
def remover_servico_barbearia(id_servico):
    con = None
    cursor = None

    try:
        id_usuario = pegar_id_barbearia_alvo()
        if not id_usuario:
            return mensagem_json('Usuário não autenticado.', 'erro'), 401

        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK',(id_usuario,))
        cursor.fetchone()
        cursor.execute('SELECT ID_SERVICO FROM SERVICO WHERE ID_SERVICO = ? AND ID_USUARIO = ?', (id_servico, id_usuario))
        if not cursor.fetchone():
            return mensagem_json('Serviço não encontrado.', 'erro'), 404

        dados_antes_log = capturar_registro(
            cursor, 'SERVICO', 'ID_SERVICO', id_servico
        )
        cursor.execute('UPDATE SERVICO SET ATIVO=0 WHERE ID_SERVICO=? AND ID_USUARIO=?',(id_servico,id_usuario))
        con.commit()
        registrar_registro(cursor,'UPDATE','SERVICO','ID_SERVICO',id_servico,dados_antes=dados_antes_log)
        return mensagem_json('Serviço desativado. Histórico preservado.', 'sucesso'), 200
    except Exception as erro:
        if con:
            con.rollback()
        return jsonify({'mensagem': {'informacao': 'Erro ao remover serviço.', 'tipo': 'erro'}, 'detalhes': 'Consulte o registro do servidor.'}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


# ==========================================================
# EXCLUIR ARQUIVO
# ==========================================================

def excluir_arquivo(caminho):

    if os.path.exists(caminho):

        try:

            os.remove(caminho)

        except Exception as erro:

            print(
                'ERRO AO EXCLUIR ARQUIVO:',
                erro
            )


# ==========================================================
# SALVAR IMAGEM
# ==========================================================

def salvar_imagem(arquivo, nome_base, batch):
    """Store the validated salon logo/gallery in the current DB transaction."""
    if not arquivo or not arquivo.filename:
        return None
    match = re.fullmatch(r'(\d+)(?:_([1-5]))?', str(nome_base))
    if not match:
        raise ValueError('Identificação da imagem inválida.')
    owner = int(match.group(1))
    slot = f'gallery{match.group(2)}' if match.group(2) else 'logo'
    return batch.save(arquivo, 'barbearia', owner_id=owner, slot=slot).url


# ==========================================================
# ==========================================================
# CRIAR PERSONALIZAÇÃO
# ==========================================================
# ==========================================================

@app.route(
    '/barbearia/personalizacao',
    methods=['POST']
)
def personalizacao_barbearia():
    from agenda_equipe import atualizar_acesso_funcionario, enviar_convites
    convites = []

    con = None
    cursor = None
    image_batch = None

    try:

        # ==================================================
        # AUTENTICAÇÃO
        # ==================================================

        id_usuario = pegar_id_barbearia_alvo()

        if not id_usuario:

            return mensagem_json('Usuário não autenticado.', 'erro'), 401


        # ==================================================
        # CONEXÃO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()
        image_batch = ImageBatch(cursor)
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (id_usuario,))
        cursor.fetchone()


        # ==================================================
        # VERIFICAR PERSONALIZAÇÃO EXISTENTE
        # ==================================================

        cursor.execute("""
            SELECT ID_PERSONALIZACAO
            FROM PERSONALIZACAO
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))


        existente = (
            cursor.fetchone()
        )


        if existente:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'A barbearia já possui uma personalização.',

                    'tipo':
                        'aviso'

                },

                'id_personalizacao':
                    existente[0]

            }), 409


        # ==================================================
        # DADOS
        # ==================================================

        cor_primaria = request.form.get(
            'cor_primaria'
        )

        cor_secundaria = request.form.get(
            'cor_secundaria'
        )

        cor_terciaria = request.form.get(
            'cor_terciaria'
        )

        # Cores específicas para textos sobre fundos claros e escuros.
        cor_texto_primario = request.form.get('cor_texto_primario')
        cor_texto_secundario = request.form.get('cor_texto_secundario')

        # Contatos exibidos publicamente na página do estabelecimento.
        contato_telefone = request.form.get('contato_telefone')
        contato_email = request.form.get('contato_email')
        instagram = request.form.get('instagram')

        # Chave PIX / Arkhé (integração bancária para pagamentos)
        chave_pix = request.form.get('chave_pix')
        arkhe_client_id = request.form.get('arkhe_client_id')
        arkhe_client_secret = request.form.get('arkhe_client_secret')

        historia = request.form.get(
            'historia'
        )

        localizacao = request.form.get(
            'localizacao'
        )

        num_funcionarios = request.form.get(
            'num_funcionarios',
            '0'
        )


        try:

            num_funcionarios = int(
                num_funcionarios
            )

        except (
            ValueError,
            TypeError
        ):

            num_funcionarios = 0


        if num_funcionarios < 0:

            num_funcionarios = 0


        # A barbearia só fica disponível depois de informar uma equipe e os
        # dados necessários para receber pagamentos. Esta validação também
        # protege a API contra envios que não passaram pela tela.
        tem_funcionario = any(
            str(request.form.get(f'funcionarios[{i}][nome]') or '').strip()
            for i in range(num_funcionarios)
        )
        if not tem_funcionario:
            return mensagem_json('Cadastre pelo menos um barbeiro na equipe.', 'erro'), 400

        if not all(str(valor or '').strip() for valor in (chave_pix, arkhe_client_id, arkhe_client_secret)):
            return mensagem_json('Informe a chave PIX, o Client ID e o Client Secret da Arkhé para receber pagamentos.', 'erro'), 400


        # ==================================================
        # PERSONALIZAÇÃO
        # ==================================================

        cursor.execute("""
            INSERT INTO PERSONALIZACAO (
                ID_PERSONALIZACAO,
                ID_USUARIO,
                COR_PRIMARIA,
                COR_SECUNDARIA,
                COR_TERCIARIA,
                COR_TEXTO_PRIMARIO,
                COR_TEXTO_SECUNDARIO,
                TEXTO,
                LOCALIZACAO,
                CONTATO_TELEFONE,
                CONTATO_EMAIL,
                INSTAGRAM,
                NUM_FUNCIONARIOS,
                CHAVE_PIX,
                ARKHE_CLIENT_ID,
                ARKHE_CLIENT_SECRET
            )
            VALUES (NEXT VALUE FOR SEQ_PERSONALIZACAO, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING ID_PERSONALIZACAO
        """, (
            id_usuario,
            cor_primaria,
            cor_secundaria,
            cor_terciaria,
            cor_texto_primario,
            cor_texto_secundario,
            historia,
            localizacao,
            contato_telefone,
            contato_email,
            instagram,
            num_funcionarios,
            chave_pix,
            arkhe_client_id,
            arkhe_client_secret
        ))


        id_personalizacao = (
            cursor.fetchone()[0]
        )


        # ==================================================
        # DIAS DE SERVIÇO
        # ==================================================

        dias = [

            'segunda',
            'terca',
            'quarta',
            'quinta',
            'sexta',
            'sabado',
            'domingo'

        ]


        ids_dias = {}


        for dia in dias:

            entrada_manha = request.form.get(
                f'{dia}_entrada_manha'
            )

            saida_manha = request.form.get(
                f'{dia}_saida_manha'
            )

            entrada_tarde = request.form.get(
                f'{dia}_entrada_tarde'
            )

            saida_tarde = request.form.get(
                f'{dia}_saida_tarde'
            )

            # Tratar strings vazias como None
            entrada_manha = entrada_manha if entrada_manha else None
            saida_manha = saida_manha if saida_manha else None
            entrada_tarde = entrada_tarde if entrada_tarde else None
            saida_tarde = saida_tarde if saida_tarde else None


            # ==========================================================
            # VALIDAÇÃO DOS HORÁRIOS
            # ==========================================================

            # Se o dia não possui nenhum horário, ignora o dia
            if not any([
                entrada_manha,
                saida_manha,
                entrada_tarde,
                saida_tarde
            ]):
                continue


            # Entrada da manhã não pode ser depois da saída da manhã
            if entrada_manha and saida_manha:
                if entrada_manha > saida_manha:
                    return mensagem_json('A entrada de manhã não pode ser maior que a saída de manhã', 'erro'), 400


            # Saída da manhã não pode ser depois da entrada da tarde
            if saida_manha and entrada_tarde:
                if saida_manha > entrada_tarde:
                    return mensagem_json('A saída de manhã não pode ser maior que a entrada de tarde', 'erro'), 400


            # Entrada da tarde não pode ser depois da saída da tarde
            if entrada_tarde and saida_tarde:
                if entrada_tarde > saida_tarde:
                    return mensagem_json('A entrada de tarde não pode ser maior que a saída de tarde', 'erro'), 400

            cursor.execute("""
                INSERT INTO DIAS_DE_SERVICO (
                    ID_DIA,
                    ID_USUARIO,
                    DIAS,
                    ENTRADA_MANHA,
                    SAIDA_MANHA,
                    ENTRADA_TARDE,
                    SAIDA_TARDE
                )
                VALUES (NEXT VALUE FOR SEQ_DIA, ?, ?, ?, ?, ?, ?)
                RETURNING ID_DIA
            """, (
                id_usuario,
                dia,
                entrada_manha,
                saida_manha,
                entrada_tarde,
                saida_tarde
            ))


            id_dia = (
                cursor.fetchone()[0]
            )


            ids_dias[dia] = id_dia


        # ==================================================
        # FUNCIONÁRIOS
        # ==================================================

        funcionarios_criados = []


        for i in range(
            num_funcionarios
        ):

            nome = request.form.get(
                f'funcionarios[{i}][nome]'
            )

            descricao = request.form.get(
                f'funcionarios[{i}][descricao]'
            )

            # O frontend envia os dias como "segunda,terca". Mantemos a
            # leitura de "dia" para compatibilidade com cadastros antigos.
            dias_funcionario = request.form.get(f'funcionarios[{i}][dias]') or request.form.get(f'funcionarios[{i}][dia]') or ''


            if not nome:

                continue


            ids_dias_funcionario = [ids_dias[dia.strip()] for dia in dias_funcionario.split(',') if dia.strip() in ids_dias]


            # ==================================================
            # FUNCIONÁRIO
            # ==================================================

            cursor.execute("""
                INSERT INTO FUNCIONARIO (
                    ID_FUNCIONARIO,
                    NOME,
                    DESCRICAO
                )
                VALUES (NEXT VALUE FOR SEQ_FUNCIONARIO, ?, ?)
                RETURNING ID_FUNCIONARIO
            """, (
                nome,
                descricao
            ))


            id_funcionario = (
                cursor.fetchone()[0]
            )

            convite = atualizar_acesso_funcionario(cursor, id_funcionario, id_usuario, i, request.form)
            if convite: convites.append(convite)

            vincular_dias_funcionario(cursor, id_funcionario, ids_dias_funcionario)


            # ==================================================
            # SERVIÇOS DO FUNCIONÁRIO
            # ==================================================
            #
            # IMPORTANTE:
            #
            # Aqui NÃO cadastramos serviços.
            #
            # Os serviços já precisam existir em SERVICO.
            #
            # Apenas criamos a relação:
            #
            # FUNCIONARIO
            #       ↓
            # SERVICO_POR_FUNCIONARIO
            #       ↓
            # SERVICO
            #
            # ==================================================

            ids_servicos = (
                vincular_servicos_funcionario(
                    cursor,
                    id_funcionario,
                    id_usuario,
                    i
                )
            )


            funcionarios_criados.append({

                'id_funcionario':
                    id_funcionario,

                'dias':
                    ids_dias_funcionario,

                'nome':
                    nome,

                'descricao':
                    descricao,

                'servicos':
                    ids_servicos

            })


        # ==================================================
        # LOGO
        # ==================================================

        logo_url = None


        if 'logo' in request.files:

            arquivo_logo = (
                request.files['logo']
            )


            if (
                arquivo_logo
                and arquivo_logo.filename
            ):

                logo_url = salvar_imagem(
                    arquivo_logo,
                    str(id_usuario), image_batch
                )


        # ==================================================
        # FOTOS
        # ==================================================

        fotos = []


        for numero in range(1, 6):

            campo = f'foto{numero}'


            if campo not in request.files:

                continue


            foto = request.files[campo]


            if (
                not foto
                or not foto.filename
            ):

                continue


            nome_base = f'{id_usuario}_{numero}'


            url = salvar_imagem(
                foto,
                nome_base, image_batch
            )


            if url:

                fotos.append({

                    'numero':
                        numero,

                    'url':
                        url

                })


        # ==================================================
        # COMMIT
        # ==================================================

        con.commit()
        image_batch.commit()
        registrar_registro(
            cursor,
            'INSERT',
            'PERSONALIZACAO',
            'ID_PERSONALIZACAO',
            id_personalizacao
        )
        for id_dia_log in ids_dias.values():
            registrar_registro(
                cursor, 'INSERT', 'DIAS_DE_SERVICO', 'ID_DIA', id_dia_log
            )
        for funcionario_log in funcionarios_criados:
            id_funcionario_log = funcionario_log['id_funcionario']
            registrar_registro(
                cursor, 'INSERT', 'FUNCIONARIO', 'ID_FUNCIONARIO',
                id_funcionario_log
            )

            cursor.execute(
                'SELECT ID_SERVI_FUNCI FROM SERVICO_POR_FUNCIONARIO WHERE ID_FUNCIONARIO = ?',
                (id_funcionario_log,)
            )
            for (id_vinculo_servico_log,) in cursor.fetchall():
                registrar_registro(
                    cursor, 'INSERT', 'SERVICO_POR_FUNCIONARIO', 'ID_SERVI_FUNCI',
                    id_vinculo_servico_log
                )

            cursor.execute(
                'SELECT ID_FUNCIONARIO_DIA FROM FUNCIONARIO_DIA WHERE ID_FUNCIONARIO = ?',
                (id_funcionario_log,)
            )
            for (id_vinculo_dia_log,) in cursor.fetchall():
                registrar_registro(
                    cursor, 'INSERT', 'FUNCIONARIO_DIA', 'ID_FUNCIONARIO_DIA',
                    id_vinculo_dia_log
                )


        # ==================================================
        # RESPOSTA
        # ==================================================

        return jsonify({

            'mensagem': {

                'informacao':
                    'Personalização criada com sucesso.',

                'tipo':
                    'sucesso'

            },

            'convites': enviar_convites(convites),
            'primeira_personalizacao':
                True,

            'id_personalizacao':
                id_personalizacao,

            'personalizacao': {

                'cor_primaria':
                    cor_primaria,

                'cor_secundaria':
                    cor_secundaria,

                'cor_terciaria':
                    cor_terciaria,

                'historia':
                    historia,

                'localizacao':
                    localizacao,

                'num_funcionarios':
                    num_funcionarios,

                'chave_pix':
                    chave_pix,

                'arkhe_client_id':
                    arkhe_client_id,

                'arkhe_client_secret':
                    arkhe_client_secret

            },

            'funcionarios':
                funcionarios_criados,

            'dias_servico':
                list(
                    ids_dias.values()
                ),

            'logo':
                logo_url,

            'fotos':
                fotos

        }), 201


    except ImageStorageError as erro:
        if con:
            con.rollback()
        return mensagem_json(str(erro), 'erro'), erro.status

    except ValueError as erro:

        if con:

            con.rollback()


        return mensagem_json(str(erro), 'erro'), 400


    except Exception as erro:

        if con:

            try:

                con.rollback()

            except Exception:

                pass


        print(
            'ERRO AO CRIAR PERSONALIZAÇÃO:',
            erro
        )


        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao criar personalização.',

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
# ==========================================================
# EDITAR PERSONALIZAÇÃO
# ==========================================================
# ==========================================================

@app.route(
    '/barbearia/personalizacao',
    methods=['PUT']
)
def editar_personalizacao():
    from agenda_equipe import atualizar_acesso_funcionario, enviar_convites
    convites = []

    con = None
    cursor = None
    image_batch = None

    try:

        # ==================================================
        # AUTENTICAÇÃO
        # ==================================================

        id_usuario = pegar_id_barbearia_alvo()


        if not id_usuario:

            return mensagem_json('Usuário não autenticado.', 'erro'), 401


        # ==================================================
        # CONEXÃO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()
        image_batch = ImageBatch(cursor)
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO=? WITH LOCK', (id_usuario,))
        cursor.fetchone()


        # ==================================================
        # VERIFICAR PERSONALIZAÇÃO
        # ==================================================

        cursor.execute("""
            SELECT ID_PERSONALIZACAO
            FROM PERSONALIZACAO
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))


        personalizacao = (
            cursor.fetchone()
        )


        if not personalizacao:

            return mensagem_json('A barbearia ainda não possui personalização. Utilize a rota POST para criar.', 'aviso'), 404


        id_personalizacao = personalizacao[0]
        dados_antes_log = capturar_registro(
            cursor, 'PERSONALIZACAO', 'ID_PERSONALIZACAO', id_personalizacao
        )

        # ==================================================
        # DADOS
        # ==================================================

        dados = request.form.to_dict()


        cor_primaria = dados.get(
            'cor_primaria'
        )

        cor_secundaria = dados.get(
            'cor_secundaria'
        )

        cor_terciaria = dados.get(
            'cor_terciaria'
        )

        cor_texto_primario = dados.get('cor_texto_primario')
        cor_texto_secundario = dados.get('cor_texto_secundario')

        historia = dados.get(
            'historia'
        )

        localizacao = dados.get(
            'localizacao'
        )

        contato_telefone = dados.get('contato_telefone')
        contato_email = dados.get('contato_email')
        instagram = dados.get('instagram')

        # Chave PIX / Arkhé
        chave_pix = dados.get('chave_pix')
        arkhe_client_id = dados.get('arkhe_client_id')
        arkhe_client_secret = dados.get('arkhe_client_secret')

        try:
            quantidade_funcionarios = int(dados.get('num_funcionarios') or 0)
        except (ValueError, TypeError):
            quantidade_funcionarios = 0
        if quantidade_funcionarios < 0:
            quantidade_funcionarios = 0

        tem_funcionario = any(
            str(dados.get(f'funcionarios[{i}][nome]') or '').strip()
            for i in range(quantidade_funcionarios)
        )
        if not tem_funcionario:
            return mensagem_json('Cadastre pelo menos um barbeiro na equipe.', 'erro'), 400

        if not all(str(valor or '').strip() for valor in (chave_pix, arkhe_client_id, arkhe_client_secret)):
            return mensagem_json('Informe a chave PIX, o Client ID e o Client Secret da Arkhé para receber pagamentos.', 'erro'), 400


        # ==================================================
        # ATUALIZAR PERSONALIZAÇÃO
        # ==================================================

        cursor.execute("""
            UPDATE PERSONALIZACAO
            SET
                COR_PRIMARIA = ?,
                COR_SECUNDARIA = ?,
                COR_TERCIARIA = ?,
                COR_TEXTO_PRIMARIO = ?,
                COR_TEXTO_SECUNDARIO = ?,
                TEXTO = ?,
                LOCALIZACAO = ?,
                CONTATO_TELEFONE = ?,
                CONTATO_EMAIL = ?,
                INSTAGRAM = ?,
                CHAVE_PIX = ?,
                ARKHE_CLIENT_ID = ?,
                ARKHE_CLIENT_SECRET = ?
            WHERE ID_USUARIO = ?
        """, (
            cor_primaria,
            cor_secundaria,
            cor_terciaria,
            cor_texto_primario,
            cor_texto_secundario,
            historia,
            localizacao,
            contato_telefone,
            contato_email,
            instagram,
            chave_pix,
            arkhe_client_id,
            arkhe_client_secret,
            id_usuario
        ))


        # ==================================================
        # BUSCAR FUNCIONÁRIOS ANTIGOS
        # ==================================================

        cursor.execute("""
            SELECT F.ID_FUNCIONARIO FROM FUNCIONARIO F WHERE F.ID_BARBEARIA = ?
        """, (
            id_usuario,
        ))


        funcionarios_antigos = (
            cursor.fetchall()
        )
        funcionarios_antigos_log = [
            capturar_registro(
                cursor, 'FUNCIONARIO', 'ID_FUNCIONARIO', funcionario[0]
            )
            for funcionario in funcionarios_antigos
        ]

        vinculos_servico_antigos_log = []
        vinculos_dia_antigos_log = []
        for funcionario in funcionarios_antigos:
            id_funcionario_antigo = funcionario[0]

            cursor.execute(
                'SELECT ID_SERVI_FUNCI FROM SERVICO_POR_FUNCIONARIO WHERE ID_FUNCIONARIO = ?',
                (id_funcionario_antigo,)
            )
            for (id_vinculo,) in cursor.fetchall():
                vinculos_servico_antigos_log.append((
                    id_vinculo,
                    capturar_registro(
                        cursor, 'SERVICO_POR_FUNCIONARIO', 'ID_SERVI_FUNCI', id_vinculo
                    )
                ))

            cursor.execute(
                'SELECT ID_FUNCIONARIO_DIA FROM FUNCIONARIO_DIA WHERE ID_FUNCIONARIO = ?',
                (id_funcionario_antigo,)
            )
            for (id_vinculo,) in cursor.fetchall():
                vinculos_dia_antigos_log.append((
                    id_vinculo,
                    capturar_registro(
                        cursor, 'FUNCIONARIO_DIA', 'ID_FUNCIONARIO_DIA', id_vinculo
                    )
                ))


        # ==================================================
        # EXCLUIR VÍNCULOS DE SERVIÇOS
        # ==================================================

        for funcionario in funcionarios_antigos:

            cursor.execute("""
                DELETE FROM SERVICO_POR_FUNCIONARIO
                WHERE ID_FUNCIONARIO = ?
            """, (
                funcionario[0],
            ))

            # Remove os vínculos de dias antes de excluir o funcionário.
            cursor.execute("""
                DELETE FROM FUNCIONARIO_DIA
                WHERE ID_FUNCIONARIO = ?
            """, (funcionario[0],))


        # ==================================================
        # EXCLUIR FUNCIONÁRIOS
        # ==================================================

        # Staff records remain to preserve bookings, accounts and commission history.
        ids_funcionarios_existentes = {row[0] for row in funcionarios_antigos}
        ids_funcionarios_mantidos = set()

        # ==================================================
        # EXCLUIR DIAS ANTIGOS
        # ==================================================

        cursor.execute(
            'SELECT ID_DIA FROM DIAS_DE_SERVICO WHERE ID_USUARIO = ?',
            (id_usuario,)
        )
        ids_dias_antigos_log = [linha[0] for linha in cursor.fetchall()]
        dias_antigos_log = [
            capturar_registro(cursor, 'DIAS_DE_SERVICO', 'ID_DIA', id_dia)
            for id_dia in ids_dias_antigos_log
        ]

        cursor.execute("""
            DELETE FROM DIAS_DE_SERVICO
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))


        # ==================================================
        # NOVOS DIAS
        # ==================================================

        dias = [

            'segunda',
            'terca',
            'quarta',
            'quinta',
            'sexta',
            'sabado',
            'domingo'

        ]


        ids_dias = {}


        for dia in dias:

            entrada_manha = dados.get(
                f'{dia}_entrada_manha'
            )

            saida_manha = dados.get(
                f'{dia}_saida_manha'
            )

            entrada_tarde = dados.get(
                f'{dia}_entrada_tarde'
            )

            saida_tarde = dados.get(
                f'{dia}_saida_tarde'
            )

            # Tratar strings vazias como None
            entrada_manha = entrada_manha if entrada_manha else None
            saida_manha = saida_manha if saida_manha else None
            entrada_tarde = entrada_tarde if entrada_tarde else None
            saida_tarde = saida_tarde if saida_tarde else None


            # ==========================================================
            # VALIDAÇÃO DOS HORÁRIOS
            # ==========================================================

            # Se o dia não possui nenhum horário, ignora o dia
            if not any([
                entrada_manha,
                saida_manha,
                entrada_tarde,
                saida_tarde
            ]):
                continue


            # Entrada da manhã não pode ser depois da saída da manhã
            if entrada_manha and saida_manha:
                if entrada_manha > saida_manha:
                    return mensagem_json('A entrada de manhã não pode ser maior que a saída de manhã', 'erro'), 400


            # Saída da manhã não pode ser depois da entrada da tarde
            if saida_manha and entrada_tarde:
                if saida_manha > entrada_tarde:
                    return mensagem_json('A saída de manhã não pode ser maior que a entrada de tarde', 'erro'), 400


            # Entrada da tarde não pode ser depois da saída da tarde
            if entrada_tarde and saida_tarde:
                if entrada_tarde > saida_tarde:
                    return mensagem_json('A entrada de tarde não pode ser maior que a saída de tarde', 'erro'), 400


            cursor.execute("""
                INSERT INTO DIAS_DE_SERVICO (
                    ID_DIA,
                    ID_USUARIO,
                    DIAS,
                    ENTRADA_MANHA,
                    SAIDA_MANHA,
                    ENTRADA_TARDE,
                    SAIDA_TARDE
                )
                VALUES (NEXT VALUE FOR SEQ_DIA, ?, ?, ?, ?, ?, ?)
                RETURNING ID_DIA
            """, (
                id_usuario,
                dia,
                entrada_manha,
                saida_manha,
                entrada_tarde,
                saida_tarde
            ))


            id_dia = (
                cursor.fetchone()[0]
            )


            ids_dias[dia] = id_dia


        # ==================================================
        # FUNCIONÁRIOS NOVOS
        # ==================================================

        funcionarios_novos_ids_log = []

        for i in range(
            quantidade_funcionarios
        ):

            nome = dados.get(
                f'funcionarios[{i}][nome]'
            )

            descricao = dados.get(
                f'funcionarios[{i}][descricao]'
            )

            dias_funcionario = dados.get(f'funcionarios[{i}][dias]') or dados.get(f'funcionarios[{i}][dia]') or ''


            if not nome:

                continue


            ids_dias_funcionario = [ids_dias[dia.strip()] for dia in dias_funcionario.split(',') if dia.strip() in ids_dias]


            # ==================================================
            # FUNCIONÁRIO
            # ==================================================

            pedido_id = dados.get(f'funcionarios[{i}][id_funcionario]')
            if pedido_id:
                id_funcionario = int(pedido_id)
                if id_funcionario not in ids_funcionarios_existentes or id_funcionario in ids_funcionarios_mantidos:
                    raise ValueError('Identificação de funcionário inválida para esta barbearia.')
                cursor.execute('UPDATE FUNCIONARIO SET NOME=?,DESCRICAO=?,ATIVO=1 WHERE ID_FUNCIONARIO=?', (nome,descricao,id_funcionario))
            else:
                cursor.execute('INSERT INTO FUNCIONARIO(ID_FUNCIONARIO,NOME,DESCRICAO,ID_BARBEARIA,ATIVO) VALUES(NEXT VALUE FOR SEQ_FUNCIONARIO,?,?,?,1) RETURNING ID_FUNCIONARIO', (nome,descricao,id_usuario))
                id_funcionario = cursor.fetchone()[0]
                funcionarios_novos_ids_log.append(id_funcionario)
            ids_funcionarios_mantidos.add(id_funcionario)
            convite = atualizar_acesso_funcionario(cursor,id_funcionario,id_usuario,i,dados)
            if convite: convites.append(convite)

            vincular_dias_funcionario(cursor, id_funcionario, ids_dias_funcionario)


            # ==================================================
            # SERVIÇOS DO FUNCIONÁRIO
            # ==================================================
            #
            # NÃO CADASTRA SERVIÇOS.
            #
            # SOMENTE VINCULA SERVIÇOS JÁ EXISTENTES.
            #
            # ==================================================

            vincular_servicos_funcionario(
                cursor,
                id_funcionario,
                id_usuario,
                i
            )


        for removido in ids_funcionarios_existentes - ids_funcionarios_mantidos:
            cursor.execute("SELECT FIRST 1 ID_AGENDAMENTO FROM AGENDAMENTO WHERE ID_FUNCIONARIO=? AND INICIO_EM>CURRENT_TIMESTAMP AND STATUS IN ('agendado','confirmado')", (removido,))
            if cursor.fetchone():
                raise ValueError('Este barbeiro possui agendamentos futuros. Redistribua ou cancele os atendimentos antes de removê-lo.')
            cursor.execute('UPDATE FUNCIONARIO SET ATIVO=0 WHERE ID_FUNCIONARIO=?', (removido,))

        # ==================================================
        # ATUALIZAR QUANTIDADE
        # ==================================================

        cursor.execute("""
            UPDATE PERSONALIZACAO
            SET NUM_FUNCIONARIOS = ?
            WHERE ID_USUARIO = ?
        """, (
            quantidade_funcionarios,
            id_usuario
        ))


        # ==================================================
        # LOGO
        # ==================================================

        logo_url = None


        if 'logo' in request.files:

            arquivo_logo = (
                request.files['logo']
            )


            if (
                arquivo_logo
                and arquivo_logo.filename
            ):

                logo_url = salvar_imagem(
                    arquivo_logo,
                    str(id_usuario), image_batch
                )


        # ==================================================
        # FOTOS
        # ==================================================

        fotos = []


        for numero in range(1, 6):

            campo = f'foto{numero}'


            if campo not in request.files:

                continue


            foto = request.files[campo]


            if (
                not foto
                or not foto.filename
            ):

                continue


            url = salvar_imagem(
                foto,
                f'{id_usuario}_{numero}', image_batch
            )


            if url:

                fotos.append({

                    'numero':
                        numero,

                    'url':
                        url

                })


        # ==================================================
        # COMMIT
        # ==================================================

        con.commit()
        image_batch.commit()
        registrar_registro(
            cursor,
            'UPDATE',
            'PERSONALIZACAO',
            'ID_PERSONALIZACAO',
            id_personalizacao,
            dados_antes=dados_antes_log
        )
        for id_vinculo_log, vinculo_antes_log in vinculos_servico_antigos_log:
            registrar_registro(
                cursor, 'DELETE', 'SERVICO_POR_FUNCIONARIO', 'ID_SERVI_FUNCI',
                id_vinculo_log, dados_antes=vinculo_antes_log
            )
        for id_vinculo_log, vinculo_antes_log in vinculos_dia_antigos_log:
            registrar_registro(
                cursor, 'DELETE', 'FUNCIONARIO_DIA', 'ID_FUNCIONARIO_DIA',
                id_vinculo_log, dados_antes=vinculo_antes_log
            )
        for funcionario_id_log, funcionario_antes_log in zip(
            [item[0] for item in funcionarios_antigos],
            funcionarios_antigos_log
        ):
            registrar_registro(
                cursor, 'UPDATE', 'FUNCIONARIO', 'ID_FUNCIONARIO',
                funcionario_id_log, dados_antes=funcionario_antes_log
            )
        for id_dia_log, dia_antes_log in zip(
            ids_dias_antigos_log, dias_antigos_log
        ):
            registrar_registro(
                cursor, 'DELETE', 'DIAS_DE_SERVICO', 'ID_DIA', id_dia_log,
                dados_antes=dia_antes_log
            )
        for id_dia_log in ids_dias.values():
            registrar_registro(
                cursor, 'INSERT', 'DIAS_DE_SERVICO', 'ID_DIA', id_dia_log
            )
        for id_funcionario_log in funcionarios_novos_ids_log:
            registrar_registro(
                cursor, 'INSERT', 'FUNCIONARIO', 'ID_FUNCIONARIO',
                id_funcionario_log
            )

            cursor.execute(
                'SELECT ID_SERVI_FUNCI FROM SERVICO_POR_FUNCIONARIO WHERE ID_FUNCIONARIO = ?',
                (id_funcionario_log,)
            )
            for (id_vinculo_servico_log,) in cursor.fetchall():
                registrar_registro(
                    cursor, 'INSERT', 'SERVICO_POR_FUNCIONARIO', 'ID_SERVI_FUNCI',
                    id_vinculo_servico_log
                )

            cursor.execute(
                'SELECT ID_FUNCIONARIO_DIA FROM FUNCIONARIO_DIA WHERE ID_FUNCIONARIO = ?',
                (id_funcionario_log,)
            )
            for (id_vinculo_dia_log,) in cursor.fetchall():
                registrar_registro(
                    cursor, 'INSERT', 'FUNCIONARIO_DIA', 'ID_FUNCIONARIO_DIA',
                    id_vinculo_dia_log
                )


        # ==================================================
        # RESPOSTA
        # ==================================================

        return jsonify({

            'mensagem': {

                'informacao':
                    'Personalização atualizada com sucesso.',

                'tipo':
                    'sucesso'

            },

            'convites': enviar_convites(convites),
            'primeira_personalizacao':
                False,

            'logo':
                logo_url,

            'fotos':
                fotos

        }), 200


    except ImageStorageError as erro:
        if con:
            con.rollback()
        return mensagem_json(str(erro), 'erro'), erro.status

    except ValueError as erro:

        if con:

            con.rollback()


        return mensagem_json(str(erro), 'erro'), 400


    except Exception as erro:

        if con:

            try:

                con.rollback()

            except Exception:

                pass


        print(
            'ERRO AO EDITAR PERSONALIZAÇÃO:',
            erro
        )


        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao editar personalização.',

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
# ==========================================================
# BUSCAR PERSONALIZAÇÃO
# ==========================================================
# ==========================================================

@app.route(
    '/barbearia/personalizacao',
    methods=['GET']
)
def buscar_personalizacao():

    con = None
    cursor = None
    ator = obter_usuario_logado() or {}
    acesso_privado = int(ator.get('tipo', -1)) == 0

    try:

        # ==================================================
        # AUTENTICAÇÃO
        # ==================================================

        id_usuario = pegar_id_barbearia_alvo()
        acesso_privado = acesso_privado or (int(ator.get('tipo', -1)) == 2 and ator.get('id_usuario') == id_usuario)


        if not id_usuario:

            return mensagem_json('Usuário não autenticado.', 'erro'), 401


        # ==================================================
        # CONEXÃO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()


        # ==================================================
        # PERSONALIZAÇÃO
        # ==================================================

        cursor.execute("""
            SELECT
                ID_PERSONALIZACAO,
                ID_USUARIO,
                COR_PRIMARIA,
                COR_SECUNDARIA,
                COR_TERCIARIA,
                COR_TEXTO_PRIMARIO,
                COR_TEXTO_SECUNDARIO,
                TEXTO,
                LOCALIZACAO,
                CONTATO_TELEFONE,
                CONTATO_EMAIL,
                INSTAGRAM,
                NUM_FUNCIONARIOS,
                CHAVE_PIX,
                ARKHE_CLIENT_ID,
                ARKHE_CLIENT_SECRET
            FROM PERSONALIZACAO
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))


        personalizacao = (
            cursor.fetchone()
        )


        # ==================================================
        # NÃO PERSONALIZADO
        # ==================================================

        if not personalizacao:

            return jsonify({

                'mensagem': {
                    'informacao':
                        'Barbearia ainda sem personalização.',
                    'tipo':
                        'aviso'
                },

                'personalizado':
                    False,

                'personalizacao':
                    None,

                'funcionarios':
                    [],

                'dias_servico':
                    [],

                'logo':
                    None,

                'fotos':
                    []

            }), 200


        # ==================================================
        # DIAS
        # ==================================================

        cursor.execute("""
            SELECT
                ID_DIA,
                DIAS,
                ENTRADA_MANHA,
                SAIDA_MANHA,
                ENTRADA_TARDE,
                SAIDA_TARDE
            FROM DIAS_DE_SERVICO
            WHERE ID_USUARIO = ?
            ORDER BY ID_DIA
        """, (
            id_usuario,
        ))


        dias_db = (
            cursor.fetchall()
        )


        dias = []


        for dia in dias_db:

            dias.append({

                'id_dia':
                    dia[0],

                'dia':
                    dia[1],

                'entrada_manha':
                    str(dia[2])
                    if dia[2]
                    else None,

                'saida_manha':
                    str(dia[3])
                    if dia[3]
                    else None,

                'entrada_tarde':
                    str(dia[4])
                    if dia[4]
                    else None,

                'saida_tarde':
                    str(dia[5])
                    if dia[5]
                    else None

            })


        # ==================================================
        # FUNCIONÁRIOS
        # ==================================================

        cursor.execute("""
            SELECT F.ID_FUNCIONARIO,F.NOME,F.DESCRICAO,F.EMAIL,F.TELEFONE,F.COMISSAO_PERCENTUAL,F.ID_USUARIO_LOGIN
            FROM FUNCIONARIO F WHERE F.ID_BARBEARIA=? AND F.ATIVO=1
            ORDER BY F.ID_FUNCIONARIO
        """, (id_usuario,))


        funcionarios_db = (
            cursor.fetchall()
        )


        funcionarios = []


        for funcionario in funcionarios_db:

            id_funcionario = (
                funcionario[0]
            )


            # =================================================
            # SERVIÇOS
            # =================================================

            cursor.execute("""
                SELECT
                    SPF.ID_SERVICO
                FROM SERVICO_POR_FUNCIONARIO SPF
                INNER JOIN SERVICO S
                    ON S.ID_SERVICO = SPF.ID_SERVICO
                WHERE
                    SPF.ID_FUNCIONARIO = ?
                    AND S.ID_USUARIO = ?
                ORDER BY SPF.ID_SERVI_FUNCI
            """, (
                id_funcionario,
                id_usuario
            ))


            servicos_db = (
                cursor.fetchall()
            )

            # A resposta inclui todos os dias selecionados para o frontend.
            cursor.execute("""
                SELECT ID_DIA FROM FUNCIONARIO_DIA
                WHERE ID_FUNCIONARIO = ?
                ORDER BY ID_DIA
            """, (id_funcionario,))
            dias_funcionario = [linha[0] for linha in cursor.fetchall()]


            funcionarios.append({
                'email': funcionario[3] if acesso_privado else None,
                'telefone': funcionario[4] if acesso_privado else None,
                'comissao_percentual': float(funcionario[5] or 0) if acesso_privado else None,
                'possui_login': bool(funcionario[6]) if acesso_privado else False,

                'id_funcionario':
                    funcionario[0],

                'dias':
                    dias_funcionario,

                'nome':
                    funcionario[1],

                'descricao':
                    funcionario[2],

                'servicos': [

                    servico[0]

                    for servico in servicos_db

                ]

            })


        # ==================================================
        # LOGO
        # ==================================================

        logo, fotos = business_images(app.config['UPLOAD_FOLDER'], id_usuario, cursor=cursor)


        # ==================================================
        # RESPOSTA
        # ==================================================

        cursor.execute('SELECT NOME FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
        usuario_barbearia = cursor.fetchone()

        return jsonify({

            'mensagem': {
                'informacao':
                    'Personalização encontrada.',
                'tipo':
                    'sucesso'
            },

            'personalizado':
                True,

            'nome_barbearia':
                usuario_barbearia[0] if usuario_barbearia else 'Barbearia',

            'personalizacao': {

                'id_personalizacao':
                    personalizacao[0],

                'id_usuario':
                    personalizacao[1],

                'cor_primaria':
                    personalizacao[2],

                'cor_secundaria':
                    personalizacao[3],

                'cor_terciaria':
                    personalizacao[4],

                'cor_texto_primario':
                    personalizacao[5],

                'cor_texto_secundario':
                    personalizacao[6],

                'historia':
                    personalizacao[7],

                'localizacao':
                    personalizacao[8],

                'contato_telefone':
                    personalizacao[9],

                'contato_email':
                    personalizacao[10],

                'instagram':
                    personalizacao[11],

                'num_funcionarios':
                    personalizacao[12],

                'chave_pix':
                    personalizacao[13],

                'arkhe_client_id':
                    personalizacao[14] if acesso_privado else None,

                'arkhe_client_secret':
                    personalizacao[15] if acesso_privado else None

            },

            'funcionarios':
                funcionarios,

            'dias_servico':
                dias,

            'logo':
                logo,

            'fotos':
                fotos

        }), 200


    except Exception as erro:

        print(
            'ERRO AO BUSCAR PERSONALIZAÇÃO:',
            erro
        )


        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao buscar personalização.',

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
# IMAGENS
# ==========================================================

@app.route(
    '/uploads/barbearia/<path:nome_arquivo>',
    methods=['GET']
)
def imagem_barbearia(nome_arquivo):
    if os.path.basename(nome_arquivo) != nome_arquivo:
        return mensagem_json('Nome de arquivo inválido.', 'erro'), 400
    legacy = re.fullmatch(r'(\d+)(?:_([1-5]))?\.(?:jpg|jpeg|png|webp)', nome_arquivo, re.I)
    if legacy:
        slot = f'gallery{legacy.group(2)}' if legacy.group(2) else 'logo'
        managed, image = slot_state('barbearia', int(legacy.group(1)), slot)
        if managed:
            if not image:
                return mensagem_json('Imagem não encontrada.', 'erro'), 404
            nome_arquivo = image.filename
    return serve_image('barbearia', nome_arquivo,
                       legacy_folder=os.path.join(app.config['UPLOAD_FOLDER'], 'barbearia'))
