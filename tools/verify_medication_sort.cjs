const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const load=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=load('_site/data.json.gz');
for(const file of Object.values(data.planDataFiles||{}))data.medications.push(...load('_site/'+file.split('?')[0].replace(/^\.\//,'')));
delete data.planDataFiles;
const script=fs.readFileSync('_site/app.js','utf8'),html=fs.readFileSync('_site/index.html','utf8');
const ctx={document:{querySelectorAll:()=>[]},Intl,console};vm.createContext(ctx);
vm.runInContext(script.replace("document.addEventListener('DOMContentLoaded', init);",'globalThis.api={state,el,render,medicationSortName,subcategoryLabel,subcategoryOptions,filteredRecords};'),ctx);
const {api}=ctx;api.state.data=data;
for(const id of ['criteriaSearch','criteriaCount','criteriaResults','criteriaLibrary','planStatus','planEvidence','evidenceList','loadingState','resultCount','effectiveDate','emptyState','resultGrid','showMore'])api.el[id]={value:'',innerHTML:'',textContent:'',hidden:false};
api.el.criteriaLibrary.hidden=true;
assert.equal(api.state.sort,'az','Default is not alphabetical');
assert(html.includes('<option value="az" selected>A–Z</option>')&&html.includes('<option value="za">Z–A</option>'),'Visible sort choices missing');
const compare=new Intl.Collator('en',{sensitivity:'base',numeric:true});
for(const plan of data.plans){
 api.state.planId=plan.id;
 for(const term of ['', 'insulin', 'Mounjaro']){
  api.state.term=term;api.state.sort='az';api.state.limit=50;
  const ascending=api.render();
  assert(ascending.every((g,i)=>!i||compare.compare(api.medicationSortName(ascending[i-1]),api.medicationSortName(g))<=0),'A–Z failed: '+plan.id+' '+term);
  const headings=[...api.el.resultGrid.innerHTML.matchAll(/<h3>(.*?)<\/h3>/g)].map(m=>m[1]);
  assert.equal(headings.length,Math.min(ascending.length,50),'Pagination count changed');
  api.state.sort='za';const descending=api.render();
  assert.deepEqual(Array.from(descending,g=>g.key),Array.from(ascending,g=>g.key).reverse(),'Z–A is not complete-set reversal');
  api.state.limit=100;const expanded=api.render();
  assert.deepEqual(Array.from(expanded,g=>g.key),Array.from(descending,g=>g.key),'Show-more changes order');
 }
}
assert(script.includes("state.sort = el.sortInput.value === 'za' ? 'za' : 'az'; resetLimitAndRender()"),'Sort interaction fails to reset pagination');
assert(script.includes("el.sortInput.value = 'az'"),'Clear filters does not restore alphabetical default');
assert.equal(api.medicationSortName({label:'5-fluorouracil Cream'}),'5-fluorouracil Cream','Genuine medication-name number removed');
const artifact='SCABICIDES & PEDICULICIDES TOPICAl AGENTS+A1106';
assert.equal(api.subcategoryLabel(artifact),'Scabicides & Pediculicides Topical Agents');
assert.equal(api.subcategoryLabel('PHOSPHODIESTERASE 4 (PDE4) INHIBITORS - TOPICAL'),'Phosphodiesterase 4 (PDE4) Inhibitors - Topical');
assert.equal(api.subcategoryLabel('NONSTEROIDAL ANTI- INFLAMMATORY AGENTS (NSAIDS)'),'Nonsteroidal Anti-Inflammatory Agents (NSAIDs)');
api.state.planId='az-complete-health';api.state.term='';api.state.category='Dermatology';api.state.subcategory=artifact;
const before=api.filteredRecords().map(r=>r.id).sort().join('|');
assert(before.length>0,'Actual artifact fixture missing');
api.state.subcategory=api.subcategoryLabel(artifact);
assert.equal(api.filteredRecords().map(r=>r.id).sort().join('|'),before,'Clean subcategory lost records');
assert(api.subcategoryOptions().includes(api.subcategoryLabel(artifact)),'Clean subcategory absent');
assert(!api.subcategoryOptions().some(x=>x.includes('+A1106')),'Backend cell artifact remains visible');
console.log('PASS: A–Z default, Z–A reversal, full-set sorting before pagination, 3-plan/search consistency and reset behavior');
