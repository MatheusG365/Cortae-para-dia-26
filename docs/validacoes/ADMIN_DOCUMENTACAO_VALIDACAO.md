# Navegação administrativa e documentação — 13/10/2026

## Alterações aplicadas

- Removido o botão redundante `VOLTAR` do cabeçalho do administrador. Os links das páginas, perfil, saída e menu de celular permanecem disponíveis.
- `/help` atualizado para explicar a loja integrada, fornecedores, custos e margem, promoções, lista de desejos, variações, estoque, cupons, vendas, metas, ranking, avaliações e termos. O catálogo lê as rotas atuais e os mesmos contratos usados pelo Swagger.
- Incluído no `/help` o link **Documentação da API**, disponível após carregar a consulta administrativa.
- O arquivo de documentação existente é `Backend/api_docs.py`. Ele e o novo `Backend/docs_contracts.py` documentam 134 caminhos e 164 operações reais, com parâmetros de URL corretos e identificadores únicos. O catálogo Help inclui as 36 páginas do frontend e todas as regras registradas no Flask.
- `/docs` e `/openapi.json` agora exigem administrador ativo e confirmado, tanto em `GET` quanto em `HEAD`. Sem sessão válida retornam `401`; outros perfis recebem `403`. A função existente de autenticação recarrega o perfil no banco a cada consulta, aplicando mudanças de perfil e bloqueios imediatamente.
- Respostas autorizadas e negadas impedem cache com `private, no-store`, diferenciam Cookie/Authorization e usam `nosniff`. A documentação não é gerada antes de autorizar o acesso.
- Swagger funciona pelo proxy do frontend e diretamente no backend, usa a sessão autenticada e não persiste credenciais. A autorização para consultar a documentação não substitui as permissões das operações descritas.

## Acesso

Entre com uma conta de administrador na aplicação e digite `http://127.0.0.1:5173/help`. O botão **Documentação da API** abre `http://127.0.0.1:5173/api/docs`, usando a mesma origem e sessão. O JSON está em `/api/openapi.json`.

Também é possível acessar `/docs` e `/openapi.json` diretamente no backend, desde que o navegador envie uma sessão administrativa válida para essa origem. `localhost` e `127.0.0.1` possuem cookies separados.

## Verificações

- Backend completo com as quatro opções de Firebird habilitadas: **289 testes, 288 aprovados e 1 ignorado** por indisponibilidade de link simbólico no Windows. Inclui os 40 testes existentes em bancos Firebird descartáveis e 8 novos testes de documentação.
- Frontend: **94 testes aprovados**, lint sem avisos e build aprovado.
- Revisão independente: 77 cenários HTTP de autenticação, outros perfis, sessão expirada, mudança de perfil, bloqueio, conta não confirmada, exclusão, falha de banco e prioridade do cookie; 23 verificações do cabeçalho/Help e 22 do JavaScript do Swagger.
- Navegador em ambiente isolado: login de administrador fictício, cabeçalho sem Voltar, busca por cupom no Help, contrato atualizado e consulta GET pelo Swagger retornando `200` na URL correta do proxy. Menu a 390 px sem rolagem horizontal.
- Versão principal após reiniciar: 16 requisições anônimas GET/HEAD ao backend direto e proxy confirmaram `401`, ausência de contrato/código e cabeçalhos de proteção.
- Banco principal preservado: mesmas 49 tabelas, 152 registros e valores de todas as colunas antes e depois. Banco principal e banco de log disponíveis em `/health`.

Não foram alterados pagamentos, integrações, configuração de credenciais, taxa, autorização de etiquetas ou dados de negócio. Os testes não acionaram provedores reais.

## Evidências

Backups dos fontes, logs, revisão independente, capturas e fingerprints estão em `C:\Users\mathe\Documents\Backups-Cortae\admin-docs-20261013`.

Arquivos principais: `backend-all-firebird-tests.log`, `frontend-tests.log`, `frontend-lint.log`, `frontend-build.log`, `independent-review.json`, `applied-http.json`, `database-preservation.json`, `help-menu-adm-final.png` e `swagger-consulta-200.png`.


## Atualização de 18/10/2026 — contrato 2.2.0

- Help atualizado com reserva sem profissional, escolhas de corte, PDF da ficha gerado no navegador, CEP/remetente, endereços salvos com gravação explícita, termos/taxa e tratamento de indisponibilidade do Pix.
- `api_docs.py` documenta profissional opcional/null, escolha_corte e confirmacao_resumo. Corrigida a descrição antiga que tornava o profissional obrigatório com equipe ativa.
- `docs_contracts.py` descreve os envelopes de CEP e endereços, parâmetros de CEP, HTTP 201 de cadastro e HTTP 428 de aceite. Cadastro com versão incorreta retorna 428; resumo alterado continua 409.
- Respostas do OpenAPI agora são copiadas por operação, evitando que uma personalização de schema altere contratos de outras rotas.
- Mantida a documentação de manutenção manual: API/rotas não criam tabelas; python -m migrations apenas confere, --aplicar exige execução explícita após backup.
- Nenhuma rota nova, mudança de permissão, aceite real ou chamada a provedor foi feita nesta atualização documental.

Validação: 44 casos executados, 43 aprovados e 1 ignorado pela limitação de links simbólicos no Windows. Cobertura de todos os métodos/caminhos atuais, parâmetros, IDs únicos, sessão ADM, ausência de cache e bloqueio de leitura de configuração preservados. HTTP real: health 200; Help, /docs e /openapi.json anônimos 401 com private, no-store. Logs: C:/Users/mathe/Documents/Backups-Cortae/limpeza-20261018/docs-final.log.
