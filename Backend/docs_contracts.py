"""Contratos dos módulos comerciais e da documentação restrita ao administrador.

As rotas de negócio mantêm suas próprias permissões. A publicação do contrato
e do código é exclusiva de administradores, inclusive para operações públicas.
"""


def objeto(campos, obrigatorios=()):
    return {'type': 'object', 'properties': campos, 'required': list(obrigatorios)}


TEXTO = {'type': 'string'}
INTEIRO = {'type': 'integer', 'minimum': 1}
BOOLEANO = {'type': 'boolean'}
DINHEIRO = {'type': 'number', 'minimum': 0}
DATA = {'type': 'string', 'format': 'date'}
ATIVO = objeto({'ativo': BOOLEANO}, ['ativo'])
AVALIACAO = objeto({'nota': {'type': 'integer', 'minimum': 1, 'maximum': 5}, 'comentario': TEXTO}, ['nota'])
ESTOQUE = objeto({'quantidade': INTEIRO, 'observacao': TEXTO, 'chave_idempotencia': TEXTO}, ['quantidade', 'chave_idempotencia'])
ENDERECO = objeto({campo: TEXTO for campo in ('nome', 'email', 'telefone', 'documento', 'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'inscricao_estadual')},
                 ['nome', 'email', 'telefone', 'documento', 'cep', 'logradouro', 'numero', 'bairro', 'cidade', 'uf'])
PRODUTO = objeto({
    **{c: TEXTO for c in ('nome', 'descricao', 'detalhes', 'categoria', 'marca')},
    'preco': DINHEIRO, 'estoque': {'type': 'integer', 'minimum': 0, 'maximum': 999999},
    'estoque_minimo': {'type': 'integer', 'minimum': 0}, 'ativo': BOOLEANO,
    **{c: {'type': 'number', 'exclusiveMinimum': True, 'minimum': 0, 'maximum': 1000}
       for c in ('peso', 'largura', 'altura', 'comprimento')},
    'imagens': {'type': 'array', 'maxItems': 8, 'items': {'type': 'string', 'format': 'uri-reference', 'description': 'URL HTTPS legada ou referência /uploads/marketplace/<identificador>.webp já pertencente à própria loja.'}},
    'id_fornecedor': {'type': 'integer', 'nullable': True},
    'custo_compra': {**DINHEIRO, 'nullable': True},
    'promocao_preco': {**DINHEIRO, 'nullable': True},
    'promocao_inicio': {**DATA, 'nullable': True}, 'promocao_fim': {**DATA, 'nullable': True},
    'lancamento_ate': {**DATA, 'nullable': True},
}, ['nome', 'descricao', 'preco', 'peso', 'largura', 'altura', 'comprimento'])
FORNECEDOR = objeto({**{c: TEXTO for c in ('nome', 'documento', 'email', 'telefone', 'observacoes')}, 'ativo': BOOLEANO}, ['nome'])
VARIACAO = objeto({**{c: TEXTO for c in ('nome', 'sku', 'tamanho', 'cor', 'volume')},
                   'preco': DINHEIRO, 'custo_compra': {**DINHEIRO, 'nullable': True},
                   'ativo': BOOLEANO, 'estoque': {'type': 'integer', 'minimum': 0}}, ['nome', 'preco'])
CUPOM = objeto({'codigo': TEXTO, 'tipo': {'type': 'string', 'enum': ['fixo', 'percentual']},
                'valor': DINHEIRO, 'inicio': DATA, 'fim': DATA, 'limite_usos': INTEIRO, 'ativo': BOOLEANO},
               ['codigo', 'tipo', 'valor', 'inicio', 'fim', 'limite_usos'])
META = objeto({'id_funcionario': INTEIRO, 'tipo': {'type': 'string', 'enum': ['atendimentos', 'faturamento']},
               'alvo': DINHEIRO, 'inicio': DATA, 'fim': DATA, 'ativo': BOOLEANO}, ['id_funcionario', 'tipo', 'alvo'])
CHECKOUT = objeto({'id_barbearia': INTEIRO, 'endereco': ENDERECO, 'retirada': BOOLEANO,
                   'id_cotacao': TEXTO, 'cupom': TEXTO}, ['id_barbearia', 'endereco'])
DONO = 'Proprietário (tipo 2) da loja ou ADM (tipo 0); ADM informa id_barbearia na query. Nenhum acesso a outra loja. '
CLIENTE = 'Cliente ativo (tipo 1); somente seus próprios dados. '
PERIODO = 'Query inicio/fim em AAAA-MM-DD. '


def complementar_contratos(documento, operacao):
    caminhos = documento['paths']

    def adicionar(rota, metodo, titulo, descricao, corpo=None, publico=False, query=(), resposta=None):
        contrato = operacao(titulo, descricao, corpo, autenticada=not publico)
        if query:
            contrato['parameters'] = [{'in': 'query', 'name': c, 'required': False, 'schema': s}
                                      for c, s in query]
        if resposta:
            contrato['responses'] = {**contrato['responses'], '200': resposta}
        caminhos.setdefault(rota, {})[metodo] = contrato

    def owner(rota, metodo, titulo, descricao='', corpo=None, query=(), resposta=None):
        adicionar(rota, metodo, titulo, DONO+descricao, corpo,
                  query=[('id_barbearia', INTEIRO), *query], resposta=resposta)

    # Mobile-safe salon operations deliberately do not use owner(): these
    # handlers accept only role 2 and derive the salon from the session.
    salao_proprio = ('Exclusivo da própria barbearia (tipo 2), ativa e com e-mail confirmado. '
                    'O estabelecimento é obtido da sessão; não há seleção de outra conta. '
                    'ADM, cliente e profissional não têm permissão. ')
    cores = ('cor_primaria', 'cor_secundaria', 'cor_terciaria',
             'cor_texto_primario', 'cor_texto_secundario')
    campos_perfil = {
        **{campo: {'type': 'string', 'pattern': '^#[0-9a-fA-F]{6}$', 'maxLength': 7} for campo in cores},
        'historia': {'type': 'string', 'maxLength': 1000},
        'localizacao': {'type': 'string', 'maxLength': 100},
        'contato_telefone': {'type': 'string', 'maxLength': 20,
                             'description': 'Vazio ou telefone com DDD; remove formatação e exige 10 ou 11 dígitos.'},
        'contato_email': {'type': 'string', 'maxLength': 100,
                          'description': 'Vazio ou endereço de e-mail válido.'},
        'instagram': {'type': 'string', 'maxLength': 100},
    }
    perfil_patch = {**objeto(campos_perfil), 'minProperties': 1, 'additionalProperties': False}
    perfil_saida = {**objeto({'id_personalizacao': INTEIRO, 'id_usuario': INTEIRO,
                             **{campo: TEXTO for campo in campos_perfil}}),
                    'nullable': True}
    resposta_perfil = {'description': 'Estado do perfil público da própria barbearia; personalizacao é null quando ausente.',
                      'content': {'application/json': {'schema': objeto(
                          {'personalizado': BOOLEANO, 'personalizacao': perfil_saida},
                          ['personalizado', 'personalizacao'])}}}
    adicionar('/barbearia/perfil', 'get', 'Consultar próprio perfil público',
              salao_proprio+'Retorna somente cinco cores, apresentação e contatos públicos; não expõe chave Pix, '
              'credenciais Arkhé, dados bancários, fotos ou configuração da equipe.', resposta=resposta_perfil)
    adicionar('/barbearia/perfil', 'patch', 'Atualizar próprio perfil público',
              salao_proprio+'JSON parcial não vazio, somente os dez campos públicos documentados. Textos são aparados; '
              'cores exigem #RRGGBB. Cria o perfil com padrões quando ainda não existe ou altera só os campos enviados. '
              'Rejeita campos extras, inclusive credenciais de pagamento e equipe; preserva dados privados e vínculos existentes.',
              perfil_patch, resposta=resposta_perfil)

    ids_servicos = {'type': 'array', 'maxItems': 100, 'items': INTEIRO,
                    'description': 'Lista de serviços ativos da própria barbearia; vazia é válida. IDs repetidos são removidos.'}
    novo_profissional = {**objeto({
        'nome': {'type': 'string', 'minLength': 1, 'maxLength': 100},
        'descricao': {'type': 'string', 'maxLength': 500, 'default': ''},
        'email': {'type': 'string', 'format': 'email', 'maxLength': 150},
        'telefone': {'type': 'string', 'minLength': 1, 'maxLength': 20,
                     'description': 'DDD e telefone; remove formatação e exige 10 ou 11 dígitos.'},
        'comissao_percentual': {'type': 'number', 'minimum': 0, 'maximum': 100, 'default': 0,
                                'description': 'Percentual arredondado a duas casas decimais; booleano não é aceito.'},
        'ids_servicos': {**ids_servicos, 'default': []},
    }, ['nome', 'email', 'telefone']), 'additionalProperties': False}
    adicionar('/barbearia/funcionarios', 'post', 'Cadastrar profissional e enviar convite',
              salao_proprio+'Aceita somente os seis campos documentados. Cria profissional ativo, vínculos de serviços '
              'e uma conta exclusiva tipo 3 ainda inativa/não confirmada. E-mail já utilizado retorna 400; '
              'nunca vincula conta de outra pessoa. Convite de uso único expira em 48 horas e permite definir senha. '
              'O cadastro é confirmado antes do envio do e-mail: falha de envio retorna 201 com convite_email_enviado=false, '
              'sem desfazer o profissional. Retorna configuracao_pendente=true; configure turnos e preços separadamente. '
              'O perfil profissional usa o site e não o login mobile.', novo_profissional)
    cadastro = caminhos['/barbearia/funcionarios']['post']
    cadastro['responses'] = {codigo: cadastro['responses'][codigo] for codigo in ('201', '400', '401', '403', '500')}
    cadastro['responses']['201'] = {'description': 'Profissional cadastrado; confira o resultado do envio do convite.',
        'content': {'application/json': {'schema': objeto({
            'funcionario': objeto({'id_funcionario': INTEIRO, 'nome': TEXTO, 'ativo': BOOLEANO,
                                    'ids_servicos': ids_servicos}, ['id_funcionario', 'nome', 'ativo', 'ids_servicos']),
            'convite_email_enviado': BOOLEANO, 'configuracao_pendente': BOOLEANO,
            'mensagem': objeto({'informacao': TEXTO, 'tipo': TEXTO}),
        }, ['funcionario', 'convite_email_enviado', 'configuracao_pendente', 'mensagem'])}}}
    estado = {**ATIVO, 'additionalProperties': False}
    adicionar('/barbearia/funcionarios/{id_funcionario}/estado', 'patch', 'Ativar ou desativar próprio profissional',
              salao_proprio+'JSON contém somente ativo booleano. Profissional fora da própria equipe retorna 404. '
              'Desativação retorna 409 se houver agendamento futuro agendado ou confirmado; redistribua ou cancele antes. '
              'Preserva histórico, conta vinculada e configurações; atualiza a contagem de profissionais ativos. '
              'Reativação usa turnos e serviços existentes, sem emitir novo convite.', estado,
              resposta={'description': 'Estado atualizado do profissional.', 'content': {'application/json': {'schema': objeto({
                  'funcionario': objeto({'id_funcionario': INTEIRO, 'nome': TEXTO, 'ativo': BOOLEANO},
                                         ['id_funcionario', 'nome', 'ativo']),
                  'mensagem': objeto({'informacao': TEXTO, 'tipo': TEXTO}),
              }, ['funcionario', 'mensagem'])}}})
    adicionar('/barbearia/funcionarios/{id_funcionario}/servicos', 'put', 'Substituir serviços do próprio profissional',
              salao_proprio+'JSON contém somente ids_servicos, lista de até 100 IDs inteiros positivos. '
              'Profissional fora da equipe retorna 404; serviço inativo ou de outra barbearia retorna 400. '
              'A lista substitui os vínculos, pode ser vazia e é devolvida ordenada sem duplicatas. '
              'Mantém preços específicos já registrados e valores históricos de agendamentos; vínculos sem preço específico '
              'usam o preço padrão do serviço até configuração individual. Não altera turnos nem exclui serviços do catálogo.',
              {**objeto({'ids_servicos': ids_servicos}, ['ids_servicos']), 'additionalProperties': False},
              resposta={'description': 'Lista completa de serviços vinculados após a atualização.',
                        'content': {'application/json': {'schema': objeto({
                            'id_funcionario': INTEIRO, 'ids_servicos': ids_servicos,
                            'mensagem': objeto({'informacao': TEXTO, 'tipo': TEXTO}),
                        }, ['id_funcionario', 'ids_servicos', 'mensagem'])}}})
    for rota, metodos in (('/barbearia/perfil', ('get', 'patch')),
                          ('/barbearia/funcionarios/{id_funcionario}/estado', ('patch',)),
                          ('/barbearia/funcionarios/{id_funcionario}/servicos', ('put',))):
        for metodo in metodos:
            contrato = caminhos[rota][metodo]
            codigos = ('200', '400', '401', '403', '404', '409', '500') if rota.endswith('/estado') else (
                ('200', '400', '401', '403', '404', '500') if rota.endswith('/servicos') else
                ('200', '401', '403', '500') if metodo == 'get' else ('200', '400', '401', '403', '500'))
            contrato['responses'] = {codigo: contrato['responses'][codigo] for codigo in codigos}

    filtros = [('busca', TEXTO), ('categoria', TEXTO),
               ('ordem', {'type': 'string', 'enum': ['recentes', 'nome', 'preco_asc', 'preco_desc']}),
               ('destaque', {'type': 'string', 'enum': ['', 'promocoes', 'lancamentos']})]
    for rota, titulo, detalhe, query in (
        ('/marketplace/produtos', 'Catálogo geral de todas as lojas', 'Até 500 produtos ativos de estabelecimentos ativos e confirmados. Busca por nome ou marca; ordena pelo preço efetivo.', filtros+[('id_barbearia', INTEIRO)]),
        ('/marketplace/barbearias/{id_barbearia}', 'Produtos da loja do estabelecimento', 'Filtros nunca alteram a loja indicada no caminho. A loja React fica embutida em /estabelecimento?usuario=ID#loja-barbearia; a URL React antiga redireciona.', filtros),
        ('/marketplace/barbearias/{id_barbearia}/perfil', 'Apresentação pública e cores da loja', 'Lista somente apresentação comercial, cinco cores, serviços/profissionais ativos e horários. Não divulga Pix, credenciais, custos, login ou contatos privados dos funcionários.', []),
        ('/marketplace/produtos/{id_produto}', 'Detalhes, variações e avaliações do produto', 'Preço efetivo, preço original, promoção, lançamento, variações, avaliações e relacionados da mesma loja. Com sessão cliente inclui favorito, desejado e elegibilidade para avaliar. Custos e fornecedores são privados.', []),
    ):
        adicionar(rota, 'get', titulo, 'Público. '+detalhe, publico=True, query=query)

    owner('/gestao/marketplace/produtos', 'get', 'Produtos, custos e margem da loja', 'Inclui ativos e inativos; preco_cadastro é o preço original e margem_lucro_percentual usa o preço efetivo. Custo não informado resulta em margem nula.', query=[('busca', TEXTO)])
    for rota, metodo, titulo in (('/gestao/marketplace/produtos', 'post', 'Cadastrar produto'), ('/gestao/marketplace/produtos/{id_produto}', 'put', 'Editar produto e condições comerciais')):
        owner(rota, metodo, titulo, 'Preço positivo; peso em kg e dimensões em cm, positivos até 1000. Aceita application/json com imagens por URLs HTTPS legadas ou referências de upload já pertencentes à mesma loja. Para novas fotos use multipart/form-data com dados (objeto JSON serializado) e o campo repetido imagens (arquivos). Até oito fotos ao todo, somando URLs mantidas e novos arquivos. Cada arquivo deve ser imagem estática de até 10 MB; o backend valida, reduz e converte em WebP sem metadados, armazena no Drive privado e persiste referência no Firebird. Falta de configuração retorna 503; arquivo inválido 400 e limite excedido 413. Estoque inicial apenas na criação; depois use entradas de estoque. Promoção exige preço menor que o cadastro e datas inclusivas válidas. Fornecedor inativo pode permanecer em vínculo antigo, mas não aceita novo vínculo. Custo/fornecedor nunca aparecem nas respostas públicas.', PRODUTO)
        caminhos[rota][metodo]['requestBody']['content']['multipart/form-data'] = {
            'schema': objeto({
                'dados': {'type': 'string', 'description': 'Objeto JSON serializado com os mesmos campos do contrato application/json; imagens preserva as referências que permanecerão no produto.'},
                'imagens': {'type': 'array', 'maxItems': 8, 'items': {'type': 'string', 'format': 'binary'},
                            'description': 'Arquivos repetidos no campo imagens; até oito fotos somando referências de dados.imagens e arquivos novos. Até 10 MB por arquivo.'},
            }, ['dados'])}
    adicionar('/uploads/marketplace/{filename}', 'get', 'Exibir foto cadastrada do produto',
              'Público. Somente identificador opaco .webp registrado na área marketplace; entrega o conteúdo pelo proxy da API a partir da referência do Firebird e do Drive privado. Não aceita URL arbitrária nem revela o ID remoto ou credenciais.',
              publico=True, resposta={'description': 'Imagem WebP do produto.', 'content': {'image/webp': {'schema': {'type': 'string', 'format': 'binary'}}}})
    owner('/gestao/marketplace/produtos/{id_produto}/ativo', 'patch', 'Ativar/desativar produto', 'Preserva histórico e pedidos.', ATIVO)
    for rota, detalhe in (
        ('/gestao/marketplace/produtos/{id_produto}/estoque', 'Produtos com variações exigem entrada na variação correspondente.'),
        ('/gestao/marketplace/produtos/{id_produto}/variacoes/{id_variacao}/estoque', 'Movimenta somente esta variação, sem alterar as outras.'),
    ):
        owner(rota, 'get', 'Histórico de movimentações de estoque', detalhe)
        owner(rota, 'post', 'Adicionar estoque com idempotência', detalhe+' Quantidade positiva; limite 999999. Mesma chave e corpo não duplica; chave com dados distintos retorna 409.', ESTOQUE)

    for nome, schema, titulo, detalhe in (
        ('fornecedores', FORNECEDOR, 'fornecedor', 'Dados privados da loja; nome obrigatório e e-mail opcional válido. Desativação preserva associações antigas.'),
        ('cupons', CUPOM, 'cupom', 'Código exclusivo por loja. Valor positivo; percentual até 100. Validade inclusiva e limite positivo. Desconto incide em mercadorias já promocionais, nunca no frete, e preserva R$ 0,01. Uso reservado ao criar pedido e liberado somente no cancelamento permitido.'),
    ):
        base = '/gestao/marketplace/'+nome
        ident = '{id_fornecedor}' if nome == 'fornecedores' else '{id_cupom}'
        owner(base, 'get', 'Consultar '+nome, detalhe)
        owner(base, 'post', 'Cadastrar '+titulo, detalhe, schema)
        owner(base+'/'+ident, 'put', 'Editar '+titulo, detalhe, schema)
        owner(base+'/'+ident+'/ativo', 'patch', 'Ativar/desativar '+titulo, detalhe, ATIVO)

    base = '/gestao/marketplace/produtos/{id_produto}/variacoes'
    owner(base, 'get', 'Listar variações de produto', 'Preço original e efetivo, tamanho/cor/volume, SKU, estoque e custo privado da variação.')
    for rota, metodo, titulo in ((base, 'post', 'Cadastrar variação'), (base+'/{id_variacao}', 'put', 'Editar variação')):
        owner(rota, metodo, titulo, 'Preço próprio positivo e SKU único na loja quando informado. Estoque inicial somente na criação; preço promocional proporcional ao desconto do produto base. Produtos com variações exigem seleção no carrinho.', VARIACAO)
    owner(base+'/{id_variacao}/ativo', 'patch', 'Ativar/desativar variação', 'Histórico preservado.', ATIVO)

    for recurso, campo, titulo in (('favoritos', 'favorito', 'Favoritos'), ('lista-desejos', 'desejado', 'Lista de desejos')):
        adicionar('/marketplace/'+recurso, 'get', titulo+' do cliente', CLIENTE+'Produtos ativos salvos. Favoritos e desejos são listas independentes.')
        adicionar('/marketplace/'+recurso+'/{id_produto}', 'put', 'Salvar/remover '+campo, CLIENTE+'Operação idempotente. Para salvar, produto precisa estar disponível.', objeto({campo: BOOLEANO}, [campo]))
    adicionar('/marketplace/carrinho', 'get', 'Carrinho individual por estabelecimento', CLIENTE+'Agrupa itens por loja e distingue variações com chave_item; informa disponibilidade e preço atual.')
    adicionar('/marketplace/carrinho/{id_produto}', 'put', 'Alterar quantidade do carrinho', CLIENTE+'Quantidade zero remove somente a linha indicada; adicionar=true soma à existente. id_variacao é obrigatório quando houver variações; nenhuma quantidade pode superar o estoque.', objeto({'quantidade': {'type': 'integer', 'minimum': 0, 'maximum': 999999}, 'id_variacao': {'type': 'integer', 'nullable': True}, 'adicionar': BOOLEANO}, ['quantidade']))
    adicionar('/marketplace/produtos/{id_produto}/avaliacao', 'put', 'Avaliar produto recebido', CLIENTE+'Somente após pedido entregue contendo o produto. Nota inteira de 1 a 5, comentário até 1000 caracteres; atualiza a própria avaliação.', AVALIACAO)
    adicionar('/marketplace/frete', 'post', 'Cotar entrega pelo Melhor Envio', CLIENTE+'Carrinho da loja, CEP de oito dígitos e remetente configurado. Cotação válida por 15 minutos e vinculada ao cliente, carrinho/endereço/remetente. Não compra nem emite etiqueta; cliente paga o frete.', objeto({'id_barbearia': INTEIRO, 'cep': TEXTO}, ['id_barbearia', 'cep']))
    adicionar('/marketplace/cep/{postal_code}', 'get', 'Preencher endereço pelo CEP', CLIENTE+'ViaCEP gratuito, somente CEP enviado ao serviço. Oito dígitos ou formato 00000-000. Retorna logradouro, bairro, cidade e UF; número e complemento são informados pelo cliente. 400 inválido, 404 inexistente, 503 indisponível; preenchimento manual continua possível.')
    owner('/gestao/marketplace/cep/{postal_code}', 'get', 'Consultar CEP do remetente', 'Mesma consulta ViaCEP, com autenticação do estabelecimento ou administrador e validação da barbearia alvo.')
    adicionar('/marketplace/enderecos', 'get', 'Listar endereços de entrega salvos', CLIENTE+'Somente os endereços da conta autenticada, com apelido, padrão e dados de contato/entrega. Não usa armazenamento local do navegador.')
    endereco_salvo = objeto({'apelido': TEXTO, 'padrao': BOOLEANO, 'endereco': ENDERECO}, ['endereco'])
    adicionar('/marketplace/enderecos', 'post', 'Salvar novo endereço de entrega', CLIENTE+'Salvamento explícito. Primeiro endereço é padrão; padrao=true substitui o anterior. Não cria pedido nem cobrança.', endereco_salvo)
    adicionar('/marketplace/enderecos/{id_endereco}', 'put', 'Editar próprio endereço de entrega', CLIENTE+'Exige titularidade. Mantém um endereço padrão e preserva os endereços históricos dos pedidos já criados.', endereco_salvo)
    consulta_cep = objeto({campo: TEXTO for campo in ('cep', 'logradouro', 'bairro', 'cidade', 'uf')},
                         ['cep', 'logradouro', 'bairro', 'cidade', 'uf'])
    salvo = objeto({'id_endereco': INTEIRO, 'apelido': {**TEXTO, 'maxLength': 80},
                    'padrao': BOOLEANO, 'dados': ENDERECO}, ['id_endereco', 'apelido', 'padrao', 'dados'])
    def resposta_json(descricao, schema):
        return {'description': descricao, 'content': {'application/json': {'schema': schema}}}
    for rota in ('/marketplace/cep/{postal_code}', '/gestao/marketplace/cep/{postal_code}'):
        contrato_cep = caminhos[rota]['get']
        contrato_cep['parameters'] = [*contrato_cep.get('parameters', []),
            {'name': 'postal_code', 'in': 'path', 'required': True,
             'schema': {'type': 'string', 'pattern': '^[0-9]{5}-?[0-9]{3}$', 'example': '01001000'}}]
        contrato_cep['responses'] = {**contrato_cep['responses'], '200': resposta_json('Endereço postal; logradouro/bairro podem vir vazios em CEP genérico.', objeto({'endereco': consulta_cep}, ['endereco']))}
    # Cada contrato recebe sua própria coleção de respostas; os padrões são compartilhados.
    caminhos['/marketplace/enderecos']['get']['responses'] = {
        **caminhos['/marketplace/enderecos']['get']['responses'],
        '200': resposta_json('Endereços da conta autenticada, padrão primeiro.', objeto({'enderecos': {'type': 'array', 'items': salvo}}, ['enderecos']))}
    for rota, metodo, codigo in (('/marketplace/enderecos', 'post', '201'),
                                 ('/marketplace/enderecos/{id_endereco}', 'put', '200')):
        contrato_endereco = caminhos[rota][metodo]
        contrato_endereco['responses'] = {**contrato_endereco['responses'], codigo: resposta_json('Endereço salvo; dados normalizados e histórico de pedidos preservado.', objeto({'endereco': salvo}, ['endereco']))}
        if codigo == '201':
            contrato_endereco['responses'].pop('200', None)
    adicionar('/marketplace/pedidos/resumo', 'post', 'Conferir total e cupom no checkout', CLIENTE+'Endereço completo exigido inclusive na retirada. Entrega exige id_cotacao válido; retirada não cobra frete. Retorna resumo, assinatura e cupom/desconto conferidos. Mudança de carrinho/cupom/valor/endereço invalida confirmação.', CHECKOUT)
    pedido = objeto({**CHECKOUT['properties'], 'chave_idempotencia': TEXTO,
                     'confirmacao_resumo': TEXTO},
                    ['id_barbearia', 'endereco', 'chave_idempotencia'])
    adicionar('/marketplace/pedidos', 'post', 'Criar pedido e reservar estoque', CLIENTE+'Reserva estoque e uso de cupom na mesma transação, preserva preços/variações e custos privados históricos. Mesma chave/corpo retorna pedido anterior. confirmacao_resumo é obrigatória quando a taxa estiver ativa; se informada com taxa inativa também é validada. Exige aceites quando publicados. Chave de idempotência: 16 a 64 caracteres alfanuméricos, hífen ou sublinhado. Não gera cobrança automaticamente.', pedido)
    adicionar('/marketplace/pedidos', 'get', 'Histórico de compras', CLIENTE+'Lista seus pedidos em ordem decrescente de ID; sem filtros de consulta.')
    owner('/gestao/marketplace/pedidos', 'get', 'Pedidos da loja', 'Filtros status exato e busca por ID/nome do cliente.', query=[('status', TEXTO), ('busca', TEXTO)])
    adicionar('/marketplace/pedidos/{id_pedido}', 'get', 'Detalhes da própria compra', CLIENTE+'Itens, preços e endereço preservados; histórico, Pix e entrega. Não revela custos privados.')
    owner('/gestao/marketplace/pedidos/{id_pedido}', 'get', 'Detalhes do pedido da loja', 'Dados de atendimento do pedido e entrega; custos permanecem fora do payload público de pedidos.')
    adicionar('/marketplace/pedidos/{id_pedido}/cancelar', 'post', 'Cancelar pedido ainda sem cobrança', CLIENTE+'Só aguardando_pagamento com pagamento nao_criado. Restaura estoque/uso de cupom uma vez. Cobrança iniciada ou pagamento exige conciliação e não é cancelado/estornado por esta rota.')
    owner('/gestao/marketplace/pedidos/{id_pedido}/status', 'patch', 'Preparação e retirada do pedido', 'Exige pagamento confirmado. pago → separando; retirada: separando → pronto_retirada → entregue. Entrega por transportadora é confirmada pelo rastreio.', objeto({'status': {'type': 'string', 'enum': ['separando', 'pronto_retirada', 'entregue']}}, ['status']))
    adicionar('/marketplace/pedidos/{id_pedido}/pix', 'post', 'Criar Pix do pedido pela Arkhé', CLIENTE+'Usa o total histórico e a conta da loja, nunca valor informado pelo navegador. Não duplica cobrança existente; resultado incerto exige conciliação. Retorna 201 na criação, ou cobrança existente.')
    adicionar('/marketplace/pedidos/{id_pedido}/pagamento', 'get', 'Consultar e conciliar Pix do pedido', CLIENTE+'Confere identificador e valor retornados pela Arkhé antes de confirmar pagamento; não confirma só pela informação do cliente.')
    owner('/gestao/marketplace/remetente', 'get', 'Consultar remetente de entrega', 'Retorna endereço cadastrado e permissões/limites da integração.')
    owner('/gestao/marketplace/remetente', 'put', 'Configurar remetente de entrega', 'Endereço completo, CEP/telefone/documento/UF válidos; inscrição estadual necessária para emissão comercial.', ENDERECO)
    entrega = '/gestao/marketplace/pedidos/{id_pedido}'
    owner(entrega+'/etiqueta', 'get', 'Consultar estado e URL da etiqueta', 'Somente consulta; não compra nem emite.')
    owner(entrega+'/etiqueta', 'post', 'Operações de etiqueta desabilitadas por padrão', 'Retorna 403 enquanto MELHOR_ENVIO_EMITIR_ETIQUETAS=false. Se explicitamente habilitado: preparar exige nota fiscal de 44 dígitos; comprar exige confirmar_custo=true e controla três envios simultâneos; gerar exige compra confirmada. Estados incertos impedem repetição automática. Não confundir limite simultâneo com gratuidade.', objeto({'acao': {'type': 'string', 'enum': ['preparar', 'comprar', 'gerar']}, 'nota_fiscal': TEXTO, 'confirmar_custo': BOOLEANO}, ['acao']))
    owner(entrega+'/vincular-envio', 'post', 'Vincular envio externo autorizado', 'Exige pedido pago com entrega e sem emissão em andamento. UUID de envio exclusivo na plataforma; confirmar_vinculo=true declara responsabilidade pelo vínculo. Melhor Envio valida existência/estado, não titularidade remota. Não compra etiqueta.', objeto({'id_envio': {'type': 'string', 'format': 'uuid'}, 'confirmar_vinculo': BOOLEANO}, ['id_envio', 'confirmar_vinculo']))
    owner(entrega+'/rastreio', 'post', 'Atualizar rastreio pelo Melhor Envio', 'Exige envio vinculado/disponível. Confere ID/estado; somente estado delivered do provedor marca entrega concluída. Não cria frete.')
    queries = [('inicio', DATA), ('fim', DATA), ('agrupamento', {'type': 'string', 'enum': ['dia', 'mes']})]
    vendas = PERIODO+'Até dez anos. Seleção pela data de criação do pedido. Faturamento inclui somente pedidos pagos não cancelados; mercadorias líquidas separadas do frete. Ticket médio das mercadorias; custos históricos privados, descontos rateados em centavos. Custo ausente significa lucro não calculado, nunca zero.'
    owner('/gestao/marketplace/relatorios', 'get', 'Dashboard de vendas do marketplace', vendas, query=queries)
    owner('/gestao/marketplace/relatorios.csv', 'get', 'Exportar vendas por produto em CSV', vendas+' CSV UTF-8, separador ponto e vírgula; protege células contra fórmulas.', query=queries, resposta={'description': 'Arquivo de vendas por produto.', 'content': {'text/csv': {'schema': TEXTO}}})

    for metodo in ('get', 'put'):
        adicionar('/agendamentos/{id_agendamento}/avaliacao', metodo, 'Consultar avaliação e elegibilidade' if metodo == 'get' else 'Avaliar próprio atendimento concluído', 'Exclusivo cliente dono (tipo 1), inclusive para GET. PUT exige atendimento concluído e encerrado. Nota inteira 1 a 5 e comentário até 1000 caracteres; uma avaliação editável por atendimento. Equipe consulta avaliações pela rota /gestao/avaliacoes.', AVALIACAO if metodo == 'put' else None)
    owner('/gestao/ranking', 'get', 'Ranking dos profissionais', PERIODO+'Até 366 dias. Atendimentos concluídos encerrados; faturamento usa valor histórico dos serviços, separado de caixa. ordenar=faturamento|atendimentos|avaliacao. Profissionais sem avaliação têm média nula.', query=[('inicio', DATA), ('fim', DATA), ('ordenar', {'type': 'string', 'enum': ['faturamento', 'atendimentos', 'avaliacao']})])
    owner('/gestao/avaliacoes', 'get', 'Avaliações dos atendimentos da equipe', PERIODO+'Até 366 dias. Paginação de 20 registros; filtro de profissional somente da loja.', query=[('inicio', DATA), ('fim', DATA), ('pagina', INTEIRO), ('id_funcionario', INTEIRO)])
    detalhe = 'Metas por profissional da loja. Alvo positivo; atendimentos inteiro até 1000000, faturamento em BRL até duas casas. Datas limitadas a 366 dias. Progresso conta concluídos já encerrados e valores históricos dos serviços, sem inferir valores ausentes ou substituir pelo caixa. '
    owner('/gestao/metas', 'get', 'Metas e progresso da equipe', detalhe+'Lista metas cujo período cruza inicio/fim; inclui ativas e inativas.', query=[('inicio', DATA), ('fim', DATA), ('id_funcionario', INTEIRO)])
    owner('/gestao/metas', 'post', 'Cadastrar meta profissional', detalhe+'Novo vínculo exige profissional ativo.', META)
    owner('/gestao/metas/{id_meta}', 'put', 'Editar meta profissional', detalhe, META)
    owner('/gestao/metas/{id_meta}', 'patch', 'Ativar/desativar meta', 'Reativação exige profissional ativo.', ATIVO)
    adicionar('/painel-barbeiro/metas', 'get', 'Metas do próprio profissional', 'Exclusivo profissional ativo (tipo 3) vinculado à loja; consulta somente suas metas e progresso. Não cria/edita metas nem vê outro profissional.', query=[('inicio', DATA), ('fim', DATA), ('id_funcionario', INTEIRO)])

    adicionar('/termos-uso', 'get', 'Documento e estado dos termos de uso', 'Público. Retorna versão, estado_publicacao, aceite_habilitado, responsável e taxa. Publicação depende de nome/contato do responsável e pagador válido; documento/endereço são opcionais. Rascunho não exige aceite nem bloqueia agendamento. Publicado exige aceite atual e permite taxa de 1,5% sobre produtos/serviços, excluindo frete, conforme pagador. Consulta não altera configuração; completar dados depois muda a versão.', publico=True)
    adicionar('/termos-uso/aceite', 'get', 'Estado de aceite da própria conta', 'Sessão ativa e confirmada; somente a própria conta.')
    adicionar('/termos-uso/aceite', 'post', 'Aceitar versão publicada dos termos', 'Sessão ativa; exige versão atual publicada e aceito=true. Persiste documento/hash e auditoria; rascunho não pode ser aceito. Versão incorreta, rascunho ou aceito diferente de true: 428; recarregue termos e resumo antes de novo aceite. Aceite pendente na operação também retorna 428.', objeto({'versao': TEXTO, 'aceito': BOOLEANO}, ['versao', 'aceito']))
    owner('/gestao/taxas-plataforma', 'get', 'Histórico das taxas da plataforma', PERIODO+'Relatório por estabelecimento; taxa em rascunho permanece inativa. Não realiza repasse bancário.', query=[('inicio', DATA), ('fim', DATA)])
    adicionar('/agendamentos/resumo', 'post', 'Resumo de serviços antes de agendar', 'Perfis 0, 1, 2 e 3. Cliente usa a própria conta; demais informam id_cliente. Dono limitado à própria barbearia; profissional limitado ao vínculo e a si próprio. id_funcionario opcional ou null para cliente/ADM/dono: sem vínculo usa preço-base do salão; com vínculo exige profissional elegível. Perfil 3 é limitado ao próprio vínculo. Informa taxa vigente, termos_versao e confirmacao_resumo. Não reserva horário nem registra aceite. Alterações de contexto exigem novo resumo.', objeto({'id_barbearia': INTEIRO, 'ids_servicos': {'type': 'array', 'items': INTEIRO}, 'id_funcionario': {**INTEIRO, 'nullable': True}, 'id_cliente': INTEIRO}, ['id_barbearia', 'ids_servicos']))
    exclusivo = 'Exclusivo ADM (tipo 0). JWT/cookie válido e conta ativa confirmada; perfil é recarregado do banco em cada consulta. 401 sem sessão válida; 403 para outros perfis. Respostas sem cache. '
    adicionar('/admin/help/catalogo', 'get', 'Catálogo técnico atualizado de rotas e arquivos', exclusivo+'Lê regras Flask e App.jsx, contratos, fluxo e dependências locais. Não executa handlers de negócio. Inclui a própria Help, telas mobile e filtros por texto, origem e método no frontend. O bloco imagens descreve validação, WebP, Drive privado, referência do Firebird, entrega binária, ACL, aliases, migração e limitações, sem acessar integrações nem ler configurações.')
    adicionar('/admin/help/codigo/{codigo_id}', 'get', 'Código autorizado por ID opaco', exclusivo+'ID hexadecimal de 32 caracteres registrado no catálogo; nunca aceita caminho arbitrário. Exclui configurações, bancos, uploads, dependências e links. Limite 500 KB; oculta credenciais literais preservando linhas.')
    adicionar('/docs', 'get', 'Documentação Swagger exclusiva do administrador', exclusivo+'HTML com busca e contrato atual, funciona em /docs no backend ou /api/docs pelo proxy. Usa a sessão existente; não persiste credenciais. Chamadas interativas obedecem permissões das rotas de negócio.')
    adicionar('/openapi.json', 'get', 'Contrato OpenAPI exclusivo do administrador', exclusivo+'Somente métodos/caminhos realmente registrados, parâmetros de URL e contratos de módulos novos. URL de servidor relativa ao contrato para backend direto e proxy /api.')
    adicionar('/static/{filename}', 'get', 'Arquivo estático do Flask', 'Infraestrutura estática; não executa operação de negócio.', publico=True)
    for rota in ('/agendamentos', '/gestao/agenda', '/marketplace/pedidos', '/termos-uso/aceite'):
        if 'post' in caminhos.get(rota, {}):
            contrato_aceite = caminhos[rota]['post']
            contrato_aceite['responses'] = {**contrato_aceite['responses'], '428': {
                'description': 'Aceite da versão atual dos termos necessário; recarregue o documento e o resumo. Em rascunho não há exigência de aceite para reservar.'}}
