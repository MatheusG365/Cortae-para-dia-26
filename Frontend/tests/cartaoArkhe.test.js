import test from 'node:test';
import assert from 'node:assert/strict';
import { dadosCartao, limiteParcelas, cartaoEmConferencia, erroCartaoIncerto, podePagarAgendamento, podePagarPedido, reciboCartao } from '../src/services/cartaoArkhe.js';
const card = { numero_cartao: '2481000000000001', validade: '09/2031', cvv: '082', tipo: 'CREDITO', parcelas: 3 };
const today = new Date(2026, 9, 19);
const booking = { quitado: false, parcial: false, saldo: 100, valor_total: 100, valor_recebido: 0, cobrancas: [] };

test('Arkhé payload preserves leading zeros and excludes client amount or arbitrary fields', () => {
    assert.deepEqual(dadosCartao({ ...card, valor: .01, pin: '0000' }, 100, today), card);
    assert.equal(dadosCartao({ ...card, cvv: '007' }, 100, today).cvv, '007');
});
test('card validation rejects incomplete numbers, invalid expiry, expired cards and numeric CVV losing zero', () => {
    for (const change of [{ numero_cartao: '123' }, { validade: '13/2031' }, { validade: '09/2026' }, { cvv: 82 }, { tipo: 'VISA' }]) assert.throws(() => dadosCartao({ ...card, ...change }, 100, today));
});
test('installments require at least one cent, at most15, and exactly1 on debit', () => {
    assert.equal(limiteParcelas(.02), 2); assert.equal(limiteParcelas(0), 0); assert.equal(limiteParcelas(100), 15);
    for (const parcelas of [0, 16, 1.5]) assert.throws(() => dadosCartao({ ...card, parcelas }, 100, today));
    assert.throws(() => dadosCartao(card, .02, today));
    assert.throws(() => dadosCartao({ ...card, tipo: 'DEBITO' }, 100, today));
    assert.equal(dadosCartao({ ...card, tipo: 'DEBITO', parcelas: 1 }, 100, today).parcelas, 1);
});
test('existing receipt, charge or uncertain state blocks another booking payment', () => {
    assert.equal(podePagarAgendamento(booking, 'agendado'), true);
    for (const extra of [{ cartao_estado: 'processando' }, { cartao_estado: 'incerto' }, { cartao_estado: 'aprovado' }, { cobrancas: [{ status: 0 }] }, { parcial: true }, { quitado: true }, { valor_recebido: 1 }]) assert.equal(podePagarAgendamento({ ...booking, ...extra }, 'agendado'), false);
    assert.equal(podePagarAgendamento({ ...booking, cartao_estado: 'recusado' }, 'agendado'), true);
});
test('order retries require deterministic refusal or no payment, never pending/uncertain/paid', () => {
    for (const pagamento_status of ['nao_criado', 'recusado']) assert.equal(podePagarPedido({ status: 'aguardando_pagamento', pagamento_status }), true);
    for (const pagamento_status of ['incerto', 'processando', 'pendente', 'pago']) assert.equal(podePagarPedido({ status: 'aguardando_pagamento', pagamento_status }), false);
    assert.equal(podePagarPedido({ status: 'aguardando_pagamento', pagamento_status: 'nao_criado', pagamento: { id_cobranca: 2 } }), false);
});
test('transport, parse,5xx and ambiguous409 require conference; definite refusal does not', () => {
    for (const error of [{}, { status: 200 }, { status: 502 }, { status: 409 }, { status: 400, dados: { cartao_estado: 'incerto' } }]) assert.equal(erroCartaoIncerto(error), true);
    assert.equal(erroCartaoIncerto({ status: 400, dados: { cartao_estado: 'recusado' } }), false);
    assert.equal(erroCartaoIncerto({ status: 422 }), false);
    assert.equal(cartaoEmConferencia({ cartao_estado: 'recusado', pagamento_status: 'processando' }), true);
});
test('receipt requires approved provider result and retains no PAN/CVV/PIN', () => {
    assert.equal(reciboCartao({ metodo: 'cartao', status: 0 }), null);
    const receipt = reciboCartao({ pagamento: { metodo: 'cartao', aprovado: true, status: 1, valor: 100, valor_recebido: 95, taxa: 5, tipo: 'CREDITO', parcelas: 3, final_cartao: '0001', numero_cartao: card.numero_cartao, cvv: '082', pin: '1234' } });
    assert.equal(receipt.valor, 100); assert.equal(receipt.valor_recebido, 95); assert.equal(receipt.final_cartao, '0001');
    for (const key of ['numero_cartao', 'cvv', 'pin']) assert.equal(Object.hasOwn(receipt, key), false);
});

test('booking GET restores only approved local receipts, never uncertain IDs or raw provider fields', () => {
    const safe = { aprovado: true, valor: 100, id_compra: 456, final_cartao: '0001', tipo: 'CREDITO', parcelas: 3 };
    assert.equal(reciboCartao({ cartao_estado: 'aprovado', cartao_resultado: safe }), null);
    const wrapped = { ...safe, metodo: 'cartao', status: 1, cartao_estado: 'aprovado' };
    assert.equal(reciboCartao({ cartao_estado: 'aprovado', cartao_resultado: wrapped }).id_compra, 456);
    for (const cartao_estado of ['incerto', 'processando', 'recusado']) assert.equal(reciboCartao({ cartao_estado, cartao_resultado: wrapped }), null);
});
