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
assert(guidance.length>=9,'Previously reviewed clinical guides missing');
const baselineIds=['gl-589207-jardiance','gl-154074-humulin-u500','gl-749236-mounjaro','gl-749236-trulicity','gl-749236-victoza','gl-589207-farxiga','gl-669273-awiqli','gl-398215-soliqua','gl-398215-xultophy'];
const ids=guidance.map(g=>g.id);
assert(new Set(ids).size===ids.length,'Duplicate medication clinical guide id');
assert(baselineIds.every(id=>ids.includes(id)),'Previously source-checked medication guide lost');
assert(guidance.every(g=>g.sourceChecks?.length>=3),'A clinical guide lacks three source phrase verifications');
console.log('Source-verified clinical products: '+guidance.length+'; distinct policy sections: '+new Set(guidance.map(g=>g.policyCode)).size);
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

const simpleGuides=[
 ['gl-547232-vitamin-d','GL-547232','VITAMIN D'],
 ['gl-550187-vitamin-b12','GL-550187','VITAMIN B-12'],
 ['gl-547233-vitamin-c','GL-547233','VITAMIN C'],
 ['gl-547234-calcium-vitamin-d','GL-547234','CALCIUM/VITAMIN D']
];
for(const [id,code,name] of simpleGuides){
 const guide=guidance.find(g=>g.id===id);
 assert(guide&&guide.policyCode===code&&guide.matchNames?.includes(name),'Missing exact generic-product source guide: '+id);
 assert(guide.stages?.length===2&&guide.stages[0].title==='Initial authorization'&&guide.stages[1].title==='Reauthorization','Incorrect vitamin initial/renewal stages: '+id);
 assert(guide.stages[0].all[0].includes('laboratory values')&&guide.stages[1].all[0].includes('improvement'),'Vitamin lab evidence incomplete: '+id);
 ui.vitaminGroup={name,brands:[]};
 const g=vm.runInContext('clinicalGuidanceFor(vitaminGroup)',ui);
 assert(g?.id===id,'Exact generic-name lookup missed '+id);
 const h=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(vitaminGroup))',ui);
 assert(h.includes('Initial authorization')&&h.includes('Reauthorization')&&h.includes(code.toLowerCase()),'Vitamin criteria not shown: '+id);
}
ui.vitaminD3Group={name:'VITAMIN D3 2000 UNIT TABLET',brands:[]};
ui.calciumGroup={name:'CALCIUM CARBONATE',brands:[]};
assert(vm.runInContext('clinicalGuidanceFor(vitaminD3Group)',ui)===null,'Loose ingredient match applied to unconfirmed Vitamin D3 form');
assert(vm.runInContext('clinicalGuidanceFor(calciumGroup)',ui)===null,'Calcium-only exemption overwritten with combo-product PA');
const inhalers=[
 ['gl-589212-arnuity','ARNUITY ELLIPTA'],
 ['gl-589212-asmanex','ASMANEX TWISTHALER'],
 ['gl-589212-qvar','QVAR REDIHALER']
];
for(const [id,brand] of inhalers){
 const guide=guidance.find(g=>g.id===id);
 assert(guide&&guide.matchBrands.includes(brand)&&guide.policyCode==='GL-589212','Preferred inhaler drug identity missing: '+id);
 assert(guide.pathways?.length===1&&guide.pathways[0].all[0].includes('Diagnosis of asthma'),'Asthma source criterion missing');
 ui.inhalerGroup={name:'INHALED CORTICOSTEROID',brands:[brand]};
 assert(vm.runInContext('clinicalGuidanceFor(inhalerGroup)',ui)?.id===id,'Inhaler exact brand rule failed: '+id);
}
ui.nonpreferredInhaler={name:'CICLESONIDE INHALER',brands:['ALVESCO']};
assert(vm.runInContext('clinicalGuidanceFor(nonpreferredInhaler)',ui)===null,'Preferred-drug guideline incorrectly transferred to nonpreferred Alvesco');
assert(source.includes('needsPa || hasStep || guidance'),'Clinically indexed preferred drug not accessible when PDL does not flag PA');
assert(guidance.length>=16&&new Set(guidance.map(g=>g.policyCode)).size>=10,'New source policy coverage not retained');

const sgProducts=[
 ['gl-589207-synjardy','SYNJARDY'],
 ['gl-589207-synjardy-xr','SYNJARDY XR'],
 ['gl-589207-invokana','INVOKANA']
];
for(const [id,brand] of sgProducts){
  const guide=guidance.find(g=>g.id===id);
  assert(guide && guide.policyCode==='GL-589207' && guide.matchBrands.length===1 && guide.matchBrands[0]===brand,'SGLT2 product-specific criteria missing: '+id);
  assert(guide.pathways.length===1 && guide.pathways[0].all.some(s=>s.includes('10 years old')),'Age threshold missing: '+id);
  assert(guide.pathways[0].all.some(s=>s.includes('1500mg daily for 90 days')),'Metformin trial threshold missing: '+id);
  assert(guide.sourcePage>=1579 && guide.sourceLastPage<=1580 && guide.approvalDuration==='12 months','SGLT2 source pages or approval length incorrect: '+id);
  ui.sgBrandGroup={name:'SGLT-2 INHIBITOR',brands:[brand]};
  const matched=vm.runInContext('clinicalGuidanceFor(sgBrandGroup)',ui);
  assert(matched?.id===id,'Wrong SGLT2 matching for '+brand);
}
const syn=guidance.find(g=>g.id==='gl-589207-synjardy');
const synxr=guidance.find(g=>g.id==='gl-589207-synjardy-xr');
const inv=guidance.find(g=>g.id==='gl-589207-invokana');
const extra=arr=>arr.some(s=>s.includes('Farxiga')&&s.includes('Jardiance'));
assert(!extra(syn.pathways[0].all),'Synjardy must not inherit Synjardy XR exclusive dual-failure prerequisite');
assert(extra(synxr.pathways[0].all),'Synjardy XR must have both additional prior-drug requirements');
assert(extra(inv.pathways[0].all),'Invokana must have dual-failure requirement');
ui.sgUnrelated={name:'EMPAGLIFLOZIN/METFORMIN TABLET',brands:['GLYXAMBI']};
assert(vm.runInContext('clinicalGuidanceFor(sgUnrelated)',ui)===null,'Wrong SGLT2 clinical rule attached to unrelated product');
console.log('PASS: Synjardy, Synjardy XR, Invokana qualification thresholds, source pages and isolated trial rules');

console.log('PASS: Four vitamin initial/renewal guides and three preferred inhaler asthma rules; no unrelated product matching');

console.log('PASS: Jardiance metformin dose/duration and HF/CKD alternatives; Humulin R U-500 insulin prerequisites or clinical need; source links and brand-specific matching');

console.log('PASS: '+data.statewideDrugList.length+' shared AHCCCS drug entries; '+data.statewidePaCriteria.length+' statewide PA index sections; 3 plan supplements; Mounjaro consolidated; route/release/strength protections');


// Regression gate for the five most recently released clinical products.
// These assertions deliberately test exact brand identity and source-backed
// qualification logic without treating statewide guidance as plan coverage.
const recentClinicalChecks=[
  {id:'gl-108675-epsolay',code:'GL-108675',brand:'EPSOLAY',page:581,
   phrases:['Diagnosis of rosacea','inflammatory lesions','30-day supply']},
  {id:'gl-108624-monurol',code:'GL-108624',brand:'MONUROL',page:1199,
   phrases:['culture and sensitivity','Ciprofloxacin','Nitrofurantoin']},
  {id:'gl-107465-twyneo',code:'GL-107465',brand:'TWYNEO',page:1881,
   phrases:['9 years of age','acne vulgaris','topical erythromycin']},
  {id:'gl-107424-korsuva',code:'GL-107424',brand:'KORSUVA',page:1047,
   phrases:['hemodialysis','pruritus','Reauthorization']},
  {id:'gl-107454-verkazia',code:'GL-107454',brand:'VERKAZIA',page:1945,
   phrases:['vernal keratoconjunctivitis','mast cell stabilizer','Reauthorization']}
];
for(const spec of recentClinicalChecks){
  const guide=guidance.find(g=>g.id===spec.id);
  assert(guide&&guide.policyCode===spec.code,'Recent guide missing: '+spec.id);
  assert(guide.sourcePage===spec.page,'Wrong policy source page: '+spec.id);
  assert(JSON.stringify(guide.matchBrands)===JSON.stringify([spec.brand]),
    'Clinical guide may match unintended brand: '+spec.id);
  assert(!guide.matchNames?.length,'Recent brand guide should not match generic: '+spec.id);
  assert(guide.sourceChecks.length>=3,'Insufficient source checks: '+spec.id);
  const raw=fs.readFileSync('_site/'+guide.sourceTextUrl.replace(/^\/+/,''),'utf8');
  const compact=s=>s.replace(/\s+/g,' ').toLowerCase();
  for(const phrase of spec.phrases){
    assert(compact(raw).includes(compact(phrase)),'Missing independent source phrase '+phrase);
  }
  ui.recentGroup={name:'UNRELATED GENERIC',brands:[spec.brand]};
  assert(vm.runInContext('clinicalGuidanceFor(recentGroup)',ui)?.id===spec.id,
    'Exact brand failed to attach guide: '+spec.brand);
  ui.recentGroup={name:'UNRELATED GENERIC',brands:[spec.brand+' XR']};
  assert(vm.runInContext('clinicalGuidanceFor(recentGroup)',ui)===null,
    'Clinical criteria leaked to a modified brand: '+spec.brand);
}
const eps=guidance.find(g=>g.id==='gl-108675-epsolay');
assert(eps.pathways.length===1&&eps.pathways[0].all.length===3,
  'Epsolay must require all three rosacea criteria');
const mon=guidance.find(g=>g.id==='gl-108624-monurol');
assert(mon.pathways.length===2&&mon.pathways[1].all[0].any.length===2,
  'Monurol alternatives or antibiotic ONE-of logic lost');
const twy=guidance.find(g=>g.id==='gl-107465-twyneo');
assert(twy.pathways[0].all.some(x=>x.includes('ALL of:')&&x.includes('topical tretinoin')),
  'Twyneo four-treatment failure requirement lost');
for(const id of ['gl-107424-korsuva','gl-107454-verkazia']){
 const guide=guidance.find(g=>g.id===id);
 assert(guide.stages?.length===2,'Initial and renewal stages required: '+id);
 assert(guide.stages[0].all.some(x=>typeof x==='object'&&x.any?.length>=2),
   'Missing initial alternative criteria: '+id);
 assert(guide.stages[1].all.some(x=>typeof x==='string'&&/positive clinical response/i.test(x)),
   'Missing renewal response criterion: '+id);
}
console.log('PASS: Five recent brand-specific source/logic regressions, exact matching, initial/renewal stages');


// Independent source/identity/branch regression for Nadolol, Zimhi and Hyftor.
const nextChecks=[
 {id:'gl-109903-nadolol',code:'GL-109903',page:1220,name:'NADOLOL',
  phrases:['PA required for patients 18 years of age or older','History of failure, contraindication, or intolerance to 3 of the following','sotalol HCl']},
 {id:'gl-114472-zimhi',code:'GL-114472',page:2110,brand:'ZIMHI',
  phrases:['Product Name:Zimhi','History of failure, or intolerance to preferred naloxone products','Kloxxado']},
 {id:'gl-114463-hyftor',code:'GL-114463',page:848,brand:'HYFTOR',
  phrases:['Diagnosis of facial angiofibroma associated with tuberous sclerosis complex','Patient is 6 years of age or older','Therapy Stage','Reauthorization']}
];
for(const spec of nextChecks){
 const guide=guidance.find(g=>g.id===spec.id);
 assert(guide&&guide.policyCode===spec.code&&guide.sourcePage===spec.page,'Missing or mismatched new guide '+spec.id);
 assert(guide.sourceChecks.length>=3,'Missing source checks '+spec.id);
 assert(spec.brand?JSON.stringify(guide.matchBrands)===JSON.stringify([spec.brand])&&!guide.matchNames?.length:
  JSON.stringify(guide.matchNames)===JSON.stringify([spec.name])&&!guide.matchBrands?.length,'Overbroad identity '+spec.id);
 const raw=fs.readFileSync('_site/'+guide.sourceTextUrl.replace(/^\//,''),'utf8');
 const compact=s=>s.replace(/\s+/g,' ').toLowerCase();
 for(const phrase of spec.phrases) assert(compact(raw).includes(compact(phrase)),'Missing raw phrase '+spec.id+': '+phrase);
 ui.newClinicalGroup={name:spec.name||'UNRELATED GENERIC',brands:spec.brand?[spec.brand]:[]};
 assert(vm.runInContext('clinicalGuidanceFor(newClinicalGroup)',ui)?.id===spec.id,'Guide fails exact match '+spec.id);
 ui.newClinicalGroup={name:(spec.name||'UNRELATED GENERIC')+' XR',brands:spec.brand?[spec.brand+' XR']:[]};
 assert(vm.runInContext('clinicalGuidanceFor(newClinicalGroup)',ui)===null,'Guide leaked to variant '+spec.id);
}
const nad=guidance.find(g=>g.id==='gl-109903-nadolol');
assert(nad.pathways.length===1&&nad.pathways[0].all.some(x=>x.includes('THREE of:')&&x.includes('sotalol HCl')),'Nadolol 3-agent threshold lost');
const zim=guidance.find(g=>g.id==='gl-114472-zimhi');
assert(zim.pathways.length===1&&zim.pathways[0].all.every(x=>!x.includes('contraindication')),'Zimhi source does not authorize contraindication');
const hyf=guidance.find(g=>g.id==='gl-114463-hyftor');
assert(hyf.stages.length===2&&hyf.stages[0].all.length===4&&hyf.stages[1].all.length===1&&
 hyf.stages[1].all[0].includes('positive clinical response'),'Hyftor initial/renewal branches lost');
console.log('PASS: Nadolol, Zimhi, Hyftor source/brand/stage regression');


const additionalGuideSpecs=[
 {id:'gl-105529-lyrica',brand:'LYRICA',code:'GL-105529',pages:[1143,1146],paths:5},
 {id:'gl-105529-lyrica-cr',brand:'LYRICA CR',code:'GL-105529',pages:[1146,1147],paths:2},
 {id:'gl-108674-glycopyrrolate-brands',brand:'CUVPOSA',code:'GL-108674',pages:[724,725],paths:1}
];
for(const spec of additionalGuideSpecs){
 const guide=guidance.find(g=>g.id===spec.id);
 assert(guide&&guide.policyCode===spec.code&&guide.sourcePage===spec.pages[0]&&guide.sourceLastPage===spec.pages[1],'New guide page/code mismatch '+spec.id);
 assert(guide.pathways.length===spec.paths&&guide.sourceChecks.length>=3,'Incomplete guide logic '+spec.id);
 const raw=fs.readFileSync('_site/'+guide.sourceTextUrl.replace(/^\//,''),'utf8').replace(/\s+/g,' ').toLowerCase();
 for(const phrase of guide.sourceChecks)assert(raw.includes(phrase.replace(/\s+/g,' ').toLowerCase()),'Source phrase absent '+spec.id+': '+phrase);
 ui.newClinicalGroup={name:'UNRELATED PRODUCT',brands:[spec.brand]};
 assert(vm.runInContext('clinicalGuidanceFor(newClinicalGroup)',ui)?.id===spec.id,'Exact brand does not resolve '+spec.id);
 ui.newClinicalGroup={name:'UNRELATED PRODUCT',brands:[spec.brand+' XR']};
 assert(vm.runInContext('clinicalGuidanceFor(newClinicalGroup)',ui)===null,'Brand leaks into variant '+spec.id);
}
const lyr=guidance.find(g=>g.id==='gl-105529-lyrica');
assert(lyr.pathways[0].title==='Seizure disorder'&&lyr.pathways.slice(1).every(p=>p.all.some(x=>x.any?.length===2)),'Lyrica indication-specific alternatives lost');
const lyrcr=guidance.find(g=>g.id==='gl-105529-lyrica-cr');
assert(lyrcr.pathways[0].all.some(x=>x.any?.length===2)&&lyrcr.pathways[1].all.every(x=>!x.any),'Lyrica CR DPN/PHN branch difference lost');
const gly=guidance.find(g=>g.id==='gl-108674-glycopyrrolate-brands');
assert(JSON.stringify(gly.matchBrands)===JSON.stringify(['CUVPOSA','DARTISLA ODT','ROBINUL','ROBINUL FORTE']),'Glycopyrrolate brand scope changed');
console.log('PASS: Lyrica, Lyrica CR and oral glycopyrrolate source and exact-brand regression');

// Cross-product negative controls: brand Lyrica criteria must never attach to
// generic pregabalin or Lyrica CR; oral glycopyrrolate criteria must never
// attach to generic oral solution or any injectable glycopyrrolate strength.
const negativeGuideCases=[
 {name:'PREGABALIN CAPSULE',brands:['PREGABALIN'],forbidden:['gl-105529-lyrica','gl-105529-lyrica-cr']},
 {name:'PREGABALIN TABLET ER',brands:['LYRICA CR'],forbidden:['gl-105529-lyrica']},
 {name:'PREGABALIN CAPSULE',brands:['LYRICA'],forbidden:['gl-105529-lyrica-cr']},
 {name:'GLYCOPYRROLATE ORAL SOLUTION',brands:['GLYCOPYRROLATE'],forbidden:['gl-108674-glycopyrrolate-brands']},
 {name:'GLYCOPYRROLATE INJECTION 0.6 MG/3 ML',brands:['GLYCOPYRROLATE'],forbidden:['gl-108674-glycopyrrolate-brands']},
 {name:'GLYCOPYRROLATE INJECTION 0.6 MG/3 ML',brands:[],forbidden:['gl-108674-glycopyrrolate-brands']}
];
for(const spec of negativeGuideCases){
 ui.negativeClinicalGroup={name:spec.name,brands:spec.brands};
 const matched=vm.runInContext('clinicalGuidanceFor(negativeClinicalGroup)',ui);
 assert(!matched||!spec.forbidden.includes(matched.id),
   'Cross-route or cross-form clinical criteria leak: '+spec.name+' / '+spec.brands.join(','));
}
console.log('PASS: Lyrica IR/CR and glycopyrrolate oral/injectable negative identity controls');


const alphaGuides=[
 {id:'gl-105169-intron-a',brand:'INTRON A',duration:'12 months',count:13},
 {id:'gl-105169-alferon-n',brand:'ALFERON N',duration:'8 weeks',count:1}
];
for(const spec of alphaGuides){
 const guide=guidance.find(g=>g.id===spec.id);
 assert(guide&&guide.policyCode==='GL-105169'&&guide.sourcePage===80&&guide.sourceLastPage===83,'Alpha interferon policy/page mismatch '+spec.id);
 assert(guide.approvalDuration===spec.duration&&guide.pathways.length===spec.count,'Alpha interferon duration/OR branches mismatch '+spec.id);
 assert(guide.matchBrands.length===1&&guide.matchBrands[0]===spec.brand&&guide.sourceChecks.length>=3,'Alpha interferon exact brand/source checks mismatch '+spec.id);
 const raw=fs.readFileSync('_site/'+guide.sourceTextUrl.replace(/^\//,''),'utf8').replace(/\s+/g,' ').toLowerCase();
 for(const phrase of guide.sourceChecks)assert(raw.includes(phrase.replace(/\s+/g,' ').toLowerCase()),'Alpha interferon source phrase absent '+spec.id+': '+phrase);
 ui.alphaClinicalGroup={name:'UNRELATED MEDICATION',brands:[spec.brand]};
 assert(vm.runInContext('clinicalGuidanceFor(alphaClinicalGroup)',ui)?.id===spec.id,'Alpha interferon exact brand match missing '+spec.id);
 ui.alphaClinicalGroup={name:'UNRELATED MEDICATION',brands:[spec.brand+' XR']};
 assert(vm.runInContext('clinicalGuidanceFor(alphaClinicalGroup)',ui)===null,'Alpha interferon fuzzy brand leakage '+spec.id);
}
ui.alphaClinicalGroup={name:'INTERFERON ALFA',brands:['INTERFERON ALFA-2B']};
assert(vm.runInContext('clinicalGuidanceFor(alphaClinicalGroup)',ui)===null,'Generic interferon should not inherit brand-only policy');
console.log('PASS: Intron A and Alferon N source, OR branches, durations, exact brand and negative matching');


// Adaptive sprint batch: direct source, exact identity/route, and branching checks.
const adaptiveSpecs=[
 ['gl-117636-eucrisa','GL-117636',604,605,'EUCRISA','12 months'],
 ['gl-117633-daliresp','GL-117633',440,441,'DALIRESP','12 months'],
 ['gl-110773-ranexa','GL-110773',1452,1453,'RANEXA','12 months'],
 ['gl-110773-ranolazine-generic','GL-110773',1452,1453,null,'12 months'],
 ['gl-110773-aspruzyo-sprinkle','GL-110773',1453,1454,'ASPRUZYO SPRINKLE','12 months'],
 ['gl-117420-lidoderm','GL-117420',1083,1084,'LIDODERM','12 months'],
 ['gl-113527-tarpeyo','GL-113527',1767,1768,'TARPEYO','9 months'],
 ['gl-113529-livtencity','GL-113529',1096,1097,'LIVTENCITY','8 weeks'],
 ['gl-120432-pedmark','GL-120432',1380,1381,'PEDMARK','12 months'],
 ['gl-116131-firdapse','GL-116131',682,683,'FIRDAPSE','12 months'],
 ['gl-116190-dojolvi','GL-116190',464,465,'DOJOLVI','12 months'],
 ['gl-116122-orkambi','GL-116122',1343,1344,'ORKAMBI','12 months']
];
const adaptiveCompact=s=>s.replace(/\s+/g,' ').toLowerCase();
for(const [id,code,startPage,endPage,brand,duration] of adaptiveSpecs){
 const guide=guidance.find(g=>g.id===id);
 assert(guide&&guide.policyCode===code&&guide.sourcePage===startPage&&guide.sourceLastPage===endPage,
   'Adaptive guide policy/page mismatch '+id);
 assert(guide.approvalDuration===duration&&guide.sourceChecks.length>=3,
   'Adaptive guide duration/phrase count mismatch '+id);
 const raw=adaptiveCompact(fs.readFileSync('_site/'+guide.sourceTextUrl.replace(/^\//,''),'utf8'));
 for(const phrase of guide.sourceChecks){
  assert(raw.includes(adaptiveCompact(phrase)),'Adaptive raw phrase mismatch '+id+' / '+phrase);
 }
 assert(brand
   ? guide.matchBrands?.length===1&&guide.matchBrands[0]===brand&&!guide.matchNames?.length
   : JSON.stringify(guide.matchNames)===JSON.stringify(['RANOLAZINE'])&&!guide.matchBrands?.length,
   'Adaptive guide has overbroad/mismatched identity '+id);
 ui.adaptiveGroup={name:brand?'UNRELATED GENERIC MEDICATION':'RANOLAZINE',brands:brand?[brand]:[]};
 assert(vm.runInContext('clinicalGuidanceFor(adaptiveGroup)',ui)?.id===id,
   'Exact adaptive guide matching failed '+id);
 ui.adaptiveGroup={name:brand?'UNRELATED GENERIC MEDICATION':'RANOLAZINE EXTENDED RELEASE',brands:brand?[brand+' EXTRA']:[]};
 assert(vm.runInContext('clinicalGuidanceFor(adaptiveGroup)',ui)===null,
   'Adaptive guide leaked into other name/form '+id);
}
const adaptiveBy=id=>guidance.find(g=>g.id===id);
const e=adaptiveBy('gl-117636-eucrisa');
assert(e.pathways.length===1&&e.pathways[0].all.length===2&&e.pathways[0].all[1].any.length===2,
  'Eucrisa age-dependent calcineurin OR branch missing');
const dl=adaptiveBy('gl-117633-daliresp');
assert(dl.stages.length===2&&dl.stages[0].all.length===3&&dl.stages[1].all.length===1,
  'Daliresp initial/renewal requirement count incorrect');
const ra=adaptiveBy('gl-110773-ranexa'),rg=adaptiveBy('gl-110773-ranolazine-generic'),
  as=adaptiveBy('gl-110773-aspruzyo-sprinkle');
assert(ra.pathways[0].all.length===2&&ra.pathways[0].all[0].any.length===3
  &&ra.pathways[0].all[1].includes('generic ranolazine'),
  'Brand Ranexa generic trial or initial anti-angina OR condition missing');
assert(rg.pathways[0].all.length===1&&rg.pathways[0].all[0].any.length===3,
  'Generic ranolazine incorrectly inherited brand failure prerequisite');
assert(as.pathways[0].all.length===2&&as.pathways[0].all[0].any.length===3
  &&as.pathways[0].all[1].any.length===3,
  'Aspruzyo BOTH sets of alternatives missing');
const t=adaptiveBy('gl-113527-tarpeyo');
assert(t.pathways[0].all.length===7&&t.pathways[0].all[4].any.length===2,
  'Tarpeyo biopsy/eGFR/steroid/nephrology or ACE/ARB branching missing');
const lv=adaptiveBy('gl-113529-livtencity');
assert(lv.pathways[0].all.length===6&&lv.pathways[0].all[0].any.length===2
  &&lv.pathways[0].all[1].any.length===2&&lv.pathways[0].all[5].any.length===2,
  'Livtencity CMV, transplant or specialist OR condition missing');
const f=adaptiveBy('gl-116131-firdapse'),d=adaptiveBy('gl-116190-dojolvi'),
  o=adaptiveBy('gl-116122-orkambi');
assert([f,d,o].every(x=>x.stages?.length===2),'Initial/renewal stage missing');
assert(d.stages[0].all[0].any.length===3
  &&d.stages[0].all[0].any.every(x=>x.all?.length===2),
  'Dojolvi at-least-TWO-of-three tests not represented correctly');
assert(o.stages[1].all[0].any.length===4,
  'Orkambi renewal ONE-of-four response options missing');
ui.adaptiveGroup={name:'ROFLUMILAST TOPICAL',brands:['ZORYVE']};
assert(vm.runInContext('clinicalGuidanceFor(adaptiveGroup)',ui)===null,
  'Oral Daliresp clinical criteria inappropriately matched topical roflumilast');
ui.adaptiveGroup={name:'LIDOCAINE INJECTION',brands:['LIDOCAINE']};
assert(vm.runInContext('clinicalGuidanceFor(adaptiveGroup)',ui)===null,
  'Lidoderm patch criteria inappropriately matched injectable lidocaine');
console.log('PASS: 12 adaptive guides, 10 sections, exact source phrases, brand/form and nested clinical decision branches');


// One adaptive PR containing 20 separately source-checked November policies.
// Exact identities must not leak between branded, generic, or adjacent products.
const batch36Specs=[
 ['120435','brexafemme','BREXAFEMME',268,269,'12 months'],
 ['124866','adacel','ADACEL',27,28,'12 months'],
 ['125301','nexiclon-xr','NEXICLON XR',1236,1237,'12 months'],
 ['127089','tepezza','TEPEZZA',1779,1780,'6 months'],
 ['133807','zinplava','ZINPLAVA',2112,2113,'14 days'],
 ['136964','kepivance','KEPIVANCE',1020,1021,'6 months'],
 ['136966','diclareal','DICLAREAL',1825,1826,'3 months'],
 ['136966','trubrexa','TRUBREXA',1826,1826,'3 months'],
 ['139356','zurzuvae','ZURZUVAE',2136,2137,'14 days'],
 ['147691','xhance','XHANCE',2055,2056,'12 months'],
 ['146005','vemlidy','VEMLIDY',1939,1940,'12 months'],
 ['146018','eohilia','EOHILIA',572,574,'12 weeks'],
 ['154516','lucemyra','LUCEMYRA',1126,1127,'14 days'],
 ['154516','lofexidine-generic',null,1126,1127,'14 days'],
 ['135438','gattex','GATTEX',706,707,'6 months'],
 ['136958','ojjaara','OJJAARA',1307,1308,'6 months'],
 ['139344','xphozah','XPHOZAH',2078,2079,'12 months'],
 ['127083','cuvrior','CUVRIOR',435,436,'12 months'],
 ['124881','syfovre','SYFOVRE',1722,1723,'12 months'],
 ['135329','izervay','IZERVAY',996,997,'6 months'],
 ['136978','veltassa','VELTASSA',1936,1938,'12 months'],
 ['143522','jesduvroq','JESDUVROQ',998,1000,'6 months']
];
assert(batch36Specs.length===22,'Batch 36 guide count mismatch');
assert(new Set(batch36Specs.map(x=>x[0])).size===20,'20 distinct new policy sections required');
const batch36Compact=t=>t.replace(/\s+/g,' ').toLowerCase();
for (const [code,suffix,brand,first,last,duration] of batch36Specs){
  const id='gl-'+code+'-'+suffix;
  const guide=guidance.find(g=>g.id===id);
  assert(guide&&guide.policyCode==='GL-'+code&&guide.sourcePage===first&&guide.sourceLastPage===last,
    'Policy/page mapping failed: '+id);
  assert(guide.approvalDuration===duration&&guide.sourceChecks?.length>=3,
    'Duration or independent source phrases missing: '+id);
  const raw=batch36Compact(fs.readFileSync('_site/'+guide.sourceTextUrl.replace(/^\//,''),'utf8'));
  for(const phrase of guide.sourceChecks)
    assert(raw.includes(batch36Compact(phrase)),'Missing literal November phrase: '+id+' / '+phrase);
  assert(brand
    ? JSON.stringify(guide.matchBrands)===JSON.stringify([brand])&&!guide.matchNames?.length
    : JSON.stringify(guide.matchNames)===JSON.stringify(['LOFEXIDINE'])&&!guide.matchBrands?.length,
    'Unverified brand or generic matcher: '+id);
  ui.batch36Group={name:brand?'UNRELATED GENERIC':'LOFEXIDINE',brands:brand?[brand]:[]};
  assert(vm.runInContext('clinicalGuidanceFor(batch36Group)',ui)?.id===id,'Expected exact lookup missed: '+id);
  ui.batch36Group={name:brand?'UNRELATED GENERIC':'LOFEXIDINE SUSPENSION',brands:brand?[brand+' XR']:[]};
  assert(vm.runInContext('clinicalGuidanceFor(batch36Group)',ui)===null,'Substring match leakage: '+id);
}
const batch36=id=>guidance.find(x=>x.id==='gl-'+id);
const branch36=[
 ['120435-brexafemme',1,3],['124866-adacel',1,4],
 ['125301-nexiclon-xr',1,2],['127089-tepezza',1,3],
 ['133807-zinplava',1,5],['136964-kepivance',1,3],
 ['136966-diclareal',1,4],['136966-trubrexa',1,4],
 ['139356-zurzuvae',1,4],['147691-xhance',1,2],
 ['146005-vemlidy',2,null],['146018-eohilia',1,8],
 ['154516-lucemyra',1,7],['154516-lofexidine-generic',1,6]
];
for(const [id,count,requirements] of branch36){
 const g=batch36(id);
 assert(g.pathways?.length===count,'Required indication alternatives not preserved: '+id);
 if(requirements!==null)assert(g.pathways[0].all.length===requirements,
   'Incorrect AND requirement count: '+id);
}
const stage36=['135438-gattex','136958-ojjaara','139344-xphozah','127083-cuvrior',
 '124881-syfovre','135329-izervay','136978-veltassa','143522-jesduvroq'];
for(const id of stage36){
 const g=batch36(id);
 assert(g.stages?.length===2
   &&/^Initial authorization/.test(g.stages[0].title)
   &&/^Reauthorization/.test(g.stages[1].title),
   'Initial vs renewal criteria missing: '+id);
}
assert(batch36('125301-nexiclon-xr').pathways[0].all[1].any.length===2,'Nexiclon requires ONE prior formulation');
assert(batch36('133807-zinplava').pathways[0].all[3].any.length===5,'Zinplava five recurrence risk alternatives lost');
assert(batch36('139356-zurzuvae').pathways[0].all[0].any.length===2,'Zurzuvae severe vs mild/moderate PPD alternatives lost');
assert(batch36('139356-zurzuvae').pathways[0].all[3].includes('12 hours'),'Zurzuvae driving precaution lost');
assert(batch36('147691-xhance').pathways[0].all[0].any.length===2,'Xhance nasal polyps OR missing');
assert(batch36('146005-vemlidy').pathways[1].all[0].any.length===2
 &&batch36('146005-vemlidy').pathways[1].all[0].any[0].all[1].any.length===2,
 'Vemlidy Viread-renal/osteoporosis vs ongoing Vemlidy branch malformed');
assert(batch36('146018-eohilia').pathways[0].all[6].includes('does not list contraindication'),
 'Eohilia topical-steroid requirement improperly extended to contraindications');
assert(batch36('154516-lucemyra').pathways[0].all.length
 ===batch36('154516-lofexidine-generic').pathways[0].all.length+1,
 'Brand Lucemyra generic-lofexidine trial wrongly required for generic product');
assert(batch36('136966-diclareal').pathways[0].all.some(x=>x.includes('2% topical solution')),
 'Diclareal 2% diclofenac step missing');
assert(batch36('136966-trubrexa').pathways[0].all.some(x=>x.includes('lidocaine patch')),
 'Trubrexa lidocaine step missing');
assert(batch36('139344-xphozah').stages.every(s=>s.all.filter(x=>typeof x==='string'&&x.includes('carbonate')).length>=2),
 'Xphozah all 3 phosphate-binder steps missing');
assert(batch36('135329-izervay').stages[1].all.some(x=>x.includes('12 months')),
 'Izervay maximum lifetime course in original guideline lost');
assert(batch36('136978-veltassa').stages[0].all.some(x=>x.includes('Lokelma')),
 'Veltassa Lokelma prerequisite missing');
assert(batch36('143522-jesduvroq').stages[0].all.some(x=>x.any?.length===3),
 'Jesduvroq one-of-three ESA alternatives missing');
ui.batch36Group={name:'FLUTICASONE PROPIONATE NASAL SPRAY',brands:['FLONASE']};
assert(vm.runInContext('clinicalGuidanceFor(batch36Group)',ui)===null,
 'Xhance guidance leaked into generic intranasal fluticasone');
ui.batch36Group={name:'CLONIDINE TABLET',brands:['CATAPRES']};
assert(vm.runInContext('clinicalGuidanceFor(batch36Group)',ui)===null,
 'Nexiclon extended-release rule leaked into immediate-release clonidine');
console.log('PASS: Adaptive 20-policy/22-guide batch, exact brand/generic identity, source checks, AND/OR and initial/renewal tests');


// 60-policy sprint: mandatory source, exact-brand, and indication/stage regression
// for the subset that passed independent detailed clinical review.
const sprintGuideIds=[
 'gl-164377-namzaric','gl-164415-emrosi','gl-211208-baclofen-branded-liquid',
 'gl-228335-vivjoa','gl-241267-zunveyl','gl-241268-xromi',
 'gl-285207-xdemvy','gl-269199-lama-laba-regular','gl-269199-bevespi',
 'gl-300315-jynarque','gl-322195-sofdra','gl-300304-velsipity',
 'gl-321192-crenessity','gl-269197-sunlenca','gl-157795-piasky',
 'gl-157798-livdelzi','gl-161661-yorvipath','gl-193195-attruby',
 'gl-155841-tryvio','gl-155844-vafseo'
];
assert(sprintGuideIds.length===20,'Expected 20 independently reviewed new guides');
const sprintCodes=new Set(sprintGuideIds.map(id=>guidance.find(g=>g.id===id)?.policyCode));
assert(sprintCodes.size===19&&!sprintCodes.has(undefined),'Expected 19 distinct new clinical policy sections');
const compactSprint=s=>String(s).replace(/\s+/g,' ').toLowerCase();
for(const id of sprintGuideIds){
 const guide=guidance.find(g=>g.id===id);
 assert(guide?.matchBrands?.length&&!guide?.matchNames?.length,'Exact brand identity missing '+id);
 assert(guide.sourceChecks.length>=3,'Insufficient source-phrase confirmations '+id);
 const s=fs.readFileSync('_site/'+guide.sourceTextUrl.replace(/^\//,''),'utf8');
 const raw=compactSprint(s);
 for(const phrase of guide.sourceChecks)
  assert(raw.includes(compactSprint(phrase)),'Original November source phrase mismatch '+id+': '+phrase);
 const pages=[...s.matchAll(/--- PDF page (\d+) ---/g)].map(x=>Number(x[1]));
 assert(pages.includes(guide.sourcePage)&&pages.includes(guide.sourceLastPage),
  'Original November page mismatch '+id);
 ui.sprintGroup={name:'UNRELATED GENERIC PRODUCT',brands:[guide.matchBrands[0]]};
 assert(vm.runInContext('clinicalGuidanceFor(sprintGroup)',ui)?.id===id,'Exact brand not linked '+id);
 ui.sprintGroup={name:'UNRELATED GENERIC PRODUCT',brands:[guide.matchBrands[0]+' XR EXTRA']};
 assert(vm.runInContext('clinicalGuidanceFor(sprintGroup)',ui)===null,
  'Substring/fuzzy drug identity attached clinical criteria '+id);
}
const getSprint=id=>guidance.find(g=>g.id==='gl-'+id);
assert(getSprint('164377-namzaric').pathways[0].all.length===3,'Namzaric dual ingredient histories lost');
assert(getSprint('211208-baclofen-branded-liquid').pathways.length===2,
 'Baclofen OR tablet failure vs inability to swallow lost');
assert(getSprint('228335-vivjoa').pathways[0].all.length===7 &&
 getSprint('228335-vivjoa').pathways[0].all[2].any.length===2 &&
 getSprint('228335-vivjoa').pathways[0].all[5].any.length===2,
 'Vivjoa RVVC/fluconazole nested criteria lost');
assert(getSprint('241267-zunveyl').pathways[0].all.length===5,'Zunveyl ALL three prior drugs missing');
assert(getSprint('241268-xromi').stages.length===2 &&
 getSprint('241268-xromi').stages[0].all[3].any.length===2,
 'Xromi solid formulation alternative or renewal lost');
assert(getSprint('285207-xdemvy').pathways[0].all.length===6,
 'Xdemvy BOTH 12-week steps or ophthalmology requirements lost');
assert(getSprint('269199-lama-laba-regular').pathways[0].all.length===2 &&
 getSprint('269199-bevespi').pathways[0].all.length===4,
 'Bevespi preferred products prerequisite leaked to other LAMA/LABA');
assert(getSprint('300315-jynarque').stages.length===2 &&
 !getSprint('300315-jynarque').matchBrands.includes('TOLVAPTAN'),
 'Jynarque brand rule leaked into generic tolvaptan');
assert(getSprint('322195-sofdra').stages.length===2 &&
 getSprint('322195-sofdra').stages[0].all.length===8 &&
 getSprint('322195-sofdra').stages[1].title.includes('6 months'),
 'Sofdra initial 6-week and renewal 6-month qualification lost');
assert(getSprint('300304-velsipity').stages[0].all.length===8 &&
 getSprint('300304-velsipity').stages[0].all[1].any.length===6 &&
 getSprint('300304-velsipity').stages[0].all[2].any.length===4,
 'Velsipity UC severity and drug trial branching missing');
assert(getSprint('321192-crenessity').stages[0].all[3].any.length===2,
 'Crenessity age-specific glucocorticoid dose rules lost');
assert(getSprint('269197-sunlenca').pathways.length===2 &&
 getSprint('269197-sunlenca').pathways[0].all[2].any.length===3,
 'Sunlenca new use vs continuation OR rules lost');
assert(getSprint('157795-piasky').stages.every(s=>s.all.some(x=>x.any?.length===2)),
 'Piasky Soliris vs Ultomiris alternative omitted');
assert(getSprint('157798-livdelzi').stages[0].all[1].any.length===2 &&
 getSprint('157798-livdelzi').stages[0].all[1].any[0].all.length===2,
 'Livdelzi UDCA failure vs intolerance branching lost');
assert(getSprint('161661-yorvipath').stages[0].all.some(x=>x.includes('7.8 mg/dL')),
 'Yorvipath corrected calcium cutoff missing');
assert(getSprint('193195-attruby').stages[0].all[1].any.length===3 &&
 getSprint('193195-attruby').stages[0].all[1].any[2].all.length===2,
 'Attruby three confirmation routes and light-chain exclusion missing');
assert(getSprint('155841-tryvio').stages[0].all.length===9 &&
 getSprint('155841-tryvio').stages[1].all.length===7,
 'Tryvio four drug-class trials or renewal conditions missing');
assert(getSprint('155844-vafseo').stages[0].all[4].any.length===2 &&
 getSprint('155844-vafseo').stages[1].all[3].any.length===2,
 'Vafseo preferred ESA step or renewal requirements lost');
console.log('PASS: 20 new guides in 19 original policies; exact-source, identity, route, AND/OR and stage safeguards');


// GL-105174 BPH is explicitly limited to the 5 mg Cialis/tadalafil product.
// Fail closed on unconfirmed, 2.5 mg, 10 mg, 20 mg, and mixed-strength records.
const bphGuide=guidance.find(g=>g.id==='gl-105174-cialis-bph');
assert(bphGuide&&bphGuide.policyCode==='GL-105174'&&bphGuide.matchStrengthMg===5,
  'Cialis BPH guide must require exact 5 mg product');
assert(bphGuide.sourcePage===337&&bphGuide.sourceLastPage===338
  &&bphGuide.approvalDuration==='12 months','Cialis BPH original source reference mismatch');
assert(JSON.stringify(bphGuide.matchBrands)===JSON.stringify(['CIALIS'])
  &&JSON.stringify(bphGuide.matchNames)===JSON.stringify(['TADALAFIL']),
  'Cialis BPH guide may only match confirmed original product identities');
const bphAll=bphGuide.pathways?.[0]?.all;
assert(bphAll?.length===4&&bphAll[1].all.length===2
  &&bphAll[1].all.every(branch=>branch.any?.length===3),
  'Cialis BPH requires BOTH alpha-blocker AND 5-alpha inhibitor failure/intolerance/contraindication');
assert(bphAll[2].includes('5 mg')&&bphAll[3].includes('Adempas'),
  'Cialis BPH dose and nitrate/riociguat protections missing');
ui.bph5={name:'TADALAFIL 5 MG TABLET',brands:['CIALIS'],
  records:[{recordType:'formulary',name:'TADALAFIL 5 MG TABLET (brand for CIALIS)'}]};
ui.bphGeneric5={name:'TADALAFIL',brands:[],
  records:[{recordType:'formulary',name:'TADALAFIL 5MG TABLET'}]};
assert(vm.runInContext('clinicalGuidanceFor(bph5)',ui)?.id===bphGuide.id,
  '5 mg Cialis brand record not recognized');
assert(vm.runInContext('clinicalGuidanceFor(bphGeneric5)',ui)?.id===bphGuide.id,
  'Explicit generic tadalafil 5 mg record not recognized');
const unsafeBph=[
 {name:'TADALAFIL 2.5 MG TABLET',brands:['CIALIS'],records:[{name:'TADALAFIL 2.5 MG TABLET'}]},
 {name:'TADALAFIL 10 MG TABLET',brands:['CIALIS'],records:[{name:'TADALAFIL 10 MG TABLET'}]},
 {name:'TADALAFIL 20 MG TABLET',brands:['CIALIS'],records:[{name:'TADALAFIL 20 MG TABLET'}]},
 {name:'TADALAFIL',brands:['CIALIS'],records:[{name:'TADALAFIL TABLET'}]},
 {name:'TADALAFIL',brands:[],records:[{name:'TADALAFIL 20 MG TABLET'}]},
 {name:'TADALAFIL 5 MG TABLET',brands:['CIALIS'],records:[{name:'TADALAFIL 5 MG TABLET'}, {name:'TADALAFIL 20 MG TABLET'}]},
 {name:'SILDENAFIL 5 MG TABLET',brands:['VIAGRA'],records:[{name:'SILDENAFIL 5 MG TABLET'}]}
];
for (const candidate of unsafeBph) {
 ui.unsafeBph=candidate;
 assert(vm.runInContext('clinicalGuidanceFor(unsafeBph)',ui)===null,
   'Strength-specific BPH criteria incorrectly attached to '+candidate.name);
}
const bphHtml=vm.runInContext('clinicalGuidanceContent(clinicalGuidanceFor(bph5))',ui);
assert(bphHtml.includes('5 mg')&&bphHtml.includes('Adempas')
  &&bphHtml.includes('alpha'), 'BPH clinical card omitted key eligibility conditions');
console.log('PASS: GL-105174 BPH 5 mg, source, branch and 7 negative strength/matcher regressions');


// Batch 39: 20 newly structured November policy sections, independent source,
// brand/formulation-negative, age-exemption and mixed-approval safety checks.
const batch39Specs=[
 ['356255','rayos'],['413207','tretinoin-topical'],['427190','leucovorin-tablets'],
 ['441190','shingrix'],['450249','orlynvah'],['450258','gralise'],
 ['450258','horizant'],['490254','effient'],['364197','vanrafia'],
 ['479196','sephience'],['481198','forzinity'],['481199','palsonify'],
 ['401288','voydeya'],['417211','krystexxa'],['363221','iluvien'],
 ['417204','opzelura'],['369200','vtama'],['396205','kerendia'],
 ['427192','prevymis'],['479197','sapropterin-generic'],
 ['479197','sapropterin-brands'],['357222','xiidra'],
 ['357222','dry-eye-nonpreferred']
];
assert(batch39Specs.length===23,'Batch 39 requires 23 independently checked medication guides');
assert(new Set(batch39Specs.map(x=>x[0])).size===20,'Batch 39 requires 20 different policy sections');
const batch39Norm=t=>String(t).replace(/\s+/g,' ').toLowerCase();
for(const [code,id] of batch39Specs){
 const guide=guidance.find(g=>g.id==='gl-'+code+'-'+id);
 assert(guide&&guide.policyCode==='GL-'+code,'Missing batch 39 product '+id);
 assert(guide.sourceChecks?.length>=3,'Insufficient exact November source checks: '+id);
 const rawText=fs.readFileSync('_site/'+guide.sourceTextUrl.replace(/^\//,''),'utf8');
 const raw=batch39Norm(rawText);
 for(const phrase of guide.sourceChecks)
  assert(raw.includes(batch39Norm(phrase)),'Published source phrase differs: '+id+' / '+phrase);
 const sourcePages=[...rawText.matchAll(/--- PDF page (\d+) ---/g)].map(x=>Number(x[1]));
 assert(sourcePages.includes(guide.sourcePage)&&sourcePages.includes(guide.sourceLastPage),
   'Incorrect original PDF page reference: '+id);
 const opts=guide.stages||guide.pathways;
 assert(opts?.length,'Clinical decision structure missing: '+id);
 assert(guide.guidelineCaution?.toLowerCase().includes('plan'),
   'Source-based guidance missing plan-benefit caveat: '+id);
 for(const brand of guide.matchBrands||[]){
   ui.audit39Group={name:'OTHER GENERIC',brands:[brand]};
   assert(vm.runInContext('clinicalGuidanceFor(audit39Group)',ui)?.id===guide.id,
     'Exact product brand lookup failed: '+brand);
   ui.audit39Group={name:'OTHER GENERIC',brands:[brand+' EXTRA']};
   assert(vm.runInContext('clinicalGuidanceFor(audit39Group)',ui)===null,
     'Unsafe substring/fuzzy brand matching: '+brand);
 }
 for(const name of guide.matchNames||[]){
   ui.audit39Group={name,brands:[]};
   assert(vm.runInContext('clinicalGuidanceFor(audit39Group)',ui)?.id===guide.id,
     'Exact generic/formulation lookup failed: '+name);
   ui.audit39Group={name:name+' EXTENDED RELEASE INJECTION',brands:[]};
   assert(vm.runInContext('clinicalGuidanceFor(audit39Group)',ui)===null,
     'Unsafe generic route/form match: '+name);
 }
}
const b39=id=>guidance.find(g=>g.id==='gl-'+id);
assert(b39('356255-rayos').pathways[0].all[3].any.length===6,
 'Rayos requires TWO of FOUR steroids; the six possible pairs must be represented');
assert(b39('413207-tretinoin-topical').pathways.length===1
 &&b39('413207-tretinoin-topical').guidelineCaution.includes('NOT required'),
 'Tretinoin age ≤26 exemption is not a PA approval pathway');
assert(b39('441190-shingrix').pathways.length===1
 &&b39('441190-shingrix').guidelineCaution.includes('NOT required'),
 'Shingrix age ≥50 exception is not a PA approval pathway');
assert(b39('450249-orlynvah').pathways[0].all[3].any.length===3,
 'Orlynvah three covered organisms must remain explicit alternatives');
assert(b39('450258-gralise').pathways[0].all.length===2
 &&b39('450258-horizant').pathways.length===2,
 'Gralise generic gabapentin step leaked into Horizant RLS pathway');
assert(b39('364197-vanrafia').stages.length===2
 &&b39('364197-vanrafia').stages[0].all.some(x=>x.any?.length===2),
 'Vanrafia ACE vs ARB minimum 90-day rule missing');
assert(b39('417211-krystexxa').stages[1].all.length===2,
 'Krystexxa requires BOTH laboratory and clinical response for renewal');
assert(b39('363221-iluvien').pathways.length===2,
 'Iluvien noninfectious uveitis vs DME pathways missing');
assert(b39('417204-opzelura').stages.length===2
 &&b39('417204-opzelura').guidelineCaution.includes('vitiligo'),
 'Opzelura benefit exclusion or initial/renewal qualifications lost');
assert(b39('369200-vtama').stages.length===4,
 'Vtama plaque psoriasis and atopic dermatitis stages incorrectly combined');
assert(b39('396205-kerendia').stages.length===4
 &&b39('396205-kerendia').stages[2].all.some(x=>typeof x==='string'&&x.includes('spironolactone')),
 'Kerendia CKD/heart-failure separate pathways or no-spironolactone rule missing');
assert(b39('427192-prevymis').pathways.length===2,
 'Prevymis kidney and HSCT transplant source requirements combined');
assert(b39('479197-sapropterin-generic').pathways[0].all.length===1
 &&b39('479197-sapropterin-brands').pathways[0].all.length===2,
 'Brand-only failure-to-generic step erroneously added to generic sapropterin');
assert(b39('357222-xiidra').stages[0].all.length+1
 ===b39('357222-dry-eye-nonpreferred').stages[0].all.length,
 'Nonpreferred dry-eye product must have BOTH Restasis and Xiidra steps');
const multiDuration39=[
 ['479196-sephience',['3 months','12 months']],
 ['417204-opzelura',['12 weeks','6 months']],
 ['369200-vtama',['6 months','12 months','6 months','12 months']],
 ['427192-prevymis',['6 months','12 months']]
];
for(const [id,expected] of multiDuration39){
 const guide=b39(id);
 const options=guide.stages||guide.pathways;
 assert(JSON.stringify(options.map(x=>x.approvalDuration))===JSON.stringify(expected),
   'Original source-specific approval lengths missing for '+id);
 ui.batch39Guide=guide;
 const markup=vm.runInContext('clinicalGuidanceContent(batch39Guide)',ui);
 assert(markup.includes('Approval duration for this ')
   &&!markup.includes('<strong>Approval duration:</strong>'),
   'Ambiguous single global approval duration displayed for '+id);
 for(const period of new Set(expected))assert(markup.includes(period),
   'Missing branch-specific duration '+period+' for '+id);
}
ui.audit39Group={name:'TRETINOIN ORAL 10 MG CAPSULE',brands:[]};
assert(vm.runInContext('clinicalGuidanceFor(audit39Group)',ui)===null,
 'Generic topical tretinoin guideline incorrectly attached to oral tretinoin');
ui.audit39Group={name:'GABAPENTIN IMMEDIATE RELEASE',brands:[]};
assert(vm.runInContext('clinicalGuidanceFor(audit39Group)',ui)===null,
 'Gralise or Horizant guidelines incorrectly attached to generic IR gabapentin');
console.log('PASS: Batch 39 audited 20 original sections, 23 guides, direct sources, exact identities, clinical logic, mixed approval periods and exemptions');
