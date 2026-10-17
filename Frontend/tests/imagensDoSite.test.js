import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { urlImagemDoSite, inicializarImagensDoSite } from '../src/services/imagensDoSite.js';

function documentoDeTeste(comFavicon = true) {
    const propriedades = new Map();
    const favicon = comFavicon ? {} : null;
    return {
        propriedades,
        favicon,
        documentElement: { style: { setProperty: (nome, valor) => propriedades.set(nome, valor) } },
        querySelector: seletor => { assert.equal(seletor, 'link[rel="icon"]'); return favicon; },
    };
}

test('logos e fotos usam o proxy da API, sem URL ou identificação do Drive no cliente', () => {
    assert.equal(urlImagemDoSite('logopreta.png'), '/api/midia/site/logopreta.png');
    assert.equal(urlImagemDoSite('foto com espaço.png'), '/api/midia/site/foto%20com%20espa%C3%A7o.png');
});

test('inicialização prepara fundos CSS e favicon antes da renderização', () => {
    const documento = documentoDeTeste();
    inicializarImagensDoSite(documento);
    assert.equal(documento.propriedades.get('--imagem-site-banner'), 'url("/api/midia/site/banner.png")');
    assert.equal(documento.propriedades.get('--imagem-site-login'), 'url("/api/midia/site/imagem_login.png")');
    assert.equal(documento.propriedades.get('--imagem-site-cadastro'), 'url("/api/midia/site/cadastro.png")');
    assert.deepEqual(documento.favicon, { type: 'image/webp', href: '/api/midia/site/logosolo.png' });
    assert.doesNotThrow(() => inicializarImagensDoSite(documentoDeTeste(false)));
});

test('API em outra origem é respeitada também nos fundos e no favicon', async () => {
    // Carrega os módulos reais com o ambiente que o Vite substituiria no build.
    const api = fs.readFileSync(new URL('../src/services/api.js', import.meta.url), 'utf8')
        .replaceAll('import.meta.env', JSON.stringify({ VITE_API_URL: ' https://api.exemplo.test/cortae/ ' }));
    const apiModulo = `data:text/javascript;base64,${Buffer.from(api).toString('base64')}`;
    const imagens = fs.readFileSync(new URL('../src/services/imagensDoSite.js', import.meta.url), 'utf8')
        .replace("'./api.js'", JSON.stringify(apiModulo));
    const modulo = await import(`data:text/javascript;base64,${Buffer.from(imagens).toString('base64')}`);
    const documento = documentoDeTeste();
    modulo.inicializarImagensDoSite(documento);
    assert.equal(modulo.urlImagemDoSite('logobranca.png'), 'https://api.exemplo.test/cortae/midia/site/logobranca.png');
    assert.equal(documento.favicon.href, 'https://api.exemplo.test/cortae/midia/site/logosolo.png');
    for (const valor of documento.propriedades.values()) {
        assert.ok(valor.startsWith('url("https://api.exemplo.test/cortae/midia/site/'));
    }
});
