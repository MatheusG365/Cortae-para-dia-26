# Mobile em JavaScript — 18/10/2026

O aplicativo já utilizava React Native com Expo. A pedido do responsável, a linguagem das fontes foi convertida de TypeScript para JavaScript, mantendo React Native, Expo SDK 57, Expo Router, componentes nativos e as áreas de cliente e estabelecimento.

## Alterações

- 89 fontes convertidas: 75 `.jsx` e 14 `.js`. Nenhum `.ts` ou `.tsx` em `Cortae_mobile-main/src`.
- Preservadas 43 telas e 3 layouts de navegação. Nenhuma área de administrador foi adicionada ao app.
- Removido `tsconfig.json`; incluído `jsconfig.json` para o editor. TypeScript e `@types/react` deixaram de ser dependências diretas. Ferramentas externas do Expo/React Native ainda podem depender deles internamente.
- Testes executam as fontes JavaScript reais usando Babel; mocks continuam limitados aos serviços nativos, renderização e HTTP. Corrigida a interoperabilidade do import React no executor dos testes de imagem após a conversão.
- `npm run check` analisa a sintaxe JS/JSX e resolve os imports locais das 89 fontes. `npm run typecheck` é um alias desse comando para compatibilidade; não promete análise estática de tipos.
- Help mobile atualizado para os caminhos `.js`/`.jsx`, incluindo layouts e dependências compartilhadas. Leitura de fontes continua exclusiva do administrador. Testes de segurança para sanitização de arquivos TypeScript externos/sintéticos foram preservados.
- README e instruções do projeto passam a orientar o uso de JavaScript/JSX.

## Resultados

| Verificação | Resultado |
|---|---|
| Testes mobile após conversão e formatação | 66 aprovados |
| Contratos da API mobile, com banco/provedores simulados | 36 aprovados |
| Catálogo e segurança do Help mobile | 12 aprovados |
| Lint do aplicativo | Aprovado |
| Sintaxe e imports JavaScript/JSX | 89 fontes aprovadas |
| Expo Doctor | 21/21 verificações aprovadas |
| Exportação Android/Hermes | Aprovada, 1.684 módulos |
| Comparação das árvores de código antes/depois | 89 fontes equivalentes, ignorando tipos, formatação, comentários e agrupamento de texto JSX adjacente |

A comparação de código não substitui os testes: ela verifica que a conversão e a formatação não alteraram a lógica emitida das fontes. Um trecho de espaço + “minutos” foi agrupado pelo formatador no mesmo texto JSX, sem alteração de conteúdo.

## Execução Android

Executado no emulador `Medium_Phone`, Android 17 x86_64, usando Expo Go compatível com SDK 57. Foram verificados:

- Abertura do app, tela de login, erro de campos vazios e formulário de cadastro.
- Login com cliente fictício, tela Descobrir, agenda, loja, perfil, confirmação visual e saída.
- Login com estabelecimento fictício, painel geral, agenda, Minha loja, Gestão, confirmação visual e saída.
- Logs `ReactNativeJS:E` e `AndroidRuntime:E` sem erros do aplicativo durante essas verificações.

As duas contas e os dados das listas são fictícios. A API temporária, ligada somente em `127.0.0.1:5055`, não usa banco de dados e bloqueia escritas de negócio. Nenhum cadastro real, aceite jurídico, pedido, cobrança, envio, e-mail ou análise por IA foi criado. A API de teste foi encerrada e a conexão normal de desenvolvimento foi restaurada ao final.

Durante o teste houve uma desconexão do Metro na sua reinicialização; o encaminhamento ADB foi restabelecido e o app foi reaberto. O buffer de crash do emulador também registrou uma falha do serviço Bluetooth do Android, não do processo React Native. Isso não foi apresentado como erro corrigido no código do Cortaê.

## Alertas e limites

`npm audit` encontrou 29 entradas de vulnerabilidade na árvore de dependências, incluindo propagação dos mesmos avisos para pacotes dependentes: 19 altas e 10 moderadas. Isso não equivale a 29 falhas distintas nas telas. O diagnóstico do Expo passou, mas não é uma auditoria de segurança.

- [braces: recursão sem limite](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm): sem versão corrigida publicada no momento da verificação; presente na cadeia do Metro.
- [node-forge: validação RSA](https://github.com/advisories/GHSA-86w9-cpqp-85rv): versão instalada 1.4.0, também a mais recente consultada, ainda afetada; dependência das ferramentas Expo.
- [decode-uri-component: decodificação de entrada inválida](https://github.com/advisories/GHSA-vcc3-ghjq-m6fr): versão afetada trazida por `query-string` do Expo Router. A versão nova consultada muda de CommonJS para ESM; não foi forçado um override incompatível nem uma troca de SDK nesta conversão.
- [uuid: limites de buffer em v3/v5/v6](https://github.com/advisories/GHSA-w5hq-g745-h8pq): versão antiga trazida por `xcode`, cujo uso localizado nesta árvore é `uuid.v4()`. O alerta permanece registrado, sem atribuir ao teste Android cobertura de compilação iOS.

Os alertas permanecem pendentes de atualização compatível ou correção upstream; não foi usado `npm audit fix --force` que sugeria inclusive regressões de versão do Expo. Não se declara ausência de vulnerabilidades nem funcionamento de todas as integrações reais. Não foram gerados APK de produção assinado, build iOS nem transações financeiras reais.

Logs, API fictícia e capturas estão fora do repositório em `C:\Users\mathe\Documents\Backups-Cortae\mobile-javascript-20261018`.

Referências de arquitetura: [React Native e TypeScript](https://reactnative.dev/docs/typescript), [Expo SDK 57](https://docs.expo.dev/versions/v57.0.0/).
