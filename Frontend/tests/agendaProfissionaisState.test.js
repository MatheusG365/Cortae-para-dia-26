import test from 'node:test';
import assert from 'node:assert/strict';
import { idsServicosAgendamento, contextoProfissionais, profissionaisDaResposta, funcionarioValido, corpoAgendamento, rotaAgendaGestao } from '../src/services/agendaProfissionaisState.js';

const equipe = [
    { id_funcionario: 9, nome: 'Ana', servicos: [1, 2] },
    { id_funcionario: 10, nome: 'Bruno', servicos: [1] },
    { id_funcionario: 11, nome: 'Caio', servicos: [1, 2], ativo: false },
    { id_funcionario: 12, nome: 'Davi', servicos: ['1', '2'] }
];

test('profissionais precisam atender todos os serviços e estar ativos', () => {
    assert.deepEqual(profissionaisDaResposta({ funcionarios: equipe }, '1,2').map(p => p.id_funcionario), [9, 12]);
    assert.deepEqual(profissionaisDaResposta({ funcionarios: equipe }, '1,3'), []);
    assert.deepEqual(profissionaisDaResposta({ funcionarios: [equipe[0]] }, '1'), [equipe[0]]);
    assert.deepEqual(profissionaisDaResposta({ funcionarios: [] }, '1'), []);
});

test('falha de contrato não é interpretada como ausência de profissionais', () => {
    for (const resposta of [null, {}, { funcionarios: null }, { funcionarios: 'indisponível' }]) {
        assert.throws(() => profissionaisDaResposta(resposta, '1'), /lista de profissionais/);
    }
});

test('profissional recebido na URL só é mantido se elegível para a combinação atual', () => {
    const corte = profissionaisDaResposta({ funcionarios: equipe }, '1');
    const corteBarba = profissionaisDaResposta({ funcionarios: equipe }, '1,2');
    assert.equal(funcionarioValido('10', corte), '10');
    assert.equal(funcionarioValido('10', corteBarba), '');
    assert.equal(funcionarioValido('9', corteBarba), '9');
    assert.equal(funcionarioValido('', corteBarba), '');
    assert.notEqual(contextoProfissionais('11', '1'), contextoProfissionais('11', '1,2'));
    assert.notEqual(contextoProfissionais('11', '1'), contextoProfissionais('12', '1'));
    assert.equal(contextoProfissionais('11', '2,1,1'), contextoProfissionais(11, '1,2'));
});

test('resumo e reserva compartilham os serviços e null explícito para agenda livre', () => {
    const semProfissional = corpoAgendamento('11', '1,2,1', '');
    assert.deepEqual(JSON.parse(JSON.stringify(semProfissional)), { id_barbearia: 11, ids_servicos: ['1', '2'], id_funcionario: null });
    assert.deepEqual(corpoAgendamento('11', '1,2', '9'), { id_barbearia: 11, ids_servicos: ['1', '2'], id_funcionario: 9 });
    assert.deepEqual(idsServicosAgendamento(' 1,2,,1,erro,-4,0 '), ['1', '2']);
});

test('perfis de gestão usam a agenda com seleção de cliente e escopo próprio', () => {
    assert.equal(rotaAgendaGestao(0, '11'), '/gestao?aba=agenda&id_barbearia=11');
    assert.equal(rotaAgendaGestao(2, '11'), '/gestao?aba=agenda');
    assert.equal(rotaAgendaGestao(3, '11'), '/gestao?aba=agenda');
});
