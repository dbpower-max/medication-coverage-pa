const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const load=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=load('_site/data.json.gz');
for(const file of Object.values(data.planDataFiles||{})) data.medications.push(...load('_site/'+file.split('?')[0].replace(/^\.\//,'')));
delete data.planDataFiles;
const script=fs.readFileSync('_site/app.js','utf8');
const hook="document.addEventListener('DOMContentLoaded', init);";
assert(script.includes(hook));
const ctx={document:{querySelectorAll:()=>[]},Intl,console};vm.createContext(ctx);
vm.runInContext(script.replace(hook,'globalThis.api={state,el,recordsForPlan,planMedicationGroups,filteredRecords,render,uniqueMedicationNames,criteriaSources,renderCriteriaLibrary,namedPlanPolicies};'),ctx);
const {api}=ctx;api.state.data=data;
for(const id of ['criteriaSearch','criteriaCount','criteriaResults','criteriaLibrary','planStatus','planEvidence','evidenceList','loadingState','resultCount','effectiveDate','emptyState','resultGrid','showMore']) api.el[id]={value:'',innerHTML:'',textContent:'',hidden:false};
for(const planId of data.plans.map(p=>p.id)) {
 api.state.planId=planId;api.state.term='Mounjaro';
 const results=api.render();
 assert.equal(results.filter(g=>/mounjaro/i.test(g.label)).length,1,'Mounjaro duplicate in '+planId);
 assert(results.every(g=>g.records.length&&g.records.every(r=>r.recordType==='formulary')),'Nonmedication result in '+planId);
 assert(!api.el.resultGrid.innerHTML.includes('Policy source indexed'));
 assert(api.el.criteriaResults.innerHTML.includes('gl-749236'),'Existing Mounjaro criteria inaccessible in '+planId);
 if(planId==='uhc-community-az') {
  assert(api.el.resultGrid.innerHTML.includes('Selected-plan policy · GLP-1 Agonists'),'Named UHC GLP-1 source not attached to Mounjaro');
  assert(api.el.resultGrid.innerHTML.includes('uhc-nov2026-policy-gl-720195'),'Wrong GLP-1 policy linked to UHC Mounjaro');
 }
 const sources=api.criteriaSources();
 assert(sources.every(p=>p.planId==='ahcccs-ffs-aihp'||p.planId===planId),'Cross-plan policy leak');
 const all=api.planMedicationGroups();
 assert.equal(new Set(all.map(g=>g.label.trim().toLowerCase())).size,all.length,'Exact duplicate medication labels in '+planId);
}
api.state.planId='banner-ufc';api.state.term='Inhaled Corticosteroids';
assert.equal(api.render().length,0,'Policy still appears as a medication');
assert(api.el.criteriaResults.innerHTML.includes('Inhaled Corticosteroids'),'Plan policy lost from criteria library');
assert.equal(api.el.criteriaLibrary.open,true,'Policy-only match is hidden in collapsed library');
api.state.term='GL-749236';api.render();
assert(api.el.criteriaResults.innerHTML.includes('Mounjaro'),'Policy code search cannot reach structured guide');
api.state.term='Qvar';api.render();
assert(api.el.resultGrid.innerHTML.includes('Selected-plan policy'),'Existing Banner policy link remains buried');
assert(api.el.resultGrid.innerHTML.includes('linked:banner-ufc:'),'Banner inline source reader missing');
assert(!api.el.resultGrid.innerHTML.includes('linked:uhc-community-az:'),'Wrong plan source reader attached');
data.policies.push({id:'combination-negative',planId:'banner-ufc',recordType:'policy_index',sourceTextUrl:'test.txt',notes:'Named Product Name fields: alpha-test/beta-test Policy product-field matches are search aids;'});
assert.equal(api.namedPlanPolicies({name:'alpha-test',brands:[]}).length,0,'Single ingredient matched a combination-product source');
assert.equal(api.namedPlanPolicies({name:'alpha-test/beta-test',brands:[]}).length,1,'Exact combination source unavailable');
// A source record accidentally inserted into medications must still fail closed.
data.medications.push({id:'internal-audit',planId:'banner-ufc',recordType:'audit',name:'Internal Audit Sentinel'});
api.state.term='Internal Audit Sentinel';assert.equal(api.render().length,0);
assert(!api.uniqueMedicationNames().some(n=>n.includes('Audit Sentinel')));
api.state.term='baseline';assert.equal(api.filteredRecords().length,0,'Provenance prose matches a medication-name query');
api.state.term='Adderall XR';api.state.coverage='pa_conditional';
assert.equal(api.render().length,1,'Conditional PA filter lost age-restricted Adderall XR');
api.state.coverage='pa_required';assert.equal(api.render().length,0,'Conditional PA appears unconditional');
console.log('PASS: only medication results, source-only records excluded, medication-only name matching, plan-isolated criteria, structured policy lookup and conditional PA filtering');
