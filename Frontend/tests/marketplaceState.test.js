import test from 'node:test';
import assert from 'node:assert/strict';
import { acoesEntrega, agruparCarrinho, fotosValidas, pagamentoDoPedido, podeCriarPix, quantidadeValida, urlFoto } from '../src/pages/Marketplace/marketplaceState.js';

test('Carrinho mantém pedidos separados por barbearia mesmo com entradas intercaladas', () => {
    const itens = [{ id_produto: 1, id_barbearia: 7 }, { id_produto: 2, id_barbearia: 9 }, { id_produto: 3, id_barbearia: 7 }];
    const grupos = agruparCarrinho(itens);
    assert.equal(grupos.length, 2);
    assert.deepEqual(grupos[0].itens.map(i => i.id_produto), [1, 3]);
    assert.deepEqual(grupos[1].itens.map(i => i.id_produto), [2]);
});
test('Imagem aceita somente HTTPS e rejeita URL com credenciais ou protocolos executáveis', () => {
    for (const v of ['javascript:alert(1)', 'data:image/svg+xml,abc', 'http://a.com/a.png', 'https://user:secret@a.com/a.jpg', '/foto.png']) assert.equal(urlFoto(v), '');
    assert.deepEqual(fotosValidas('https://a.com/a.png\n \nhttps://b.com/b.jpg'), ['https://a.com/a.png', 'https://b.com/b.jpg']);
});
test('Quantidade precisa ser inteira, positiva e dentro do estoque', () => {
    assert.equal(quantidadeValida('2', 3), true);
    for (const q of ['0', '-1', '1.2', '4', 'abc']) assert.equal(quantidadeValida(q, 3), false);
});
test('Estados incertos e operações pagas não permitem repetir criação Pix', () => {
    assert.equal(podeCriarPix({ status: 'aguardando_pagamento', pagamento_status: 'nao_criado' }), true);
    for (const status of ['pendente', 'processando', 'incerto', 'pago']) assert.equal(podeCriarPix({ status: 'aguardando_pagamento', pagamento_status: status }), false);
    assert.equal(podeCriarPix({ status: 'cancelado', pagamento_status: 'nao_criado' }), false);
});
test('Etiqueta avança uma etapa por vez e estados incertos não mostram ações financeiras', () => {
    const base = { status: 'pago', pagamento_status: 'pago', retirada: false };
    assert.deepEqual(acoesEntrega({ ...base, entrega: { status: 'nao_criada' } }, true), ['preparar']);
    assert.deepEqual(acoesEntrega({ ...base, entrega: { status: 'preparada' } }, true), ['comprar']);
    assert.deepEqual(acoesEntrega({ ...base, entrega: { status: 'comprada' } }, true), ['gerar']);
    for (const status of ['preparo_incerto', 'compra_incerta', 'geracao_incerta', 'comprando', 'gerando']) assert.deepEqual(acoesEntrega({ ...base, entrega: { status } }), []);
    assert.deepEqual(acoesEntrega({ ...base, retirada: true, entrega: { status: 'preparada' } }), []);
    assert.deepEqual(acoesEntrega({ ...base, pagamento_status: 'pendente', entrega: { status: 'preparada' } }), []);
});
test('Integração com permissão apenas de cotação e rastreio não oferece emissão paga', () => {
    const pedido = { status: 'pago', pagamento_status: 'pago', retirada: false };
    for (const status of ['nao_criada', 'preparada', 'comprada']) assert.deepEqual(acoesEntrega({ ...pedido, entrega: { status } }), []);
    assert.deepEqual(acoesEntrega({ ...pedido, entrega: { status: 'enviado' } }), ['rastreio']);
    assert.deepEqual(acoesEntrega({ ...pedido, entrega: { status: 'vinculada' } }), ['rastreio']);
    assert.deepEqual(acoesEntrega({ ...pedido, entrega: { status: 'gerada', url_etiqueta: 'https://melhorenvio.com.br/etiqueta' } }), ['ver', 'rastreio']);
});
test('Navegação detalhe/lista/detalhe não acessa cache nulo nem mostra Pix de outro pedido', () => {
    const pedido = { id_pedido: 1, pagamento: { codigo_pix: 'Pix do pedido 1' } };
    assert.deepEqual(pagamentoDoPedido('1', pedido, null), pedido.pagamento);
    assert.equal(pagamentoDoPedido(undefined, pedido, null), null);
    assert.equal(pagamentoDoPedido(undefined, undefined, null), null);
    assert.equal(pagamentoDoPedido('2', pedido, { id: '1', dados: pedido.pagamento }), null);
    const segundo = { id_pedido: 2, pagamento: { codigo_pix: 'Pix do pedido 2' } };
    assert.deepEqual(pagamentoDoPedido('2', segundo, { id: '1', dados: pedido.pagamento }), segundo.pagamento);
    assert.deepEqual(pagamentoDoPedido('2', segundo, { id: '2', dados: { codigo_pix: 'Consulta atualizada' } }), { codigo_pix: 'Consulta atualizada' });
});

