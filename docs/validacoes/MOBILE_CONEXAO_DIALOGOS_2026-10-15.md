# Mobile: confirmações e conexão automática — 15/10/2026

Atualização posterior à [validação inicial mobile](VALIDACAO_MOBILE_2026-10-15.md). Instruções de execução no [README do app](../../Cortae_mobile-main/README.md).

## Confirmações

Todas as chamadas `Alert.alert` do aplicativo foram substituídas pelo diálogo visual do Cortaê. Confirmações, avisos, detalhes de corte e leitura dos termos usam o mesmo componente: cartão escuro, ícone, tipografia do app, ação identificada, destaque laranja e ação destrutiva em vermelho. Textos longos têm rolagem. Fechar, voltar ou tocar fora não executa a ação.

A fila mantém mensagens concorrentes em ordem. Cada confirmação pertence à sessão que a abriu; troca de usuário ou servidor invalida os callbacks anteriores. A solicitação é consumida antes de executar o callback, evitando repetição por clique duplo. Os helpers existentes `ask` e `confirmAction` continuam centralizados.

## Conexão

- Desenvolvimento nativo: o app usa o host do computador que serve o projeto pelo Expo, com porta 5000 por padrão. IPs locais, nomes de máquina e IPv6 são tratados pelo resolvedor. O alias do computador no emulador Android é aplicado apenas ao caso de localhost.
- Expo web em desenvolvimento: usa o hostname atual do navegador e a porta da API. O site React/Vite mantém seu proxy `/api`, independente do IP usado pelo navegador.
- API e inicializador web escutam em `0.0.0.0` por padrão. O inicializador respeita `PORT`, `API_HOST` e seus parâmetros, sincronizando proxy e verificação de saúde. Uma configuração explícita de acesso somente local continua sendo respeitada.
- Endereços antigos gravados pelo app deixam de forçar IP fixo. A página `/configuracao`, seus botões e a edição manual do servidor foram removidos por solicitação do usuário. Não há opção avançada de conexão disponível ao cliente ou à barbearia; o endereço é determinado pelo Expo ou pela configuração de compilação.
- O token nativo é vinculado à URL-base da API. Troca automática de host descarta a sessão anterior antes de encaminhar credenciais. As proteções contra respostas atrasadas foram preservadas.

O computador e o celular precisam estar na mesma rede, com a API acessível. Um túnel do Expo publica o projeto, mas não publica automaticamente a API. O app informa esse caso, em vez de presumir um endereço incorreto.

Para um APK de produção, configure `EXPO_PUBLIC_API_URL` com o domínio HTTPS uma vez antes da compilação. O cliente não informa IP. Um app instalado sem Metro não consegue descobrir sozinho qual servidor da internet pertence ao projeto. Na versão web publicada, o servidor de hospedagem precisa encaminhar `/api` ao Flask.

## Validação

| Verificação | Resultado |
|---|---|
| Lint e TypeScript mobile | Aprovados |
| Testes mobile | 52 aprovados, zero falhas |
| Exportação Android | Aprovada |
| Backend completo | 325 casos: 284 aprovados, 41 ignorados, zero falhas |
| Inicializador PowerShell | Sintaxe aprovada; 10 cenários isolados aprovados |
| Frontend web | Build aprovado |
| HTTP pela rede local | Site respondeu 200 e proxy `/api/health` confirmou API pronta |

No emulador Android, o endereço antigo da porta 5002 migrou para o modo automático na porta 5000, e o login sintético abriu o painel da barbearia. A conexão foi validada antes da remoção definitiva da página de configuração; a captura `android-conexao-automatica.jpg` registra essa etapa intermediária e não corresponde a uma página disponível na entrega final. O novo modal de saída foi inspecionado visualmente, com ações claras e layout dentro da tela; captura `android-confirmacao-cortae.jpg` na pasta externa de evidências.

Os testes novos cobrem fila e consumo único de confirmação, descarte de callbacks antigos, migração do IP antigo, hosts diferentes, IPv6, portas inválidas, túnel do Expo e token associado ao servidor. As 41 verificações ignoradas do backend dependem de integrações optativas ou condições do ambiente; não foram contadas como aprovadas.

Após a remoção da tela de configuração, o app possui 41 telas de funcionalidades: cinco públicas, quinze de cliente e vinte e uma de barbearia, além dos layouts, redirecionamento inicial e página de rota desconhecida.

A versão final também remove as funções de alteração manual de URL da camada de API. Os testes verificam que os endereços e modos manuais antigos são ignorados e apagados, inclusive os da versão intermediária. A captura do novo modal e a ação Voltar foram verificadas no Android antes da última remoção da tela de conexão; o emulador foi fechado entre as mensagens posteriores. A remoção final foi conferida nas rotas, referências, testes e nova exportação Android.

O teste HTTP e a verificação Android usaram exclusivamente o clone externo do Firebird, contas fictícias e provedores/SMTP bloqueados. A API de QA foi iniciada temporariamente na porta 5000 para testar a descoberta padrão; não foram iniciadas migrações sobre os bancos de uso normal. Nenhuma compra, cobrança ou mensagem real foi criada.

Após os testes, os processos temporários de QA da API na porta 5000 e do frontend na porta 5175 foram encerrados com conferência de PID, comando e data de criação. A inicialização normal do projeto pode usar essas portas novamente.

Os serviços antigos da demonstração (Metro em localhost na porta 8081 e clone de API na porta 5002) também foram encerrados após conferir suas identidades registradas. Na próxima execução, use o iniciador normal da API e `npm run android` na pasta mobile para abrir o Expo com a configuração atual.

Foram feitas revisões independentes entre os responsáveis pelos diálogos, conexão e inicializador. O Graphify local foi consultado, mas seu extrator não incluiu os arquivos TS/TSX nesta execução; os imports e fluxos foram conferidos diretamente, inclusive com AST TypeScript. Não se atribui ao mapa uma cobertura inexistente.

Evidências externas: `C:\Users\mathe\Documents\Backups-Cortae\mobile-20261015` e `C:\Users\mathe\MegaBrain\.mega_brain\tasks\mobile-network-dialog-20261015`.

Referências consultadas: [Constants no Expo SDK 57](https://docs.expo.dev/versions/v57.0.0/sdk/constants/) e [Modal do React Native](https://reactnative.dev/docs/modal).
