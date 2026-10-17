# Módulos comerciais — validação em 13/10/2026

Os itens 13, 19, 20, 32, 35 e 40 foram implementados no frontend, backend e Firebird. A aplicação local está disponível em http://127.0.0.1:5173.

## Funcionalidades e acesso

| Item | Entrega | Onde acessar |
| --- | --- | --- |
| 13 | Fornecedores, custo de compra e margem bruta dos produtos. Dados de custo e fornecedor ficam restritos à gestão. | `/gestao-marketplace?aba=fornecedores` e edição do produto |
| 19 | Lista de desejos separada dos favoritos, promoções com período e destaque de lançamentos. | `/marketplace/lista-desejos`, catálogo e edição do produto |
| 20 | Receita de produtos, pedidos criados e pagos, ticket médio, descontos, frete, custos e lucro bruto, agrupamento diário/mensal e exportação CSV. | `/gestao-marketplace?aba=vendas` |
| 32 | Cadastro e acompanhamento de metas por profissional, quantidade de atendimentos ou valor dos serviços realizados. Profissionais consultam somente suas próprias metas. | `/gestao?aba=metas` e painel do profissional |
| 35 | Variações com tamanho, cor e volume; preço, custo e estoque próprios; ativação, edição e entradas de estoque. | Gestão do produto e seleção na página do produto |
| 40 | Cupons por loja, desconto fixo ou percentual, validade, ativação e limite de utilizações. | `/gestao-marketplace?aba=cupons` e checkout |

A loja individual está incorporada em `/estabelecimento?usuario=ID#loja-barbearia`, com as cores escolhidas pelo estabelecimento. `/marketplace` reúne todas as lojas. URLs antigas de loja redirecionam para a página do estabelecimento, preservando os filtros permitidos.

O bloco de cupom tem botão destacado, remoção discreta e economia exibida somente após confirmação dos valores pelo servidor. Enter no campo aplica o código sem criar o pedido. Códigos inválidos não mantêm a mensagem de economia nem permitem finalizar com um resumo inválido.

## Regras verificadas

- A promoção altera o preço efetivo no catálogo, carrinho e checkout. A edição usa o preço original de cadastro.
- Cada variação ocupa uma linha distinta do carrinho. Produtos com variações exigem uma escolha e descontam apenas o estoque correspondente.
- O cupom desconta produtos, sem incluir frete. Seu limite é reservado na criação do pedido. Cancelamentos permitidos liberam a reserva e o estoque uma única vez. Repetições da mesma requisição não duplicam reservas.
- O período do relatório considera a criação dos pedidos. A receita considera somente pedidos pagos e não cancelados. Frete aparece separado do faturamento de produtos. Custos históricos são preservados; custo desconhecido gera lucro não calculado.
- Metas consideram atendimentos concluídos e já realizados, com o valor histórico do serviço. Não representam recebimento em caixa.
- Catálogo, carrinho, pedidos e perfil público não expõem fornecedores, custos, credenciais bancárias ou dados privados de funcionários. APIs privadas continuam exigindo autenticação.
- As cinco cores escolhidas permanecem preservadas. Textos derivados recebem contraste legível quando necessário, e o tema de uma loja não se propaga para outra ou para o catálogo geral.

## Testes e aplicação

- Backend: 281 casos, 280 aprovados e 1 ignorado porque o Windows não permitiu criar o link simbólico usado por esse teste. Inclui 40 testes em bancos Firebird descartáveis.
- Frontend: 94 testes aprovados; lint sem avisos e build aprovado.
- Revisão independente: 13 cenários de backend e 55 verificações anteriores de frontend; revisão final acrescentou 23 verificações do cupom, 15 do catálogo com sessão expirada e repetiu 18 verificações de isolamento do tema. A matriz de contraste verificou 5.476 combinações de cores.
- Navegador: loja integrada, duas paletas, catálogo geral, edição de custos, estoque por variação, lista de desejos, vendas e metas do profissional. Cupom validado com subtotal fictício de R$ 63,84, desconto de R$ 6,38 e total de R$ 57,46; erro e remoção também conferidos. Tela de 390 px sem rolagem horizontal no diálogo.
- Migrações aplicadas: 49 tabelas no banco principal, incluindo as 9 novas tabelas comerciais/metas. As 40 tabelas anteriores e seus 152 registros mantiveram exatamente os valores das colunas originais.
- Saúde após aplicação: banco principal e banco de log disponíveis; servidor e frontend respondendo.
- Loja pública conferida na versão aplicada: sessão expirada não gera aviso indevido no catálogo; favoritos, desejos e alterações continuam protegidos.

Os testes de pagamento, entrega e mensagens usaram provedores fictícios e bancos isolados. Não houve compra real, emissão de etiqueta ou teste de envio real. A taxa e os termos continuam no estado anterior de rascunho/inativo; a integração do Melhor Envio continua limitada à autorização existente de cotação e rastreio.

## Evidências locais

Backups do banco principal e de log, cópia dos fontes anteriores, resultados, revisão e capturas de tela estão em `C:\Users\mathe\Documents\Backups-Cortae\comercial-20261013`.

Arquivos principais: `backend-final-validation.json`, `backend-final-all-tests.log`, `production-preservation-result.json`, `review\independent-review-final.json`, `review\independent-review-delta-final.json` e `browser-qa\final-coupon-qa.json`.
