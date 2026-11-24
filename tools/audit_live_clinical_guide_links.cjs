const fs=require('fs'),vm=require('vm'),zlib=require('zlib');
const assert=(condition,message)=>{if(!condition)throw Error(message)};
const loadFile=(path)=>{
  const buf=fs.readFileSync(path);
  return JSON.parse((buf[0]===31&&buf[1]===139?zlib.gunzipSync(buf):buf).toString('utf8'));
};
const data=loadFile('_site/data.json.gz');
const source=fs.readFileSync('_site/app.js','utf8');
const from=source.indexOf('  // Keep one immutable statewide source');
const to=source.indexOf('  function categoryOptions(',from);
const clinicalStart=source.indexOf('  function clinicalGuidanceFor(');
const clinicalEnd=source.indexOf('  function clinicalRequirementItem(',clinicalStart);
assert(from>=0&&to>from&&clinicalStart>=0&&clinicalEnd>clinicalStart,'Cannot isolate current medication matcher');
const code=source.slice(from,to)+'\n'+source.slice(clinicalStart,clinicalEnd);
const loaded={...data,medications:[...data.medications]};
for(const [plan,file] of Object.entries(data.planDataFiles||{})){
  const target='_site/'+String(file).split('?')[0].replace(/^\.\//,'').replace(/^\//,'');
  const rows=loadFile(target);
  assert(Array.isArray(rows)&&rows.every(r=>r.planId===plan),'Supplement not isolated to expected plan');
  loaded.medications.push(...rows);
}
const guides=data.statewideClinicalGuidance;
assert(guides.length>=16,'Previously reviewed guides missing');
const plans=['az-complete-health','banner-ufc','uhc-community-az'];
for(const planId of plans){
  const ctx={normalize:s=>String(s||'').trim().toLowerCase(),state:{planId,data:loaded}};
  vm.createContext(ctx);
  vm.runInContext(code,ctx);
  const groups=vm.runInContext('planMedicationGroups()',ctx);
  const regularInsulin=groups.filter(g=>/insulin regular \(human\) solution/i.test(g.name));
  const units = brand => /\bU[- ]?(100|500)\b/i.exec(brand)?.[1] || '';
  const u500 = regularInsulin.filter(g=>g.brands.some(b=>units(b)==='500'));
  const u100 = regularInsulin.filter(g=>g.brands.some(b=>units(b)==='100'));
  assert(u500.length>0&&u100.length>0,'Insulin concentrations absent in displayed source data: '+planId);
  assert(u500.every(g=>g.brands.every(b=>units(b)==='500')),'U-500 shared a medication card with non-U-500 insulin: '+planId);
  assert(u100.every(g=>g.brands.every(b=>units(b)==='100')),'U-100 shared a medication card with another insulin concentration: '+planId);
  ctx.mixedU100={name:'INSULIN REGULAR (HUMAN) SOLUTION',brands:['HUMULIN R U-100']};
  ctx.mixedU500={name:'INSULIN REGULAR (HUMAN) SOLUTION',brands:['HUMULIN R U-500 (CONCENTRATED)']};
  assert(!vm.runInContext('sameProductGroup(mixedU100,mixedU500)',ctx),'Cross-source grouping can still mix U-100 with U-500');
  const matchedGuideIds=new Set();
  const ambiguous=[];
  const assignments=[];
  for(const group of groups){
    ctx.currentGroup=group;
    const guide=vm.runInContext('clinicalGuidanceFor(currentGroup)',ctx);
    if(!guide)continue;
    matchedGuideIds.add(guide.id);
    assignments.push({guide:guide.id,label:group.label,brands:group.brands});
    const compatibleBrands=(guide.matchBrands||[]).map(s=>s.toLowerCase());
    const aliases=group.brands.map(s=>s.toLowerCase());
    const differentBrand=compatibleBrands.length&&aliases.some(b=>!compatibleBrands.includes(b));
    if(differentBrand)ambiguous.push({guide:guide.id,label:group.label,brands:group.brands});
  }
  const missing=guides.filter(g=>!matchedGuideIds.has(g.id)).map(g=>g.id);
  for (const guide of guides) {
    const query=(guide.matchBrands||[])[0] || (guide.matchNames||[])[0] || guide.product;
    assert(query,'Structured clinical guide lacks search identity: '+guide.id);
    ctx.clinicalQuery=query;
    // The criteria library searches every structured guide independently of
    // medication cards. Do not recompute every card-to-guide mapping per query.
    ctx.visibleGroups=[];
    const sources=vm.runInContext('clinicalPolicyOnlyGroups(clinicalQuery,visibleGroups)',ctx);
    const included=sources.some(g=>g.guide.id===guide.id);
    assert(included,'Structured guide inaccessible in criteria library: '+guide.id);
    assert(sources.every(g=>g.policyOnly===true&&g.records.length===0),'Clinical policy-only search invented formulary records');
  }
  console.log('GUIDE VISIBILITY '+planId+': '+matchedGuideIds.size+'/'+guides.length+' guide IDs attached; '+groups.length+' medication groups; '+ambiguous.length+' mixed-brand group matches');
  console.log('UNLINKED '+planId+': '+JSON.stringify(missing));
  console.log('EXAMPLES '+planId+': '+JSON.stringify(assignments.slice(0,15)));
  if(ambiguous.length)console.log('MIXED BRANDS '+planId+': '+JSON.stringify(ambiguous.slice(0,20)));
  assert(!ambiguous.length,'Product-specific clinical guidance is assigned to a mixed-brand medication group: '+planId);
}
// Confirm that existing plan-only medication cards actually render their
// source-verified clinical guidance rather than merely matching it internally.
const cardStart=source.indexOf('  function constipationCoverageNote(');
const cardEnd=source.indexOf('  function render()',cardStart);
assert(cardStart>0&&cardEnd>cardStart,'Medication card UI function missing');
const ui={cardClinicalGroups:new Map(),uhcRestrictionSummary:()=>'',cardPaReference:()=>'',state:{planId:'az-complete-health'},normalize:s=>String(s).toLowerCase(),sourceHref:()=>'',
 escapeHtml:s=>String(s),
 readableMedicationName:s=>String(s),
 sourcesLink:()=>'',criteriaLibraryShortcut:()=>'',linkedPolicyPanels:()=>[],clinicalGuidanceContent:()=>'Clinically validated source details',
 clinicalGuidanceFor:g=>g.brands.includes('FARXIGA')?{policyCode:'GL-589207',heading:'Farxiga guidance'}:null,
 statusChips:()=>'',medicationPolicyDropdown:()=>'',recordDetails:()=>''
};
vm.createContext(ui);
const dosageFormDefinitions=source.slice(source.indexOf('  const formWords ='),source.indexOf('  // These reviewed UHC rows'));
const constipationDefinitions=dosageFormDefinitions+source.slice(source.indexOf('  const constipationGenericRows ='),source.indexOf('  function planMedicationGroups('));
vm.runInContext(constipationDefinitions+source.slice(cardStart,cardEnd),ui);
ui.card={label:'Dapagliflozin (Farxiga)',name:'dapagliflozin',brands:['FARXIGA'],records:[{name:'Dapagliflozin'}]};
const withGuide=vm.runInContext('medicationGroupCard(card)',ui);
assert(withGuide.includes('Clinically validated source details')&&withGuide.includes('Clinical details &amp; PA criteria'),'Plan-only clinical criteria missing or misleading');
ui.card={label:'Unrelated product',name:'other',brands:['OTHER'],records:[{name:'other'}]};
const withoutGuide=vm.runInContext('medicationGroupCard(card)',ui);
assert(!withoutGuide.includes('Clinically validated source details'),'Incorrect product received clinical PA guidance');
console.log('PASS: plan-only medication cards display only their exact source-backed clinical guidance, with no inferred PA status');

console.log('PASS: all clinical guide IDs reachable in the separate criteria library for each of 3 plans; no mixed-brand medication criteria');
