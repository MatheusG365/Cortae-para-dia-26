# Migração completa de imagens — 17/10/2026

## Resultado

As 32 imagens locais disponíveis e 45 imagens externas distintas do catálogo estão armazenadas em WebP no Drive privado: 77 arquivos. Os 45 arquivos do catálogo atendem a 46 referências de cortes; duas referências usavam a mesma URL. Não restam URLs HTTPS externas no catálogo cadastrado durante esta execução.

| Área | Arquivos |
|---|---:|
| Fotos privadas de visagismo | 13 |
| Fotos, banners e logos do site | 16 |
| Fotos, fundo e logo de conteúdo do app | 3 |
| Referências de cortes | 45 |
| Total | 77 |

As 32 imagens locais somavam 8.916.950 bytes; os arquivos convertidos somam 1.155.434 bytes, redução de 87,0%. A comparação não inclui os originais externos, que não foram gravados no disco do projeto.

## Código e acesso

O Firebird mantém referências, proprietário, área, dimensões, MIME, bytes e SHA-256. A API lê os arquivos privados do Google. As rotas públicas `/midia/site/<nome>` e `/midia/mobile/<nome>` atendem apenas suas duas áreas de conteúdo fixo. Fotos privadas de visagismo continuam protegidas pelas relações e permissões existentes.

Foram atualizados Header, Footer, Home, fundos de Home/login/cadastro, favicon e logo do login mobile. O site respeita `VITE_API_URL` e o proxy, incluindo imagens no CSS. O aplicativo usa a API inicializada automaticamente, acompanha mudanças do servidor e apresenta texto acessível quando a logo falha.

Foi corrigida a consulta de imagens do catálogo, que exigia a presença de um arquivo local mesmo quando a foto estava no Drive. Com o provedor Google, a aplicação não consulta o disco como fallback e não recria as pastas de imagens na inicialização. O provedor local continua disponível apenas como configuração explícita de desenvolvimento.

A importação externa utiliza o downloader HTTPS já protegido contra SSRF, limites de tamanho e redirecionamentos revalidados. O download acontece antes das travas; a URL é conferida novamente antes de confirmar upload e alteração do cadastro na mesma transação. Uma falha temporária ocorreu na migração de um corte; uma segunda execução migrou somente a referência pendente, com sucesso.

## Retirada das imagens locais

Antes da retirada, foi gerado um ZIP com os 38 arquivos encontrados, incluindo os seis ícones nativos preservados. A leitura do ZIP e os hashes de todos os arquivos foram conferidos. O backup consistente do Firebird foi restaurado em uma base isolada: 51 tabelas e 165 registros antes da migração complementar.

Após conferir os bytes no Drive, foram retirados do projeto:

- `Backend/uploads`, contendo os 13 originais de visagismo;
- `Frontend/public`, contendo as 16 imagens fixas;
- `Cortae_mobile-main/assets/logo-cortae.png`, `fundo-login.png` e `Banner 1.png`.

Os originais foram preservados fora do projeto, em `C:\Users\mathe\Documents\Backups-Cortae\drive-images-20261017-all\removed-from-project`, além do ZIP `before-all-images.zip`. O build do site foi refeito após a retirada, eliminando as cópias antigas de imagens em `dist`.

Permanecem os seis arquivos necessários aos ícones e à abertura do build nativo, conforme o escopo confirmado pelo proprietário. O cache do Expo contém apenas uma miniatura do favicon nativo. Nenhuma foto, banner ou logo de conteúdo permanece nos diretórios de execução do projeto, excluídas dependências instaladas.

## Verificações após a retirada

| Verificação | Resultado |
|---|---|
| Backend | 444 testes: 400 aprovados, 44 opcionais ignorados, zero falhas |
| Site | 106 testes aprovados; lint e build aprovados |
| App | 66 testes aprovados; TypeScript, lint e exportação web aprovados |
| Revisão independente | 10 testes backend e 3 testes de contrato entre clientes e API aprovados |
| Imagens fixas pela API e proxy do site | 19 respostas HTTP 200, MIME WebP, tamanho e SHA-256 conferidos |
| Fotos privadas | 13 respostas HTTP 403 sem login; bytes lidos do Drive e conferidos pelo serviço interno |
| Cortes pelo endpoint público | 45 respostas HTTP 200, MIME WebP e hashes conferidos |
| Catálogo | HTTP 200 com 46 URLs do Drive resolvidas pela API, sem depender de arquivos locais |
| Integridade de negócio | Hashes das 49 tabelas originais preservados, excluindo apenas a coluna de referência de imagem dos cortes, cuja alteração era prevista |
| Saúde da API | Banco principal e banco de auditoria disponíveis, estado pronto |
| Novo inventário | Zero imagens elegíveis pendentes; 78 referências gerenciadas para 77 arquivos |
| Navegador | Home com banner, logos e ilustrações; login web com fundo remoto; login do app exportado com logo remota carregada |

O teste visual do app foi realizado na exportação web. O template instalado do Expo 57 habilita WebP estático no Android, mas esta etapa não executou um novo teste visual no emulador nem gerou APK.

Os testes automatizados simulam pagamentos, e-mail e IA. Não foram feitos pagamentos reais, chamadas de IA, envios de e-mail ou compra de etiquetas nesta tarefa.

## Pendências existentes

Há 40 referências históricas sem arquivo recuperável nesta instalação: uma imagem de corte, 15 fotos e 24 resultados de visagismo. Elas já estavam ausentes antes da migração; os registros foram mantidos. A migração não inventa fotos pessoais nem substitui resultados antigos por outras imagens.

O OAuth continua Externo em modo de teste, autorizado apenas para a conta aprovada. O refresh token desse modo expira em sete dias; preparar o app para produção continua necessário para operação contínua. [Política oficial do Google](https://developers.google.com/identity/protocols/oauth2#expiration).

## Evidências

Diretório externo: `C:\Users\mathe\Documents\Backups-Cortae\drive-images-20261017-all`.

- `inventory.json`, `before-all-images.zip` e `database/verification.json`;
- `readback-before-removal.json`, `http-after-removal.json` e `catalog-and-business-verification.json`;
- `backend-after-removal.log`, `frontend-after-removal.log`, `frontend-build-after-removal.log`, `mobile-after-removal.log` e `mobile-export.log`;
- `independent-review/REVIEW.md` e seus testes;
- `site-sem-imagens-locais.png`, `login-sem-imagens-locais.png` e `mobile-sem-imagens-locais.png`.

Nenhuma credencial foi incluída nesta documentação.
