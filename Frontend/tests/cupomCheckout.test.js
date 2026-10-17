import test from 'node:test';
import assert from 'node:assert/strict';
import { estadoCupomCheckout } from '../src/pages/Marketplace/cupomCheckoutState.js';

const confirmado = { cupom: 'BEMVINDO10', resumo: { cupom: 'BEMVINDO10', desconto: 6.38 }, podeConferir: true };
test('cupom mostra apenas economia positiva confirmada pelo servidor para o código aplicado', () => {
    assert.deepEqual(estadoCupomCheckout(confirmado), { tipo: 'aplicado', codigo: 'BEMVINDO10', desconto: 6.38 });
    assert.equal(estadoCupomCheckout({ ...confirmado, cupom: '  bemvindo10 ', resumo: { cupom: { codigo: 'BEMVINDO10' }, desconto: 6.38 } }).tipo, 'aplicado');
});
test('resumo anterior não confirma novo cupom nem um cupom removido', () => {
    assert.equal(estadoCupomCheckout({ ...confirmado, cupom: 'NOVO10' }).tipo, 'conferindo');
    assert.equal(estadoCupomCheckout({ ...confirmado, cupom: '' }).tipo, 'vazio');
    assert.equal(estadoCupomCheckout({ ...confirmado, resumo: undefined }).tipo, 'conferindo');
});
test('endereço incompleto, requisição pendente e falha nunca anunciam economia antiga', () => {
    assert.equal(estadoCupomCheckout({ ...confirmado, podeConferir: false }).tipo, 'dados');
    assert.equal(estadoCupomCheckout({ ...confirmado, carregando: true }).tipo, 'conferindo');
    assert.equal(estadoCupomCheckout({ ...confirmado, erro: 'Cupom expirado.' }).tipo, 'erro');
});
test('descontos inválidos, inexistentes ou sem valor positivo nunca mostram sucesso', () => {
    for (const desconto of [0, -1, NaN, Infinity, undefined, null, '6.38']) {
        assert.equal(estadoCupomCheckout({ ...confirmado, resumo: { cupom: 'BEMVINDO10', desconto } }).tipo, 'semDesconto');
    }
});
