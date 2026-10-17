# Arkhé e comissões no Cortaê

Inspeção em 10/10/2026. Em 11/10/2026, o usuário esclareceu que o Cortaê deve calcular as comissões por percentual de cada barbeiro e mostrar quanto a barbearia deve pagar. O pagamento aos profissionais é realizado pela barbearia. Não é requisito enviar comissões ou estatísticas para a API Arkhé, nem executar repasses automáticos.

## Evidência atual

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

As requisições da integração usam `X-Client-ID` e `X-Client-Secret`, exclusivamente no backend. Não foi identificado endpoint documentado para gravar comissão, vincular barbeiro, dividir recebimento, executar repasse ou armazenar indicadores de agendamento.

O aplicativo Arkhé possui rotas internas de funcionários e folha salarial. Elas usam sessão com cookie, e o cadastro de funcionário exige CPF e salário. Esses contratos não equivalem à API externa com Client ID/Secret. Não foram usados para lançar comissão ou salário, nem foi feita transferência financeira.

## Comissão local e pagamentos

A comissão fica registrada no Firebird do Cortaê com atendimento, profissional, barbearia, valor-base, percentual e valor calculado. A barbearia consulta os totais e os detalhes por período para pagar seus profissionais. Esse cálculo não é apresentado como confirmação de transferência bancária.

As cobranças Arkhé continuam vinculadas aos pagamentos dos clientes. A cobrança deve usar o valor salvo no agendamento; editar o preço do serviço não deve modificar uma reserva já registrada. Pagamentos pendentes e recebimentos confirmados são separados do valor de serviços realizados e das comissões calculadas.

Uma futura automação de repasses exigiria outro contrato de API, identificação dos destinatários e confirmação de pagamento. Essa automação não faz parte desta implementação.
