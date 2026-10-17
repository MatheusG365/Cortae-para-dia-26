# Termos de uso e taxa da plataforma

Atualização: 12/10/2026, horário de São Paulo.

## Entrega

- Página pública `/termos-de-uso`, com índice, identificação do responsável, versão e acesso no rodapé.
- Aceite explícito da própria conta, sem caixa pré-marcada. O banco guarda data, versão, hash e cópia do texto aceito. Contas antigas e contas criadas por terceiros não recebem aceite inventado.
- Cadastro, agendamento e checkout usam o estado de publicação e a versão corrente. Mudanças relevantes exigem novo aceite. Enquanto o documento está em rascunho, o uso existente continua disponível.
- Taxa de 1,5% calculada no servidor sobre produtos ou serviços, sem frete. Arredondamento decimal ao centavo, uma vez por operação. Modos preparados: acréscimo pago pelo cliente ou obrigação da barbearia.
- Resumo antes da confirmação, protegido por assinatura e comparação dos preços. Alterações entre a consulta e a gravação exigem nova confirmação, sem criar reserva ou consumir estoque.
- Snapshot por compra/agendamento; históricos anteriores conservam seus valores e não recebem cobrança retroativa. Comissão do profissional continua baseada nos serviços. Reagendamento conserva o snapshot. Cancelamento e falta preservam o histórico, com taxa devida anulada, sem afirmar que houve estorno.
- Gestão → Taxas da plataforma: relatório por estabelecimento e período, separando registro histórico, taxa prevista e repasse pendente de operações cujo pagamento do cliente foi confirmado.
- O relatório não executa nem confirma transferência da taxa à plataforma. A integração de pagamento existente não recebeu uma função de divisão automática do pagamento.

## Configuração ainda necessária

O usuário ainda deve definir quem paga a taxa: cliente ou barbearia. Também faltam os dados reais do responsável: nome/razão social, documento, endereço e contato. Por isso, a configuração real permanece pendente; o termo é rascunho e nenhuma taxa nova é cobrada.

As chaves de configuração estão documentadas em `Backend/.env.example`: `PLATAFORMA_TAXA_PAGADOR`, `TERMOS_RESPONSAVEL_NOME`, `TERMOS_RESPONSAVEL_DOCUMENTO`, `TERMOS_RESPONSAVEL_CONTATO`, `TERMOS_RESPONSAVEL_ENDERECO`. Credenciais e a configuração local existente não foram alteradas.

## Verificação

- Backend: 238 testes passaram, com 23 casos condicionais ignorados.
- Frontend: 65 testes passaram; lint e build aprovados.
- Revisão independente: 17 testes com cópias descartáveis do Firebird e 45 verificações React passaram.
- Casos monetários: cliente R$ 70,00 + R$ 1,05 = R$ 71,05; barbearia R$ 70,00 + frete R$ 12,34 mantém total do cliente em R$ 82,34, taxa R$ 1,05 e líquido dos produtos/serviços em R$ 68,95.
- Verificados aceites reais, isolamento entre contas e estabelecimentos, mudança de versão, repetição de pedido, cancelamento, comissão, saldo de recebimentos, alteração concorrente de preços e ausência de cobrança retroativa.
- Provedores de pagamento, frete e e-mail simulados. Nenhum pagamento, envio ou transferência real foi executado.
- Root verificou o resumo de agendamento no navegador e em tela de 375 px, sem transbordamento horizontal. Evidências externas em `C:/Users/mathe/Documents/Backups-Cortae/termos-taxa-20261012`.
- Backup dos dois bancos antes da aplicação: 38 tabelas e 152 linhas originais. A comparação após aplicar a migração confirmou todas as colunas e linhas originais preservadas. Os dois bancos ficaram disponíveis em `/health`; a API real confirmou termo em rascunho e taxa desativada.

Relatório independente: `C:/Users/mathe/Documents/Backups-Cortae/termos-taxa-20261012/independent-review/final-independent-review.json`.

## Referências do texto

O modelo preserva os direitos do consumidor e distingue aceite contratual de consentimento para publicidade. Referências oficiais consultadas: [Código de Defesa do Consumidor](https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm), [Decreto 7.962/2013](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/decreto/d7962.htm), [LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm). O texto permanece em rascunho até completar identificação e política comercial.

