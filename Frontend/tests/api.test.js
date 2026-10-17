import test from 'node:test';
import assert from 'node:assert/strict';
import { API_URL, apiFetch, mensagemDaApi, urlDaApi } from '../src/services/api.js';

test('API usa mesma origem e resolve uploads locais ou URLs completas', () => {
    assert.equal(API_URL, '/api');
    assert.equal(urlDaApi('/uploads/foto.png'), '/api/uploads/foto.png');
    assert.equal(urlDaApi('uploads/foto.png'), '/api/uploads/foto.png');
    assert.equal(urlDaApi('https://imagens.example/foto.png'), 'https://imagens.example/foto.png');
    assert.equal(urlDaApi('blob:preview'), 'blob:preview');
    assert.equal(urlDaApi(null), '');
});

test('JSON preserva cabeçalhos, cookies e sinal de cancelamento', async (t) => {
    const controller = new AbortController();
    const body = JSON.stringify({ nome: 'Cliente' });
    t.mock.method(globalThis, 'fetch', async (url, options) => {
        assert.equal(url, '/api/cadastro');
        assert.equal(options.method, 'POST');
        assert.equal(options.credentials, 'include');
        assert.equal(options.signal, controller.signal);
        assert.equal(options.body, body);
        assert.equal(options.headers.get('Content-Type'), 'application/json');
        assert.equal(options.headers.get('X-Teste'), 'sim');
        return new Response('{"usuario":{"id":1}}', { status: 201 });
    });
    assert.deepEqual(await apiFetch('/cadastro', { method: 'POST', body, signal: controller.signal, headers: new Headers({ 'X-Teste': 'sim' }) }), { usuario: { id: 1 } });
});

test('FormData deixa navegador definir boundary e respeita opções explícitas', async (t) => {
    const body = new FormData();
    body.append('nome', 'Cliente');
    t.mock.method(globalThis, 'fetch', async (_url, options) => {
        assert.equal(options.headers.has('Content-Type'), false);
        assert.equal(options.body, body);
        assert.equal(options.credentials, 'omit');
        return new Response(null, { status: 204 });
    });
    assert.deepEqual(await apiFetch('/upload', { method: 'POST', body, credentials: 'omit' }), {});
});

test('Content-Type explícito é preservado', async (t) => {
    t.mock.method(globalThis, 'fetch', async (_url, options) => {
        assert.equal(options.headers.get('Content-Type'), 'text/plain');
        return new Response('{}');
    });
    await apiFetch('/teste', { body: 'texto', headers: { 'Content-Type': 'text/plain' } });
});

test('erro HTTP mantém status e contrato legado de mensagem', async (t) => {
    t.mock.method(globalThis, 'fetch', async () => new Response('{"mensagem":{"informacao":"Sessão expirada."}}', { status: 401 }));
    await assert.rejects(apiFetch('/perfil'), (erro) => {
        assert.equal(erro.tipo, 'http');
        assert.equal(erro.status, 401);
        assert.equal(mensagemDaApi(erro), 'Sessão expirada.');
        assert.equal(erro.dados.mensagem.informacao, 'Sessão expirada.');
        return true;
    });
});

test('HTML de erro HTTP não vaza para mensagem ao usuário', async (t) => {
    t.mock.method(globalThis, 'fetch', async () => new Response('<html>Traceback e caminhos internos</html>', { status: 502 }));
    await assert.rejects(apiFetch('/teste'), (erro) => {
        assert.equal(erro.tipo, 'http');
        assert.equal(erro.status, 502);
        assert.doesNotMatch(mensagemDaApi(erro), /html|Traceback|caminhos/);
        return true;
    });
});

test('JSON inválido em HTTP 200 é falha de resposta', async (t) => {
    t.mock.method(globalThis, 'fetch', async () => new Response('não é JSON'));
    await assert.rejects(apiFetch('/teste'), (erro) => erro.tipo === 'resposta' && erro.status === 200);
});

test('falha de rede recebe mensagem clara', async (t) => {
    t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Failed to fetch'); });
    await assert.rejects(apiFetch('/teste'), (erro) => erro.tipo === 'rede' && mensagemDaApi(erro).includes('conexão'));
});

test('cancelamento preserva AbortError', async (t) => {
    const erro = new DOMException('Cancelado', 'AbortError');
    t.mock.method(globalThis, 'fetch', async () => { throw erro; });
    await assert.rejects(apiFetch('/teste'), (recebido) => recebido === erro);
});

test('gráfico binário usa cookies e aceita SVG sem interpretar como JSON', async (t) => {
    t.mock.method(globalThis, 'fetch', async (_url, options) => {
        assert.equal(options.credentials, 'include');
        return new Response('<svg xmlns="http://www.w3.org/2000/svg"></svg>', { headers: { 'Content-Type': 'image/svg+xml' } });
    });
    const grafico = await apiFetch('/financeiro/grafico', {}, 'blob');
    assert.equal(grafico.type, 'image/svg+xml');
    assert.match(await grafico.text(), /^<svg/);
});

test('erro do gráfico mantém mensagem JSON do servidor', async (t) => {
    t.mock.method(globalThis, 'fetch', async () => new Response('{"erro":"Sem permissão."}', { status: 403 }));
    await assert.rejects(apiFetch('/financeiro/grafico', {}, 'blob'), (erro) => erro.status === 403 && mensagemDaApi(erro) === 'Sem permissão.');
});

test('mensagem de API rejeita objetos e HTML também em JSON', () => {
    assert.equal(mensagemDaApi({ dados: { erro: { interno: true } }, message: 'Falha segura' }), 'Falha segura');
    assert.equal(mensagemDaApi({ dados: { mensagem: { informacao: '<html>Segredo</html>' } } }), 'Ocorreu um erro ao comunicar com o servidor.');
    assert.equal(mensagemDaApi({ dados: { erro: { informacao: 'Dados inválidos.' } } }), 'Dados inválidos.');
});
