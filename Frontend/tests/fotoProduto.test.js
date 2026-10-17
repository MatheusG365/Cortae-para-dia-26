import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { transformSync } from 'rolldown/utils';
import { urlFoto } from '../src/pages/Marketplace/marketplaceState.js';
import { urlDaApi } from '../src/services/api.js';

function imageHarness() {
    const source=fs.readFileSync(new URL('../src/pages/Marketplace/MarketplaceUI.jsx',import.meta.url),'utf8');
    const actual=source.slice(source.indexOf('export function FotoProduto'),source.indexOf('export function LojaLayout')).replace('export function','function');
    const compiled=transformSync('FotoProduto.jsx',actual,{jsx:{runtime:'classic',pragma:'jsx'}}).code;
    let state;
    const jsx=(type,props,...children)=>({type,props:{...props,children}});
    const FotoProduto=vm.runInNewContext(compiled+';FotoProduto',{
        jsx, useState(initial) { if(state===undefined)state=initial;return[state,value=>{state=typeof value==='function'?value(state):value;}]; },
        urlFoto,urlDaApi,styles:{semFoto:'semFoto'},FiShoppingBag:'Icon',
    });
    return (url)=>FotoProduto({url,nome:'Produto'});
}

test('capa recupera ao editar URL e erro tardio da capa antiga não afeta foto nova',()=>{
    const render=imageHarness();const old='/uploads/marketplace/'+'a'.repeat(32)+'.webp';const next=old.replace('a'.repeat(32),'b'.repeat(32));
    const first=render(old);assert.equal(first.type,'img');first.props.onError();assert.equal(render(old).type,'div');
    const second=render(next);assert.equal(second.type,'img');assert.equal(second.props.src,urlDaApi(next));
    first.props.onError();assert.equal(render(next).type,'img');
    second.props.onError();assert.equal(render(next).type,'div');
    first.props.onError();assert.equal(render(next).type,'div');
    assert.equal(render('https://example.test/new.jpg').type,'img');
});
