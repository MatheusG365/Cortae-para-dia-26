import test from 'node:test';
import assert from 'node:assert/strict';
import { anexarFuncionario, erroFuncionario, erroSenhaBarbeiro, podeEntrarNaEspera, podeFinalizarAtendimento } from '../src/services/agendaState.js';

test('equipe preserva ID persistido ao salvar dias e acesso', () => {
    const formulario = new FormData();
    anexarFuncionario(formulario, { id_funcionario: 72, nome: ' João ', descricao: '', email: 'joao@example.com', telefone: '11999999999', comissao_percentual: 0, dias: ['segunda'], servicos: [12, 14] }, 0);
    assert.equal(formulario.get('funcionarios[0][id_funcionario]'), '72');
    assert.equal(formulario.get('funcionarios[0][nome]'), 'João');
    assert.equal(formulario.get('funcionarios[0][servicos]'), '12,14');
    assert.equal(formulario.get('funcionarios[0][comissao_percentual]'), '0');
});

test('novo barbeiro exige contato e percentual válido; funcionário antigo sem acesso é preservado', () => {
    assert.match(erroFuncionario({ nome: 'João' }), /e-mail/);
    assert.match(erroFuncionario({ nome: 'João', email: 'joao@example.com', telefone: '123' }), /telefone/);
    assert.equal(erroFuncionario({ nome: 'João', email: 'joao@example.com', telefone: '(11) 99999-9999', comissao_percentual: 0 }), '');
    assert.equal(erroFuncionario({ id_funcionario: 72, nome: 'João', email: '', telefone: '', comissao_percentual: 15 }), '');
    assert.match(erroFuncionario({ id_funcionario: 72, nome: 'João', comissao_percentual: 101 }), /0% e 100%/);
    assert.match(erroFuncionario({ id_funcionario: 72, nome: 'João', comissao_percentual: -1 }), /0% e 100%/);
});

test('lista de espera só oferece horários ocupados autorizados pelo servidor', () => {
    assert.equal(podeEntrarNaEspera({ disponivel: false, lista_espera_disponivel: true }), true);
    assert.equal(podeEntrarNaEspera({ disponivel: true, lista_espera_disponivel: true }), false);
    assert.equal(podeEntrarNaEspera({ disponivel: false }), false);
    assert.equal(podeEntrarNaEspera(null), false);
});

test('barbeiro só finaliza atendimentos agendados após o término', () => {
    const agora = new Date('2026-10-10T15:00:00').getTime();
    assert.equal(podeFinalizarAtendimento({ status: 'agendado', fim_em: '2026-10-10T14:00:00' }, agora), true);
    assert.equal(podeFinalizarAtendimento({ status: 'agendado', fim_em: '2026-10-10T16:00:00' }, agora), false);
    assert.equal(podeFinalizarAtendimento({ status: 'cancelado', fim_em: '2026-10-10T14:00:00' }, agora), false);
    assert.equal(podeFinalizarAtendimento({ status: 'agendado', fim_em: 'inválido' }, agora), false);
});

test('ativação exige senha forte, confirmação e limite de bytes do backend', () => {
    assert.equal(erroSenhaBarbeiro('Acesso123!', 'Acesso123!'), '');
    assert.match(erroSenhaBarbeiro('Acesso123!', 'outra'), /coincidem/);
    for (const senha of ['abc123!!', 'ABC123!!', 'Abcdefgh!', 'Acesso123', 'Aa1!']) assert.notEqual(erroSenhaBarbeiro(senha, senha), '');
    const longa = 'Aa1!' + 'é'.repeat(36);
    assert.match(erroSenhaBarbeiro(longa, longa), /72 bytes/);
});
