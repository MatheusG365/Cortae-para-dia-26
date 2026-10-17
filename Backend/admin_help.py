"""Catálogo técnico somente para administradores, sem executar as rotas descritas."""
import ast
import hashlib
import inspect
import os
from pathlib import Path
import re
import stat

from flask import jsonify
from application import app
from funcoes import decodificar_token

RAIZ = Path(__file__).absolute().parent.parent
LIMITE_CODIGO = 500_000
EXTENSOES = {'.py': 'python', '.jsx': 'jsx', '.js': 'javascript', '.css': 'css',
             '.ts': 'typescript', '.tsx': 'tsx'}
PROIBIDOS = {'config.py', 'database.py', '.env', 'node_modules', '.venv', 'tests',
             'uploads', '__pycache__', '.git', 'dist', 'assets'}
SENSIVEL = re.compile(r'(?:password|passwd|senha|secret|api[_-]?key|access[_-]?token|client[_-]?id|token|credential|authorization|private[_-]?key)', re.I)

PAGINAS = {
    '/': ('Início', 'Apresenta a plataforma e os caminhos de navegação.'),
    '/login': ('Entrar', 'Autentica a conta e inicia a sessão do usuário.'),
    '/cadastro': ('Cadastrar usuário', 'Recebe os dados pessoais e a senha para criar uma conta.'),
    '/redefinirsenha': ('Recuperar senha', 'Permite solicitar a recuperação da senha por e-mail.'),
    '/verificar-codigo': ('Verificar código', 'Recebe o código de verificação enviado ao usuário.'),
    '/editarusuario': ('Editar perfil', 'Permite revisar os dados da conta autenticada.'),
    '/editarusuario/:id': ('Editar usuário por ID', 'Abre a edição do usuário indicado no caminho; a API valida a permissão.'),
    '/estabelecimento': ('Estabelecimento e sua loja integrada', 'Com ?usuario=ID mostra apresentação pública, serviços, equipe e loja completa em #loja-barbearia, com as cinco cores escolhidas pelo salão. Sem ID, o próprio estabelecimento exige sessão. A vitrine tem busca, categoria, ordenação, promoções e lançamentos.'),
    '/barbearias-disponiveis': ('Encontrar estabelecimentos', 'Lista estabelecimentos e permite pesquisar pelo nome.'),
    '/cadastrobarbearia': ('Cadastrar estabelecimento', 'Recebe os dados de cadastro de uma barbearia ou salão.'),
    '/personalizacaobarbearia': ('Personalizar estabelecimento', 'Organiza apresentação, fotos e informações do estabelecimento.'),
    '/editarbarbearia': ('Editar estabelecimento', 'Permite editar cadastro, equipe e serviços do estabelecimento.'),
    '/visagismo': ('Escolher corte e visagismo', 'Permite analisar a imagem, consultar cortes ou escolher o corte durante o atendimento.'),
    '/selecionar-servicos': ('Selecionar serviços', 'Escolhe os serviços antes das etapas de corte e agendamento.'),
    '/agendamento': ('Reservar horário', 'Seleciona profissional, data e horário e confirma a reserva ou a entrada na lista de espera.'),
    '/meus-agendamentos': ('Meus agendamentos', 'Exibe o histórico do cliente, detalhes, cancelamento, reagendamento e avaliações elegíveis.'),
    '/agendamentosadm': ('Administrar agendamentos', 'Permite ao administrador ou estabelecimento consultar e gerenciar atendimentos.'),
    '/financeiro': ('Painel financeiro', 'Apresenta movimentações, indicadores e controles financeiros disponíveis.'),
    '/admin/usuarios': ('Administrar usuários', 'Permite ao administrador consultar e gerenciar contas de usuários.'),
    '/admin/cortes': ('Administrar cortes', 'Gerencia o catálogo de cortes usado na escolha e no visagismo.'),
    '/painel-barbeiro': ('Painel do profissional', 'Exibe a própria agenda, atendimentos, comissões, avaliações e acesso às metas do profissional autenticado.'),
    '/comissoes-barbearia': ('Comissões da equipe', 'Consulta os valores calculados para o estabelecimento pagar aos profissionais.'),
    '/ativar-barbeiro': ('Ativar acesso profissional', 'Conclui a ativação do acesso gerado para um profissional.'),
    '/gestao': ('Gestão do estabelecimento e metas', 'Query aba: agenda, equipe, clientes, financeiro, taxas, ranking, metas, relatorios ou logs. Metas permite cadastro, edição, ativação e progresso por atendimentos concluídos ou faturamento histórico. Profissional consulta somente a própria agenda e metas; logs exclusivos do administrador.'),
    '/marketplace': ('Marketplace geral de todas as lojas', 'Vitrine de produtos ativos de todos os estabelecimentos com busca, loja, categoria, ordenação, promoções e lançamentos. Identidade geral Cortaê; cada estabelecimento possui sua loja embutida com as próprias cores.'),
    '/marketplace/barbearias/:id_barbearia': ('Redirecionamento para loja integrada', 'URL antiga redireciona para /estabelecimento?usuario=ID#loja-barbearia, preservando filtros permitidos. A loja individual não é uma página separada.'),
    '/marketplace/produtos/:id': ('Produto, promoção e variações', 'Apresenta fotos, descrição, detalhes, preço original/efetivo, variações com tamanho/cor/volume e estoque próprio. Produto com variações exige escolha; favoritos e desejos são independentes. Avaliação somente após compra entregue.'),
    '/marketplace/favoritos': ('Produtos favoritos', 'Lista os produtos salvos pelo cliente autenticado.'),
    '/marketplace/lista-desejos': ('Lista de desejos independente', 'Lista produtos desejados pelo cliente; salvar ou remover não altera os favoritos. Mostra somente produtos de lojas disponíveis.'),
    '/marketplace/carrinho': ('Carrinho, cupom e checkout por loja', 'Mantém quantidades e variações por cliente, agrupa por loja, permite retirada ou cotação de frete. Cupom fixo/percentual é exclusivo da loja e desconta mercadorias, sem frete. Servidor confere validade, limite e resumo; criação reserva estoque e uso, cancelamento permitido restaura uma vez.'),
    '/marketplace/pedidos': ('Minhas compras', 'Exibe o histórico de pedidos do cliente, pagamento Pix e acompanhamento da entrega.'),
    '/marketplace/pedidos/:id': ('Detalhes da compra', 'Exibe os itens e preços preservados do pedido, o Pix e o status de retirada ou entrega.'),
    '/gestao-marketplace': ('Gestão comercial do marketplace', 'Query aba: produtos, fornecedores, cupons, vendas, pedidos ou remetente. Gerencia produtos/variações, preço de compra, margem, promoções, lançamentos, estoque e histórico. Fornecedores e custos são privados. Painel de vendas separa faturamento pago, pedidos, ticket, frete, desconto e lucro com custos históricos; exporta CSV. Etiquetas permanecem desabilitadas; cotação e rastreio não compram envios.'),
    '/termos-de-uso': ('Termos de uso e aceite', 'Exibe documento, versão e estado de publicação. Rascunho não exige aceite; cobrança de taxa depende da configuração vigente, sem ativação por visitar a página.'),
    '/help': ('Ajuda técnica exclusiva do administrador', 'Acesso por URL e sessão ADM. Catálogo das páginas do site, telas nativas do aplicativo e rotas da API, com fluxo, entradas, saídas e fontes. O administrador consulta o funcionamento do mobile pelo site; não existe painel ADM no aplicativo. Busca e filtros por origem, área e método; código por ID opaco com credenciais ocultadas. Swagger e /openapi.json também exigem ADM.'),
    '/*': ('Página não encontrada', 'Exibe a tela de erro quando nenhum caminho cadastrado corresponde à URL.'),
}


def _permitido(caminho):
    """Aceita somente código próprio, sem links ou diretórios de dados/configuração."""
    caminho = Path(caminho).absolute()
    try:
        relativo = caminho.relative_to(RAIZ)
        if any(parte.lower() in PROIBIDOS or parte.startswith('.') for parte in relativo.parts):
            return False
        if caminho.suffix not in EXTENSOES:
            return False
        mobile = relativo.parts[:2] == ('Cortae_mobile-main', 'src')
        if mobile and caminho.suffix not in {'.ts', '.tsx', '.js', '.jsx'}:
            return False
        if not ((relativo.parts[0] == 'Backend' and len(relativo.parts) == 2)
                or relativo.parts[:2] == ('Frontend', 'src') or mobile):
            return False
        for atual in (caminho, *caminho.parents):
            if atual == RAIZ:
                break
            info = atual.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                return False
        return caminho.is_file() and caminho.resolve().is_relative_to(RAIZ.resolve())
    except (ValueError, OSError):
        return False


def _ler(caminho):
    if not _permitido(caminho):
        raise ValueError('Arquivo indisponível.')
    antes = caminho.stat()
    if antes.st_size > LIMITE_CODIGO or antes.st_nlink > 1:
        raise ValueError('Arquivo indisponível ou excede o limite de leitura.')
    with caminho.open('rb') as arquivo:
        aberto = os.fstat(arquivo.fileno())
        if (antes.st_dev, antes.st_ino, antes.st_size, antes.st_mtime_ns) != (
                aberto.st_dev, aberto.st_ino, aberto.st_size, aberto.st_mtime_ns):
            raise ValueError('Arquivo alterado durante a leitura.')
        conteudo = arquivo.read(LIMITE_CODIGO + 1)
        depois = caminho.stat()
        if (aberto.st_dev, aberto.st_ino, aberto.st_size, aberto.st_mtime_ns) != (
                depois.st_dev, depois.st_ino, depois.st_size, depois.st_mtime_ns):
            raise ValueError('Arquivo alterado durante a leitura.')
    if not _permitido(caminho) or len(conteudo) > LIMITE_CODIGO:
        raise ValueError('Arquivo indisponível.')
    return conteudo.decode('utf-8-sig')


def _id(caminho):
    return hashlib.sha256(caminho.relative_to(RAIZ).as_posix().encode()).hexdigest()[:32]


def _metadado(caminho, linha=1):
    return {'id': _id(caminho), 'caminho': caminho.relative_to(RAIZ).as_posix(),
            'linguagem': EXTENSOES[caminho.suffix], 'linha_inicio': linha}


def _resolver(base, importacao):
    candidatos = []
    caminho = base / importacao
    if caminho.suffix in EXTENSOES:
        candidatos.append(caminho)
    else:
        candidatos.extend(Path(str(caminho) + ext) for ext in EXTENSOES)
        candidatos.extend(caminho / ('index' + ext) for ext in ('.js', '.jsx', '.ts', '.tsx'))
    # Normaliza ../ lexicalmente; resolve() seguiria links antes da verificação.
    normalizados = (Path(os.path.abspath(item)) for item in candidatos)
    return next((item for item in normalizados if _permitido(item)), None)


def _dependencias(inicial, memo):
    if inicial in memo['fechos']:
        return memo['fechos'][inicial]
    vistos, fila = set(), [inicial]
    while fila:
        caminho = fila.pop(0)
        if caminho in vistos or not _permitido(caminho):
            continue
        try:
            if caminho in memo['imports']:
                vistos.add(caminho)
                fila.extend(p for p in memo['imports'][caminho] if p not in vistos)
                continue
            texto = _ler(caminho)
            if caminho.suffix == '.py':
                arvore = ast.parse(texto)
                nomes = []
                for node in ast.walk(arvore):
                    if isinstance(node, ast.Import): nomes.extend(n.name.split('.')[0] for n in node.names)
                    if isinstance(node, ast.ImportFrom) and node.module: nomes.append(node.module.split('.')[0])
                novos = [_resolver(RAIZ / 'Backend', nome) for nome in nomes]
            else:
                nomes = re.findall(r'(?:from\s*|import\s*\(|import\s*)[\'\"](\.[^\'\"]+)[\'\"]', texto)
                novos = [_resolver(caminho.parent, nome) for nome in nomes]
            vistos.add(caminho)
            memo['imports'][caminho] = [item for item in novos if item]
            fila.extend(item for item in novos if item and item not in vistos)
        except (ValueError, OSError, UnicodeError, SyntaxError):
            continue
    resultado = sorted(vistos, key=lambda path: path.as_posix())
    memo['fechos'][inicial] = resultado
    return resultado


def _funcao_atual(funcao, memo=None):
    """Localiza o handler pelo nome qualificado, mesmo após editar suas linhas."""
    try:
        arquivo = Path(inspect.getsourcefile(funcao) or '').absolute()
        if not _permitido(arquivo): return None, arquivo, 1
        arvores = memo.setdefault('arvores', {}) if memo is not None else {}
        if arquivo not in arvores:
            arvores[arquivo] = ast.parse(_ler(arquivo))
        arvore = arvores[arquivo]
        qualname = funcao.__qualname__.replace('.<locals>.', '.')
        def procurar(nodes, prefixo=''):
            for node in nodes:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    nome = prefixo + node.name
                    if nome == qualname and not isinstance(node, ast.ClassDef): return node
                    encontrado = procurar(node.body, nome + '.')
                    if encontrado is not None: return encontrado
            return None
        funcao_ast = procurar(arvore.body)
        if funcao_ast is None: return None, arquivo, 1
        linha = min([funcao_ast.lineno] + [d.lineno for d in funcao_ast.decorator_list])
        return funcao_ast, arquivo, linha
    except (OSError, TypeError, ValueError, UnicodeError, SyntaxError):
        return None, RAIZ, 1


def _analise(funcao_ast):
    """Extrai nomes de entradas/saídas e chamadas; não executa a função."""
    if funcao_ast is None:
        return [], [], [], ''
    entradas, saidas, chamadas = set(), set(), set()
    for node in ast.walk(funcao_ast):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name): chamadas.add(node.func.id)
            if isinstance(node.func, ast.Attribute) and node.func.attr in {'get', 'getlist'} and node.args:
                nome = node.args[0]
                if isinstance(nome, ast.Constant) and isinstance(nome.value, str):
                    base = ast.unparse(node.func.value)
                    if base.startswith(('dados', 'payload', 'request.args', 'request.form', 'request.files')):
                        entradas.add(f'{base}: {nome.value}')
            if isinstance(node.func, ast.Name) and node.func.id == 'jsonify':
                saidas.update(kw.arg for kw in node.keywords if kw.arg)
                for arg in node.args:
                    if isinstance(arg, ast.Dict):
                        saidas.update(key.value for key in arg.keys if isinstance(key, ast.Constant) and isinstance(key.value, str))
    docstring = ast.get_docstring(funcao_ast) or ''
    if SENSIVEL.search(docstring):
        docstring = 'Consulte o fluxo observado e os arquivos de implementação; trechos de credenciais são ocultados.'
    return sorted(entradas), sorted(saidas), sorted(chamadas), docstring


def _backend(memo):
    from api_docs import contrato_atual
    contratos_atuais = contrato_atual()['paths']
    rotas = []
    for regra in sorted(app.url_map.iter_rules(), key=lambda rule: (rule.rule, rule.endpoint)):
        funcao = inspect.unwrap(app.view_functions[regra.endpoint])
        metodos = sorted(regra.methods - {'HEAD', 'OPTIONS'})
        caminho_openapi = re.sub(r'<(?:\w+:)?([^>]+)>', r'{\1}', regra.rule)
        contratos = [contratos_atuais.get(caminho_openapi, {}).get(m.lower(), {}) for m in metodos]
        contrato = next((c for c in contratos if c), {})
        funcao_ast, arquivo, linha = _funcao_atual(funcao, memo)
        entradas, saidas, chamadas, docstring = _analise(funcao_ast)
        fontes = _dependencias(arquivo, memo) if _permitido(arquivo) else []
        protegido = 'decodificar_token' in chamadas
        funcionamento = []
        if regra.rule == '/admin/help/catalogo':
            funcionamento.extend(['Confirma o perfil de administrador antes de analisar os arquivos.',
                'Lê o roteador React do site, os arquivos de telas Expo Router do mobile e as regras do Flask, sem executar os handlers de negócio.',
                'Associa cada rota aos arquivos próprios e às dependências locais permitidas; a própria Help também aparece na lista.'])
        elif regra.rule == '/admin/help/codigo/<codigo_id>':
            funcionamento.extend(['Confirma o perfil de administrador e procura o ID opaco no catálogo atual.',
                'Aceita somente arquivos próprios permitidos, sem configurações, links, bancos ou pastas de dados; nenhum caminho enviado pelo navegador é aberto.',
                'Lê no máximo 500 KB e oculta trechos com credenciais literais, mantendo os números das linhas.',
                'Retorna o código como texto em JSON e proíbe o cache da resposta.'])
        if protegido: funcionamento.append('Lê a sessão com decodificar_token; essa função recarrega o perfil ativo no banco antes de continuar.')
        if entradas: funcionamento.append('Recebe os campos listados em Entradas e aplica as validações presentes no código.')
        if 'conectar_banco' in chamadas: funcionamento.append('Abre uma conexão com o banco; consulte o código para os filtros e operações desta rota.')
        if chamadas: funcionamento.append('Chamadas diretas: ' + ', '.join(chamadas) + '.')
        if not fontes: funcionamento.append('Esta rota é fornecida pela infraestrutura externa; seu código não pertence ao projeto e não é exibido.')
        else: funcionamento.append(f'O handler {regra.endpoint} está no arquivo principal indicado, seguido de suas dependências locais.')
        acesso = 'Regras de sessão e perfil: consulte o handler e suas chamadas locais.'
        if regra.rule.startswith('/admin/help/') or regra.rule in ('/docs', '/openapi.json'):
            acesso = 'Somente administrador (tipo 0), com perfil recarregado no banco a cada consulta.'
        elif contrato.get('security'):
            acesso = 'Sessão exigida no contrato OpenAPI; o código define os perfis e o escopo de dados.'
        elif not protegido:
            acesso = 'O handler não chama decodificar_token diretamente; verifique as validações e funções auxiliares no código.'
        from image_docs import MEDIA_PATHS, UPLOAD_PATHS, ETAPAS, normalizar
        if normalizar(regra.rule) in MEDIA_PATHS:
            acesso = ('Cortes são públicos; fotos e resultados exigem cliente dono, barbearia responsável, profissional vinculado ou ADM. A ACL vem antes do Drive.'
                      if regra.rule.startswith('/uploads/visagismo/') else 'Imagem pública entregue pela API; o arquivo correspondente permanece privado no Drive.')
        parametros = [f'URL: {argumento}' for argumento in sorted(regra.arguments)]
        campos_corpo = {campo for c in contratos for campo in c.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {}).get('properties', {})}
        campos_form = {campo for c in contratos for campo in c.get('requestBody', {}).get('content', {}).get('multipart/form-data', {}).get('schema', {}).get('properties', {})}
        campos_query = {p['name'] for c in contratos for p in c.get('parameters', []) if p.get('in') == 'query'}
        entradas = sorted(set(entradas + parametros + [f'JSON: {campo}' for campo in campos_corpo] + [f'Form: {campo}' for campo in campos_form] + [f'Query: {campo}' for campo in campos_query]))
        tipos_saida = {mime for c in contratos for mime in c.get('responses', {}).get('200', {}).get('content', {})}
        saidas_semanticas = ['Bytes: image/webp (imagem binária; não JSON).'] if 'image/webp' in tipos_saida else []
        if normalizar(regra.rule) in MEDIA_PATHS:
            funcionamento.extend(['Resolve somente uma imagem registrada no Firebird, respeitando aliases e exclusões.',
                'Para fotos/resultados de visagismo, confere a ACL antes de buscar o Drive privado; cortes e as demais mídias públicas não exigem essa sessão.',
                'Confere tamanho/hash do arquivo e entrega WebP; imagem ausente retorna 404 e provedor indisponível retorna 503. No modo Drive não lê arquivos locais.'])
        elif normalizar(regra.rule) in UPLOAD_PATHS and campos_form:
            funcionamento.extend(ETAPAS)
        resumo = contrato.get('summary') or regra.endpoint.replace('_', ' ').capitalize()
        descricao = contrato.get('description') or docstring or f'{", ".join(metodos)} {regra.rule} é atendida pela função {regra.endpoint}; o fluxo observado no código está detalhado abaixo.'
        for metodo, contrato_metodo in zip(metodos, contratos):
            if contrato_metodo:
                funcionamento.append(metodo + ': ' + contrato_metodo.get('summary', '') + '. ' + contrato_metodo.get('description', ''))
        rotas.append({'id': 'backend:' + regra.endpoint + ':' + regra.rule, 'origem': 'backend',
                      'rota': regra.rule, 'metodos': metodos, 'endpoint': regra.endpoint,
                      'titulo': resumo, 'descricao': descricao, 'como_funciona': funcionamento,
                      'entrada': entradas, 'saida': saidas_semanticas + ['JSON: ' + campo for campo in saidas],
                      'acesso': acesso, 'arquivos': [_metadado(p, linha if p == arquivo else 1) for p in ([arquivo] + [p for p in fontes if p != arquivo]) if p in fontes],
                      'observacoes': ['HEAD e OPTIONS são métodos auxiliares gerados pelo Flask.']})
    return rotas


def _frontend(memo):
    app_arquivo = RAIZ / 'Frontend' / 'src' / 'App.jsx'
    texto = _ler(app_arquivo)
    imports = dict(re.findall(r'const\s+(\w+)\s*=\s*lazy\s*\(\s*\(\)\s*=>\s*import\s*\([\'\"]([^\'\"]+)', texto))
    rotas = []
    for match in re.finditer(r'<Route\b[\s\S]*?\s/>', texto):
        bloco = match.group()
        path = re.search(r'\bpath=[\'\"]([^\'\"]+)', bloco)
        if not path: continue
        rota = path.group(1)
        componente = next((nome for nome in imports if re.search(r'<' + re.escape(nome) + r'\b', bloco)), '')
        pagina = _resolver(app_arquivo.parent, imports[componente]) if componente else None
        tipos = re.search(r'tipos=\{\[([^\]]+)\]', bloco)
        acesso = 'Navegação pública; chamadas ao backend têm suas próprias validações.'
        if 'RequireAuth' in bloco:
            acesso = 'Sessão obrigatória.'
            if tipos:
                perfis = {'0': 'administrador', '1': 'cliente', '2': 'estabelecimento', '3': 'profissional'}
                acesso += ' Perfis: ' + ', '.join(perfis.get(v.strip(), v.strip()) for v in tipos.group(1).split(',')) + '.'
        titulo, descricao = PAGINAS.get(rota, (componente or rota, 'Página cadastrada no roteador React; consulte a implementação indicada.'))
        fontes = _dependencias(pagina, memo) if pagina else []
        codigo_pagina = _ler(pagina) if pagina else ''
        consulta = sorted(set(re.findall(r'(?:params|searchParams|parametros|query)\.get\(\s*[\'\"]([^\'\"]+)', codigo_pagina)))
        chamadas_api = sorted(set(re.findall(r'apiFetch\(\s*[\'\"]([^\'\"]+)', codigo_pagina)))
        funcionamento = [f'App.jsx associa o caminho {rota} ao componente {componente}.', acesso,
                         'O componente da página e seus imports locais implementam os formulários, interações e chamadas à API.']
        if chamadas_api:
            funcionamento.append('Chamadas de API com caminho literal no componente: ' + ', '.join(chamadas_api) + '. Consulte os arquivos para as chamadas dinâmicas e seus métodos.')
        comuns = [app_arquivo, _resolver(app_arquivo.parent, './components/RequireAuth/RequireAuth'), _resolver(app_arquivo.parent, './contexts/AuthContext')]
        fontes = list(dict.fromkeys(([pagina] if pagina else []) + fontes + [p for p in comuns if p]))
        rotas.append({'id': 'frontend:' + rota, 'origem': 'frontend', 'rota': rota,
                      'metodos': ['NAVEGAÇÃO'], 'endpoint': componente, 'titulo': titulo,
                      'descricao': descricao, 'como_funciona': funcionamento,
                      'entrada': ['Parâmetro de URL: ' + p for p in re.findall(r':(\w+)', rota)] + ['Query string: ' + p for p in consulta],
                      'saida': ['Interface React no navegador.'], 'acesso': acesso,
                      'arquivos': [_metadado(p) for p in fontes], 'observacoes': []})
    return rotas


def _catalogo():
    from mobile_help import catalogo_mobile
    from image_docs import catalogo_imagens
    memo = {'imports': {}, 'fechos': {}}
    backend = _backend(memo)
    telas, mobile = catalogo_mobile(RAIZ, memo, backend, _permitido, _ler, _dependencias, _metadado)
    rotas = _frontend(memo) + backend + telas
    imagens = catalogo_imagens(backend)
    fontes_imagem = {'Backend/' + name for name in ('image_storage.py', 'google_drive_storage.py',
                     'image_storage_schema.py', 'midia.py', 'image_docs.py')}
    imagens['arquivos'] = list({source['id']: source for route in backend for source in route['arquivos']
                                if source['caminho'] in fontes_imagem}.values())
    return {'rotas': rotas, 'mobile': mobile, 'imagens': imagens,
            'total': {origem: sum(r['origem'] == origem for r in rotas) for origem in ('frontend', 'backend', 'mobile')},
            'ajuda': {'titulo': 'Como funciona esta página', 'passos': [
                'Digite /help na URL e entre com uma conta de administrador. Esta página não tem link nos menus.',
                'O catálogo lê App.jsx, as telas de Cortae_mobile-main/src/app e as regras do Flask; nenhuma rota de negócio é executada.',
                'Use a busca e os filtros para encontrar um caminho, método, função ou arquivo.',
                'Abra uma rota para consultar o fluxo, as entradas, as saídas e os arquivos de implementação.',
                'Selecione Mobile para conhecer as telas de cliente e barbearia, seus parâmetros, a navegação e as APIs relacionadas; o ADM continua acessando somente o site.',
                'Consulte Imagens para entender validação, WebP, Drive privado, referências do Firebird, permissões, migração e entrega ao site e ao aplicativo.',
                'Selecione um arquivo para carregar seu código pelo ID cadastrado. O arquivo principal aparece antes das dependências.',
                'A documentação OpenAPI existente complementa o catálogo; quando não há contrato, a página descreve as chamadas observadas no código.',
                'A própria /help e seus dois endpoints estão incluídos neste catálogo.'],
                'seguranca': ['O backend exige administrador em toda consulta e não permite cache das respostas.',
                    'Arquivos de configuração, credenciais, banco, uploads, testes e dependências externas não são publicados.',
                    'Valores literais atribuídos a campos de credenciais são ocultados; variáveis de ambiente e dados de usuários não são lidos.',
                    'A tela é somente de consulta: não executa serviços, não altera registros e não dispara integrações.']}}


def _sanitizar(texto, linguagem='python'):
    """Redação conservadora de atribuições multilinha; mantém números de linha."""
    linhas = texto.splitlines(keepends=True)
    ocultar = set()
    if linguagem == 'python':
        arvore = ast.parse(texto)
        for node in ast.walk(arvore):
            valores = []
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                alvos = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(SENSIVEL.search(ast.unparse(alvo)) for alvo in alvos): valores.append(node.value)
            elif isinstance(node, ast.Dict):
                valores.extend(valor for chave, valor in zip(node.keys, node.values)
                               if isinstance(chave, ast.Constant) and isinstance(chave.value, str) and SENSIVEL.search(chave.value))
            elif isinstance(node, ast.Call):
                valores.extend(kw.value for kw in node.keywords if kw.arg and SENSIVEL.search(kw.arg))
                # Defaults of environment configuration are literal credentials too.
                if isinstance(node.func, ast.Attribute) and node.func.attr in ('getenv', 'get') and len(node.args) > 1:
                    chave = node.args[0]
                    if isinstance(chave, ast.Constant) and isinstance(chave.value, str) and SENSIVEL.search(chave.value):
                        valores.append(node.args[1])
            for valor in valores:
                if valor is not None and any(isinstance(p, ast.Constant) and isinstance(p.value, str) and p.value for p in ast.walk(valor)):
                    ocultar.update(range(valor.lineno-1, valor.end_lineno))
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and '\n' in node.value and SENSIVEL.search(node.value):
                # Historical credentials can also be pasted in a docstring.
                ocultar.update(range(node.lineno-1, node.end_lineno))
    else:
        # Scan a complete assigned JS expression, including arrays, objects,
        # ternaries and concatenations, without executing or evaluating it.
        padrao = re.compile(r'(?P<nome>[\w$]+|"[\w$-]+"|\'[\w$-]+\')\s*[:=]\s*', re.S)
        tipados = re.compile(r'(?P<nome>[\w$]+)\s*\??\s*:\s*[^=;]{1,2000}?=\s*', re.S)
        for match in list(padrao.finditer(texto)) + list(tipados.finditer(texto)):
            if SENSIVEL.search(match['nome']):
                pos, nivel, aspas, escapado = match.end(), 0, None, False
                comentario, codigo = None, []
                while pos < len(texto):
                    char = texto[pos]
                    seguinte = texto[pos:pos+2]
                    if comentario == 'bloco':
                        if seguinte == '*/':
                            comentario = None
                            pos += 2
                            continue
                        pos += 1
                        continue
                    if comentario == 'linha':
                        if char != '\n':
                            pos += 1
                            continue
                        comentario = None
                    if aspas:
                        if escapado: escapado = False
                        elif char == '\\': escapado = True
                        elif char == aspas: aspas = None
                    elif seguinte in ('//', '/*'):
                        comentario = 'linha' if seguinte == '//' else 'bloco'
                        pos += 2
                        continue
                    elif char in ('\'', '"', '`'): aspas = char
                    elif char in '([{': nivel += 1
                    elif char in ')]}':
                        if nivel == 0: break
                        nivel -= 1
                    elif nivel == 0 and char in ';,': break
                    elif nivel == 0 and char == '\n':
                        antes = ''.join(codigo).rstrip()
                        depois = texto[pos+1:].lstrip()
                        if antes and antes[-1] not in '+?:=&|\\' and (not depois or depois[0] not in '+?:=&|'):
                            break
                    codigo.append(char)
                    pos += 1
                expressao = texto[match.end():pos]
                if not any(char in expressao for char in ('\'', '"', '`')):
                    continue
                inicio = texto.count('\n', 0, match.start())
                fim = texto.count('\n', 0, pos)
                ocultar.update(range(inicio, fim+1))
        for match in re.finditer(r'/\*[\s\S]*?\*/', texto):
            if SENSIVEL.search(match.group()):
                ocultar.update(range(texto.count('\n', 0, match.start()), texto.count('\n', 0, match.end())+1))
    # Comments mentioning credentials are omitted in full; they may repeat an old
    # value even when the executable assignment correctly uses the environment.
    for index, linha in enumerate(linhas):
        if SENSIVEL.search(linha) and re.search(r'#|//|/\*|\*/', linha): ocultar.add(index)
    for index in ocultar:
        fim = '\n' if linhas[index].endswith('\n') else ''
        linhas[index] = '[conteúdo sensível ocultado]' + fim
    return ''.join(linhas), ['Algumas linhas com valores de credenciais foram ocultadas.'] if ocultar else []


def _resposta(dados, status=200):
    resposta = jsonify(dados)
    resposta.status_code = status
    resposta.headers['Cache-Control'] = 'private, no-store'
    resposta.headers['Vary'] = 'Cookie, Authorization'
    resposta.headers['X-Content-Type-Options'] = 'nosniff'
    return resposta


def _autorizar():
    usuario = decodificar_token()
    if not usuario:
        return _resposta({'mensagem': {'informacao': 'Faça login para acessar a ajuda técnica.', 'tipo': 'erro'}}, 401)
    if usuario.get('tipo') != 0:
        return _resposta({'mensagem': {'informacao': 'A ajuda técnica é exclusiva do administrador.', 'tipo': 'erro'}}, 403)
    return None


@app.get('/admin/help/catalogo')
def catalogo_help():
    """Consulta as rotas e fontes atuais somente após validar o administrador."""
    bloqueio = _autorizar()
    if bloqueio is not None: return bloqueio
    try:
        return _resposta(_catalogo())
    except (OSError, ValueError, UnicodeError):
        return _resposta({'mensagem': {'informacao': 'Não foi possível ler o catálogo técnico.', 'tipo': 'erro'}}, 503)


@app.get('/admin/help/codigo/<codigo_id>')
def codigo_help(codigo_id):
    """Lê exclusivamente um ID opaco registrado no catálogo, nunca um caminho enviado."""
    bloqueio = _autorizar()
    if bloqueio is not None: return bloqueio
    if not re.fullmatch(r'[0-9a-f]{32}', codigo_id):
        return _resposta({'mensagem': {'informacao': 'Código não encontrado.', 'tipo': 'erro'}}, 404)
    try:
        arquivos = {arquivo['id']: arquivo for rota in _catalogo()['rotas'] for arquivo in rota['arquivos']}
        metadado = arquivos.get(codigo_id)
        if not metadado: raise ValueError('ID desconhecido.')
        texto = _ler(RAIZ / metadado['caminho'])
        conteudo, avisos = _sanitizar(texto, metadado['linguagem'])
        return _resposta({**metadado, 'linha_inicio': 1, 'conteudo': conteudo,
                          'total_linhas': len(conteudo.splitlines()), 'avisos': avisos})
    except (OSError, ValueError, UnicodeError, SyntaxError):
        return _resposta({'mensagem': {'informacao': 'Código indisponível.', 'tipo': 'erro'}}, 404)
