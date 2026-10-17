import test from 'node:test';
import assert from 'node:assert/strict';
import { dinheiroZero, formatarMoeda, dataAgendamento, horaAgendamento, momentoCurto } from '../src/services/formatacao.js';
import { dinheiro } from '../src/services/gestaoState.js';
import { moeda } from '../src/pages/Marketplace/marketplaceState.js';
import { dataLocal, periodoDoMes, rotuloStatusAgendamento } from '../src/services/agendaState.js';
import { emailSemEspacos, somenteDigitos, barbeariasDaResposta, estadosBrasil } from '../src/services/cadastroState.js';
import { identidadeDoUsuario } from '../src/contexts/authStorage.js';
import { rotaPagamentoAgendamento } from '../src/services/pagamentoState.js';
import { queryDaApi } from '../src/services/api.js';

test('preços históricos ausentes permanecem diferentes de zero e normalização do marketplace preserva NaN', () => {
    assert.equal(dinheiro(null), 'Sem valor registrado');
    assert.equal(dinheiro(undefined), 'Sem valor registrado');
    assert.equal(dinheiro(0), 'R$\u00a00,00');
    assert.equal(dinheiroZero(null), 'R$\u00a00,00');
    assert.equal(dinheiroZero(''), 'R$\u00a00,00');
    assert.equal(dinheiroZero('1234.56'), 'R$\u00a01.234,56');
    assert.equal(formatarMoeda(-12.5), '-R$\u00a012,50');
    assert.equal(moeda('inválido'), 'R$\u00a00,00');
    assert.match(dinheiro('inválido'), /NaN/);
});

test('datas da agenda preservam o dia e a hora reservados sem conversão de fuso', () => {
    assert.equal(dataAgendamento('2026-10-12T00:30:00Z'), '12/10/2026');
    assert.equal(horaAgendamento('2026-10-12T00:30:00Z'), '00:30');
    assert.equal(dataAgendamento('2026-10-12'), '12/10/2026');
    assert.equal(horaAgendamento('2026-10-12'), '');
    assert.equal(dataAgendamento(null), '-');
    assert.equal(horaAgendamento(null), '');
    assert.equal(momentoCurto('não é data'), '-');
    assert.equal(momentoCurto(null), '-');
});

test('período do mês considera calendário local e preserva fevereiro bissexto', () => {
    const hoje = new Date(2024, 1, 29, 23, 59, 59);
    assert.equal(dataLocal(hoje), '2024-02-29');
    assert.deepEqual(periodoDoMes(hoje), { inicio: '2024-02-01', fim: '2024-02-29' });
    assert.deepEqual(periodoDoMes(new Date(2026, 0, 1, 0, 1)), { inicio: '2026-01-01', fim: '2026-01-01' });
});

test('rótulos históricos mantêm fallback para estados desconhecidos e propriedades de objetos', () => {
    assert.equal(rotuloStatusAgendamento('cancelado'), 'Cancelado');
    assert.equal(rotuloStatusAgendamento('concluido'), 'Concluído');
    assert.equal(rotuloStatusAgendamento('faltou'), 'Cliente faltou');
    for (const estado of [null, undefined, 'confirmado', 'novo', 'toString', '__proto__']) assert.equal(rotuloStatusAgendamento(estado), 'Agendado');
});

test('contatos removem apenas espaços ou máscaras, preservando maiúsculas do email', () => {
    assert.equal(emailSemEspacos('  Ana\t.Silva @Example.com\n'), 'Ana.Silva@Example.com');
    assert.equal(somenteDigitos('(11) 99999-0000'), '11999990000');
    assert.equal(somenteDigitos('12345-678'), '12345678');
    assert.equal(somenteDigitos(null), '');
    assert.equal(somenteDigitos(123456), '123456');
});

test('catálogo aceita envelope e resposta histórica sem inventar lojas; UFs são imutáveis', () => {
    const lojas = [{ id: 11, nome: 'Salão A' }];
    assert.equal(barbeariasDaResposta(lojas), lojas);
    assert.equal(barbeariasDaResposta({ barbearias: lojas }), lojas);
    assert.deepEqual(barbeariasDaResposta({}), []);
    assert.equal(estadosBrasil.length, 27);
    assert.equal(new Set(estadosBrasil).size, 27);
    assert.ok(Object.isFrozen(estadosBrasil));
});

test('identidade distingue conta, papel e visitante, mantendo compatibilidade dos IDs', () => {
    assert.equal(identidadeDoUsuario({ id_usuario: 7, tipo: 0 }), '7:0');
    assert.equal(identidadeDoUsuario({ id: 7, tipo: 0 }), '7:0');
    assert.notEqual(identidadeDoUsuario({ id: 7, tipo: 0 }), identidadeDoUsuario({ id: 7, tipo: 2 }));
    assert.notEqual(identidadeDoUsuario({ id: 7, tipo: 2 }), identidadeDoUsuario({ id: 8, tipo: 2 }));
    assert.equal(identidadeDoUsuario(null), 'anonimo:');
});

test('pagamentos roteiam só os quatro métodos anteriores, sem transformar intenção em confirmação', () => {
    assert.equal(rotaPagamentoAgendamento('pix'), '/pagamentos/pix');
    assert.equal(rotaPagamentoAgendamento('boleto'), '/pagamentos/boleto');
    assert.equal(rotaPagamentoAgendamento('cartao'), '/pagamentos/cartao');
    assert.equal(rotaPagamentoAgendamento('na_hora'), '/pagamentos/na-hora');
    for (const metodo of ['__proto__', 'toString', 'pix_pago', null, undefined]) assert.equal(rotaPagamentoAgendamento(metodo), null);
});

test('query preserva codificação, chaves repetidas e zero sem acrescentar interrogação vazia', () => {
    assert.equal(queryDaApi({}), '');
    assert.equal(queryDaApi({ busca: 'óleo & shampoo', pagina: 0 }), '?busca=%C3%B3leo+%26+shampoo&pagina=0');
    const query = new URLSearchParams([['categoria', 'cabelo'], ['categoria', 'barba']]);
    assert.equal(queryDaApi(query), '?categoria=cabelo&categoria=barba');
});
