"""Read-only image documentation. Never initializes providers or reads settings/data."""

ETAPAS = [
    'Site e aplicativo enviam cada imagem em multipart/form-data à mesma API; seleção de câmera/galeria depende da permissão do dispositivo.',
    'O servidor decodifica os bytes reais: JPEG, PNG, WebP ou GIF estático, até 10 MB e 24 megapixels por arquivo. Animações e arquivos inválidos são rejeitados.',
    'Aplica a orientação EXIF, limita a maior dimensão a 512 px no perfil e 1600 px nas demais imagens, preservando transparência quando existente.',
    'Converte para WebP, escolhe a menor codificação entre as candidatas com e sem perdas e remove EXIF, GPS, comentários e demais metadados.',
    'Envia o arquivo privado ao Google Drive. O Firebird guarda referência, área, vínculo, dimensões, tamanho e hash; não recebe o conteúdo binário da foto.',
    'A gravação da referência acompanha a transação do cadastro. Falha desfaz a referência e tenta limpar o upload novo; substituições preservam o anterior até confirmar a transação.',
    'Os clientes recebem URLs da API. O servidor consulta a referência, verifica permissão quando necessária, lê o Drive e confere tamanho/hash antes de entregar bytes image/webp.',
]
TIPOS = [
    'Perfil: foto pública, redimensionada até 512 px; exclusão e substituição respeitam o vínculo atual, inclusive nas URLs antigas.',
    'Barbearia: logo e até cinco fotos públicas da galeria; envio nos campos logo e foto1 a foto5.',
    'Marketplace: fotos públicas dos produtos; até oito por produto, somando referências mantidas e arquivos novos. Custo e fornecedor continuam privados.',
    'Catálogo de cortes: referências públicas. Novo arquivo vira WebP no Drive; uma nova imagem_url HTTPS permanece URL externa até importação explícita.',
    'Visagismo: fotos do cliente e resultados são privados. A API verifica cliente dono, barbearia responsável, profissional vinculado ao atendimento ou ADM antes de buscar bytes.',
    'Imagens fixas: fotos, banners e logos do site usam /midia/site/<nome>; conteúdo visual do aplicativo usa /midia/mobile/<nome>.',
    'Compilação nativa: cinco ícones referenciados em app.json para Android/Expo permanecem locais; não são fotos de conteúdo nem uploads.',
]
OBSERVACOES = [
    'No modo Google Drive não há fallback para imagens locais. Aliases registrados mantêm URLs antigas compatíveis mesmo após remover as pastas de fotos.',
    'Imagem ausente ou removida retorna 404; Drive indisponível ou sem configuração retorna 503; limites de arquivo/resolução/tamanho retornam 413. Arquivo inválido retorna 400 e foto privada sem permissão retorna 403.',
    'A migração é uma operação técnica explícita, com backup verificado e revalidação das referências. A CLI pode importar imagens locais, o manifesto fixo site/mobile e referências HTTPS existentes do catálogo com proteção SSRF; não importa novas URLs automaticamente.',
    'Uma imagem muito otimizada pode não ficar menor depois da conversão; o servidor respeita os limites e não promete redução fixa.',
    'A limpeza remota é uma tentativa: interrupções ou indisponibilidade podem deixar um arquivo privado pendente de limpeza, sem referência pública válida.',
    'Credenciais e configuração OAuth ficam exclusivamente no servidor. Se o OAuth externo estiver em modo de teste e usar os escopos do Drive, o refresh token normalmente expira em sete dias; a equipe deve preparar a configuração para produção.',
    'Esta documentação é somente consulta: não abre o Drive, não envia imagens, não executa migração, não altera permissões e não testa integrações.',
]

MEDIA_PATHS = {'/midia/site/{nome}', '/midia/mobile/{nome}',
               '/fotos-perfil/{nome_arquivo}', '/uploads/perfil/{nome_arquivo}',
               '/uploads/barbearia/{nome_arquivo}', '/uploads/marketplace/{filename}',
               '/uploads/visagismo/{tipo}/{nome}'}
UPLOAD_PATHS = {'/editar-usuario/{id_usuario}', '/barbearia/personalizacao',
                '/visagismo/cortes', '/visagismo/cortes/{id_corte}',
                '/visagismo/analisar', '/visagismo/salvar-foto',
                '/gestao/marketplace/produtos', '/gestao/marketplace/produtos/{id_produto}'}


def normalizar(rota):
    import re
    return re.sub(r'<(?:\w+:)?([^>]+)>', r'{\1}', rota)


def catalogo_imagens(backend):
    apis = [{key: route[key] for key in ('id', 'rota', 'titulo', 'metodos')}
            for route in backend if normalizar(route['rota']) in MEDIA_PATHS | UPLOAD_PATHS
            or route['rota'] == '/visagismo/<int:id_visagismo>/simular']
    return {'titulo': 'Imagens do site e do aplicativo no Google Drive',
            'descricao': 'Uploads, logos, banners, fotos de produtos e visagismo compartilham o armazenamento privado; a API controla a entrega das imagens ao site e ao mobile.',
            'etapas': list(ETAPAS), 'tipos': list(TIPOS),
            'observacoes': list(OBSERVACOES), 'apis': apis}


def complementar_imagens(documento):
    """Describe actual bytes and fields without changing route authorization."""
    paths = documento['paths']
    for path in MEDIA_PATHS:
        operation = paths[path]['get']
        operation['responses'] = {**operation['responses'], '200': {
            'description': 'Bytes da imagem WebP; não é uma resposta JSON nem um redirecionamento público do Drive.',
            'headers': {'X-Content-Type-Options': {'schema': {'type': 'string', 'enum': ['nosniff']}}},
            'content': {'image/webp': {'schema': {'type': 'string', 'format': 'binary'}}}}}
        if path == '/uploads/visagismo/{tipo}/{nome}':
            parameters = operation.setdefault('parameters', [])
            if not any(p['name'] == 'tipo' and p.get('in') == 'path' for p in parameters):
                parameters.append({'name': 'tipo', 'in': 'path', 'required': True,
                    'schema': {'type': 'string', 'enum': ['cortes', 'fotos', 'resultados']}})
    for path in UPLOAD_PATHS:
        for method, operation in paths[path].items():
            multipart = operation.get('requestBody', {}).get('content', {}).get('multipart/form-data')
            if not multipart:
                continue
            properties = multipart['schema'].get('properties', {})
            encoding = {}
            for name, field in properties.items():
                binary = field.get('format') == 'binary' or field.get('items', {}).get('format') == 'binary'
                if binary:
                    annotation = 'JPEG, PNG, WebP ou GIF estático; até 10 MB e 24 megapixels por arquivo. Convertido para WebP sem metadados no servidor.'
                    description = field.get('description', '')
                    if annotation not in description:
                        field['description'] = (description + ' ' + annotation).strip()
                    encoding[name] = {'contentType': 'image/jpeg, image/png, image/webp, image/gif'}
            if encoding:
                multipart['encoding'] = encoding
