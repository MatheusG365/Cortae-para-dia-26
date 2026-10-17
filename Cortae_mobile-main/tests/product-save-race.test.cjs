const test=require('node:test');const assert=require('node:assert/strict');
const {createProductSaver}=require('../src/features/owner/productSave.ts');
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return{promise,resolve}};
function harness(){let epoch=1,server='https://old.test/api';const states=[],calls=[];const saver=createProductSaver({sessionVersion:()=>epoch,apiUrl:()=>server,message:error=>error.message,update:state=>states.push(state)});return{saver,states,calls,change:()=>epoch++,changeServer:()=>server='https://new.test/api'}};
for(const invalidation of ['change','changeServer','dispose'])test(`product preparation cannot send or update UI after ${invalidation}`,async()=>{
 const h=harness(),photo=deferred();let done=0,signal;
 const run=h.saver.run(async context=>{signal=context.signal;await photo.promise;if(context.current())h.calls.push('POST');},()=>done++);
 assert.equal(h.states.length,1);
 invalidation==='dispose'?h.saver.dispose():h[invalidation]();photo.resolve();
 assert.equal(await run,false);assert.deepEqual(h.calls,[]);assert.equal(done,0);assert.equal(h.states.length,1);
 if(invalidation==='dispose')assert.equal(signal.aborted,true);
});
test('late response after account change cannot navigate or update UI',async()=>{
 const h=harness(),response=deferred();let done=0;
 const run=h.saver.run(async context=>{assert.equal(context.current(),true);h.calls.push('POST');await response.promise;},()=>done++);
 h.change();response.resolve();assert.equal(await run,false);assert.equal(done,0);assert.equal(h.states.length,1);
});
test('current session submits once and releases loading state',async()=>{
 const h=harness(),response=deferred();let done=0;
 const action=async context=>{if(context.current())h.calls.push('POST');await response.promise};
 const run=h.saver.run(action,()=>done++);assert.equal(await h.saver.run(action),false);response.resolve();
 assert.equal(await run,true);assert.deepEqual(h.calls,['POST']);assert.equal(done,1);assert.equal(h.states.at(-1).busy,false);
});
