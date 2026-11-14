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
  console.log('GUIDE VISIBILITY '+planId+': '+matchedGuideIds.size+'/'+guides.length+' guide IDs attached; '+groups.length+' medication groups; '+ambiguous.length+' mixed-brand group matches');
  console.log('UNLINKED '+planId+': '+JSON.stringify(missing));
  console.log('EXAMPLES '+planId+': '+JSON.stringify(assignments.slice(0,15)));
  if(ambiguous.length)console.log('MIXED BRANDS '+planId+': '+JSON.stringify(ambiguous.slice(0,20)));
  assert(!ambiguous.length,'Product-specific clinical guidance is assigned to a mixed-brand medication group: '+planId);
}
console.log('PASS: 3-plan real-data guide-to-medication linkage audit completed without mixed-brand rule transfers');
