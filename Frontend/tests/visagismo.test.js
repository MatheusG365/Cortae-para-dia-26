import test from 'node:test';
import assert from 'node:assert/strict';
import { assinaturaSimulacao, CAMPOS_CARACTERISTICAS, erroDaSelecao, normalizarAnalise, normalizarCatalogo, textoCaracteristica, validarFotoSalva } from '../src/pages/Visagismo/visagismoState.js';
import { dadosEscolhaCorte, permiteEscolhaNoAtendimento, rotuloEscolhaCorte } from '../src/services/escolhaCorte.js';

const corte = { id_corte: 12, nome: 'Degradê baixo', motivo: 'Mantém o topo ondulado e o comprimento observado.', compativel_com_cabelo_existente: true };
const resposta = { id_visagismo: 91, foto_url: '/uploads/foto.png', recomendacoes: [corte], caracteristicas: { textura_cabelo: 'Ondulado' }, cabelo_atual: 'Curto no topo', observacoes: 'Linha frontal encoberta' };

test('análise aceita apenas um corte cadastrado com motivo específico e foto salva', () => {
    const resultado = normalizarAnalise(resposta);
    assert.equal(resultado.corte, corte);
    assert.deepEqual(resultado.caracteristicas, { textura_cabelo: 'Ondulado' });
    assert.equal(resultado.cabeloAtual, 'Curto no topo');
    assert.equal(resultado.observacoes, 'Linha frontal encoberta');
});

test('análise vazia, múltipla, sem motivo ou incompatível é recusada', () => {
    for (const recomendacoes of [[], [corte, corte], [{ ...corte, motivo: '' }], [{ ...corte, id_corte: null }], [{ ...corte, compativel_com_cabelo_existente: false }], [{ ...corte, compativel_com_cabelo_existente: undefined }]]) {
        assert.throws(() => normalizarAnalise({ ...resposta, recomendacoes }));
    }
});

test('foto sem confirmação de persistência não pode iniciar simulação', () => {
    assert.throws(() => validarFotoSalva({ foto_url: '/foto.png' }));
    assert.throws(() => validarFotoSalva({ id_visagismo: 1, foto_url: '' }));
    assert.doesNotThrow(() => validarFotoSalva(resposta));
});

test('cada mudança relevante invalida a assinatura de uma simulação anterior', () => {
    const selecao = { idBarbearia: 11, idsServicos: '1,2', idVisagismo: 91, idCorte: 12, cor: '#432818', alvo: 'cabelo', categoriaCor: 'pintar_cabelos' };
    const anterior = assinaturaSimulacao(selecao);
    for (const [campo, novoValor] of Object.entries({ idBarbearia: 22, idsServicos: '2,3', idVisagismo: 92, idCorte: 24, cor: '#000000', alvo: 'barba', categoriaCor: 'pintar_barba' })) {
        assert.notEqual(assinaturaSimulacao({ ...selecao, [campo]: novoValor }), anterior, campo);
    }
    assert.equal(assinaturaSimulacao({ ...selecao, idCorte: '12' }), anterior);
});

test('corte com pintura exige corte recomendado e cor, inclusive após análise', () => {
    const selecao = { apenasCor: false, temPintar: true, modoPulado: false, corteSelecionado: corte, corSelecionada: '#432818', idVisagismo: 91 };
    assert.equal(erroDaSelecao(selecao), '');
    assert.match(erroDaSelecao({ ...selecao, corteSelecionado: null }), /corte cadastrado/);
    assert.match(erroDaSelecao({ ...selecao, corSelecionada: null }), /Selecione uma cor/);
    assert.match(erroDaSelecao({ ...selecao, idVisagismo: null }), /foto/);
});

test('pintura sem corte exige foto e cor; catálogo manual sem pintura pode agendar', () => {
    assert.equal(erroDaSelecao({ apenasCor: true, temPintar: true, modoPulado: true, corteSelecionado: null, corSelecionada: '#432818', idVisagismo: 91 }), '');
    assert.match(erroDaSelecao({ apenasCor: true, temPintar: true, modoPulado: true, corSelecionada: '#432818', idVisagismo: null }), /foto/);
    assert.equal(erroDaSelecao({ apenasCor: false, temPintar: false, modoPulado: true, corteSelecionado: corte, idVisagismo: null }), '');
});

test('seis características preservam limitações observadas sem inventar informação', () => {
    assert.equal(CAMPOS_CARACTERISTICAS.length, 6);
    assert.equal(textoCaracteristica('Não foi possível observar na foto'), 'Não foi possível observar na foto');
    assert.equal(textoCaracteristica(undefined), 'Não informado na análise');
    assert.equal(textoCaracteristica({ formato: 'oval' }), 'Não informado na análise');
});

test('escolher no atendimento funciona sem catálogo, mas exige pular análise sem pintura', () => {
    const fluxo = { modoPulado: true, temPintar: false, apenasCor: false };
    for (const escolhaCorte of ['na_hora', 'profissional']) {
        assert.equal(erroDaSelecao({ ...fluxo, escolhaCorte, corteSelecionado: null, idVisagismo: null }), '');
        for (const condicao of [{ modoPulado: false }, { temPintar: true }, { apenasCor: true }]) {
            assert.equal(permiteEscolhaNoAtendimento({ ...fluxo, ...condicao }), false);
            assert.match(erroDaSelecao({ ...fluxo, ...condicao, escolhaCorte, corSelecionada: '#000000', idVisagismo: 91 }), /simulação/);
        }
    }
    assert.match(erroDaSelecao({ ...fluxo, escolhaCorte: 'catalogo' }), /corte cadastrado/);
    assert.match(erroDaSelecao({ ...fluxo, escolhaCorte: 'inventado' }), /válida/);
});

test('gênero do serviço determina o profissional; mistos e desconhecidos usam termo genérico', () => {
    assert.equal(rotuloEscolhaCorte('profissional', ['feminino']), 'A cabeleireira escolhe');
    assert.equal(rotuloEscolhaCorte('profissional', ['feminino', 'feminino']), 'A cabeleireira escolhe');
    assert.equal(rotuloEscolhaCorte('profissional', ['masculino']), 'O barbeiro escolhe');
    for (const generos of [[], ['unissex'], ['feminino', 'masculino'], ['feminino', 'unissex']]) {
        assert.equal(rotuloEscolhaCorte('profissional', generos), 'O profissional escolhe');
    }
    assert.equal(rotuloEscolhaCorte('na_hora', ['feminino']), 'Escolho na hora');
});

test('escolhas especiais removem IDs anteriores no contrato de reserva e espera', () => {
    for (const escolhaCorte of ['na_hora', 'profissional']) {
        assert.deepEqual(dadosEscolhaCorte({ escolhaCorte, idCorte: '12', idVisagismo: '91' }), {
            escolha_corte: escolhaCorte, id_corte: null, id_visagismo: null
        });
    }
    assert.deepEqual(dadosEscolhaCorte({ escolhaCorte: 'catalogo', idCorte: '12', idVisagismo: '91' }), {
        escolha_corte: 'catalogo', id_corte: 12, id_visagismo: 91
    });
    assert.equal(dadosEscolhaCorte({ idCorte: -1 }).id_corte, null);
});

test('simulação apenas de cor preserva a sessão sem declarar um corte de catálogo inexistente', () => {
    assert.deepEqual(dadosEscolhaCorte({ escolhaCorte: null, idVisagismo: '91' }), {
        escolha_corte: null, id_corte: null, id_visagismo: 91
    });
    assert.deepEqual(dadosEscolhaCorte({ idVisagismo: '91' }), {
        escolha_corte: null, id_corte: null, id_visagismo: 91
    });
    assert.deepEqual(dadosEscolhaCorte({ escolhaCorte: 'catalogo', idCorte: null, idVisagismo: '91' }), {
        escolha_corte: null, id_corte: null, id_visagismo: 91
    });
    assert.equal(erroDaSelecao({ apenasCor: true, temPintar: true, modoPulado: true, corSelecionada: '#432818', idVisagismo: 91 }), '');
});

test('catálogo vazio válido permite decisão no atendimento; resposta quebrada não vira vazio', () => {
    assert.deepEqual(normalizarCatalogo({ cortes: [], generos_servico: ['feminino'] }), { cortes: [], generosServicos: ['feminino'] });
    assert.equal(normalizarCatalogo({ cortes: [{ id_corte: 12, nome: 'Long bob', genero: 'feminino' }], generos_servico: ['masculino'] }).generosServicos[0], 'masculino');
    for (const dados of [undefined, {}, { cortes: null }, { cortes: [{ id_corte: 'fake', nome: 'Inválido' }] }]) assert.throws(() => normalizarCatalogo(dados), /catálogo válido/);
});
