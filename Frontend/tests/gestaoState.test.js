import assert from 'node:assert/strict';
import test from 'node:test';
import { estadoFinanceiroHistorico, intervaloAgenda, linkAgendamento, momento, servicosDoAtendimento, totalRecebimentos } from '../src/services/gestaoState.js';

test('semana inicia segunda e preserva virada do ano', () => {
    const periodo = intervaloAgenda('2027-01-03', 'semana');
    assert.equal(periodo.inicio, '2026-12-28'); assert.equal(periodo.fim, '2027-01-03'); assert.equal(periodo.dias.length, 7);
});
test('calendário mensal inclui dia extra em fevereiro bissexto', () => {
    const periodo = intervaloAgenda('2028-02-14', 'mes');
    assert.equal(periodo.inicio, '2028-02-01'); assert.equal(periodo.fim, '2028-02-29'); assert.equal(periodo.dias.length, 29);
});
test('calendário mensal não avança mês ao navegar desde dia 31', () => {
    const periodo = intervaloAgenda('2026-01-31', 'mes');
    assert.equal(periodo.fim, '2026-01-31'); assert.equal(periodo.dias.length, 31);
});
test('visão diária contém somente a data solicitada', () => {
    assert.deepEqual(intervaloAgenda('2026-10-11', 'dia').dias, ['2026-10-11']);
});
test('total dividido soma centavos sem resíduo de ponto flutuante', () => {
    assert.equal(totalRecebimentos([{ valor: '0.10' }, { valor: '0.20' }, { valor: '10.15' }]), 10.45);
});
test('link público preserva salão e profissional sem depender de sessão', () => {
    const url = new URL(linkAgendamento('http://localhost:5173', 14, 22));
    assert.equal(url.pathname, '/selecionar-servicos'); assert.equal(url.searchParams.get('barbearia'), '14'); assert.equal(url.searchParams.get('funcionario'), '22');
    assert.equal(new URL(linkAgendamento('http://localhost:5173', 14)).searchParams.has('funcionario'), false);
});
test('data de pagamento sem horário mantém dia local, sem recuo por UTC', () => {
    assert.equal(momento('2026-10-11'), '11/10/2026'); assert.equal(momento('invalida'), '—');
});
test('histórico conserva nomes dos serviços registrados quando o catálogo muda', () => {
    assert.equal(servicosDoAtendimento({ servicos: [{ nome: 'Corte antigo' }, { nome: 'Barba' }] }), 'Corte antigo, Barba');
});
test('ficha do cliente não confunde intenção de pagamento com recebimento', () => {
    assert.equal(estadoFinanceiroHistorico({ tipo: 'na_hora_pendente' }), 'Pendente');
    assert.equal(estadoFinanceiroHistorico({ tipo: 'na_hora' }), 'Recebido');
    assert.equal(estadoFinanceiroHistorico({ tipo: 'pix' }), 'Confirmação não informada');
});
