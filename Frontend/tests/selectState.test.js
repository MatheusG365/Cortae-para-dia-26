import test from 'node:test';
import assert from 'node:assert/strict';
import { buscarOpcao, indiceSelecionado, moverOpcao, posicionarLista } from '../src/components/Select/selectState.js';

const opcoes = [{ value: '', label: 'Selecione', disabled: true }, { value: '0', label: 'Álvaro' }, { value: 'b', label: 'Bruna', disabled: true }, { value: 'c', label: 'Carla' }];

test('seleção mantém zero e placeholder vazio, e usa primeiro habilitado para valor removido', () => {
    assert.equal(indiceSelecionado(opcoes, 0), 1);
    assert.equal(indiceSelecionado(opcoes, ''), 0);
    assert.equal(indiceSelecionado(opcoes, 'valor removido'), 1);
    assert.equal(indiceSelecionado([], ''), -1);
});
test('teclado pula desabilitados, percorre extremos e volta ao início', () => {
    assert.equal(moverOpcao(opcoes, 1, 'proximo'), 3);
    assert.equal(moverOpcao(opcoes, 3, 'proximo'), 1);
    assert.equal(moverOpcao(opcoes, 1, 'anterior'), 3);
    assert.equal(moverOpcao(opcoes, 3, 'inicio'), 1);
    assert.equal(moverOpcao(opcoes, 1, 'fim'), 3);
    assert.equal(moverOpcao(opcoes.map(opcao => ({ ...opcao, disabled: true })), 1, 'proximo'), -1);
});
test('busca por digitação ignora acentos e opções desabilitadas', () => {
    assert.equal(buscarOpcao(opcoes, 'alv'), 1);
    assert.equal(buscarOpcao(opcoes, 'bru'), -1);
    assert.equal(buscarOpcao(opcoes, 'car', 1), 3);
    assert.equal(buscarOpcao(opcoes, 'inexistente'), -1);
});
test('popup cabe em viewport móvel e abre acima quando falta espaço abaixo', () => {
    const posicao = posicionarLista({ left: 250, top: 680, bottom: 724, width: 200 }, { width: 375, height: 820 });
    assert.ok(posicao.left >= 8);
    assert.ok(posicao.left + posicao.width <= 367);
    assert.ok(posicao.top + posicao.maxHeight < 680);
    assert.ok(posicao.top >= 8);
});
test('popup considera viewport visual deslocado e limita a altura', () => {
    const posicao = posicionarLista({ left: 30, top: 160, bottom: 204, width: 100 }, { left: 20, top: 120, width: 320, height: 250 }, 300);
    assert.ok(posicao.left >= 28);
    assert.ok(posicao.top >= 128);
    assert.ok(posicao.top + posicao.maxHeight <= 362);
});
test('clamp vertical não deixa o popup fora da tela mesmo com âncora fora do viewport', () => {
    const posicao = posicionarLista({ left: 10, top: 1000, bottom: 1044, width: 250 }, { width: 375, height: 820 });
    assert.ok(posicao.top >= 8);
    assert.ok(posicao.top + posicao.maxHeight <= 812);
});
