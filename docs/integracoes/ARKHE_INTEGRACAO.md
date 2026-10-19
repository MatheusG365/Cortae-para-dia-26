# Arkhé e comissões no Cortaê

Atualização em 19/10/2026 a partir da documentação oficial fornecida pelo responsável. O Cortaê calcula as comissões por percentual de cada barbeiro e mostra quanto a barbearia deve pagar. O pagamento aos profissionais é realizado pela barbearia. Não é requisito enviar comissões ou estatísticas para a API Arkhé, nem executar repasses automáticos.

## Evidência atual

O responsável forneceu a documentação atualizada da API, incluindo venda com
cartão virtual Arkhé. Esse contrato substitui, para cartão, a antiga suposição de
checkout em `/api/v1/cobrancas/cartao`, que não faz parte da documentação atual.
Os parágrafos de inspeção abaixo registram a integração consultada em outubro,
antes dessa atualização.

O frontend oficial publica a documentação no componente de `/desenvolvedores/api`, incluído no [bundle oficial consultado](https://arkhe-frontend.zbbquj.easypanel.host/assets/index-D2A1Ywy2.js). O acesso direto à página redirecionou para login. O bundle foi apenas lido; nenhuma conta foi criada ou pagamento realizado.

A integração configurada no banco local foi conferida com `GET /api/v1/conta`: HTTP 200. Credenciais e dados da conta não foram expostos no relatório. Essa consulta não alterou o banco remoto.

| Método | Rota documentada | Finalidade |
| --- | --- | --- |
| GET | `/api/v1/conta` | Dados da conta PJ vinculada à integração |
| GET | `/api/v1/saldo` | Saldo da conta |
| GET | `/api/v1/movimentacoes` | Movimentações, com período opcional |
| GET | `/api/v1/resumo-financeiro` | Receitas, despesas e saldo do período |
| POST | `/api/v1/cobrancas/pix` | Cobrança Pix; corpo documentado contém `valor` |
| GET | `/api/v1/cobrancas/pix/{id_cobranca}` | Consulta da cobrança; status 0 pendente ou 1 pago |
| POST | `/api/v1/cobrancas/pix/qrcode` | QR com valor fixo ou livre; não utilizado para alterar valores dos pedidos |
| POST | `/api/v1/cobrancas/boletos` | Emissão entre contas Arkhé; exige documento do pagador e vencimento |
| GET | `/api/v1/cobrancas/boletos/{id_cobranca}` | Estado do boleto |
| GET | `/api/v1/cobrancas/boletos/{id_cobranca}/pdf` | PDF autenticado pelo servidor |
| POST | `/api/v1/vendas/cartao` | Venda com cartão virtual Arkhé, débito ou crédito |

As requisições da integração usam `X-Client-ID` e `X-Client-Secret`, exclusivamente no backend. Não foi identificado endpoint documentado para gravar comissão, vincular barbeiro, dividir recebimento, executar repasse ou armazenar indicadores de agendamento.

## Cartão virtual nos agendamentos e no marketplace

O cliente pode pagar os dois tipos de pedido com seu cartão virtual Arkhé. Esse
fluxo é interno ao Arkhé: não representa aceitação geral de cartões Visa ou
Mastercard. O site e o aplicativo enviam os dados ao backend somente após a
confirmação do cliente.

O contrato recebe `numero_cartao` com 16 dígitos, `validade` em `MM/YYYY` e `cvv`
como texto com três dígitos, preservando zeros à esquerda. Não recebe PIN. No
débito, `tipo=DEBITO` e `parcelas=1`; no crédito, `tipo=CREDITO` e de uma a 15
parcelas, com pelo menos um centavo por parcela. O valor é calculado pelo servidor
a partir do agendamento ou pedido, independentemente de um valor enviado pelo
cliente.

O cliente paga o total bruto registrado. Segundo a documentação fornecida, no
débito o recebedor recebe 100%; no crédito recebe 95%, com taxa de 5%. O valor
bruto quita o pedido. O recebimento líquido e a taxa do Arkhé são guardados
separadamente no resultado da venda. Essa taxa não aumenta automaticamente o
valor do cliente nem substitui as regras de comissão e taxa da plataforma.

As rotas Cortaê são `POST /pagamentos/cartao`, com `id_agendamento`, e
`POST /marketplace/pedidos/<id_pedido>/cartao`. Elas enviam exclusivamente o
contrato documentado para `POST /api/v1/vendas/cartao`, usando a integração da
barbearia recebedora. O recibo conserva somente aprovação, IDs da compra e
movimentação, valores, modalidade, parcelas, quatro dígitos finais e data.
Número completo, validade, CVV e PIN não entram no banco, no histórico de
auditoria, no armazenamento local do navegador ou no dispositivo.

### Tentativas e confirmação

Antes de enviar a venda, o backend confirma no Firebird uma reserva da tentativa.
A criação de outro pagamento para o mesmo alvo é bloqueada enquanto houver venda
em processamento, incerta ou aprovada. O estado aprovado permite recuperar o
recibo já gravado sem enviar outra venda. Uma recusa conhecida permite uma nova
tentativa explícita, depois de corrigir os dados.

Timeout, HTTP 409, resposta incompleta ou falha de confirmação local deixam a
operação bloqueada para conferência manual. O Arkhé não documenta referência
externa persistida nem consulta de cartão por ID de cobrança. O bloqueio de
venda semelhante por cinco minutos não garante idempotência: depois desse prazo,
repetir pode cobrar novamente. Por isso o Cortaê não repete POST automaticamente
e não tenta descobrir pagamento de cartão pela consulta de Pix.

O proprietário deve conferir as movimentações e tratar resultados incertos antes
de qualquer nova cobrança. A integração não implementa estorno, transferência
automática de comissões ou reconciliação automática por semelhança de valor.

### Estrutura e credenciais

A tabela `PAGAMENTO_CARTAO` é criada pela migração manual, após backup e
verificação em banco isolado. Rotas HTTP não executam DDL. A consulta de
pagamento do agendamento e os dados do pedido permitem recuperar o estado local.

As credenciais ficam no servidor utilizado. Ao publicar snapshots Firebird,
remova os valores de `PERSONALIZACAO.ARKHE_CLIENT_ID` e
`PERSONALIZACAO.ARKHE_CLIENT_SECRET` em uma cópia, depois faça novo backup e
restauração dessa cópia para excluir versões antigas das páginas do arquivo.
Não publique diretamente o arquivo ativo do servidor. A primeira publicação
continha uma chave Arkhé; a versão atual foi limpa, mas a chave anterior precisa
ser revogada porque permanece no histórico Git.

O aplicativo Arkhé possui rotas internas de funcionários e folha salarial. Elas usam sessão com cookie, e o cadastro de funcionário exige CPF e salário. Esses contratos não equivalem à API externa com Client ID/Secret. Não foram usados para lançar comissão ou salário, nem foi feita transferência financeira.

## Comissão local e pagamentos

A comissão fica registrada no Firebird do Cortaê com atendimento, profissional, barbearia, valor-base, percentual e valor calculado. A barbearia consulta os totais e os detalhes por período para pagar seus profissionais. Esse cálculo não é apresentado como confirmação de transferência bancária.

As cobranças Arkhé continuam vinculadas aos pagamentos dos clientes. A cobrança deve usar o valor salvo no agendamento; editar o preço do serviço não deve modificar uma reserva já registrada. Pagamentos pendentes e recebimentos confirmados são separados do valor de serviços realizados e das comissões calculadas.

Uma futura automação de repasses exigiria outro contrato de API, identificação dos destinatários e confirmação de pagamento. Essa automação não faz parte desta implementação.
