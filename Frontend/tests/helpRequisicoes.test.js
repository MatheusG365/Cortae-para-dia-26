import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { transformSync } from 'rolldown/utils';
import { rotaVinculada } from '../src/pages/HelpAdmin/helpCatalogo.js';

function componente() {
    const source = fs.readFileSync(new URL('../src/pages/HelpAdmin/VisaoRequisicoes.jsx', import.meta.url), 'utf8');
    const actual = source.slice(source.indexOf('export default function')).replace('export default function', 'function');
    const compiled = transformSync('VisaoRequisicoes.jsx', actual, { jsx: { runtime: 'classic', pragma: 'jsx' } }).code;
    return vm.runInNewContext(`${compiled};VisaoRequisicoes`, {
        jsx: React.createElement, React, rotaVinculada,
        styles: new Proxy({}, { get: (_, name) => name }),
        FiArrowRight: 'span', FiGitMerge: 'span',
        fetch() { assert.fail('Opening documentation must not execute requests'); },
    });
}

const rotas = [{ id: 'api:cep', rota: '/marketplace/cep/<postal_code>', metodos: ['GET'] }];
const requisicoes = { titulo: 'Requisições', observacoes: ['Consulta exclusiva do ADM.'], guias: [{
    id: 'cep', titulo: 'Busca por CEP', descricao: 'ViaCEP através do backend.',
    etapas: ['Valida oito dígitos.', 'Preenche rua, bairro, cidade e UF.'],
    diagnostico: ['503: consulta indisponível; preenchimento manual permitido.'],
    requisicoes: [
        { metodo: 'GET', rota: '/marketplace/cep/{postal_code}', api_id: 'api:cep', entrada: 'CEP válido.', saida: 'endereco.', corpo: { texto: '<img src=x onerror=alert(1)>' } },
        { metodo: 'POST', rota: '/ausente', api_id: 'ausente', entrada: 'Exemplo.', saida: 'Sem contrato disponível.' },
    ],
}] };

function elementos(node) {
    if (!node || typeof node !== 'object') return [];
    if (Array.isArray(node)) return node.flatMap(elementos);
    return [node, ...elementos(node.props?.children)];
}

test('guia mostra sequência, exemplos escapados e diagnóstico sem executar operações', () => {
    const tree = componente()({ requisicoes, rotas, onSelecionar() {} });
    const html = renderToStaticMarkup(tree);
    for (const content of ['Busca por CEP', 'Valida oito', 'Recebe:', 'Retorna:', '503:', 'não executa a requisição']) assert.ok(html.includes(content));
    assert.ok(html.includes('&lt;img'));
    assert.ok(!html.includes('<img src=x'));
    assert.equal(elementos(tree).filter(node => node.type === 'details').length, 1);
});

test('botão abre somente documento registrado e não invoca o endpoint descrito', () => {
    const selected = [];
    const tree = componente()({ requisicoes, rotas, onSelecionar: id => selected.push(id) });
    const buttons = elementos(tree).filter(node => node.type === 'button');
    assert.equal(buttons.length, 2);
    assert.equal(buttons[0].props.disabled, false);
    assert.equal(buttons[1].props.disabled, true);
    assert.ok(buttons.every(node => node.props.type === 'button'));
    buttons[0].props.onClick();
    assert.deepEqual(selected, ['api:cep']);
});

test('catálogo anterior sem guias continua renderizável', () => {
    const render = componente();
    assert.equal(render({ rotas, onSelecionar() {} }), null);
    assert.equal(render({ requisicoes: { guias: [] }, rotas, onSelecionar() {} }), null);
});
