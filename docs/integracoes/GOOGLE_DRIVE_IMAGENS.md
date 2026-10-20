# Imagens no Google Drive: leitura pública e conteúdo privado

O backend valida o conteúdo real das imagens, aplica a orientação EXIF, reduz a resolução e grava WebP sem os metadados originais. As selfies e os resultados de visagismo ficam privados no Drive. As áreas de apresentação pública podem publicar cada arquivo individualmente, sem publicar pastas. O Firebird guarda a referência, o proprietário, a área, o tamanho, a resolução, o hash e o estado. Site e aplicativo continuam pedindo a imagem pela API do Cortaê, preservando as regras de acesso de cada rota.

Com o provedor Google Drive, a aplicação resolve as imagens pelo Firebird e pelo Drive, sem consultar arquivos locais como alternativa. O provedor `local` permanece uma opção explícita de desenvolvimento. Uma referência removida deixa um registro de exclusão. A substituição entra na mesma transação dos dados do cadastro; se a gravação falhar, o sistema preserva a referência anterior e tenta limpar somente os novos uploads.

## Ler as imagens públicas em outro computador

A ausência de `GOOGLE_DRIVE_CREDENTIALS_JSON` e `GOOGLE_DRIVE_CREDENTIALS_FILE` não permite ler um arquivo com `IMAGE_ASSET.PROVIDER=google_drive`: esse provedor é autenticado. Copiar somente código e banco não copia a autorização do servidor. O erro correspondente é HTTP 503; o backend não troca automaticamente de provedor nem busca fotos privadas por links públicos.

O provedor explícito `public_google_drive` resolve essa dependência para `site`, `mobile`, `perfil`, `barbearia`, `marketplace` e `visagismo/cortes`. Ele aceita somente um ID de arquivo já registrado no Firebird. A leitura anônima usa os endpoints HTTPS de download do Drive, não a API `alt=media` sem chave. Redirecionamentos são manuais, limitados a três e aos hosts exatos `drive.usercontent.google.com` e `drive.google.com`, mantendo o mesmo ID. Login, outro host, caminho, porta ou ID são recusados. Proxies e credenciais do ambiente não são utilizados; cookies não seguem entre etapas. Respostas HTML, tamanhos excessivos e conteúdo que não corresponde ao tamanho/SHA-256/WebP registrado são rejeitados.

Esse provedor não envia arquivos nem cria permissões. Nunca o configure como `IMAGE_STORAGE_PROVIDER` para uploads. A origem continua sendo o Google Drive; nenhuma cópia local é usada como fallback. Rotas públicas do Cortaê continuam entregando os bytes e não expõem links ou IDs do Drive nos cabeçalhos.

### Publicar referências existentes: operação administrativa

Esta atualização de código não altera as permissões nem os metadados de arquivos existentes. O administrador deve fazer uma operação explícita, com um backup do banco restaurado e verificado:

1. Produza um manifesto das referências ativas das seis áreas públicas, contendo área, nome, ID, provedor anterior, tamanho e SHA-256. Preserve também as permissões anteriores e o ID de cada permissão criada pela operação. Não registre tokens ou credenciais no manifesto.
2. Exclua do plano qualquer ID que também apareça em uma referência ativa de `visagismo/fotos` ou `visagismo/resultados`. Essa interseção bloqueia tanto a publicação de uploads quanto a leitura anônima, mesmo se um registro estiver classificado incorretamente.
3. Com OAuth do administrador, conceda apenas `type=anyone`, `role=reader`, `allowFileDiscovery=false` em cada arquivo aprovado. Não compartilhe a pasta principal, pastas de área, selfies ou resultados.
4. Baixe cada arquivo sem OAuth e confira tamanho, SHA-256 e WebP. Somente depois marque as referências verificadas como `public_google_drive`. Preserve aliases, nomes, proprietários, slots e hashes. Falhas permanecem no provedor anterior para revisão; não marque uma permissão não confirmada como sucesso.
5. Para reverter, restaure os provedores anteriores a partir do manifesto e remova somente as permissões criadas pela operação, usando seus IDs. Não remova permissões anteriores do proprietário e não restaure cegamente um banco ativo com dados novos.

Fotos e resultados privados continuam exigindo autenticação e vínculo de proprietário nas rotas do Cortaê e autorização Google no servidor. Um clone sem OAuth não recebe esse conteúdo privado. Use uma API central autorizada ou configure OAuth no servidor que precisa atendê-lo.

### Novos uploads em áreas públicas

`IMAGE_STORAGE_PROVIDER=google_drive` continua sendo o provedor de escrita. `GOOGLE_DRIVE_PUBLIC_AREAS` lista as áreas que devem receber publicação individual após o upload autenticado; o padrão são as seis áreas acima. Um valor vazio mantém todos os novos uploads privados. Incluir fotos ou resultados privados é um erro de configuração e bloqueia o upload; não amplia a política de publicação.

A sequência é: validar/comprimir, enviar com OAuth, confirmar ausência de referência privada ativa para o ID, criar permissão individual de leitura, registrar `public_google_drive` e concluir a transação de negócio. Falha de publicação remove somente o novo upload e conserva a referência anterior. Rollback remove o novo arquivo através do provedor autenticado; a substituição move o arquivo anterior para a lixeira somente depois do commit, também com OAuth. A leitura pública nunca realiza essas mutações.

O Drive e o Firebird não formam uma transação distribuída. Uma interrupção pode deixar um upload órfão, inclusive já público nas áreas configuradas. Preserve os registros operacionais e faça a limpeza administrativa por ID; não publique pastas para corrigir uma falha de entrega.

## Autorizar a conta usada pelo servidor

### Acesso pelo site e aplicativo em qualquer aparelho

Uma implantação pode usar uma API central hospedada; a autorização do Drive fica somente nesse servidor. Um clone em outro computador também consegue ler os arquivos explicitamente registrados como `public_google_drive`, sem receber a autorização privada. Uploads e conteúdo privado continuam exigindo OAuth no servidor; clientes e barbearias não criam credenciais Google.
Configure `VITE_API_URL` no site e `EXPO_PUBLIC_API_URL` no build do aplicativo
com a URL HTTPS dessa API. Um backend acessível apenas no computador de
desenvolvimento não passa a estar hospedado ao publicar o código no GitHub.

O backend aceita `GOOGLE_DRIVE_CREDENTIALS_JSON`: o conteúdo completo da
autorização `authorized_user`, incluindo `refresh_token`, guardado no cofre de
segredos ou ambiente privado da hospedagem. Assim, não depende de um caminho
Windows nem de um arquivo de credenciais em cada aparelho. O JSON é obtido após
o consentimento descrito abaixo; Client ID e Client Secret sozinhos identificam
o aplicativo, mas não concedem acesso às imagens. Veja o
[fluxo OAuth oficial](https://developers.google.com/identity/protocols/oauth2/web-server#offline).

Quando preenchido, esse segredo tem prioridade sobre
`GOOGLE_DRIVE_CREDENTIALS_FILE`. Um JSON inválido falha explicitamente, sem usar
uma credencial antiga como alternativa. Não publique Client Secret ou refresh
token no código, nos builds ou em exemplos. O cache interno identifica o JSON
por SHA-256; não inclui o segredo nas chaves.

`Backend/google_drive_folders.json` já contém os IDs das oito áreas existentes
na pasta Cortaê informada pelo responsável. Esses IDs são configuração, não
autorização. O mapa padrão é usado quando `GOOGLE_DRIVE_FOLDER_IDS` está vazio;
um JSON explícito o substitui e `GOOGLE_DRIVE_FOLDER_IDS_FILE` tem prioridade
sobre ambos. Remova um valor legado literal `{}` para usar o mapa padrão.
Nenhuma pasta é criada ou tornada pública por essa configuração.

Se o Google retornar `deleted_client`, o cliente vinculado ao refresh token foi
excluído. Autorize novamente um cliente válido: trocar somente ID e Secret na
autorização antiga não transforma o refresh token em uma nova autorização.
O consentimento é feito uma vez pelo responsável pelo servidor, não a cada
instalação do aplicativo. Revogação ou expiração podem exigir novo consentimento.

### Consentimento inicial

Esta configuração pertence ao servidor. Não existe uma tela de conexão para clientes ou barbearias e nenhuma credencial vai para o React ou o React Native. A conexão do Google Drive feita em outra ferramenta, inclusive no Codex, não substitui a autorização OAuth do backend.

Para um Drive pessoal, use OAuth de usuário com acesso contínuo. Uma conta de serviço só é aceita pelo backend quando houver um Drive compartilhado configurado; ela não substitui o proprietário de um Drive pessoal.

1. No [Google Cloud Console](https://console.cloud.google.com/), selecione ou crie um projeto de sua conta.
2. Em **APIs e serviços → Biblioteca**, habilite a **Google Drive API**.
3. Abra **Google Auth Platform**. Preencha a identificação do aplicativo, o e-mail de suporte e o contato do desenvolvedor. Para uma conta Gmail, configure o público **Externo**. Se estiver em teste, inclua como usuário de teste a conta que possui a pasta de imagens.
4. Em **Clientes**, crie um cliente OAuth do tipo **Aplicativo para computador / Desktop app**. Baixe o JSON e guarde-o fora da pasta do projeto, por exemplo em `%LOCALAPPDATA%\Cortae\google-drive\client_desktop.json`.
5. Autorize a conta no navegador normal do computador do servidor. O responsável pela conta deve conferir o projeto e os escopos e concluir o consentimento do Google. Se o Google bloquear o aplicativo ou exigir uma verificação, resolva essa exigência no projeto; o sistema não contorna as políticas do Google.

O cliente OAuth deve ser do Google. Um Client ID/Secret do Figma ou de outro provedor não serve para acessar o Drive. Não cole o JSON, o segredo ou o refresh token em mensagens, no Git ou na documentação.

Na pasta `Backend`, execute no PowerShell:

```powershell
.\.venv\Scripts\python.exe configurar_drive.py --autorizar --cliente-oauth "$env:LOCALAPPDATA\Cortae\google-drive\client_desktop.json" --credenciais "$env:LOCALAPPDATA\Cortae\google-drive\authorized_user.json"
```

O comando abre o navegador padrão e recebe a resposta somente em `127.0.0.1`, em uma porta temporária, com `state` e PKCE S256. O código de autorização não é exibido nem gravado em logs. A credencial é salva atomicamente fora do projeto, com acesso restrito ao usuário do servidor e ao SYSTEM no Windows. Um arquivo existente é preservado; para refazer o consentimento e substituí-lo, use explicitamente `--substituir-credencial`.

O escopo padrão é `drive.file`, que limita o acesso aos arquivos criados pelo aplicativo ou concedidos a ele. **Uma pasta criada por outro cliente OAuth não fica automaticamente acessível só porque a conta Google é a mesma.** Este configurador não implementa Google Picker nem cria pastas alternativas quando uma pasta existente não pode ser lida. [Escopos oficiais do Drive](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

Para usar as pastas já criadas por outro aplicativo, é necessário concedê-las ao mesmo cliente por um fluxo apropriado, ou decidir explicitamente autorizar o escopo amplo `drive`. Nesse segundo caso, refaça a autorização com `--acesso-drive-completo`. Essa opção amplia o acesso à conta, depende do consentimento do proprietário e pode trazer requisitos adicionais de verificação do Google; ela nunca é ativada automaticamente.

```powershell
.\.venv\Scripts\python.exe configurar_drive.py --autorizar --cliente-oauth "$env:LOCALAPPDATA\Cortae\google-drive\client_desktop.json" --credenciais "$env:LOCALAPPDATA\Cortae\google-drive\authorized_user.json" --acesso-drive-completo
```

Projetos OAuth externos em **Testing** que solicitam acesso ao Drive têm refresh tokens com validade de sete dias. Prepare o projeto para produção conforme a política e os requisitos do Google antes de depender dessa autorização continuamente. Mesmo em produção uma autorização pode ser revogada ou expirar por outras razões. [Validade dos refresh tokens](https://developers.google.com/identity/protocols/oauth2#expiration), [OAuth para aplicativos Desktop](https://developers.google.com/identity/protocols/oauth2/native-app).

## Configurar as pastas existentes

Crie ou selecione uma pasta principal privada da conta. O mapa aponta para oito subpastas, uma por área; as pastas de visagismo podem ficar dentro de uma pasta intermediária `visagismo`. As áreas `site` e `mobile` guardam fotos, banners e logos fixos. Mantenha as pastas privadas. A publicação permitida neste documento é individual e restrita às seis áreas públicas; fotos e resultados pessoais nunca são publicados. A API continua controlando suas próprias rotas e referências.

Guarde fora do projeto um JSON com os IDs reais das pastas. O exemplo abaixo mostra somente o formato; os textos de exemplo devem ser substituídos pelos IDs do seu Drive:

```json
{
  "root": "ID_DA_PASTA_PRINCIPAL",
  "perfil": "ID_DA_PASTA_PERFIL",
  "barbearia": "ID_DA_PASTA_BARBEARIA",
  "marketplace": "ID_DA_PASTA_MARKETPLACE",
  "site": "ID_DA_PASTA_SITE",
  "mobile": "ID_DA_PASTA_MOBILE",
  "visagismo": "ID_DA_PASTA_INTERMEDIARIA",
  "visagismo/cortes": "ID_DA_PASTA_CORTES",
  "visagismo/fotos": "ID_DA_PASTA_FOTOS",
  "visagismo/resultados": "ID_DA_PASTA_RESULTADOS"
}
```

Configure somente no ambiente privado do backend:

```dotenv
IMAGE_STORAGE_PROVIDER=google_drive
GOOGLE_DRIVE_CREDENTIALS_FILE=C:/caminho/privado/authorized_user.json
GOOGLE_DRIVE_FOLDER_IDS_FILE=C:/caminho/privado/pastas.json
GOOGLE_DRIVE_SHARED_DRIVE_ID=
GOOGLE_DRIVE_PUBLIC_AREAS=site,mobile,perfil,barbearia,marketplace,visagismo/cortes
```

`GOOGLE_DRIVE_FOLDER_IDS_FILE` aponta para o mapa JSON local e prevalece sobre `GOOGLE_DRIVE_FOLDER_IDS`, que também aceita o JSON diretamente. A chave `root` é usada pelo verificador; as oito chaves de área são usadas nos uploads. A chave intermediária `visagismo` é opcional. Um ambiente que usa conta de serviço precisa informar `GOOGLE_DRIVE_SHARED_DRIVE_ID` e conceder acesso adequado à conta de serviço nesse Drive compartilhado.

## Verificar sem alterar arquivos

```powershell
.\.venv\Scripts\python.exe configurar_drive.py --verificar
```

O comando lê a configuração privada, valida a pasta principal, as oito áreas, a capacidade de adicionar arquivos e se cada área pertence à árvore da pasta principal. Ele não abre Firebird, não envia imagem, não cria pasta, não altera compartilhamento e não apaga arquivo. Se o mapa não tiver `root`, informe `--pasta-raiz ID_EXISTENTE`.

Também é possível informar os arquivos diretamente sem editar o ambiente:

```powershell
.\.venv\Scripts\python.exe configurar_drive.py --verificar --credenciais "C:/caminho/privado/authorized_user.json" --pastas "C:/caminho/privado/pastas.json" --pasta-raiz ID_EXISTENTE
```

A falta de acesso é um erro de configuração, não uma autorização para criar outra pasta. Verifique primeiro a conta, o cliente OAuth e o escopo concedido.

## Teste opcional de envio

Depois de verificar a configuração, o operador pode executar:

```powershell
.\.venv\Scripts\python.exe configurar_drive.py --teste-envio
```

Esse comando verifica as pastas, gera uma imagem WebP sintética de 8 × 8 pixels, envia um único arquivo chamado `cortae-teste-<identificador>.webp`, lê os bytes de volta e compara o SHA-256. Ao terminar, tenta mover **somente esse arquivo recém-criado** para a lixeira do Drive. Não faz exclusão permanente, não usa fotografias de clientes e não altera o banco. Se a limpeza falhar, o comando informa o nome exato do arquivo de teste para uma limpeza manual.

## Migrar os arquivos locais existentes

O inventário é o modo padrão e não envia arquivos. Por padrão considera as referências locais elegíveis. `--incluir-estaticas` adiciona o manifesto de 16 imagens do site e três imagens de conteúdo do aplicativo. `--incluir-referencias-externas` adiciona as referências HTTPS do catálogo de cortes; somente a aplicação efetiva baixa essas referências, usando validação de endereços públicos, conexões limitadas e redirecionamentos revalidados.

```powershell
.\.venv\Scripts\python.exe migrar_imagens_drive.py --planejar
```

Antes de aplicar, o operador deve produzir um backup consistente do Firebird e verificar sua restauração. A existência de um arquivo não comprova que o backup é restaurável. Faça primeiro uma execução em uma base isolada com a mesma estrutura e configuração da produção.

```powershell
.\.venv\Scripts\python.exe migrar_imagens_drive.py --aplicar --banco "C:/caminho/exato/CORTAE.FDB" --backup "C:/backup/externo/cortae-verificado.fbk"
```

O comando exige a identidade exata do banco configurado e um backup externo existente e não vazio. Ele registra metadados do armazenamento e converte as imagens em WebP no Drive. Preserva os nomes legados como aliases para manter as URLs e permissões de sessões já cadastradas; o conteúdo convertido é entregue com MIME WebP. Os arquivos locais originais não são apagados. A execução é idempotente para referências já migradas. Revise o inventário e o resultado antes de considerar qualquer remoção manual dos originais.

Para incluir as imagens fixas, acrescente `--incluir-estaticas --raiz-site "C:/projeto/Frontend/public" --raiz-mobile "C:/projeto/Cortae_mobile-main/assets"`. O manifesto mantém os seis ícones e arquivos de abertura usados pelo build nativo. O arquivo de origem `Banner 1.png` usa o alias público `banner-1.png`.

Para incluir o catálogo externo, acrescente `--incluir-referencias-externas`. Cada URL é baixada antes das travas de banco; a referência é conferida novamente antes do upload e da atualização. Falhas mantêm a referência anterior. Uma mesma URL usada por dois cortes é migrada para um arquivo compartilhado.

Fotos, logos e fundos fixos são entregues por `/midia/site/<nome>` e `/midia/mobile/<nome>`. Essas rotas públicas aceitam somente as duas áreas de conteúdo fixo e somente arquivos registrados. O site usa o proxy e `VITE_API_URL`, inclusive para CSS e favicon. O aplicativo usa a conexão automática da API. Credenciais e IDs do Drive não são entregues aos clientes.

Antes de retirar uma pasta local, verifique um backup dos arquivos e a restauração do banco, confira a leitura e o SHA-256 no Drive e execute os testes com os diretórios fora do projeto. Refaça o build do site após retirar `Frontend/public`, para eliminar as cópias antigas de `dist`. O backend configurado para Drive não recria a árvore de uploads ao iniciar. Referências históricas sem arquivo de origem exigem recuperação de outro backup ou novo envio pelo usuário.

## Limites operacionais

Uploads novos precisam da autorização do Google e das tabelas de metadados no banco. A migração de esquema e a migração dos arquivos existentes devem ser executadas pelo operador após backup e validação em uma base isolada. O configurador deste documento não migra o banco nem os arquivos existentes.

Sem configuração válida, a API devolve um erro de armazenamento com mensagem própria; não grava silenciosamente no disco como alternativa ao Drive. `IMAGE_STORAGE_PROVIDER=local` é uma escolha explícita de desenvolvimento, não a configuração de produção.

O Drive e o Firebird não participam de uma transação distribuída. A aplicação preserva a referência anterior até o commit e tenta remover uploads não confirmados; interrupções de rede ou do processo podem deixar arquivos órfãos, privados ou já publicados individualmente conforme a área, para uma limpeza posterior. Não trate uma falha de comunicação como confirmação de upload ou de exclusão.

As imagens são servidas pela API do Cortaê. URLs públicas originais continuam públicas somente quando já faziam parte da apresentação do estabelecimento; selfies e resultados privados mantêm suas regras de autenticação. IDs do Drive, refresh tokens e Client Secret não precisam ser enviados ao navegador ou ao aplicativo.
