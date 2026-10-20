# Imagens em outra instalação — 20/10/2026

## Causa e correção

O computador original possuía a autorização privada do Google no ambiente do
backend. Outro computador recebia código e banco pelo Git, mas não essa
autorização. As referências antigas usavam o provedor autenticado `google_drive`,
por isso a leitura devolvia HTTP 503 nessa instalação.

Foi implementado o provedor explícito `public_google_drive`, de leitura anônima,
para arquivos de apresentação pública. Cada imagem foi publicada individualmente
como leitor por link, sem publicar pastas. O backend continua consultando a
referência no Firebird e entregando os bytes pela mesma URL da aplicação.
Nenhuma credencial do Google foi incluída no código ou nos bancos publicados.

Foram atualizadas **64 referências**: 16 imagens do site, três do aplicativo e
45 do catálogo de cortes. Todas tiveram leitura anônima, tamanho, SHA-256 e
formato WebP conferidos antes da mudança de provedor no banco. Aliases,
proprietários, slots, hashes e demais dados foram preservados.

As **27 referências privadas** — 21 fotos e seis resultados de visagismo —
continuam no provedor autenticado, com autorização de usuário nas rotas. Nenhum
ID de arquivo público coincide com uma referência privada do banco. As áreas
públicas possíveis são site, mobile, perfil, barbearia, marketplace e catálogo;
fotos e resultados privados não podem ser incluídos nessa configuração.

## Escrita e transporte

Novos uploads continuam usando OAuth no servidor. Nas áreas configuradas como
públicas, o envio é seguido da permissão individual e da gravação da referência.
Falha na publicação preserva a imagem anterior. Limpeza e substituição usam o
transporte autenticado. O leitor anônimo não envia arquivos nem altera permissões.

O leitor aceita somente IDs registrados e endpoints HTTPS exatos do Google,
limita redirecionamentos e tamanho e recusa login, HTML ou mudança de ID. Não
usa proxies, autenticação ou cookies do ambiente. O backend confere os bytes
contra os metadados antes de responder com WebP.

Backup do banco foi restaurado e verificado antes da atualização. O recibo
operacional para conferência ou reversão está fora do Git em
`C:\Users\mathe\Documents\Backups-Cortae\drive-public-portable-20261020-134614\publication-receipt.json`.

## Verificações realizadas

- 127 testes focados de imagens aprovados; seis testes do Help também passaram após atualizar seus textos.
- Revisão independente do transporte, da política pública e da proteção das áreas privadas.
- Leitura anônima real dos 64 arquivos com tamanho e SHA-256 corretos.
- QA independente em banco descartável, conexões de leitura e credenciais Google vazias: 22 URLs da API retornaram HTTP 200 com WebP íntegro — todas as 19 imagens fixas e três cortes do catálogo.
- Todas as 27 URLs privadas retornaram HTTP 403 antes de qualquer download; o construtor OAuth foi proibido durante essa verificação.
- Cópia separada do projeto criada a partir do Git, com os FDB publicados e o código revisado, sem credenciais Google. Dependências instaladas foram reutilizadas; dados e configurações da aplicação foram separados.
- Essa cópia iniciou API na porta 5001 e site na 5174 com Firebird 4.0.4.3010/ODS 13.0. No navegador, banner, logos e ilustrações apareceram; os quatro elementos de imagem da página inicial tinham dimensões naturais válidas.
- Snapshots públicos reconstruídos no Firebird 4, sem credenciais Arkhé e com valores sensíveis de auditoria protegidos. Principal preserva 53 tabelas/288 registros; auditoria preserva 4.896 registros.

Não houve teste físico em outro computador ou nova execução em emulador nesta
etapa. A reprodução usou uma instalação separada sem a autorização Google que
causava a dependência. O acesso privado e novos uploads continuam exigindo uma
API central autorizada ou configuração OAuth no servidor responsável.

[Guia do Drive](../integracoes/GOOGLE_DRIVE_IMAGENS.md) ·
[Migração Firebird](FIREBIRD_4_0_4_2026-10-19.md) ·
[Índice](../README.md)
