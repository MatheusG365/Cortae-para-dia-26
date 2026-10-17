# Limpeza de código e regressão

Concluída em 12/10/2026. Projeto: JOHN2-main.

## Mudanças

Foram revisados os módulos de aplicação, componentes, páginas, serviços, imports, rotas e testes. A lógica repetida foi concentrada em funções compartilhadas, mantendo as regras específicas de cada fluxo.

- Backend: respostas JSON, criação idempotente de objetos do Firebird, identificação de agendamentos nas descrições financeiras, normalização de contatos e bloqueios por usuário.
- Frontend: formatação de valores e datas, períodos de consulta, normalização de contatos, filtros de URL, consultas com cancelamento, estados da agenda e solicitação de pagamento.
- Consultas compartilhadas invalidam dados ao mudar conta, papel, rota, filtro, função de consulta ou versão de recarga. Respostas de consultas antigas não são reaproveitadas.
- Foram ajustados 24 módulos existentes do backend e 30 do frontend. Quatro helpers Python e três JavaScript foram adicionados, além de dois arquivos de testes.
- Nove funções sem chamadas, imports, rotas ou referências documentadas foram removidas. Dois scripts de alteração antigos, `Frontend/src/pages/Agendamento/remove_duplicate.py` e `replace_payment.py`, foram excluídos após verificar que apontavam para outro checkout e tinham cópias idênticas no backup.

Não foram fundidas validações com limites, mensagens ou permissões diferentes. Inicialização de estado local e opções de formulários permanecem locais quando a extração só acrescentaria indireção. Imports que registram rotas, classes CSS dinâmicas, configuração de editor, auxiliares usados por ferramentas de teste e scripts de manutenção foram preservados.

## Testes antes e depois

| Verificação | Antes | Depois |
| --- | --- | --- |
| Suíte completa do backend, integrações Firebird habilitadas | 238 casos: 237 aprovados e 1 ignorado | 244 casos: 243 aprovados e 1 ignorado |
| Testes do frontend | 65 aprovados | 74 aprovados |
| Lint | Aprovado | Aprovado |
| Build | Aprovado | Aprovado |
| Rotas do backend | 125 | 125, preservadas |
| Rotas do frontend | 35 | 35, preservadas |

O único caso ignorado depende de permissão do Windows para criar um link simbólico no teste de segurança de caminhos. As três integrações opcionais com Firebird foram habilitadas e executadas em bancos descartáveis.

Revisão independente:

- 210 verificações HTTP tiveram os mesmos métodos, status e respostas do código anterior.
- 126 casos numéricos conservaram resultados, tipos, exceções e mensagens.
- 43 testes aprovados no conjunto de revisão de integração: 21 unitários e 22 com bancos Firebird descartáveis.
- Sete cenários React conservaram o comportamento anterior. Mais 22 verificações cobriram identidade da conta, mudança de papel, consultas atrasadas, cancelamento, erro, recarga e desmontagem.
- Exclusões auditadas por referências, imports, documentação e registro de rotas. Nenhuma rota foi removida.

A verificação no navegador usou autenticação pelo endpoint de login, contas fictícias e bancos separados. Login, caixa/comissões e loja individual renderizaram corretamente; o console da aba de teste não registrou erros. Os testes de provedores usaram respostas simuladas, sem pagamentos, fretes ou mensagens reais.

## Aplicação e preservação

Foi criado backup dos dois bancos e de 232 arquivos de código/documentação antes das edições, fora do projeto. Após reiniciar a aplicação, a comparação confirmou **40 tabelas e 152 registros originais preservados**, incluindo todas as colunas e valores anteriores. `/health` confirmou os dois bancos disponíveis e o frontend respondeu HTTP 200.

Nenhuma alteração em credenciais, dependências ou regras de negócio. A taxa de 1,5% permanece pendente, o termo permanece em rascunho e a emissão de etiquetas continua desativada conforme as decisões anteriores.

Evidências e cópias de recuperação:

- `C:/Users/mathe/Documents/Backups-Cortae/limpeza-20261012/source/`
- `backend-final-all-firebird.log`, `frontend-final.log`, `lint-final.log`, `build-final.log`
- `backend-final-manifest.json`, `frontend-manifest.json`, `frontend-deletions.json`
- `independent-review/independent-review-final.json`
- `production-preservation-result.json`
- `gestao-qa-final.png`, `loja-qa-final.png`

Os dados fictícios e os scripts usados somente para a validação permanecem fora do projeto.
