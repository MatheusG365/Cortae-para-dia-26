"""Documentação OpenAPI mantida junto ao backend Flask.

Flask não cria documentação automática como o FastAPI. Este módulo fornece o
mesmo ponto de entrada de uso (`/docs`) e publica o contrato em `/openapi.json`
sem acrescentar uma dependência de produção apenas para a interface.
"""

from copy import deepcopy
import hashlib
import re

from flask import jsonify, make_response, render_template_string

from application import app
from funcoes import decodificar_token


# Respostas padronizadas tornam a especificação curta e deixam claro que toda
# mensagem de falha usa `mensagem.informacao` ou `erro` no corpo JSON.
RESPOSTAS_PADRAO = {
    '200': {'description': 'Operação concluída.'},
    '201': {'description': 'Recurso criado.'},
    '400': {'description': 'Dados inválidos ou incompletos.'},
    '401': {'description': 'Sessão ausente, expirada ou inválida.'},
    '403': {'description': 'Perfil sem permissão.'},
    '404': {'description': 'Recurso não encontrado.'},
    '409': {'description': 'Conflito de dados, como horário já reservado.'},
    '413': {'description': 'Imagem maior que 10 MB ou limite de resolução/tamanho excedido.'},
    '502': {'description': 'Falha em serviço externo.'},
    '503': {'description': 'Serviço temporariamente indisponível.'},
    '500': {'description': 'Erro interno do servidor.'},
}


def operacao(resumo, descricao, corpo=None, autenticada=True):
    """Evita repetir o bloco de autenticação em cada operação do contrato."""
    resultado = {
        'summary': resumo,
        'description': descricao,
        'responses': deepcopy(RESPOSTAS_PADRAO),
    }
    if corpo:
        resultado['requestBody'] = {
            'required': True,
            'content': {'application/json': {'schema': corpo}},
        }
    if autenticada:
        resultado['security'] = [{'cookieAuth': []}, {'bearerAuth': []}]
    return resultado


IMAGENS_UPLOAD = (' Novos arquivos: imagem estática JPEG, PNG, WebP ou GIF, até 10 MB e 24 megapixels por arquivo; '
                  'o backend valida os bytes, aplica orientação EXIF, reduz a resolução e converte para WebP sem metadados. '
                  'O arquivo fica privado no Google Drive; o Firebird guarda a referência e a API entrega os bytes sem revelar credenciais. '
                  'Sem configuração de armazenamento retorna 503. URLs antigas continuam compatíveis por aliases registrados; '
                  'no modo Google Drive não há leitura de imagens locais sem metadados.')


USUARIO = {
    'type': 'object',
    'required': ['nome', 'email', 'telefone', 'senha', 'confirmarSenha', 'tipo'],
    'properties': {
        'nome': {'type': 'string', 'example': 'Maria Silva'},
        'email': {'type': 'string', 'format': 'email', 'example': 'maria@email.com'},
        'telefone': {'type': 'string', 'example': '11999999999'},
        'senha': {'type': 'string', 'format': 'password'},
        'confirmarSenha': {'type': 'string', 'format': 'password'},
        'tipo': {'type': 'integer', 'enum': [0, 1, 2], 'description': '0 ADM, 1 cliente, 2 barbearia.'},
        'genero': {'type': 'string', 'enum': ['masculino', 'feminino', 'outro'], 'description': 'Opcional no cadastro e disponível somente para o perfil cliente.'},
    },
}


SERVICO = {
    'type': 'object',
    'required': ['nome', 'preco', 'duracao', 'genero'],
    'properties': {
        'nome': {'type': 'string', 'example': 'Corte degradê'},
        'preco': {'type': 'number', 'format': 'float', 'minimum': 0, 'example': 45.0},
        'duracao': {'type': 'integer', 'minimum': 1, 'description': 'Duração total do serviço em minutos.', 'example': 45},
        'genero': {'type': 'string', 'enum': ['masculino', 'feminino', 'unissex'], 'description': 'Público do serviço; define o catálogo de cortes exibido.'},
        'descricao': {'type': 'string', 'example': 'Acabamento com máquina e tesoura.'},
    },
}


PERFIL = {
    'type': 'object',
    'properties': {
        'nome': {'type': 'string', 'example': 'Maria Silva'},
        'email': {'type': 'string', 'format': 'email'},
        'telefone': {'type': 'string', 'example': '11999999999'},
        'senha': {'type': 'string', 'format': 'password', 'description': 'Opcional; mantenha vazio para não alterar.'},
        'genero': {'type': 'string', 'enum': ['masculino', 'feminino', 'outro'], 'description': 'Campo do perfil cliente; pode ficar vazio.'},
        'foto': {'type': 'string', 'format': 'binary'},
    },
}


# Campos da personalização são multipart porque também incluem logo e fotos.
# A tela /docs informa esse detalhe para que o teste manual não envie JSON.
PERSONALIZACAO = {
    'type': 'object',
    'properties': {
        'cor_primaria': {'type': 'string', 'example': '#121212'},
        'cor_secundaria': {'type': 'string', 'example': '#D57C15'},
        'cor_terciaria': {'type': 'string', 'example': '#FFFFFF'},
        'cor_texto_primario': {'type': 'string', 'example': '#FFFFFF'},
        'cor_texto_secundario': {'type': 'string', 'example': '#333333'},
        'texto': {'type': 'string'},
        'localizacao': {'type': 'string'},
        'contato_telefone': {'type': 'string'},
        'contato_email': {'type': 'string', 'format': 'email'},
        'instagram': {'type': 'string'},
        'chave_pix': {'type': 'string', 'description': 'Obrigatória para receber pagamentos.'},
        'arkhe_client_id': {'type': 'string', 'description': 'Client ID da conta Arkhé; obrigatório.'},
        'arkhe_client_secret': {'type': 'string', 'format': 'password', 'description': 'Client Secret da conta Arkhé; obrigatório.'},
        'logo': {'type': 'string', 'format': 'binary'},
        **{f'foto{number}': {'type': 'string', 'format': 'binary',
                            'description': f'Foto pública da galeria na posição {number}; campo individual, não array fotos.'}
           for number in range(1, 6)},
        'funcionarios[0][nome]': {'type': 'string'},
        'funcionarios[0][id_funcionario]': {'type': 'integer', 'description': 'Preserve este ID ao editar um barbeiro existente.'},
        'funcionarios[0][email]': {'type': 'string', 'format': 'email', 'maxLength': 150, 'description': 'Novos barbeiros recebem uma conta exclusiva com convite para definir senha.'},
        'funcionarios[0][telefone]': {'type': 'string', 'description': 'DDD e telefone, 10 ou 11 dígitos.'},
        'funcionarios[0][comissao_percentual]': {'type': 'number', 'minimum': 0, 'maximum': 100, 'description': 'Percentual sobre o valor contratado de atendimentos concluídos; padrão 0.'},
        'funcionarios[0][dias]': {'type': 'string', 'example': 'segunda,terca'},
        'funcionarios[0][servicos]': {'type': 'string', 'example': '1,2'},
    },
}


# Corte do catálogo de visagismo. Criação/edição são multipart porque aceitam
# upload de imagem OU imagem_url HTTPS.
VISAGISMO_CORTE = {
    'type': 'object',
    'properties': {
        'nome': {'type': 'string', 'example': 'Low Fade'},
        'descricao': {'type': 'string', 'example': 'Degradê baixo com topo texturizado.'},
        'categoria': {'type': 'string', 'enum': ['cabelo', 'barba', 'barba_cabelo', 'corte_pintura', 'pintura']},
        'genero': {'type': 'string', 'enum': ['masculino', 'feminino', 'unissex'], 'description': 'Filtro do catálogo. A seleção depende do serviço escolhido, não do gênero do cliente.'},
        'imagem': {'type': 'string', 'format': 'binary', 'description': 'Arquivo de imagem estática de até 10 MB; convertido pelo servidor em WebP privado no Drive.'},
        'imagem_url': {'type': 'string', 'format': 'uri', 'example': 'https://exemplo.com/corte.jpg'},
    },
}


AGENDAMENTO = {
    'type': 'object',
    'required': ['id_barbearia', 'ids_servicos', 'data', 'horario'],
    'properties': {
        'id_barbearia': {'type': 'integer', 'example': 3},
        'ids_servicos': {'type': 'array', 'items': {'type': 'integer'}, 'example': [1, 2]},
        'data': {'type': 'string', 'format': 'date', 'example': '2026-10-05'},
        'horario': {'type': 'string', 'example': '14:30'},
        'id_corte': {'type': 'integer', 'description': 'Opcional: corte escolhido no visagismo.'},
        'id_visagismo': {'type': 'integer', 'description': 'Opcional: sessão de visagismo que originou a escolha.'},
        'escolha_corte': {'type': 'string', 'enum': ['catalogo', 'na_hora', 'profissional'], 'description': 'catalogo exige id_corte. na_hora/profissional não aceitam id_corte/id_visagismo: o cliente deve limpar esses IDs antes de enviar. Serviços de pintura/coloração mantêm o fluxo de simulação.'},
        'confirmacao_resumo': {'type': 'string', 'description': 'Assinatura recebida de /agendamentos/resumo, exigida com taxa ativa. Alterar serviços, profissional, cliente ou valores exige novo resumo.'},
        'id_funcionario': {'type': 'integer', 'nullable': True, 'description': 'Opcional ou null: reserva sem profissional definido, usando disponibilidade e preço-base do salão. Quando informado, deve pertencer à barbearia e atender todos os serviços.'},
    },
}


OPENAPI = {
    'openapi': '3.0.3',
    'info': {
        'title': 'Cortaê API',
        'version': '2.2.0',
        'description': 'API compartilhada pelo site React e pelo aplicativo React Native. Imagens enviadas são validadas, convertidas em WebP sem metadados e armazenadas no Google Drive privado; o Firebird guarda referências e a API entrega bytes sem fallback local no modo Drive. Perfis, logos, galerias, produtos, catálogo e mídia fixa são públicos; fotos/resultados de visagismo exigem ACL. /help, /docs e /openapi.json são exclusivos do ADM. O login web grava o JWT no cookie `access_token`; o frontend usa `credentials: include`. Com `X-Cortae-Client: mobile`, o login permite somente cliente (tipo 1) e barbearia (tipo 2), devolve o JWT no JSON sem definir cookie e as chamadas nativas usam `Authorization: Bearer <access_token>`. Agendamentos iniciam como `agendado`; só cliente ou barbearia podem cancelá-los e, após o horário, a barbearia registra se o atendimento foi concluído ou se houve falta.',
    },
    'servers': [{'url': '/', 'description': 'Backend atual'}],
    'paths': {
        '/midia/site/{nome}': {'get': operacao('Exibir imagem fixa do site', 'Logo, banner ou foto fixa registrada no Firebird. Entrega WebP do Drive privado sem revelar IDs; imagem ausente retorna 404, falha do provedor retorna 503. Sem fallback para pasta local.', autenticada=False)},
        '/midia/mobile/{nome}': {'get': operacao('Exibir imagem de conteúdo do app', 'Logo, fundo e banner do aplicativo em WebP pelo Drive privado. Ícones de compilação e splash nativo continuam empacotados localmente. Sem fallback para pasta local.', autenticada=False)},
        '/health': {'get': operacao('Verificar saúde', 'Confere conexão, tabelas/campos exigidos e tabela de auditoria, usando somente consultas. Não cria nem altera estrutura. Retorna 503 quando recursos obrigatórios estão ausentes; manutenção manual: python -m migrations (conferir) ou --aplicar após backup.', None, False)},
        '/cadastro': {'post': operacao('Cadastrar usuário', 'Cria usuário e envia código de confirmação por e-mail. O tipo 0 exige sessão ativa de administrador.', USUARIO, False)},
        '/verificar-codigo': {'post': operacao('Confirmar e-mail', 'Ativa o cadastro usando o código de seis dígitos.', {
            'type': 'object', 'required': ['email', 'codigo'], 'properties': {'email': {'type': 'string'}, 'codigo': {'type': 'string', 'example': '123456'}}
        }, False)},
        '/login': {'post': {
            **operacao('Entrar', 'Valida senha, confirmação de e-mail e estado da conta. Sem o cabeçalho mobile, grava JWT no cookie HttpOnly access_token por 7200 segundos. Com X-Cortae-Client: mobile, permite somente perfis 1 e 2; outros perfis retornam 403. Na resposta mobile, envia access_token, token_type=Bearer e expires_in=7200 no JSON, sem Set-Cookie. Respostas usam Cache-Control: no-store. Nas chamadas seguintes envie Authorization: Bearer <access_token>; o cabeçalho mobile apenas seleciona o formato de login e não concede permissões.', {
            'type': 'object', 'required': ['email', 'senha'], 'properties': {'email': {'type': 'string'}, 'senha': {'type': 'string', 'format': 'password'}}
            }, False),
            'parameters': [{'name': 'X-Cortae-Client', 'in': 'header', 'required': False,
                            'description': 'Envie mobile para obter autenticação nativa por Bearer (somente tipos 1 e 2).',
                            'schema': {'type': 'string', 'enum': ['mobile']}}],
            'responses': {**RESPOSTAS_PADRAO, '200': {
                'description': 'Usuário autenticado. Os três campos de token aparecem somente na resposta mobile.',
                'headers': {'Cache-Control': {'schema': {'type': 'string', 'enum': ['no-store']}}},
                'content': {'application/json': {'schema': {'type': 'object', 'required': ['usuario', 'mensagem'], 'properties': {
                    'usuario': {'type': 'object', 'properties': {
                        'id_usuario': {'type': 'integer'}, 'id': {'type': 'integer'}, 'nome': {'type': 'string'},
                        'email': {'type': 'string'}, 'telefone': {'type': 'string', 'nullable': True},
                        'tipo': {'type': 'integer', 'enum': [0, 1, 2, 3]}, 'genero': {'type': 'string', 'nullable': True}}},
                    'mensagem': {'type': 'object', 'properties': {'informacao': {'type': 'string'}, 'tipo': {'type': 'string'}}},
                    'access_token': {'type': 'string'}, 'token_type': {'type': 'string', 'enum': ['Bearer']},
                    'expires_in': {'type': 'integer', 'enum': [7200]},
                }}}},
            }},
        }},
        '/logout': {'post': operacao('Sair', 'Remove os cookies de sessão; não revoga JWT já emitido. O aplicativo nativo também deve apagar o Bearer e o perfil armazenados localmente.')},
        '/recuperar-senha': {'post': operacao('Recuperar senha', 'Fluxo público de envio, validação e troca de senha; consulte os campos exigidos pela etapa enviada.', autenticada=False)},
        '/listar_usuarios': {'get': operacao('Listar usuários', 'Exclusivo para ADM. Aceita o filtro opcional `tipo` (0, 1 ou 2).')},
        '/usuarios/{id_usuario}/status': {'put': operacao('Ativar/desativar usuário', 'Exclusivo para ADM. Ao desativar, `motivo` é obrigatório e é enviado por e-mail.', {
            'type': 'object', 'required': ['ativo'], 'properties': {'ativo': {'type': 'boolean'}, 'motivo': {'type': 'string'}}
        })},
        '/dados-perfil/{id_usuario}': {'get': operacao('Buscar perfil', 'Busca os dados de um perfil autorizado.')},
        '/editar-usuario/{id_usuario}': {'put': {
            **operacao('Editar perfil', 'Atualiza os campos do usuário autenticado ou administrado. Envie `multipart/form-data`; para cliente, `genero` é opcional e pode ser masculino, feminino ou outro.'+IMAGENS_UPLOAD, None),
            'requestBody': {'content': {'multipart/form-data': {'schema': PERFIL}}},
        }},
        '/excluir-foto-perfil/{id_usuario}': {'delete': operacao('Excluir foto de perfil', 'Remove a foto de perfil do usuário.')},
        '/barbearias-disponiveis': {'get': operacao('Listar barbearias', 'Lista as barbearias cadastradas e a indicação de personalização.')},
        '/barbearia/servicos': {
            'get': operacao('Listar serviços', 'Lista os serviços da barbearia autenticada.'),
            'post': operacao('Criar serviço', 'Cria um serviço para posterior vínculo a funcionários. `duracao` é obrigatória, em minutos, e é usada para montar os horários disponíveis.', SERVICO),
        },
        '/barbearia/servicos/{id_servico}': {
            'put': operacao('Editar serviço', 'Atualiza nome, preço, duração em minutos e descrição de um serviço da barbearia autenticada.', SERVICO),
            'delete': operacao('Excluir serviço', 'Exclui um serviço pertencente à barbearia autenticada.'),
        },
        '/barbearia/personalizacao': {
            'get': operacao('Buscar personalização', 'Retorna cores, contatos, fotos, serviços, funcionários e dias. ADM pode informar `id_usuario` na query.'),
            'post': {
                **operacao('Criar personalização', 'Primeira personalização da barbearia. Envie `multipart/form-data`. É obrigatório cadastrar pelo menos um funcionário e informar `chave_pix`, `arkhe_client_id` e `arkhe_client_secret`.'+IMAGENS_UPLOAD, None),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': PERSONALIZACAO}}},
            },
            'put': {
                **operacao('Editar personalização', 'Atualiza a personalização existente. Envie `multipart/form-data`. A barbearia deve manter pelo menos um funcionário e os dados de pagamento (chave Pix e credenciais Arkhé).'+IMAGENS_UPLOAD, None),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': PERSONALIZACAO}}},
            },
        },
        '/fotos-perfil/{nome_arquivo}': {'get': operacao('Exibir foto de perfil', 'Proxy público da foto de perfil atual. Retorna o conteúdo WebP referenciado no banco; aceita URLs locais antigas e respeita exclusões.', autenticada=False)},
        '/uploads/perfil/{nome_arquivo}': {'get': operacao('Exibir upload de perfil', 'Proxy público de perfil com nome opaco .webp; consulta a referência no Firebird e lê o Drive privado. URLs locais antigas permanecem compatíveis.', autenticada=False)},
        '/uploads/barbearia/{nome_arquivo}': {'get': operacao('Exibir imagem da barbearia', 'Proxy público da logo ou galeria da barbearia. Nomes opacos .webp resolvem a referência no Firebird; URLs antigas consultam o espaço atual registrado. O provedor Google Drive não usa arquivos locais como fallback.', autenticada=False)},
        '/visagismo/status': {'get': operacao(
            'Diagnóstico do visagismo',
            'Retorna somente a indicação booleana de chave configurada, disponibilidade da biblioteca e modelos configurados. Nunca retorna chave ou prefixo. Sem autenticação.',
            autenticada=False)},
        '/visagismo/cortes': {
            'get': operacao(
                'Listar cortes do catálogo',
                'Público. Query opcional: id_barbearia + ids_servicos (ex: 1,2) filtram por categoria (cabelo/barba/barba_cabelo); ou passe categoria direto.',
                autenticada=False),
            'post': {
                **operacao('Criar corte', 'ADM ou barbearia. Envie multipart/form-data com nome, categoria e imagem (arquivo) ou imagem_url HTTPS. URLs externas cadastradas continuam aceitas; o servidor não as migra automaticamente.'+IMAGENS_UPLOAD),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': VISAGISMO_CORTE}}},
            },
        },
        '/visagismo/cortes/{id_corte}': {
            'put': {
                **operacao('Editar corte', 'ADM ou barbearia. Mesmos campos da criação; nova imagem substitui a referência anterior somente após confirmar a transação.'+IMAGENS_UPLOAD),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': VISAGISMO_CORTE}}},
            },
            'delete': operacao('Excluir corte', 'ADM ou barbearia. Exclusão lógica (ATIVO=0), preserva histórico e agendamentos.')},
        '/visagismo/analisar': {
            'post': {
                **operacao(
                    'Analisar foto (IA)',
                    'Logado. Multipart: imagem (JPG/PNG/WEBP até 10 MB), id_barbearia, ids_servicos. '
                    'A IA analisa características visíveis e devolve exatamente uma recomendação ativa do catálogo, com motivo personalizado, '
                    'caracteristicas (seis campos), cabelo_atual, observacoes, categoria, versao_analise=2, recomendacoes, id_visagismo e foto_url. '
                    'Sem pessoa/rosto ou corte viável retorna 422; sem integração 503; resposta inválida/provedor 502. Não há fallback aleatório.'+IMAGENS_UPLOAD),
                'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': {
                    'type': 'object',
                    'required': ['imagem', 'id_barbearia', 'ids_servicos'],
                    'properties': {
                        'imagem': {'type': 'string', 'format': 'binary'},
                        'id_barbearia': {'type': 'integer', 'example': 3},
                        'ids_servicos': {'type': 'string', 'example': '1,2'},
                    }}}}},
            },
        },
        '/visagismo/salvar-foto': {'post': {
            **operacao(
                'Salvar foto para escolha manual ou coloração',
                'Logado. Salva a foto sem inventar análise. Serviços somente de coloração criam modo=cor; os demais modo=manual, validado contra a foto antes da simulação. Envie imagem e serviços em multipart.'+IMAGENS_UPLOAD,
                None),
            'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': {
                'type': 'object',
                'required': ['imagem', 'id_barbearia', 'ids_servicos'],
                'properties': {
                    'imagem': {'type': 'string', 'format': 'binary'},
                    'id_barbearia': {'type': 'integer', 'example': 3},
                    'ids_servicos': {'type': 'string', 'example': '4'},
                },
            }}}},
        }},
        '/visagismo/{id_visagismo}/simular': {'post': operacao(
            'Gerar simulação do corte',
            'Logado. JSON {id_corte?, cor?, alvo?}. Em análise v2 aceita só o corte recomendado; análises antigas exigem nova análise (409). '
            'Revalida corte ativo, compatibilidade e serviços. Preserva pessoa/cobertura real e escopo: barba não altera cabelo. '
            'Envia cliente primeiro, referência cadastrada depois quando disponível; qualidade medium/high. Retorna imagem_url, referencia_utilizada e aviso. '
            'Coloração não altera corte e alvo deve pertencer aos serviços. Sem integração 503; provedor/resposta inválida 502.',
            {'type': 'object', 'properties': {
                'id_corte': {'type': 'integer', 'example': 1},
                'cor': {'type': 'string', 'example': '#5B3A29'},
                'alvo': {'type': 'string', 'enum': ['cabelo', 'barba', 'ambos'], 'description': 'Padrão derivado dos serviços; não permite áreas fora do escopo.'},
            }})},
        '/uploads/visagismo/{tipo}/{nome}': {'get': operacao(
            'Exibir arquivo do visagismo',
            'tipo = cortes (público) | fotos | resultados (cliente dono, barbearia responsável, profissional vinculado ao agendamento ou ADM, via cookie ou Bearer). A ACL é conferida antes da leitura no Drive; nome opaco não concede acesso. Aceita nomes legados já vinculados à sessão. Sem sessão/permissão em fotos e resultados retorna 403; cortes não exige autenticação.',
            autenticada=False)},
        '/agendamentos/horarios': {'get': operacao(
            'Listar horários disponíveis',
            'Público. Query obrigatória: id_barbearia, ids_servicos (ou servicos, ex: 1,2), data (AAAA-MM-DD). '
            'Query opcional id_funcionario: filtra a agenda do barbeiro (só dias dele, só ocupação dele; 404 se não for da barbearia, 400 se não atender os serviços). '
            'Retorna {data, duracao_minutos, funcionario, valor_total, servicos, horarios: [{horario, fim, disponivel}]} com orçamento individual e slots dentro dos turnos e bloqueios. Sem id_funcionario usa o preço-base do salão e horários globais, mesmo havendo equipe ativa; funcionario retorna null. Bloqueios, expediente, duração e reservas em conflito continuam sendo respeitados.',
            autenticada=False)},
        '/agendamentos': {
            'get': operacao(
                'Listar agendamentos',
                'Logado. Cliente vê os próprios; barbearia vê os seus; ADM filtra por id_barbearia/id_usuario. '
                'Filtros opcionais status e data (AAAA-MM-DD). Retorna itens com cliente/barbearia/profissional/serviços, valor_total e `historico_atendimento`. '
                'Agendamentos não são concluídos automaticamente ao passar do horário e só são cancelados por ação do cliente ou da barbearia.'),
            'post': operacao(
                'Criar agendamento',
                'Logado. Cria o agendamento com status `agendado`, valida expediente, turnos e bloqueios, trava contra reserva dupla (409 se ocupado) e vincula id_corte/id_visagismo quando vindos do visagismo. id_funcionario é opcional ou null, inclusive com equipe ativa; sem vínculo usa preço-base e agenda do salão. Com profissional, valida elegibilidade e preço individual. Preço, duração e profissional aceitos ficam no histórico. Quando a taxa está ativa, consulte /agendamentos/resumo e envie confirmacao_resumo; termos publicados exigem aceite da versão atual (428 se pendente). '
                'Retorna 201 com {id_agendamento, inicio_em, fim_em, id_funcionario}.',
                AGENDAMENTO)},
        '/agendamentos/{id_agendamento}/cancelar': {'put': operacao(
            'Cancelar agendamento',
            'Cliente dono, barbeiro responsável, barbearia dona ou ADM. Cliente respeita o prazo configurado no salão. Marca como cancelado e coloca avisos para cliente e salão na fila persistida. Retorna {email_agendado:true}; não confirma entrega SMTP.')},
        '/agendamentos/{id_agendamento}/reagendar': {'put': operacao(
            'Reagendar',
            'Cliente dono, barbeiro responsável, barbearia dona ou ADM. Body {data, horario, id_funcionario?}. Cliente respeita o prazo configurado no salão. Consulte `/agendamentos/horarios` para mostrar opções livres. Revalida expediente, turnos, bloqueios e ocupação, excluindo o próprio atendimento; invalida lembretes antigos e coloca avisos na fila persistida. Retorna {email_agendado:true,agendamento}; não confirma entrega SMTP.',
            {'type': 'object', 'required': ['data', 'horario'],
             'properties': {'data': {'type': 'string', 'format': 'date'}, 'horario': {'type': 'string', 'example': '14:30'},
                            'id_funcionario': {'type': 'integer'}}})},
        '/agendamentos/{id_agendamento}/avisar': {'post': operacao(
            'Avisar cliente',
            'Barbearia ou ADM. Body {texto até 500 caracteres}. Grava em AVISO e envia e-mail ao cliente. Retorna 201 com {email_enviado}.',
            {'type': 'object', 'required': ['texto'], 'properties': {'texto': {'type': 'string', 'example': 'Chegue com 10 minutos de antecedência.'}}})},
        '/agendamentos/{id_agendamento}/status-atendimento': {'put': operacao(
            'Registrar atendimento',
            "Barbearia dona, barbeiro responsável ou ADM. Depois do fim do horário agendado, registra manualmente {status: 'concluido' ou 'faltou'} e adiciona o evento ao `historico_atendimento` devolvido pela listagem. Cliente não pode alterar este status.",
            {'type': 'object', 'required': ['status'], 'properties': {
                'status': {'type': 'string', 'enum': ['concluido', 'faltou']},
                'valor_realizado': {'type': 'number', 'minimum': 0, 'description': 'Somente proprietário ou ADM: informa o valor efetivo de um atendimento legado sem preço histórico. Não altera valores já registrados.'}
            }})},
        '/pagamentos/pix': {'post': operacao(
            'Gerar cobrança Pix (Arkhé)',
            'Cliente dono, barbearia proprietária ou ADM; perfil de barbeiro não autorizado. Body {id_agendamento}; valor informado pelo navegador é ignorado. Usa o preço salvo no agendamento, cria a cobrança na Arkhé e registra em FINANCEIRO como pix_pendente. Agendamento legado sem preço histórico retorna 400. Retorna 201 com {id_cobranca, codigo_pagamento, valor, status}. Resposta HTTP 5xx da Arkhé é tratada como indisponibilidade, sem repetição automática da criação nem confirmação de pagamento. Em resultado incerto, confira as cobranças antes de tentar novamente.',
            {'type': 'object', 'required': ['id_agendamento'], 'properties': {'id_agendamento': {'type': 'integer'}, 'valor': {'type': 'number'}}})},
        '/pagamentos/pix/{id_cobranca}': {'get': operacao(
            'Consultar cobrança Pix',
            'Logado. Consulta o status na Arkhé; se pago, marca pix_pago no FINANCEIRO. Retorna {pago, status}.')},
        '/pagamentos/boleto': {'post': operacao(
            'Gerar boleto do agendamento',
            'Cliente dono, barbearia proprietária ou ADM. Body {id_agendamento}. Usa o preço salvo, cria a cobrança e registra em FINANCEIRO como boleto_pendente. Falha do provedor não cria boleto fictício. Retorna 201 com {url_boleto, codigo_pagamento, valor}.',
            {'type': 'object', 'required': ['id_agendamento'], 'properties': {'id_agendamento': {'type': 'integer'}}})},
        '/pagamentos/cartao': {'post': operacao(
            'Gerar checkout de cartão do agendamento',
            'Cliente dono, barbearia proprietária ou ADM. Body {id_agendamento}. Usa o preço salvo e registra em FINANCEIRO como cartao_pendente. Falha do provedor não cria checkout fictício. Retorna 201 com {url_checkout, valor}.',
            {'type': 'object', 'required': ['id_agendamento'], 'properties': {'id_agendamento': {'type': 'integer'}}})},
        '/pagamentos/na-hora': {'post': operacao(
            'Escolher pagamento no local ou confirmar recebimento',
            'Body {id_agendamento}. Cliente dono registra na_hora_pendente, status=0, confirmado=false. Barbeiro não autorizado. Proprietário ou ADM confirma somente o saldo ainda devido como na_hora, status=1; também aceita atendimento concluído. Recebimentos parciais anteriores são descontados. Repetições após quitação não duplicam. Não aceita cancelado/falta. O estado do atendimento não é alterado; nenhum provedor é chamado.',
            {'type': 'object', 'required': ['id_agendamento'], 'properties': {'id_agendamento': {'type': 'integer'}}})},
        '/pagamentos/agendamento/{id_agendamento}': {'get': operacao(
            'Consultar pagamentos do agendamento',
            'Cliente dono, barbearia proprietária ou ADM. Retorna cobranças somente do cliente e do ID exato do agendamento; cada item contém tipo, valor, status, confirmado e pendente. Inclui valor_total, valor_recebido, saldo, parcial e quitado; na_hora_confirmado exige quitação completa. Perfil de barbeiro não autorizado.')},
        '/financeiro/grafico': {'get': operacao(
            'Gráfico financeiro (pygal)',
            'Barbearia ou ADM. Query data_inicio, data_fim (AAAA-MM-DD, máx. 92 dias) e tipo=todos|ganhos|custos. ADM pode filtrar id_barbearia. Retorna SVG de linha.')},
        '/financeiro/geral/resumo': {'get': operacao(
            'Resumo financeiro geral (ADM)',
            'ADM. Agregado do banco local (snapshot atualizado a cada visualização do dono da conta). Query data_inicio/data_fim. Retorna totais + por_barbearia.')},
        '/financeiro/geral/movimentacoes': {'get': operacao(
            'Movimentações gerais (ADM)',
            'ADM. Itemizado do banco local com barbearia_nome. Query data_inicio/data_fim.')},
        '/financeiro/geral/grafico': {'get': operacao(
            'Gráfico geral (ADM)',
            'ADM. SVG de linha agregado de todas as barbearias. Query data_inicio, data_fim e tipo.')},
        '/financeiro/conta': {'get': operacao('Consultar conta Arkhé', 'Barbearia ou ADM. Retorna os dados da conta financeira vinculada, quando configurada.')},
        '/financeiro/saldo': {'get': operacao('Consultar saldo', 'Barbearia ou ADM. Retorna {saldo, origem_dados}; usa dados Arkhé quando disponíveis e cálculo local como alternativa.')},
        '/financeiro/resumo': {'get': operacao('Resumo financeiro da barbearia', 'Barbearia ou ADM. Query opcional `data_inicio` e `data_fim` (AAAA-MM-DD, intervalo máximo de 92 dias). Retorna receitas, despesas e saldo do período.')},
        '/financeiro/movimentacoes': {'get': operacao('Movimentações financeiras da barbearia', 'Barbearia ou ADM. Query opcional `data_inicio` e `data_fim`. Retorna {movimentacoes, total, origem_dados}.')},
        '/financeiro/cobrancas/pix': {'post': operacao('Criar cobrança Pix avulsa', 'Barbearia ou ADM. Cria cobrança na conta financeira; não vincula um agendamento.', {
            'type': 'object', 'required': ['valor'], 'properties': {'valor': {'type': 'number', 'minimum': 0.01, 'example': 45.0}}
        })},
        '/financeiro/cobrancas/pix/{id_cobranca}': {'get': operacao('Consultar cobrança Pix avulsa', 'Barbearia ou ADM. Consulta uma cobrança Pix diretamente na Arkhé.')},
        '/financeiro/cobrancas/boleto': {'post': operacao('Criar boleto avulso', 'Barbearia ou ADM. Body {valor}. Quando Arkhé não suporta boleto, pode retornar um boleto simulado.', {
            'type': 'object', 'required': ['valor'], 'properties': {'valor': {'type': 'number', 'minimum': 0.01, 'example': 45.0}}
        })},
        '/financeiro/cobrancas/cartao': {'post': operacao('Criar checkout de cartão avulso', 'Barbearia ou ADM. Body {valor}. Quando Arkhé não suporta cartão, pode retornar checkout simulado.', {
            'type': 'object', 'required': ['valor'], 'properties': {'valor': {'type': 'number', 'minimum': 0.01, 'example': 45.0}}
        })},
        '/financeiro/cobrancas/na-hora': {'post': operacao('Registrar recebimento avulso na hora', 'Barbearia ou ADM. Body {valor}; confirma um recebimento sem criar cobrança externa.', {
            'type': 'object', 'required': ['valor'], 'properties': {'valor': {'type': 'number', 'minimum': 0.01, 'example': 45.0}}
        })},
        '/financeiro/cobrancas/boleto/{id_cobranca}': {'get': operacao('Consultar boleto avulso', 'Barbearia ou ADM. Consulta o boleto na Arkhé.')},
        '/financeiro/cobrancas/cartao/{id_cobranca}': {'get': operacao('Consultar checkout de cartão avulso', 'Barbearia ou ADM. Consulta o checkout na Arkhé.')},
        '/financeiro/webhook/arkhe': {'post': operacao('Receber webhook Arkhé', 'Endpoint de integração chamado pela Arkhé para notificações de pagamento. Não usa autenticação por cookie.', autenticada=False)},
        '/barbearias/{id_barbearia}/funcionarios': {'get': operacao(
            'Listar profissionais da barbearia',
            'Público. Retorna [{id_funcionario, nome, descricao, servicos, dias}] para o cliente escolher o barbeiro. '
            'Query opcional servicos=1,2 filtra só quem atende TODOS os serviços.',
            autenticada=False)},
        '/agendamentos/lista-espera': {
            'get': operacao('Minha lista de espera', 'Perfil cliente. Retorna somente suas inscrições e os estados de aviso por e-mail.'),
            'post': operacao('Entrar na lista de espera',
                'Perfil cliente. Exige horário futuro ocupado, dentro do expediente e compatível com serviços e profissional. '
                'Repetir a inscrição ativa não cria duplicata. Ao liberar o intervalo por cancelamento ou remarcação, '
                'a fila persistida de e-mail revalida disponibilidade antes de enviar. O aviso não reserva o horário.',
                {'type': 'object', 'required': ['id_barbearia', 'ids_servicos', 'data', 'horario'], 'properties': {
                    'id_barbearia': {'type': 'integer'}, 'ids_servicos': {'type': 'array', 'items': {'type': 'integer'}},
                    'data': {'type': 'string', 'format': 'date'}, 'horario': {'type': 'string', 'example': '10:00'},
                    'id_funcionario': {'type': 'integer'}, 'id_corte': {'type': 'integer'}, 'id_visagismo': {'type': 'integer'}}})},
        '/agendamentos/lista-espera/{id_espera}': {'delete': operacao('Sair da lista de espera', 'Somente o cliente proprietário pode cancelar sua inscrição e os avisos pendentes.')},
        '/barbeiros/ativar': {'post': operacao('Ativar acesso do barbeiro',
            'Convite de uso único, válido por 48 horas. Define senha com os mesmos requisitos do cadastro, no máximo 72 bytes UTF-8. '
            'O perfil 3 é criado somente pela barbearia ou pelo administrador, nunca no cadastro público.',
            {'type': 'object', 'required': ['token', 'senha', 'confirmarSenha'], 'properties': {
                'token': {'type': 'string'}, 'senha': {'type': 'string', 'format': 'password'},
                'confirmarSenha': {'type': 'string', 'format': 'password'}}}, autenticada=False)},
        '/barbearias/{id_barbearia}/funcionarios/{id_funcionario}/convite': {'post': operacao(
            'Reenviar convite do barbeiro', 'Administrador ou barbearia proprietária. Invalida o convite anterior e retorna link de ativação e email_enviado. Conta já ativada usa recuperação de senha.')},
        '/barbearia/comissoes': {'get': operacao('Comissões da equipe para pagamento manual',
            'Somente proprietário ou ADM. Query inicio/fim AAAA-MM-DD, período até 366 dias; ADM informa id_usuario ou id_barbearia. '
            'Retorna funcionários ativos e inativos com bases, percentuais históricos, valores de comissão e detalhes de cada atendimento. '
            'Inclui totais e avisos sobre preços históricos ausentes, atendimento sem profissional e comissão ausente. '
            'O cálculo é salvo no Firebird do Cortaê; este relatório não registra ou executa repasse bancário.')},
        '/barbeiro/painel': {'get': operacao('Painel do barbeiro',
            'Exclusivo do perfil 3 com vínculo ativo. Query inicio/fim AAAA-MM-DD, intervalo até 366 dias. '
            'Retorna funcionario, estatisticas, agendamentos e comissoes somente do profissional vinculado. '
            'Estatísticas de realizados/cancelados/faltas e valores usam a data do agendamento; remarcados contam agendamentos distintos com evento no período. '
            'Valor dos atendimentos concluídos, recebimentos confirmados e comissão calculada são apresentados separadamente. '
            'Snapshots legados ausentes são informados; comissão e percentual persistidos não mudam após edição do cadastro.')},
    },
    'components': {'securitySchemes': {
        'cookieAuth': {'type': 'apiKey', 'in': 'cookie', 'name': 'access_token'},
        'bearerAuth': {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'},
    }},
}

# Gestão local: o proprietário usa seu próprio ID. O administrador informa
# id_barbearia na query, exceto na auditoria global. Valores monetários são BRL.
GESTAO_ESCOPO = 'Proprietário ou ADM; ADM informa id_barbearia. Dados restritos ao estabelecimento. '
GESTAO_PERIODO = 'Query inicio/fim em AAAA-MM-DD, intervalo máximo de 366 dias. '
OPENAPI['paths'].update({
    '/gestao/agenda': {
        'get': operacao('Agenda diária, semanal ou mensal', GESTAO_ESCOPO + GESTAO_PERIODO + 'Perfil 3 vê somente sua própria agenda e os clientes vinculados. Retorna agendamentos, profissionais, serviços e clientes.'),
        'post': operacao('Reservar para cliente cadastrado', GESTAO_ESCOPO + 'Perfil 3 reserva somente para si. Body {id_cliente, id_funcionario, ids_servicos, data, horario}. Reutiliza validações de duração, disponibilidade, preço individual e conflitos do cliente.')},
    '/gestao/agenda/cliente': {'get': operacao('Encontrar cliente por e-mail exato', GESTAO_ESCOPO + 'Também permite perfil 3. Query email obrigatório. Busca um cliente ativo; não oferece listagem global de usuários.')},
    '/gestao/agenda/config': {
        'get': operacao('Regras da agenda', GESTAO_ESCOPO + 'Retorna cancelamento_horas, reagendamento_horas e lembrete_horas.'),
        'put': operacao('Configurar prazos e lembretes', GESTAO_ESCOPO + 'Body com os três campos inteiros de 0 a 720 horas. Prazos limitam alterações pelo cliente. Zero mantém cancelamento/reagendamento sem antecedência mínima; lembrete zero desativa lembretes.')},
    '/gestao/agenda/bloqueios': {
        'get': operacao('Consultar bloqueios', GESTAO_ESCOPO + 'Retorna intervalos bloqueados do salão e dos profissionais.'),
        'post': operacao('Bloquear folga, feriado ou intervalo', GESTAO_ESCOPO + 'Body {inicio_em, fim_em, motivo, id_funcionario?}; datas locais ISO sem fuso. Sem profissional bloqueia o salão. Rejeita sobreposição com reservas ativas.')},
    '/gestao/agenda/bloqueios/{id_bloqueio}': {'delete': operacao('Liberar intervalo bloqueado', GESTAO_ESCOPO + 'Somente bloqueios do estabelecimento selecionado.')},
    '/gestao/profissionais/{id_funcionario}/config': {
        'get': operacao('Preços, turnos e comissão individual', GESTAO_ESCOPO + 'Retorna comissao_tipo, comissao_valor, horarios e precos.'),
        'put': operacao('Configurar profissional', GESTAO_ESCOPO + 'Body {comissao_tipo: percentual|fixa, comissao_valor, horarios:[{dia,inicio,fim}], precos:[{id_servico,preco}]}. Turnos semanais sem sobreposição, dentro do expediente. Intervalos são lacunas entre turnos. Comissão fixa por atendimento concluído; histórico anterior preservado. Preço individual prevalece sobre catálogo em reservas futuras.')},
    '/gestao/servicos/{id_servico}/ativo': {'put': operacao('Ativar ou desativar serviço', GESTAO_ESCOPO + 'Body {ativo: boolean}. Preserva atendimentos históricos; serviço inativo não aceita nova reserva.')},
    '/gestao/clientes': {'get': operacao('Clientes do estabelecimento', GESTAO_ESCOPO + 'Somente clientes com atendimento no salão. Query busca, inativos_dias, inicio/fim. Inclui frequência, última visita e faltas.')},
    '/gestao/clientes/{id_cliente}': {
        'get': operacao('Ficha e histórico do cliente', GESTAO_ESCOPO + 'Atendimentos e financeiro somente deste salão; inclui observacoes e preferencias.'),
        'put': operacao('Salvar observações e preferências', GESTAO_ESCOPO + 'Body {observacoes, preferencias}, cada texto até 10000 caracteres.')},
    '/gestao/logs': {'get': operacao('Auditoria em banco separado', 'Exclusivo ADM. Query pagina, limite (até 100), acao, tabela, usuario, inicio/fim, busca. Paginação e valores sensíveis mascarados também nos registros antigos.')},
    '/gestao/relatorios': {'get': operacao('Relatório operacional', GESTAO_ESCOPO + GESTAO_PERIODO + 'Resumo de status, serviços, profissionais, horários, frequência e clientes inativos; valores de atendimentos concluídos separados do caixa.')},
    '/gestao/financeiro/categorias': {
        'get': operacao('Categorias financeiras', GESTAO_ESCOPO),
        'post': operacao('Cadastrar categoria', GESTAO_ESCOPO + 'Body {nome, tipo: entrada|saida}.')},
    '/gestao/financeiro/categorias/{id_categoria}': {'delete': operacao('Desativar categoria', GESTAO_ESCOPO + 'Preserva lançamentos históricos.')},
    '/gestao/financeiro/lancamentos': {
        'get': operacao('Histórico financeiro local', GESTAO_ESCOPO + GESTAO_PERIODO + 'Reúne lançamentos manuais e recebimentos de atendimentos sem contar seus espelhos duas vezes.'),
        'post': operacao('Registrar receita ou despesa', GESTAO_ESCOPO + 'Body {tipo: entrada|saida, descricao, valor, categoria_id?, vencimento, status: pendente|pago|cancelado, data_pagamento?}. Pago exige data não futura.')},
    '/gestao/financeiro/lancamentos/{id_lancamento}': {'put': operacao('Editar lançamento manual', GESTAO_ESCOPO + 'Mesmo body da criação. Despesa vinculada ao pagamento de comissão é imutável.')},
    '/gestao/financeiro/resumo': {'get': operacao('Caixa e comparação financeira', GESTAO_ESCOPO + GESTAO_PERIODO + 'Query agrupamento=dia|semana|mes. Receitas/despesas pagas e resultado, pendências, série e comparação com período anterior de igual duração. Base anterior zero retorna variação nula.')},
    '/gestao/agendamentos/{id_agendamento}/recebimentos': {
        'get': operacao('Consultar recebido e saldo', GESTAO_ESCOPO + 'Preço histórico, pagamentos confirmados locais/legados e saldo restante.'),
        'post': operacao('Registrar recebimento dividido', GESTAO_ESCOPO + 'Body {pagamentos:[{forma: dinheiro|cartao|pix_manual,valor}], data_pagamento?, observacao?, chave_idempotencia?}. Cartão é registro de máquina física; Pix manual é confirmação externa. Nenhum provedor é chamado. Rejeita exceder saldo, falta e cancelamento; 1 a 10 parcelas por operação. Repetição com mesma chave/corpo não duplica.')},
    '/gestao/comissoes/pagamentos': {
        'get': operacao('Comissões devidas e pagas', GESTAO_ESCOPO + GESTAO_PERIODO + 'Período opcional pela data do atendimento; inclui saldos e histórico de pagamentos manuais.'),
        'post': operacao('Registrar pagamento manual de comissão', GESTAO_ESCOPO + 'Body {id_agendamento, valor, data_pagamento?, observacao?, chave_idempotencia?}. Exige atendimento concluído e comissão histórica. Aceita pagamento parcial até saldo devido; cria despesa local na mesma transação. Não transfere dinheiro.')},
})


from docs_contracts import complementar_contratos
from image_docs import complementar_imagens

complementar_contratos(OPENAPI, operacao)
complementar_imagens(OPENAPI)


def contrato_atual():
    """Publica somente caminhos/métodos registrados, com os parâmetros reais."""
    documento = deepcopy(OPENAPI)
    caminhos = {}
    for regra in app.url_map.iter_rules():
        caminho = re.sub(r'<(?:\w+:)?([^>]+)>', r'{\1}', regra.rule)
        modelo = re.sub(r'\{[^}]+\}', '{}', caminho)
        fonte = next((valor for rota, valor in OPENAPI['paths'].items()
                      if re.sub(r'\{[^}]+\}', '{}', rota) == modelo), {})
        operacoes = caminhos.setdefault(caminho, {})
        for metodo in sorted(regra.methods - {'HEAD', 'OPTIONS'}):
            contrato = fonte.get(metodo.lower())
            if not contrato:
                # O catálogo Help continua descrevendo handlers novos; o teste de
                # cobertura exige contrato explícito antes de publicar uma rota.
                continue
            contrato = deepcopy(contrato)
            parametros = [p for p in contrato.get('parameters', []) if p.get('in') != 'path']
            for nome, conversor in regra._converters.items():
                existente = next((p for p in contrato.get('parameters', [])
                                  if p.get('in') == 'path' and p['name'] == nome), {})
                parametros.append({'name': nome, 'in': 'path', 'required': True,
                                   'schema': {**existente.get('schema', {}), 'type': 'integer' if conversor.__class__.__name__ == 'IntegerConverter' else 'string'}})
            if parametros:
                contrato['parameters'] = parametros
            sufixo = hashlib.sha256(caminho.encode()).hexdigest()[:12]
            contrato['operationId'] = regra.endpoint + '_' + metodo.lower() + '_' + sufixo
            operacoes[metodo.lower()] = contrato
    documento['paths'] = caminhos
    # Relativo à URL do JSON: resolve /api no proxy e / no backend direto.
    documento['servers'] = [{'url': '.', 'description': 'Backend na mesma origem do contrato'}]
    return documento


def _resposta_privada(resposta, status=200):
    resposta = make_response(resposta, status)
    resposta.headers['Cache-Control'] = 'private, no-store'
    resposta.headers['Vary'] = 'Cookie, Authorization'
    resposta.headers['X-Content-Type-Options'] = 'nosniff'
    return resposta


def _administrador():
    usuario = decodificar_token()
    if not usuario:
        return _resposta_privada(jsonify(mensagem={'informacao': 'Faça login como administrador para acessar a documentação.', 'tipo': 'erro'}), 401)
    if usuario.get('tipo') != 0:
        return _resposta_privada(jsonify(mensagem={'informacao': 'Documentação exclusiva do administrador.', 'tipo': 'erro'}), 403)
    return None


@app.route('/openapi.json', methods=['GET'])
def openapi_json():
    """Contrato consumível por Swagger, Postman e outras ferramentas."""
    bloqueio = _administrador()
    if bloqueio is not None:
        return bloqueio
    return _resposta_privada(jsonify(contrato_atual()))


@app.route('/docs', methods=['GET'])
def documentacao_api():
    """Interface interativa equivalente ao `/docs` oferecido pelo FastAPI."""
    bloqueio = _administrador()
    if bloqueio is not None:
        return bloqueio
    return _resposta_privada(render_template_string('''
<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cortaê API Docs</title><link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="swagger-ui"></div><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script><script>
const prefix = location.pathname.replace(/\\/docs\\/?$/, '');
fetch(prefix+'/openapi.json',{credentials:'include',cache:'no-store'})
.then(async response=>{if(!response.ok)throw new Error('Entre novamente com uma conta de administrador.');return response.json();})
.then(spec=>{spec.servers=[{url:prefix||'/'}];SwaggerUIBundle({spec,dom_id:'#swagger-ui',persistAuthorization:false,
withCredentials:true,filter:true,requestInterceptor:(req)=>{req.credentials='include';return req;}});})
.catch(error=>{document.getElementById('swagger-ui').textContent=error.message;});
</script></body></html>
'''))
