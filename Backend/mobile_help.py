"""Documentação do aplicativo obtida de fontes locais, sem importar código nativo."""
import os
import re
import stat


def tela(titulo, descricao, passos, entrada=(), api=(), observacoes=()):
    return dict(titulo=titulo, descricao=descricao, passos=passos, entrada=entrada,
                api=api, observacoes=observacoes)


# Os caminhos são comparados à árvore real: uma tela removida não é publicada.
TELAS = {
    '/': tela('Entrada automática do aplicativo', 'Direciona a navegação conforme a sessão validada.',
        ['Aguarda o carregamento da sessão.', 'Sem sessão abre /entrar; cliente segue para /cliente e estabelecimento para /barbearia.']),
    '/*': tela('Tela nativa não encontrada', 'Oferece retorno ao início para um caminho inexistente.',
        ['Expo Router utiliza +not-found.tsx quando não encontra a tela.', 'O botão de início volta ao redirecionamento de sessão.']),
    '/entrar': tela('Entrar no aplicativo', 'Login compartilhado pelos clientes e responsáveis pelas barbearias.',
        ['Valida os campos e envia o login com identificação de cliente mobile.', 'Armazena a sessão nativa no SecureStore e abre a área correspondente ao perfil.', 'Exibe recuperação, cadastro e acesso à confirmação de e-mail quando aplicável.'],
        api=('/login', '/dados-perfil/:id'),
        observacoes=('Contas de administrador e profissional não possuem painel mobile; o administrador utiliza o site.',)),
    '/cadastro': tela('Cadastrar cliente ou barbearia', 'Cria uma conta de cliente ou estabelecimento com contato e senha.',
        ['Seleciona o uso como cliente (tipo 1) ou barbearia (tipo 2) e confere dados pessoais, telefone e confirmação da senha.', 'Consulta os termos vigentes e envia o cadastro.', 'Encaminha ao código enviado por e-mail.'],
        api=('/cadastro', '/termos-uso')),
    '/verificar-codigo': tela('Verificar cadastro por e-mail', 'Confirma o código de ativação da conta.',
        ['Recebe o e-mail da etapa anterior.', 'Envia o código informado à API e orienta o retorno ao login.'],
        entrada=('Query: email',), api=('/verificar-codigo',)),
    '/recuperar-senha': tela('Recuperar senha', 'Solicita código de recuperação e permite definir uma nova senha.',
        ['Informa o e-mail e solicita o código.', 'Após receber o código, envia a nova senha e sua confirmação.', 'Retorna ao login ao concluir.'],
        api=('/recuperar-senha',)),
    '/termos': tela('Termos de uso no aplicativo', 'Consulta o documento e, quando aplicável, registra o aceite da conta autenticada.',
        ['Carrega o documento e sua versão publicada.', 'Consulta o aceite da sessão e permite aceitar a versão vigente.'],
        api=('/termos-uso', '/termos-uso/aceite')),
    '/cliente': tela('Descobrir barbearias', 'Lista estabelecimentos disponíveis e pesquisa por nome.',
        ['Carrega a lista de estabelecimentos.', 'O cliente pesquisa e abre a apresentação da barbearia escolhida.'],
        api=('/barbearias-disponiveis',)),
    '/cliente/barbearia/:id': tela('Barbearia e loja integrada', 'Reúne apresentação, serviços, equipe e produtos do estabelecimento escolhido.',
        ['Recebe o ID da barbearia.', 'Consulta personalização, serviços e produtos da mesma loja.', 'Usa as cores do estabelecimento e oferece acesso à seleção de serviços e ao produto.'],
        entrada=('URL: id da barbearia',), api=('/barbearia/personalizacao', '/barbearia/servicos', '/marketplace/barbearias/:id')),
    '/cliente/servicos': tela('Escolher serviços', 'Seleciona os serviços antes de escolher o corte e o horário.',
        ['Carrega os serviços da barbearia e mantém a seleção.', 'Continua para o visagismo com os serviços e o estabelecimento.'],
        entrada=('Query: barbearia', 'Query opcional: selecionado, funcionario'), api=('/barbearia/servicos',)),
    '/cliente/visagismo': tela('Escolher corte e visagismo', 'Oferece catálogo, escolha na hora ou pelo profissional e análise opcional de foto.',
        ['Consulta os cortes cadastrados e seus detalhes.', 'Permite pular a análise e escolher na hora ou deixar a escolha com o profissional.', 'Com foto e consentimento, solicita análise; a recomendação única apresenta motivo e características.', 'A simulação é uma ação explícita; continua para a reserva com a escolha do corte.'],
        entrada=('Query: barbearia', 'Query: servicos', 'Query opcional: funcionario, tem_pintar, apenas_cor, alvo'),
        api=('/visagismo/cortes', '/visagismo/analisar', '/visagismo/salvar-foto', '/visagismo/:id/simular'),
        observacoes=('Câmera/galeria dependem das permissões do dispositivo. A disponibilidade e a qualidade da IA dependem do provedor configurado; esta ajuda não executa a geração. Selfies e resultados são servidos pela API com controle de acesso antes de ler o Drive privado.',)),
    '/cliente/agendar': tela('Reservar horário ou entrar na lista de espera', 'Seleciona profissional, data e disponibilidade para os serviços escolhidos.',
        ['Carrega profissionais compatíveis e horários.', 'Solicita um resumo validado antes de confirmar a reserva.', 'Em um horário ocupado permite solicitar lista de espera; o aviso depende do processamento do backend.', 'Após reservar, abre o acompanhamento do atendimento.'],
        entrada=('Query: barbearia', 'Query: servicos', 'Query opcional: funcionario, escolha_corte, id_corte, id_visagismo'),
        api=('/barbearias/:id/funcionarios', '/agendamentos/horarios', '/agendamentos/resumo', '/agendamentos', '/agendamentos/lista-espera')),
    '/cliente/agendamentos': tela('Meus agendamentos e pagamentos', 'Acompanha reservas, espera, pagamento e avaliações de atendimento.',
        ['Lista os próprios atendimentos e inscrições na espera.', 'Abre detalhes e permite cancelar ou reagendar conforme as regras da API.', 'Atendimentos elegíveis permitem nota e comentário.', 'Consulta cobrança existente antes de oferecer criação explícita; mostra o código Pix retornado pelo provedor e permite consultar sua situação.'],
        entrada=('Query opcional: id do agendamento',),
        api=('/agendamentos', '/agendamentos/lista-espera', '/agendamentos/lista-espera/:id', '/agendamentos/:id/cancelar', '/agendamentos/:id/reagendar', '/agendamentos/:id/avaliacao', '/agendamentos/horarios', '/pagamentos/agendamento/:id', '/pagamentos/pix', '/pagamentos/pix/:id', '/pagamentos/na-hora'),
        observacoes=('A existência do botão não comprova liquidação bancária real. Códigos internos ARKHEPIX não são apresentados como Pix de outro banco.',)),
    '/cliente/perfil': tela('Meu perfil', 'Edita dados pessoais, telefone, gênero, foto e senha da própria conta.',
        ['Consulta o perfil da sessão.', 'Valida as alterações e envia os dados; foto usa upload e permissão de galeria. A API valida até 10 MB, reduz para WebP, armazena no Drive privado e devolve uma referência opaca.', 'Atualiza a sessão após salvar e oferece saída segura.'],
        api=('/dados-perfil/:id', '/editar-usuario/:id', '/logout')),
    '/cliente/loja': tela('Marketplace geral', 'Apresenta produtos de todas as lojas com busca e filtros.',
        ['Busca produtos disponíveis e aplica os filtros escolhidos.', 'Abre o detalhe do produto ou o estabelecimento; favoritos e desejos possuem telas próprias.'],
        api=('/marketplace/produtos',)),
    '/cliente/produto/:id': tela('Detalhes do produto', 'Mostra fotos, descrição, variações, estoque, preço, avaliações e produtos relacionados.',
        ['Carrega o produto e a identidade visual da loja.', 'Exige variação quando aplicável e confere quantidade para o carrinho.', 'Permite favoritar, salvar em desejos e avaliar quando a compra for elegível.'],
        entrada=('URL: id do produto',), api=('/marketplace/produtos/:id', '/marketplace/barbearias/:id/perfil', '/marketplace/carrinho/:id', '/marketplace/favoritos/:id', '/marketplace/lista-desejos/:id', '/marketplace/produtos/:id/avaliacao')),
    '/cliente/favoritos': tela('Meus favoritos', 'Lista produtos marcados como favoritos.',
        ['Consulta os favoritos da própria conta.', 'Abre o produto para consultar detalhes ou alterar a marcação.'], api=('/marketplace/favoritos',)),
    '/cliente/desejos': tela('Minha lista de desejos', 'Mantém os produtos desejados independentemente dos favoritos.',
        ['Consulta a lista de desejos do cliente.', 'Abre os detalhes do produto para continuar a compra.'], api=('/marketplace/lista-desejos',)),
    '/cliente/carrinho': tela('Carrinho por cliente e por loja', 'Organiza os itens por estabelecimento e permite alterar quantidades e remover itens.',
        ['Consulta o carrinho da sessão e agrupa por barbearia.', 'Atualiza quantidades respeitando produto, variação e estoque.', 'Segue para finalizar a compra de uma loja por vez.'], api=('/marketplace/carrinho', '/marketplace/carrinho/:id')),
    '/cliente/checkout': tela('Finalizar compra da loja', 'Confere retirada ou entrega, endereço, frete, cupom e resumo antes de criar o pedido.',
        ['Recebe a barbearia do grupo do carrinho.', 'Para entrega, solicita cotação e seleciona uma opção; retirada dispensa frete.', 'Valida o resumo e o cupom no servidor.', 'Somente a confirmação explícita cria o pedido e reserva os itens.'],
        entrada=('Query: barbearia',), api=('/marketplace/carrinho', '/marketplace/frete', '/marketplace/pedidos/resumo', '/marketplace/pedidos'),
        observacoes=('Cotação não compra etiqueta. O funcionamento real do frete depende das credenciais e do contrato de transporte do backend.',)),
    '/cliente/pedidos': tela('Minhas compras', 'Lista o histórico de pedidos do cliente.',
        ['Consulta apenas pedidos autorizados pela sessão.', 'Abre um pedido para acompanhar itens, pagamento e entrega.'], api=('/marketplace/pedidos',)),
    '/cliente/pedidos/:id': tela('Detalhe da compra e Pix', 'Consulta itens e preços históricos, pagamento, cancelamento permitido e entrega.',
        ['Recebe o ID do pedido e consulta os detalhes.', 'Exibe o código de pagamento fornecido pelo servidor e permite consultar a situação.', 'Exibe dados de entrega e rastreio retornados no pedido; cancelamento segue as regras da API.'],
        entrada=('URL: id do pedido',), api=('/marketplace/pedidos/:id', '/marketplace/pedidos/:id/pix', '/marketplace/pedidos/:id/pagamento', '/marketplace/pedidos/:id/cancelar')),
    '/barbearia': tela('Visão geral da barbearia', 'Resumo da agenda do dia e atalhos de gestão do estabelecimento autenticado.',
        ['Carrega a agenda do dia no escopo da própria barbearia.', 'Mostra indicadores e próximos atendimentos.', 'Abre agenda, equipe, clientes, caixa, ranking, metas, relatórios e perfil.'], api=('/gestao/agenda',)),
    '/barbearia/agenda': tela('Agenda e status dos atendimentos', 'Consulta períodos e gerencia atendimentos e bloqueios da própria barbearia.',
        ['Seleciona período e visualização e carrega atendimentos e bloqueios.', 'Permite concluir, registrar falta, cancelar ou reagendar com confirmação personalizada.', 'Cadastra ou remove bloqueios de disponibilidade e abre recebimentos do atendimento.'],
        entrada=('Query opcional: atendimento',), api=('/gestao/agenda', '/gestao/agenda/bloqueios', '/gestao/agenda/bloqueios/:id', '/agendamentos/:id/status-atendimento', '/agendamentos/:id/cancelar', '/agendamentos/:id/reagendar')),
    '/barbearia/novo-agendamento': tela('Agendar para um cliente', 'Cria atendimento para um cliente cadastrado a partir da gestão.',
        ['Localiza o cliente pelo e-mail e seleciona serviços e profissional.', 'Consulta disponibilidade e resumo.', 'Confirma a criação pela API de gestão e retorna à agenda.'],
        api=('/gestao/agenda', '/gestao/agenda/cliente', '/agendamentos/horarios', '/agendamentos/resumo')),
    '/barbearia/equipe': tela('Equipe, serviços e convites', 'Gerencia profissionais, serviços, preços, horários, vínculos e comissão percentual.',
        ['Consulta equipe e serviços do estabelecimento.', 'Cadastra ou edita serviços e ativa/desativa os existentes.', 'Cadastra profissional e gera convite; configura horários, preços, vínculos e percentual individual.', 'Ativação/desativação preserva histórico e respeita impedimentos da API.'],
        api=('/gestao/agenda', '/barbearia/servicos', '/barbearia/servicos/:id', '/gestao/servicos/:id/ativo', '/barbearia/funcionarios', '/barbearia/funcionarios/:id/estado', '/barbearia/funcionarios/:id/servicos', '/gestao/profissionais/:id/config', '/barbearias/:id/funcionarios/:id/convite'),
        observacoes=('Convites e criação de acesso dependem do envio de e-mail do backend; a documentação não dispara mensagens.',)),
    '/barbearia/clientes': tela('Clientes e histórico', 'Pesquisa clientes, consulta histórico e mantém observações e preferências.',
        ['Aplica os filtros e abre um cliente autorizado.', 'Consulta atendimentos, faltas e histórico disponível.', 'Salva observações e preferências pela API de gestão.'], api=('/gestao/clientes', '/gestao/clientes/:id')),
    '/barbearia/financeiro': tela('Caixa, despesas e comissões', 'Consulta resumo financeiro e mantém lançamentos locais, recebimentos e pagamento manual de comissões.',
        ['Filtra o período e consulta resumo, lançamentos e categorias.', 'Registra receitas/despesas e recebimentos presenciais, inclusive divisão por forma de pagamento.', 'Consulta as comissões calculadas e registra o controle manual do pagamento.'],
        entrada=('Query opcional: atendimento',), api=('/gestao/financeiro/resumo', '/gestao/financeiro/lancamentos', '/gestao/financeiro/lancamentos/:id', '/gestao/financeiro/categorias', '/gestao/agendamentos/:id/recebimentos', '/gestao/comissoes/pagamentos'),
        observacoes=('Registrar um pagamento manual de comissão não transfere dinheiro pela Arkhé.',)),
    '/barbearia/ranking': tela('Ranking e avaliações da equipe', 'Compara profissionais por indicadores e consulta avaliações autorizadas.',
        ['Escolhe período e ordenação do ranking.', 'Consulta indicadores, notas e comentários de atendimentos da própria barbearia.'], api=('/gestao/ranking', '/gestao/avaliacoes')),
    '/barbearia/metas': tela('Metas dos profissionais', 'Cadastra e acompanha metas por atendimentos realizados ou faturamento.',
        ['Seleciona o período e consulta progresso.', 'Define profissional, indicador, alvo e vigência.', 'Edita ou ativa/desativa as metas existentes.'], api=('/gestao/metas', '/gestao/metas/:id', '/gestao/agenda')),
    '/barbearia/relatorios': tela('Relatórios de atendimento', 'Consulta estatísticas de agenda, serviços, equipe, horários e clientes.',
        ['Seleciona período e solicita relatório.', 'Exibe os agrupamentos e clientes frequentes ou inativos retornados pelo servidor.'], api=('/gestao/relatorios',)),
    '/barbearia/loja': tela('Produtos da minha loja', 'Gerencia o catálogo e abre edição, estoque, variações e áreas comerciais.',
        ['Lista os produtos da própria loja com filtros.', 'Abre cadastro, edição, estoque e variações.', 'Ativa ou desativa os produtos conforme as regras da API.'], api=('/gestao/marketplace/produtos', '/gestao/marketplace/produtos/:id')),
    '/barbearia/produto': tela('Cadastrar ou editar produto', 'Mantém descrição, fotos já cadastradas, categoria, marca, custos, preços e destaques comerciais. A API também aceita novos arquivos em multipart, preservando o suporte a URLs HTTPS legadas.',
        ['Com id=novo abre cadastro; com ID carrega o produto existente.', 'Preenche os dados e vínculos de fornecedor, promoção e lançamento.', 'Seleciona e remove fotos, confere prévias e salva novos arquivos em multipart; cada imagem vira WebP no Drive pela API, com até oito fotos no total.', 'Valida e salva o produto no escopo da própria loja.'], entrada=('Query: id (novo ou ID do produto)',), api=('/gestao/marketplace/produtos', '/gestao/marketplace/produtos/:id', '/gestao/marketplace/fornecedores')),
    '/barbearia/variacoes': tela('Variações do produto', 'Mantém tamanho, cor, volume, preço, custo e estoque por variação.',
        ['Recebe o produto e lista suas variações.', 'Cadastra ou edita as opções e sua situação.', 'Abre estoque da variação escolhida.'], entrada=('Query: id do produto',), api=('/gestao/marketplace/produtos/:id/variacoes', '/gestao/marketplace/produtos/:id/variacoes/:id')),
    '/barbearia/estoque': tela('Entradas e histórico de estoque', 'Adiciona unidades e consulta o histórico do produto ou variação.',
        ['Recebe o ID do produto e, opcionalmente, da variação.', 'Consulta movimentos e informa quantidade de entrada, custo e motivo.', 'Confirma a entrada e recarrega o saldo retornado pelo servidor.'], entrada=('Query: id do produto', 'Query opcional: variacao'), api=('/gestao/marketplace/produtos/:id/estoque', '/gestao/marketplace/produtos/:id/variacoes/:id/estoque')),
    '/barbearia/fornecedores': tela('Fornecedores da loja', 'Cadastra, edita e controla a situação dos fornecedores do estabelecimento.',
        ['Consulta os fornecedores próprios.', 'Mantém identificação e contato e altera sua situação.'], api=('/gestao/marketplace/fornecedores', '/gestao/marketplace/fornecedores/:id')),
    '/barbearia/cupons': tela('Cupons da loja', 'Mantém descontos fixos ou percentuais, validade, valor mínimo e limite de uso.',
        ['Lista os cupons da própria loja.', 'Cadastra ou edita as regras e ativa/desativa o cupom.', 'O uso é conferido pelo servidor na finalização da compra.'], api=('/gestao/marketplace/cupons', '/gestao/marketplace/cupons/:id')),
    '/barbearia/pedidos': tela('Pedidos da loja', 'Pesquisa pedidos por situação e busca e abre a gestão de uma compra.',
        ['Consulta pedidos autorizados do estabelecimento.', 'Filtra a situação e abre o detalhe pelo ID.'], api=('/gestao/marketplace/pedidos',)),
    '/barbearia/pedido': tela('Gerenciar compra e entrega', 'Mostra cliente, itens, pagamento e etapas de preparação, retirada e envio.',
        ['Recebe o ID do pedido e carrega o histórico.', 'Permite avançar os status de preparação e retirada previstos.', 'Para entrega, abre o Melhor Envio externamente e permite vincular um envio existente após confirmação.', 'Atualiza o rastreio de envio vinculado sem comprar uma etiqueta.'], entrada=('Query: id do pedido',), api=('/gestao/marketplace/pedidos/:id', '/gestao/marketplace/pedidos/:id/status', '/gestao/marketplace/pedidos/:id/rastreio', '/gestao/marketplace/pedidos/:id/vincular-envio'),
        observacoes=('A emissão e a compra de etiquetas não são realizadas por esta tela. A vinculação exige conferir os dados do envio existente.',)),
    '/barbearia/vendas': tela('Painel de vendas do marketplace', 'Consulta faturamento, pedidos, ticket médio e relatório comercial por período.',
        ['Seleciona período e solicita o relatório de vendas.', 'Exibe indicadores e agrupamentos com os valores retornados pelo servidor.'], api=('/gestao/marketplace/relatorios',)),
    '/barbearia/entregas': tela('Remetente e entregas', 'Mantém os dados do remetente usados na cotação de frete.',
        ['Carrega o cadastro de remetente da própria loja.', 'Valida identificação, contato e endereço e salva os dados.'], api=('/gestao/marketplace/remetente',)),
    '/barbearia/perfil': tela('Perfil público e regras da agenda', 'Edita informações públicas, cores, contato e regras de prazo do estabelecimento.',
        ['Consulta o perfil e as configurações de agenda.', 'Salva apenas os campos públicos permitidos pelo endpoint seguro.', 'Atualiza regras de cancelamento/reagendamento pela API de gestão.'], api=('/barbearia/perfil', '/gestao/agenda/config')),
    '/barbearia/mais': tela('Menu de gestão da barbearia', 'Agrupa os atalhos das áreas secundárias e a saída da conta.',
        ['Abre equipe, clientes, caixa, ranking, metas, relatórios, loja e perfil.', 'Ao sair, limpa a sessão nativa e retorna ao login.'], api=('/logout',)),
}


FLUXOS = [
    ('acesso', 'Cadastro, acesso e sessão', ['/cadastro', '/verificar-codigo', '/entrar', '/', '/recuperar-senha', '/termos'],
     ['Cliente cria a conta e confirma o código enviado por e-mail.', 'Login aceita cliente e estabelecimento; o perfil dirige a navegação.', 'A sessão é revalidada pela API; expiração e saída levam ao login.']),
    ('agendamento', 'Cliente: descobrir e agendar', ['/cliente', '/cliente/barbearia/:id', '/cliente/servicos', '/cliente/visagismo', '/cliente/agendar', '/cliente/agendamentos'],
     ['Escolhe barbearia e serviços.', 'Seleciona corte ou deixa a escolha para o atendimento; visagismo é opcional.', 'Confere profissional, horário e resumo e reserva ou entra na espera.', 'Acompanha, paga quando aplicável e avalia após o atendimento elegível.']),
    ('compra', 'Cliente: compra por loja', ['/cliente/loja', '/cliente/barbearia/:id', '/cliente/produto/:id', '/cliente/favoritos', '/cliente/desejos', '/cliente/carrinho', '/cliente/checkout', '/cliente/pedidos', '/cliente/pedidos/:id'],
     ['Encontra produto na loja geral ou dentro da barbearia.', 'Escolhe variação e quantidade e adiciona ao próprio carrinho.', 'Finaliza uma loja por vez com retirada ou entrega e resumo validado.', 'Acompanha pagamento e entrega no histórico de compras.']),
    ('gestao', 'Barbearia: atendimento e equipe', ['/barbearia', '/barbearia/agenda', '/barbearia/novo-agendamento', '/barbearia/equipe', '/barbearia/clientes', '/barbearia/financeiro', '/barbearia/ranking', '/barbearia/metas', '/barbearia/relatorios', '/barbearia/perfil', '/barbearia/mais'],
     ['Consulta a agenda e mantém profissionais, serviços, horários e bloqueios.', 'Gerencia atendimento, status, recebimentos e clientes.', 'Acompanha comissões manuais, avaliações, metas e relatórios.']),
    ('loja', 'Barbearia: operação comercial', ['/barbearia/loja', '/barbearia/produto', '/barbearia/variacoes', '/barbearia/estoque', '/barbearia/fornecedores', '/barbearia/cupons', '/barbearia/pedidos', '/barbearia/pedido', '/barbearia/vendas', '/barbearia/entregas'],
     ['Cadastra produtos, fornecedores, variações, estoque e descontos.', 'Acompanha compras e avança preparação e retirada.', 'Mantém remetente e vincula envio existente para rastrear entregas.', 'Consulta indicadores de vendas por período.']),
    ('imagens', 'Fotos e imagens no Drive', ['/cliente/perfil', '/cliente/visagismo', '/barbearia/produto'],
     ['Perfil, visagismo e fotos de produtos usam uploads pela mesma API do site.',
      'O backend valida até 10 MB e 24 megapixels, aplica orientação, reduz e converte a imagem estática para WebP sem metadados.',
      'O Drive guarda arquivos privados e o Firebird guarda referências; o aplicativo exibe URLs da API, com sessão autorizada para selfies e resultados.',
      'Logo, fundo e banner de conteúdo usam /midia/mobile/<nome>; seis recursos nativos de ícones e splash ficam locais. Nenhuma tela oferece configuração da conexão ou acesso ADM.']),
]

# Um mesmo caminho pode ter handlers distintos para consulta e escrita.
# Associamos apenas o handler utilizado pela tela, preservando seus métodos reais.
USO_METODOS = {
    '/cliente/barbearia/:id': {'/barbearia/personalizacao': {'GET'}, '/barbearia/servicos': {'GET'}},
    '/cliente/servicos': {'/barbearia/servicos': {'GET'}},
    '/cliente/visagismo': {'/visagismo/cortes': {'GET'}},
    '/cliente/agendamentos': {'/agendamentos': {'GET'}},
    '/cliente/agendar': {'/agendamentos': {'POST'}},
    '/cliente/pedidos': {'/marketplace/pedidos': {'GET'}},
    '/cliente/checkout': {'/marketplace/pedidos': {'POST'}},
    '/barbearia/equipe': {'/barbearia/servicos/:id': {'PUT'}},
}


def caminho_router(arquivo, pasta):
    partes = list(arquivo.relative_to(pasta).with_suffix('').parts)
    partes = [p for p in partes if not (p.startswith('(') and p.endswith(')'))]
    if partes and partes[-1] == 'index':
        partes.pop()
    if partes == ['+not-found']:
        return '/*'
    return '/' + '/'.join(re.sub(r'^\[(?:\.\.\.)?([^]]+)\]$', r':\1', p) for p in partes)


def _paginas(pasta, permitido):
    def diretorio_seguro(caminho):
        try:
            info = caminho.lstat()
            return stat.S_ISDIR(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400
        except OSError:
            return False
    if not all(diretorio_seguro(p) for p in (pasta, *pasta.parents)):
        return []
    encontrados = []
    for atual, diretorios, arquivos in os.walk(pasta, followlinks=False):
        # Nunca segue junctions/reparse points ou pastas de dados durante o scan.
        diretorios[:] = [nome for nome in diretorios if not nome.startswith('.') and
                        diretorio_seguro(type(pasta)(atual) / nome)]
        for nome in sorted(arquivos):
            caminho = type(pasta)(atual) / nome
            if (caminho.suffix in {'.tsx', '.ts', '.jsx', '.js'} and
                    caminho.stem != '_layout' and not caminho.stem.endswith('+api') and
                    (not caminho.stem.startswith('+') or caminho.stem == '+not-found') and permitido(caminho)):
                encontrados.append(caminho)
    return sorted(encontrados, key=lambda p: p.as_posix())


def _api_relacionada(padroes, backend, caminho):
    def normalizar(caminho):
        return re.sub(r'<(?:\w+:)?[^>]+>', ':id', caminho)
    usos = USO_METODOS.get(caminho, {})
    return [{chave: r[chave] for chave in ('id', 'rota', 'metodos', 'titulo')}
            for r in backend if normalizar(r['rota']) in padroes and
            (normalizar(r['rota']) not in usos or set(r['metodos']) & usos[normalizar(r['rota'])])]


def catalogo_mobile(raiz, memo, backend, permitido, ler, dependencias, metadado):
    pasta = raiz / 'Cortae_mobile-main' / 'src' / 'app'
    rotas = []
    comuns = [pasta / '_layout.tsx', pasta.parent / 'lib' / 'session.tsx',
              pasta.parent / 'lib' / 'api.ts', pasta.parent / 'lib' / 'apiAddress.ts',
              pasta.parent / 'lib' / 'dialogs.tsx']
    for arquivo in _paginas(pasta, permitido):
        caminho = caminho_router(arquivo, pasta)
        area = 'cliente' if caminho.startswith('/cliente') else 'barbearia' if caminho.startswith('/barbearia') else 'publico'
        acesso = {'cliente': 'Somente cliente autenticado (tipo 1), protegido pelo Expo Router e pela API.',
                  'barbearia': 'Somente estabelecimento autenticado (tipo 2); a API delimita os dados da própria barbearia.',
                  'publico': 'Área pública ou de entrada; /entrar, cadastro e recuperação são exibidos sem sessão. Termos também podem ser consultados autenticado.'}[area]
        dados = TELAS.get(caminho, tela('Tela mobile ' + caminho,
            'Tela encontrada no Expo Router; consulte seus arquivos para o comportamento implementado.',
            ['Expo Router resolve este caminho pelo arquivo indicado.', 'Os imports locais e layouts listados implementam a navegação e as validações.']))
        fontes = dependencias(arquivo, memo)
        layouts = [pai / '_layout.tsx' for pai in arquivo.parents if pai.is_relative_to(pasta)]
        for extra in layouts + comuns:
            if permitido(extra):
                fontes += dependencias(extra, memo)
        fontes = list(dict.fromkeys([arquivo] + fontes))
        rotas.append({'id': 'mobile:' + caminho, 'origem': 'mobile', 'area': area, 'rota': caminho,
            'metodos': ['NAVEGAÇÃO'], 'endpoint': arquivo.relative_to(pasta).as_posix(),
            'titulo': dados['titulo'], 'descricao': dados['descricao'], 'acesso': acesso,
            'como_funciona': [f'Expo Router associa {caminho} ao arquivo {arquivo.relative_to(pasta).as_posix()}.',
                              *dados['passos'], acesso],
            'entrada': list(dados['entrada']), 'saida': ['Interface React Native no aplicativo Expo.'],
            'arquivos': [metadado(p) for p in fontes],
            'api_relacionada': _api_relacionada(dados['api'], backend, caminho),
            'observacoes': list(dados['observacoes'])})
    ids = {r['id'] for r in rotas}
    mobile = {'titulo': 'Como funciona o aplicativo Cortaê',
        'descricao': 'Aplicativo React Native com Expo Router para clientes e barbearias. O administrador acompanha a documentação pelo site; não há painel ADM mobile.',
        'funcionamento': [
            'As abas do cliente são Descobrir, Agenda, Loja e Perfil; as da barbearia são Visão geral, Agenda, Minha loja e Gestão.',
            'Os arquivos em src/app definem os caminhos. Layouts organizam navegação e proteção de perfil e aparecem como fontes de apoio, sem serem contados como telas.',
            'Componentes em src/features implementam as telas; UI, confirmações personalizadas, sessão, API e regras compartilhadas ficam em src/ui.tsx e src/lib.',
            'A sessão nativa usa SecureStore; dados e permissões continuam sendo validados pelo backend compartilhado com o site.',
            'Cada imagem enviada pela API compartilhada é validada e convertida em WebP no servidor; os arquivos ficam privados no Google Drive e o banco guarda a referência. O aplicativo usa as URLs da API, sem receber credenciais do Drive. Fotos privadas de visagismo exigem a sessão autorizada; aliases registrados mantêm nomes antigos compatíveis, sem fallback para pasta local no modo Drive.',
            'Em desenvolvimento o endereço da API deriva do servidor Expo; na publicação é definido pela equipe. Não existe tela nem botão de configurar conexão para o usuário.',
            'Os links de API nesta ajuda abrem a documentação do handler; não executam pedidos, agendamentos, pagamentos ou integrações.'],
        'fluxos': [{'id': ident, 'titulo': titulo, 'etapas': etapas,
                    'rotas': ['mobile:' + p for p in caminhos if 'mobile:' + p in ids]}
                   for ident, titulo, caminhos, etapas in FLUXOS],
        'observacoes': [
            'Banners, logos e fundos do aplicativo são conteúdo servido por /midia/mobile/<nome>; somente os seis recursos exigidos pela compilação nativa permanecem locais.',
            'Nova URL HTTPS cadastrada como referência continua externa até importação técnica explícita; consultar Help não inicia migração nem acessa o Drive.',
            'O catálogo descreve a implementação atual e não certifica que todos os serviços externos estejam operacionais.',
            'Pagamentos reais, geração de imagem por IA e entrega de e-mails dependem da configuração e da validação externa; abrir esta ajuda não realiza esses testes.',
            'Frete tem cotação e rastreio de envio existente; a compra e emissão automática de etiquetas não estão disponíveis no aplicativo.',
            'Comissões são calculadas e controladas para pagamento manual, sem transferência bancária automática.',
            'WhatsApp permanece fora da integração atual.',
            'Administradores e profissionais utilizam os acessos do site; o aplicativo aceita apenas cliente e estabelecimento.']}
    return rotas, mobile
