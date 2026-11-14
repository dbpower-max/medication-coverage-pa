const fs=require('fs'),vm=require('vm'),zlib=require('zlib');
const assert=(ok,message)=>{if(!ok)throw Error(message)};
const data=JSON.parse(zlib.gunzipSync(fs.readFileSync('_site/data.json.gz')).toString('utf8'));
const plans=new Set(data.plans.map(x=>x.id));
assert(plans.size===3&&['az-complete-health','banner-ufc','uhc-community-az'].every(x=>plans.has(x)),'Wrong public plan set');
assert(data.statewideDrugList.length>=1400&&data.statewideDrugList.length<=1500,'Missing shared November statewide list');
assert(data.statewidePaCriteria.length>=400,'Missing shared November PA criteria index');
assert(data.statewideDrugList.every(x=>x.planId==='ahcccs-statewide'&&x.sourceEffective==='2026-11-01'),'Wrong statewide drug source');
assert(data.statewidePaCriteria.every(x=>x.sourceEffective==='2026-11-01'&&x.recordType==='policy_index'),'Wrong PA criteria index');
assert(data.medications.every(x=>x.planId!=='ahcccs-statewide'&&x.validation!=='mandated_statewide_minimum_with_plan_adoption_evidence'),'Duplicated statewide overlays in plan data');
assert(fs.existsSync('_site/sources/ahcccs-drug-list-2026-11-01.pdf'),'Statewide PDF is missing');
assert(fs.existsSync('_site/sources/ahcccs-ffs-pa-criteria-2026-11-01.pdf'),'Statewide PA PDF is missing');
const source=fs.readFileSync('_site/app.js','utf8');
const start=source.indexOf('  // Keep one immutable statewide source');
const end=source.indexOf('  function categoryOptions(',start);
assert(start>=0&&end>start,'Could not isolate app grouping implementation');
function model(input,planId='az-complete-health'){
 const ctx={normalize:s=>String(s||'').trim().toLocaleLowerCase(),state:{data:input,planId}};
 vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
 return {groups:()=>vm.runInContext('planMedicationGroups()',ctx),matches:(a,b)=>{ctx.a=a;ctx.b=b;return vm.runInContext('sameProductGroup(a,b)',ctx);}};
}
const glp=data.statewideDrugList.filter(r=>String(r.brand).toUpperCase()==='MOUNJARO');
assert(glp.length===1,'Expected one current statewide Mounjaro entry');
assert(glp[0].pa==='required'&&glp[0].preferred!=='preferred','Mounjaro authoritative PA/preference flags incorrect');
const live=model(data);
const groups=live.groups();
const mounjaro=groups.filter(g=>g.brands.some(b=>b.toLowerCase()==='mounjaro'));
assert(mounjaro.length===1,'Mounjaro still appears in multiple AZ plan groups: '+mounjaro.map(g=>g.label).join(' | '));
assert(mounjaro[0].isStatewide&&mounjaro[0].statewideRecord.pa==='required','Mounjaro does not inherit statewide PA');
assert(mounjaro[0].records.some(r=>/MOUNJARO \(SUBCUTANEOUS\)/i.test(r.name)),'October AZ plan notice not retained as supplement');
assert(mounjaro[0].records.some(r=>r.validation==='official_json_baseline_with_later_updates'),'Older ACH baseline record is not retained for source audit');
const mock=model({medications:[
  {id:'plan-notice',planId:'az-complete-health',recordType:'formulary',name:'MOUNJARO (SUBCUTANEOUS)',brand:'',preferred:'preferred'},
  {id:'plan-json',planId:'az-complete-health',recordType:'formulary',name:'TIRZEPATIDE SOLN AUTO-INJ',brand:'MOUNJARO',pa:'required'}],
  statewideDrugList:[{id:'state-1',planId:'ahcccs-statewide',recordType:'formulary',name:'TIRZEPATIDE SOLN AUTO-INJ',brand:'MOUNJARO',preferred:'not_specified',pa:'required'}]});
const mg=mock.groups();assert(mg.length===1&&mg[0].records.length===3&&mg[0].statewideRecord.pa==='required','Known equivalent products were not consolidated');
assert(!mock.matches({name:'DRUG ORAL TABLET',brands:['DRUG']},{name:'DRUG SOLN AUTO-INJ',brands:['DRUG']}),'Oral and injectable products incorrectly joined');
assert(!mock.matches({name:'DRUG TABLET ER',brands:['BRAND']},{name:'DRUG TABLET',brands:['BRAND']}),'Modified release incorrectly joined');
assert(!mock.matches({name:'DRUG TABLET 5 MG',brands:['BRAND']},{name:'DRUG TABLET 10 MG',brands:['BRAND']}),'Different strengths incorrectly joined');
console.log('PASS: '+data.statewideDrugList.length+' shared AHCCCS drug entries; '+data.statewidePaCriteria.length+' statewide PA index sections; 3 plan supplements; Mounjaro consolidated; route/release/strength protections');
