# Marketplace — validação de 12/10/2026

Implementado e aplicado no Firebird local, com isolamento por barbearia e por cliente.

## Acesso

- Loja: `/marketplace`.
- Gestão: `/gestao-marketplace`, para barbearia ou administrador.
- Clientes: favoritos, carrinho, pedidos, detalhes e avaliações de compras entregues.
- A página administrativa `/help` incorpora automaticamente as novas rotas, incluindo as lojas individuais.

## Funcionalidades

- Cadastro e edição de nome, categoria, marca, preço, descrição, detalhes, até oito fotos por URL HTTPS, peso e dimensões do pacote.
- Ativação e desativação, estoque inicial, reposições com histórico e alerta de estoque mínimo.
- Carrinho e favoritos persistidos por cliente; checkout separado por barbearia.
- Preços e frete calculados no servidor, reservas de estoque, prevenção de venda concorrente acima do estoque e idempotência.
- Histórico de pedidos com valores preservados, estados de preparação, retirada e entrega.
- Pix Arkhé com credenciais da barbearia, confirmação consultada no provedor e prevenção de cobrança duplicada em resultados incertos.
- Cancelamento com devolução de estoque antes da criação do Pix. Cobrança iniciada ou paga exige conferência; não há estorno automático inventado.
- Avaliações de 1 a 5, comentário editável e média; somente compradores com o produto em pedido entregue podem avaliar.
- Frete Melhor Envio por CEP, peso, medidas e quantidade; comprador paga o frete. Retirada disponível.

## Melhor Envio

O usuário autorizou o token somente para `shipping-calculate` e `shipping-tracking`. A cotação real foi validada com CEPs públicos e um pacote fictício; nenhuma etiqueta foi criada ou comprada.

A conta mostrou limite de **três etiquetas simultâneas**, com zero aguardando postagem e carteira sem saldo. O limite não significa três fretes gratuitos.

Emissão e compra pela API permanecem desabilitadas (`MELHOR_ENVIO_EMITIR_ETIQUETAS=false`). O lojista pode emitir o envio diretamente no Melhor Envio e vincular seu UUID ao próprio pedido pago, confirmando que remetente, destinatário e itens correspondem. A API verifica a existência e o estado do envio; o vínculo é uma declaração do responsável, não uma prova automática de titularidade remota. Reutilizar o mesmo envio em outro pedido local é bloqueado.

Token apenas na configuração local do backend, ignorada pelo repositório; senha de login ausente do código. Cabeçalhos, token e respostas privadas do provedor não são retornados ao cliente.

## Verificação

- Backend: 218 testes, 19 verificações condicionais ignoradas; suíte aprovada.
- Frontend: 62 testes, lint e build aprovados.
- Revisão independente: 21 testes em Firebird restaurado e isolado, com provedores simulados.
- Teste independente React/JSDOM: detalhe, histórico, outro pedido e Pix isolado por pedido. A expressão antiga reproduziu o erro; a correção passou sem erros de renderização.
- Navegador: cadastro, edição, entrada de estoque, ativação/desativação, favorito, carrinho, cotação, checkout, Pix simulado, vínculo de envio simulado, histórico e avaliação.
- Layout móvel a 375 px sem rolagem horizontal da página.
- Corrigidas durante a QA a validação das medidas inteiras e a falha de navegação no histórico.

## Aplicação e preservação

Backup dos bancos principal e de auditoria antes da aplicação. Migração aditiva: nove tabelas `MP_*`, três sequências e configuração do limite; nenhuma tabela original removida.

**29 tabelas e 151 registros originais preservados**, incluindo todas as colunas originais. Os produtos, clientes e pedidos fictícios permaneceram no ambiente de QA. A loja real começa sem produtos cadastrados.

Frontend HTTP 200, ambos os bancos prontos em `/health`; endpoints privados anônimos retornam 401. Nenhum pagamento real efetuado e nenhum envio consumido nos testes.

Evidências externas: `C:/Users/mathe/Documents/Backups-Cortae/marketplace-20261012/`.

Documentação oficial: [cotação](https://docs.melhorenvio.com.br/reference/calculo-de-fretes-por-produtos), [compra de fretes](https://docs.melhorenvio.com.br/reference/compra-de-fretes-1), [geração](https://docs.melhorenvio.com.br/reference/geracao-de-etiquetas), [rastreio](https://docs.melhorenvio.com.br/reference/rastreio-de-envios).

## Atualização: lojas por barbearia

- `/marketplace` continua como catálogo geral de todos os estabelecimentos.
- `/marketplace/barbearias/:id_barbearia` apresenta nome, produtos e categorias exclusivos da barbearia; o ID da URL prevalece sobre os filtros da query.
- A página do estabelecimento inclui seus produtos, acesso à loja completa e a aba “Loja”. A loja funciona mesmo quando a personalização do estabelecimento ainda não foi concluída.
- Produtos e links de vendedores levam à loja correta. Mudanças rápidas entre estabelecimentos cancelam consultas antigas e não reaproveitam os dados da loja anterior.
- Loja válida sem produtos possui estado vazio próprio. Contas inválidas, bloqueadas ou não verificadas e IDs acima do limite do banco retornam 404.
- Verificação: 221 testes backend (21 condicionais ignorados), 65 testes frontend, lint/build, 5 testes independentes em Firebird e 14 verificações React de navegação, filtros, isolamento e logout.
- QA de navegador com duas barbearias: catálogo geral com cinco produtos, loja A com quatro e loja B com um; query de outra loja não alterou o catálogo individual. Página do estabelecimento, retorno do produto e layout a 375 px passaram sem erros de console.
- Aplicação sem migração ou alteração de pagamentos, credenciais e integração de entrega. Todas as 38 tabelas e 152 registros presentes antes desta atualização foram preservados.
- Evidências: `C:/Users/mathe/Documents/Backups-Cortae/lojas-por-barbearia-20261012/` e relatório independente `marketplace-20261012/independent-review/own-stores-independent-review.json`.
