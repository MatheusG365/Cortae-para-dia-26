# Gestão local — validação do backend

Implementação: `Backend/gestao_schema.py`, `Backend/gestao.py`; compatibilidade de recebimentos parciais em `Backend/pagamento.py`. Integração e documentação geral coordenadas separadamente.

Todas as páginas de gestão exigem proprietário ou administrador, com escopo de salão. Administrador informa `id_barbearia`; proprietário não pode substituir o próprio salão. Logs exigem administrador e usam o banco de auditoria separado. Dados sensíveis históricos são mascarados na leitura, inclusive objetos JSON aninhados.

Clientes e histórico financeiro derivam somente de agendamentos vinculados ao salão. Relatórios usam preço histórico aceito, nunca o catálogo atual; valores históricos ausentes permanecem explícitos. Categorias são desativadas sem apagar histórico. Lançamentos manuais possuem vencimento, data efetiva de pagamento e estados pendente/pago/cancelado. Caixa diferencia entradas recebidas, despesas pagas e valores pendentes, incluindo comparação com período anterior.

Recebimentos locais admitem dinheiro, cartão físico e Pix manual, confirmados apenas pelo proprietário/administrador. Cada recebimento espelha uma linha FINANCEIRO; a soma considera esse espelho apenas uma vez e inclui pagamentos legados exatos por agendamento e cliente. Parcelas reduzem o saldo, sem marcar o atendimento inteiro quitado. A confirmação antiga de pagamento na hora recebe somente o restante. Cobranças pendentes repetidas não duplicam dívida.

Pagamentos manuais de comissão respeitam a comissão histórica, admitem pagamento parcial e criam uma única despesa financeira vinculada e imutável por parcela. Não executam transferências. Atendimentos cancelados ou com falta não aceitam novos recebimentos; pagamento de comissão exige atendimento concluído e profissional correspondente ao registro histórico. Chaves de idempotência opcionais impedem repetição de parcelas; reaproveitamento com outro conteúdo é recusado.

Verificação em 11/10/2026:

- **141 testes backend passaram**, incluindo 13 novos testes de gestão/compatibilidade. Sem chamadas reais de IA, SMTP ou pagamento.
- **85 assertivas Firebird** em banco restaurado exclusivo: permissões, relações de clientes, notas, relatórios históricos, categorias, caixa, cancelamento, legado misto, três formas locais, idempotência, comissões parciais e concorrência. Inclui duas requisições simultâneas de recebimento, de comissão e de recebimento novo contra a confirmação antiga.
- **26 assertivas complementares**: falha provocada reverte recibo e FINANCEIRO e não cria auditoria falsa; atualização de notas registra auditoria; todas as **146 linhas das 18 tabelas originais** permanecem com os mesmos valores nas colunas originais após inserir os dados fictícios.
- Migração `migrar_gestao()` executada duas vezes, sem alteração de linhas/colunas existentes; adiciona seis tabelas e quatro sequências.

Artefatos reproduzíveis e bancos preservados fora do projeto: `C:\Users\mathe\Documents\Backups-Cortae\parciais-20261011-012332`, scripts `gestao_restore.py`, `qa_gestao.py`, `gestao_finish.py`; banco `qa-gestao.FDB`, auditoria limpa `log-gestao-clean.FDB`, referência `qa-gestao-baseline.FDB`. Backups `.fbk` anteriores foram preservados. O teste que insere um log histórico usa identidade automática; uma versão inicial da fixture atribuía manualmente ID e causou colisão no banco de teste, corrigida na fixture. Auditoria também foi revalidada no banco restaurado limpo.

Nenhuma migração ou alteração de dados foi aplicada à produção nesta validação. Integrações externas existentes foram preservadas; o novo fluxo local não chama provedores. Revisão independente final e validação visual cabem ao coordenador/revisor seguinte.
