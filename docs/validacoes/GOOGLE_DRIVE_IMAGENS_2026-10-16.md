# Imagens no Google Drive — 16/10/2026

Etapa posterior concluída em 17/10/2026: [migração completa de imagens e remoção das pastas locais](GOOGLE_DRIVE_IMAGENS_COMPLETA_2026-10-17.md). O relatório posterior registra o estado atual, incluindo as imagens fixas e o catálogo externo.

## Situação da entrega

Implementação concluída e validada em ambientes isolados. Em 17/10/2026, o proprietário concluiu o consentimento OAuth, as seis áreas do Drive passaram na verificação e as 13 imagens locais elegíveis foram migradas para WebP no Drive real. A leitura das 13 imagens confirmou formato, dimensões, tamanho e SHA-256. Os originais locais e os registros das 49 tabelas de negócio foram preservados.

O projeto OAuth está Externo em modo de teste, com somente a conta autorizada cadastrada como testadora. Essa configuração permite a validação real, mas o refresh token desse modo expira em sete dias; preparar o OAuth para produção continua pendente para uso contínuo. [Política do Google](https://developers.google.com/identity/protocols/oauth2#expiration).

A pasta `cortae` e suas subpastas foram criadas na conta conectada e verificadas por leitura dos metadados. Somente o proprietário consta nas permissões observadas. O mapa de pastas e o caminho esperado da credencial estão configurados localmente, fora do código publicado. Uma chave de API isolada não substitui a autorização OAuth para arquivos privados.

```text
cortae/
  perfil/
  barbearia/
  visagismo/
    cortes/
    fotos/
    resultados/
  marketplace/
```

## Funcionamento

O backend decodifica o arquivo enviado, valida seu conteúdo e limita cada imagem a 10 MB e 24 megapixels. Corrige a orientação EXIF, preserva transparência, remove metadados e reduz dimensões. A saída é WebP; o codificador compara alternativas com e sem perdas e escolhe o arquivo menor. Fotos de perfil usam limite de 512 pixels; as demais, normalmente 1600 pixels. WebP e redimensionamento não garantem redução para toda imagem já otimizada.

O Firebird guarda referência do provedor, ID do arquivo, área, proprietário, posição, MIME, dimensões, tamanho e hash. Os bytes ficam no provedor. Site e aplicativo pedem as imagens pela API do Cortaê; credenciais e links privados do Google não são entregues ao cliente.

Uploads de perfil, logos, galerias, cortes, fotos de visagismo, resultados gerados e produtos usam o mesmo serviço. O marketplace aceita até oito fotos no total, com prévia e remoção no site e seleção pela galeria no aplicativo. Requisições JSON com URLs HTTPS continuam aceitas; arquivos novos usam multipart com `dados` JSON e `imagens`.

Fotos e resultados privados de visagismo exigem vínculo com a sessão antes da leitura no provedor. Mudanças de perfil e de produto compartilham a transação do cadastro. Falhas tentam remover o upload novo e preservam a referência anterior. Arquivos substituídos são revogados e sua limpeza remota é recuperável. Uma falha de rede durante uma operação distribuída ainda pode deixar arquivo privado pendente de limpeza; não existe transação única entre Firebird e Google Drive.

O aplicativo descarta a preparação e o resultado do salvamento quando muda a conta, a sessão, o servidor ou a tela. A API também confere a sessão esperada antes de capturar as credenciais e enviar a requisição.

## Testes finais

| Verificação | Resultado |
|---|---|
| Backend completo | 434 casos: 390 aprovados e 44 opcionais ignorados; nenhuma falha |
| Site | 103 testes aprovados; lint e build aprovados |
| Aplicativo | 62 testes aprovados; lint e TypeScript aprovados |
| SQL real de imagens e migração | 3 testes aprovados com bancos Firebird temporários criados e descartados |
| HTTP e Firebird em clone externo | 3 testes aprovados: perfil/substituição/revogação, ACL privada e produto multipart com falha de armazenamento |
| Testes escritos pela revisão independente | 18 aprovados na reexecução final: 9 backend, 5 cliente e 4 OAuth |
| Dependências Python | `pip check` aprovado |
| Navegador | Seleção de arquivo, prévia, salvamento e reabertura com duas fotos persistidas; nenhum erro de console observado |

Na validação inicial, os testes de provedor simularam respostas Google; os testes de banco e navegador usaram arquivos sintéticos e armazenamento local de teste em pasta externa. Na ativação real de 17/10, houve verificação das seis pastas, envio/leitura por hash de um WebP sintético e limpeza recuperável somente desse arquivo. Não houve pagamento, envio de e-mail, uso de IA nem compra de etiqueta.

A revisão encontrou e corrigiu: capa que não se recuperava depois de uma URL quebrada; envio de formulário antigo após troca de conta; ACL de credencial que mantinha permissões explícitas extras no Windows; resposta 404 de pasta indisponível convertida incorretamente em erro interno; registro repetido do handler ao reexecutar o ponto de entrada. Os testes externos originais foram reexecutados pelo agente principal após as correções. O teste de componente recebeu somente adaptação do carregamento para executar o novo hook real.

## Migração existente

O inventário inicial encontrou 13 imagens locais de visagismo. Após backup e verificação da restauração, a aplicação migrou as 13 imagens com zero erros. Os bytes originais somavam 708.743; os WebP armazenados somam 242.848, redução de 65,7%. Todas foram lidas de volta do Drive e verificadas. O endpoint de foto privada continuou retornando 403 sem autenticação. Um novo inventário encontrou zero imagens pendentes e 13 já gerenciadas, sem repetir uploads.

Outras 86 referências foram classificadas como ausentes localmente ou externas e não foram alteradas. Não foram criadas fotos substitutas para referências ausentes nem baixadas imagens externas.

A aplicação exige identificação explícita do banco, backup externo declarado e credencial Google válida. Mantém os arquivos originais e os nomes usados pelas referências antigas, registrando um alias para o novo conteúdo WebP. A execução é idempotente, revalida vínculos e usa travas antes de confirmar cada imagem. A existência do arquivo de backup não comprova sua restauração; o operador deve verificá-la antes de aplicar.

Em 17/10/2026, com confirmação explícita do proprietário, foi adicionado um segredo ao cliente OAuth existente Cortae Drive, preservando o anterior. O novo segredo foi salvo no .env local do backend e no JSON Desktop protegido fora do projeto; a conferência local confirmou que os valores correspondem. O proprietário concluiu o consentimento no navegador padrão, e a credencial de acesso contínuo foi salva em arquivo privado fora do projeto. Nenhum segredo foi incluído neste relatório.

A primeira tentativa de consentimento retornou `403 org_internal`. Com confirmação explícita do proprietário, o público OAuth do app Corte, projeto Onglogin, foi corrigido para Externo em modo de teste e somente sua conta foi adicionada à lista de testadores. A nova autorização foi concluída com sucesso.

Foi produzido um backup consistente pelo serviço Firebird e restaurado em um novo banco isolado. A leitura de todas as 49 tabelas restauradas somou 152 registros. Evidência: `production-backup-20261017-000758/verification.json`, na pasta externa de evidências. O banco principal não foi alterado por esse procedimento.

A migração do esquema foi ensaiada no clone restaurado, preservando a contagem das 49 tabelas originais, antes da aplicação no banco principal. Evidência agregada da ativação e leitura real: `activation-real-drive.json`, na pasta externa de evidências. Não foram refeitas alterações no código durante a ativação; os resultados da suíte acima permanecem os da validação anterior.

Pendente para operação contínua: preparar o app OAuth para produção segundo as exigências do Google, evitando a expiração de sete dias do modo de teste. Os clientes do site e aplicativo não configuram essa conexão; ela pertence ao servidor.

Evidências locais: `C:\Users\mathe\Documents\Backups-Cortae\drive-images-20261016`, incluindo logs, revisões, clone de QA e `product-images.png`.

## Referências técnicas

- [Google: configuração OAuth em Python](https://developers.google.com/workspace/drive/api/quickstart/python).
- [Google: escopos e acesso por aplicativo](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).
- [Google: upload de arquivos](https://developers.google.com/workspace/drive/api/guides/manage-uploads) e [download](https://developers.google.com/workspace/drive/api/guides/manage-downloads).
- [Pillow: suporte a WebP](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#webp).

Veja o [guia de configuração](../integracoes/GOOGLE_DRIVE_IMAGENS.md).
