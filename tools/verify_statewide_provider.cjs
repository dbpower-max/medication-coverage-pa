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
// An older ACH JSON baseline record may or may not name Mounjaro.
// Retain any such original records when present, but never invent one.
const baselineRows=data.medications.filter(r=>r.planId==='az-complete-health'
  && r.validation==='official_json_baseline_with_later_updates'
  && (/mounjaro/i.test(r.name)||/mounjaro/i.test(r.brand||'')));
if(baselineRows.length) {
  const represented=new Set(mounjaro[0].records.map(r=>r.id));
  assert(baselineRows.every(r=>represented.has(r.id)),'Existing named Mounjaro baseline evidence was not linked');
}
console.log('MOUNJARO: '+mounjaro[0].records.map(r=>r.name+' ['+(r.validation||'statewide')+']').join(' + '));
const mock=model({medications:[
  {id:'plan-notice',planId:'az-complete-health',recordType:'formulary',name:'MOUNJARO (SUBCUTANEOUS)',brand:'',preferred:'preferred'},
  {id:'plan-json',planId:'az-complete-health',recordType:'formulary',name:'TIRZEPATIDE SOLN AUTO-INJ',brand:'MOUNJARO',pa:'required'}],
  statewideDrugList:[{id:'state-1',planId:'ahcccs-statewide',recordType:'formulary',name:'TIRZEPATIDE SOLN AUTO-INJ',brand:'MOUNJARO',preferred:'not_specified',pa:'required'}]});
const mg=mock.groups();assert(mg.length===1&&mg[0].records.length===3&&mg[0].statewideRecord.pa==='required','Known equivalent products were not consolidated');
assert(!mock.matches({name:'DRUG ORAL TABLET',brands:['DRUG']},{name:'DRUG SOLN AUTO-INJ',brands:['DRUG']}),'Oral and injectable products incorrectly joined');
assert(!mock.matches({name:'DRUG TABLET ER',brands:['BRAND']},{name:'DRUG TABLET',brands:['BRAND']}),'Modified release incorrectly joined');
assert(!mock.matches({name:'DRUG TABLET 5 MG',brands:['BRAND']},{name:'DRUG TABLET 10 MG',brands:['BRAND']}),'Different strengths incorrectly joined');

// Clinical source guidance must be actionable, limited to the verified product,
// and linked to the exact November source sections.
const guidance=data.statewideClinicalGuidance;
assert(guidance.length===2,'Expected two source-checked clinical guideline pilots');
function guideByCode(code){return guidance.find(g=>g.policyCode===code);}
const sg=guideByCode('GL-589207'), ins=guideByCode('GL-154074');
assert(sg&&ins,'Missing Jardiance or concentrated insulin guideline');
assert(sg.pathways.length===3&&ins.pathways.length===2,'Wrong clinical qualification branch count');
assert(sg.pathways.some(p=>p.all.some(r=>r.includes('1,500 mg daily for 90 days'))),'Metformin trial dose/duration not shown');
assert(sg.pathways.some(p=>/heart failure OR adult CKD/i.test(p.title)
  &&p.all.some(x=>x.includes('No metformin trial'))),'HF/CKD alternative pathway missing');
assert(ins.pathways.some(p=>p.all.some(x=>x.includes('insulin aspart OR insulin lispro'))
  &&p.all.some(x=>x.includes('Lantus'))),'Insulin prior therapy conditions missing');
assert(ins.pathways.some(p=>p.all.some(x=>x.includes('special circumstance'))),'Concentrated insulin rationale pathway missing');
assert(sg.sourcePage===1578&&ins.sourcePage===976,'Guideline page links incorrect');
const guidelineRuntime=source.slice(source.indexOf('  function clinicalGuidanceFor('),source.indexOf('  function medicationGroupCard('));
assert(guidelineRuntime.length>100,'Cannot find clinical guidance renderer');
const ui={
 normalize:s=>String(s||'').trim().toLowerCase(),
 escapeHtml:s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
 sourceHref:g=>g.sourceUrl+'#page='+g.sourcePage,
 state:{data},
 groupJ:{name:'EMPAGLIFLOZIN',brands:['JARDIANCE']},
 groupU:{name:'INSULIN REGULAR (HUMAN) SOLUTION PEN INJECTION',brands:['HUMULIN R U-500 KWIKPEN']},
 groupOther:{name:'INSULIN REGULAR',brands:['HUMULIN R U-100']}
};
vm.createContext(ui);
vm.runInContext(guidelineRuntime,ui);
const guideJ=vm.runInContext('clinicalGuidanceFor(groupJ)',ui);
const guideU=vm.runInContext('clinicalGuidanceFor(groupU)',ui);
assert(guideJ&&guideJ.policyCode==='GL-589207'&&guideU&&guideU.policyCode==='GL-154074','Exact medication guidance matching failed');
assert(vm.runInContext('clinicalGuidanceFor(groupOther)',ui)===null,'Wrong concentration inherited U-500 criteria');
const htmlJ=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(groupJ))',ui);
const htmlU=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(groupU))',ui);
assert(/metformin/i.test(htmlJ)&&/90 days/.test(htmlJ)&&/heart failure/i.test(htmlJ),'Jardiance clinician details not rendered');
assert(/Lantus/.test(htmlU)&&/concentrated insulin/.test(htmlU),'U-500 clinician details not rendered');
assert(/gl-589207/i.test(htmlJ)&&/gl-154074/i.test(htmlU),'Guideline source links not rendered');
const jardiance=data.statewideDrugList.find(r=>String(r.brand).toUpperCase()==='JARDIANCE');
const u500=data.statewideDrugList.find(r=>String(r.brand).toUpperCase()==='HUMULIN R U-500 KWIKPEN');
assert(jardiance&&jardiance.step==='specified'&&jardiance.pa!=='required','Jardiance list step status incorrectly converted into PA required');
assert(u500&&u500.pa==='required','U-500 drug list PA requirement missing');
console.log('PASS: Jardiance metformin dose/duration and HF/CKD alternatives; Humulin R U-500 insulin prerequisites or clinical need; source links and brand-specific matching');

console.log('PASS: '+data.statewideDrugList.length+' shared AHCCCS drug entries; '+data.statewidePaCriteria.length+' statewide PA index sections; 3 plan supplements; Mounjaro consolidated; route/release/strength protections');
