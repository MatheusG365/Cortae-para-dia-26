"""Guias de requisições compartilhados pelo Help e OpenAPI, sem I/O de negócio."""
from copy import deepcopy
import json
import re


GUIAS = [
    {
        'id': 'logs', 'titulo': 'Logs e auditoria das alterações',
        'descricao': 'Como uma operação gera auditoria e como o administrador consulta o histórico.',
        'etapas': [
            'A autenticação identifica o usuário pelo cookie web ou Bearer do aplicativo. Login não é a mesma coisa que log de auditoria.',
            'Handlers instrumentados chamam capturar_registro, registrar_registro ou registrar_log. Não existe um POST público para o cliente escrever logs, nem registro automático de todo GET.',
            'O backend compara antes/depois e grava uma linha por campo alterado; UPDATE sem mudança não gera linha. Guarda ação, tabela, registro, usuário, campo, valores e data/hora.',
            'Auditoria usa conexão própria ao banco LOG_DB e tabela LOG_ALTERACAO, com commit independente do banco principal. Não há transação distribuída garantindo atomicidade entre os dois bancos.',
            'Campos sensíveis são mascarados na gravação e na consulta. O IP considera X-Forwarded-For, X-Real-IP e endereço remoto; cabe ao proxy confiável controlar os cabeçalhos recebidos.',
            'O ADM abre /gestao?aba=logs no site. Proprietários, clientes e profissionais não podem consultar /gestao/logs; o app não tem painel ADM.',
        ],
        'diagnostico': [
            'LOG_OBRIGATORIO=false: falta de usuário identificado ou falha de auditoria registra aviso/erro no servidor e retorna zero linhas; a operação pode continuar.',
            'LOG_OBRIGATORIO=true: a falha é propagada ao chamador. Algumas operações já confirmam o banco principal antes da auditoria; erro de log não prova que o negócio foi desfeito.',
            'Se não houver registros, confira filtros, instrumentação do handler e disponibilidade do banco de log. A inicialização não cria a tabela automaticamente.',
        ],
        'requisicoes': [
            {'metodo': 'GET', 'rota': '/gestao/logs',
             'entrada': 'Query: pagina ou page, limite (até 100), inicio/fim, acao, tabela, usuario e busca. Exclusivo ADM.',
             'saida': 'JSON com logs, pagina, limite, total e paginas; valores sensíveis ocultados.'},
        ],
    },
    {
        'id': 'visagismo', 'titulo': 'Visagismo: foto, análise e simulação',
        'descricao': 'A análise recomenda um corte do catálogo; a simulação de imagem é uma solicitação separada.',
        'etapas': [
            'Site e app consultam os serviços e os cortes compatíveis com a barbearia. O cliente pode escolher catálogo, decidir na hora ou deixar o profissional escolher, sem obrigar o uso de IA.',
            'A análise recebe multipart/form-data com imagem, id_barbearia e ids_servicos. O backend valida autenticação, serviços, catálogo e o conteúdo real da foto.',
            'A imagem é otimizada para WebP e enviada ao Drive privado. A API usa a foto e o catálogo na análise OpenAI Responses, exigindo resposta estruturada com exatamente um ID de corte permitido.',
            'O backend salva a sessão VISAGISMO_SESSAO vinculada ao cliente, salão e serviços; devolve id_visagismo, foto_url, características e recomendação. Não inventa uma recomendação de sucesso se a IA falhar.',
            'Salvar foto sem análise permite uma sessão manual. Simular é outra requisição e pode consumir créditos: verifica dono da sessão, corte compatível, cor e alvo autorizados pelos serviços antes de chamar a geração de imagem.',
            'Fotos e resultados são lidos por URLs da API com controle de acesso. IDs e credenciais do Drive/OpenAI permanecem no servidor.',
        ],
        'diagnostico': [
            'GET /visagismo/status informa disponibilidade e modelos configurados, sem devolver a chave. Configuração ausente pode retornar 503 na análise; falha da IA pode retornar 502.',
            'Sessão de outro cliente, corte incompatível ou análise antiga pode ser recusada. Não repita análise/simulação automaticamente; são chamadas externas que podem gerar custo.',
        ],
        'requisicoes': [
            {'metodo': 'GET', 'rota': '/visagismo/cortes', 'entrada': 'Filtros de catálogo e serviços conforme o contrato da rota.', 'saida': 'Cortes ativos e compatíveis para a seleção.'},
            {'metodo': 'POST', 'rota': '/visagismo/analisar', 'entrada': 'Multipart; não enviar JSON ou caminho local no lugar dos bytes da imagem.',
             'corpo': {'id_barbearia': 17, 'ids_servicos': '[1]', 'imagem': '<arquivo selecionado pelo usuário>'},
             'saida': 'id_visagismo, foto_url, análise e uma recomendação de corte cadastrado.'},
            {'metodo': 'POST', 'rota': '/visagismo/salvar-foto', 'entrada': 'Multipart com imagem, id_barbearia e ids_servicos.', 'saida': 'Sessão manual e foto_url, sem executar análise por IA.'},
            {'metodo': 'POST', 'rota': '/visagismo/{id_visagismo}/simular', 'entrada': 'JSON com escolha compatível com a sessão e os serviços.',
             'corpo': {'id_corte': 1}, 'saida': 'Resultado da simulação e URL privada da imagem gerada. Cor é opcional; quando enviada, precisa ser um nome ou hexadecimal válido, com alvo autorizado.'},
        ],
    },
    {
        'id': 'agendamento', 'titulo': 'Agendamento: disponibilidade, resumo e reserva',
        'descricao': 'A consulta de horários é informativa; a reserva exige nova validação dentro da transação.',
        'etapas': [
            'Escolha barbearia e serviços; consulte a equipe habilitada. Uma resposta válida sem profissionais permite consultar a agenda do salão sem profissional definido. Falha ao carregar a equipe não equivale a equipe vazia.',
            'Consulte horários por data, serviços e profissional opcional. O backend considera duração, expediente, bloqueios e conflitos; o servidor permanece responsável pela disponibilidade real.',
            'Solicite /agendamentos/resumo para obter preços, taxa e confirmacao_resumo. O cliente não decide o preço enviando um total arbitrário.',
            'Consulte /termos-uso. Quando publicados, registre aceite explícito da versão atual; rascunho não exige aceite. Mudanças de preços ou termos exigem novo resumo/aceite.',
            'Envie a reserva com confirmacao_resumo. O backend trava o salão e revalida cliente, equipe, serviços, horário, conflito e escolha do corte; salva agendamento, preços históricos e dados financeiros relacionados.',
            'Uma reserva não é pagamento. Remarcação e cancelamento usam rotas próprias, validam escopo e prazos. A lista de espera avisa por e-mail quando houver liberação; o aviso não reserva o horário.',
            'No mobile, confirmar outra data limpa a seleção anterior; cancelar o calendário preserva data, horário e resumo. Essa correção vale também para reagendamento.',
        ],
        'diagnostico': [
            '409 pode indicar conflito de horário ou resumo desatualizado; atualize disponibilidade e resumo. 428 indica aceite exigido pelas regras publicadas.',
            'Não repita automaticamente POST /agendamentos após resposta incerta: consulte os agendamentos do cliente antes de tentar novamente.',
        ],
        'requisicoes': [
            {'metodo': 'GET', 'rota': '/barbearias/{id_barbearia}/funcionarios', 'entrada': 'Query servicos com os IDs selecionados.', 'saida': 'Profissionais habilitados para os serviços.'},
            {'metodo': 'GET', 'rota': '/agendamentos/horarios', 'entrada': 'Query id_barbearia, ids_servicos, data (AAAA-MM-DD) e id_funcionario opcional.', 'saida': 'Horários, disponibilidade e duração.'},
            {'metodo': 'POST', 'rota': '/agendamentos/resumo', 'entrada': 'JSON da seleção; o backend calcula os valores.',
             'corpo': {'id_barbearia': 17, 'ids_servicos': [1], 'id_funcionario': None}, 'saida': 'resumo com valores, termos_versao e confirmacao_resumo.'},
            {'metodo': 'POST', 'rota': '/termos-uso/aceite', 'entrada': 'Somente após leitura e ação explícita do usuário.',
             'corpo': {'versao': '<versão publicada retornada pela API>', 'aceito': True}, 'saida': 'Registro de aceite da versão informada.'},
            {'metodo': 'POST', 'rota': '/agendamentos', 'entrada': 'Exemplo de cliente decidindo o corte no atendimento; data/IDs devem existir e estar disponíveis.',
             'corpo': {'id_barbearia': 17, 'ids_servicos': [1], 'id_funcionario': None, 'data': '<AAAA-MM-DD futuro>', 'horario': '14:00', 'escolha_corte': 'na_hora', 'confirmacao_resumo': '<retornado pelo resumo>'},
             'saida': 'Agendamento criado com status agendado; não confirma pagamento.'},
        ],
    },
    {
        'id': 'compras', 'titulo': 'Compras: carrinho, pedido e pagamento',
        'descricao': 'Cada barbearia recebe seu próprio pedido; estoque, cupom, frete e valores são conferidos pelo backend.',
        'etapas': [
            'O cliente autenticado adiciona produto/variação ao carrinho. Quantidades e estoque são validados; um produto com variações exige a seleção correta.',
            'O checkout escolhe retirada ou entrega. Para entrega, complete o endereço e obtenha uma cotação. CEP preenchido não equivale a frete calculado.',
            'Solicite o resumo com loja, endereço, retirada/id_cotacao e cupom. O servidor confere promoção, variação, cupom da própria loja e cotação; devolve total, taxa e confirmacao_resumo.',
            'Após o aceite exigível, crie o pedido com confirmacao_resumo e chave_idempotencia. A mesma chave com o mesmo conteúdo recupera o pedido; a mesma chave com conteúdo diferente é conflito.',
            'A criação reserva estoque/uso do cupom e grava snapshots dos itens, custos, preços e endereço. Editar produto ou endereço salvo depois não reescreve o pedido antigo.',
            'Somente uma ação explícita solicita a cobrança na Arkhé. As credenciais são resolvidas pela barbearia no servidor; consultar pagamento atualiza o estado conforme a resposta do provedor.',
            'Criar pedido, gerar cobrança e pagar são estados diferentes. Cancelamento permitido restaura reservas uma vez; pedidos com cobrança ou pagamento exigem conciliação antes do cancelamento.',
        ],
        'diagnostico': [
            '409: estoque, resumo, cupom ou cotação pode ter mudado; confira a mensagem e refaça a conferência. 428: aceite pendente quando exigido.',
            'HTTP 5xx da Arkhé não confirma cobrança nem pagamento. A criação não é repetida automaticamente; confira cobranças existentes antes de tentar de novo.',
            'ARKHEPIX: é código interno Arkhé; renderizar seu QR não o transforma em Pix bancário interoperável.',
        ],
        'requisicoes': [
            {'metodo': 'GET', 'rota': '/marketplace/carrinho', 'entrada': 'Sessão do próprio cliente.', 'saida': 'Itens e grupos por barbearia.'},
            {'metodo': 'POST', 'rota': '/marketplace/pedidos/resumo', 'entrada': 'id_barbearia, endereco, retirada, id_cotacao quando entrega e cupom opcional.', 'saida': 'resumo confirmado pelo servidor e confirmacao_resumo.'},
            {'metodo': 'POST', 'rota': '/marketplace/pedidos', 'entrada': 'Os mesmos campos do resumo, mais confirmacao_resumo e chave_idempotencia. Não reutilize a chave para outra compra.', 'saida': 'Pedido aguardando_pagamento; estoque e cupom reservados.'},
            {'metodo': 'POST', 'rota': '/marketplace/pedidos/{id_pedido}/pix', 'entrada': 'Ação explícita do dono do pedido; valor vem do pedido, não do navegador.', 'saida': 'Cobrança ou cobrança existente, código recebido do provedor e status.'},
            {'metodo': 'GET', 'rota': '/marketplace/pedidos/{id_pedido}/pagamento', 'entrada': 'ID do pedido do cliente autenticado.', 'saida': 'Pagamento consultado e estado atualizado; consulta pode acessar a Arkhé e gravar a conciliação.'},
        ],
    },
    {
        'id': 'entregas', 'titulo': 'Entregas e API Melhor Envio',
        'descricao': 'Cotação, emissão de etiqueta e rastreio têm permissões e efeitos distintos.',
        'etapas': [
            'A barbearia cadastra o remetente, com endereço de origem. O token, o ambiente sandbox/produção e o contato técnico Melhor Envio são configuração exclusiva do servidor.',
            'POST /marketplace/frete lê remetente e carrinho. O backend envia à rota calculate do Melhor Envio os CEPs, dimensões, peso, quantidade e valor dos produtos.',
            'As cotações aceitas recebem id_cotacao local e expiram em 15 minutos. A cotação fica vinculada ao cliente, à loja, ao CEP e ao hash do carrinho/remetente; mudanças exigem nova cotação.',
            'Criar cotação ou pedido não compra frete nem gera etiqueta. O cliente escolhe uma cotação válida ou retirada gratuita no estabelecimento.',
            'Emissão de etiqueta exige MELHOR_ENVIO_EMITIR_ETIQUETAS habilitado, permissões da conta, pedido pago e confirmação de custo na compra. As etapas preparar, comprar e gerar são separadas; compra consome saldo.',
            'A integração prevê até três etiquetas operacionais simultâneas; isso não significa três fretes gratuitos. Estados incertos exigem conferência manual antes de repetir uma etapa financeira.',
            'Um envio existente pode ser vinculado explicitamente. O backend consulta o rastreio e atualiza o pedido; validar que o ID existe não prova titularidade remota, declarada pelo responsável pelo vínculo.',
        ],
        'diagnostico': [
            'Sem remetente, token ou contato técnico válido, a cotação pode retornar 503. Falha do provedor pode retornar 502; seu corpo sensível não é repassado ao cliente.',
            'Emissão desabilitada retorna 403. Rastreio não compra etiqueta, mas sua rota POST atualiza os dados locais da entrega.',
        ],
        'requisicoes': [
            {'metodo': 'PUT', 'rota': '/gestao/marketplace/remetente', 'entrada': 'Dados completos do remetente, restritos à própria loja; ADM informa o escopo autorizado.', 'saida': 'Remetente salvo e indicadores de integração; nunca retorna o token.'},
            {'metodo': 'POST', 'rota': '/marketplace/frete', 'entrada': 'Carrinho válido e remetente configurado.',
             'corpo': {'id_barbearia': 17, 'cep': '01310930'}, 'saida': 'cotacoes com id_cotacao, preço, prazo e expiração; retirada_disponivel.'},
            {'metodo': 'POST', 'rota': '/gestao/marketplace/pedidos/{id_pedido}/etiqueta', 'entrada': 'Proprietário/ADM, pedido pago; acao preparar, comprar ou gerar. Comprar exige confirmar_custo=true.', 'saida': 'Estado da emissão. Desabilitada por padrão; pode gerar custo real quando autorizada.'},
            {'metodo': 'POST', 'rota': '/gestao/marketplace/pedidos/{id_pedido}/vincular-envio', 'entrada': 'Vínculo explícito de envio externo, conforme os campos do contrato.', 'saida': 'Entrega vinculada após consulta ao provedor.'},
            {'metodo': 'POST', 'rota': '/gestao/marketplace/pedidos/{id_pedido}/rastreio', 'entrada': 'Pedido da loja com envio disponível para rastreio.', 'saida': 'Rastreio, entrega e pedido atualizados; não compra frete.'},
        ],
    },
    {
        'id': 'cep', 'titulo': 'CEP: preenchimento e endereços salvos',
        'descricao': 'ViaCEP preenche o endereço; número, complemento, frete e salvamento permanecem etapas próprias.',
        'etapas': [
            'No site, a consulta começa após um CEP válido de oito dígitos. O frontend chama a API Cortaê, não envia nome, documento, telefone ou token do cliente ao ViaCEP.',
            'A API valida o CEP e consulta o host HTTPS fixo ViaCEP, sem redirecionamentos, credenciais herdadas ou cookies; limites de tempo e de resposta impedem esperas ou conteúdo sem limite.',
            'A resposta é validada e normalizada em cep, logradouro, bairro, cidade e uf. Há cache em memória de até 256 resultados por 600 segundos; não é cadastro do cliente.',
            'O formulário preenche rua, bairro, cidade e UF. Número e complemento são manuais; alguns CEPs não possuem rua/bairro e esses campos precisam ser completados.',
            'Endereços salvos pertencem ao cliente no Firebird. Listar carrega o padrão; criar e editar exigem ação explícita. Alterar campos apenas para uma compra não atualiza o endereço salvo automaticamente.',
            'Novo endereço usa POST; edição usa PUT com ID do próprio cliente. Pode haver endereço padrão, e a compra grava seu próprio snapshot. Trocar CEP/endereço invalida a conferência de entrega no checkout do site.',
            'O remetente da barbearia possui consulta de CEP própria e salvamento separado. No app atual, checkout/remetente recebem endereço manualmente; não há interface de busca automática por CEP ou seleção de endereços salvos equivalente à do site.',
        ],
        'diagnostico': [
            '400: formato inválido. 404: CEP não encontrado. 503: ViaCEP indisponível ou resposta inválida; o usuário pode completar os campos manualmente.',
            'A consulta de CEP não garante entrega, não calcula preço de frete, não valida CPF/CNPJ nem salva endereço por conta própria.',
        ],
        'requisicoes': [
            {'metodo': 'GET', 'rota': '/marketplace/cep/{postal_code}', 'entrada': 'Cliente autenticado; CEP 01310930 ou 01310-930, sem dados pessoais adicionais.', 'saida': 'endereco com cep, logradouro, bairro, cidade e uf.'},
            {'metodo': 'GET', 'rota': '/gestao/marketplace/cep/{postal_code}', 'entrada': 'Proprietário/ADM no escopo da loja.', 'saida': 'Os mesmos campos para preencher o remetente.'},
            {'metodo': 'GET', 'rota': '/marketplace/enderecos', 'entrada': 'Sessão do próprio cliente.', 'saida': 'Endereços do cliente, incluindo indicação de padrão.'},
            {'metodo': 'POST', 'rota': '/marketplace/enderecos', 'entrada': 'JSON com apelido, padrao e endereco completo (contato, documento e endereço).', 'saida': 'Endereço criado e seu id_endereco; não cria pedido.'},
            {'metodo': 'PUT', 'rota': '/marketplace/enderecos/{id_endereco}', 'entrada': 'Mesmo formato do cadastro; o ID precisa pertencer ao cliente autenticado.', 'saida': 'Endereço atualizado; pedidos anteriores preservam o snapshot.'},
        ],
    },
]


def _normalizar(rota):
    return re.sub(r'<(?:\w+:)?([^>]+)>', r'{\1}', rota)


def catalogo_requisicoes(backend):
    guias = deepcopy(GUIAS)
    for guia in guias:
        vinculadas = {}
        for requisicao in guia['requisicoes']:
            rota = next((r for r in backend if _normalizar(r['rota']) == requisicao['rota']
                         and requisicao['metodo'] in r['metodos']), None)
            if rota:
                requisicao['api_id'] = rota['id']
                vinculadas[rota['id']] = {k: rota[k] for k in ('id', 'rota', 'titulo', 'metodos')}
        guia['apis'] = list(vinculadas.values())
    return {'titulo': 'Como as requisições percorrem o sistema', 'guias': guias,
            'observacoes': [
                'Conteúdo exclusivo do ADM no site. Abrir um guia ou sua documentação não executa a requisição.',
                'Exemplos são ilustrativos; IDs, datas e confirmações devem vir da sessão e das respostas reais. Não contêm credenciais.',
                'Site usa cookie HttpOnly; app usa Bearer recebido no login mobile. O servidor revalida perfil e escopo em cada operação protegida.',
            ]}


def complementar_requisicoes(documento):
    documento['x-cortae-fluxos'] = deepcopy(GUIAS)
    texto = ['\n\n## Guias de requisições',
             'Exemplos ilustrativos e sem credenciais. A leitura não executa operações. Consulte também os guias no Help exclusivo do ADM.']
    for guia in GUIAS:
        texto.extend(['\n### ' + guia['titulo'], guia['descricao']])
        texto.extend(f'{n}. {etapa}' for n, etapa in enumerate(guia['etapas'], 1))
        for req in guia['requisicoes']:
            texto.extend(['\n**' + req['metodo'] + ' ' + req['rota'] + '**',
                          'Entrada: ' + req['entrada'], 'Saída: ' + req['saida']])
            if 'corpo' in req:
                texto.append('```json\n' + json.dumps(req['corpo'], ensure_ascii=False, indent=2) + '\n```')
            operacao = documento['paths'].get(req['rota'], {}).get(req['metodo'].lower())
            if operacao is not None:
                operacao.setdefault('x-cortae-fluxos', []).append(guia['id'])
        texto.extend('\nDiagnóstico: ' + item for item in guia['diagnostico'])
    documento['info']['description'] += '\n'.join(texto)
