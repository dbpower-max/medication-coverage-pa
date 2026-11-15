const fs=require('fs'),vm=require('vm'),zlib=require('zlib');
function assert(ok,msg){if(!ok)throw Error(msg)}
const data=JSON.parse(zlib.gunzipSync(fs.readFileSync('_site/data.json.gz')));
const index=data.statewidePaCriteria;
assert(index.length===481,'Expected complete November statewide clinical guideline index');
assert(new Set(index.map(p=>p.policyCode)).size===481,'Duplicate guideline identifiers');
let totalBytes=0;
for(const p of index){
  assert(p.sourceEffective==='2026-11-01','Guideline source version mismatch: '+p.policyCode);
  assert(p.sourcePage>0&&p.sourceLastPage>=p.sourcePage,'Invalid PDF page bounds: '+p.policyCode);
  assert(p.sourceTextUrl,'Missing text path: '+p.policyCode);
  const textPath='_site/'+p.sourceTextUrl.replace(/^\.\//,'').replace(/^\//,'');
  assert(fs.existsSync(textPath),'Unpublished source text: '+p.policyCode);
  const content=fs.readFileSync(textPath,'utf8');
  assert(content.includes(p.policyCode),'Source section has wrong code: '+p.policyCode);
  assert(content.includes('--- PDF page '+p.sourcePage+' ---'),'First source page label missing: '+p.policyCode);
  assert(content.length>=250,'Unexpectedly short complete guideline section: '+p.policyCode);
  totalBytes+=content.length;
}
const script=fs.readFileSync('_site/app.js','utf8');
const first=script.indexOf('  function searchIndexedCriteria(');
const last=script.indexOf('  function renderCriteriaLibrary(',first);
assert(first>0&&last>first,'Clinical criteria search implementation missing');
const runtime={normalize:s=>String(s||'').trim().toLocaleLowerCase()};
vm.createContext(runtime);
vm.runInContext(script.slice(first,last),runtime);
const matches=q=>{runtime.query=q;runtime.index=index;return vm.runInContext('searchIndexedCriteria(query,index)',runtime);};
for(const [q,id] of [['Mounjaro','GL-749236'],['Jardiance','GL-589207'],['Insulins, Concentrated','GL-154074'],['Actimmune','GL-99673']]){
 assert(matches(q).some(x=>x.policyCode===id),'Search did not find '+id+' for '+q);
}
assert(matches('')?.length===0,'Blank query must not list 481 policies');
assert(matches('not-a-real-drug-zz999')?.length===0,'Nonmatch must not return unrelated policies');
const html=fs.readFileSync('_site/index.html','utf8');
for(const id of ['criteriaLibrary','criteriaSearch','criteriaCount','criteriaResults']){
 assert(html.includes('id="'+id+'"'),'Missing search control '+id);
}
assert(script.includes('pre.textContent = await response.text()'),'Original guideline is not rendered as literal text');
assert(script.includes('button.dataset.readGuideline'),'On-demand text lookup is missing');
// Every medication card can open the statewide source index using the
// displayed generic/brand identity; it never asserts that a policy applies.
const startShortcut=script.indexOf('  function criteriaLibraryShortcut(');
const endShortcut=script.indexOf('  function medicationGroupCard(',startShortcut);
assert(startShortcut>0&&endShortcut>startShortcut,'Card-to-criteria shortcut missing');
const shortcutCtx={escapeHtml:value=>String(value).replace(/[&<>'"]/g,chr=>({
 '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
})[chr])};
vm.createContext(shortcutCtx);
vm.runInContext(script.slice(startShortcut,endShortcut),shortcutCtx);
shortcutCtx.group={name:'TIRZEPATIDE SOLN AUTO-INJ',brands:['MOUNJARO']};
const shortcut=vm.runInContext('criteriaLibraryShortcut(group)',shortcutCtx);
assert(shortcut.includes('data-criteria-query="MOUNJARO"'),'Mounjaro shortcut not tied to brand');
shortcutCtx.group={name:'drug generic',brands:['<unsafe>']};
const safe=vm.runInContext('criteriaLibraryShortcut(group)',shortcutCtx);
assert(safe.includes('&lt;unsafe&gt;')&&!safe.includes('="<unsafe>"'),'Shortcut escaped drug names incorrectly');
assert((script.match(/\$\{criteriaLibraryShortcut\(group\)\}/g)||[]).length===2,'Both statewide and plan-specific cards need source shortcuts');
assert(script.includes('el.criteriaLibrary.open = true')&&script.includes('shortcut.dataset.criteriaQuery'),'Source shortcut does not activate the library');

console.log('PASS: all '+index.length+' policy source files present and tied to November PDF page/code; '+totalBytes+' source-text bytes; search returns expected guideline sections; original text safely rendered');


// Independent source and clinical-branch regression for November five-policy batch.
const reviewed=JSON.parse(fs.readFileSync('tools/provider_statewide_clinical_guidance.json','utf8')).guides;
const cases=[
 ['GL-427190','gl-427190-leucovorin-tabs','LEUCOVORIN CALCIUM',1078,1079,'12 months','pathways'],
 ['GL-441190','gl-441190-shingrix','SHINGRIX',1584,1585,'12 months','pathways'],
 ['GL-450249','gl-450249-orlynvah','ORLYNVAH',1346,1347,'5 days','pathways'],
 ['GL-490254','gl-490254-effient','EFFIENT',526,527,'12 months','pathways'],
 ['GL-364197','gl-364197-vanrafia','VANRAFIA',1926,1928,'12 months','stages']
];
const normalizePhrase=s=>String(s).replace(/\\s+/g,' ').toLowerCase();
for(const [code,id,brand,first,last,duration,branch] of cases){
 const guide=reviewed.find(g=>g.id===id);
 assert(guide&&guide.policyCode===code,'Missing or wrong clinical guide '+id);
 assert(guide.sourcePage===first&&guide.sourceLastPage===last,'Wrong page range '+id);
 assert(guide.approvalDuration===duration,'Wrong approval duration '+id);
 assert(guide.sourceChecks.length>=3,'Insufficient literal source checks '+id);
 const original=fs.readFileSync('_site/policy-text/ahcccs-ffs-nov2026/'+code.toLowerCase()+'.txt','utf8');
 for(const phrase of guide.sourceChecks)assert(normalizePhrase(original).includes(normalizePhrase(phrase)),'Source phrase mismatch '+id+': '+phrase);
 assert(guide.matchBrands?.includes(brand)||guide.matchNames?.includes(brand),'Exact product identity missing '+id);
 assert(Array.isArray(guide[branch])&&guide[branch].length>0,'Clinical branch missing '+id);
 assert(!guide.matchBrands?.includes('MERCY CARE'),'Wrong plan identity '+id);
}
const vanrafia=reviewed.find(g=>g.id==='gl-364197-vanrafia');
assert(vanrafia.stages.length===2&&/Initial/.test(vanrafia.stages[0].title)&&/Reauthorization/.test(vanrafia.stages[1].title),'Vanrafia initial and renewal must remain separate');
assert(JSON.stringify(vanrafia.stages[0]).includes('90 days')&&!JSON.stringify(vanrafia.stages[1]).includes('90 days'),'Vanrafia renewal incorrectly inherits initial step therapy');
const orlynvah=reviewed.find(g=>g.id==='gl-450249-orlynvah');
assert(orlynvah.pathways[0].all.some(v=>v.any?.length===3),'Orlynvah organism alternatives must remain OR');
const shingrix=reviewed.find(g=>g.id==='gl-441190-shingrix');
assert(shingrix.pathways.length===2&&/50/.test(JSON.stringify(shingrix.pathways[1])),'Shingrix age exemption absent');
const effient=reviewed.find(g=>g.id==='gl-490254-effient');
assert(effient.matchNames.includes('PRASUGREL')&&!effient.matchNames.includes('TICAGRELOR'),'Effient generic identity leakage');
console.log('PASS: five new November source-matched clinical guides, exact identities, stage/age/organism regressions');
