# Cartão virtual Arkhé — 19/10/2026

## Entrega

Pagamento com cartão virtual Arkhé disponível nos agendamentos e nas compras do
marketplace, no site e no aplicativo. O contrato utilizado é o fornecido pelo
responsável: `POST /api/v1/vendas/cartao`. O fluxo anterior supunha um checkout
de cartão que não consta nesse contrato.

- Débito em uma parcela; crédito de uma a 15 parcelas, mínimo de R$ 0,01 por parcela.
- Número com 16 dígitos, validade `MM/YYYY` e CVV textual, inclusive zeros à esquerda.
- Confirmação explícita do cliente, recibo e recuperação do resultado local.
- Valor calculado pelo servidor a partir do pedido ou agendamento salvo.
- No crédito, o cliente quita o total bruto; a taxa de 5% reduz o recebimento do estabelecimento.
- Número completo, validade, CVV e PIN não são persistidos pelo fluxo. Campos são limpos após envio e saída.

O cartão é o cartão virtual interno da Arkhé. Não foi adicionada aceitação geral
de cartões de outras bandeiras, estorno ou transferência automática de comissões.

## Proteção contra cobrança repetida

A tabela `PAGAMENTO_CARTAO` registra uma reserva durável antes do envio externo.
Travas e chave do alvo impedem cobranças concorrentes para o mesmo pedido.
Uma aprovação já salva devolve o recibo, sem outro POST. Recusa conhecida permite
nova tentativa explícita. Timeout, HTTP 409, resposta inconsistente e falha na
confirmação local bloqueiam nova cobrança até conferência manual das movimentações.

O provedor não documenta idempotência persistente nem consulta de cartão por
ID de cobrança. A consulta do cartão usa o banco local, sem recorrer à rota Pix.
O bloqueio também cobre pagamento por Pix, boleto e recebimento manual enquanto
a tentativa de cartão estiver em processamento ou incerta.

## Falhas encontradas e corrigidas

1. A integração anterior usava uma rota de checkout incompatível com a documentação recebida.
2. Um índice composto com ID ainda NULL impedia duas reservas distintas da mesma barbearia.
3. A primeira alternativa de índice parcial exigia ODS 13.1; o banco ativo usa ODS 13.0.
4. O recibo recuperado de agendamento precisava dos campos de método e status esperados pelas telas.

Os índices finais são `UNIQUE COMPUTED BY`: retornam NULL para tentativa sem ID
do provedor e uma chave `barbearia:ID` após a resposta. Isso permite reservas
distintas e impede reaproveitar IDs na mesma barbearia. A migração usa o catálogo
compatível com ODS 13.0 e preserva os índices corretos ao ser reaplicada.

## Banco local e cópias publicadas

Backup completo dos bancos principal e de auditoria realizado e restaurado fora
do projeto antes da conclusão da migração. Diretório local:
`C:\Users\mathe\Documents\Backups-Cortae\arkhe-live-migration-20261019-182123`.

A migração foi aplicada ao banco ativo: **53 tabelas, 288 registros preservados,
zero tentativas de cartão e nenhuma pendência de estrutura**. O formato do banco
ativo permaneceu **ODS 13.0**. Não houve conversão ou substituição do arquivo ativo.

Os dois arquivos FDB publicados são cópias independentes, obtidas por backup e
restauração. As credenciais Arkhé foram removidas da cópia principal; campos
sensíveis de auditoria foram protegidos na cópia de log. Um segundo backup e
restauração eliminou versões antigas das páginas. As cópias preservam as contagens:
principal com 53 tabelas/288 registros e auditoria com 1 tabela/4.896 registros.
Foram verificadas a estrutura de cartão e a ausência binária das credenciais
conhecidas em UTF-8 e UTF-16. Os arquivos ativos não foram substituídos.

As credenciais reais continuam privadas no servidor. Por isso os arquivos FDB
ativos podem aparecer modificados em relação aos snapshots publicados. Não use
`git add` diretamente nesses arquivos para atualizar as cópias públicas.

## Verificação

Todos os testes de backend e Firebird desta entrega usaram **Python de 32 bits**.
Cobranças foram simuladas; os testes financeiros usaram bancos descartáveis fora
do projeto.

- 17 casos financeiros em Firebird real: concorrência, reserva confirmada antes do POST, falhas de commit e perda de confirmação, recusas, timeout/409, valores, permissão e proteção de dados.
- Caso adicional em cópia fria de arquivo ODS 13.0 real: dois NULL na mesma barbearia aceitos, IDs repetidos rejeitados, IDs iguais em outra barbearia aceitos, segunda migração sem DDL e arquivo original intacto.
- Após a mudança dos índices, casos afetados de aprovação e duplicidade foram conferidos novamente.
- 14 testes de núcleo e compatibilidade de catálogo aprovados.
- 58 testes focados de site/aplicativo aprovados, incluindo 34 novos.
- Site: lint e build aprovados. Aplicativo: lint sem avisos e verificação de tipos de 92 fontes aprovada.
- Após a migração, `/health` retornou HTTP 200, com ambos os bancos prontos. As duas rotas de cartão rejeitaram acesso sem login com HTTP 401.

As verificações de interface desta etapa foram automatizadas; não houve nova
execução em emulador/dispositivo nem compra real. O relatório Android anterior
continua disponível, mas não comprova uma transação real com cartão nesta entrega.

## Credenciais e limite externo

A nova integração foi configurada somente no servidor e respondeu HTTP 200 em
`GET /api/v1/conta`. Nenhuma cobrança real foi enviada.

A primeira publicação do banco continha uma chave Arkhé. A versão atual do banco
foi limpa, mas a chave antiga permanece no histórico Git. Mesmo após o responsável
informar a revogação, uma requisição nova, sem cookies e sem cache, ainda retornou
HTTP 200 com a chave anterior. A nova também retornou 200; o controle com chave
inválida retornou 401. Isso demonstra aceitação da chave antiga para essa consulta,
sem afirmar que cobranças com ela foram testadas. A revogação efetiva depende do
Arkhé. O responsável escolheu manter o repositório público após ser informado.

[Integração e contratos](../integracoes/ARKHE_INTEGRACAO.md) ·
[Índice da documentação](../README.md)
