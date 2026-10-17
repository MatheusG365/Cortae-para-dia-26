import test from 'node:test';
import assert from 'node:assert/strict';
import { estadoPagamento, podeConfirmarRecebimento } from '../src/services/pagamentoState.js';

test('pagamento dividido mantém saldo pendente e permite somente a confirmação do restante', () => {
    const agendamento = { status: 'agendado', valor_total: 100 };
    const resposta = { quitado: false, parcial: true, saldo: 60, na_hora_pendente: true, na_hora_confirmado: true, cobrancas: [{ confirmado: true, status: 1, valor: 40 }] };
    assert.equal(podeConfirmarRecebimento(resposta, agendamento), true);
    assert.equal(podeConfirmarRecebimento({ ...resposta, quitado: true, saldo: 0 }, agendamento), false);
});

test('intenção de pagar no local nunca é apresentada como dinheiro recebido', () => {
    assert.match(estadoPagamento({ tipo: 'na_hora_pendente', status: 0, pendente: true }), /pendente de confirmação/);
    assert.match(estadoPagamento({ tipo: 'na_hora_pendente', status: 1, confirmado: true }), /pendente de confirmação/);
    assert.equal(estadoPagamento({ tipo: 'na_hora', status: 1, confirmado: true }), 'Recebido');
    assert.notEqual(estadoPagamento({ tipo: 'na_hora', status: 1 }), 'Recebido');
    assert.equal(estadoPagamento({ tipo: 'pix', status: 0 }), 'Pendente');
});

test('confirmação presencial exige intenção pendente, preço conhecido e atendimento válido', () => {
    const pendente = { na_hora_pendente: true, na_hora_confirmado: false };
    const agendamento = { status: 'concluido', valor_total: 40 };
    assert.equal(podeConfirmarRecebimento(pendente, agendamento), true);
    assert.equal(podeConfirmarRecebimento({ ...pendente, na_hora_confirmado: true }, agendamento), false);
    assert.equal(podeConfirmarRecebimento({}, agendamento), false);
    assert.equal(podeConfirmarRecebimento(pendente, { ...agendamento, status: 'cancelado' }), false);
    assert.equal(podeConfirmarRecebimento(pendente, { ...agendamento, status: 'faltou' }), false);
    assert.equal(podeConfirmarRecebimento(pendente, { ...agendamento, valor_total: null }), false);
    assert.equal(podeConfirmarRecebimento(pendente, { ...agendamento, valor_total: 0 }), true);
});

test('pagamento confirmado em outro método bloqueia nova confirmação presencial', () => {
    const agendamento = { status: 'concluido', valor_total: 40 };
    const pendente = { na_hora_pendente: true, na_hora_confirmado: false };
    assert.equal(podeConfirmarRecebimento({ ...pendente, cobrancas: [{ tipo: 'pix', status: 1, confirmado: true }] }, agendamento), false);
    assert.equal(podeConfirmarRecebimento({ ...pendente, cobrancas: [{ tipo: 'cartao', status: 1 }] }, agendamento), false);
    assert.equal(podeConfirmarRecebimento({ ...pendente, cobrancas: [{ tipo: 'boleto', confirmado: true }] }, agendamento), false);
    assert.equal(podeConfirmarRecebimento({ ...pendente, cobrancas: [{ tipo: 'pix', status: 0, confirmado: false }, { tipo: 'na_hora_pendente', status: 0 }] }, agendamento), true);
});
