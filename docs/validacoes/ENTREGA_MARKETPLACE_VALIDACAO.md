# Entrega e marketplace — validação em 18/10/2026

- Cards, carrinho, modal e opções de entrega: branco, borda visível e texto escuro.
- Foto principal: usa a cor de destaque da loja e preserva proporção (object-fit: contain).
- Consulta ViaCEP: serviço gratuito, CEP enviado exclusivamente pelo backend ao host HTTPS fixo. Não envia nome, documento ou contato ao ViaCEP.
- Consulta disponível para cliente e para remetente da própria barbearia; administrador valida a loja alvo.
- Endereços: criação, listagem, edição e padrão por conta do cliente; dados persistidos no banco MP_ENDERECO. Histórico dos pedidos não é alterado.
- Mudanças de endereço invalidam cotação e resumo antes de criar pedido; respostas antigas são descartadas.
- Consulta real ViaCEP com CEP público de exemplo 01001000: rua/bairro/cidade/UF retornaram corretamente.
- Migração local: tabela MP_ENDERECO criada. Nenhum endereço real de cliente criado durante QA.
- Backend: 496 testes executados; 452 passaram e 44 integrações opt-in ignoradas.
- Navegador com dados fictícios: consulta CEP, número/complemento preservados, edição manual durante consulta preservada, CEP inexistente com preenchimento manual, salvamento, edição, reabertura e descarte da cotação anterior verificados.

## Pix

Consulta somente leitura GET /api/v1/conta da Arkhé: HTTP 502, resposta text/html, com credenciais configuradas no banco da barbearia. Nenhuma cobrança criada nesse diagnóstico.

A criação de Pix segue o endpoint e corpo da documentação fornecida (POST /api/v1/cobrancas/pix, valor numérico). O sistema apresenta mensagem segura de indisponibilidade e orienta conferir cobranças antes de repetir; não repete automaticamente a criação. Testes simulam HTTP 500/502/503/504/429 e falhas de rede sem expor corpo do provedor nem inventar pagamento.

Pagamento real permanece dependente de recuperação da Arkhé. HTTP 502 não confirma que as credenciais foram validadas nem que uma cobrança anterior foi ou não criada.

Fonte ViaCEP: https://viacep.com.br/

## Verificação final

- Frontend: 124 testes passaram; lint e build de produção passaram.
- Navegador: múltiplos endereços Casa/Trabalho selecionáveis; remetente com CEP automático; mobile 375 px sem overflow horizontal.
- API local reiniciada: health e vitrine públicos HTTP 200; endereços/CEP e OpenAPI sem login HTTP 401.
- Help e contratos OpenAPI atualizados com as novas rotas.

## Checkout compacto e orientação de bloqueio — 18/10/2026

- No caso da captura, entrega em casa estava selecionada sem cotação escolhida. Sem frete não há resumo confirmado, portanto “Criar pedido” permanece desabilitado. O aceite dos termos já registrado não era a pendência mostrada.
- Endereço salvo aparece em cartão compacto; campos completos abrem ao editar ou adicionar. É possível usar alterações somente nesta compra ou restaurar o endereço salvo sem sobrescrever o cadastro.
- Entrega e resumo usam duas colunas no desktop e uma no celular. Cupom é opcional e recolhido; fretes aparecem em cartões com preço e prazo. Mensagem junto ao botão informa dados faltantes, frete, resumo ou termos pendentes.
- Preservados resumo assinado pelo servidor, taxa de 1,5%, aceite explícito e chave de idempotência. A criação do pedido continua separada do pagamento Pix.
- Navegador com fetch inteiramente simulado e dados fictícios: entrega econômica (produtos R$ 16,00 + frete R$ 10,00 + taxa R$ 0,24 = R$ 26,24), retirada (R$ 16,24), edição e restauração de endereço, invalidação de cotação e indisponibilidade de frete verificados. Criação fictícia concluída nos dois modos. Nenhum pedido, cobrança ou aceite real enviado.
- Tela de celular sem overflow horizontal. Evidências e fixture de QA arquivados fora do projeto em `C:\Users\mathe\Documents\Backups-Cortae\checkout-visual-20261018`.
- Frontend: 129 testes passaram; lint sem avisos e build de produção passaram. Arquivos temporários de demonstração removidos do frontend após a verificação.
