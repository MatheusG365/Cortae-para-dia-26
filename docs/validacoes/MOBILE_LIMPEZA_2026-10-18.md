# Auditoria de uso e limpeza do aplicativo — 18/10/2026

## Resultado

A limpeza foi limitada a `Cortae_mobile-main`. Foram preservadas as alterações anteriores de conversão para JavaScript, adaptação ao Figma e cadastro público exclusivo de clientes. O aplicativo continua em React Native com Expo SDK 57, sem painel administrativo ou cadastro de barbearias. O administrador utiliza o site.

Os 90 módulos JavaScript/JSX têm uso a partir das rotas do Expo Router, considerando imports e reexports. Nenhuma tela ou módulo funcional foi removido. Rotas descobertas pelo Router são pontos de entrada mesmo quando não possuem um import convencional.

## Remoções comprovadas

| Item | Evidência e ação |
| --- | --- |
| `components/`, `Services/`, `Screens/` | Pastas antigas sem arquivos; `Screens/Login` e `Screens/SelecioneBarbearia` também estavam vazias. Removidas. Diretórios vazios não são versionados pelo Git. |
| `assets/splash-icon.png` | Nenhuma referência no código ou na configuração; `app.json` não utiliza esse arquivo. Removido, com cópia externa de segurança. |
| `ui.Heading` | Componente sem consumidores. Removido; os componentes `Heading` das áreas de cliente e barbearia permanecem utilizados. |
| `owner/shared.saveRecord` | Função sem chamadas. Removida junto com seu import de `api`, que ficou sem uso. |
| Estilos antigos | Removidos `authStyles.logo`, `authStyles.intro`, `ui.s.heading` e `client/common.s.gap`, `accent`, `price`. Referências locais e imports com alias foram conferidos. |
| Exclusões antigas do ESLint | Removidas as entradas para `Screens`, `Services`, `components`, `App.js` e `index.js`. Permanecem as exclusões dos diretórios de build nativo. |

`Row` e `sectionTitle` continuam em uso pelo seletor de opções. Funções exportadas que possuem chamadas internas ou uso nos testes também foram preservadas.

## O que deve continuar

| Item | Utilização |
| --- | --- |
| `src/` | 90 módulos da aplicação: rotas, fluxos, sessão, API, diálogos e interface. |
| `assets/` | Cinco imagens referenciadas por `app.json`: ícone geral, favicon e três componentes do ícone adaptativo Android. |
| `node_modules/` | Dependências do app e ferramentas. Não é conteúdo versionado e pode ser recriado pelo instalador. |
| `.expo/` | Estado local e cache do Expo, fora do Git. Não é código abandonado. |
| `scripts/`, `tests/` | Verificação de JavaScript e regressões funcionais; executados nesta auditoria. |
| Configurações, instruções, licença e lockfile | Configuração de compilação, documentação, direitos de uso e instalação reproduzível. |

Bibliotecas sem import direto podem ser necessárias ao Router, ao ambiente nativo, à versão web ou aos plugins de compilação. Nenhuma dependência foi removida por ausência isolada de import.

## Bugs corrigidos

1. **Cancelar o calendário apagava o horário escolhido.** A biblioteca instalada chama o callback legado `onChange` também ao cancelar, passando a data original. Agendamento e reagendamento interpretavam esse evento como uma escolha confirmada, limpando horário e resumo. Os dois fluxos passaram a utilizar `onValueChange` para confirmação e `onDismiss` exclusivamente para fechar o calendário.
2. **Falha na busca de profissionais era tratada como lista vazia.** A consulta de horários agora aguarda uma resposta bem-sucedida dos profissionais. Uma resposta válida sem profissionais continua permitindo consultar disponibilidade sem vínculo, conforme as regras do backend.

As interfaces foram conferidas na implementação instalada de `@react-native-community/datetimepicker` 9.1.0 e na [referência do Expo SDK 57](https://docs.expo.dev/versions/v57.0.0/sdk/date-time-picker/).

## Testes e evidências

| Verificação | Resultado |
| --- | --- |
| Base anterior à limpeza | 70 testes passaram; lint e sintaxe/imports passaram. |
| Novas regressões antes das correções | 6 casos: 3 falharam e 3 passaram, reproduzindo os problemas. |
| Suíte final | 76 testes passaram, nenhuma falha ou teste ignorado. |
| Lint final | Sem erros ou avisos. |
| `npm run typecheck` | Alias de verificação JavaScript/JSX: 90 fontes válidas e imports locais encontrados; não representa análise de tipos TypeScript. |
| Expo Doctor | 21 de 21 verificações passaram antes e depois. |
| Exportação Android/Hermes | Concluída, com bundle `.hbc`. Não equivale à geração de APK assinado. |
| Navegação Android | 15 telas privadas de cliente e 21 de barbearia abertas com API fictícia; verificadas também as rotas parametrizadas de novo produto, variações e estoque. Sem erro fatal de renderização identificado. |
| Calendário Android | Antes, cancelar removia a seleção de `14:00`; após a correção, data e horário selecionados foram preservados. |
| Mídias pela API real | Logo, fundo de login e banner retornaram HTTP 200 com `image/webp`, sem disponibilizar credenciais no app. |
| Revisão de código | Revisão local independente aprovou as alterações. |
| QA independente | Validação local aprovada com cobertura global parcial: integrações de produção e plataformas não executadas continuam sem certificação. A avaliação final registrou explicitamente os 29 alertas de dependências. |

Na navegação, o detalhe de produto foi conferido novamente após o carregamento inicial do bundle. Os parâmetros usados inicialmente nos acessos diretos de produto/estoque/variações foram ajustados aos links reais da interface e os acessos foram repetidos. Ausência de dados nas fixtures não foi considerada comprovação das operações comerciais.

Os testes nativos utilizaram contas fictícias em servidor isolado, sem banco de dados nem provedores externos. Escritas de negócio estavam bloqueadas. Pagamento real, envio de e-mail, criação de pedido/agendamento real, câmera física, IA, etiquetas, upload no Drive, iOS e APK assinado não foram certificados nesta auditoria.

A conta fictícia foi desconectada ao final. O servidor de fixtures e o Metro exclusivo de QA foram encerrados, sem mudar arquivos de ambiente ou as configurações permanentes de conexão do aplicativo.

## Dependências e limites

`npm audit` permanece com **29 alertas: 19 altos e 10 moderados**, já presentes antes desta limpeza. Entre as cadeias afetadas estão `braces`, `node-forge`, `decode-uri-component` e `uuid`. O comando sugere mudanças de versão principal, incluindo downgrade de Expo ou mudança de Router, em parte das cadeias. Não foi aplicado `npm audit fix --force`; esta auditoria não certifica ausência de vulnerabilidades nas dependências.

O processo seguiu o Mega Brain local: Graphify AST, compressão de contexto pelo Qwen 3B, especialistas locais e revisão independente pelo Qwen 14B. Propostas incorretas foram rejeitadas antes de aplicar mudanças. OpenCode estava indisponível; nenhuma chamada de fallback à OpenAI foi utilizada. Os modelos maiores foram executados em série, com reservas de IA de até 10,6 GB.

O Graphify sinalizou ausência de extrator JSON e não modelou símbolos de alguns arquivos que apenas reexportam telas. Por isso, configuração, imagens e reexports também foram conferidos diretamente com AST JavaScript, buscas e exportação Android.

Relatórios dos modelos e grafo ficaram em `C:\Users\mathe\MegaBrain\.mega_brain`. Logs, XMLs da interface, screenshots, backup da imagem e exportação Android ficaram fora do repositório em `C:\Users\mathe\Documents\Backups-Cortae\mobile-limpeza-20261018`.

Nenhum commit ou envio ao GitHub foi realizado nesta etapa.
