import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { transformSync } from 'rolldown/utils';
import { filtrarRotas, rotaVinculada } from '../src/pages/HelpAdmin/helpCatalogo.js';

const rotas = [
    { id: 'api:midia_site', origem: 'backend', rota: '/midia/site/<path:nome>', metodos: ['GET'], titulo: 'Imagens públicas do site', como_funciona: ['Lê a imagem WebP privada no Google Drive pela API.'] },
    { id: 'api:perfil', origem: 'backend', rota: '/perfil', metodos: ['PUT'], titulo: 'Editar perfil', observacoes: ['Imagem enviada como arquivo é otimizada em WebP e armazenada no Drive.'] },
];
const imagens = {
    titulo: 'Imagens no Google Drive',
    descricao: 'Site e aplicativo usam a mesma API para ler imagens privadas.',
    etapas: ['Seleção no formulário.', 'Validação e otimização WebP.', 'Envio privado ao Drive e referência no banco.', 'Leitura pela API.'],
    tipos: ['Perfil, cortes, logo, galeria e visagismo.', 'Produtos do marketplace e imagens fixas.'],
    observacoes: ['Links externos permanecem URLs.', 'Ícones de compilação do app continuam locais.', '404: ausente; 413: limite excedido; 503: armazenamento indisponível.'],
    apis: [...rotas, { id: 'api:ausente', rota: '/indisponivel', titulo: 'Documentação não fornecida', metodos: ['POST'] }],
    arquivos: [{ id: 'storage', caminho: 'Backend/image_storage.py' }],
};

function componente() {
    const source = fs.readFileSync(new URL('../src/pages/HelpAdmin/VisaoImagens.jsx', import.meta.url), 'utf8');
    const actual = source.slice(source.indexOf('export default function')).replace('export default function', 'function');
    const compiled = transformSync('VisaoImagens.jsx', actual, { jsx: { runtime: 'classic', pragma: 'jsx' } }).code;
    return vm.runInNewContext(`${compiled};VisaoImagens`, {
        jsx: React.createElement,
        rotaVinculada,
        styles: new Proxy({}, { get: (_, nome) => nome }),
        FiArrowRight: 'span', FiFileText: 'span', FiImage: 'span',
        fetch: () => assert.fail('Consultar o Help não deve executar nenhuma integração.'),
    });
}

function elementos(arvore) {
    if (!arvore || typeof arvore !== 'object') return [];
    if (Array.isArray(arvore)) return arvore.flatMap(elementos);
    return [arvore, ...elementos(arvore.props?.children)];
}

test('resumo renderiza o fluxo recebido e abre somente documentos presentes no catálogo', () => {
    const selecionadas = [];
    const arvore = componente()({ imagens, rotas, onSelecionar: id => selecionadas.push(id) });
    const html = renderToStaticMarkup(arvore);
    for (const texto of [...imagens.etapas, ...imagens.tipos, ...imagens.observacoes]) assert.ok(html.includes(texto));
    assert.ok(html.includes('Backend/image_storage.py'));
    const elementosRenderizados = elementos(arvore);
    assert.equal(elementosRenderizados.filter(item => ['img', 'a', 'form', 'iframe'].includes(item.type)).length, 0);
    const botoes = elementosRenderizados.filter(item => item.type === 'button');
    assert.equal(botoes.length, 3);
    assert.deepEqual(botoes.map(item => item.props.disabled), [false, false, true]);
    for (const botao of botoes.filter(item => !item.props.disabled)) {
        assert.equal(botao.props.type, 'button');
        botao.props.onClick();
    }
    assert.deepEqual(selecionadas, rotas.map(rota => rota.id));
});

test('API anterior sem resumo permanece compatível e aviso OAuth vem somente do servidor', () => {
    const render = componente();
    assert.equal(render({ rotas, onSelecionar() {} }), null);
    assert.equal(render({ imagens: null, rotas, onSelecionar() {} }), null);
    const semAviso = renderToStaticMarkup(render({ imagens, rotas, onSelecionar() {} }));
    assert.ok(!semAviso.includes('sete dias'));
    const aviso = 'OAuth em teste: a autorização pode expirar após sete dias.';
    const comAviso = renderToStaticMarkup(render({ imagens: { ...imagens, observacoes: [aviso] }, rotas, onSelecionar() {} }));
    assert.ok(comAviso.includes(aviso));
});

test('buscas de Drive, WebP e imagem encontram leitura e envio, preservando filtros', () => {
    for (const busca of ['Drive', 'WebP', 'imagem']) {
        assert.deepEqual(filtrarRotas(rotas, { busca }).map(rota => rota.id), rotas.map(rota => rota.id));
        assert.deepEqual(filtrarRotas(rotas, { busca, metodo: 'GET' }).map(rota => rota.id), ['api:midia_site']);
        assert.equal(filtrarRotas(rotas, { busca, origem: 'mobile' }).length, 0);
    }
});
