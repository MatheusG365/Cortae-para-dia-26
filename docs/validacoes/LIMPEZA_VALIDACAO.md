# Limpeza de código e regressão

## Atualização de 18/10/2026

A API passou a usar o banco já preparado: iniciar o servidor, abrir a agenda ou consultar o financeiro não cria tabelas, altera colunas, realinha sequences nem migra registros legados.

- Preparação de banco isolada em `Backend/migrations/`, com um único comando: `python -m migrations` confere sem escrever; `python -m migrations --aplicar` é manutenção manual após backup. Exige um banco base existente.
- `/health` confere os campos obrigatórios e a largura da origem financeira sem modificar dados. A base local tem as 52 tabelas e os 410 campos esperados; as 30 sequences declaradas estão presentes, sem sequences base atrasadas.
- Arquivos Python na raiz do backend: 57 → 44. Módulos de esquema foram organizados na pasta de manutenção.
- Retirados `merge_sessions.py`, `atualizar_referencias.py`, `verificar_categorias.py`, `verificar_servicos.py` e o arquivo inválido `git.ignore`. Foram retiradas cinco funções sem chamadas e duas constantes de extensões sem uso.
- O manifesto antigo do catálogo foi movido para `docs/referencias/catalogo_cortes.json`, como histórico documental. Cadastro/edição de imagens continuam pelas telas do sistema e pelo Drive.
- Configuração duplicada de BASE_DIR, flag STARTUP_MIGRATIONS e padrões repetidos do .gitignore foram removidos. Credenciais, bancos, templates de e-mail e ambiente .venv foram preservados.
- A pasta local .idea e caches de Python foram retirados da pasta do backend, com cópia recuperável fora do projeto. O Python pode recriar caches normalmente.
- A busca de dependências do frontend não encontrou módulos JS/JSX/CSS sem ligação ao ponto de entrada; nenhuma página foi excluída por suposição.
- Inventário por decoradores: 176 combinações de rota/método antes e depois, sem remoção de endpoints. Help, contratos OpenAPI e READMEs atualizados.

### Validação

- Backend: **501 casos, 500 aprovados e 1 ignorado por limitação de links simbólicos no Windows**. Integrações Firebird habilitadas em bancos temporários independentes; sem cobrança bancária, envio real de e-mail ou alteração de dados da base principal.
- Frontend: **124 aprovados**, lint sem erros e build de produção aprovado.
- Novas regressões verificam importação da API sem conexão ou DDL, detecção de campos ausentes sem escrita, manutenção manual e ausência de DDL nos módulos de requisição.
- Testes de snapshot foram ajustados para executar a atualização de estrutura explicitamente. Com estrutura antiga não preparada, a consulta falha sem alterar a coluna nem perder o histórico.
- Conferência manual do banco: estrutura completa, sem alterações realizadas.
- HTTP real após reiniciar: health pronto; marketplace e consulta de horários HTTP 200; OpenAPI e endereços sem autenticação HTTP 401.

Fontes anteriores e arquivos retirados estão em `C:/Users/mathe/Documents/Backups-Cortae/limpeza-20261018/`. Logs completos de backend, integração, testes frontend, lint/build e inventário de rotas estão nessa mesma pasta. Nenhuma tabela de negócio foi apagada.

## Histórico — 12/10/2026

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
