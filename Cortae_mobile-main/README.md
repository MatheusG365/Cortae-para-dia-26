# Cortaê Mobile

Aplicativo React Native com Expo SDK 57 e Expo Router. Possui áreas separadas para **cliente** e **barbearia**, usando a mesma API Flask e os mesmos dados do site. Não oferece páginas de administrador ou painel do profissional.

O visual segue a referência mobile do Figma: base escura, destaque laranja, tipografia Montserrat e navegação inferior. Páginas de estabelecimento e produtos aplicam o destaque cadastrado pela barbearia, com contraste de texto.

## Executar no Android Studio

1. Instale as dependências nesta pasta: `npm ci`.
2. Inicie a API pelo `Iniciar-Cortae.cmd` da pasta principal. Para iniciar apenas a API, execute `Backend/Iniciar-Backend-Cortae.cmd` na pasta principal.
3. Abra o Device Manager do Android Studio e inicie um emulador.
4. Nesta pasta, execute `npm run android`. O Expo abre o projeto no Expo Go do emulador. O emulador precisa ter acesso à internet para instalar o Expo Go na primeira execução.
5. Entre no aplicativo. Em desenvolvimento, ele usa automaticamente o computador que está servindo o projeto pelo Expo e conecta à API na porta 5000. Não é necessário digitar o IP. O usuário não tem página, botão, campo ou opção avançada para alterar o servidor; essa definição pertence ao projeto.

Se o Metro abrir somente em IPv6 e o emulador não encontrar o projeto, use:

```powershell
node --dns-result-order=ipv4first node_modules/expo/bin/cli start --localhost
```

Depois, abra o projeto no Expo Go pelo endereço mostrado no terminal. Os diretórios nativos `android/` e `ios/` são gerados pelo Expo, quando necessários; não precisam existir para usar o Expo Go. Para um build de desenvolvimento local independente do Expo Go, use `npx expo run:android`, com o SDK e o JDK do Android Studio configurados.

## Celular físico e produção

No celular físico, abra o projeto pelo QR do Expo na mesma rede do computador. O app obtém o endereço do computador pela conexão do Expo. Se o IP do computador mudar, abra novamente o projeto servido por esse computador; não é preciso alterar o código ou salvar outro IP. A API precisa estar em execução e acessível nessa rede. O modo automático não procura servidores aleatórios na internet.

O emulador Android usa o endereço especial do computador quando o Expo está em localhost. No Expo web em desenvolvimento, a API usa o hostname atual do navegador. `EXPO_PUBLIC_API_PORT` permite informar uma porta de desenvolvimento diferente, uma vez ao iniciar o Expo. Em produção web, o caminho `/api` deve ser encaminhado ao Flask pelo servidor que hospeda o app.

Para um APK publicado, defina `EXPO_PUBLIC_API_URL` com o domínio HTTPS da API antes de gerar o aplicativo, conforme `.env.example`. O endereço é configurado uma vez para a distribuição; os clientes não precisam informar o IP. Sem o servidor de desenvolvimento do Expo, o app instalado não consegue deduzir qual servidor da internet pertence ao Cortaê. Esse endereço é público no aplicativo: **nunca coloque Client Secret, senha de banco ou chave privada em variáveis `EXPO_PUBLIC_*`**. Credenciais da Arkhé e de outros serviços permanecem exclusivamente no backend.

Links de agendamento compartilhados pela barbearia usam `EXPO_PUBLIC_WEB_URL`. Configure essa variável com o endereço público do site, sem barra final. Se não estiver definida, o app orienta a configuração em vez de compartilhar um endereço local incorreto.

## Funcionalidades

| Cliente | Barbearia |
|---|---|
| Cadastro, confirmação, recuperação de senha e perfil | Painel geral e agenda diária/semanal |
| Busca de estabelecimentos e loja integrada de cada um | Criação, remarcação, cancelamento, conclusão e faltas |
| Serviços, profissional, horários e lista de espera | Equipe, convites, serviços, vínculos, turnos, preços e comissões |
| Catálogo de cortes, detalhes, decisão no atendimento e visagismo opcional | Clientes, observações e histórico |
| Histórico, cancelamento, remarcação e avaliação de atendimentos | Receitas, despesas, categorias, recebimentos e comissões manuais |
| Loja geral, variações, favoritos, desejos e carrinho | Produtos, fotos por URL, estoque, variações, fornecedores e cupons |
| Cupom, endereço, cotação, pedido e histórico de compras | Pedidos, entregas, vendas, ranking, avaliações, metas e relatórios |
| Consulta de cobrança e QR/cópia do código recebido da API | Cores, contatos e informações públicas do estabelecimento |

O login nativo recebe um Bearer token somente para os perfis cliente e barbearia. O token fica no SecureStore; a sessão salva é validada no servidor antes de liberar a área privada. O login do site continua com cookie HttpOnly. Alterar o servidor encerra a sessão local; um token armazenado para outro endereço não é encaminhado ao novo servidor.

Confirmações, avisos, detalhes e leitura de termos usam o diálogo visual do Cortaê, com fundo escuro, tipografia do app, ações claras e rolagem para textos longos. Fechar ou voltar cancela a ação. A fila de diálogos é invalidada quando a sessão muda, evitando executar uma confirmação antiga para outra conta.

O cadastro de profissional cria um convite para ativar o acesso. Esse perfil usa o painel do profissional no site; não existe uma área desse perfil neste aplicativo. E-mails e links públicos dependem da configuração do backend.

## Limites das integrações

- O código `ARKHEPIX:` representa pagamento **interno Arkhé**. Gerar um QR desse texto não o transforma em Pix bancário interoperável. O app informa essa distinção.
- A criação de cobrança sempre exige ação explícita. Cobrança existente é consultada e reapresentada, sem criar outra. Pagamentos parciais de agendamento são tratados com o estabelecimento, evitando cobrar novamente o valor integral.
- Pagamento de comissão e recebimentos manuais são registros locais; não fazem transferência bancária.
- Visagismo real requer configuração da API e pode consumir créditos. Câmera/galeria só são utilizadas após ação do usuário; a foto é enviada na ação de análise/simulação.
- Cotação e rastreio dependem do Melhor Envio. O app não compra etiquetas nem consome envios automaticamente. A emissão externa permanece sujeita à conta e às permissões configuradas.
- Termos e taxa de plataforma seguem a política publicada pelo backend. Política em rascunho não é apresentada como taxa ativa.
- WhatsApp continua fora do escopo. Pagamento real, e-mail entregue, imagem gerada por IA e postagem física não são comprovados por testes locais.

## Estrutura

```text
src/app/                 Rotas públicas e layouts protegidos
src/app/cliente/         Área do cliente
src/app/barbearia/       Área de gestão do proprietário
src/features/           Fluxos e componentes de cada área
src/lib/                API, armazenamento de sessão e carregamento de dados
src/ui.tsx               Componentes visuais compartilhados
src/theme.ts             Cores e fontes
assets/                  Identidade visual e imagens locais
tests/                   Regressões de regras, pagamento e concorrência da sessão
```

O ponto de entrada é `expo-router/entry`, definido em `package.json`. A implementação inicial de duas telas foi arquivada fora do projeto antes da substituição; o app atual usa `src/app/`.

## Verificações

```powershell
npm run lint
npm run typecheck
npm test
npx expo-doctor
npx expo export --platform android
```

Os testes automatizados não pagam cobranças, enviam e-mail, geram imagens por IA ou compram etiquetas. Para testes HTTP com escrita, use cópias descartáveis do Firebird e provedores bloqueados/simulados. Não utilize os bancos reais como fixtures.

Referências técnicas: [Expo SDK 57](https://docs.expo.dev/versions/v57.0.0/), [Expo Router](https://docs.expo.dev/router/introduction/) e [emulador Android](https://docs.expo.dev/workflow/android-studio-emulator/).
