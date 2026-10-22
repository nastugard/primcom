import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const registry=JSON.parse(await fs.readFile(path.join(root,'seo/content-registry.json'),'utf8'));
let checks=0;
for (const [slug, predicate] of [
  ['do-2-mln',(_m,l)=>l.price>0 && l.price<=2000000],
  ['do-160-ls',(_m,l)=>l.powerHp>0 && l.powerHp<=160],
  ['miniveny-iz-yaponii',(m,l)=>m.country==='japan' && l.body==='Минивэн'],
]) {
  const expected=registry.models.filter(m=>m.status!=='inactive').filter(m=>(m.listings||[]).some(l=>predicate(m,l)));
  const html=await fs.readFile(path.join(root,'cars/podborki',slug,'index.html'),'utf8');
  for(const m of expected) assert.ok(html.includes(`/cars/${m.country}/${m.makeSlug}/${m.slug}/`),`${slug}: missing ${m.model}`);
  if(slug==='do-160-ls') {
    const unknown=registry.models.filter(m=>m.status!=='inactive' && !(m.listings||[]).some(l=>predicate(m,l)));
    for(const m of unknown) assert.ok(!html.includes(`class="seo-card__image" href="/cars/${m.country}/${m.makeSlug}/${m.slug}/"`),`Unknown power included: ${m.model}`);
  }
  assert.ok(html.includes('data-lead-modal') && html.includes('data-cookie'));
  checks++;
}

// Изолированный тест контракта формы. Сеть и отправка сообщений полностью подменены.
const listeners={};const formListeners={};const events=[];const requests=[];
const node=(extra={})=>({dataset:{},textContent:'',hidden:false,tabIndex:0,getClientRects:()=>[{}],focus(){document.activeElement=this;},...extra});
const fields=Object.fromEntries(['name','phone','city','budget','comment','company'].map(k=>[k,node({value:''})]));
const submit=node();const status=node();const context=node();const title=node();const dialog=node({querySelectorAll:()=>[submit]});
const form=node({elements:{namedItem:k=>fields[k]},addEventListener:(n,f)=>formListeners[n]=f,reportValidity:()=>true,setAttribute(){},removeAttribute(){},reset(){for(const f of Object.values(fields))f.value='';},querySelector:()=>submit});
const selectors={'[data-lead-form]':form,'[role="dialog"]':dialog,'[data-form-status]':status,'[data-lead-context]':context,'#lead-modal-title':title};
const modal=node({hidden:true,querySelector:s=>selectors[s]});
globalThis.document={querySelector:()=>modal,body:{dataset:{pageType:'model',leadModel:'Toyota Raize'},style:{overflow:''}},addEventListener:(n,f)=>listeners[n]=f,activeElement:null};
globalThis.window={ym:(...args)=>events.push(args)};
globalThis.location={origin:'https://primcom.ru',pathname:'/cars/japan/toyota/raize/'};
Object.defineProperty(globalThis,'navigator',{value:{userAgent:'unit-test'},configurable:true});
let resolveRequest;
globalThis.fetch=(url,options)=>{requests.push({url,payload:JSON.parse(options.body)});return new Promise(resolve=>resolveRequest=resolve);};
const {initLeadModal}=await import('../js/modules/modal-lead.js');
initLeadModal();
const button=node({dataset:{leadModel:'Toyota Raize',leadBudget:'до 2 млн ₽'},isConnected:true,closest:()=>null});
listeners.click({target:{closest:s=>s==='[data-open-lead-modal]'?button:null},preventDefault(){}});
assert.equal(modal.hidden,false);assert.equal(fields.budget.value,'до 2 млн ₽');checks++;
Object.assign(fields.name,{value:'TEST NAME'});fields.phone.value='123';
await formListeners.submit({preventDefault(){}});assert.equal(requests.length,0);checks++;
fields.phone.value='+79990000000';fields.city.value='TEST CITY';fields.comment.value='TEST PRIVATE COMMENT';
const first=formListeners.submit({preventDefault(){}});
await formListeners.submit({preventDefault(){}});assert.equal(requests.length,1);checks++;
resolveRequest({ok:true,json:async()=>({ok:true})});await first;
assert.match(requests[0].payload.comment,/Toyota Raize/);assert.match(requests[0].payload.comment,/TEST CITY/);
assert.ok(events.some(args=>args[2]==='lead_submit_success'));
assert.ok(!JSON.stringify(events).includes('TEST PRIVATE COMMENT'));assert.ok(!JSON.stringify(events).includes('+79990000000'));assert.ok(!JSON.stringify(events).includes('TEST CITY'));checks++;
const successes=events.filter(args=>args[2]==='lead_submit_success').length;
fields.name.value='TEST';fields.phone.value='+79990000000';
const failed=formListeners.submit({preventDefault(){}});resolveRequest({ok:false,status:500});await failed;
assert.equal(requests.length,2);assert.equal(events.filter(args=>args[2]==='lead_submit_success').length,successes);assert.equal(submit.disabled,false);checks++;
const invalid=formListeners.submit({preventDefault(){}});resolveRequest({ok:true,json:async()=>({ok:false})});await invalid;
assert.equal(events.filter(args=>args[2]==='lead_submit_success').length,successes);checks++;
for(const file of ['cars/japan/toyota/raize/index.html','guides/kak-chitat-aukcionnyy-list/index.html','cars/primery/suzuki-jimny-2021/index.html']){
 const html=await fs.readFile(path.join(root,file),'utf8');assert.equal((html.match(/data-lead-modal hidden/g)||[]).length,1);assert.ok(html.includes('data-cookie'));checks++;
}
console.log(`Organic conversion checks passed: ${checks}/${checks}. No real requests sent.`);
