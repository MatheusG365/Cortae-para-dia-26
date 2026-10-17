# Auditoria de rotas e pagamentos — Cortaê

Data: 14/10/2026. Resultado: os fluxos locais principais responderam aos testes, mas há falhas financeiras reproduzidas. O sistema não deve ser considerado integralmente validado para pagamentos reais.

Esta execução auditou a versão atual. Não corrigiu o código de produção. O relatório separa testes locais, provedores simulados, chamadas externas reais e fluxos ainda não concluídos.

## Cobertura e critérios

| Verificação | Resultado | Limite |
|---|---|---|
| API | 134 caminhos, 164 operações por método, 932 requisições | Inclui 1 operação de arquivos estáticos; 163 são de negócio |
| Exercício HTTP | Todas as 164 operações chamadas; 163 tiveram ao menos um 2xx esperado | 2xx também pode ser confirmação sem efeito; não equivale a funcionalidade completa |
| Backend | 288 testes passaram, 1 ignorado, 0 falhas | Teste ignorado: criação de link simbólico não permitida neste Windows |
| Firebird | Casos opt-in ligados, bancos descartáveis | Nenhuma alteração intencional nos dados reais |
| Frontend | 94 testes passaram; lint e build passaram | Build atualizou somente artefatos gerados |
| React | 198 montagens reais do App/componentes: 36 rotas × 5 perfis, mais 18 estados | API simulada; não comprova pagamento, envio ou cadastro externo |
| Navegador | 36 declarações de rota visitadas e renderizadas | Dados fictícios em cópia isolada; não executa toda combinação de botões/formulários |
| Revisão independente | Achados financeiros reproduzidos em 12 cenários próprios | Não somar essas reproduções como novas rotas |

Classificação consolidada das 164 operações:

| Classe | Operações | Interpretação |
|---|---:|---|
| Funciona localmente | 127 | Fluxo válido no aplicativo real com Firebird isolado |
| Funciona com provedor simulado | 27 | Lógica local passou; integração externa não comprovada por essa evidência |
| Problema reproduzido | 7 | Operação possui pelo menos uma falha demonstrada |
| Parcial ou desativada | 3 | Aceite de termos em rascunho, webhook sem conciliação, compra de etiqueta desativada |

Os sete casos são operações, não sete causas distintas. Quatro métodos de cobrança compartilham a falha de valor `NaN`. A cobrança presencial avulsa tem duas falhas na mesma operação.

## O que funcionou nos testes

| Área | Evidência e resultado |
|---|---|
| Login, contas e permissões | Login real contra a cópia do Firebird gerou JWT. Perfis e negativas de acesso foram exercitados. Cadastro/recuperação usam e-mail simulado |
| Ajuda e documentação ADM | `/help`, catálogo/código autorizados e documentação protegida testados. A página carregou 36 páginas e 143 regras Flask; regras e operações por método têm contagens diferentes |
| Barbearias, personalização, serviços e equipe | Cadastro/edição, configuração de serviços e vínculo profissional exercitados localmente; isolamento entre estabelecimentos verificado |
| Agenda e clientes | Consulta, criação, bloqueios, reagendamento, cancelamento, status e histórico exercitados no backend isolado |
| Lista de espera | Entrada/saída e rotina de notificação exercitadas com envio simulado; entrega real de e-mail não comprovada |
| Caixa de agendamentos e comissões | Recebimentos vinculados, saldo, cálculo por profissional e consultas testados localmente. Não confundir com o endpoint avulso defeituoso abaixo |
| Ranking, avaliações e metas | Rotas exercitadas. No navegador, profissional fictício viu metas de 16% em valor e 20% em atendimentos |
| Marketplace | Produtos por loja, ativação, variações, estoque, fornecedores, custos/margem, favoritos, desejos, promoções, cupons, carrinho, pedidos, avaliações e relatórios exercitados localmente |
| Loja integrada | Rota antiga da loja redirecionou para `/estabelecimento?usuario=17#loja-barbearia`, com produtos da loja fictícia |
| Escolha de corte | Pular IA abriu catálogo; “Ver mais” mostrou descrição; “Escolho na hora” foi preservado até o calendário |
| Financeiro Arkhé real | Conta, saldo, movimentações, resumo e gráficos responderam 200, incluindo consultas pelo Cortaê; origem Arkhé identificada nas respostas |
| Frete real | Melhor Envio retornou 10 opções de cotação. Nenhuma etiqueta comprada ou emitida |

“Funcionou localmente” significa os cenários exercitados, não garantia de ausência de outros defeitos.

## Problemas reproduzidos

### Prioridade alta: pagamentos de agendamento

1. **Cobrança duplicada ou acima do saldo — PAY-01.** `POST /pagamentos/pix` cria outra cobrança em repetição e até em atendimento quitado. Com total R$1,00 e R$0,40 recebido, pediu R$1,00, embora faltassem R$0,60. Outro controle confirmou total R$80,00, recebido R$20,00 e cobrança indevida de R$80,00. Falta validar quitação, cobrar o saldo e impedir duplicação. Fonte: `Backend/pagamento.py:280`.
2. **Resposta inválida aceita na criação — PAY-02.** A mesma operação aceitou valor divergente e código de pagamento ausente, retornando 201 e registro financeiro local. Deve conferir contrato, valor e código antes de persistir. Fonte: `Backend/pagamento.py:515`.
3. **Confirmação com ID/valor divergentes — PAY-03.** `GET /pagamentos/pix/<id_cobranca>` marcou pagamento local como pago ao receber `status=1`, mesmo com ID diferente e valor R$0,01. Deve conferir identidade, recebedor e valor antes da conciliação. Fonte: `Backend/pagamento.py:700`.

Esses erros foram provocados com provedores fictícios. Não foi adulterada nem paga cobrança real para reproduzi-los.

### Prioridade média: financeiro e marketplace

4. **Valor não finito aceito — PAY-04.** `POST /financeiro/cobrancas/pix`, `/boleto`, `/cartao` e `/na-hora` aceitam a string `NaN`. O validador deve exigir número finito e positivo. `Infinity` foi rejeitado corretamente. Fonte: `Backend/arkhe.py:2135` e handlers seguintes.
5. **Marketplace aceita cobrança sem código — PAY-05.** `POST /marketplace/pedidos/<id_pedido>/pix` aceitou resposta com ID/valor/status válidos, mas sem `codigo_pagamento`, e devolveu 201 com código vazio. Os controles de ID/valor divergentes e reutilização de cobrança pendente funcionaram nesse módulo. Fonte: `Backend/marketplace.py:514`.
6. **Recebimento avulso não persiste.** `POST /financeiro/cobrancas/na-hora` devolve “confirmado”, mas não grava em `FINANCEIRO`. A rota de recebimento ligada ao agendamento persiste corretamente. Fonte: `Backend/arkhe.py:2336`.

### Interface e documentação

7. **Financeiro mostra zero ou valores antigos após falha — média.** Em `/gestao?aba=financeiro`, uma primeira consulta com erro exibe indicadores zerados. Após sucesso e troca de período com erro, mantém os valores do período anterior sem identificá-los. Existe alerta, mas os números induzem leitura incorreta. Fonte: `Frontend/src/pages/Gestao/FinanceiroGestao.jsx:28` e `:44`.
8. **Agenda confunde erro com ausência de registros — baixa.** Em `/gestao?aba=agenda`, falha simulada de API exibe alerta e “Sem registros” em todas as colunas. Deve identificar indisponibilidade da consulta. Fonte: `Frontend/src/pages/Gestao/AgendaGestao.jsx:56`.
9. **Aba inválida deixa conteúdo vazio — baixa.** `/gestao?aba=invalid` não tem fallback nem aviso. Fonte: `Frontend/src/pages/Gestao/Gestao.jsx:29` e `:70`.
10. **Contrato documentado diverge do código.** A documentação menciona fallback simulado de boleto/cartão ausente nos handlers atuais e apresenta recebimento avulso como registro persistente. Fonte: `Backend/api_docs.py:352-359`. A proteção ADM foi testada separadamente e não é esse defeito.

## Parcial, desativado ou ainda sem comprovação real

| Recurso | Estado e trabalho restante |
|---|---|
| Pix real | Criação e consulta pendente funcionaram. Pagamento e conciliação reais não concluídos |
| Webhook Arkhé | `POST /financeiro/webhook/arkhe` apenas responde 200, sem autenticar evento nem reconciliar pagamento. Não foi demonstrada falsificação efetiva de pagamento: ele não altera o estado |
| Boleto e cartão online | Caminhos locais exercitados com simulação. API pública fornecida não documenta criação desses métodos; nenhuma cobrança real desses tipos foi criada. Um GET 404 não demonstra ausência de suporte |
| Termos e taxa de 1,5% | Configuração atual em rascunho/inativa. Fluxo de aceite e cálculo foram exercitados com política fictícia temporária; cobrança efetiva universal da taxa não está validada |
| E-mail | Conexão SMTP TLS e NOOP 250 funcionaram. Autenticação, envio e recebimento reais não testados; mensagens dos cenários locais foram simuladas |
| Visagismo por IA | Fluxo, catálogo e integração simulada testados. Não houve geração real nem avaliação da fidelidade de imagens nesta auditoria |
| Rastreio Melhor Envio | API respondeu 200 em consulta com UUID inexistente. Isso confirma acesso ao endpoint, não rastreio de encomenda real |
| Etiquetas | Compra/emissão desativadas por escolha do usuário. POST protegido retornou 403; nenhum dos três envios foi consumido por esta execução |
| WhatsApp | Adiado pelo usuário; sem provedor configurado/testado |
| Repasse de comissão e estornos Arkhé | Não executados. Comissão local serve para pagamento manual; nenhum repasse ou estorno foi realizado |

Observação de configuração: no clone, o serviço 1 do El Brabo não tinha profissional compatível. Thiago (9) estava vinculado aos serviços 3 e 5. A tela pediu seleção de profissional sem mostrar candidatos. Isso não foi classificado como falha geral de agendamento; requer conferir os vínculos e melhorar a mensagem de indisponibilidade. Os testes positivos da API usaram configuração válida.

## Três cobranças reais autorizadas

O usuário autorizou El Brabo, R$1,00 por cobrança. Foram criadas uma vez:

| Caso | ID na Arkhé | Valor | Último estado observado |
|---|---:|---:|---|
| Agendamento | 162 | R$1,00 | Pendente |
| Marketplace | 163 | R$1,00 | Pendente |
| Avulsa | 164 | R$1,00 | Pendente |

Total solicitado: R$3,00. A conta configurada respondeu com recebedor “JhonJhon”. O usuário informou que não conseguiu pagar; não houve confirmação posterior de pagamento nesta execução.

A documentação fornecida descreve **Pix interno Arkhé**. As respostas retornaram `codigo_pagamento` com prefixo `ARKHEPIX:`, sem imagem QR, BR Code ou código EMV de banco externo. Na auditoria, foram geradas três imagens QR locais a partir dos códigos exatos existentes, sem criar novas cobranças. Converter o texto em QR não o transforma em Pix interoperável com outros bancos.

Portanto, pagamento pelo banco externo do cliente permanece sem validação. Para concluí-lo, é necessário um contrato da Arkhé que forneça payload Pix bancário compatível, ou confirmar o fluxo interno na própria plataforma. O agente não executou pagamento, transferência, baixa, estorno ou compra de etiqueta.

## Preservação e ambiente

- Backup Firebird principal e de logs criado antes dos testes.
- Após a auditoria, as 49 tabelas e 152 linhas originais do banco principal conservaram conteúdo e colunas originais.
- Os 193 arquivos de código acompanhados por hash permaneceram iguais.
- Escritas de testes ocorreram em bancos descartáveis. Credenciais e conteúdo privado das respostas não foram incluídos neste relatório.
- Navegação ocorreu em frontend 5174/backend 5001 isolados. Esses processos de QA foram encerrados após a conferência. Não é um atestado do serviço principal em execução.

## Ordem recomendada de correção

1. Corrigir duplicação/saldo e validação da criação/consulta de Pix de agendamento.
2. Rejeitar valores não finitos e respostas sem código; persistir recebimento avulso corretamente.
3. Definir a conciliação e o contrato real de pagamento externo com Arkhé.
4. Identificar dados indisponíveis/antigos no financeiro e na agenda; corrigir fallback de abas.
5. Alinhar documentação, publicar configuração de termos/taxa e completar os testes externos ainda pendentes.

## Evidências e matriz completa

Os arquivos abaixo estão no diretório local de auditoria, fora do código da aplicação:

- [Matriz das 164 operações, método por método](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/MATRIZ_ROTAS_CONSOLIDADA.csv>)
- [Resumo consolidado legível por ferramentas](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/RESUMO_CONSOLIDADO.json>)
- [Ledger das 932 requisições](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/backend/route-ledger.json>)
- [Relatório backend](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/backend/BACKEND_AUDITORIA.md>)
- [Relatório frontend](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/frontend/FRONTEND_AUDITORIA.md>)
- [Relatório de pagamentos e integrações](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/payments/PAGAMENTOS_AUDITORIA.md>)
- [Revisão independente](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/INDEPENDENT_AUDIT_REVIEW.md>)
- [Revisão final do relatório consolidado](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/FINAL_REPORT_REVIEW.md>)
- [Navegação real das 36 rotas](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/browser/browser-navigation.json>)
- [Preservação dos dados originais](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/production-preservation-result.json>)
- [Preservação das fontes](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/source-preservation-result.json>)
- [Manifesto dos QR gerados dos códigos existentes](<C:/Users/mathe/Documents/Backups-Cortae/auditoria-rotas-20261014/payments/qr-manifest.json>)

## Matriz de navegação no navegador

Esta tabela registra renderização e navegação. A matriz CSV separada registra os testes por operação HTTP.

| Rota declarada | Perfil utilizado | Resultado da navegação |
|---|---|---|
| `/` | guest | LEVE A SUA BARBEARIA AOPRÓXIMO ESTÁGIO. |
| `/termos-de-uso` | guest | Termos de Uso |
| `/marketplace` | guest | Produtos das nossas barbearias |
| `/marketplace/barbearias/:id_barbearia` | staff | Marketplace QA owner |
| `/marketplace/produtos/:id` | guest | Pomada modeladora QA |
| `/ativar-barbeiro` | guest | Ative seu acesso de barbeiro — tela sem token/código de convite; operação positiva coberta separadamente na API |
| `/*` | guest | Página não encontrada |
| `/cadastro` | guest | FAÇA SEU CADASTRO |
| `/redefinirsenha` | guest | REDEFINIÇÃO DE SENHA |
| `/verificar-codigo` | guest | CONFIRME SEU E-MAIL — tela sem token/código de convite; operação positiva coberta separadamente na API |
| `/estabelecimento` | guest | Marketplace QA owner |
| `/barbearias-disponiveis` | guest | Barbearias Disponíveis |
| `/cadastrobarbearia` | guest | CADASTRO |
| `/login` | guest | REALIZE O LOGIN |
| `/marketplace/lista-desejos` | client | Sua lista de desejos |
| `/marketplace/favoritos` | client | Seus favoritos |
| `/marketplace/carrinho` | client | Seu carrinho |
| `/marketplace/pedidos` | client | Meus pedidos |
| `/marketplace/pedidos/:id` | client | Pedido #1 |
| `/editarusuario` | client | EDITAR SUAS INFORMAÇÕES |
| `/editarusuario/:id` | client | EDITAR SUAS INFORMAÇÕES |
| `/meus-agendamentos` | client | Meus Agendamentos |
| `/selecionar-servicos` | client | Selecione os serviços |
| `/visagismo` | client | Coloque uma imagem paraser feito o visagismo. |
| `/agendamento` | client | outubro de 2026 |
| `/gestao-marketplace` | owner | Sua loja, organizada |
| `/gestao` | owner | Rotina da barbearia |
| `/comissoes-barbearia` | owner | Valores para pagamento manual |
| `/personalizacaobarbearia` | owner | Editar barbearia |
| `/editarbarbearia` | owner | Editar barbearia |
| `/agendamentosadm` | owner | AGENDAMENTOS |
| `/financeiro` | owner | PAINEL FINANCEIRO — erro esperado na cópia com credenciais fictícias; Arkhé real testada separadamente |
| `/admin/cortes` | owner | Catálogo de cortes |
| `/help` | admin | Central técnica do sistema |
| `/admin/usuarios` | admin | Usuários cadastrados |
| `/painel-barbeiro` | staff | Profissional QA |
