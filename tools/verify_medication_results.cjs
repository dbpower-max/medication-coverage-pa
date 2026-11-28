const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const load=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=load('_site/data.json.gz');
for(const file of Object.values(data.planDataFiles||{})) data.medications.push(...load('_site/'+file.split('?')[0].replace(/^\.\//,'')));
delete data.planDataFiles;
const script=fs.readFileSync('_site/app.js','utf8');
const hook="document.addEventListener('DOMContentLoaded', init);";
assert(script.includes(hook));
const ctx={document:{querySelectorAll:()=>[]},Intl,console};vm.createContext(ctx);
vm.runInContext(script.replace(hook,'globalThis.api={state,el,medicationGroupCard,recordsForPlan,planMedicationGroups,filteredRecords,render,uniqueMedicationNames,criteriaSources,renderCriteriaLibrary,namedPlanPolicies,statusChips,recordDetails,medicationSearchResult,policyLookupQuery,searchIndexedCriteria,cardClinicalGroups};'),ctx);
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
const smartNoticeUrl = 'https://www.azcompletehealth.com/newsroom/PU26135.html';
for (const plan of data.plans) {
 api.state.planId = plan.id;
 const groups = api.planMedicationGroups().filter(group => /symbicort|budesonide.*formoterol/i.test(group.label));
 assert(groups.length, plan.id);
 for (const group of groups) {
  const isAch = plan.id === 'az-complete-health';
  const card = api.medicationGroupCard(group);
  assert.equal(card.includes('SMART asthma notice covers the authorized generic and Teva generic'), isAch, group.label);
  if (group.records.some(row => row.id === 'banner-pcp-nov10-037')) {
   assert.equal((card.match(/6 per 90 days/g) || []).length, 1, group.label);
   assert(card.includes('The formulary does not specify a unit.'), group.label);
   assert(card.includes('Banner lists the authorized generic only as preferred.'), group.label);
   assert(card.includes('>Authorized generic only<'), group.label);
  }
  for (const row of group.records) {
   const sources = api.recordDetails(row);
   assert.equal(sources.includes(smartNoticeUrl), isAch, row.id);
   if (isAch && row.isStatewideReference) {
    assert(card.includes('>AHCCCS Statewide<') && card.includes('>Authorized generic only<'), row.id);
   } else if (isAch) {
    assert(['ach-json-1246288','ach-json-1246304'].includes(row.id), row.id);
    assert(sources.includes('row '+row.sourceRow), row.id);
    assert(card.includes('>Preferred<') && !card.includes('>Authorized generic only<'), row.id);
   }
  }
 }
}
api.state.planId='banner-ufc';
const pradaxaCapsules=api.planMedicationGroups().find(g=>g.records.some(r=>r.id==='banner-pcp-nov10-071'));
const capsuleListing=pradaxaCapsules.records.find(r=>r.id==='banner-pcp-nov10-071');
assert.equal(capsuleListing.pa,'not_specified');
assert.equal(capsuleListing.preferred,'preferred');
assert.equal(capsuleListing.qlAmount,'60');
assert.equal(capsuleListing.qlDays,'30');
const capsuleCard=api.medicationGroupCard(pradaxaCapsules);
assert(capsuleCard.includes('>Brand only<') && !capsuleCard.includes('>PA required<'));
for (const html of [capsuleCard,api.recordDetails(capsuleListing)]) {
 assert(!/12-1377|page=1377|Pradaxa Pellet Packs/.test(html));
}
assert(data.policies.some(p=>p.id==='banner-policy-12-1377' && p.name==='Pradaxa Pellet Packs'));
api.state.planId='uhc-community-az';
const anticoagGroups=api.planMedicationGroups();
for (const [suffix,dose,tablets,rxcui] of [
 ['ebc651f39c6b05eb','1.5',3,2749695],['8148b6eef83b111c','2',4,2749698],
]) {
 const group=anticoagGroups.find(g=>g.records.some(r=>r.id.endsWith(suffix)));
 const row=group.records.find(r=>r.id.endsWith(suffix));
 const card=api.medicationGroupCard(group);
 assert.equal(row.rawRestrictions,'Tier 2; QL');
 assert.equal(row.pa,'not_specified');
 assert.equal(row.preferred,'preferred');
 assert(card.includes(dose+' mg packet') && card.includes('0.5 mg tablets for oral suspension'));
 assert(card.includes('Each packet contains '+tablets+' tablets') && !card.includes('dosage form unverified'));
 const sources=api.recordDetails(row);
 assert(sources.includes('searchTerm='+rxcui) && sources.includes('e9481622-7cc6-418a-acb6-c5450daae9b0'));
 assert(sources.includes('UHC electronic formulary') && sources.includes('pdf#page=75'));
}
const plainEliquis=anticoagGroups.find(g=>g.records.some(r=>r.id.endsWith('7be205a1df723a04')));
assert(!api.medicationGroupCard(plainEliquis).includes('0.5 mg tablets for oral suspension'));
api.state.planId='banner-ufc';api.state.term='Inhaled Corticosteroids';
assert.equal(api.render().length,0,'Policy still appears as a medication');
assert(api.el.criteriaResults.innerHTML.includes('Inhaled Corticosteroids'),'Plan policy lost from criteria library');
assert.equal(api.el.criteriaLibrary.open,true,'Policy-only match is hidden in collapsed library');
api.state.planId='az-complete-health';
for (const [rxcui,packId,ordinaryId,sourceRow] of [
 ['1992428','formulary-9832','formulary-9831',1641],
 ['1549683','formulary-9835','formulary-9834',694],
]) {
 const achGroups=api.planMedicationGroups();
 const group=achGroups.find(g=>g.records.some(r=>r.id==='ach-json-'+rxcui));
 const row=group.records.find(r=>r.id==='ach-json-'+rxcui);
 assert.equal(group.statewideRecord.id,'az-complete-health:statewide:'+packId);
 assert.equal(row.sourceRow,sourceRow);
 assert.equal(row.baselineSource.values.drug_tier,'PREFERRED');
 assert.equal(row.baselineSource.values.quantity_limit,true);
 assert.equal(row.benefitSources.quantityLimited,'presumed_2022');
 assert.equal(row.qlAmount,'');
 assert.equal(row.qlDays,'');
 assert(row.sourceUpdates.some(u=>u.id==='ach-mandated-'+packId));
 assert(!row.sourceUpdates.some(u=>u.id==='ach-mandated-'+ordinaryId));
 const regular=achGroups.find(g=>g.statewideRecord?.id==='az-complete-health:statewide:'+ordinaryId);
 assert(!regular.records.some(r=>r.id===row.id));
 const sources=api.recordDetails(row);
 assert(sources.includes('row '+sourceRow) && sources.includes('TAB THER PACK') && sources.includes('pdf#page=7'));
}
api.state.planId='uhc-community-az';
const starterGroups=api.planMedicationGroups();
for (const [id,rxcui,contents] of [
 ['uhc-oct-complete-8b74d0de978fabcb',1992428,'74 tablets'],
 ['uhc-oct-complete-14a0d201b338bbcc',1549683,'42 tablets of 15 mg and 9 tablets of 20 mg'],
]) {
 const group=starterGroups.find(g=>g.records.some(row=>row.id===id));
 const row=group.records.find(r=>r.id===id);
 assert.equal(group.records.length,1,id);
 assert.equal(row.rawRestrictions,'Tier 2; QL',id);
 assert.equal(row.qlDays,'',id);
 const card=api.medicationGroupCard(group);
 assert(card.includes('oral tablets') && card.includes(contents),id);
 assert(!card.includes('dosage form unverified') && !card.includes('>PA required<'),id);
 const sources=api.recordDetails(row);
 assert(sources.includes('searchTerm='+rxcui) && sources.includes('UHC electronic formulary') && sources.includes('pdf#page=75'),id);
}
api.state.planId='banner-ufc';
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
assert(api.render().some(group => group.label === 'doxepin HCl 10 MG Oral Capsule'));
api.state.coverage = 'non_preferred';
assert(!api.render().some(group => group.label === 'doxepin HCl 10 MG Oral Capsule'));
api.state.coverage = '';
assert(api.render().some(group => group.label === 'doxepin HCl 10 MG Oral Capsule'));
// The cards and search tool must agree on the source of each displayed benefit.
for (const [term, id, expected] of [
  ['lispro', 'ach-json-242120', [['Covered', 'Preferred'], ['Plan formulary', 'QL: 1 mL per day']]],
  ['Tudorza', 'ach-json-1303107', [['Plan notice', 'Covered', 'Nonpreferred', 'PA required']]],
  ['clozapine', 'ach-json-1006801', [['Quantity limit'], ['Plan notice', 'Covered', 'Preferred'],
    ['AHCCCS Statewide', 'Conditional PA']]]
]) {
  api.state.term = term;
  const group = api.render().find(g => g.records.some(r => r.id === id));
  assert(group, id);
  const record = group.records.find(r => r.id === id);
  const report = api.medicationSearchResult(group).products.find(p => p.medication_id === id);
  assert.equal(report.benefit_sources.pa, record.benefitSources.pa);
  const card = api.medicationGroupCard({...group, records: [record], isStatewide: false});
  const chips = Array.from(card.matchAll(/<div class="chips"[^>]*>([\s\S]*?)<\/div>/g),
    line => Array.from(line[1].matchAll(/<span[^>]*>([^<]+)<\/span>/g), match => match[1]));
  assert.deepEqual(chips, expected, id);
  assert(!/presum|baseline/i.test(card.replace(/<[^>]+>/g, '')), id);
  assert(!/presum|baseline/i.test(api.recordDetails(record).replace(/<[^>]+>/g, '')), id);
  assert(api.recordDetails(record).includes(`row ${record.sourceRow}`), id);
}
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
assert(api.el.resultGrid.innerHTML.includes('>AHCCCS Statewide<'), 'Missing separate statewide source');
api.state.planId='uhc-community-az';
api.state.term='Zenzedi';
api.state.coverage='pa_conditional';
api.render();
assert(!api.el.resultGrid.innerHTML.includes('generic for ZENZEDI'), 'Nonmatching UHC option remained in filtered results');


for (const [plan, term, heading] of [
  ['uhc-community-az', 'Soolantra cream', /Ivermectin \(Soolantra\) 1% topical cream/i],
  ['uhc-community-az', 'Acuvail solution', /Acuvail.*Ophthalmic Solution/i],
  ['uhc-community-az', 'acitretin capsule', /acitretin.*Oral Capsule/i],
  ['uhc-community-az', 'acarbose tablet', /acarbose.*tablet/i],
  ['banner-ufc', 'acarbose', /Acarbose Tablets/i],
  ['az-complete-health', 'acarbose', /acarbose 25 MG Oral Tablet/i]
]) {
  Object.assign(api.state, {planId:plan, term, selectedMedicationKey:null, category:'', subcategory:'', coverage:''});
  const results = api.render();
  const titles = Array.from(api.el.resultGrid.innerHTML.matchAll(/<h3>(.*?)<\/h3>/g), match => match[1]);
  assert(titles.some(title => heading.test(title)), plan + ' ' + term);
  if (term === 'Soolantra cream') {
    assert.equal(results.length, 1);
    const card = api.el.resultGrid.innerHTML;
    for (const text of ['10 mg/g', 'exact presentation are unverified', 'PA required', 'Quantity limit']) assert(card.includes(text));
    const policies = api.cardClinicalGroups.get(results[0].key).policies;
    assert(policies.every(p => !['GL-99431','GL-140680'].includes(p.policyCode)));
  }
}
Object.assign(api.state, {planId:'uhc-community-az', term:'Uceris'});
api.render();
assert.match(api.el.resultGrid.innerHTML, /<h3>Uceris \(Budesonide\) Extended-Release Oral Tablet or Rectal Foam \(Payer Form Unspecified\)<\/h3>/i);
assert.match(api.el.resultGrid.innerHTML, /Exact UHC product-specific initial\/renewal criteria/);

api.state.term = 'Freestyle Libre 3 Reader';
api.render();
assert.match(api.el.resultGrid.innerHTML, /<h3>Freestyle Libre 3 Reader<\/h3>/i);
