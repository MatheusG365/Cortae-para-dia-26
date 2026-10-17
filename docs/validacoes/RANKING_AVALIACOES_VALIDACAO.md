# Ranking de profissionais e avaliações

O salão e o administrador podem comparar a equipe por valor dos serviços, quantidade
de atendimentos concluídos ou média das avaliações, com um período de até 366 dias.
O administrador precisa selecionar o estabelecimento. Cada salão vê seus próprios
dados; profissionais veem apenas os comentários e o resumo de suas próprias visitas.

## Métricas

- Entram atendimentos com status `concluido` e horário final já passado. O período
  considera a data de início do atendimento, incluindo o último dia selecionado.
- `faturamento` soma somente `AGENDAMENTO.VALOR_TOTAL`, preservado no momento da reserva
  ou informado ao concluir um atendimento antigo. É valor dos serviços realizados,
  não dinheiro recebido, saldo bancário ou comissão.
- Valores antigos ausentes permanecem ausentes. O relatório contabiliza esses
  atendimentos em `sem_valor_historico` e não consulta preços atuais para estimá-los.
- Profissionais inativos e sem atendimentos continuam na lista. Reservas sem um
  profissional do salão ficam separadas em `resumo.sem_profissional`.
- Notas vão de 1 a 5. Sem avaliações, `media_nota` é `null`. A ordenação usa a média
  antes de arredondar o número exibido. Empates têm a mesma posição: 1, 1, 3.
  Nome e ID organizam os empatados de maneira determinística.

## Avaliação do atendimento

O cliente autenticado pode avaliar somente sua própria reserva, após o fim de um
atendimento concluído. Há uma avaliação por reserva, editável pelo mesmo cliente;
editar não altera `criado_em`. O comentário é opcional, com até 1000 caracteres.
Notas booleanas, decimais e strings são recusadas. A gravação segue o bloqueio
salão → agendamento usado nas demais alterações de agenda. A chave primária impede
votos duplicados. Um conflito concorrente retorna 409 para atualização e nova tentativa.

Caso o status deixe de ser concluído, a avaliação permanece armazenada, mas não é
exibida nem contabilizada enquanto o atendimento não voltar a ser elegível.
Auditoria usa o módulo existente e é emitida depois do commit da avaliação.

## Contrato

- `GET /gestao/ranking?inicio=YYYY-MM-DD&fim=YYYY-MM-DD&ordenar=faturamento|atendimentos|avaliacao`
  retorna `id_barbearia`, `periodo`, `criterio`, `resumo` e `profissionais`.
  Para administrador, acrescentar `id_barbearia`.
- `GET /gestao/avaliacoes` aceita o mesmo período, `id_barbearia` para administrador,
  `id_funcionario` opcional e `pagina`. Retorna `periodo`, `avaliacoes`, `pagina`,
  `total` e `paginas`. Cada página tem no máximo 20 avaliações.
- `GET /agendamentos/<id>/avaliacao` retorna `avaliacao` e `pode_avaliar` somente
  ao cliente dono da reserva. `PUT` recebe `nota` inteira e `comentario` opcional.
  Não existe endpoint para o proprietário ou profissional editar a nota do cliente.
- A serialização de agendamentos acrescenta `avaliacao` e `pode_avaliar`.
- `GET /barbeiro/painel` acrescenta `resumo_avaliacoes` (`media_nota`,
  `total_avaliacoes`) do período selecionado. Comentários estão nos próprios
  agendamentos do profissional.

## Banco e validação

Depois de backup verificado, executar `ranking_schema.migrar_ranking_avaliacoes()`.
Ela cria somente `AGENDAMENTO_AVALIACAO`, com chave primária e estrangeira para a
reserva, restrição de nota e timestamps. Repetir a migração preserva os dados.
O arranque normal já chama essa migração em `main.py`.

Na pasta `Backend`, executar:

```powershell
$env:RUN_FIREBIRD_RANKING_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Os testes Firebird desta funcionalidade criam e removem bancos descartáveis em
diretórios temporários, sem abrir os bancos de produção. Validam migração repetida
com preservação das reservas, SQL de ranking e comentários, isolamento entre
clientes e salões, reservas futuras e canceladas, edição e concorrência de votos.
Os testes de integrações preexistentes usam provedores simulados. Nenhuma chamada
à Arkhé, WhatsApp, SMTP ou OpenAI foi adicionada à funcionalidade.
