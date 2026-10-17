import test from 'node:test';
import assert from 'node:assert/strict';
import { atualizarAvaliacao, erroAvaliacao, rotuloMedia } from '../src/services/avaliacaoState.js';

test('avaliação exige nota inteira de 1 a 5 e comentário dentro do limite', () => {
    for (const nota of [1, 2, 3, 4, 5]) assert.equal(erroAvaliacao(nota, ''), '');
    for (const nota of [null, '5', 0, 6, 2.5, NaN]) assert.ok(erroAvaliacao(nota, ''));
    assert.equal(erroAvaliacao(5, 'a'.repeat(1000)), '');
    assert.ok(erroAvaliacao(5, 'a'.repeat(1001)));
    assert.ok(erroAvaliacao(5, {}));
});

test('ausência de avaliação permanece distinta de média zero', () => {
    assert.equal(rotuloMedia(null), 'Sem avaliações');
    assert.equal(rotuloMedia(undefined), 'Sem avaliações');
    assert.equal(rotuloMedia(4.25), '4,25 / 5');
});

test('salvar ou editar avaliação atualiza o atendimento sem duplicar nem alterar outros', () => {
    const outros = { id_agendamento: 11, status: 'concluido', avaliacao: null };
    const itens = [{ id: 10, corte_nome: 'Escolho na hora', avaliacao: null }, outros];
    const primeira = atualizarAvaliacao(itens, '10', { avaliacao: { nota: 5, comentario: '<script>texto</script>' }, pode_avaliar: true });
    assert.equal(primeira.length, 2);
    assert.equal(primeira[0].corte_nome, 'Escolho na hora');
    assert.equal(primeira[0].avaliacao.comentario, '<script>texto</script>');
    assert.equal(primeira[1], outros);
    assert.equal(itens[0].avaliacao, null);
    const edicao = atualizarAvaliacao(primeira, 10, { avaliacao: { nota: 4, comentario: 'Editado' }, pode_avaliar: true });
    assert.equal(edicao.length, 2);
    assert.equal(edicao[0].avaliacao.nota, 4);
    assert.equal(edicao[0].pode_avaliar, true);
});
