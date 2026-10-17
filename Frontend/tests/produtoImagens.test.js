import test from 'node:test';
import assert from 'node:assert/strict';
import { fotosValidas, urlFoto } from '../src/pages/Marketplace/marketplaceState.js';
import { produtoRequest, validarFotosProduto } from '../src/pages/Marketplace/produtoImagens.js';
const url='/uploads/marketplace/'+'a'.repeat(32)+'.webp';
test('fotos da loja aceitam somente referência estrita e não imagens privadas',()=>{
    assert.equal(urlFoto(url),url);
    for(const value of ['/uploads/visagismo/fotos/cliente_1.webp',url+'?x=1','/uploads/marketplace/../'+url,'/uploads/marketplace/photo.png']) assert.equal(urlFoto(value),'');
    assert.deepEqual(fotosValidas(url+'\nhttps://example.com/photo.jpg'),[url,'https://example.com/photo.jpg']);
});
test('produto sem fotos novas conserva contrato JSON',()=>{
    const dados={nome:'Pomada',imagens:[url]};const options=produtoRequest('PUT',dados);
    assert.equal(options.method,'PUT');assert.deepEqual(JSON.parse(options.body),dados);
});
test('fotos novas são enviadas com os dados do produto no mesmo formulário',()=>{
    const file=new File(['png'],'photo.png',{type:'image/png'});const dados={nome:'Pomada',imagens:[url]};
    const options=produtoRequest('POST',dados,[file]);assert.equal(options.body instanceof FormData,true);
    assert.deepEqual(JSON.parse(options.body.get('dados')),dados);assert.equal(options.body.getAll('imagens').length,1);
    assert.equal(options.body.get('imagens').name,'photo.png');assert.equal(options.body.get('imagens').type,'image/png');
    assert.equal(options.headers,undefined);
});
test('limite de fotos conta existentes e novas e rejeita arquivo inválido',()=>{
    const file={type:'image/png',size:100};assert.doesNotThrow(()=>validarFotosProduto(Array(7).fill(url),[file]));
    assert.throws(()=>validarFotosProduto(Array(8).fill(url),[file]));
    for(const image of [{type:'image/svg+xml',size:1},{type:'image/png',size:0},{type:'image/png',size:10*1024*1024+1}])assert.throws(()=>validarFotosProduto([],[image]));
});
