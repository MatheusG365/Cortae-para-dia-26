# Validação independente — agenda e equipe

Revisão de 10 e 11/10/2026 concluída. Migração aditiva aplicada após backup confirmado; verificação visual e reinício local concluídos pelo agente principal. Nenhum bloqueador encontrado nos fluxos exercitados.

## Evidência executada

- Backend: **120 testes aprovados**, incluindo os 75 anteriores e 45 novos testes comportamentais de agenda/equipe/pagamentos. OpenAI, SMTP e bancos de produção não são usados pela suíte.
- Frontend: **27 testes aprovados**, ESLint sem erros ou avisos, build Vite aprovado.
- Integração Flask com Firebird restaurado: **67 assertivas aprovadas**.
- Concorrência real com conexões Firebird independentes: **11 assertivas aprovadas**.
- Verificação final em outra cópia restaurada: **14 assertivas aprovadas** sobre valor legado, falta, auditoria da comissão, bloqueio entre salões e intervalo parcialmente liberado.
- Pagamentos e relatório de comissões do proprietário, em uma cópia adicional: **43 assertivas aprovadas**, incluindo confirmação presencial concorrente e isolamento financeiro por reserva/cliente/salão. Total independente de integração/revisão: **135 assertivas aprovadas**.
- Migração executada **duas vezes** no banco restaurado: preservação integral das **140 linhas das 14 tabelas originais**, comparadas por SHA-256 de todos os valores das colunas originais. A preservação foi novamente conferida após os testes e os dados sintéticos para UI.

## Comportamentos conferidos

Convites guardam apenas o hash do token, expiram e são usados uma vez; a conta fica inativa até a ativação com senha forte. Cadastro público não cria tipo 3. Login de barbeiro pendente não gera código de ativação comum, e `/verificar-codigo` não ativa tipo 3. E-mail de conta existente não é apropriado por outro funcionário; e-mail vinculado não pode ser trocado pela personalização.

O barbeiro vê somente seus agendamentos no próprio salão, não altera reservas de outro profissional, não transfere atendimento para outro profissional e não acessa personalização, edição de serviços ou a conta financeira. Sessão de visagismo deve pertencer ao cliente e ao salão; corte inativo é recusado. Desativar funcionário invalida seu acesso existente.

Editar a equipe conserva IDs, contas vinculadas e referências dos agendamentos. Remover funcionário com atendimento futuro ativo é recusado; após o cancelamento ele é desativado, conservando registros e histórico. Telefone informado no cadastro é persistido com DDD e somente dígitos.

Lista de espera aceita apenas horário futuro ocupado e compatível com expediente, profissional e serviços. Horário livre, fora do expediente ou com profissional inválido é recusado. Inscrição duplicada retorna o mesmo ID. Reserva sem profissional bloqueia também tentativa direta de reservar aquele intervalo com profissional escolhido.

Cancelar ou remarcar repetidamente o mesmo estado não duplica evento nem aviso. A falha de SMTP não desfaz o cancelamento. O aviso de disponibilidade fica no outbox persistido; a disponibilidade integral é revalidada antes da entrega. Alteração de duração do serviço impede entrega incompatível. Falhas de envio têm backoff e encerram após oito tentativas. Dois workers concorrentes fizeram somente uma chamada de envio.

Valores usam Decimal com arredondamento explícito. A reserva guarda preço, nome e duração originais; alteração posterior de serviço não modifica o valor apresentado. Conclusão registra base, percentual e comissão, que permanecem iguais após mudar preço ou configuração. Conclusão concorrente gerou apenas uma comissão e um evento. Reserva antiga sem valor histórico não ganha receita inventada: barbeiro não informa esse valor; proprietário pode registrar o valor realizado explicitamente antes da conclusão. A comissão resultante é auditada. Falta do cliente é persistida e contada no painel sem gerar comissão.

O painel separa valor de atendimentos concluídos de dinheiro efetivamente recebido. Foram conferidos pagamento confirmado, pagamento no local, cobrança pendente, ID vizinho e cliente errado: somente os recebimentos pagos do agendamento exato e do cliente correto entram no total.

As cobranças também usam o valor original da reserva: uma reserva real do teste de R$ 23,55 continuou enviando R$ 23,55 no corpo HTTP Pix simulado depois que o preço do serviço mudou para R$ 999,00. Valor ausente no legado retorna 400 sem consultar o provedor; o catálogo atual não reconstrói esse valor. Falha do provedor não produz cobrança/checkout fictício.

Escolher pagamento no local cria `na_hora_pendente`, status 0 e sem dinheiro recebido. Repetir a escolha reutiliza a mesma cobrança. Somente proprietário/admin confirma o recebimento: duas confirmações simultâneas atualizaram o mesmo ID e produziram um único recebimento. Repetições não criam linha nem rebaixam a confirmação. Confirmar presencialmente não altera cobrança Pix pendente; pagamento já confirmado por outro método bloqueia novo recebimento presencial. Consultas retornam somente o ID exato da reserva e seu cliente, sem confundir `ag#1` com `ag#10`. Tipo 3 é recusado nas seis rotas financeiras mesmo que tenha acesso operacional à reserva.

`GET /barbearia/comissoes` é somente leitura, permitido ao proprietário do salão e ao administrador com salão selecionado. Cliente, barbeiro e proprietário de outro salão são recusados. O período usa a data do atendimento; totais e detalhes preservam base, percentual e comissão históricos, inclusive para profissional inativo. Os testes conferiram dois profissionais, base total R$ 180,00 e comissão total R$ 32,50. O relatório informa valor para pagamento manual; não cria repasse, transferência ou confirmação de pagamento da comissão.

## Backups e reprodução

Backups duráveis fora do projeto:

- `C:\Users\mathe\Documents\Backups-Cortae\agenda-equipe-main-antes-20261010.fbk`
- `C:\Users\mathe\Documents\Backups-Cortae\agenda-equipe-log-antes-20261010.fbk`
- Fonte anterior: `C:\Users\mathe\Documents\Backups-Cortae\agenda-equipe-antes-20261010.zip`

Scripts, manifesto de hashes, JSONs de resultados e bancos restaurados estão em `C:\Users\mathe\Documents\Backups-Cortae\agenda-review-qa-a8kd2se1`. `integration-runtime.txt` identifica a primeira cópia e `payment-runtime.txt` a cópia de pagamentos; os arquivos permanecem preservados fora do projeto. A preservação das 140 linhas originais foi novamente conferida na cópia de pagamentos. O servidor visual atualizado usa `qa_payment_server.py`, loopback `127.0.0.1:5001`, chave JWT exclusiva de QA, `STARTUP_MIGRATIONS=false`, worker desligado, SMTP sem envio, OpenAI sem chave e provedores financeiros bloqueados. `payment-ui-fixtures.json` contém somente contas fictícias, reserva presencial pendente e período de comissão para a UI.

## Aplicação local e navegador

Depois da revisão independente, a migração foi aplicada no banco principal em 10/10/2026. Os servidores registrados do projeto foram reiniciados pelos scripts próprios. `/health` retornou `status=ok`, `pronto=true`, `banco_principal=true` e `banco_log=true`. As quatro tabelas novas existem e estavam vazias na verificação; nenhum dado sintético foi inserido na produção.

Em 11/10/2026, após as correções finais de pagamentos e a validação visual, o ambiente local principal foi reiniciado novamente por `Parar-Cortae.ps1` e `Iniciar-Cortae.ps1`. A saúde confirmou ambos os bancos disponíveis, frontend `/login` retornou HTTP 200 e o OpenAPI servido contém `/barbearia/comissoes` e `/agendamentos/lista-espera`. Logs de inicialização sem exceções da aplicação. O backend usa o servidor de desenvolvimento do Flask; esta conferência valida a execução local, não um deploy público.

No navegador, usando somente o backend isolado e contas fictícias, foram confirmados login com redirecionamento para o painel do barbeiro, seus indicadores e comissões, entrada em horário ocupado e inscrição persistida em Minha lista de espera. Os estados de aviso enviado e falha também foram exibidos a partir das fixtures. O proprietário alterou o percentual pelo formulário da equipe e salvou com sucesso. Não houve erros ou avisos no console desses fluxos. A captura `fila-ui.png` foi salva junto aos arquivos de QA.

A conferência final em 11/10/2026 confirmou o relatório de comissões no desktop e em viewport real de 375 × 812 pixels, sem overflow horizontal (largura do documento: 360 pixels). Com dados fictícios, dois atendimentos apresentaram base total de R$ 180,00 e comissão de R$ 32,50. Um barbeiro com percentual atual de 15% preservou 12,5% no detalhe histórico; outro profissional inativo permaneceu no relatório. A reserva fictícia 28 passou de pagamento presencial pendente para recebido de R$ 32,25 imediatamente após a confirmação, sem recarregar a página, e o botão de confirmação desapareceu. Console sem erros ou avisos. Capturas: `comissoes-ui.png`, `comissoes-mobile.png` e `recebimento-ui.png`, no diretório externo de QA. Login fictício encerrado e override removido.

## Limites de integração

Nenhum e-mail real, pagamento, repasse financeiro ou chamada de IA foi realizado nesta validação. Comissão registrada representa cálculo devido; não confirma repasse ao profissional. Testes confirmam idempotência normal e concorrência; SMTP não oferece entrega exatamente uma vez se o processo cair entre a aceitação remota e a confirmação no banco. A leitura autenticada da conta Arkhé retornou HTTP 200. Conforme esclarecimento do usuário, as comissões são calculadas e armazenadas pelo Cortaê para pagamento manual da barbearia; não há requisito pendente de gravação de comissões na Arkhé. Consulte a [documentação da integração Arkhé](../integracoes/ARKHE_INTEGRACAO.md). A auditoria mantém o modelo existente: banco de logs separado, gravado após o commit principal, sem transação distribuída.
