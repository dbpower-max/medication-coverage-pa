const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const read=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=read('_site/data.json.gz');
for(const file of Object.values(data.planDataFiles||{})) data.medications.push(...read('_site/'+file.split('?')[0].replace(/^\.\//,'')));
delete data.planDataFiles;
const source=fs.readFileSync('_site/app.js','utf8');
const ctx={Intl,console,document:{addEventListener:()=>{}},fetch:async url=>({ok:true,json:async()=>read('_site/'+url.split('?')[0].replace(/^\.\//,'')),text:async()=>fs.readFileSync('_site/'+url.split('?')[0].replace(/^\.\//,''),'utf8')})};
vm.createContext(ctx);vm.runInContext(source.replace("document.addEventListener('DOMContentLoaded', init);",'globalThis.api={state,planMedicationGroups,medicationGroupCard,populateCardClinical,matchingClinicalBranches,cardBranchMarkup,cardClinicalGroups,clinicalGuidanceFor,recordDetails};'),ctx);
const api=ctx.api;api.state.data=data;
function targetFor(group){const target={innerHTML:'',isConnected:true};return {target,details:{open:true,dataset:{cardClinical:group.key||group.label},querySelector:selector=>selector==='.card-pa-references'?{innerHTML:''}:target}};}
(async()=>{
// Label-backed form and device remain separate from the listing-specific payer flags.
for (const [plan, rows] of [
 ['az-complete-health', [['ach-json-2535243','Prefilled Syringe','2535243'],['ach-notice-13882','Autoinjector','2535249'],['ach-notice-13883','Syringe','2535243']]],
 ['uhc-community-az', [['uhc-oct-complete-229568f7f286fb5b','One Pack','2180671'],['uhc-oct-complete-1c725dc535b842a6','Two Pack','2180671'],
   ['uhc-oct-complete-5fcb0ddd3560f776','Autoinjector (1-Pack)'],['uhc-oct-complete-7caf82e6ee33bfff','Autoinjector (2-Pack)'],
   ['uhc-oct-complete-a5fa4856ca09e8de','Prefilled Syringe'],['uhc-oct-complete-5eca184f4914d610','Vial and Syringe']]]
]) {
 api.state.planId=plan;
 for (const [id,device,rxcui] of rows) {
   const group=api.planMedicationGroups().find(g=>g.records.some(r=>r.id===id));
   const row=group.records.find(r=>r.id===id);
   const html=api.medicationGroupCard(group);
   const heading=html.match(/<h3>(.*?)<\/h3>/)[1];
   assert(heading.includes(device) && /solution|nasal powder/i.test(heading) && !heading.includes('unverified'),id);
   const sources=api.recordDetails(row);
   if (rxcui) assert(sources.includes('searchTerm='+rxcui), id);
   else assert(html.includes('UHC does not specify eligible strengths') && sources.includes('92385737-dbad-98c5-e053-2995a90a2805'), id);
 }
}

api.state.planId='banner-ufc';
const bannerPremixGroups=api.planMedicationGroups();
for (const [id,stateId,brand,pen] of [
  ['banner-oct26-029','formulary-9983','Humulin 70/30',false],
  ['banner-pcp-nov10-006','formulary-9984','Humulin 70/30 KwikPen',true],
  ['banner-pcp-nov10-008','formulary-9990','Novolin 70/30',false]
]) {
  const group=bannerPremixGroups.find(g=>g.records.some(r=>r.id===id));
  assert.deepEqual(Array.from(group.records,r=>r.id).sort(),[id,'banner-ufc:statewide:'+stateId].sort(),id);
  const row=group.records.find(r=>r.id===id);
  const markup=api.medicationGroupCard(group);
  assert(group.label.startsWith(brand+' (human NPH/regular insulin) 100 units/mL'),id);
  assert.equal(group.label.includes('prefilled pen'),pen,id);
  assert.equal(markup.includes('1-unit dose increments'),pen,id);
  assert.equal(markup.includes('without a device or package'),!pen,id);
  assert(!group.label.includes('vial')&&!markup.includes('>PA required<'),id);
  assert.equal(row.pa,'not_specified',id);
  assert.equal(row.step,'not_specified',id);
  assert(!row.qlDays&&!row.qlAmount,id);
  assert(markup.includes('>Preferred<')&&markup.includes('>Brand only<'),id);
  assert.equal(api.recordDetails(row).includes('searchTerm=847189'),pen,id);
}
for (const id of ['banner-pcp-nov10-012','banner-pcp-nov10-013']) {
  const group=bannerPremixGroups.find(g=>g.records.some(r=>r.id===id));
  assert(group.label.includes('Aspart')&&!group.label.includes('human NPH/regular insulin'),id);
  assert.equal(group.label.includes('FlexPen'),id==='banner-pcp-nov10-013',id);
}
for(const plan of data.plans){
 api.state.planId=plan.id;
 const groups=api.planMedicationGroups();
 const acamprosate=groups.find(group=>group.statewideRecord?.id.endsWith(':statewide:formulary-9707'));
 assert(acamprosate, 'Missing statewide acamprosate in '+plan.id);
 const acamprosateCard=api.medicationGroupCard(acamprosate).split('<div class="card-source-access">')[0];
 assert(acamprosateCard.includes(plan.id==='banner-ufc' ? 'Banner formulary' : '>AHCCCS Statewide<'),
   'Statewide badges lack a visible source qualifier in '+plan.id);
 const xigduo=groups.find(g=>g.brands.includes('XIGDUO XR')&&g.isStatewide);
 assert(xigduo,'Xigduo missing '+plan.id);
 for (const product of groups.filter(g=>(g.records||[]).some(r=>/^Xigduo XR/.test(r.standardName||'')))) {
  api.medicationGroupCard(product);
  assert(api.cardClinicalGroups.get(product.key).policies.some(p=>p.structuredCriteriaUrl),'Official RxTerms name did not bridge legacy Xigduo brand');
  const exact=targetFor(product);await api.populateCardClinical(exact.details);
  assert(exact.target.innerHTML.includes('metformin'),'Strength-specific Xigduo criteria missing');
 }
 const markup=api.medicationGroupCard(xigduo);
 for(const banned of ['STEP THROUGH METFORMIN','AHCCCS reference policy','Selected-plan products','Read full guideline text','data-criteria-query','View clinical criteria','guideline-verbatim']) assert(!markup.includes(banned),banned+' leaked onto card');
 const {target,details}=targetFor(xigduo);await api.populateCardClinical(details);
 assert.equal(details.dataset.loaded,'true','Criteria failed to load');
 assert(/(?:1500\s*mg|500\s*mg) daily for 90 days/.test(target.innerHTML.replace(/\s+/g,' ')),'Source metformin duration/dose lost');
 assert(target.innerHTML.includes('10 years')&&target.innerHTML.includes('NYHA class II-IV')&&target.innerHTML.includes('chronic kidney disease'),'Clinical pathways lost');
 assert(target.innerHTML.includes('OR')&&target.innerHTML.includes('AND'),'Source Boolean connectors lost');
 assert.equal((target.innerHTML.match(/More clinical criteria/g)||[]).length,1,'Generic-only additions need one nonredundant expansion');
 for(const banned of ['Farxiga','Jardiance','Synjardy','Invokamet','Inpefa','PA Team Note','Product Name:','guideline-verbatim'])assert(!target.innerHTML.includes(banned),'Unrelated/admin text leaked: '+banned);
 const old=target.innerHTML;await api.populateCardClinical(details);assert.equal(target.innerHTML,old,'Reopening duplicated criteria');
 const mounjaro=groups.find(g=>g.brands.includes('MOUNJARO')&&api.clinicalGuidanceFor(g));
 assert(mounjaro);const guideMarkup=api.medicationGroupCard(mounjaro);
 assert(guideMarkup.includes('90 days')&&guideMarkup.includes('A1c'),'Existing reviewed criteria disappeared');
 assert(!guideMarkup.includes('Documentation suggestions')&&!guideMarkup.includes('Clinician approval pending'),'Technical review notices leaked');
 const more=targetFor(mounjaro);await api.populateCardClinical(more.details);
 assert(!more.target.innerHTML.includes('More clinical criteria'),'Redundant second lookup remains');
 assert(!more.target.innerHTML.includes('View clinical criteria'),'Whole-policy reader remains');
}
// DEC-06/07/19/20: ACH exact baseline flags and label presentation.
api.state.planId='az-complete-health';
const achOudGroups=api.planMedicationGroups();
for(const [rx,matched] of [
 ['285018',true],['847232',true],['106892',true],['847189',true],['311027',true],['311033',true],
 ['311040',true],['1653202',true],['242120',true],['1652639',true],['1926331',true],['847252',false],
 ['351926',false],['1653198',false],['1653204',false],['977842',false],['977840',false]
]){
 const g=achOudGroups.find(g=>g.records.some(r=>r.id==='ach-json-'+rx));
 const r=g.records.find(r=>r.id==='ach-json-'+rx),card=api.medicationGroupCard(g),src=api.recordDetails(r);
 assert.equal(card.includes('QL: 1 mL per day'),matched,rx);
 assert.equal(r.baselineSource.values.quantity_limit,true);assert.equal(r.baselineSource.values.prior_authorization,false);
 assert.equal(src.includes('Feb%202023.pdf#page='),matched);
 if (['242120','1652639','1926331','847252'].includes(rx)) assert(src.includes('searchTerm='+rx+'"'), rx);
 if(matched) assert.equal(r.benefitSources.quantityLimited,'selected_plan');
}
for(const [rx,row,identity,pa] of [
 ['1670016',886,'100 units/mL prefilled pen',false],['1670023',887,'200 units/mL prefilled pen',false],
 ['2107522',1908,'100 units/mL multidose vial',false],['1731317',966,'500 units/mL prefilled pen',true]
]){
 const id='ach-json-'+rx;
 const group=achOudGroups.find(g=>g.records.some(r=>r.id===id)),record=group.records[0];
 assert.equal(group.records.length,1);assert.equal(record.baselineSource.row,row);
 const card=api.medicationGroupCard(group),source=api.recordDetails(record);
 assert(card.includes(identity)&&card.includes('>Preferred<')&&card.includes('>Quantity limit<'));
 assert.equal(card.includes('>PA required<'),pa);assert(source.includes('searchTerm='+rx)&&source.includes('row '+row));
 assert.equal(source.includes('Feb%202023.pdf#page=26'),pa);
 assert.equal(card.includes('Never withdraw insulin'),pa);
}
for(const suffix of ['9977','9978']){
 const state=achOudGroups.find(g=>g.records.some(r=>r.id==='az-complete-health:statewide:formulary-'+suffix));
 assert(state.records.every(r=>r.isStatewideReference),'Tresiba direct record under statewide heading');
}
for(const [id,sourceRow] of [['ach-json-848333',3851],['ach-json-848343',3852]]){
 const group=achOudGroups.find(g=>g.records.some(r=>r.id===id));
 const record=group.records.find(r=>r.id===id);
 assert.equal(record.baselineSource.row,sourceRow);
 assert.equal(record.baselineSource.values.prior_authorization,true);
 assert.equal(record.baselineSource.values.drug_tier,'PREFERRED');
 const card=api.medicationGroupCard(group);
 assert(card.includes('>Covered<')&&card.includes('>Preferred<')&&card.includes('>PA required<'),id+' plan benefits');
 assert(card.includes('Arizona Complete Health’s product-specific approval criteria are unverified.'),id);
 assert(card.includes('AHCCCS Statewide · Fee-for-service reference')&&card.includes('ahcccs-ffs-pa-criteria-2026-11-01.pdf#page=602'),id+' scope and page');
 assert(!card.includes('Either menopausal indication'),id+' statewide summary on plan listing');
 const expanded=targetFor(group);await api.populateCardClinical(expanded.details);
 assert(expanded.target.innerHTML.includes('AHCCCS Statewide · Fee-for-service criteria'),id+' labeled statewide disclosure');
 assert(expanded.target.innerHTML.includes('vasomotor symptoms')&&expanded.target.innerHTML.includes('vulvar and vaginal atrophy'),id+' exact Femring criteria');
 assert(!expanded.target.innerHTML.includes('kraurosis vulvae'),id+' Premarin branch');
 assert(api.recordDetails(record).includes('row '+sourceRow),id+' 2022 source row');
}

for(const [id,dose] of [['ach-json-1996189','100 mg/0.5 mL'],['ach-json-1996193','300 mg/1.5 mL']]){
 const g=achOudGroups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
 const r=g.records.find(r=>r.id===id);
 assert.equal(r.pa,'required',id+' preserved explicit baseline PA');
 assert.equal(r.preferred,'preferred',id);assert(!r.quantityLimited,id);
 const card=api.medicationGroupCard(g);
 assert(card.includes(dose)&&card.includes('Extended-Release Subcutaneous Injection'),id+' presentation');
 assert(card.includes('Exact plan initial/renewal criteria are unverified'),id+' criteria scope');
 assert(card.includes('PA required'),id+' displayed PA');
 assert(card.includes('AHCCCS Statewide · Fee-for-service reference'),id+' unlabeled fee-for-service link');
 const expanded=targetFor(g);
 await api.populateCardClinical(expanded.details);
 const reference=expanded.target.innerHTML.match(/<details class="result-disclosure statewide-criteria-reference"><summary>AHCCCS Statewide · Fee-for-service criteria<\/summary>[\s\S]*?<\/details>/);
 assert(reference,id+' missing separately labeled statewide criteria');
 assert(reference[0].includes('Initial Authorization') && reference[0].includes('Reauthorization'),id+' missing statewide stages');
 const statewidePages=Array.from(reference[0].matchAll(/ahcccs-ffs-pa-criteria[^"#]*#page=(\d+)/g),match=>Number(match[1]));
 assert.deepEqual(statewidePages,[1696,1698],id+' statewide links must land on the printed stage and its criteria');
 assert(!expanded.target.innerHTML.replace(reference[0],'').includes('Treatment stage:'),id+' statewide stages displayed as plan criteria');
 assert(!r.achProviderRule,id+' mono rule must not transfer');
}
for(const id of ['ach-json-351266','ach-json-351267','ach-json-351264','ach-json-351265']){
 const g=achOudGroups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
 const r=g.records.find(r=>r.id===id);assert(r.quantityLimited,id+' preserved QL');
 const mono=['ach-json-351264','ach-json-351265'].includes(id);
 assert.equal(Boolean(r.achProviderRule),mono,id+' rule scope');
 if(mono){assert(api.medicationGroupCard(g).includes('except for pregnancy or nursing'),id);assert.equal(r.achProviderRule.effectiveDate,null);}
 else assert(!['required','conditional'].includes(r.pa),id+' no mono PA transfer');
}
api.state.planId='uhc-community-az';
const patchGroup=api.planMedicationGroups().find(g=>g.records.some(r=>r.id==='uhc-oct-complete-907ff55568d6ecfb'));
assert.deepEqual(Array.from(patchGroup.records, r=>r.id).sort(), ['uhc-oct-complete-1f6816a7379d66cd','uhc-oct-complete-907ff55568d6ecfb']);
const patchCard=api.medicationGroupCard(patchGroup);
for(const expected of ['Transdermal Patches','Generic buprenorphine patches','Brand Butrans patches','Tier 1','Tier 2','PA required','Quantity limit']) assert(patchCard.includes(expected),expected);
assert(!patchCard.includes('Conditional PA') && !patchCard.includes('unless the member is pregnant'));
const patchDetails=targetFor(patchGroup);
await api.populateCardClinical(patchDetails.details);
assert(patchDetails.target.innerHTML.includes('generic buprenorphine patches'));
assert(!patchDetails.target.innerHTML.includes('unless the member is pregnant'));
// Banner label evidence must not collapse source rows or imply a verified package.
api.state.planId='banner-ufc';
const bannerGroups=api.planMedicationGroups();
const bannerCases=[
 ['banner-full-150d0a331d6c46df','Alpha1-Proteinase Inhibitor (Prolastin-C / Glassia; IV Form Unresolved)','Exact covered brand, formulation and package are unverified','https://www.fda.gov/vaccines-blood-biologics/approved-blood-products/alpha1-proteinase-inhibitor'],
 ['banner-full-c50d5a831e1c6a83','Aralast NP (Alpha1-Proteinase Inhibitor) IV Powder for Solution','require reconstitution','https://www.fda.gov/media/69965/download?attachment='],
 ['banner-full-79924464664746a2','Adefovir Dipivoxil Oral Tablets (Hepsera Reference)','does not specify strength','https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=08e07fae-3191-b6a3-c894-d3a8cc53923f']
];
for(const [id,label,caveat,url] of bannerCases){
 const g=bannerGroups.find(x=>x.records.some(r=>r.id===id));
 assert(g,id+' missing');
 assert.equal(g.label,label);
 assert.equal(g.records.length,1,id+' merged with another presentation or reference');
 assert.equal(g.records[0].planId,'banner-ufc');
 assert.equal(g.records[0].pa,'required');
 const card=api.medicationGroupCard(g);
 assert(card.includes(caveat)&&card.includes(url)&&card.includes('>PA required<'),id+' lost label scope or PA');
}
console.log('PASS: three Banner source rows preserve distinct FDA presentations, label links, unresolved payer package and explicit PA.');

// Exact-source card safety: initiation-only product and adult/pediatric CGRP distinction.
const scopedCases=[
 ['banner-ufc','banner-full-25a305f34bbe1d14','Aristada Initio (Aripiprazole Lauroxil) IM Initiation Injection','not for repeated maintenance dosing','b18fdfd9-31cd-4a2f-9f1c-ebc70d7a9403','conditional'],
 ['banner-ufc','banner-full-753b957d55158ac0','Abilify Asimtufii (Aripiprazole) Extended-Release IM Suspension','distinct from monthly Abilify Maintena','da4c07fd-1130-4341-bb44-63acfa4162be','conditional'],
 ['uhc-community-az','uhc-oct-complete-8989a933ae7b4319','Aimovig (Erenumab-aooe) Subcutaneous Injection','not Aimovig','b998ed05-94b0-47fd-b28f-cddd1e128fd8','required'],
 ['uhc-community-az','uhc-oct-complete-f4bec275aa84db05','Ajovy (Fremanezumab-vfrm) Subcutaneous Injection','episodic migraine only','98e344ea-5916-4947-b6f2-4a76ccc04b6b','required']
];
for(const [plan,id,label,note,sourceId,pa] of scopedCases){
 api.state.planId=plan;
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));
 assert(g,id+' missing');assert.equal(g.label,label);assert.equal(g.records.length,1);
 assert.equal(g.records[0].planId,plan);assert.equal(g.records[0].pa,pa);assert.equal(g.records[0].preferred,'preferred');
 const card=api.medicationGroupCard(g);
 assert(card.includes(note)&&card.includes(sourceId),id+' lost scope or label evidence');
}
console.log('PASS: four exact source cards preserve original PA/preference and noninterchangeability or indication scope.');

// Newly located named Banner policy links retain source-specific benefit flags.
api.state.planId='banner-ufc';
for(const [id,label,pid,page,preference,note] of [
 ['banner-full-df471ac18a4edcdf','Ambrisentan Tablets (Letairis Reference)','banner-policy-12-1422',1422,'preferred','brand Letairis as nonpreferred'],
 ['banner-full-42e11b3c0513cedb','Anastrozole Tablets (Arimidex Reference)','banner-policy-12-259',259,'not_specified','separate NCCN initial and renewal branches']
]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));
 assert(g,id+' missing');assert.equal(g.label,label);assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,'required');assert.equal(r.preferred,preference);
 assert(r.policySources.some(p=>p.policyId===pid&&p.firstPage===page),'Named Banner source link missing');
 const markup=api.medicationGroupCard(g);
 assert(markup.includes(note),'Source scope caveat missing');
 assert(api.cardClinicalGroups.get(g.key).policies.some(p=>p.id===pid&&p.planId==='banner-ufc'&&p.sourcePage===page),'Exact-plan policy missing from card');
}
console.log('PASS: two named Banner source links preserve generic versus brand scope, PA and original preference.');

// Fasenra devices must not obscure the syringe-only pediatric dose.
api.state.planId='banner-ufc';
for(const [id,label,note] of [["banner-full-f280cb398b11247e","Fasenra Pen (Benralizumab) Subcutaneous Autoinjector","FDA label: 30 mg/mL pen only. The 10 mg pediatric asthma dose requires the prefilled syringe"],["banner-full-bc2f140b456dcb21","Fasenra (Benralizumab) Subcutaneous Prefilled Syringe","FDA label: 10 mg/0.5 mL or 30 mg/mL syringes"]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));
 assert(g,id+' missing');assert.equal(g.label,label);assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
 const markup=api.medicationGroupCard(g);
 assert(markup.includes(note)&&markup.includes('Exact covered strength/package remains unverified')&&markup.includes('da6aca1a-19ed-44a4-abb7-696c7d58b784'),id+' lost device scope');
 assert(api.cardClinicalGroups.get(g.key).policies.some(p=>p.planId==='banner-ufc'&&p.sourcePage===647),id+' lost exact policy');
}
console.log('PASS: Fasenra pen and syringe remain separate, with unchanged PA/preference and named Banner policy.');

// Exact named Banner specialty policy links; do not transfer preference or formulation.
api.state.planId='banner-ufc';
for(const [id,label,pid,page,preference,note] of [["banner-full-3896cdde40e8e8a1","Mvasi (Bevacizumab-awwb) Injection","banner-policy-12-237",237,"not_specified","The named October 2025 guideline identifies Mvasi and Zirabev as preferred. The October 2026 formulary does not specify preference for this row. Exact package eligibility is unverified."],["banner-full-6c72cfb332a399ef","Zirabev (Bevacizumab-bvzr) Injection","banner-policy-12-237",237,"not_specified","The named October 2025 guideline identifies Mvasi and Zirabev as preferred. The October 2026 formulary does not specify preference for this row. Exact package eligibility is unverified."],["banner-full-96013cd1d8204447","Bexarotene Capsules (Banner Formulary)","banner-policy-12-1754",1754,"not_specified","The named guideline includes both capsules and Targretin gel. This formulary row is capsules only. Separate CTCL and NCCN initial and renewal criteria apply; gel coverage is not established by this row."],["banner-full-04d6c166dbdc7a8a","Bosentan Tablets for Oral Suspension (Tracleer Reference)","banner-policy-12-1422",1422,"preferred","The September 2026 guideline identifies generic tablets for oral suspension as preferred, but brand Tracleer and generic conventional tablets as nonpreferred. Exact brand/package eligibility is unverified."]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));
 assert(g,id+' missing');assert.equal(g.label,label);assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,'required');assert.equal(r.preferred,preference);
 assert(r.policySources.some(p=>p.policyId===pid&&p.firstPage===page),id+' named policy source missing');
 const markup=api.medicationGroupCard(g);
 assert(markup.includes(note),id+' scope caveat missing');
 assert(api.cardClinicalGroups.get(g.key).policies.some(p=>p.id===pid&&p.planId==='banner-ufc'&&p.sourcePage===page),id+' exact policy missing');
}
console.log('PASS: four named specialty policy bindings retain original payer flags and formulation scope.');

// Banner's combined C1 inhibitor row must retain its scope; weekly/monthly Brixadi is not a single interchangeable dose.
api.state.planId='banner-ufc';
for(const [id,label,preference,caveat,source] of [
 ['banner-full-ea0529db441446f6','Berinert (C1 Esterase Inhibitor) IV Powder for Solution (Banner Formulary)','preferred','acute hereditary angioedema attacks','approved-blood-products/berinert'],
 ['banner-full-81af49ca953b804f','Cinryze / Haegarda (C1 Esterase Inhibitor) Reconstituted Injection (Banner Combined Listing)','not_specified','Cinryze intravenous; Haegarda subcutaneous','approved-blood-products/haegarda'],
 ['banner-full-63b29ba46f628277','Brixadi (Buprenorphine) Subcutaneous Extended-Release Prefilled Syringe (Banner Formulary)','preferred','weekly and monthly formulations','5d8a8fd0-8619-422a-a664-d1d2e8970f48']
]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));
 assert(g,id+' missing');assert.equal(g.label,label);assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,'required');assert.equal(r.preferred,preference);
 const card=api.medicationGroupCard(g);assert(card.includes(caveat)&&card.includes(source),id+' lost label evidence');
 if(id==='banner-full-81af49ca953b804f')assert(card.includes('individual product/package eligibility'),id+' lost combined-listing caveat');
 if(id==='banner-full-63b29ba46f628277')assert(card.includes('does not specify covered schedule or strength'),id+' lost schedule hold');
}
console.log('PASS: Banner C1 inhibitor acute versus prophylactic routes and Brixadi schedule caveats preserve exact source rows and payer flags.');

// Explicit same-plan named policy bindings; retain exact payer flags.
api.state.planId='banner-ufc';
for(const [id,pid,page,pa,pref] of [
 ['banner-full-ea0529db441446f6','banner-policy-12-811',811,'required','preferred'],
 ['banner-full-81af49ca953b804f','banner-policy-12-811',811,'required','not_specified'],
 ['banner-full-f1d24c36af2451fa','banner-policy-12-105',105,'required','not_specified'],
 ['banner-full-b2b56363cbca0ab9','banner-policy-12-105',105,'required','not_specified'],
 ['banner-full-ffeacef3b187fde3','banner-policy-12-156',156,'conditional','not_specified'],
 ['banner-full-289217947e14a99e','banner-policy-12-156',156,'conditional','not_specified'],
 ['banner-full-08918817a94bbfa0','banner-policy-12-156',156,'conditional','not_specified']
]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));
 assert(g,id+' missing');const r=g.records.find(r=>r.id===id);
 assert.equal(r.pa,pa);assert.equal(r.preferred,pref);
 assert(r.policySources.some(p=>p.policyId===pid&&p.firstPage===page),id+' missing named link');
 const markup=api.medicationGroupCard(g);
 assert(api.cardClinicalGroups.get(g.key).policies.some(p=>p.id===pid&&p.planId==='banner-ufc'&&p.sourcePage===page),id+' card missing exact-plan policy');
 if(id==='banner-full-81af49ca953b804f')assert(markup.includes('Cinryze only, not Haegarda'),'Acute off-label branch scope lost');
}
console.log('PASS: seven exact Banner named policy links with unchanged PA/preference and scoped HAE distinction.');

// Same-plan source links, original flags and visible option-specific policy scope.
api.state.planId='banner-ufc';
for(const [id,pid,page,pref,scope] of [["banner-full-1ecc15f32d5c5aa0","banner-policy-12-1193",1193,"not_specified","MS guideline: generic dalfampridine is preferred; brand Ampyra is nonpreferred. Separate initial and renewal branches. The formulary row does not specify preference; exact brand/package eligibility is unverified."],["banner-full-c3c6e41b892ea1d1","banner-policy-12-681",681,"not_specified","Bildyos osteoporosis branch; preferred in the guideline, preference unspecified in the formulary. Separate initial and renewal criteria. The shared renewal text refers to cumulative PTH analog use, not a verified Bildyos lifetime cap."],["banner-full-b93efaf3c38dcf21","banner-policy-12-183",183,"not_specified","Austedo XR tablet: separate tardive dyskinesia and Huntington chorea initial and renewal criteria. One active strength PA; titration-kit eligibility is not established. Preserve the XR tablet quantity limit."],["banner-full-13ebf33d7a321470","banner-policy-12-1193",1193,"not_specified","Generic dimethyl fumarate capsules are preferred in the guideline, branded Tecfidera capsules and starter packs are nonpreferred. Formulary preference and exact brand/package eligibility are unverified."],["banner-full-c144470bcd338e8c","banner-policy-12-811",811,"preferred","Preferred acute HAE branch: age 12 or older; nonpreferred-agent step requirements do not apply. Exact package eligibility is unverified."],["banner-full-30fc49366041be95","banner-policy-12-601",601,"not_specified","Generic tablet for oral suspension preferred in the guideline; brand Afinitor Disperz nonpreferred. Preferred product approval is NDC-specific. Exact package eligibility is unverified; do not transfer transplant or conventional-tablet coverage."]]){
 const g=api.planMedicationGroups().find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,'required');assert.equal(r.preferred,pref);
 assert(r.policySources.some(p=>p.policyId===pid&&p.firstPage===page&&p.scope===scope),id+' missing named policy binding');
 api.medicationGroupCard(g);assert(api.cardClinicalGroups.get(g.key).policies.some(p=>p.id===pid&&p.planId==='banner-ufc'),id+' exact policy missing from card');
 assert(api.recordDetails(r).includes(scope),id+' missing policy scope in Sources');
}
console.log('PASS: six newly verified Banner named policy links and visible source scope.');

// Xalkori oral pellets and capsules have distinct handling and strengths.
api.state.planId='banner-ufc';
for(const [id,label,caveat] of [["banner-full-300d0c135e0cb20c","Xalkori (Crizotinib) Oral Pellets (Banner Formulary)","Do not swallow the shell"],["banner-full-98c661a1f951a1e3","Xalkori (Crizotinib) Oral Capsules (Banner Formulary)","Swallow whole"]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));
 assert(g,id+' missing');assert.equal(g.label,label);assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const markup=api.medicationGroupCard(g);assert(markup.includes(caveat)&&markup.includes('2a51b0de-47d6-455e-a94c-d2c737b04ff7')&&markup.includes('exact covered strengths and packages are unverified'),id+' missing label evidence or payer hold');
}
console.log('PASS: Banner Xalkori capsules and pellets preserve distinct handling, source rows and payer flags.');

// AUT-01: verify exact source-linked cards and preserve conditional PA flags.
api.state.planId='banner-ufc';
for(const [id,pid,page,pa,pref,scope] of [["banner-full-dc42f2a6c586a16a","banner-policy-12-357",357,"required","preferred","Nivestym is a named preferred product in the shared CSF policy. The exact syringe and indication must be checked separately; the shared policy includes off-label uses and does not establish interchangeability or package eligibility."],["banner-full-5446ad5479340eeb","banner-policy-12-357",357,"required","preferred","Nivestym is a named preferred product in the shared CSF policy. The exact solution presentation and indication must be checked separately; the shared policy includes off-label uses and does not establish interchangeability or package eligibility."],["banner-full-73d3701a5467c050","banner-policy-12-357",357,"required","preferred","Releuko is a named preferred product in the shared CSF policy. The formulary does not specify its presentation; exact product, indication and package must be verified. Shared criteria include off-label uses."],["banner-full-f0147593c0e3df11","banner-policy-12-305",305,"required","preferred","Migraine prevention: separate initial and renewal branches; pediatric eligibility applies only to episodic migraine for Ajovy ages 6–17 and weight at least 45 kg. Verify age-specific device labeling; the policy does not establish exact package eligibility."],["banner-full-1216731a2ac10ef5","banner-policy-12-305",305,"required","preferred","Migraine prevention: separate initial and renewal branches; pediatric eligibility applies only to episodic migraine for Ajovy ages 6–17 and weight at least 45 kg. Verify age-specific device labeling; the policy does not establish exact package eligibility."],["banner-full-146f9141864dbe2a","banner-policy-12-1321",1321,"required","not_specified","Named oral oncology cancer branch: NCCN category 1, 2A or 2B. Do not apply the separate imatinib step requirement. No separately stated renewal stage; exact package eligibility unverified."],["banner-full-dfa5cdbe92a21695","banner-policy-12-798",798,"conditional","preferred","Preferred one-time lifetime course without PA; retreatment requires PA. Preserve printed packet-specific 280 per lifetime limit; do not transfer tablet quantities. Policy names Mavyret, not the exact packet package."],["banner-full-d4b82dd7596688b0","banner-policy-12-798",798,"conditional","preferred","Preferred one-time lifetime course without PA; retreatment requires PA. Preserve printed tablet-specific 168 per lifetime limit; do not transfer packet quantities. Policy names Mavyret, not the exact tablet package."],["banner-full-f0dac8422def3d7b","banner-policy-12-1896",1896,"required","not_specified","Urea cycle disorder initial and renewal branches; generic glycerol phenylbutyrate alone has the additional brand Ravicti failure/intolerance requirement. October brand-only flag is retained; no separate generic eligibility inferred."]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,pa);assert.equal(r.preferred,pref);
 assert(r.policySources.some(p=>p.policyId===pid&&p.firstPage===page&&p.scope===scope),id+' missing exact named link');
 api.medicationGroupCard(g);assert(api.cardClinicalGroups.get(g.key).policies.some(p=>p.id===pid&&p.planId==='banner-ufc'),id+' exact policy missing from card');
 assert(api.recordDetails(r).includes(scope),id+' missing visible source caveat');
}
console.log('PASS: nine Banner policy links preserve original preference, PA and scoped product caveats.');

// AUT-01 2026-11-24: source-linked Banner prescribing rows, no inferred coverage.
api.state.planId='banner-ufc';
for(const [id,pid,page,pa,pref,scope] of [["banner-full-015b1506addec038","banner-policy-12-351",351,"required","not_specified","Named famciclovir tablet branch, 12-month approval; separate renewal stage not specified. Do not infer brand eligibility."],["banner-full-b1b2bf86bd6d4857","banner-policy-12-1099",1099,"required","preferred","Preferred transdermal patch rates: 12, 25, 50, 75 and 100 mcg/hr; distinct cancer/hospice and noncancer initial/renewal pathways and separate DUR, MME and quantity-review branches. This is not the transmucosal fentanyl policy."],["banner-full-e6a1b62352bfbc70","banner-policy-12-351",351,"required","not_specified","Named Foscavir injection criteria; CMV and compendium-supported covered indications; 12-month approval, separate renewal stage not specified. Original payer spelling retained."],["banner-full-d17bd539fa8f578f","banner-policy-12-305",305,"required","preferred","120 mg/mL prefilled pen for adult migraine prevention; 6-month initial and 12-month renewal. The pediatric branch is Ajovy only; the 100 mg/mL cluster headache branch is syringe only. Exact package eligibility unverified."],["banner-full-f4e7ff20751921ce","banner-policy-12-305",305,"required","preferred","Adult migraine prevention uses the 120 mg/mL syringe (6-month initial, 12-month renewal); episodic cluster headache uses the 100 mg/mL syringe (3-month initial, 12-month renewal). Exact covered strength and package not printed."],["banner-full-3426a5ee04aae9ee","banner-policy-12-351",351,"required","not_specified","Named ganciclovir injection branch; CMV and compendium-supported covered indications; 12-month approval, separate renewal stage not specified."],["banner-full-0b18cd1fd8a34f98","banner-policy-12-129",129,"required","not_specified","Tablet branch; chemotherapy, radiotherapy and postoperative prevention have different approval lengths. Granisol oral solution-only swallowing and ondansetron ODT criteria do not apply to tablets."],["banner-full-40d2ce2b10232236","banner-policy-12-1413",1413,"conditional","preferred","October formulary prints PA for age greater than 18; November policy distinguishes under 18 from 18 and older, including inability to swallow solid forms for the latter. Exact handling at age 18 is unresolved. No self-step through lansoprazole ODT; generic policy only."]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,pa);assert.equal(r.preferred,pref);
 assert(r.policySources.some(p=>p.policyId===pid&&p.firstPage===page&&p.scope===scope),id+' missing exact named link');
 api.medicationGroupCard(g);assert(api.cardClinicalGroups.get(g.key).policies.some(p=>p.id===pid&&p.planId==='banner-ufc'),id+' exact policy missing from card');
 assert(api.recordDetails(r).includes(scope),id+' missing visible source caveat');
}
console.log('PASS: eight Banner policy links retain exact payer flags and product scope.');

// AUT-01: scoped named-policy and cough safety regression.
api.state.planId='banner-ufc';
for(const [id,pid,page,pref,scope] of [["banner-full-24223240af77db72","banner-policy-12-1321",1321,"not_specified","Oral oncology NCCN category 1, 2A or 2B; 12 months. Capsule package not specified; the separate imatinib brand step does not apply."],["banner-full-3562c19cd796ad78","banner-policy-12-1321",1321,"not_specified","Oral oncology NCCN category 1, 2A or 2B; 12 months. Suspension package not specified; the separate imatinib brand step does not apply."],["banner-full-1ae1517495876514","banner-policy-12-811",811,"preferred","Preferred generic acute HAE branch, age 18 or older; 12 months. Nonpreferred-agent step does not apply. Exact package eligibility unverified."],["banner-full-559d389f3b8ed5ff","banner-policy-12-1321",1321,"not_specified","Cancer NCCN category 1, 2A or 2B; 12 months. The additional generic imatinib failure requirement applies to brand Gleevec or Imkeldi requests only. This tablet row does not establish brand eligibility."],["banner-full-2a684512a53f1ec8","banner-policy-12-1321",1321,"not_specified","Named oral oncology cancer branch; NCCN category 1, 2A or 2B; 12 months. The separate imatinib step does not apply. Exact package eligibility unverified."],["banner-full-21719e40e35b7441","banner-policy-12-1321",1321,"not_specified","Named oral oncology cancer branch; NCCN category 1, 2A or 2B; 12 months. October brand-only restriction retained; the generic mention in the guideline does not establish generic coverage."],["banner-full-a485618380e6e997","banner-policy-12-1071",1071,"not_specified","Tablet policy: methotrexate toxicity prophylaxis, hematologic toxicity from folic acid antagonists, or documented cerebral folate deficiency. Twelve months; no separate renewal. Do not transfer to injection."],["banner-full-1710dea660c37719","banner-policy-12-468",468,"not_specified","Xiidra preferred in guideline; October preference unspecified. Separate 12-month initial and renewal branches. Initial requires qualifying diagnosis, documented testing, lubricant trial, specialist and brand Restasis single-dose trial unless contraindicated; renewal requires positive response."],["banner-full-a4a289cc6cd11b2a","banner-policy-12-379",379,"not_specified","Separate 12-month initial and renewal. IBS-C age 7 or older; CIC age 18 or older; functional constipation age 2–17 only for 72 mcg requests. Generic lubiprostone and prucalopride steps both apply to new starts only. Exact package eligibility unverified."]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,'required');assert.equal(r.preferred,pref);
 assert(r.policySources.some(p=>p.policyId===pid&&p.firstPage===page&&p.scope===scope),id+' missing exact named link');
 api.medicationGroupCard(g);assert(api.cardClinicalGroups.get(g.key).policies.some(p=>p.id===pid&&p.planId==='banner-ufc'),id+' missing card policy');
 assert(api.recordDetails(r).includes(scope),id+' missing source scope');
}
for(const [id,label] of [["banner-full-71027bfebf274e67","Guaifenesin / Codeine Oral Syrup"],["banner-full-997a2746536fd44b","Hydrocodone / Homatropine Oral Syrup"],["banner-full-a17980fe85989bde","Hydrocodone / Homatropine Oral Tablets"]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,'conditional');assert.equal(r.preferred,'not_specified');
 assert.equal(g.label,label);const markup=api.medicationGroupCard(g);assert(markup.includes('FDA labeling for prescription opioid cough products limits use to adults 18 and older')&&markup.includes('codeine-information'),id+' safety warning missing');
}
console.log('PASS: nine scoped Banner named-policy links and three opioid cough safety warnings; payer flags retained.');

// AUT-01: additional named scopes and concentration-specific holds.
api.state.planId='banner-ufc';
for(const [id,pid,page,pa,pref,scope] of [["banner-full-b720c6ff93fb1ac3","banner-policy-12-1576",1576,"conditional","not_specified","Printed PA applies to more than two short-acting opioids in 30 days. Corresponding policy branch pp1578–1579 covers dose adjustment, replacement, or documented necessity; duration up to 12 months. Generic tablets preferred in guideline; brand Dilaudid nonpreferred. Other DUR/MME/QL branches separate."],["banner-full-852b41b52868cf72","banner-policy-12-78",78,"required","not_specified","Intron A branch pp78–80: documentation of one of the listed indications, 12 months. No distinct renewal; do not apply Alferon N criteria. Current package availability unverified."],["banner-full-30fc4f26a9ae9605","banner-policy-12-78",78,"required","not_specified","Alferon N branch pp80–81: refractory or recurrent external HPV condylomata acuminata, documented; eight weeks. No distinct renewal; do not apply Intron A criteria. Current package availability unverified."],["banner-full-0272cfe23aa2123e","banner-policy-12-1365",1365,"required","not_specified","Topical head lice branch, 30 days. Generic spinosad failure requirement applies to brand Natroba only. No separate renewal; exact package eligibility unverified."]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,pa);assert.equal(r.preferred,pref);
 assert(r.policySources.some(p=>p.policyId===pid&&p.firstPage===page&&p.scope===scope),id+' missing exact named link');
 api.medicationGroupCard(g);assert(api.cardClinicalGroups.get(g.key).policies.some(p=>p.id===pid&&p.planId==='banner-ufc'),id+' missing card policy');
 assert(api.recordDetails(r).includes(scope),id+' missing source scope');
}
for(const [id,label,notice] of [["banner-full-53ebd7131685b7bf","Lidocaine Topical Patch (ZTlido Reference)","Formulary PA applies only to 1.8% and 3.5% strengths. The named Lidoderm 5% policy is not verified for those concentrations; exact product-specific criteria are unavailable. Printed conditional PA and quantity limit retained."],["banner-full-89f80c3b6125808a","Lidocaine HCl Topical Lotion (Lido-Sorb Reference)","Formulary PA applies only to 3% lotion. Exact concentration-specific policy is unavailable; do not apply patch criteria. Printed conditional PA retained."]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'conditional');assert.equal(r.preferred,'not_specified');assert.equal(g.label,label);
 const markup=api.medicationGroupCard(g);assert(markup.includes(notice),id+' missing exact concentration hold');
 const clinical=api.cardClinicalGroups.get(g.key);assert(!clinical.guidance&&!clinical.policies.length,id+' incorrectly attached policy');
 if(id==='banner-full-53ebd7131685b7bf')assert.equal(String(r.qlAmount),'60');
}
console.log('PASS: four named Banner policy links and two topical concentration-specific holds.');

// AUT-01: GnRH depot product, route, policy scope and holds.
api.state.planId='banner-ufc';
for(const [id,label,scope,hold] of [["banner-full-5fb305c6fb16021c","Eligard Reference — Leuprolide 3-Month SC Depot Injection","Eligard is named in the advanced or metastatic prostate-cancer branch, page 734; 12 months. Preferred in guideline, preference unspecified in October row. Do not apply Lupron Depot nonpreferred step or CPP criteria.",false],["banner-full-fd34a1dfbfb6a466","Eligard Reference — Leuprolide 4-Month SC Depot Injection Kit","Eligard is named in the advanced or metastatic prostate-cancer branch, page 734; 12 months. Preferred in guideline, preference unspecified in October row. Do not apply Lupron Depot nonpreferred step or CPP criteria.",false],["banner-full-01c3982354a89897","Eligard Reference — Leuprolide 6-Month SC Depot Injection Kit","Eligard is named in the advanced or metastatic prostate-cancer branch, page 734; 12 months. Preferred in guideline, preference unspecified in October row. Do not apply Lupron Depot nonpreferred step or CPP criteria.",false],["banner-full-79cf3f8c029341a9","Fensolvi Reference — Leuprolide 6-Month SC CPP Injection Kit","CPP initial and renewal branches, pages 721–724; 12 months each. Preferred in guideline; October preference unspecified. Age limits for gender dysphoria in the separate October 14, 2026 policy do not apply to CPP. Other indications require their own branch; not a blanket coverage determination.",false],["banner-full-81df8d84d1f32707","Lupron Depot-Ped Reference — Leuprolide 1-Month IM CPP Injection Kit","CPP initial and renewal branches, pages 721–724; 12 months each. Preferred in guideline; October preference unspecified. Age limits for gender dysphoria in the separate October 14, 2026 policy do not apply to CPP. Other indications require their own branch; not a blanket coverage determination.",false],["banner-full-ed9523c0d8429e9e","Leuprolide 3-Month Injection Kit (Product Unverified)","October formulary does not identify strength, route or exact depot product. The named 22.5 mg prostate-cancer policy branch cannot be assigned to this unspecified kit; no transfer from Eligard or Lupron Depot.",true],["banner-full-44032f1d9f0702a8","Lupron Depot Reference — Leuprolide IM Depot Injection Kit","October formulary does not specify strength or release schedule. Lupron Depot IM presentations have different strengths and indication-specific policies; monthly and longer-release strengths are not interchangeable. Exact benefit and branch unresolved.",true]]){
 const g=api.planMedicationGroups().find(x=>x.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.planId,'banner-ufc');assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');assert.equal(g.label,label);assert.equal(g.records.length,1);
 const markup=api.medicationGroupCard(g);assert(markup.includes(scope),id+' missing scope');
 const clinical=api.cardClinicalGroups.get(g.key);
 if(hold)assert(!clinical.guidance&&!clinical.policies.length,id+' incorrectly assigned criteria');
 else {assert(r.policySources.some(p=>p.policyId==='banner-policy-12-721'&&p.scope===scope),id+' missing exact source link');assert(clinical.policies.some(p=>p.id==='banner-policy-12-721'),id+' missing policy chapter');assert(markup.includes('dailymed.nlm.nih.gov'),id+' missing label evidence');}
}
console.log('PASS: five distinct labeled depot options and two exact kit holds; original PA and preference retained.');

api.state.planId='banner-ufc';
const auditedBannerGroups=api.planMedicationGroups();
const ageRows=data.medications.filter(r=>r.agePolicyConflict);
assert.equal(ageRows.length,32);
for(const row of ageRows){
 const group=auditedBannerGroups.find(g=>g.records.some(r=>r.id===row.id));
 const card=api.medicationGroupCard(group);
 assert.equal(row.pa,'conditional');
 assert(card.includes(row.agePolicyConflict.note) && card.includes('#page='+row.agePolicyConflict.page));
}
for(const id of ['banner-full-0265ef7d56628527','banner-full-cc76cd1e0045dbf1','banner-full-a1e8bea060c802c9']){
 const group=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));
 const record=group.records.find(r=>r.id===id);
 assert.equal(record.pa,'required');
 const card=api.medicationGroupCard(group);
 assert(card.includes(record.reviewedPresentation.note) && !card.includes('data-card-clinical='));
}
// Exact Banner MS links retain the formulary's unknown preference and device distinctions.
for(const [id,product] of [
 ['banner-full-b20b5312833f8841','Avonex'],
 ['banner-full-46cc6b2b57f100b3','Avonex'],
 ['banner-full-fe7518236db69cb0','Rebif']
]){
 const group=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(group,id+' missing');
 const record=group.records.find(r=>r.id===id);
 assert.equal(record.planId,'banner-ufc');assert.equal(record.pa,'required');assert.equal(record.preferred,'not_specified');
 const link=record.policySources.find(p=>p.policyId==='banner-policy-12-1193');
 assert(link && link.matchedProduct===product && link.firstPage===1193 && link.scope.includes('positive clinical response') && link.scope.includes('Exact device/package eligibility is unverified'),id+' missing correct scope');
 api.medicationGroupCard(group);
 assert(api.cardClinicalGroups.get(group.key).policies.some(p=>p.id==='banner-policy-12-1193' && p.planId==='banner-ufc'),id+' missing exact-plan policy');
}
console.log('PASS: three Banner MS listings preserve original PA and preference and named guideline scope.');
 // Reviewed Banner stage selections use exact pages, not nonpreferred MS or other growth-hormone products.
 for(const [id,initial,renewal,exclude] of [
  ['banner-full-b20b5312833f8841',1193,1195,null], ['banner-full-46cc6b2b57f100b3',1193,1195,null],
  ['banner-full-fe7518236db69cb0',1193,1195,null], ['banner-full-32585265928bf196',1193,1195,null],
  ['banner-full-5f7934d566956f29',764,766,737]
 ]){
  const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
  const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
  assert(r.reviewedBannerBranches);api.medicationGroupCard(g);const expanded=targetFor(g);await api.populateCardClinical(expanded.details);
  const html=expanded.target.innerHTML;assert.equal(expanded.details.dataset.loaded,'true',id+' expanded criteria failed: '+html);
  for(const p of [initial,renewal])assert(html.includes('Criteria source · PDF page '+p+'<'),id+' missing stage page '+p);
  assert(!html.includes('Criteria source · PDF page 1194<'),id+' unrelated nonpreferred MS criteria');
  if(exclude){assert(html.includes('Criteria source · PDF page '+exclude+'<'));assert(html.includes('Separate indication exclusion'));assert(html.includes('Idiopathic Short Stature'));assert(html.includes('neutralizing antibodies'));assert(!html.includes('Revision History'));}
  else{assert(html.includes('Diagnosis of multiple sclerosis'));assert(html.includes('positive clinical response'));}
  assert(api.recordDetails(r).includes('Exact')&&api.recordDetails(r).includes('unverified'));
 }
 console.log('PASS: five reviewed Banner rows show precise initial/renewal links and separate Increlex ISS exclusion.');
 for(const id of ['banner-full-a500a55a6c2da52e','banner-full-9d81da2b37ae5a9a']){
  const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
  const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
  assert.equal(r.reviewedBannerBranches.unstagedPage,87);assert(r.policySources.some(p=>p.policyId==='banner-policy-12-87'&&p.scope.includes('not separately labeled')));
  api.medicationGroupCard(g);const expanded=targetFor(g);await api.populateCardClinical(expanded.details);
  const html=expanded.target.innerHTML;assert.equal(expanded.details.dataset.loaded,'true',id+' criteria failed '+html);
  assert(html.includes('Criteria source · PDF page 87<')&&html.includes('Authorization stage is not separately labeled')&&html.includes('dementia of the Alzheimer’s type')&&html.includes('12 month(s)'));
  assert(!html.includes('Parkinson')&&!html.includes('Adlarity')&&!html.includes('Criteria source · PDF page 88<')&&!html.includes('Treatment stage:'));
  assert(api.recordDetails(r).includes('Exact covered package eligibility is unverified'));
 }
 console.log('PASS: two exact Banner memantine rows retain PA and unknown preference, unstaged criteria page and product scope.');
// Methadone FDA label and payer indication must remain distinct for all four Banner rows.
 for(const [id,hold] of [["banner-full-abc845306384483c",true],["banner-full-9ec47e1a44d309df",false],["banner-full-bffe9a14c9598aaf",false],["banner-full-7f30550aa500ee70",true]]){
  const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');assert.equal(g.records.length,1,id+' merged forms');
  const r=g.records[0];assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
  const card=api.medicationGroupCard(g);assert(/OUD\)? PA criteria/.test(card)&&card.includes('>PA required<'),id+' missing OUD caveat or PA: '+card.slice(0,2400));
  assert(api.recordDetails(r).includes('GL-611235'));
  assert.equal(r.reviewedPresentation.policyUnverified,hold);
  if(hold){assert(!card.includes('data-card-clinical='),id+' pain criteria shown despite label hold');}
  else{const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
   assert.equal(e.details.dataset.loaded,'true',id+' expanded pain source failed '+html);
   for(const p of [1100,1104,1110,1099,1111,1112])assert(html.includes('Criteria source · PDF page '+p+'<'),id+' missing '+p);
   assert(html.includes('pain only')&&html.includes('Opioid use disorder authorization is unverified')&&html.includes('Separate conditional review references'));
   assert(html.includes('Cancer-related pain')&&html.includes('Initial Authorization')&&html.includes('Reauthorization'));
   for(const p of [1101,1102,1105,1108,1113,1114,1115])assert(!html.includes('Criteria source · PDF page '+p+'<'),id+' unrelated policy branch');
  }
 }
 console.log('PASS: four Banner methadone forms, PA flags, label conflicts and distinct indication/DUR scopes.');
for(const [id,route] of [['banner-full-89559c60a03b28df','NOT IV'],['banner-full-6c6a47cf0133d553','IV/IM solution']]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes(route)&&card.includes('>PA required<')&&!card.includes('data-card-clinical='),id+' lost route or hold');
 assert(r.reviewedPresentation.policyUnverified&&r.reviewedPresentation.labelUrl);
}
{
 const id='banner-full-7c0d8ee13a73e22b',g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.pa,'conditional');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes('over age 10')&&card.includes('pediatric safety and effectiveness not established'));
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert(html.includes('Criteria source · PDF page 1249<')&&html.includes('Authorization stage is not separately labeled')&&html.includes('generic equivalent')&&html.includes('unable to swallow')&&html.includes('12 month(s)'),html);
 for(const other of ['Norliqva','Sdamlo','Katerzia','Subvenite','Criteria source · PDF page 1248<'])assert(!html.includes(other),'unrelated step '+other);
}
console.log('PASS: two injectable route/criteria holds and conditional Lopressor product branch with age and label caveats.');
{
 const id='banner-full-c221a2227136f081',g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes('Sandoz')&&card.includes('100 mg')&&card.includes('150 mg')&&card.includes('>PA required<'));
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 for(const p of [589,591,592,593,594,595])assert(html.includes('Criteria source · PDF page '+p+'<'),id+' missing '+p);
 for(const term of ['Idiopathic pulmonary fibrosis','Systemic sclerosis-associated','Progressive fibrosing ILD','Initial Authorization','Reauthorization','positive clinical response','pulmonologist','12 month(s)'])assert(html.includes(term),id+' missing '+term);
 assert(!/For Non-Preferred requests|PA Team: Please approve/i.test(html),'Unrelated nonpreferred steps or administrative note leaked');
 assert(api.recordDetails(r).includes('GL-620196'));
}
console.log('PASS: Sandoz nintedanib exact manufacturer and indication-stage criteria, raw flags unchanged.');

for(const id of ['banner-full-697faa8211f23f28','banner-full-4710a711a65069e2','banner-full-bcd63d76ee8d2c84']){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.pa,'conditional');assert.equal(r.preferred,'not_specified');
 assert(api.medicationGroupCard(g).includes('data-card-clinical='),id+' clinical action absent');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert(html.includes('Criteria source · PDF page 1578<')&&html.includes('Authorization stage is not separately labeled'),html);
 assert(/adjust the dose/i.test(html)&&/attests/i.test(html),html);
 assert(!html.includes('Criteria source · PDF page 1577<')&&!html.includes('Criteria source · PDF page 1576<'),id+' unrelated conditional reviews rendered');
 assert(api.recordDetails(r).includes('GL-709190'));
}
for(const [id,pref] of [['banner-full-087c94375a6182f2','preferred'],['banner-full-ef27a4dfae81f655','not_specified']]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');assert.equal(g.records.length,1);
 const r=g.records[0];assert.equal(r.pa,'required');assert.equal(r.preferred,pref);
 assert(api.medicationGroupCard(g).includes('data-card-clinical='),id+' clinical action absent');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 for(const p of [1100,1104,1110])assert(html.includes('Criteria source · PDF page '+p+'<'),id+' missing '+p);
 for(const p of [1099,1101,1105,1111,1112])assert(!html.includes('Criteria source · PDF page '+p+'<'),id+' unrelated stage '+p);
}
{
 const id='banner-full-e50339bf35f4c1a8',g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
 assert(api.medicationGroupCard(g).includes('HBV criteria unverified'));
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert(html.includes('Criteria source · PDF page 806<')&&html.includes('48 Week(s)')&&/combination antiviral/i.test(html),html);
 assert(!html.includes('Criteria source · PDF page 807<'),id+' separate ribavirin branch');
}
for(const [id,name] of [['banner-full-3d7714307e911530','Fulphila'],['banner-full-c9e709fdd45fb2d7','Fylnetra']]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');const r=g.records.find(r=>r.id===id);
 assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');assert(r.reviewedPresentation.policyUnverified&&r.reviewedPresentation.labelUrl);
 const card=api.medicationGroupCard(g);assert(card.includes(name)&&card.includes('6 mg/0.6 mL')&&card.includes('stem-cell mobilization')&&!card.includes('data-card-clinical='),id+' unsafe general CSF criteria');
}
console.log('PASS: five exact opioid records, Pegasys HCV-only branch and two CSF indication holds.');

for(const [id,page,pref,pattern] of [
 ['banner-full-a385ef7908014d5f',963,'not_specified',/NCCN|National Comprehensive Cancer Network/i],
 ['banner-full-e532fae3af52a7f5',1322,'not_specified',/NCCN|National Comprehensive Cancer Network/i],
 ['banner-full-dbd10ab6ed6cbec3',1322,'not_specified',/NCCN|National Comprehensive Cancer Network/i],
 ['banner-full-201c806b5669b4d1',1322,'not_specified',/NCCN|National Comprehensive Cancer Network/i],
 ['banner-full-33b6c65c4a83387f',1322,'not_specified',/NCCN|National Comprehensive Cancer Network/i],
 ['banner-full-127d40be02571b08',1805,'preferred',/cystic fibrosis/i],
 ['banner-full-2d20172bd0ae6a5a',1805,'preferred',/cystic fibrosis/i],
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,pref);
 assert(api.medicationGroupCard(g).includes('data-card-clinical='),id+' missing criteria action');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert(html.includes('Criteria source · PDF page '+page+'<')&&pattern.test(html),id+' '+html);
 assert(html.includes('Authorization stage is not separately labeled'),id+' stage incorrectly assigned');
 if(page===1322)assert(!/tried and failed the preferred generic counterpart/i.test(html),id+' unrelated imatinib step');
 if(page===1805)assert(!/positive culture|history of failure|positive clinical response/i.test(html),id+' unrelated TOBI criteria');
}
for(const [id,pa,pref,term] of [
 ['banner-full-d703bdd7986bae9f','required','not_specified','not interchangeable'],
 ['banner-oct26-025','required','preferred','Model Unverified'],
 ['banner-oct26-001','required','preferred','SymlinPen 60'],
 ['banner-full-37f793a83cc9e549','conditional','not_specified','18 and older'],
 ['banner-full-09077a336e9813e5','conditional','not_specified','18 and older'],
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,pa);assert.equal(r.preferred,pref);
 assert(r.reviewedPresentation.policyUnverified&&r.reviewedPresentation.labelUrl,id+' missing source hold');
 const card=api.medicationGroupCard(g);assert(card.includes(term)&&!card.includes('data-card-clinical='),id+' hold missing or unrelated criteria attached');
}
console.log('PASS: exact oncology and tobramycin criteria; distinct presentations and five unresolved-policy safety holds.');
for(const [id,name] of [['banner-full-0557b6b7d1ec805f','Ribavirin Oral Capsules'],['banner-full-b77993fa62dc7389','Ribavirin Oral Tablets']]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
 const card=api.medicationGroupCard(g);assert(card.includes(name)&&card.includes('data-card-clinical='),id+' form or criteria action missing');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert(html.includes('Criteria source · PDF page 807<')&&/chronic hepatitis C infection/i.test(html)&&/direct-acting agent/i.test(html),id+' '+html);
 assert(html.includes('Authorization stage is not separately labeled'),id+' incorrect stage');
 assert(!/HCV RNA|MedWatch|decompensated liver disease/i.test(html),id+' unrelated DAA/Pegasys criteria');
}
console.log('PASS: distinct ribavirin capsule and tablet cards, exact HCV branch and retained PA/preference.');

{
 const id='banner-full-302dc8a037e00f33',g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.name,'RITUXIMAB-ABBS');assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 assert(r.reviewedPresentation.policyUnverified&&!r.reviewedBannerBranches,id+' identity hold missing');
 assert(!(r.policySources||[]).some(p=>p.policyCode==='GL-540210'),id+' conflicting policy attached');
 const card=api.medicationGroupCard(g);
 assert(card.includes('Identity Conflict')&&card.includes('rituximab-arrx')&&card.includes('Truxima')&&!card.includes('data-card-clinical='),id+' issuer conflict not visible or unsafe criteria attached');
}
for(const [id,pa,pref,pages] of [
 ['banner-full-a7f4dfa0b5da7c81','required','not_specified',[1530,1531,1531,1533,1534,1534,1535,1535,1535]],
 ['banner-full-fb30ee751e608466','required','preferred',[1798,1799,1803]],
 ['banner-full-f5992d3fa1f49565','required','not_specified',[1896,1899]],
 ['banner-full-dbcd5faa36dfde5f','required','not_specified',[1896,1899]],
 ['banner-full-fa4f8ddffa54cfb6','conditional','preferred',[798]]
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,pa);assert.equal(r.preferred,pref);
 assert(api.medicationGroupCard(g).includes('data-card-clinical='),id+' missing criteria action');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),pages,id+' wrong or missing branch '+html);
 if(pages[0]===1530){
  assert(html.includes('pediatric branch is off-label for Ruxience')&&/Waldenstrom macroglobulinemia \(off-label\)/i.test(html)&&/Immune thrombocytopenia \(off-label\)/i.test(html),id+' unsafe label/stage scope');
  assert(/16 weeks/i.test(html)&&/methotrexate/i.test(html)&&/fludarabine/i.test(html)&&/glucocorticoids/i.test(html),id+' missing indication-specific criteria');
  assert(!/Requests for Non-Preferred biosimilars are not approved/i.test(html),id+' unrelated nonpreferred policy');
 }
 if(pages[0]===1798){
  assert(/positive clinical response/i.test(html)&&/Corticosteroids/i.test(html)&&/myelosuppressive doses of radiation/i.test(html),id+' missing exact criteria');
  assert(!/For Non-Preferred Drug requests|Aplastic Anemia|scheduled to undergo a procedure/i.test(html),id+' unrelated or self step');
 }
 if(pages[0]===1896){
  assert(/Brand Buphenyl and Pheburane only/i.test(html)&&/CPS1/i.test(html)&&/positive clinical response/i.test(html),id+' missing conditional brand step or renewal');
  assert(!/history of failure or intolerance to Brand Ravicti/i.test(html),id+' unrelated glycerol criteria');
 }
 if(pages[0]===798){
  assert.equal(String(r.qlAmount),'168');assert.equal(String(r.qlDays),'Lifetime');
  assert(/HCV\) RNA|HCV RNA/i.test(html)&&/past 90 days/i.test(html)&&/Authorization stage is not separately labeled/i.test(html),id+' retreatment criteria missing');
  assert(!/MedWatch|therapeutic failure, contraindication, or intolerance to the generic/i.test(html),id+' brand-only criteria');
 }
}
console.log('PASS: rituximab issuer conflict held; five exact Banner records scoped, stages and flags retained, no unrelated Nplate/DAA/glycerol step.');
{
 const id='banner-full-b6ed7f51c1eb7ebe',g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'conditional');assert.equal(r.preferred,'not_specified');
 assert(r.reviewedPresentation.policyUnverified&&!r.reviewedBannerBranches,id+' pediatric hold missing');
 const card=api.medicationGroupCard(g);assert(card.includes('Age/Policy Conflict')&&card.includes('age exactly 12')&&card.includes('13–17')&&!card.includes('data-card-clinical='),id+' unsafe pediatric inference');
}
for(const id of ['banner-full-60198c9988b7fac5','banner-full-a16e47fcf26287e4']){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes('PAH Oral Tablets')&&card.includes('data-card-clinical='),id+' exact criteria missing');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),[1422,1425],id+' wrong PAH branches '+html);
 assert(/18 years of age or older/i.test(html)&&/right heart catheterization/i.test(html)&&/positive clinical response/i.test(html),id+' lost PAH clinical requirements');
 assert(!/Requests for Tracleer|Requests for Uptravi|request is for Brand Adcirca|request is for Opsynvi|non-preferred product|CTEPH/i.test(html),id+' unrelated age or product criteria');
}
console.log('PASS: Banner sildenafil suspension age conflict held and two adult generic PAH tablet branches scoped.');
for(const [id,pref,term] of [
 ['banner-full-b5d2b1db3141799d','not_specified','Weekly SC Solution Pen'],
 ['banner-full-7f3830370febcc33','preferred','SC Powder Cartridge'],
 ['banner-full-9d1ec74eeb56ae29','preferred','Single-dose SC Powder Delivery Device'],
 ['banner-full-1fada00875b7d8d2','preferred','Daily SC Solution Pen']
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,pref);
 const card=api.medicationGroupCard(g);assert(card.includes(term)&&/not (?:a )?prescribing dose/.test(card)&&card.includes('ISS exclusion'),id+' dose/label caveat missing');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 const pages=[...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1]));
 const base=[738,741,...(pref==='preferred'?[743,744]:[]),745,746,746,748,748,749,750,751,752,755,756,760,761,763,763,737];
 assert.deepEqual(pages,base,id+' missing or wrong indication stage');
 assert(/not FDA-labeled/i.test(html)&&/benefit exclusion|not authorized/i.test(html),id+' off-label/ISS separation missing');
 assert(!/failure to ALL preferred products/i.test(html),id+' nonpreferred-only step leaked');
 if(pref==='not_specified')assert(!/Prader-Willi syndrome/i.test(html)&&/2\.5\+/.test(html),id+' Sogroya pediatric or PWS scope');
}
console.log('PASS: four separate growth hormone devices and exact staged criteria, label caveats and ISS exclusion.');
for(const [id,pa,pref,form,pages] of [
 ['banner-full-cec1a88dc96d5532','required','preferred','Topical Ointment',[531,532]],
 ['banner-full-fe8f9d5e4dfee7b6','required','not_specified','IV Powder',[706]],
 ['banner-full-76e5b2efb93b4591','conditional','preferred','Oral Capsules',[1558,1559]],
 ['banner-full-4d4c6a25d76989bf','required','preferred','SC Solution Autoinjector',[1808,1809,1810,1810,1811,1811,1813]],
 ['banner-full-9c0e6d815920bc01','required','preferred','SC Solution Prefilled Syringe',[1808,1809,1810,1810,1811,1811,1813]],
 ['banner-full-9464979a40566984','required','preferred','IV Infusion Concentrate Vial',[1808,1809,1810,1810,1811,1813]],
 ['banner-full-ad25104047d308ec','required','preferred','SC Solution Autoinjector',[1808,1809,1810,1810,1811,1811,1813]],
 ['banner-full-2f8cff650d027225','required','preferred','SC Solution Prefilled Syringe',[1808,1809,1810,1810,1811,1811,1813]],
 ['banner-full-f4f2df53529dbd35','required','preferred','IV Infusion Concentrate Vial',[1808,1809,1810,1810,1811,1813]],
 ['banner-full-31f510c5e7f38c18','required','preferred','IV Infusion Concentrate Vial',[1808,1809,1810,1810,1811,1813]]
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,pa);assert.equal(r.preferred,pref);
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes('data-card-clinical='),id+' form or criteria missing');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),pages,id+' incorrect branches');
 if(pages[0]===531) assert(card.includes('0.03%')&&card.includes('0.1%')&&card.includes('16 years'),id+' strength-specific age scope missing');
 if(pages[0]===706) assert(/renewal applicability/i.test(card)&&card.includes('Type 3')&&!/For VPRIV requests ONLY|generic miglustat/i.test(html),id+' Vpriv prerequisites or unresolved renewal');
 if(pages[0]===1558) {
  assert.equal(String(r.qlAmount),'30');assert.equal(String(r.qlDays),'30');
  assert(/greater than one hypnotic/i.test(html)&&/age under 6/i.test(html)&&!/generic temazepam 7.5 mg/i.test(html),id+' wrong conditional branch');
 }
 if(pages[0]===1808){
  assert(!/Requests for Non-Preferred biosimilars/i.test(html),id+' unrelated nonpreferred criteria');
  if(form.startsWith('SC'))assert(/SC-only SSc-ILD/i.test(html)&&!/Coronavirus disease 2019/i.test(html),id+' IV-only criteria leaked');
  else assert(/IV-only hospitalized COVID-19/i.test(html)&&!/SSc-ILD/i.test(html),id+' SC-only criteria leaked');
 }
}
console.log('PASS: ten Banner option-specific records; conditional ages, exact stages and route branches; Elelyso renewal hold and no Vpriv-only prerequisite.');

for(const [id,form,pages] of [
 ['banner-full-f92ada2e9cdc655f','Immediate-Release Oral Tablets',[2017,2018,2018,2019,2020,2021,2021,2022,2023,2023]],
 ['banner-full-d4ea7eb7e9b33e7f','Extended-Release Oral Tablets',[1100,1104,1110]]
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes('data-card-clinical='),id+' missing form or action');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),pages,id+' incorrect branches');
 if(id==='banner-full-f92ada2e9cdc655f')assert(card.includes('TNF blocker')&&card.includes('not an additional inferred payer step')&&!/Requests for generic tofacitinib are not authorized/i.test(html),id+' label distinction or unrelated generic denial');
 else assert(card.includes('exact brand eligibility')&&!/MME Exceeded|Quantity Limit Override|Conzip/i.test(html),id+' unrelated opioid policy branch');
}
console.log('PASS: Xeljanz IR five staged indications and generic tramadol ER three pain branches; product holds retained.');

for(const [id,pa,form,pages] of [
 ['banner-full-5b8daa67d76d4afd','required','Toremifene Oral Tablets',[260,261,261]],
 ['banner-full-2d903aad91549aef','conditional','Immediate-Release Oral Tablets',[1578]]
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,pa);assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes('data-card-clinical='),id+' form or action missing');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),pages,id+' incorrect branches');
 if(pa==='required'){
  assert(card.includes('QT prolongation')&&/metastatic breast cancer/i.test(html)&&/positive clinical response/i.test(html),id+' indication, renewal or label warning missing');
  assert(!/adjuvant treatment|progression following tamoxifen/i.test(html),id+' unrelated cancer criteria');
 }else{
  assert(card.includes('30 days')&&card.includes('tonsillectomy/adenoidectomy')&&/adjust the dose/i.test(html)&&/medically necessary/i.test(html),id+' conditional trigger or safety warning missing');
  assert(!/history of failure, contraindication or intolerance|MME exceeded|concurrent opioid therapy/i.test(html),id+' unrelated opioid criteria');
 }
}
console.log('PASS: exact Fareston three cancer branches and tramadol 50 mg conditional PA; original flags and label cautions retained.');

for(const [id,preferred] of [["banner-full-910fdc030a0e440e",false],["banner-full-8e3ddd09c2a6ceef",true],["banner-full-b83161f7a9a12ddf",false],["banner-full-afa717d825297dd3",false]]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes('IV Infusion Powder')&&card.includes('data-card-clinical=')&&card.includes('cardiomyopathy'),id+' form, warning or criteria missing');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),[1822],id+' incorrect branch');
 if(preferred)assert(/National Comprehensive Cancer Network/i.test(html)&&!/not approved at this time/i.test(html),id+' incorrect preferred branch');
 else assert(/Ogivri/i.test(html)&&/not approved/i.test(html)&&!/National Comprehensive Cancer Network/i.test(html),id+' incorrect nonpreferred branch');
}
{
 const id='banner-full-4ca60ba6b5918217';const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes('Form Unverified')&&card.includes('ready-to-use solution')&&!card.includes('data-card-clinical='),id+' unsafe automatic criteria');
 assert(!g.records.some(r=>r.id==='banner-full-910fdc030a0e440e'),id+' collapsed conflicting form');
}
console.log('PASS: trastuzumab product-specific restriction and Kanjinti solution hold; original flags retained.');

for(const [id,form,warning] of [
 ['banner-full-ef9bc93d53ee9c80','Extended-Release Oral Tablets','swallow whole with food'],
 ['banner-full-917087991e3a1d92','Extended-Release Oral Tablet Therapy Pack','exact month and contents'],
 ['banner-full-a6ce2a3f193366dd','Inhalation Powder Capsules','DO NOT SWALLOW']
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes(warning)&&card.includes('data-card-clinical='),id+' form or warning missing');
 assert(!g.records.some(r=>r.id!==id&&['banner-full-ef9bc93d53ee9c80','banner-full-917087991e3a1d92','banner-full-a6ce2a3f193366dd'].includes(r.id)),id+' unsafe form merge');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),[1422,1425],id+' wrong PAH branches');
 assert(/18 years of age or older/i.test(html)&&/right heart catheterization/i.test(html)&&/positive clinical response/i.test(html),id+' lost PAH clinical requirements');
 assert(!/Requests for Tracleer|Requests for Uptravi|request is for Brand Adcirca|request is for Opsynvi|non-preferred product|CTEPH|PH-ILD/i.test(html),id+' unrelated age or product criteria');
}
console.log('PASS: Orenitram tablets, titration pack and Yutrepia inhalation capsule separate; adult PAH stages and no-swallow warning preserved.');

for(const [id,form] of [["banner-full-9c89c762ecf4a4e7","Starjemza (Ustekinumab-hmny) Solution — Route Unverified"]]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&!card.includes('data-card-clinical='),id+' unsafe automatic criteria or missing form');
 assert(!g.records.some(r=>r.id!==id&&["banner-full-7c9407dc50aeffd6","banner-full-9c89c762ecf4a4e7","banner-full-d2638c75bf2c5094","banner-full-e859b1c3f1be58db","banner-full-6d23af5aca74fca8"].includes(r.id)),id+' unsafe form merge');
}
for(const [id,form] of [["banner-full-b6f0f769c82aaeea","Vandetanib Oral Tablets (Caprelsa Reference)"],["banner-full-4b852a28d521d828","Vemurafenib Oral Tablets (Zelboraf Reference)"],["banner-full-237950cc08ca1717","Vorinostat Oral Capsules (Zolinza Reference)"]]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes('data-card-clinical='),id+' missing criteria or form');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),[1322],id+' wrong oncology branch');
 assert(/NCCN|National Comprehensive Cancer Network/i.test(html)&&!/imatinib/i.test(html),id+' wrong oncology scope');
}
for(const [id,form,q] of [["banner-full-1ff7d86a645bdc05","Zolpidem Extended-Release Oral Tablets (Ambien CR Reference)","30"],["banner-full-d93c4badc39b2d2f","Zolpidem Immediate-Release Oral Tablets 10 mg (Ambien Reference)","30"],["banner-full-b41b5e9a4587cefd","Zolpidem Immediate-Release Oral Tablets 5 mg (Ambien Reference)","60"]]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'conditional');assert.equal(r.preferred,'preferred');assert.equal(String(r.qlAmount),q);assert.equal(String(r.qlDays),'30');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes('data-card-clinical='),id+' missing criteria or form');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),[1558,1559],id+' wrong conditional branch');
 assert(/greater than one hypnotic/i.test(html)&&/age under 6/i.test(html)&&!/generic temazepam 7.5 mg/i.test(html),id+' unrelated nonpreferred branch');
}
console.log('PASS: five form/criteria holds, three oncology branches, three zolpidem conditional options; raw payer flags and QL retained.');

{
 const id="banner-full-5fb011fb853c0158";const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
 const card=api.medicationGroupCard(g);assert(card.includes('Epogen (Epoetin Alfa) IV or Subcutaneous Injection')&&card.includes('Payer conflict')&&card.includes('Retacrit')&&!card.includes('data-card-clinical='),id+' lost conflict or unsafe automatic criteria');
 assert(!g.records.some(r=>r.id==='banner-full-b744ae9803f287da'),id+' unsafe merge with Retacrit');
}
for(const [id,form,pa,pref,pages] of [["banner-full-4ea1555b6e50ad9b","Dasatinib Oral Tablets (Sprycel Reference)","required","not_specified",[1322]],["banner-full-744c182ca2569adb","Dolasetron Oral Tablets (Anzemet Reference)","required","not_specified",[129,130,131]],["banner-full-b744ae9803f287da","Retacrit (Epoetin Alfa-epbx) IV or Subcutaneous Injection","required","preferred",[581,582,584,584,585,585,586,586,587,587]],["banner-full-0865865cc9f5fed9","Eszopiclone Oral Tablets (Lunesta Reference)","conditional","preferred",[1558,1559]],["banner-full-0a392c206a4c7134","Etoposide Oral Capsules","required","not_specified",[1322]],["banner-full-7f9d539620cb5752","Exemestane Oral Tablets (Aromasin Reference)","required","not_specified",[260,261,261]]]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,pa);assert.equal(r.preferred,pref);
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes('data-card-clinical='),id+' missing criteria or form');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),pages,id+' wrong branches');
 if(pages[0]===129)assert(/chemotherapy/i.test(html)&&/radiotherapy/i.test(html)&&/postoperative/i.test(html)&&!/Granisol requests ONLY|ondansetron ODT/i.test(html),id+' other product requirement');
 if(pages[0]===581)assert(/dialysis/i.test(html)&&/Zidovudine/i.test(html)&&/MDS/i.test(html)&&/HCV/i.test(html)&&/case-by-case/i.test(html)&&!/non-preferred drug is not approved/i.test(html),id+' missing or unrelated ESA criteria');
 if(pages[0]===1558){assert.equal(String(r.qlAmount),'30');assert.equal(String(r.qlDays),'30');assert(/greater than one hypnotic/i.test(html)&&/age under 6/i.test(html)&&!/generic temazepam 7.5 mg/i.test(html),id+' wrong conditional criteria');}
 if(pages[0]===1322)assert(/NCCN|National Comprehensive Cancer Network/i.test(html)&&!/Brand Gleevec or Imkeldi/i.test(html),id+' wrong oncology scope');
 if(pages[0]===260)assert(/tamoxifen/i.test(html)&&/positive clinical response/i.test(html)&&!/tumors of unknown estrogen receptor status/i.test(html),id+' wrong breast cancer scope');
}
console.log('PASS: six reviewed exact Banner policy rows and one ESA payer conflict; product, stage, indication, QL and safety scope.');

for(const [id,form,pages] of [["banner-full-7c9407dc50aeffd6","Starjemza (Ustekinumab-hmny) Subcutaneous Prefilled Syringe",[1900,1901,1902,1903,1903,1904,1905]],["banner-full-d2638c75bf2c5094","Valganciclovir Powder for Oral Solution (Valcyte Reference)",[351]],["banner-full-e859b1c3f1be58db","Valganciclovir Oral Tablets (Valcyte Reference)",[351]],["banner-full-6d23af5aca74fca8","Vfend (Voriconazole) Powder for Oral Suspension",[200,207]]]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes('data-card-clinical='),id+' missing form or criteria');
 assert(!g.records.some(r=>r.id!==id&&["banner-full-7c9407dc50aeffd6","banner-full-9c89c762ecf4a4e7","banner-full-d2638c75bf2c5094","banner-full-e859b1c3f1be58db","banner-full-6d23af5aca74fca8"].includes(r.id)),id+' unsafe form merge');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),pages,id+' wrong branches');
 if(pages[0]===1900)assert(/psoriasis/i.test(html)&&/arthritis/i.test(html)&&/Crohn/i.test(html)&&/colitis/i.test(html)&&/not IV induction/i.test(card)&&/adult IBD only/i.test(card),id+' SC or stage scope lost');
 if(pages[0]===351)assert(/retinitis/i.test(html)&&/prophylaxis/i.test(html)&&!/Herpes simplex/i.test(html),id+' incorrect antiviral branch');
 if(pages[0]===200)assert(/suspension/i.test(html)&&/hospital/i.test(html)&&/aspergillosis/i.test(html)&&/brand only/i.test(card),id+' wrong antifungal scope');
}
console.log('PASS: recovered four exact policy rows; Starjemza solution route held; original flags and separate forms preserved.');

for(const [id,form,pages] of [["banner-full-c50d5a831e1c6a83","Aralast NP (Alpha1-Proteinase Inhibitor) IV Powder for Solution",[82,83]],["banner-full-b9c82fb411440f4c","Cidofovir IV Infusion Solution (Vistide Reference)",[352]],["banner-full-514f1b7852e793e4","Demeclocycline Hydrochloride Oral Tablets",[449]],["banner-full-655161387e7d56c9","Donepezil Hydrochloride Orally Disintegrating Tablets (Aricept Reference)",[87]],["banner-full-5871af4cc5e1eb9b","Premarin (Conjugated Estrogens) Vaginal Cream",[598]]]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'not_specified');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes('data-card-clinical='),id+' missing form or criteria: label='+g.label+' scoped='+JSON.stringify(r.reviewedBannerBranches)+' presentation='+JSON.stringify(r.reviewedPresentation)+' group ids='+g.records.map(x=>x.id).join(',')+' title present='+card.includes(form)+' clinical present='+card.includes('data-card-clinical='));
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),pages,id+' wrong branches');
 if(pages[0]===82)assert(/emphysema/i.test(html)&&/positive clinical response/i.test(html)&&/require reconstitution/i.test(card),id+' form or stage scope lost');
 if(pages[0]===352)assert(/retinitis/i.test(html)&&!/CMV disease prophylaxis/i.test(html)&&/NOT intraocular/i.test(card),id+' wrong cidofovir branch');
 if(pages[0]===449)assert(/infectious disease/i.test(html)&&/6 months/i.test(html)&&/no labeled SIADH/i.test(card),id+' wrong demeclocycline scope');
 if(pages[0]===87)assert(/Alzheimer/i.test(html)&&!/Parkinson|generic rivastigmine patch/i.test(html),id+' wrong dementia scope');
 if(pages[0]===598)assert(/atrophic vaginitis/i.test(html)&&/kraurosis vulvae/i.test(html)&&!/Femring/i.test(html),id+' wrong vaginal indication');
}
{
 const id="banner-full-150d0a331d6c46df";const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const card=api.medicationGroupCard(g);assert(card.includes('Exact covered brand, formulation and package are unverified')&&card.includes('GL-731221')&&!card.includes('data-card-clinical='),id+' unsafe auto criteria or missing hold');
 assert.equal(g.records.length,1);
}
console.log('PASS: five Banner exact rows and one A1PI package/form hold, original flags preserved.');
for(const [id,form,code,warning] of [
 ['banner-full-3880bff4a3b70b55','Adalimumab-bwwd Subcutaneous Prefilled Syringe','GL-525274','Payer identity hold'],
 ['banner-full-649d84d33fb33d42','Hulio (Adalimumab-fkjp) Subcutaneous Autoinjector Kit','GL-525274','Payer conflict'],
 ['banner-full-7c98df91d2b8f9ad','Hulio (Adalimumab-fkjp) Subcutaneous Prefilled Syringe Kit','GL-525274','Payer conflict'],
 ['banner-full-84b2d91ea0a7c4f1','Promacta (Eltrombopag Olamine) Oral Tablets','GL-525300','Payer conflict']
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
 assert(r.reviewedPresentation.policyUnverified&&!r.reviewedBannerBranches,id+' missing hold');
 assert(r.policySources.some(p=>p.policyCode===code),id+' missing exact policy source');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes(code)&&card.includes(warning)&&!card.includes('data-card-clinical='),id+' lost warning or unsafe branch');
 assert.equal(g.records.length,1,id+' unsafe product merge');
}
console.log('PASS: four exact Banner identity/preference conflicts preserve source flags, forms, dated policy links and suppress unverified criteria.');
for(const [id,form,pages] of [
 ["banner-full-28415ec20645c82d","Hadlima Push (Adalimumab-bwwd) Subcutaneous Autoinjector",[33,34,35,35,36,37,37,39,39,40,41,42,42,43,44]],
 ["banner-full-7112927146512ad5","Eltrombopag Olamine Oral Tablets (Generic)",[1798,1799,1800,1801,1801,1802]],
 ["banner-full-a6e3c12492730c31","Aimovig (Erenumab-aooe) Subcutaneous Autoinjector",[305,308]],
 ["banner-full-719caae0c9978dca","Infliximab (Janssen Unbranded Remicade Reference) IV Powder for Solution",[945,946,947,947,948,949,949,950,951,952,952,953,954,955]]
]){
 const g=auditedBannerGroups.find(g=>g.records.some(r=>r.id===id));assert(g,id+' missing');
 const r=g.records.find(r=>r.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
 const card=api.medicationGroupCard(g);assert(card.includes(form)&&card.includes('data-card-clinical='),id+' missing form or criteria: '+g.label);
 assert.equal(g.records.length,1,id+' unsafe product merge');
 const e=targetFor(g);await api.populateCardClinical(e.details);const html=e.target.innerHTML;
 assert.equal(e.details.dataset.loaded,'true',id+' criteria failed '+html);
 assert.deepEqual([...html.matchAll(/Criteria source · PDF page (\d+)</g)].map(m=>Number(m[1])),pages,id+' wrong stages');
 if(pages[0]===33)assert(card.includes('78206018701')&&card.includes('78206018401')&&/institutional vial/i.test(card)&&/uveitis/i.test(html)&&!/non-preferred drug is not approved/i.test(html),id+' NDC or indication scope');
 if(pages[0]===1798)assert(/aplastic anemia/i.test(html)&&/interferon/i.test(html)&&!/For Non-Preferred Drug requests/i.test(html),id+' preferred generic step scope');
 if(pages[0]===305){assert.equal(String(r.qlAmount),'3');assert.equal(String(r.qlDays),'90');assert(/18 years of age or older/i.test(html)&&!/6-17 years of age|45 kg or greater|applies to Ajovy/i.test(html),id+' pediatric alternative transferred');}
 if(pages[0]===945)assert(/sarcoidosis/i.test(html)&&/off-label/i.test(html)&&/57894016001/.test(card)&&!/non-preferred drug is not approved/i.test(html),id+' Janssen scope');
}
console.log('PASS: four exact Banner rows, 37 named stages, product-specific conditional criteria and NDC evidence; raw flags preserved.');
const policy=read('_site/clinical-criteria/gl-589207.json');
assert.equal(api.matchingClinicalBranches(policy,{name:'Dapagliflozin',brands:['FARXIGA'],records:[{name:'Dapagliflozin'}]}).length,1,'Monotherapy selected combination products');
assert.equal(api.matchingClinicalBranches(policy,{name:'dapagliflozin',brands:['UNRELATED BRAND'],records:[{name:'dapagliflozin'}]}).length,0,'Unrelated brand received generic policy');
assert(!fs.readFileSync('_site/index.html','utf8').includes('Source-linked clinical reference.'));
assert(api.cardBranchMarkup({fields:{},criteria:[{text:'<script>alert(1)</script>'}],notes:[]}).includes('&lt;script&gt;'),'Clinical text is not escaped');
console.log('PASS: product-only clinical cards, 3-plan Xigduo pathways and AND/OR, no raw/admin/other-medication text, no guide duplication, preserved source/PA scope, reopen and escaping');
})().catch(e=>{console.error(e);process.exitCode=1});
