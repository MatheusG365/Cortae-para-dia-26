# Help e documentação da API — imagens no Drive

Atualização de 17/10/2026. A página `/docs` é implementada em `Backend/api_docs.py`; o contrato OpenAPI passa à versão 2.1.0. `/help`, `/docs`, `/openapi.json` e a consulta de fontes continuam restritos ao administrador.

## Conteúdo atualizado

- Nova seção no Help com etapas da imagem, formulários atendidos, limites, permissões e botões que abrem os documentos das rotas.
- Validação de bytes, formatos estáticos, limites de 10 MB e 24 megapixels, orientação, dimensões, WebP e remoção de metadados.
- Drive privado, referência no Firebird, leitura pela API, aliases antigos e ausência de fallback local no modo Google.
- Produtos, perfil, logo, galeria, cortes, fotos privadas de visagismo, resultados e imagens fixas do site/mobile.
- Links externos preservados como URLs nos novos cadastros; importação explícita de referências existentes pela ferramenta de migração.
- Exceção dos ícones e arquivos de abertura exigidos para o build nativo; aviso condicional sobre OAuth externo em modo de teste.
- Contratos multipart com `foto1` a `foto5`, campo `dados` e arquivos `imagens` do produto, até oito fotos no total.
- Respostas de mídia descritas como bytes `image/webp`, sem confundi-las com JSON. Fotos e resultados privados mantêm as permissões condicionais.
- Entradas multipart aparecem como `Form` no catálogo do Help; erros 400, 403, 404, 413 e 503 são explicados.

O novo resumo é montado sem consultar Drive, dados de negócio ou configurações privadas. Os botões somente selecionam documentos. A tela continua compatível com versões anteriores da API sem o bloco `imagens`.

## Validação

| Verificação | Resultado |
|---|---|
| Backend: imagens, OpenAPI, Help e Help mobile | 40 testes: 39 aprovados, 1 opcional ignorado, zero falhas |
| Frontend | 109 testes aprovados; lint e build aprovados |
| Revisão independente | 4 testes backend e 2 de renderização aprovados |
| Acesso | 401/403 antes de montar catálogo/contrato; cabeçalhos privados preservados nos endpoints protegidos |
| Efeitos externos | Construção do resumo validada com banco de negócio, construtores do provedor e rede proibidos pelos testes |

A revisão corrigiu a descrição dos cabeçalhos do Help, esclareceu que a limpeza de uploads interrompidos é uma tentativa e evitou duplicação de anotações em schemas compartilhados. Os testes independentes foram repetidos após essas correções.

Esta etapa alterou documentação, metadados e apresentação do Help. Não repetiu migração, não alterou armazenamento ou credenciais, não executou integrações reais e não apagou arquivos.

## Evidências

- `C:\Users\mathe\Documents\Backups-Cortae\drive-images-20261017-all\help-docs-tests.log`;
- `C:\Users\mathe\Documents\Backups-Cortae\docs-review-20261017\REVIEW.md` e testes independentes;
- `Backend/API_DOCUMENTATION.md` e [guia de imagens](../integracoes/GOOGLE_DRIVE_IMAGENS.md).
