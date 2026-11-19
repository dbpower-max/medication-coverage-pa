const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const load=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=load('_site/data.json.gz');for(const f of Object.values(data.planDataFiles||{}))data.medications.push(...load('_site/'+f.split('?')[0].replace(/^\.\//,'')));delete data.planDataFiles;
const ctx={Intl,console,document:{addEventListener:()=>{}},fetch:async url=>({ok:true,json:async()=>load('_site/'+url.split('?')[0].replace(/^\.\//,'')),text:async()=>fs.readFileSync('_site/'+url.split('?')[0].replace(/^\.\//,''),'utf8')})};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('_site/app.js','utf8').replace("document.addEventListener('DOMContentLoaded', init);",'globalThis.api={state,planMedicationGroups,medicationGroupCard,populateCardClinical,uhcGroupBindings,clinicalGuidanceFor};'),ctx);
const a=ctx.api;a.state.data=data;a.state.planId='uhc-community-az';
async function open(g){const content={innerHTML:'',isConnected:true},ref={innerHTML:''};a.medicationGroupCard(g);const d={open:true,dataset:{cardClinical:g.key||g.label},querySelector:s=>s==='.card-pa-references'?ref:content};await a.populateCardClinical(d);assert.equal(d.dataset.loaded,'true',g.label+' did not load');return {html:content.innerHTML,ref:ref.innerHTML};}
(async()=>{
 const groups=a.planMedicationGroups().filter(g=>g.records.some(r=>r.planId==='uhc-community-az'&&!r.isStatewideReference&&(['required','conditional'].includes(r.pa)||r.qlAmount||r.qlDays)));
 const mounjaro=a.planMedicationGroups().find(g=>/mounjaro/i.test(g.label));assert(a.medicationGroupCard(mounjaro).includes('uhc-az-clinical-pharmacy-2026-11-01.pdf'),'Initial UHC reference incorrectly points to statewide criteria');
 let n=0;
 for(const g of groups){const out=await open(g);assert(out.html.trim(),g.label+' empty');assert(out.ref.includes('href='),g.label+' no policy/formulary reference');assert(!out.html.includes('Formatted criteria for this medication are not available'),'Empty template remains');
  if (a.uhcGroupBindings(g).some(binding => binding.policyId.endsWith('gl-735259'))) {
   const [pa, exception] = out.html.split('<h4>Therapeutic duplication exceptions</h4>');
   assert(!pa.includes('The requested medication will be used exclusively'),g.label+' shows GL-735259 as standard PA');
   assert(exception?.includes('DUR: Therapeutic Duplication'),g.label+' missing scoped duplication');
   assert(out.ref.includes('Duplication reference'),g.label+' mislabeled duplication reference');
  }
  n++;
 }
 for(const term of ['Apidra SoloStar','Apidra Vial']){const g=groups.find(g=>g.label.toLowerCase()===term.toLowerCase());assert(g,term);assert(!a.medicationGroupCard(g).includes('PA is printed in at least one source row.'),'Internal PA-column notice leaked');const out=await open(g);assert(out.html.includes('THREE')&&out.html.includes('pharmacy claims'),'Nonpreferred criteria missing');assert(out.html.includes('requested dosage cannot be achieved'),'QL exception criteria missing');assert(out.ref.includes('page=1202')&&out.ref.includes('page=702'),'Wrong UHC source');}
 const qvar=groups.find(g=>/qvar/i.test(g.label)&&a.clinicalGuidanceFor(g));if(qvar){const out=await open(qvar);assert(out.html.includes('Diagnosis of asthma'),'Existing non-PA clinical guide erased by quantity-policy loading');}
 const supplies=groups.filter(g=>g.records.some(r=>r.policyQuantityLimit));assert(supplies.length>5);
 for(const g of supplies){const out=await open(g);assert(out.html.includes('more frequent delivery of insulin'));const card=a.medicationGroupCard(g);assert(card.includes('6 pen needles per day and 6 syringes per day.'));if(g.records.every(r=>r.preferred==='preferred'))assert(!out.html.includes('unable to use a preferred'),'Preferred product got nonpreferred PA');}
 const dpp4Cases = [
  ['9f51490fe737364d', [['Alogliptin', 0]]],
  ['58dba0a2f1b044a1', [['Brand Januvia', 0]]],
  ['0bbc20aa86db36bf', [['Jentadueto XR', 1]]],
  ['e15eed57b66af71f', [['Brand Janumet', 0], ['Generic sitagliptin phosphate/metformin', 1]]],
 ];
 for (const [id, products] of dpp4Cases) {
  const g = groups.find(group => group.records.some(record => record.id === 'uhc-oct-complete-' + id));
  assert(g, id);
  const bindings = a.uhcGroupBindings(g);
  const dpp4Bindings = bindings.filter(binding => binding.policyId.endsWith('gl-752241'));
  assert.deepEqual(Array.from(dpp4Bindings, binding => [binding.productLabel, ...binding.branchIndexes]).sort(), products.sort());
  const duplication = bindings.filter(binding => binding.policyId.endsWith('gl-735259'));
  assert.equal(duplication.length, 1);
  assert.equal(duplication[0].role, 'duplication');
  const {html, ref} = await open(g);
  const [pa, other] = html.split('<h4>Therapeutic duplication exceptions</h4>');
  assert(pa.startsWith('<section class="uhc-restriction-criteria"><h4>Prior authorization</h4>'));
  assert(other.includes('when a therapeutic duplication edit is triggered'));
  assert.equal(/THREE of the following/i.test(pa), products.some(([,index]) => index === 1));
  assert(ref.includes('page=459') && ref.includes('Duplication reference') && ref.includes('QL reference'));
  for (const [label] of products) {
   assert(pa.includes('<strong>Product:</strong> ' + label));
   if (products.length > 1) assert(a.medicationGroupCard(g).includes('Coverage attributes for ' + label));
  }
  if (products.length > 1) {
   const brand = pa.split('<strong>Product:</strong> Brand Janumet')[1]
     .split('<strong>Product:</strong> Generic sitagliptin phosphate/metformin')[0];
   assert(!/THREE of the following/i.test(brand));
  }
 }
 console.log('PASS: Four DPP-4 cards show exact product PA branches and a separately labeled duplication exception.');
 const byId = id => groups.find(group => group.records.some(record => record.id === 'uhc-oct-complete-' + id));
 const tablet = byId('c2dc81c1dae5f5c3');
 const solution = byId('c2d62d774fbaa9ab');
 assert(tablet && solution && tablet !== solution);
 assert.match(tablet.label, /tablet/i);
 assert.match(solution.label, /oral solution/i);
 for (const group of [tablet, solution]) {
  assert.match(group.search, /Zoloft/i);
  const card = a.medicationGroupCard(group);
  for (const chip of ['Preferred', 'Age limit', 'Quantity limit']) assert(card.includes('>' + chip + '</span>'));
  assert(!card.includes('>PA required</span>'));
  const {html, ref} = await open(group);
  assert(html.includes('Age-specific PA criteria') && html.includes('6 years of age or younger'));
  assert.equal(html.includes('greater than 12 years of age'), group === solution);
  assert.equal(html.includes('unable to swallow the oral tablet/capsule'), group === solution);
  assert(ref.includes('page=116'));
 }
 const pristiq = byId('e40b2afd31f1fb40');
 assert(pristiq && pristiq === byId('094b55526d4ad05f'));
 const card = a.medicationGroupCard(pristiq);
 assert.match(card, /Coverage attributes for Brand Pristiq[^]*?Nonpreferred[^]*?>PA required<[^]*?<\/div>/);
 assert.match(card, /Coverage attributes for Generic desvenlafaxine ER[^]*?>Preferred<[^]*?<\/div>/);
 assert.equal((card.match(/>PA required</g) || []).length, 1);
 const {html, ref} = await open(pristiq);
 const [brandCriteria, genericCriteria] = html.split('Age-specific PA criteria');
 assert(brandCriteria.includes('Brand Pristiq') && brandCriteria.includes('at least 3'));
 assert(genericCriteria.includes('Generic desvenlafaxine ER') && genericCriteria.includes('6 years of age or younger'));
 assert(!genericCriteria.includes('at least 3'));
 assert(ref.includes('page=116'));
 console.log('PASS: Sertraline tablet and solution criteria are isolated; Pristiq and generic restrictions and clinical criteria are labeled.');
 const tylenol = [
  ['be91d378ac6cf394', /suspension 160 mg\/5\s*mL/i],
  ['39c4999cab7992c8', /chewable 160 mg/i],
  ['847afe1526008a20', /tablet 325 mg, 500 mg/i],
  ['974130f36218cf8a', /extended release 650 mg/i],
 ];
 const presentations = tylenol.map(([id, form]) => {
  const group = byId(id);
  assert(group && form.test(group.label), id + ' missing printed Tylenol form or strength');
  assert.match(group.search, /tylenol/i);
  assert.match(group.search, /acetaminophen|arthritis pain/i);
  const card = a.medicationGroupCard(group);
  assert(card.includes('>Quantity limit</span>') && !card.includes('>PA required</span>'));
  return group;
 });
 assert.equal(new Set(presentations).size, tylenol.length);
 for (const id of ['a709d5d38c2fadd5', '54172b754703daa3']) {
  const {html, ref} = await open(byId(id));
  const [pa, exception] = html.split('<h4>Therapeutic duplication exceptions</h4>');
  assert(pa.includes('postherpetic neuralgia') && exception.includes('DUR: Therapeutic Duplication'));
  assert(ref.includes('page=729'));
 }
 const naprelan = await open(byId('59050bbcdc345020'));
 assert(naprelan.html.includes('General nonpreferred PA criteria') &&
  naprelan.html.includes('Product-specific approval criteria are unverified.'));
 assert(a.medicationGroupCard(byId('59050bbcdc345020')).includes('>PA required</span>'));
 const tiotropium = await open(byId('818668349b64ef42'));
 assert(tiotropium.html.includes('The formulary lists conditional PA.'));
 assert(!tiotropium.html.includes('PA is required.'));
 assert.match(tiotropium.html, /Applies to:<\/strong> Spiriva Handihaler \(Brand For Tiotropium Bromide\)/i);
 console.log('PASS: four Tylenol presentations remain distinct; Gralise product PA, Naprelan fallback and conditional tiotropium duplication are separately scoped.');
 const packet = byId('b91029349d6055f8');
 const tabletGroup = byId('fb9cfa1b045ef925');
 assert(packet && packet === byId('4848e3a8d39fd8d9') && tabletGroup && packet !== tabletGroup);
 assert.match(packet.label, /pantoprazole.*packets.*protonix/i);
 assert(!a.planMedicationGroups().some(group => /tablet/i.test(group.label) && group.records.some(record =>
  /b91029349d6055f8|4848e3a8d39fd8d9/.test(record.id))));
 const packetCard = a.medicationGroupCard(packet);
 for (const [label,tier] of [['Generic pantoprazole packets',1], ['Brand Protonix packets',2]]) {
  const chips = packetCard.split('Coverage attributes for ' + label)[1].split('</div>')[0];
  assert(chips.includes('Tier ' + tier) && chips.includes('Quantity limit') && chips.includes('Age limit'));
 }
 assert(!/>(?:PA required|Conditional PA)</.test(packetCard));
 assert(packetCard.includes('Packet PA guideline') && packetCard.includes('page=1380'));
 const packetPolicy = await open(packet);
 assert(packetPolicy.ref.includes('page=1380') && packetPolicy.ref.includes('Packet PA guideline'));
 assert(packetPolicy.html.includes('leaves their PA fields blank'));
 for (const text of ['less than 18 years', '18 years of age or older', 'unable to swallow solid oral dosage forms', 'failure to lansoprazole ODT']) assert(packetPolicy.html.includes(text));
 assert(!packetPolicy.html.includes('Brand Nexium') && !packetPolicy.html.includes('generic esomeprazole'));
 assert(!(await open(tabletGroup)).ref.includes('page=1380'));
 const nexiumPacket = await open(byId('5c3694b58912d172'));
 assert(nexiumPacket.ref.includes('page=1380') && nexiumPacket.html.includes('Brand Nexium'));
 console.log('PASS: Protonix and generic packets share one UHC card with separate tier chips and source-scoped GL-255208 criteria; tablets and Nexium keep their own scopes.');
 a.state.planId='banner-ufc';assert.equal(a.uhcGroupBindings(groups[0]).length,0,'UHC policy leaked across plans');
 console.log('PASS: '+n+' restricted UHC cards load clinical content and source references; Apidra nonpreferred + QL; preferred/nonpreferred syringe branches; plan isolation');
})().catch(e=>{console.error(e);process.exitCode=1});
