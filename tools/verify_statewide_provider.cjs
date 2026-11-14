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
assert(guidance.length===9,'Expected nine source-verified drug guidance records after stage-aware batch');
function guideByCode(code){return guidance.find(g=>g.policyCode===code);}
const sg=guideByCode('GL-589207'), ins=guideByCode('GL-154074');
assert(sg&&ins,'Missing Jardiance or concentrated insulin guideline');
const moun=guideByCode('GL-749236');
assert(moun&&moun.matchBrands.length===1&&moun.matchBrands[0]==='MOUNJARO','Incorrect Mounjaro identity/scope');
assert(moun.pathways.length===1&&moun.pathways[0].all.length===7,'Mounjaro must show all seven eligibility conditions');
assert(moun.pathways[0].all.some(x=>x.includes('A1c ≥6.5%')&&x.includes('MUST')),'Mounjaro A1c lab report missing');
assert(moun.pathways[0].all.some(x=>x.includes('paid claims')&&x.includes('1,500 mg/day')&&x.includes('90 days')),'Mounjaro metformin verification missing');
assert(moun.pathways[0].all.some(x=>x.includes('10 years old')),'Mounjaro minimum age missing');
assert(moun.pathways[0].all.some(x=>x.includes('weight loss')),'Mounjaro indication limitation missing');
assert(moun.pathways[0].all.some(x=>x.includes('DPP-4'))&&moun.pathways[0].all.some(x=>x.includes('another GLP-1')),'Mounjaro concurrency criteria missing');
assert(moun.sourcePage===718&&moun.sourceLastPage===719&&moun.approvalDuration==='12 months','Mounjaro approval duration or source page incorrect');
const truli=guidance.find(g=>g.id==='gl-749236-trulicity');
assert(truli&&truli.policyCode==='GL-749236','Trulicity source guideline not linked');
assert(truli.matchBrands.length===1&&truli.matchBrands[0]==='TRULICITY','Trulicity identity not specific');
assert(truli.pathways.length===1&&truli.pathways[0].all.length===7,'Trulicity must inherit all seven source criteria');
assert(JSON.stringify(truli.pathways)===JSON.stringify(moun.pathways),'Same source GLP-1 branch has different Trulicity clinical requirements');
assert(truli.sourcePage===718&&truli.sourceLastPage===719,'Trulicity source page incorrect');

const vict=guidance.find(g=>g.id==='gl-749236-victoza');
assert(vict&&vict.policyCode==='GL-749236'&&vict.matchBrands.length===1&&vict.matchBrands[0]==='VICTOZA','Victoza source or brand identity wrong');
assert(JSON.stringify(vict.pathways)===JSON.stringify(moun.pathways),'Victoza clinical criteria differ from shared source branch');
assert(vict.sourcePage===718&&vict.sourceLastPage===719,'Victoza page reference incorrect');

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
ui.groupM={name:'TIRZEPATIDE SOLN AUTO-INJ',brands:['MOUNJARO']};
ui.groupZ={name:'TIRZEPATIDE SOLN AUTO-INJ',brands:['ZEPBOUND']};
const guideM=vm.runInContext('clinicalGuidanceFor(groupM)',ui);
assert(guideM&&guideM.policyCode==='GL-749236','Mounjaro not matched to exact rule');
assert(vm.runInContext('clinicalGuidanceFor(groupZ)',ui)===null,'Mounjaro diabetes criteria incorrectly applied to Zepbound');
const htmlM=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(groupM))',ui);
ui.groupT={name:'DULAGLUTIDE',brands:['TRULICITY']};
ui.groupO={name:'SEMAGLUTIDE',brands:['OZEMPIC']};
const guideT=vm.runInContext('clinicalGuidanceFor(groupT)',ui);
assert(guideT&&guideT.id==='gl-749236-trulicity','Trulicity criteria did not attach to exact brand');
assert(vm.runInContext('clinicalGuidanceFor(groupO)',ui)===null,'Trulicity preferred-branch guidance incorrectly applied to Ozempic');
ui.groupV={name:'LIRAGLUTIDE INJECTION',brands:['VICTOZA']};
ui.groupL={name:'LIRAGLUTIDE INJECTION',brands:['SAXENDA']};
const guidelineV=vm.runInContext('clinicalGuidanceFor(groupV)',ui);
assert(guidelineV&&guidelineV.id==='gl-749236-victoza','Victoza did not map to its confirmed clinical criteria');
assert(vm.runInContext('clinicalGuidanceFor(groupL)',ui)===null,'Incorrectly applied Victoza T2DM criteria to Saxenda');
const htmlV=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(groupV))',ui);
assert(/A1c ≥6.5%/.test(htmlV)&&/90 days/.test(htmlV)&&/paid claims/.test(htmlV),'Victoza clinical and metformin verification missing');

const htmlT=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(groupT))',ui);
assert(/A1c ≥6.5%/.test(htmlT)&&/paid claims/.test(htmlT)&&/DPP-4/.test(htmlT)&&/12 months/.test(htmlT),'Trulicity full source requirements not rendered');
assert(/A1c ≥6.5%/.test(htmlM)&&/90 days/.test(htmlM)&&/DPP-4/.test(htmlM),'Clinical Mounjaro requirements not rendered');
assert(/gl-749236/.test(htmlM)&&/12 months/.test(htmlM),'Mounjaro guideline link or approval duration missing');
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
const trulicityState=data.statewideDrugList.find(r=>String(r.brand).toUpperCase()==='TRULICITY');
assert(trulicityState,'Trulicity statewide entry missing');
const fzg=guideByCode('GL-589207') && guidance.find(g=>g.id==='gl-589207-farxiga');
assert(fzg&&fzg.policyCode==='GL-589207'&&JSON.stringify(fzg.matchBrands)===JSON.stringify(['FARXIGA']),'Farxiga-specific guidance not present');
assert(fzg.pathways.length===2,'Both Farxiga qualification pathways required');
assert(fzg.pathways[0].all.some(x=>x.includes('1,500 mg/day for 90 days')),'Farxiga metformin threshold missing');
assert(fzg.pathways[1].all.some(x=>x.includes('NYHA class II')&&x.includes('preserved ejection fraction')),'Farxiga HF functional class/EF criteria missing');
assert(fzg.pathways[1].all.some(x=>x.includes('No metformin trial')),'Farxiga CKD/HF exception missing');
assert(/Generic dapagliflozin requests/.test(fzg.guidelineCaution),'Farxiga generic-specific rule not disclosed');
ui.groupF={name:'DAPAGLIFLOZIN TABLET',brands:['FARXIGA']};
ui.groupX={name:'DAPAGLIFLOZIN-METFORMIN TABLET',brands:['XIGDUO XR']};
assert(vm.runInContext('clinicalGuidanceFor(groupF)',ui)?.id==='gl-589207-farxiga','Farxiga brand mapping missing');
assert(vm.runInContext('clinicalGuidanceFor(groupX)',ui)===null,'Farxiga criteria leaked to Xigduo');
const htmlF=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(groupF))',ui);
assert(/NYHA/.test(htmlF)&&/90 days/.test(htmlF)&&/gl-589207/.test(htmlF),'Farxiga source-based clinical details not rendered');

const aw=guidance.find(g=>g.id==='gl-669273-awiqli');
const sol=guidance.find(g=>g.id==='gl-398215-soliqua');
const xul=guidance.find(g=>g.id==='gl-398215-xultophy');
assert(aw&&sol&&xul,'Missing one of the stage-specific source guidelines');
assert(aw.stages.length===2&&sol.stages.length===2&&xul.stages.length===2,'Both approval stages required');
assert(aw.sourcePage===195&&aw.sourceLastPage===197&&aw.policyCode==='GL-669273','Awiqli source location wrong');
assert(sol.sourcePage===370&&xul.sourcePage===371&&sol.policyCode==='GL-398215'&&xul.policyCode==='GL-398215','Combined-insulin GLP-1 guideline page mismatch');
assert(aw.stages[0].all.some(x=>typeof x==='object'&&x.any?.length===2),'Awiqli requires a nested alternative criterion');
assert(aw.stages[0].all.some(x=>typeof x==='string'&&x.includes('18 years')),'Awiqli age requirement missing');
assert(aw.stages[1].all.some(x=>x.includes('Positive clinical response')),'Awiqli renewal requirement missing');
assert(!sol.stages[0].all.some(x=>x.includes('failure, intolerance, or contraindication to Soliqua')),'Soliqua erroneously needs failure to itself');
assert(xul.stages[0].all.some(x=>x.includes('failure, intolerance, or contraindication to Soliqua')),'Xultophy first-use Soliqua prerequisite missing');
assert(xul.stages[1].all.some(x=>x.includes('positive clinical response')),'Xultophy renewal requirement missing');
ui.awGroup={name:'INSULIN ICODEC',brands:['AWIQLI']};
ui.solGroup={name:'INSULIN GLARGINE/LIXISENATIDE',brands:['SOLIQUA 100/33']};
ui.xulGroup={name:'INSULIN DEGLUDEC/LIRAGLUTIDE',brands:['XULTOPHY 100/3.6']};
const htmlAw=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(awGroup))',ui);
const htmlSol=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(solGroup))',ui);
const htmlXul=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(xulGroup))',ui);
assert(/Initial authorization/.test(htmlAw)&&/Reauthorization/.test(htmlAw)&&/ONE of the following/.test(htmlAw),'Awiqli staged/nested logic not rendered');
assert(/90-day supply/.test(htmlAw)&&/once weekly|weekly dosing/i.test(htmlAw),'Awiqli treatment barriers or counseling missing');
assert(/GLP-1/.test(htmlSol)&&/DPP-4/.test(htmlSol)&&/Reauthorization/.test(htmlSol),'Soliqua clinical stage criteria missing');
assert(/failure, intolerance, or contraindication to Soliqua/.test(htmlXul),'Xultophy Soliqua pretrial missing');
assert(!htmlAw.includes('Qualifying pathways — any ONE:'),'Renewal criteria mistakenly rendered as initial alternative');
assert(htmlAw.includes('gl-669273')&&htmlSol.includes('gl-398215')&&htmlXul.includes('gl-398215'),'Source links missing');
console.log('PASS: Three stage-aware products with initial/renewal criteria, nested ONE-of logic, source pages, and legacy-guide compatibility');

console.log('PASS: Jardiance metformin dose/duration and HF/CKD alternatives; Humulin R U-500 insulin prerequisites or clinical need; source links and brand-specific matching');

console.log('PASS: '+data.statewideDrugList.length+' shared AHCCCS drug entries; '+data.statewidePaCriteria.length+' statewide PA index sections; 3 plan supplements; Mounjaro consolidated; route/release/strength protections');
