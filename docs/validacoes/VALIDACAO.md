# Validação e revisão independente do Cortaê

Data: 10/10/2026. Resultado: **aprovado no escopo verificado**, sem falhas abertas nos testes executados.

## Evidências executadas

- **81 verificações independentes** contra cópias isoladas dos bancos principal e de auditoria, criadas com backup e restauração `gbak`. Nenhuma alteração de teste foi aplicada aos dados reais.
- **25 testes de regressão do backend**: todos aprovados.
- **12 testes do frontend**: todos aprovados.
- Frontend: `npm run lint` aprovado com zero avisos; `npm run build` aprovado.

As 81 verificações independentes cobriram:

| Grupo | Verificações | Comportamentos confirmados |
| --- | ---: | --- |
| API, segurança e auditoria | 30 | Preparação repetível do banco; sequência nunca reduzida; saúde dos dois bancos; documentação; listagens públicas; permissões; JSON inválido rejeitado; cadastro público de administrador bloqueado; conta desativada perde acesso; serviço criado, editado e excluído com logs; segredos protegidos e apenas campos alterados registrados. |
| Autenticação, recuperação e prontidão | 18 | Login; cookie HttpOnly; logout; três tentativas bloqueiam acesso; recuperação completa com envio de e-mail simulado; senha antiga rejeitada; senha nova aceita; eventos auditados; banco de log opcional indisponível produz estado degradado; log obrigatório indisponível produz HTTP 503. |
| Importação de imagens e financeiro | 13 | HTTPS público aceito; HTTP, credenciais na URL, porta alternativa, endereços internos, loopback, IPv6 local, metadados e DNS misto rejeitados; snapshot financeiro registrado com auditoria; falha injetada durante inserção preserva integralmente o snapshot anterior. |
| Agendamento | 15 | Disponibilidade; reserva; total do serviço; conflito HTTP 409; horário ocupado; listagem do cliente; cancelamento de outro cliente negado; reagendamento libera horário anterior; cancelamento libera horário; alterações auditadas. |
| Transporte seguro de imagens | 5 | Conexão usa IP previamente validado; hostname original mantido; certificado TLS obrigatório e hostname verificado; redirecionamento para endereço privado bloqueado antes da requisição. |

## Preservação dos dados

Comparação independente, somente leitura, de colunas e hashes SHA-256 de todas as linhas das **14 tabelas de aplicação** confirmou que todas as linhas do banco de `Salvar-main` estão no banco consolidado de JOHN. Nenhum valor pessoal foi incluído neste relatório.

As 13 sessões de visagismo que faltavam foram incorporadas: `VISAGISMO_SESSAO` passou a conter as mesmas 28 sessões da origem. Os registros adicionais de JOHN em `AGENDAMENTO`, `AGENDAMENTO_HISTORICO` e `FINANCEIRO` foram preservados. As demais tabelas da origem são subconjuntos exatos do destino.

Comparação independente de arquivos confirmou que todos os 13 arquivos de upload da origem existem no destino com bytes idênticos. O coordenador também preservou as configurações necessárias. Os projetos originais foram arquivados antes da alteração em `Backups-Cortae/antes-correcao-20261010-124518.zip`.

## Verificação visual e de navegação

Verificação final realizada pelo coordenador em navegador:

- Login e cadastro sem rolagem horizontal em largura de 375 px.
- Diálogo de credenciais incorretas recebe foco, mantém navegação por teclado, fecha com Escape e devolve foco ao botão de entrada.
- Lista pública carrega dados reais; acesso a estabelecimento protegido direciona ao login.
- Imagens e caminhos de recursos verificados sem imagens quebradas no fluxo inspecionado.
- A rota de retorno do cliente mantém caminho e parâmetros da navegação anterior ao login.

## Scripts de inicialização e encerramento

Revisão independente dos scripts finais confirmou que o encerramento valida o caminho absoluto dentro do projeto, o PID, o horário de criação em UTC e o comando do processo antes de encerrá-lo. O script captura os filhos enquanto o pai verificado ainda existe e encerra somente filhos que executam o mesmo arquivo do projeto e nasceram após o pai. Registros incompatíveis e falhas de encerramento permanecem disponíveis para nova verificação.

O coordenador executou duas rodadas reais de parada e reinício: processos registrados encerrados, portas 5000 e 5173 livres após cada parada e API/frontend disponíveis após reinício. A API confirmou bancos principal e de log prontos. O sistema foi deixado em execução ao fim da verificação.

O favicon final aponta para `/logosolo.png`, com tipo `image/png`; o coordenador confirmou build após essa alteração.

## Limites da aprovação

SMTP real, cobranças reais, pagamentos financiados e chamadas reais de OpenAI não foram executados. Os fluxos de recuperação e notificações usaram funções de envio simuladas; os testes não criaram cobranças externas nem consumiram geração de imagem.

Os bancos principal e de auditoria são separados. Os logs são gravados após o commit principal; não existe transação distribuída entre os bancos. Falha de auditoria com `LOG_OBRIGATORIO=true` pode ser reportada depois de a alteração principal já estar persistida. A configuração e a prontidão são documentadas; essa propriedade arquitetural não constitui atomicidade entre os bancos.

A aprovação corresponde aos testes, rotas e fluxos descritos. Não afirma ausência universal de defeitos nem valida implantação pública ou integrações externas não executadas.

## Consolidação final

Configurar-Cortae.ps1 e Iniciar-Cortae.ps1 foram executados com sucesso. Frontend respondeu HTTP 200; /health confirmou pronto=true, banco_principal=true e banco_log=true. Somente JOHN2-main permanece na pasta Arrumar. A política automática bloqueou a exclusão definitiva, sem motivo detalhado; como alternativa reversível, Salvar-main foi movido para C:\Users\mathe\Documents\Backups-Cortae\Salvar-main-consolidado-20261010. O ZIP original permanece em C:\Users\mathe\Documents\Backups-Cortae\antes-correcao-20261010-124518.zip. A pasta temporária de QA também foi mantida fora do workspace.

