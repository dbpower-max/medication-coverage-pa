const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const data=JSON.parse(zlib.gunzipSync(fs.readFileSync('_site/data.json.gz')));
const source=fs.readFileSync('_site/app.js','utf8');
const rows=data.statewideDrugList;
for(const brand of ['HUMATIN','ALKERAN','EULEXIN']) {
 const row=rows.find(r=>r.brand===brand);
 assert.equal(row.coverage,'explicit_not_covered',brand+' noncoverage lost');
 assert.equal(row.pa,'not_specified',brand+' noncoverage mislabeled PA');
 assert.match(row.coverageText,/Not covered through AHCCCS/);
}
for(const brand of ['LAGEVRIO','PAXLOVID']) {
 const row=rows.find(r=>r.brand===brand);
 assert.equal(row.pa,'not_specified',brand+' minimum age mislabeled PA');
 assert.equal(row.ageLimited,true);
 assert.match(row.ageRestrictionText,/Minimum Patient Age/);
}
for(const brand of ['SINGULAIR','LIKMEZ','SYNAGIS']) {
 const row=rows.find(r=>r.brand===brand&&r.paExceptionText);
 assert(row,brand+' exemption missing');
 assert.equal(row.pa,'not_specified',brand+' exemption implies PA outside exception');
}
const nadolol=rows.find(r=>r.name==='NADOLOL');
assert.equal(nadolol.pa,'not_specified');assert.match(nadolol.paExceptionText,/UNDER 19/);
for(const name of ['GLECAPREVIR-PIBRENTASVIR TABLETS','GLECAPREVIR-PIBRENTASVIR PACKETS','SOFOSBUVIR-VELPATASVIR TABLETS']) {
 const row=rows.find(r=>r.name===name);
 assert.equal(row.pa,'conditional','HCV prior-treatment condition misclassified: '+name);
 assert.match(row.paText,/if member has been treated previously/);
}
for(const name of ['LIDOCAINE HCL LOTION','LIDOCAINE PATCH']) {
 const row=data.medications.find(r=>r.planId==='banner-ufc'&&r.name===name);
 assert.equal(row.pa,'conditional',name+' concentration condition lost');
 assert.match(row.paText,/Only/);
}
const ctx={state:{data},normalize:s=>String(s||'').trim().toLowerCase(),
 escapeHtml:s=>String(s||'').replace(/</g,'&lt;').replace(/>/g,'&gt;'),
 linkedPolicyPanels:()=>'',clinicalGuidanceFor:()=>null,criteriaLibraryShortcut:()=>'',statusChips:()=>'',
 readableMedicationName:s=>String(s),sourcesLink:()=>'',recordDetails:()=>'',medicationPolicyDropdown:()=>''};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('  function medicationGroupCard('),source.indexOf('  function render()')),ctx);
const conditional=rows.filter(r=>r.pa==='conditional');
for(const row of conditional) {
 ctx.group={label:row.name,brands:[],records:[row],isStatewide:true,statewideRecord:row};
 const html=vm.runInContext('medicationGroupCard(group)',ctx);
 assert(!html.includes('PA is required by the statewide drug list.'),row.name+' unconditional assertion');
 assert(html.includes(ctx.escapeHtml(row.paText)),row.name+' condition missing');
}
assert(conditional.length>200);
console.log('PASS: 14 reviewed PA-column product corrections, explicit noncoverage, age restrictions, PA exemptions, concentration/prior-treatment PA, and '+conditional.length+' conditional statewide panels preserve source wording');
