const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const load=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=load('_site/data.json.gz');for(const f of Object.values(data.planDataFiles||{}))data.medications.push(...load('_site/'+f.split('?')[0].replace(/^\.\//,'')));delete data.planDataFiles;
const ctx={Intl,console,document:{addEventListener:()=>{}},fetch:async url=>({ok:true,json:async()=>load('_site/'+url.split('?')[0].replace(/^\.\//,'')),text:async()=>fs.readFileSync('_site/'+url.split('?')[0].replace(/^\.\//,''),'utf8')})};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('_site/app.js','utf8').replace("document.addEventListener('DOMContentLoaded', init);",'globalThis.api={state,planMedicationGroups,medicationGroupCard,populateCardClinical,uhcGroupBindings,clinicalGuidanceFor,recordDetails};'),ctx);
const a=ctx.api;a.state.data=data;a.state.planId='uhc-community-az';
async function open(g){const content={innerHTML:'',isConnected:true},ref={innerHTML:''};a.medicationGroupCard(g);const d={open:true,dataset:{cardClinical:g.key||g.label},querySelector:s=>s==='.card-pa-references'?ref:content};await a.populateCardClinical(d);assert.equal(d.dataset.loaded,'true',g.label+' did not load');return {html:content.innerHTML,ref:ref.innerHTML};}
(async()=>{
 const groups=a.planMedicationGroups().filter(g=>g.records.some(r=>r.planId==='uhc-community-az'&&!r.isStatewideReference&&(['required','conditional'].includes(r.pa)||r.qlAmount||r.qlDays)));
 for (const suffix of ['9cd407726d2e7fc5','6fc882e449630255']) {
   const id='uhc-oct-complete-'+suffix;
   const g=groups.find(group=>group.records.some(r=>r.id===id));
   const card=a.medicationGroupCard(g);
   const detail=await open(g);
   assert.equal(g.records.find(r=>r.id===id).pa,'required');
   assert(card.includes('Criteria for this exact presentation are unverified.'));
   assert(![card,detail.html,detail.ref].join('').includes('gl-565277'));
   assert(!detail.html.includes('For Desmoda ONLY'));
 }
 for (const [suffix,pages] of [['87576cc498d5cebd',[135]],['06139dd1f71f96aa',[149]],['b979e34950fd619d',[135,149]]]) {
   const id='uhc-oct-complete-'+suffix;
   const g=groups.find(group=>group.records.some(r=>r.id===id));
   const output=await open(g);
   for(const page of [133,135,149]) {
     assert.equal(output.html.includes('Criteria source · PDF page '+page+'<'),pages.includes(page),id+' page '+page);
   }
 }
 for (const [name,code,expected] of [
   ['dronabinol oral capsule (generic for MARINOL)','397200',[1,3]],
   ['FORTEO (brand for teriparatide)','755194',[0,2]],
   ['TROKENDI XR (brand for topiramate er)','572198',[12]],
   ['topiramate er oral capsule er 24 hour sprinkle','572198',[12]],
   ['XELJANZ XR (brand for tofacitinib citrate er)','657310',[0,1,3,4,5,6,7,8]]
 ]) {
   const record=data.medications.find(r=>r.planId===a.state.planId&&r.sourceEffective==='2026-10-01'&&r.name===name);
   const binding=record.uhcClinicalBindings.find(b=>b.policyId.endsWith(code)&&b.role==='product');
   assert.deepEqual(binding.branchIndexes,expected,name);
 }
 for (const [suffix,expectedPages,excludedPage] of [
   ['367d1f3038b2b927',[],93],
   ['c4664159ec823baf',[1389,1391],335],
   ['96f164d71a0d7aab',[986,987],1488],
   ['a2446a6eca08c16e',[986,987],1488],
 ]) {
   const id='uhc-oct-complete-'+suffix;
   const group=groups.find(g=>g.records.some(r=>r.id===id));
   const result=await open(group);
   for(const page of expectedPages) assert(result.html.includes('Criteria source · PDF page '+page+'<'),id);
   assert(!result.html.includes('Criteria source · PDF page '+excludedPage+'<'),id);
   if(!expectedPages.length) assert(a.medicationGroupCard(group).includes('Criteria for this exact presentation are unverified.'));
 }
 const samsca=groups.find(g=>g.records.some(r=>r.name.startsWith('SAMSCA (brand')));
 const samscaContent=await open(samsca);
 assert(samscaContent.html.includes('Criteria source · PDF page 1488<'));
 assert(!samscaContent.html.includes('Criteria source · PDF page 986<'));
 const mounjaro=a.planMedicationGroups().find(g=>/mounjaro/i.test(g.label));assert(a.medicationGroupCard(mounjaro).includes('uhc-az-clinical-pharmacy-2026-11-01.pdf'),'Initial UHC reference incorrectly points to statewide criteria');
 let n=0;
 for(const g of groups){const out=await open(g);assert(out.html.trim(),g.label+' empty');assert(out.ref.includes('href='),g.label+' no policy/formulary reference');assert(!out.html.includes('Formatted criteria for this medication are not available'),'Empty template remains');
  if (a.uhcGroupBindings(g).some(binding => binding.policyId.endsWith('gl-735259'))) {
   const [pa, exception] = out.html.split('<h4>Therapeutic duplication exceptions</h4>');
   assert(!pa.includes('The requested medication will be used exclusively'),g.label+' shows GL-735259 as standard PA');
   assert(exception?.includes('DUR: Therapeutic Duplication'),g.label+' missing scoped duplication');
   assert(out.ref.includes('Duplication reference'),g.label+' mislabeled duplication reference');
  }
  if (a.uhcGroupBindings(g).some(binding => binding.policyId.endsWith('gl-733328'))) {
   const [pa, exceptions] = out.html.split('<h4>Therapeutic duplication exceptions</h4>');
   assert(!pa.includes('DUR: Therapeutic Duplication'), g.label);
   assert(exceptions?.includes('DUR: Therapeutic Duplication'), g.label);
   assert.match(out.ref, /page=1716[^>]*>Duplication reference/);
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
 const acthar = byId('14411026d49668ea'), cortrophin = byId('9b40fc8558feebd0');
 assert(acthar && cortrophin && acthar !== cortrophin);
 for (const [group, indexes, scope] of [[acthar, [0,1], 'Acthar Gel vial only (PDL device unspecified)'], [cortrophin, [1], 'Cortrophin Gel - OMS (confirm covered vial or syringe)']]) {
  const binding = a.uhcGroupBindings(group).find(b => b.policyId.endsWith('gl-235210'));
  assert.deepEqual(Array.from(binding.branchIndexes), indexes);
  const {html, ref} = await open(group);
  assert(html.includes(scope) && html.includes('Opsoclonus-myoclonus'));
  assert.equal(html.includes('Infantile spasm'), group === acthar);
  assert(ref.includes('page=17'));
  assert(a.medicationGroupCard(group).includes('>PA required<'));
 }
 console.log('PASS: Acthar vial-only PA branch and Cortrophin OMS branch remain distinct in generated cards.');

 // Specialty presentation labels must not merge named devices, invent eligible packages, or change PA.
 const specialties = [["14411026d49668ea","Acthar Gel (Repository Corticotropin Injection; Device Unspecified by UHC)","https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=7b48ddec-e815-45f4-9ca0-5c0daaf56f30"],["9b40fc8558feebd0","Cortrophin Gel (Repository Corticotropin Injection; Device Unspecified by UHC)","https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f27544ee-a0e2-4d84-b193-1c9efdf9e34c"],["e4f26f2f128c5fba","Actimmune (Interferon Gamma-1b) Subcutaneous Injection","https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=5d0b1256-1981-4519-94f4-a4a2f98bd8a3"],["649c128564a43176","Hadlima PushTouch (Adalimumab-bwwd) Subcutaneous Autoinjector","https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=4774a951-3ce8-43b6-80b1-e6b23752aae6"],["ea00e4f93f96d5d5","Hadlima (Adalimumab-bwwd) Subcutaneous Solution (Device Unspecified by UHC)","https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=4774a951-3ce8-43b6-80b1-e6b23752aae6"]];
 for (const [id, label, url] of specialties) {
  const g=byId(id);
  assert(g && g.label===label, id+' incorrect presentation');
  assert.equal(g.records.length,1, id+' merged with a different plan or device');
  const record=g.records[0];
  assert.equal(record.pa,'required');
  assert.equal(record.preferred,['14411026d49668ea','9b40fc8558feebd0'].includes(id)?'non_preferred':'preferred');
  const card=a.medicationGroupCard(g);
  assert(card.includes(url) && card.includes('>PA required<'),id+' lost label link or PA');
 }
 assert.notEqual(byId('649c128564a43176'),byId('ea00e4f93f96d5d5'));
 assert(a.medicationGroupCard(byId('649c128564a43176')).includes('package-specific'));
 assert(a.medicationGroupCard(byId('ea00e4f93f96d5d5')).includes('confirm exact NDC'));
 const immune=byId('e4f26f2f128c5fba');
 assert.deepEqual(Array.from(a.uhcGroupBindings(immune).find(b=>b.policyId.endsWith('gl-140909')).branchIndexes),[0,1,2,3,4,5,6,7]);
 const immuneHtml=await open(immune);
 assert(immuneHtml.html.includes('Initial Authorization') && immuneHtml.html.includes('Reauthorization'));
 for(const id of ['649c128564a43176','ea00e4f93f96d5d5']){
  const g=byId(id), b=a.uhcGroupBindings(g).find(b=>b.policyId.endsWith('gl-541212'));
  assert.deepEqual(Array.from(b.branchIndexes),Array.from({length:15},(_,i)=>i));
 }
 console.log('PASS: Five specialty cards preserve exact plan scope, policy stages, label links and device distinctions.');

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
 assert.match(packet.label, /pantoprazole delayed-release granules for oral suspension \(protonix packets\)/i);
 assert.match(packet.search, /granules for oral suspension/i);
 assert(!a.planMedicationGroups().some(group => /tablet/i.test(group.label) && group.records.some(record =>
  /b91029349d6055f8|4848e3a8d39fd8d9/.test(record.id))));
 const packetCard = a.medicationGroupCard(packet);
 for (const [label,tier] of [['Generic pantoprazole granules (packets)',1], ['Brand Protonix granules (packets)',2]]) {
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
 const myrbetriq = [
  ['9e58d3383e72691c', 'Myrbetriq ER granules for oral suspension', /granules for oral suspension/i, true],
  ['136c92bbb186b8d5', 'Myrbetriq ER tablets', /ER tablets/i, false],
 ];
 for (const [id, label, form, ageLimited] of myrbetriq) {
  const group = byId(id);
  assert(group && form.test(group.label));
  assert.match(group.search, /myrbetriq/i);
  const card = a.medicationGroupCard(group);
  assert(card.includes('>PA required<') && card.includes('>Quantity limit<'));
  assert.equal(card.includes('>Age limit<'), ageLimited);
  const result = await open(group);
  assert(result.html.includes('<strong>Product:</strong> ' + label));
  assert(result.ref.includes('page=1239') && result.html.includes('THREE of'));
 }
 const toviaz = byId('ea20f5bf0c3a4bee');
 assert(toviaz && toviaz === byId('a366862b44246566'));
 const toviazCard = a.medicationGroupCard(toviaz);
 const brandChips = toviazCard.split('Coverage attributes for Brand Toviaz')[1].split('</div>')[0];
 const genericChips = toviazCard.split('Coverage attributes for Generic fesoterodine ER')[1].split('</div>')[0];
 assert(brandChips.includes('Tier 2') && brandChips.includes('>PA required<') && brandChips.includes('>Nonpreferred<'));
 assert(genericChips.includes('Tier 1') && genericChips.includes('>Preferred<') && !genericChips.includes('>PA required<'));
 for (const chips of [brandChips, genericChips]) assert(chips.includes('>Quantity limit<'));
 const toviazResult = await open(toviaz);
 assert.deepEqual(Array.from(a.uhcGroupBindings(toviaz).filter(b => b.policyId.endsWith('gl-647193')), b => b.productLabel), ['Brand Toviaz']);
 assert(toviazResult.html.includes('<strong>Product:</strong> Brand Toviaz') && toviazResult.ref.includes('page=1239'));
 console.log('PASS: Myrbetriq ER formulations retain distinct flags and criteria; the shared Toviaz card identifies brand-only PA.');
 const estradiolCases = [
  ['4a1149afa9a553fd', /Alora.*Twice-Weekly Patch/i, false, true],
  ['e47a9b1dca9eed6b', /Climara.*Weekly Patch/i, false, true],
  ['a1fd4a9ce974ca76', /Divigel.*0\.25 mg\/0\.25 g.*1\.25 mg\/1\.25 g/i, true, true],
  ['9565852ad73b0131', /Divigel.*1 mg\/g/i, true, false],
  ['928b9ed963c27b15', /EstroGel.*Transdermal Gel Pump/i, true, false],
  ['4fe26eac35258974', /Minivelle.*Twice-Weekly Patch/i, false, true],
  ['962d779bc98c5112', /Vagifem.*Vaginal Insert/i, true, true],
  ['aef4eca1a35449a0', /Vivelle-Dot.*Twice-Weekly Patch/i, false, true],
 ];
 const estradiolGroups = new Set();
 for (const [id, label, pa, ql] of estradiolCases) {
  const group = byId(id);
  assert(group && label.test(group.label), group?.label || id);
  assert.match(group.search, /estradiol/i);
  assert.equal(group.records.length, 1);
  const card = a.medicationGroupCard(group);
  assert.equal(card.includes('>PA required<'), pa);
  assert.equal(card.includes('>Quantity limit<'), ql);
  const {html,ref} = await open(group);
  assert.equal(html.includes('Product-specific approval criteria are unverified.'), pa);
  assert.equal(html.includes('General nonpreferred PA criteria'), pa);
  assert.equal(ref.includes('QL reference'), ql);
  estradiolGroups.add(group);
 }
 assert.equal(estradiolGroups.size, estradiolCases.length);
 console.log('PASS: Eight UHC estradiol listings have separate cards with their own source flags and policy scope.');
 const testosteroneCases = [
  ['95bdf1191fb6ac5a', /AndroGel.*Pump.*Concentration Unspecified/i, true],
  ['48446e194e4aaa49', /Testim.*Testosterone Gel/i, false],
  ['4f5abf9646902163', /Vogelxo.*Testosterone Gel/i, false],
  ['0618ed2eee749f42', /Depo-Testosterone.*IM.*Concentration Unspecified/i, true],
  ['95f3abcf725dc69c', /Testosterone Cypionate 200 mg\/mL IM Solution/i, true],
 ];
 const testosteroneGroups = new Set();
 for (const [id, label, preferred] of testosteroneCases) {
  const group = byId(id);
  assert(group && label.test(group.label), group?.label || id);
  assert.match(group.search, /testosterone/i);
  assert.equal(group.records.length, 1);
  const card = a.medicationGroupCard(group);
  assert(card.includes('>PA required<') && card.includes('>Quantity limit<'));
  assert.equal(card.includes('>Preferred<'), preferred);
  assert.equal(card.includes('>Nonpreferred<'), !preferred);
  const {html, ref} = await open(group);
  assert(html.includes('Hypogonadism') && html.includes('Initial Authorization'));
  assert(ref.includes('page=1689') && ref.includes('QL reference'));
  testosteroneGroups.add(group);
 }
 assert.equal(testosteroneGroups.size, testosteroneCases.length);
 for (const id of ['0ea5d84001467f7a','4532690d14e80d40','824717b27ea6c089','edf9f82d54c3283d','ee7ee2bd895649ed']) {
  const group = byId(id);
  assert(group && !testosteroneGroups.has(group), id);
 }
 console.log('PASS: Five UHC brand testosterone listings retain distinct flags, concentration scope and policy references.');
 const oralAzithromycin = byId('2cf325e856cd66c2');
 assert(oralAzithromycin);
 assert.equal(oralAzithromycin.label, 'Azithromycin Oral (Dosage Form Unspecified)');
 assert.equal(oralAzithromycin.records.length, 1);
 assert.match(oralAzithromycin.search, /Zithromax/i);
 const statewideAzithromycin = a.planMedicationGroups().filter(group => group.isStatewide && /azithromycin/i.test(group.label));
 assert(statewideAzithromycin.some(group => /tablets/i.test(group.label)));
 assert(statewideAzithromycin.every(group => !group.records.some(record => record.id === 'uhc-oct-complete-2cf325e856cd66c2')));
 const azithromycinCard = a.medicationGroupCard(oralAzithromycin);
 assert(azithromycinCard.includes('>Tier 1<') && azithromycinCard.includes('>Quantity limit<'));
 assert(!/>(?:PA required|Conditional PA)</.test(azithromycinCard));
 assert((await open(oralAzithromycin)).ref.includes('QL reference'));
 console.log('PASS: UHC azithromycin oral keeps its unspecified dosage form and exact PDL flags.');
 const triptans = [
  ['225b27c2efa3ce8d', 'Maxalt (Rizatriptan Tablets)', 'Maxalt tablets'],
  ['286fa8dd551d5183', 'Maxalt-MLT (Rizatriptan ODT)', 'Maxalt-MLT ODT'],
  ['391d5cb4040d560f', 'Generic Rizatriptan (Dosage Form Unspecified)'],
  ['7a2afaed6fab2683', 'Generic Sumatriptan Oral (Dosage Form Unspecified)'],
 ];
 for (const [id, label, product] of triptans) {
  const group = byId(id);
  assert(group && group.label === label);
  assert.equal(group.records.length, 1);
  const card = a.medicationGroupCard(group);
  assert(card.includes(product ? '>Tier 2<' : '>Tier 1<'));
  assert.equal(card.includes('>PA required<'), Boolean(product));
  assert(card.includes('>Quantity limit<'));
  const policy = a.uhcGroupBindings(group).filter(b => b.policyId.endsWith('gl-742200'));
  const {html,ref} = await open(group);
  assert.deepEqual(Array.from(policy, b => [b.role, ...b.branchIndexes]), product ? [['product',0],['quantity',3]] : []);
  if (product) assert(html.includes('<strong>Product:</strong> ' + product));
  assert.equal(ref.includes('page=1761'), Boolean(product));
  if (!product) assert(card.includes('QL reference') && !card.includes('PA reference'));
 }
 assert(a.planMedicationGroups().some(group => group.isStatewide && /sumatriptan.*tablets/i.test(group.label)));
 const nicotine = [
  ['d1c2937b9b38c3e1', /NicoDerm CQ.*Nicotine Patch/],
  ['3a0a37a01a0c20cd', /Nicorette.*Dosage Form Unspecified/],
  ['634f76b31abaf672', /Nicorette Mini.*Nicotine Lozenge/],
  ['d448da71a98f8d4c', /Nicorette Starter Kit.*Kit Contents Unspecified/],
  ['190ba800fac4ab36', /Thrive.*Dosage Form Unspecified/],
 ];
 for (const [id,label] of nicotine) {
  const group = byId(id);
  assert(group && label.test(group.label));
  assert.equal(group.records.length, 1);
  const card = a.medicationGroupCard(group);
  assert(card.includes('>Tier 2<') && card.includes('>Quantity limit<') && card.includes('>Age limit<'));
  assert(!card.includes('>PA required<'));
 }
 const injection = a.planMedicationGroups().find(group => group.records.some(r => r.id.endsWith('c9674280d79f813f')));
 assert(injection && injection.records.some(r => r.id.endsWith('79d267b3a75cff82')));
 const injectionCard = a.medicationGroupCard(injection);
 const generic = injectionCard.split('Coverage attributes for Generic for Kenalog-40')[1].split('</div>')[0];
 const unspecified = injectionCard.split('Coverage attributes for Triamcinolone acetonide injection (brand unspecified in formulary)')[1].split('</div>')[0];
 assert(generic.includes('>Tier 1<') && unspecified.includes('>Tier 2<'));
 assert(!injectionCard.includes('>PA required<'));
 const injection10 = a.planMedicationGroups().find(group => group.records.some(r => r.id.endsWith('3f0646c9671a33c6')));
 assert(injection10 && injection10 !== injection);
 console.log('PASS: Verified UHC triptan policy scopes, five nicotine presentations and both triamcinolone tier labels.');
 const pcpForms = [
  ['e018bef948c68b97', 'Generic Oseltamivir Oral (Dosage Form Unspecified)', 1, false, false],
  ['a71cdeaaee7ac819', 'Tamiflu (Oseltamivir, Dosage Form Unspecified)', 2, false, false],
  ['420688dc751a74bb', 'Montelukast Oral Granules (Singulair Packets)', 1, false, true],
  ['3ea94beb4ebaf734', 'Diclofenac Epolamine 1.3% Topical Patch (Flector)', 2, true, false],
 ];
 for (const [id, label, tier, pa, age] of pcpForms) {
  const group = byId(id);
  assert(group && group.label === label && group.records.length === 1);
  const card = a.medicationGroupCard(group);
  assert(card.includes('>Tier ' + tier + '<') && card.includes('>Quantity limit<'));
  assert.equal(card.includes('>PA required<'), pa);
  assert.equal(card.includes('>Age limit<'), age);
  assert(card.includes(pa ? 'PA reference' : 'QL reference'));
  const {html,ref} = await open(group);
  assert(ref.includes('QL reference'));
  assert.equal(ref.includes('page=1738'), pa);
  if (pa) assert.match(html, /acute pain due to minor strains/i);
 }
 assert.match(byId('e018bef948c68b97').search, /Tamiflu/i);
 assert.match(byId('420688dc751a74bb').search, /Singulair/i);
 assert(a.planMedicationGroups().some(g => g.isStatewide && /oseltamivir.*capsules/i.test(g.label)
  && g.records.every(r => r.isStatewideReference)));
 for (const id of ['c1523d2c7cd562ed','856368f38bb1fe39']) {
  const group = byId(id);
  assert(group && !a.medicationGroupCard(group).includes('>Age limit<'));
 }
 console.log('PASS: UHC oseltamivir, montelukast and Flector display source-supported dosage forms and exact payer flags.');
 const insulinAndSupplies = [
  ['4b27f95aecd5c517', /Admelog.*Labeled Vial/, true],
  ['7fb64d26f93768e3', /Humalog.*Vial or Cartridge/, true],
  ['99b7a79d60f9be27', /Insulin Lispro U-100.*Labeled Vial/, false],
  ['a864ab78ab9356d7', /Humalog Mix 75\/25 KwikPen/, true],
  ['6b20c512802745b5', /75\/25 U-100 Prefilled Pen/, false],
  ['96922f638bb987d2', /Glargine-yfgn SC Solution.*Device Unspecified/, true],
  ['4270f8a1ce19e554', /Glargine-yfgn SC Pen Injector/, false],
  ['31c74f821a4c856f', /Semglee.*Device Unspecified/, true],
  ['c005b426150daab6', /BD Pen Needle Micro Ultra-Fine/, false],
  ['d8778fc0002099ad', /BD Pen Needle Mini Ultra-Fine/, false],
  ['29ba3ba96676a42d', /BD Ultra-Fine Pen Needles.*Size Unspecified/, false],
  ['f4049ada026c8bf2', /Embecta Nano Pen Needles/, false],
  ['81e91bccf7a7db62', /Embecta Nano 2 Gen Pen Needles/, false],
  ['3d04833acbadee64', /31G × 5 mm or 8 mm/, false],
  ['a78b03c4eeae093a', /32G × 6 mm/, false],
  ['41e85281dfbe85c2', /29G × 12 mm.*33G × 4 mm/, true],
  ['73c972bcaea5b9de', /32G × 4 mm or 6 mm/, true],
  ['d44e6b5c3ba5f44e', /BD Ultra-Fine Insulin Syringes.*PA-Flagged Listing/, true],
  ['72a4f8fa78ad8fa9', /31G × 15\/64-inch, 0\.3 mL/, false],
  ['95af09ad92b3e0f1', /31G × 15\/64-inch, 0\.5 mL/, false],
  ['6746ad40c619fcaa', /31G × 15\/64-inch, 1 mL/, false],
 ];
 const insulinCards = new Set();
 for (const [id,label,pa] of insulinAndSupplies) {
  const group = byId(id);
  assert(group && label.test(group.label), group?.label || id);
  assert.equal(group.records.length, 1, group.label);
  const card = a.medicationGroupCard(group);
  assert(card.includes('>Tier 2<') && card.includes('>Quantity limit<'));
  assert.equal(card.includes('>PA required<'), pa, group.label);
  const {html,ref} = await open(group);
  assert(ref.includes('QL reference'));
  if (!pa) assert(!card.includes('PA reference') && !ref.includes('PA reference') && !html.includes('General nonpreferred PA criteria'), group.label);
  insulinCards.add(group);
 }
 assert.equal(insulinCards.size, insulinAndSupplies.length);
 const standardLispro = byId('2dbe0497f9246f1b');
 assert.equal(standardLispro.label, 'Insulin Lispro U-100 Prefilled Pen (1-Unit Increments)');
 assert.equal(standardLispro.records.length, 1);
 assert(!a.medicationGroupCard(standardLispro).includes('>PA required<'));
 const vialCard = a.medicationGroupCard(byId('99b7a79d60f9be27'));
 assert(vialCard.includes('<h3>Insulin lispro 100 units/mL multidose vial</h3>'));
 assert(vialCard.includes('Vial size: 10 mL') && !vialCard.includes('3 mL'));
 assert(vialCard.includes('UHC does not specify a preferred vial size.'));
 assert(a.medicationGroupCard(byId('4b27f95aecd5c517')).includes('Vial sizes: 3 mL, 10 mL'));
 assert(a.medicationGroupCard(standardLispro).includes('3 mL · 1-unit increments'));
 const junior = byId('1a0caccc9f7c79ae');
 assert(junior && junior === byId('d68963fe88140f42') && junior.records.length === 2);
 assert.match(junior.label, /Prefilled Pen.*0\.5-Unit Increments/i);
 const juniorCard = a.medicationGroupCard(junior);
 assert(juniorCard.includes('<h3>Insulin lispro 100 units/mL Junior KwikPen</h3>'));
 assert(juniorCard.includes('3 mL · 0.5-unit increments'));
 const brandJunior = juniorCard.split('Coverage attributes for Humalog Junior KwikPen')[1].split('</div>')[0];
 const otherJunior = juniorCard.split('Coverage attributes for Insulin Lispro Junior KwikPen Listing')[1].split('</div>')[0];
 assert(brandJunior.includes('>PA required<') && !otherJunior.includes('>PA required<'));
 const juniorPolicy = await open(junior);
 assert(juniorPolicy.html.includes('General nonpreferred PA criteria'));
 assert(juniorPolicy.html.includes('<strong>Applies to:</strong> Humalog Junior KwikPen'));
 assert(juniorPolicy.html.includes('Product-specific approval criteria are unverified.'));
 console.log('PASS: 23 UHC insulin/supply rows keep exact device descriptions, PA scope and quantity references across 22 cards.');
 const planGroups = a.planMedicationGroups();
 const findExact = id => planGroups.find(g => g.records.some(r => r.id === 'uhc-oct-complete-' + id));
 const subtypeB = planGroups.filter(g => a.uhcGroupBindings(g).some(b => b.policyId.endsWith('gl-733328')));
 const subtypeBRows = subtypeB.flatMap(g => g.records).filter(r => r.uhcClinicalBindings?.some(b => b.policyId.endsWith('gl-733328')));
 // The generic row references Glatopa. Its payer attributes belong on a separate card from Copaxone.
 assert.notEqual(findExact('f39eb58c8f337264'), findExact('874cc6f50f122e2b'));
 assert.equal(subtypeB.length, 76);
 assert.equal(subtypeBRows.length, 76);
 assert(subtypeBRows.every(r => r.pa === 'required'));
 assert.equal(subtypeBRows.filter(r => r.uhcClinicalBindings.some(b => b.role === 'product')).length, 61);
 const auditedSupplies = [
  ['3b25d168e772f4bb', /BD AutoShield Duo/, 'conflict'],
  ['c97b122f4df189e3', /Embecta AutoShield Duo/],
  ['c4e9ac46f2349955', /Size Unspecified/, 'conflict'],
  ['22070f6565eaddd7', /31G × 5\/16-inch, 0.3 mL/, 'conflict'],
  ['8f8bfca30d969dde', /Half-Unit Markings/],
  ['f91198d15b3621e2', /30G × 1\/2-inch, 0.3 mL/],
  ['f119ef35ec9d1e98', /30G × 1\/2-inch, 0.5 mL/],
  ['1a93bee462473cf9', /30G × 1\/2-inch, 1 mL/],
  ['f585b5e77ab99c2b', /31G × 5\/16-inch, 0.3 mL/],
  ['3369cc3c10c7bce9', /31G × 5\/16-inch, 0.5 mL/],
  ['c13ee393243d1dfe', /31G × 5\/16-inch, 1 mL/],
  ['47f6c2b5f18c5f97', /29G × 12.7 mm/],
  ['8a18c2c65b39a452', /29G × 12.7 mm/, 'required'],
  ['71a7f5b0011ace42', /29G.*30G.*31G/, 'required'],
  ['982cb3c91791283c', /0.3 or 0.5 mL/, 'required'],
 ];
 for (const [id, label, pa] of auditedSupplies) {
  const g = findExact(id);
  assert.match(g.label, label);
  assert.equal(g.records.length, 1);
  const card = a.medicationGroupCard(g);
  assert.equal(card.includes('>PA listings conflict<'), pa === 'conflict', g.label);
  assert.equal(card.includes('>PA required<'), pa === 'required', g.label);
  if (pa === 'conflict') {
   const details = a.recordDetails(g.records[0]);
   assert.match(details, /Both printed listings/);
   assert.match(details, /Tier 2; QL/);
   assert.match(details, /Tier 2; PA; QL/);
  }
  const {html, ref} = await open(g);
  assert(ref.includes('QL reference') && ref.includes('page=949'), g.label);
  if (pa !== 'required') assert(!html.includes('<h4>Prior authorization</h4>'), g.label);
 }
 const solutionGroup = findExact('ef1b74ce89ce3609');
 assert.equal(solutionGroup, findExact('3a61ac9c932595a2'));
 const oralSolutionCard = a.medicationGroupCard(solutionGroup);
 assert.match(oralSolutionCard, /Coverage attributes for Brand Risperdal oral solution/);
 assert.match(oralSolutionCard, /Coverage attributes for Generic risperidone oral solution/);
 assert.match(oralSolutionCard, /PA listings conflict/);
 assert.match(oralSolutionCard, /age 8 and older.*age 6 and older/);
 const risperidoneSolution = await open(solutionGroup);
 assert.match(risperidoneSolution.html, /Brand Risperdal oral solution \/ Generic risperidone oral solution/);
 const tablets = findExact('9218dfef977f1cc2');
 assert.equal(tablets.records.length, 6);
 assert(tablets !== solutionGroup);
 assert(tablets.records.every(r => r.planId === 'uhc-community-az'));
 const lowerTabletHtml = (await open(tablets)).html;
 assert.match(lowerTabletHtml, /Brand Risperdal tablets.*Generic risperidone tablets 0.25–3 mg/);
 const npSection = lowerTabletHtml.slice(lowerTabletHtml.lastIndexOf('<strong>Product:</strong>'));
 assert.match(npSection, /Brand Risperdal tablets/);
 assert.doesNotMatch(npSection, /Generic risperidone tablets/);
 const four = findExact('f4378fc22a9c05ca');
 assert.equal(four, findExact('3b293a6608a5bb5c'));
 assert.equal(four.records.length, 2);
 const fourCard = a.medicationGroupCard(four);
 assert.equal((fourCard.match(/>Diagnosis required</g) || []).length, 2);
 assert(!fourCard.includes('>Conditional PA<') && !fourCard.includes('>PA required<'));
 assert(!(await open(four)).html.includes('<h4>Prior authorization</h4>'));
 const consta = findExact('8e6412598dc3cc82');
 assert.equal(consta.records.length, 5);
 const constaCard = a.medicationGroupCard(consta);
 assert.equal((constaCard.match(/>PA listings conflict</g) || []).length, 4);
 assert.match((await open(consta)).html, /<strong>Product:<\/strong> Brand Risperdal Consta/);
 const focalin = findExact('6dff573813c31f0b');
 assert.equal(focalin, findExact('b49b6b0ee990825a'));
 const focalinCard = a.medicationGroupCard(focalin);
 assert.match(focalinCard, /Coverage attributes for Generic dexmethylphenidate ER[^]*?Tier 1[^]*?Coverage attributes for Brand Focalin XR[^]*?Tier 2/);
 assert(focalinCard.includes('QL reference') && !focalinCard.includes('PA reference'));
 const caplets = findExact('8869cd1c155ab813');
 assert.equal(caplets.records.length, 4);
 const capletCard = a.medicationGroupCard(caplets);
 assert.equal((capletCard.match(/Drug Facts/g) || []).length, 4);
 assert.match(capletCard, /Acetaminophen 250 mg \/ aspirin 250 mg \/ caffeine 65 mg per caplet/);
 assert.doesNotMatch(a.medicationGroupCard(findExact('4df17abd4833e4f1')), /250 mg/);
 const macro = findExact('1f745c455ddaac86'), macrobid = findExact('2304475710970aa6');
 assert.match(macro.label, /^Nitrofurantoin Macrocrystals Capsules$/);
 assert.match(macrobid.label, /Monohydrate \/ Macrocrystals Capsules/);
 assert.equal(new Set([macro,macrobid,findExact('9e0eb4cf3a3dfd2b')]).size, 3);
 console.log('PASS: 115 UHC records retain exact product restrictions, policy scope and provider-facing labels.');
 a.state.planId='banner-ufc';assert.equal(a.uhcGroupBindings(groups[0]).length,0,'UHC policy leaked across plans');
 const bannerGroups=a.planMedicationGroups();
 const igRows=[
  ['3a476647011e0ef8','not_specified','Gammagard Liquid'],
  ['b99ccac646481857','preferred','Octagam 5%'],
  ['31c646f5de1a7360','preferred','Gammagard S/D'],
  ['8e1bca979c1c79f5','preferred','do not transfer that dosing to SC'],
  ['3393fbf3661bfb25','preferred','do not transfer that dosing to SC'],
  ['449f33903bd3010c','not_specified','cannot be transferred to this SC product'],
  ['20163d7b5f42cae1','preferred','cannot be transferred to this SC product']
 ];
 for(const [suffix,pref,caution] of igRows){
   const id='banner-full-'+suffix;
   const g=bannerGroups.find(g=>g.records.some(r=>r.id===id));
   assert(g,id);
   const r=g.records.find(r=>r.id===id);
   assert.equal(r.pa,'required');assert.equal(r.preferred,pref);
   const link=r.policySources.find(p=>p.policyCode==='GL-525296');
   assert(link&&link.scope.includes(caution),id+' route/indication scope missing');
   assert(a.medicationGroupCard(g).includes(caution),id+' missing visible option-specific caveat');
   assert(a.recordDetails(r).includes(caution),id+' missing source caveat');
 }
 const infliximab=bannerGroups.find(g=>g.records.some(r=>r.id==='banner-full-719caae0c9978dca'));
 assert(infliximab);
 const infliximabRow=infliximab.records.find(r=>r.id==='banner-full-719caae0c9978dca');
 assert.equal(infliximabRow.pa,'required');assert.equal(infliximabRow.preferred,'preferred');
 assert(infliximabRow.reviewedPresentation.policyUnverified);
 assert(a.medicationGroupCard(infliximab).includes('not a separately licensed biosimilar'));
 console.log('PASS: Eight exact Banner IG/infliximab options retain flags and route/product caveats.');

 console.log('PASS: '+n+' restricted UHC cards load clinical content and source references; Apidra nonpreferred + QL; preferred/nonpreferred syringe branches; plan isolation');
})().catch(e=>{console.error(e);process.exitCode=1});
