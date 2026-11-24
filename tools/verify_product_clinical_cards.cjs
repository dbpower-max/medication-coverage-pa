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
for(const plan of data.plans){
 api.state.planId=plan.id;
 const groups=api.planMedicationGroups();
 const acamprosate=groups.find(group=>group.statewideRecord?.id.endsWith(':statewide:formulary-9707'));
 assert(acamprosate, 'Missing statewide acamprosate in '+plan.id);
 const acamprosateCard=api.medicationGroupCard(acamprosate).split('<div class="card-source-access">')[0];
 assert(acamprosateCard.includes(plan.id==='banner-ufc' ? 'Banner formulary' : 'AHCCCS statewide reference. Exact-plan coverage and restrictions are unverified.'),
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

const policy=read('_site/clinical-criteria/gl-589207.json');
assert.equal(api.matchingClinicalBranches(policy,{name:'Dapagliflozin',brands:['FARXIGA'],records:[{name:'Dapagliflozin'}]}).length,1,'Monotherapy selected combination products');
assert.equal(api.matchingClinicalBranches(policy,{name:'dapagliflozin',brands:['UNRELATED BRAND'],records:[{name:'dapagliflozin'}]}).length,0,'Unrelated brand received generic policy');
assert(!fs.readFileSync('_site/index.html','utf8').includes('Source-linked clinical reference.'));
assert(api.cardBranchMarkup({fields:{},criteria:[{text:'<script>alert(1)</script>'}],notes:[]}).includes('&lt;script&gt;'),'Clinical text is not escaped');
console.log('PASS: product-only clinical cards, 3-plan Xigduo pathways and AND/OR, no raw/admin/other-medication text, no guide duplication, preserved source/PA scope, reopen and escaping');
})().catch(e=>{console.error(e);process.exitCode=1});
