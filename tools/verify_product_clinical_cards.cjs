const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const read=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=read('_site/data.json.gz');
for(const file of Object.values(data.planDataFiles||{})) data.medications.push(...read('_site/'+file.split('?')[0].replace(/^\.\//,'')));
delete data.planDataFiles;
const source=fs.readFileSync('_site/app.js','utf8');
const ctx={Intl,console,document:{addEventListener:()=>{}},fetch:async url=>({ok:true,json:async()=>read('_site/'+url.split('?')[0].replace(/^\.\//,'')),text:async()=>fs.readFileSync('_site/'+url.split('?')[0].replace(/^\.\//,''),'utf8')})};
vm.createContext(ctx);vm.runInContext(source.replace("document.addEventListener('DOMContentLoaded', init);",'globalThis.api={state,planMedicationGroups,medicationGroupCard,populateCardClinical,matchingClinicalBranches,cardBranchMarkup,cardClinicalGroups,clinicalGuidanceFor};'),ctx);
const api=ctx.api;api.state.data=data;
function targetFor(group){const target={innerHTML:'',isConnected:true};return {target,details:{open:true,dataset:{cardClinical:group.key||group.label},querySelector:selector=>selector==='.card-pa-references'?{innerHTML:''}:target}};}
(async()=>{
for(const plan of data.plans){
 api.state.planId=plan.id;
 const groups=api.planMedicationGroups();
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

const policy=read('_site/clinical-criteria/gl-589207.json');
assert.equal(api.matchingClinicalBranches(policy,{name:'Dapagliflozin',brands:['FARXIGA'],records:[{name:'Dapagliflozin'}]}).length,1,'Monotherapy selected combination products');
assert.equal(api.matchingClinicalBranches(policy,{name:'dapagliflozin',brands:['UNRELATED BRAND'],records:[{name:'dapagliflozin'}]}).length,0,'Unrelated brand received generic policy');
assert(!fs.readFileSync('_site/index.html','utf8').includes('Source-linked clinical reference.'));
assert(api.cardBranchMarkup({fields:{},criteria:[{text:'<script>alert(1)</script>'}],notes:[]}).includes('&lt;script&gt;'),'Clinical text is not escaped');
console.log('PASS: product-only clinical cards, 3-plan Xigduo pathways and AND/OR, no raw/admin/other-medication text, no guide duplication, preserved source/PA scope, reopen and escaping');
})().catch(e=>{console.error(e);process.exitCode=1});
