const test=require('node:test');const assert=require('node:assert/strict');
const {productImageLinks,productImageUrl,validateProductPhotos,productPhotoBody}=require('../src/features/owner/productPhotos.ts');
const url='/uploads/marketplace/'+'a'.repeat(32)+'.webp';
test('native product refs allow only managed marketplace and public HTTPS',()=>{
 assert.equal(productImageUrl(url),url);assert.deepEqual(productImageLinks(url+'\nhttps://example.com/x'),[url,'https://example.com/x']);
 for(const path of ['/uploads/visagismo/fotos/x.webp',url+'?x=1','file:///data/x','data:image/png;base64,x','https://secret@x.test/a'])assert.throws(()=>productImageLinks(path));
});
test('native product photos count combined refs and reject large or unsupported media',()=>{
 assert.doesNotThrow(()=>validateProductPhotos(Array(7).fill(url),[{uri:'file:///x',mimeType:'image/png',fileSize:100}]));
 assert.throws(()=>validateProductPhotos(Array(8).fill(url),[{uri:'file:///x'}]));
 for(const photo of [{uri:''},{uri:'file:///x',fileSize:10*1024*1024+1},{uri:'file:///x',mimeType:'image/svg+xml'}])assert.throws(()=>validateProductPhotos([],[photo]));
});
test('native JSON remains compatible and multipart appends files with product data',async()=>{
 const data={nome:'Pomada',imagens:[url]};let calls=[];
 assert.equal(await productPhotoBody(data,[],async()=>{}),data);
 const photo={uri:'file:///x',mimeType:'image/png'};
 const body=await productPhotoBody(data,[photo],async(form,key,item)=>{calls.push({key,item});form.append(key,new Blob(['png'],{type:item.mimeType}),'x.png')});
 assert.equal(body instanceof FormData,true);assert.deepEqual(JSON.parse(body.get('dados')),data);assert.equal(calls[0].key,'imagens');assert.equal(calls[0].item,photo);assert.equal(body.get('imagens').type,'image/png');
});
