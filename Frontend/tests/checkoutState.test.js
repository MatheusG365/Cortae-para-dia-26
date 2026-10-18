import test from 'node:test';
import assert from 'node:assert/strict';
import { orientacaoCheckout, pendenciasEndereco } from '../src/pages/Marketplace/checkoutState.js';

const endereco = { nome: 'Cliente QA', email: 'qa@example.invalid', telefone: '(11) 91234-5678', documento: '12345678901', cep: '01001-000', logradouro: 'Praça da Sé', numero: '10', bairro: 'Sé', cidade: 'São Paulo', uf: 'SP', complemento: '' };
const pronto = { endereco, retirada: false, selecionada: { id_cotacao: 'qa' }, previa: { resumo: {} }, termos: { permitido: true } };

test('endereço completo aceita formatação e complemento opcional, sem exigir salvamento', () => {
    assert.deepEqual(pendenciasEndereco(endereco), []);
    assert.deepEqual(pendenciasEndereco({ ...endereco, documento: '12345678000199', telefone: '1133334444' }), []);
});
test('identifica dados incompletos ou formatos inválidos antes do pedido', () => {
    assert.deepEqual(pendenciasEndereco({ ...endereco, numero: ' ', documento: '123', email: 'inválido', telefone: '123', uf: 'ZZ', cep: '123' }), ['e-mail', 'telefone', 'CPF ou CNPJ', 'CEP', 'número', 'UF']);
});
test('entrega sem cotação explica o motivo que impede criar pedido', () => {
    assert.match(orientacaoCheckout({ ...pronto, selecionada: null }), /Calcule o frete/);
    assert.match(orientacaoCheckout({ ...pronto, selecionada: null, temCotacoes: true }), /Escolha uma opção/);
    assert.match(orientacaoCheckout({ ...pronto, selecionada: null, calculando: true }), /Buscando opções/);
});
test('retirada dispensa frete mas exige dados, total conferido e termos', () => {
    assert.equal(orientacaoCheckout({ ...pronto, selecionada: null, retirada: true }), '');
    assert.match(orientacaoCheckout({ ...pronto, retirada: true, endereco: { ...endereco, numero: '' } }), /número/);
});
test('bloqueia falha de resumo e de termos sem ocultar a orientação', () => {
    assert.match(orientacaoCheckout({ ...pronto, previa: { erro: 'erro' } }), /conferir o total/);
    assert.match(orientacaoCheckout({ ...pronto, previa: { carregando: true } }), /Conferindo/);
    assert.match(orientacaoCheckout({ ...pronto, termos: { erro: 'erro' } }), /Termos de Uso novamente/);
    assert.match(orientacaoCheckout({ ...pronto, termos: { carregando: true } }), /Consultando/);
    assert.match(orientacaoCheckout({ ...pronto, termos: { permitido: false } }), /Leia e aceite/);
    assert.equal(orientacaoCheckout(pronto), '');
});
