const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const load=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=load('_site/data.json.gz');
for(const file of Object.values(data.planDataFiles||{}))data.medications.push(...load('_site/'+file.split('?')[0].replace(/^\.\//,'')));
delete data.planDataFiles;
const script=fs.readFileSync('_site/app.js','utf8'),html=fs.readFileSync('_site/index.html','utf8');
const handlers=[];const dialog={open:false,querySelector:s=>s==='#sourceDialogTitle'?dialog.title:dialog.body,title:{textContent:''},body:{innerHTML:''},showModal(){this.open=true},close(){this.open=false}};
const ctx={document:{querySelectorAll:()=>[],getElementById:()=>dialog,addEventListener:(name,fn)=>{if(name==='click')handlers.push(fn)}},Intl,console};
vm.createContext(ctx);
vm.runInContext(script.replace("document.addEventListener('DOMContentLoaded', init);",'globalThis.api={state,el,render,planMedicationGroups,statusChips,resolvePlan,valuesForCombo,bindCriteriaLibrary,cardSourceGroups};'),ctx);
const api=ctx.api;api.state.data=data;
for(const id of ['criteriaSearch','criteriaCount','criteriaResults','criteriaLibrary','planStatus','planEvidence','evidenceList','loadingState','resultCount','effectiveDate','emptyState','resultGrid','showMore'])api.el[id]={value:'',innerHTML:'',textContent:'',hidden:false,addEventListener:()=>{}};
api.el.criteriaLibrary.hidden=true;
assert(/id="criteriaLibrary"[^>]*hidden/.test(html),'Standalone search is not archived');
assert(html.indexOf('id="results"')<html.indexOf('id="planStatus"'),'Technical plan panel still precedes medication results');
assert(html.includes('id="sourceDialog"')&&html.includes('data-close-sources'),'Sources dialog/close control absent');
for(const plan of data.plans){
 api.state.planId=plan.id;
 assert(api.valuesForCombo('plan').every(n=>n.startsWith('AHCCCS: ')),'Plan prefix missing');
 assert.equal(api.resolvePlan('AHCCCS: '+plan.name).id,plan.id);
 assert.equal(api.resolvePlan(plan.name).id,plan.id,'Existing plan API name broken');
 for(const term of ['Mounjaro','Epclusa','Qvar','Paxlovid','Humatin']){
  api.state.term=term;const groups=api.render();const markup=api.el.resultGrid.innerHTML;
  const stack=[];let cards=0,topDetails=0;
  for(const m of markup.matchAll(/<(\/?)([a-z][a-z0-9-]*)\b([^>]*)>/gi)){
   const [,closing,tag,attrs]=m;const name=tag.toLowerCase();
   if(closing){assert.equal(stack.pop(),name,'Invalid card nesting: '+term);continue;}
   if(name==='article'&&/result-card/.test(attrs))cards++;
   if(name==='details'&&stack.length===1&&stack[0]==='article'){
    topDetails++;assert(attrs.includes('clinical-details'),'Extra top-level technical dropdown');
    assert(!/\bopen(?:\s|=|$)/.test(attrs),'Clinical details opened by default');
   }
   if(!['br','input','hr','img','meta','link'].includes(name))stack.push(name);
  }
  assert.equal(cards,groups.length);assert.equal(topDetails,cards,'One clinical dropdown per card required');
  assert(!markup.includes('Preference not specified')&&!markup.includes('Details and source records'),'Internal labels remain');
  assert(!api.el.criteriaLibrary.open,'Medication search reopened archived criteria library');
 }
}
api.state.planId='az-complete-health';api.state.term='Mounjaro';api.render();api.bindCriteriaLibrary();
const key=api.cardSourceGroups.keys().next().value;
const sourceButton={dataset:{cardSources:key}};
for(const fn of handlers)fn({target:{closest:s=>s==='[data-card-sources]'?sourceButton:null}});
assert(dialog.open&&dialog.body.innerHTML.includes('AHCCCS')&&dialog.body.innerHTML.includes('href='),'Original records/source links not accessible');
for(const fn of handlers)fn({target:{closest:s=>s==='[data-close-sources]'?{}:null}});
assert(!dialog.open,'Sources close failed');
const content={hidden:true,dataset:{},innerHTML:''};
const shortcut={dataset:{criteriaQuery:'FLEXERIL',criteriaFallback:'cyclobenzaprine'},closest:()=>({querySelector:()=>content}),setAttribute:()=>{}};
for(const fn of handlers)fn({target:{closest:s=>s==='[data-criteria-query]'?shortcut:null}});
assert(!content.hidden&&content.innerHTML.includes('Fexmid'),'Archived search removal stranded legacy-brand criteria');
assert(api.el.criteriaLibrary.hidden&&!api.el.criteriaLibrary.open,'Inline lookup exposed archived search');
console.log('PASS: one collapsed clinical dropdown/card; archived search; inline criteria; source dialog/close; 3-plan prefixes; preserved original links and PA statuses');
