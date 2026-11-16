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
assert(script.includes('data-card-clinical=')&&script.includes('${sourcesLink(group)}'),'Common medication card must retain direct criteria and original source access');
assert(script.includes('el.criteriaLibrary.open = true')&&script.includes('shortcut.dataset.criteriaQuery'),'Source shortcut does not activate the library');

console.log('PASS: all '+index.length+' policy source files present and tied to November PDF page/code; '+totalBytes+' source-text bytes; search returns expected guideline sections; original text safely rendered');
