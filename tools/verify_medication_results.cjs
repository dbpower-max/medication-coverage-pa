const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const load=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=load('_site/data.json.gz');
for(const file of Object.values(data.planDataFiles||{})) data.medications.push(...load('_site/'+file.split('?')[0].replace(/^\.\//,'')));
delete data.planDataFiles;
const script=fs.readFileSync('_site/app.js','utf8');
const hook="document.addEventListener('DOMContentLoaded', init);";
assert(script.includes(hook));
const ctx={document:{querySelectorAll:()=>[]},Intl,console};vm.createContext(ctx);
vm.runInContext(script.replace(hook,'globalThis.api={state,el,recordsForPlan,planMedicationGroups,filteredRecords,render,uniqueMedicationNames,criteriaSources,renderCriteriaLibrary,namedPlanPolicies,statusChips,recordDetails,medicationSearchResult,policyLookupQuery,searchIndexedCriteria,cardClinicalGroups};'),ctx);
const {api}=ctx;api.state.data=data;
for(const id of ['criteriaSearch','criteriaCount','criteriaResults','criteriaLibrary','planStatus','planEvidence','evidenceList','loadingState','resultCount','effectiveDate','emptyState','resultGrid','showMore']) api.el[id]={value:'',innerHTML:'',textContent:'',hidden:false};
for(const planId of data.plans.map(p=>p.id)) {
 api.state.planId=planId;api.state.term='Mounjaro';
 const results=api.render();
 assert(results.some(g=>/mounjaro/i.test(g.label)),'Mounjaro missing in '+planId);
 if(planId==='uhc-community-az') {
  assert(results.some(g=>g.isStatewide)&&results.some(g=>!g.isStatewide),'Typed brand name silently selected one source variant');
  const report=api.medicationSearchResult(results.find(g=>g.isStatewide));
  assert.equal(report.pa,'required');assert.equal(report.coverage,'listed');assert(report.source&&report.products.every(p=>p.source),'Search tool lost grouped product clinical/source fields');
  const chosen=results.find(g=>g.isStatewide);
  api.state.selectedMedicationKey=chosen.key;api.state.term=chosen.label;
  assert.equal(api.render().length,1,'Explicit formulation selection did not narrow results');
  api.state.selectedMedicationKey=null;api.state.term='Mounjaro';api.render();
 }
 assert(results.every(g=>g.records.length&&g.records.every(r=>r.recordType==='formulary')),'Nonmedication result in '+planId);
 assert(!api.el.resultGrid.innerHTML.includes('Policy source indexed'));
 assert(api.el.criteriaResults.innerHTML.includes('gl-749236'),'Existing Mounjaro criteria inaccessible in '+planId);
 if(planId==='uhc-community-az') {
  assert(results.some(g=>api.cardClinicalGroups.get(g.key)?.policies.some(p=>p.id==='uhc-nov2026-policy-gl-720195')),'Wrong UHC GLP-1 source attached to Mounjaro');
  assert(api.el.resultGrid.innerHTML.includes('PA reference'),'PA source reference inaccessible');
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
api.state.term='Qvar';const qvarGroups=api.render();
assert(api.el.resultGrid.innerHTML.includes('Diagnosis of asthma'),'Preferred inhaler criteria lost when no PA flag is present');
assert(!/<span[^>]*>PA required<\/span>/.test(api.el.resultGrid.innerHTML),'Clinical guideline existence incorrectly asserted inhaler PA');
const qvarPolicies=qvarGroups.flatMap(g=>api.cardClinicalGroups.get(g.key)?.policies||[]);
assert(qvarPolicies.some(p=>p.id.startsWith('linked:banner-ufc:')),'Banner clinical source missing');
assert(!qvarPolicies.some(p=>p.planId==='uhc-community-az'),'Wrong plan clinical source attached');
assert(api.el.resultGrid.innerHTML.includes('PA reference'),'PA reference not accessible');
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
api.state.coverage='';api.state.planId='uhc-community-az';api.state.term='CONTOUR NEXT TEST STRIP IN VITRO';
const strips=api.render();
assert.equal(strips.length,1,'Specific test-strip search returned other device brands');
assert.equal(strips[0].brands.length,1,'Device card still groups incompatible meter brands');
assert(!api.el.resultGrid.innerHTML.includes('Accu-Chek'),'Contour search exposes another meter brand');
const epclusa=data.statewideDrugList.find(r=>r.name==='SOFOSBUVIR-VELPATASVIR TABLETS');
assert(api.statusChips(epclusa).includes('Authorized generic only'),'Authorized-generic source restriction hidden');
const entresto=data.statewideDrugList.find(r=>r.brand==='ENTRESTO');
assert(api.statusChips(entresto).includes('Generic only'),'Generic-only source scope hidden behind a reference brand');
const limits=api.recordDetails(epclusa);
assert(limits.includes('per Lifetime')&&!limits.includes('Lifetime days'),'Lifetime quantity limit mislabeled as days');
api.state.planId='az-complete-health';
assert.equal(api.searchIndexedCriteria('FLEXERIL',api.criteriaSources()).length,0,'Fixture unexpectedly gained a Flexeril heading');
const fallback=api.policyLookupQuery('CYCLOBENZAPRINE HCL TABLETS');
assert.equal(fallback,'cyclobenzaprine');
assert(api.searchIndexedCriteria(fallback,api.criteriaSources()).length>0,'Legacy-brand shortcut cannot find the existing generic source');
assert.equal(api.policyLookupQuery('METFORMIN-SITAGLIPTIN TABLETS'),'metformin sitagliptin','Combination components were lost in source discovery');
console.log('PASS: only medication results, source-only records excluded, medication-only name matching, plan-isolated criteria, structured policy lookup and conditional PA filtering');

// Run the complete search and card pipeline against the dated ACH records.
for (const [filter, notice] of [['preferred', 'ach-notice-13796'], ['pa_required', 'ach-notice-13791']]) {
  api.state.term = '';
  api.state.coverage = filter;
  const groups = api.render();
  assert(groups.every(group => group.records.length > 0), filter + ' returned empty medication cards');
  assert(groups.some(group => group.records.some(record => record.id === notice)), filter + ' lost a verified notice');
}
api.state.term = 'doxepin';
api.state.coverage = 'preferred';
assert(!api.render().some(group => group.label === 'doxepin HCl 10 MG Oral Capsule'));
api.state.coverage = '';
assert(api.render().some(group => group.label === 'doxepin HCl 10 MG Oral Capsule'));
api.state.planId = null;
assert.equal(api.render().length, 0);
assert.equal(api.el.resultGrid.innerHTML, '');
assert.match(api.el.loadingState.textContent, /Select an insurance plan/);
api.state.planId = 'banner-ufc';
api.state.term = 'Humalog';
assert(api.render().some(group => group.records.some(record => record.planId === 'banner-ufc')));
console.log('PASS: source-attributed filters, verified notice controls and pending plan selection');

api.state.planId='banner-ufc';
api.state.coverage='';
api.state.term='Adderall XR';
api.render();
assert(api.el.resultGrid.innerHTML.includes('50 per 90 days'), 'Banner Adderall XR quantity hidden by statewide value');
assert(api.el.resultGrid.innerHTML.includes('AHCCCS statewide reference'), 'Missing separate statewide source');
api.state.planId='uhc-community-az';
api.state.term='Zenzedi';
api.state.coverage='pa_conditional';
api.render();
assert(!api.el.resultGrid.innerHTML.includes('generic for ZENZEDI'), 'Nonmatching UHC option remained in filtered results');
