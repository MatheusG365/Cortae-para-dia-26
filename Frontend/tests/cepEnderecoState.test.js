import test from 'node:test';
import assert from 'node:assert/strict';
import { aplicarResultadoCep, enderecoSalvo, formatarCep, mudarCep, normalizarCep, novoEndereco } from '../src/services/cepEnderecoState.js';

test('CEP é normalizado e formatado sem aceitar mais de oito dígitos', () => {
    assert.equal(normalizarCep('01310-100'), '01310100');
    assert.equal(formatarCep('01310100extra9'), '01310-100');
    assert.equal(formatarCep('013'), '013');
});
test('outro CEP remove endereço anterior, preservando apenas contato e documento', () => {
    const anterior = { ...novoEndereco({ nome: 'Ana' }), documento: '123', cep: '01310-100', logradouro: 'Antiga', bairro: 'Centro', cidade: 'São Paulo', uf: 'SP', numero: '42', complemento: 'Apto 8' };
    const atual = mudarCep(anterior, '20040002');
    for (const campo of ['logradouro', 'bairro', 'cidade', 'uf', 'numero', 'complemento']) assert.equal(atual[campo], '');
    assert.equal(atual.nome, 'Ana');
    assert.equal(atual.documento, '123');
    assert.equal(mudarCep(anterior, '01310100').numero, '42');
});
test('resposta atrasada não troca CEP nem campos editados durante a consulta', () => {
    const atual = { ...novoEndereco(), cep: '01310-100', logradouro: 'Rua escolhida', numero: '42', complemento: 'Apto 8' };
    const dados = { logradouro: 'Avenida postal', bairro: 'Bela Vista', cidade: 'São Paulo', uf: 'SP', numero: '999', complemento: 'lado ímpar' };
    assert.equal(aplicarResultadoCep(atual, dados, '20040002'), atual);
    const resultado = aplicarResultadoCep(atual, dados, '01310100', ['logradouro']);
    assert.equal(resultado.logradouro, 'Rua escolhida');
    assert.equal(resultado.bairro, 'Bela Vista');
    assert.equal(resultado.numero, '42');
    assert.equal(resultado.complemento, 'Apto 8');
});
test('CEP genérico permite campos manuais e seleção de endereço nunca carrega resíduos', () => {
    const resultado = aplicarResultadoCep({ ...novoEndereco(), cep: '12345-000', bairro: 'Rural' }, { logradouro: '', bairro: '', cidade: 'Cidade', uf: 'MG' }, '12345000', ['bairro']);
    assert.equal(resultado.bairro, 'Rural');
    assert.equal(resultado.logradouro, '');
    assert.equal(enderecoSalvo({ cep: '12345000', cidade: 'Outra' }).complemento, '');
    const novo = novoEndereco({ nome: 'Ana', email: 'a@example.com', telefone: '11999999999', documento: 'não copiar' });
    assert.equal(novo.documento, '');
    assert.equal(novo.nome, 'Ana');
});
