import test from 'node:test';
import assert from 'node:assert/strict';
import { carregarPerfilPublico } from '../src/pages/Marketplace/perfilPublico.js';
import { temaDaLoja } from '../src/pages/Marketplace/lojaState.js';

test('Visitante lê perfil e cores pela API pública sem sessão ou requisição privada', async t => {
    const controle = new AbortController();
    const perfil = { nome_barbearia: 'Loja pública', personalizado: true,
        personalizacao: { id_usuario: 17, cor_primaria: '#123456' },
        servicos: [{ id_servico: 3, nome: 'Corte', preco: 30, duracao: 40 }], funcionarios: [] };
    const chamada = t.mock.method(globalThis, 'fetch', async (url, options) => {
        assert.equal(url, '/api/marketplace/barbearias/17/perfil');
        assert.equal(options.credentials, 'omit');
        assert.equal(options.signal, controle.signal);
        return new Response(JSON.stringify(perfil), { status: 200 });
    });
    assert.deepEqual(await carregarPerfilPublico('17', { signal: controle.signal }), perfil);
    assert.equal(chamada.mock.callCount(), 1);
    assert.equal(temaDaLoja(perfil.personalizacao)['--cor-destaque'], '#123456');
});

test('Perfil indisponível mantém 404 sem tentar configuração privada como alternativa', async t => {
    const chamada = t.mock.method(globalThis, 'fetch', async () => new Response('{"erro":"Barbearia não encontrada."}', { status: 404 }));
    await assert.rejects(carregarPerfilPublico(99), erro => erro.status === 404);
    assert.equal(chamada.mock.callCount(), 1);
    assert.equal(temaDaLoja(null)['--cor-destaque'], '#FF9C08');
});

test('ID inválido nunca dispara uma requisição de perfil público', async t => {
    const chamada = t.mock.method(globalThis, 'fetch', async () => { throw new Error('Requisição inesperada'); });
    for (const id of ['', 0, -1, '../config', '9007199254740993']) {
        await assert.rejects(carregarPerfilPublico(id), /Barbearia inválida/);
    }
    assert.equal(chamada.mock.callCount(), 0);
});
