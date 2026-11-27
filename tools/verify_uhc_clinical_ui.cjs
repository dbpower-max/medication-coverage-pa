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
 // Reviewed UHC SC route and preference-specific seven-stage policy.
 for (const [suffix,pref,label] of [
   ['6e31fd16d0c3fee4','non_preferred','Actemra (Tocilizumab) Subcutaneous Injection'],
   ['2e1049037c5dbd67','preferred','Avtozma (Tocilizumab-anoh) Subcutaneous Injection'],
   ['4bfb77000b6496ad','preferred','Tyenne (Tocilizumab-aazg) Subcutaneous Injection']
 ]) {
   const id='uhc-oct-complete-'+suffix;
   const g=groups.find(group=>group.records.some(record=>record.id===id));
   assert(g,id+' missing');
   const record=g.records.find(r=>r.id===id);
   assert.equal(record.pa,'required');assert.equal(record.preferred,pref);
   assert.equal(record.reviewedPresentation.separate,true);
   const binding=record.uhcClinicalBindings.find(b=>b.policyId.endsWith('gl-565279')&&b.role==='product');
   assert.deepEqual(binding.branchIndexes,[0,1,2,3,4,5,6]);
   assert.equal(Boolean(binding.omitNonpreferredCondition),pref==='preferred');
   const card=a.medicationGroupCard(g);
   assert(card.includes(label),id+' missing dosage form');
   assert(card.includes('Exact payer device/package and numeric quantity limit are unverified'),id+' missing package hold');
   if(pref==='preferred')assert(card.includes('not an FDA-labeled '+(suffix==='4bfb77000b6496ad'?'Tyenne':'Avtozma')+' indication'),id+' missing label distinction');
   else assert(card.includes('ACTPen use has not been studied for SSc-ILD'),id+' missing device distinction');
   const out=await open(g);
   const pa=out.html.split('<h4>Therapeutic duplication exceptions</h4>')[0].split('<h4>Quantity-limit exceptions</h4>')[0];
   for(let page=1728;page<=1734;page++)assert(pa.includes('Criteria source · PDF page '+page+'<'),id+' missing stage page '+page);
   assert.equal(/history of failure to ALL preferred\*? tocilizumab biosimilars/i.test(pa),pref==='non_preferred',id+' wrong preference scope');
   assert(out.ref.includes('page=1728'),id+' wrong named policy source');
 }
 const scIds=new Set(['uhc-oct-complete-6e31fd16d0c3fee4','uhc-oct-complete-2e1049037c5dbd67','uhc-oct-complete-4bfb77000b6496ad']);
 for(const record of data.medications.filter(r=>!scIds.has(r.id)))assert(!record.uhcClinicalBindings?.some(b=>b.omitNonpreferredCondition),record.id+' preference override leaked');
 // Exact UHC UnoReady 300 mg device: mixed SC policy branches retain source text and scope.
 const unoId='uhc-oct-complete-9449c2ad49f55210';
 const uno=groups.find(g=>g.records.some(r=>r.id===unoId));assert(uno,unoId);
 const unoRow=uno.records.find(r=>r.id===unoId);
 assert.equal(unoRow.pa,'required');assert.equal(unoRow.preferred,'non_preferred');
 const unoPolicy=unoRow.uhcClinicalBindings.find(b=>b.role==='product'&&b.policyId.endsWith('gl-628292'));
 assert.deepEqual(unoPolicy.branchIndexes,[0,1,2,5,6,7,8]);
 assert(unoRow.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 const unoCard=a.medicationGroupCard(uno);
 for(const p of ['Cosentyx UnoReady (Secukinumab) 300 mg/2 mL Subcutaneous Pen','not for 75 mg or 150 mg doses or IV infusion','not pen-specific','numeric quantity limit are unverified'])assert(unoCard.includes(p),p);
 assert(unoCard.includes('href="'+unoRow.reviewedPresentation.labelUrl+'"'));
 const unoDetail=await open(uno);
 assert(unoDetail.html.includes('adult AS escalation; NOT the nr-axSpA or pediatric AS regimen'));
 assert(unoDetail.html.includes('pediatric HS weighing at least 90 kg'));
 assert(!unoDetail.html.includes('Enthesitis-Related Arthritis (ERA)'));
 assert(unoDetail.ref.includes('page=405'));
 // Avlayah: label-only identity, never promote statewide criteria to UHC.
 const avlayahId='uhc-oct-complete-a8d0977aeaff8cc1';
 const avlayah=groups.find(g=>g.records.some(r=>r.id===avlayahId));
 assert(avlayah,'Avlayah exact listing missing');
 const avlayahRow=avlayah.records.find(r=>r.id===avlayahId);
 assert.equal(avlayahRow.pa,'required');
 assert.equal(avlayahRow.preferred,'preferred');
 assert(!avlayahRow.uhcClinicalBindings.some(b=>b.role==='product'));
 const avlayahCard=a.medicationGroupCard(avlayah);
 for(const phrase of ['Avlayah (Tividenofusp alfa-eknm) IV Infusion','150 mg lyophilized','Boxed warning: anaphylaxis','Exact UHC initial/renewal criteria are unverified']) assert(avlayahCard.includes(phrase),'Avlayah missing '+phrase);
 assert(avlayahCard.includes('href="'+avlayahRow.reviewedPresentation.labelUrl+'"'),'Avlayah label citation missing from prescribing card');
 // Inbrija: retain both named stages and nonpreferred/quantity scopes, never an oral capsule.
 const inbrijaId='uhc-oct-complete-9979c6aa29c27e3e';
 const inbrija=groups.find(g=>g.records.some(r=>r.id===inbrijaId));assert(inbrija,inbrijaId);
 const inbrijaRow=inbrija.records.find(r=>r.id===inbrijaId);
 assert.equal(inbrijaRow.pa,'required');assert.equal(inbrijaRow.preferred,'non_preferred');
 const inbrijaBindings=inbrijaRow.uhcClinicalBindings.filter(b=>b.role==='product');
 assert.equal(inbrijaBindings.length,1);assert(inbrijaBindings[0].policyId.endsWith('gl-140661'));assert.deepEqual(inbrijaBindings[0].branchIndexes,[0,1]);
 assert(inbrijaRow.uhcClinicalBindings.some(b=>b.role==='nonpreferred'));
 assert(inbrijaRow.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 assert.equal(inbrijaRow.reviewedPresentation.dosageForm,'inhalation powder capsule');
 const inbrijaCard=a.medicationGroupCard(inbrija);
 for(const phrase of ['Inbrija (Levodopa) Inhalation Powder Capsules','42 mg levodopa','do not swallow','Inbrija inhaler','not as a substitute','numeric quantity limit remain unverified'])assert(inbrijaCard.includes(phrase),phrase);
 assert(inbrijaCard.includes('href="'+inbrijaRow.reviewedPresentation.labelUrl+'"'));
 const inbrijaDetail=await open(inbrija);
 for(const phrase of ['Initial Authorization','Reauthorization','6 month(s)','12 month(s)','Criteria source · PDF page 934<','Criteria source · PDF page 935<'])assert(inbrijaDetail.html.includes(phrase),phrase);
 assert(inbrijaDetail.ref.includes('page=934'));
 // Increlex is not GH. ISS is an explicit denial, not a positive approval stage.
 const increlexId='uhc-oct-complete-beefc17346ab027f';
 const increlex=groups.find(g=>g.records.some(r=>r.id===increlexId));assert(increlex,increlexId);
 const increlexRow=increlex.records.find(r=>r.id===increlexId);
 assert.equal(increlexRow.pa,'required');assert.equal(increlexRow.preferred,'preferred');
 const increlexBindings=increlexRow.uhcClinicalBindings.filter(b=>b.role==='product');
 assert.equal(increlexBindings.length,1);assert(increlexBindings[0].policyId.endsWith('gl-723191'));assert.deepEqual(increlexBindings[0].branchIndexes,[0,21,22]);
 assert.equal(increlexRow.reviewedPresentation.dosageForm,'subcutaneous injection');
 const increlexCard=a.medicationGroupCard(increlex);
 for(const phrase of ['Increlex (Mecasermin) Subcutaneous Injection','10 mg/mL','Not a substitute for growth hormone','Severe hypoglycemia','omit dose if food is omitted','explicitly excludes idiopathic short stature'])assert(increlexCard.includes(phrase),phrase);
 assert(increlexCard.includes('href="'+increlexRow.reviewedPresentation.labelUrl+'"'));
 const increlexDetail=await open(increlex);
 for(const phrase of ['Idiopathic Short Stature','Initial Authorization','Reauthorization','12 month(s)','Criteria source · PDF page 732<','Criteria source · PDF page 759<','Criteria source · PDF page 761<'])assert(increlexDetail.html.includes(phrase),phrase);
 // Ingrezza: all four exact stages, not a blanket Sprinkle coverage assertion.
 const ingrezzaId='uhc-oct-complete-33105a41b749978a';
 const ingrezza=groups.find(g=>g.records.some(r=>r.id===ingrezzaId));assert(ingrezza,ingrezzaId);
 const ingrezzaRow=ingrezza.records.find(r=>r.id===ingrezzaId);
 assert.equal(ingrezzaRow.pa,'required');assert.equal(ingrezzaRow.preferred,'preferred');
 const ingrezzaBindings=ingrezzaRow.uhcClinicalBindings.filter(b=>b.role==='product');
 assert.equal(ingrezzaBindings.length,1);assert(ingrezzaBindings[0].policyId.endsWith('gl-157491'));assert.deepEqual(ingrezzaBindings[0].branchIndexes,[0,1,2,3]);
 assert(ingrezzaRow.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 const ingrezzaCard=a.medicationGroupCard(ingrezza);
 for(const phrase of ['Ingrezza (Valbenazine) Oral Capsules','only Sprinkle may be opened','Exact payer eligibility for Sprinkle or kit is unverified','depression and suicidality','one active PA for one strength','numeric dispensing quantity limit remains unverified'])assert(ingrezzaCard.includes(phrase),phrase);
 assert(ingrezzaCard.includes('href="'+ingrezzaRow.reviewedPresentation.labelUrl+'"'));
 const ingrezzaDetail=await open(ingrezza);
 for(const phrase of ['Initial Authorization','Reauthorization','6 month(s)','12 month(s)','Criteria source · PDF page 941<','Criteria source · PDF page 942<','Criteria source · PDF page 943<','Criteria source · PDF page 944<'])assert(ingrezzaDetail.html.includes(phrase),phrase);
 // Gammagard plain brand must not inherit route- or formulation-specific criteria.
 const gammagardRows=[];
 for(const [suffix,sd] of [['c5af301ff34ca5f3',false],['c3048c00894b30ac',true]]){
  const id='uhc-oct-complete-'+suffix;
  const g=groups.find(g=>g.records.some(r=>r.id===id));
  assert(g,id+' listing missing');
  gammagardRows.push(g);
  const row=g.records.find(r=>r.id===id);
  assert.equal(row.pa,'required');assert.equal(row.preferred,'preferred');assert(!row.qlAmount&&!row.qlDays);
  const products=row.uhcClinicalBindings.filter(b=>b.role==='product');
  const card=a.medicationGroupCard(g);
  assert(card.includes('href="'+row.reviewedPresentation.labelUrl+'"'));
  if(sd){
   assert.equal(products.length,1);assert(products[0].policyId.endsWith('gl-552230'));
   assert.equal(products[0].branchIndexes.length,34);
   for(const phrase of ['Gammagard S/D Less IgA (Immune Globulin) Powder for IV Infusion','IV use only; not subcutaneous','does not eliminate anaphylaxis risk','payer acute ITP branch is not an FDA-labeled S/D indication','Asthma, BMT, CIDP, dermatomyositis/polymyositis, LEMS, Lennox-Gastaut syndrome, MMN, multiple myeloma infection prevention, relapsing MS, neuromyelitis optica, post B-cell targeted therapy, Rasmussen syndrome, stiff-person syndrome and specified secondary thrombocytopenia are off-label for S/D','Immune globulin is not a replacement for insulin','payer criteria are not FDA-approved indications or prescribing instructions','Autoimmune bullous disease criteria held','Kawasaki criteria held','Myasthenia gravis and posttransfusion purpura pathways held','all-other indications held for explicit diagnosis scope','Other indications and medical benefit applicability remain unverified'])assert(card.includes(phrase),phrase);
   const detail=await open(g);
   for(const phrase of ['Primary Immunodeficiency Syndromes','Prevention of infection in B-cell Chronic Lymphocytic Leukemia (CLL)','Immune thrombocytopenia','Asthma (severe, persistent, high-dose steroid-dependent)','Bone Marrow Transplant (BMT)','Chronic Inflammatory Demyelinating Polyneuropathy','Dermatomyositis or polymyositis','Lambert-Eaton Myasthenic Syndrome (LEMS)','Lennox Gastaut Syndrome','Multifocal Motor Neuropathy (MMN)','Prevention of infection in Multiple Myeloma','Relapsing Multiple Sclerosis','Neuromyelitis Optica','Post B-Cell Targeted Therapies','Rasmussen Syndrome','Stiff-Person Syndrome','Thrombocytopenia, secondary to Hepatitis C Virus (HCV)','Initial Authorization','Reauthorization'])assert(detail.html.includes(phrase),phrase);
   assert(!detail.html.includes('Posttransfusion Purpura'));assert(!detail.html.includes('All other indications'));assert(!detail.html.includes('Kawasaki Disease'));assert(!detail.html.includes('Autoimmune Bullous Disease'));assert(!detail.html.includes('Diagnosis Diabetes Mellitus'));assert(!detail.html.includes('Graves’ ophthalmopathy'));
   assert(detail.ref.includes('page=868')||detail.ref.includes('page=921')||detail.ref.includes('page=923'));
  }else{
   assert.equal(products.length,0);
   for(const phrase of ['Gammagard (Immune Globulin) Infusion (Formulation Unspecified)','does not identify Liquid, Liquid ERC or S/D','not a payer product match'])assert(card.includes(phrase),phrase);
  }
 }
 assert.notEqual(gammagardRows[0],gammagardRows[1],'ambiguous Gammagard merged with S/D');
 {
  const id='uhc-oct-complete-cb36a822ee8dc7d4';
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);
  assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
  const b=r.uhcClinicalBindings.find(b=>b.role==='product'&&b.policyId.endsWith('gl-141021'));assert(b);assert.deepEqual(b.branchIndexes,[0,1,2,3,4,5]);
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
  assert(!r.uhcClinicalBindings.some(b=>b.role==='nonpreferred'));
  const card=a.medicationGroupCard(g);assert(card.includes('Orencia (Abatacept) Subcutaneous Injection'));assert(card.includes('not the IV vial'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
  const out=await open(g);for(const phrase of ['Rheumatoid Arthritis','Polyarticular Juvenile Idiopathic Arthritis','Psoriatic Arthritis','Initial Authorization','Reauthorization'])assert(out.html.includes(phrase),phrase);
  assert(out.ref.includes('page=1289')||out.ref.includes('page=1290'));
 }
 const pertzyeGroups=['7f3a07339d47bc24','7fbd2d78a81af2c4'].map(s=>groups.find(x=>x.records.some(r=>r.id==='uhc-oct-complete-'+s)));
 assert(pertzyeGroups.every(Boolean));assert.notEqual(pertzyeGroups[0],pertzyeGroups[1],'Pertzye strength-specific QL must not merge');
 {
  const skyGroups=[];
  for(const [suffix,label,phrase,indexes] of [
   ['51060c1e6747eba6','Skyrizi (Risankizumab-rzaa) Subcutaneous Prefilled Pen','not this pen',[0,1,2,3]],
   ['9fdaab30a29cac66','Skyrizi (Risankizumab-rzaa) Subcutaneous Cartridge for On-Body Injector','prior IV induction',[4,5,6]],
   ['f6100e969a589a1d','Skyrizi (Risankizumab-rzaa) 150 mg/mL Subcutaneous Prefilled Syringe','not the same total dose',[0,1,2,3,4,5,6]]
  ]){
   const id='uhc-oct-complete-'+suffix;
   const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);skyGroups.push(g);
   const r=g.records.find(x=>x.id===id);
   assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
   const products=r.uhcClinicalBindings.filter(b=>b.role==='product');
   assert.equal(products.length,1);assert(products[0].policyId.endsWith('gl-684216'));assert.deepEqual(products[0].branchIndexes,indexes);
   for(const role of ['duplication','nonpreferred','global_quantity'])assert(r.uhcClinicalBindings.some(b=>b.role===role),id+' '+role);
   const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
   const out=await open(g);assert(out.html.includes('Initial Authorization'));assert(out.html.includes('Reauthorization'));
   if(indexes.includes(0)){assert(out.html.includes('Plaque Psoriasis'));assert(out.html.includes('Psoriatic Arthritis'));}
   else{assert(!out.html.includes('Plaque Psoriasis'));assert(!out.html.includes('Psoriatic Arthritis'));}
   if(indexes.includes(4)){assert(out.html.includes('Ulcerative Colitis'));assert(out.html.includes('intravenous induction'));}
   else{assert(!out.html.includes('Ulcerative Colitis'));}
   assert(out.ref.includes('page=1544')||out.ref.includes('page=1548'));
  }
  assert.equal(new Set(skyGroups).size,3);
 }
 {
  const id='uhc-oct-complete-21d7009b80e338fa';
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');
  assert.equal(b.length,1);assert(b[0].policyId.endsWith('gl-452192'));assert.deepEqual(b[0].branchIndexes,[0,1,2,3,4,5,6]);
  for(const role of ['duplication','nonpreferred','global_quantity'])assert(r.uhcClinicalBindings.some(b=>b.role===role),role);
  const card=a.medicationGroupCard(g);assert(card.includes('Simponi (Golimumab) Subcutaneous Injection'));assert(card.includes('distinct from intravenous Simponi Aria'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
  const out=await open(g);for(const phrase of ['Rheumatoid Arthritis','Ankylosing Spondylitis','Psoriatic Arthritis','Ulcerative Colitis','Initial Authorization','Reauthorization','15 kg'])assert(out.html.includes(phrase),phrase);
  assert(out.ref.includes('page=1529')||out.ref.includes('page=1530'));
 }
 {
  const id='uhc-oct-complete-31f36e8df6c98ba4';
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith('gl-618190'));assert.deepEqual(b[0].branchIndexes,[0,1]);
  for(const role of ['nonpreferred','global_quantity'])assert(r.uhcClinicalBindings.some(b=>b.role===role),role);
  const card=a.medicationGroupCard(g);assert(card.includes('Spinraza (Nusinersen) 12 mg/5 mL Intrathecal Solution'));assert(card.includes('high-dose presentation benefit'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
  const out=await open(g);for(const phrase of ['Initial Authorization','Reauthorization','3 month','12 month','SMN2','intrathecally'])assert(out.html.includes(phrase),phrase);
  assert(out.ref.includes('page=1583')||out.ref.includes('page=1586'));
 }
 {
  const id='uhc-oct-complete-be7159d568ed9f80';
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith('gl-713343'));assert.deepEqual(b[0].branchIndexes,[0,1,2,3]);
  for(const role of ['nonpreferred','global_quantity','duplication'])assert(r.uhcClinicalBindings.some(b=>b.role===role),role);
  const card=a.medicationGroupCard(g);assert(card.includes('Tezspire (Tezepelumab-ekko) Subcutaneous Prefilled Pen'));assert(card.includes('patient or caregiver administration'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
  const out=await open(g);for(const phrase of ['Asthma','CRSwNP','Initial Authorization','Reauthorization','6 month','12 month','Dupixent','Fasenra','Xolair'])assert(out.html.includes(phrase),phrase);
  assert(out.ref.includes('page=1696')||out.ref.includes('page=1699'));
  const syringe=groups.flatMap(x=>x.records).find(r=>r.id==='uhc-oct-complete-26eaf8d3998418d6');assert(syringe);assert(!syringe.uhcClinicalBindings.some(b=>b.policyId.endsWith('gl-713343')),'autoinjector PA leaked into syringe');
 }
 {const id='uhc-oct-complete-8ae98137dd88048f';
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith('gl-500226'));assert.deepEqual(b[0].branchIndexes,[0,1,2,3,4,5,6]);
  for(const role of ['nonpreferred','global_quantity','duplication'])assert(r.uhcClinicalBindings.some(b=>b.role===role),role);
  const card=a.medicationGroupCard(g);assert(card.includes('Tremfya (Guselkumab) Subcutaneous Injection (Device and Strength Unspecified)'));assert(card.includes('PsO/PsA payer branches apply to SC 100 mg only'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
  const out=await open(g);for(const phrase of ['Plaque Psoriasis','Psoriatic Arthritis','Ulcerative Colitis','Initial Authorization','Reauthorization','12 month','induction dosing','maintenance dose following the intravenous induction doses'])assert(out.html.includes(phrase),phrase);
  assert(out.ref.includes('page=1743')||out.ref.includes('page=1747'));
 }
 {const id='uhc-oct-complete-d37573826a734ebb';
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);const r=g.records.find(x=>x.id===id);
  assert.equal(r.pa,'conditional');assert.equal(r.preferred,'non_preferred');
  assert(!r.uhcClinicalBindings.some(b=>b.role==='product'),id+' wrong 50 mg or ER criteria');
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
  const card=a.medicationGroupCard(g);assert(card.includes('Topamax Sprinkle (Topiramate) Oral Sprinkle Capsule'));assert(card.includes('age 8 or older'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
  const out=await open(g);assert(out.ref.includes('page=702'));
 }
 // DEC-05/06/12/13/14/19/20: Tyvaso kit safety and preserved payer scopes.
 for(const [suffix,label,hasQL,product] of [["e6ced40cd1e57c05","Tyvaso DPI (Treprostinil) Inhalation Powder Maintenance Kit",true,false],["36bba0f4b45c9df3","Tyvaso DPI (Treprostinil) Inhalation Powder Titration Kit",true,true],["8dc08b2e585b8095","Tyvaso (Treprostinil) Inhalation Solution Refill Kit",false,false],["4df51b8e7e6b64bc","Tyvaso (Treprostinil) Inhalation Solution Starter Kit",false,false]]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL);
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,product?1:0);
  if(product){assert(b[0].policyId.endsWith('gl-715293'));assert.deepEqual(b[0].branchIndexes,[0,1]);}
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes('PH-ILD'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 for(const [suffix,indexes,phrase] of [['001e5ba120fa0c78',[0,1,2,3,4,5,6],'CD/UC age 2 and older'],['4bef2dde256711a9',[0,1,2,3],'CD/UC adults only']]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith('gl-745190'));assert.deepEqual(b[0].branchIndexes,indexes);
  for(const role of ['nonpreferred','global_quantity','duplication'])assert(r.uhcClinicalBindings.some(b=>b.role===role),role);
  const card=a.medicationGroupCard(g);assert(card.includes(phrase));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
  const out=await open(g);for(const x of ['Plaque Psoriasis','Psoriatic Arthritis','Initial Authorization','Reauthorization'])assert(out.html.includes(x),x);
 }
 // Exact Zolgensma weight-band kits; product-level policy, not Itvisma or numerical QL.
 const zolgensmaGroupIds=new Set();
 for(const [id,band,v55,v83] of [
  ['uhc-oct-complete-122631375b25a969','10.1-10.5',0,7],
  ['uhc-oct-complete-0213c9a06e7ceeeb','10.6-11.0',2,6],
  ['uhc-oct-complete-ff19f0cc1479f5d4','11.1-11.5',1,7],
  ['uhc-oct-complete-23163e3715d68ae7','11.6-12.0',0,8],
  ['uhc-oct-complete-6e07ada48071efc9','12.1-12.5',2,7],
  ['uhc-oct-complete-156d9eb0e3a4501e','12.6-13.0',1,8],
  ['uhc-oct-complete-bec695bbe3fb9d86','13.1-13.5',0,9],
  ['uhc-oct-complete-4042ef9a85590d2d','2.6-3.0',0,2],
  ['uhc-oct-complete-54785c1031f7131a','3.1-3.5',2,1],
  ['uhc-oct-complete-52292de6d5e4f7be','3.6-4.0',1,2],
  ['uhc-oct-complete-cf41b06d6fd22ae5','4.1-4.5',0,3],
  ['uhc-oct-complete-fd57381446d25d5c','4.6-5.0',2,2],
  ['uhc-oct-complete-195c447d02e43c25','5.1-5.5',1,3],
  ['uhc-oct-complete-295e76d74fbeb575','5.6-6.0',0,4],
  ['uhc-oct-complete-9a60913597362b45','6.1-6.5',2,3],
  ['uhc-oct-complete-4a226682a344144b','6.6-7.0',1,4],
  ['uhc-oct-complete-c94a751831dd15a2','7.1-7.5',0,5],
  ['uhc-oct-complete-5954d294b103e821','7.6-8.0',2,4],
  ['uhc-oct-complete-4396fa24871642c0','8.1-8.5',1,5],
  ['uhc-oct-complete-6fe8632c59acf63d','8.6-9.0',0,6],
  ['uhc-oct-complete-0b4dfcf8c2bf84a2','9.1-9.5',2,5],
  ['uhc-oct-complete-18cd666810c8003b','9.6-10.0',1,6],
 ]){
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  assert(!zolgensmaGroupIds.has(g),id+' weight-band kit collapsed');zolgensmaGroupIds.add(g);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));assert(r.uhcClinicalBindings.some(b=>b.role==='nonpreferred'));
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product'&&b.policyId.endsWith('gl-523191'));assert.equal(b.length,1);assert.deepEqual(b[0].branchIndexes,[0]);
  const card=a.medicationGroupCard(g);assert(card.includes('IV Infusion Kit '+band+' kg'));assert(card.includes(v55+' x 5.5 mL and '+v83+' x 8.3 mL'));assert(card.includes('not intrathecal Itvisma'));assert(card.includes('exact kit applicability and numeric QL remain unverified'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 assert.equal(zolgensmaGroupIds.size,22);
 // DEC-05/06/12/13/14/19/20: oncology identities retain the exact existing class/stage bindings.
 for(const [suffix,label,phrase,code,indexes] of [
  ['6fdc3ea2abaea52b','Zejula (Niraparib) Film-Coated Oral Tablet','100, 200 and 300 mg tablets','gl-741203',[1]],
  ['47dbf4be655ad1a4','Zykadia (Ceritinib) Oral Tablet or Capsule (Payer Form Unspecified)','current SPL product data lists tablets only','gl-741203',[1]],
  ['aa3337eda974b8e5','Yulithira (Everolimus; payer reference Torpenz) Oral Tablet','separate ANDAs','gl-657254',Array.from({length:15},(_,i)=>i)]
 ]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith(code));assert.deepEqual(b[0].branchIndexes,indexes);
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: preserve stage bindings and explicitly qualify option scope.
 for(const [suffix,label,phrase,code,indexes,pref,scope] of [
  ['50027926c12f2fc5','Isotretinoin Oral Capsule (payer reference Accutane)','not milligram-for-milligram substitutable with Absorica LD','gl-288262',[0,1,2,3],'preferred','verify formulation-specific applicability'],
  ['ebfa91d6e2f468c4','Cresemba (Isavuconazonium Sulfate) 186 mg Oral Capsule','this is not FDA capsule eligibility','gl-751212',[12,14],'non_preferred','186 mg capsule applicability unverified'],
  ['9cb53245e3257820','Droxidopa 100 mg Oral Capsule (payer reference Northera)','exact generic applicability','gl-140900',[0,1],'non_preferred','generic applicability unverified'],
  ['598734c054ff21fe','Eltrombopag Olamine Oral Tablet (payer reference Promacta)','not milligram-for-milligram substitutable','gl-546252',[0,1,2,3,4,5],'preferred','Generic eltrombopag tablets']
 ]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,pref);
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
  if(pref==='non_preferred')assert(r.uhcClinicalBindings.some(b=>b.role==='nonpreferred'));
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith(code));assert.deepEqual(b[0].branchIndexes,indexes);assert(b[0].productLabel.includes(scope));
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: exact stage/route/form and unchanged raw benefit scope.
 for(const [suffix,label,phrase,code,indexes,hasQL,scope] of [
  ['a27cea08627d0ce7','Epclusa (Sofosbuvir / Velpatasvir) Oral Pellets Packet','retreatment-oriented','gl-392223',[1],true,'packet applicability and initial stage unverified'],
  ['da63c83c6a7d29e4','Epclusa (Sofosbuvir / Velpatasvir) 200/50 mg Oral Tablet','distinct from oral pellets','gl-392223',[1],true,'200/50 mg applicability and initial stage unverified'],
  ['f7b511540f1cf564','Esperoct (Turoctocog Alfa Pegol) Powder for Intravenous Injection','frequency criteria are not a dispensing quantity limit','gl-716187',[14],false,'authorization stage unspecified'],
  ['32c32ab5f5ac35e6','Premarin (Conjugated Estrogens) Oral Tablet','do not treat this reference as confirmed oral criteria','gl-140685',[1],true,'oral route applicability unverified']
 ]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL);
  assert(r.uhcClinicalBindings.some(b=>b.role==='nonpreferred'));
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith(code));assert.deepEqual(b[0].branchIndexes,indexes);assert(b[0].productLabel.includes(scope));
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: generic everolimus formulations and conditional brand restriction.
 for(const [suffix,label,phrase] of [
  ['b16c95f918a6dc2d','Everolimus Oral Tablet (payer reference Torpenz)','not this tablet'],
  ['c97bdc185635bff6','Everolimus Tablet for Oral Suspension (payer reference Afinitor Disperz)','not formulation-specific FDA indications']
 ]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));assert(!r.uhcClinicalBindings.some(b=>b.role==='nonpreferred'));
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith('gl-657254'));assert.deepEqual(b[0].branchIndexes,Array.from({length:15},(_,i)=>i));assert(b[0].productLabel.includes('indication-specific applicability unverified'));
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('conditional on brand Afinitor/Disperz or Torpenz requests'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: Fasenra Pen vs syringe and named (not device-specific) policy.
 {
  const id='uhc-oct-complete-991b6422f8bc9a8f',g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));assert(r.uhcClinicalBindings.some(b=>b.role==='duplication'));
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith('gl-646191'));assert.deepEqual(b[0].branchIndexes,[0,1,2,3,4,5]);assert(b[0].productLabel.includes('pen-specific eligibility unverified'));
  const card=a.medicationGroupCard(g);assert(card.includes('Fasenra Pen (Benralizumab) Subcutaneous Autoinjector'));assert(card.includes('10 mg dose requires the syringe'));assert(card.includes('caregiver or healthcare provider'));assert(card.includes('not pen-specific eligibility'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
  const other=groups.flatMap(x=>x.records).find(x=>x.id==='uhc-oct-complete-42072ccb0efa2505');assert(other);assert(!other.reviewedPresentation?.label?.includes('Autoinjector'));assert(!other.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 }
 // DEC-05/06/12/13/14/19/20: named branches; do not infer label indication or payer form.
 for(const [suffix,label,phrase,code,indexes,scope,hasQL] of [
 ["ed2c1f1831632e6b","Fensolvi (Leuprolide Acetate) Six-Month Subcutaneous Extended-Release Suspension","this is not an approval stage","gl-752232",[0,1,5,6,7,8,9],"includes under-19 gender dysphoria exclusion",true],
 ["90f3ce4ee5762d4c","Fibryga (Fibrinogen Human) Intravenous Solution After Reconstitution","Acquired indication eligibility is not established","gl-716187",[22],"acquired indication unverified",false],
 ["16f1d6bb95149d00","Dificid (Fidaxomicin) Oral Tablet or Suspension (Payer Form Unverified)","conditional on generic tablets or brand suspension, not brand tablets","gl-390203",[0],"payer form unverified",true]
 ]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL);
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith(code));assert.deepEqual(b[0].branchIndexes,indexes);assert(b[0].productLabel.includes(scope));
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: retain distinct exact stage and formulation/quantity scopes.
 for(const [suffix,label,phrase,code,indexes,scope,preference,hasQL] of [["f00d8199bade0f54","Genotropin (Somatropin) Powder for Subcutaneous Injection","this is not an approval stage","gl-723191",[0,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20],"includes ISS exclusion; device eligibility unverified","preferred",false],["e48ac36405f1549a","Granisetron HCl Oral Tablet or Solution (Payer Form Unverified)","apply to Granisol only, not tablets","gl-632222",[0,1,2],"payer form unverified","preferred",true],["f23ca72ff27b5a94","Hemlibra (Emicizumab-kxwh) Subcutaneous Solution 105 mg/0.7 mL, 150 mg/mL, 30 mg/mL","do not combine different concentrations","gl-716187",[10],"routine prophylaxis; stage unspecified","non_preferred",false],["16792cef09a93d60","Hemlibra (Emicizumab-kxwh) Subcutaneous Solution 60 mg/0.4 mL","60 mg/0.4 mL single-dose vial is 150 mg/mL","gl-716187",[10],"routine prophylaxis; stage unspecified","non_preferred",true]]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,preference);
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL);
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith(code));assert.deepEqual(b[0].branchIndexes,indexes);assert(b[0].productLabel.includes(scope));
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: exact Humira packages and Hysingla stage/quantity scopes.
 for(const [suffix,label,phrase,code,indexes,scope,quantity] of [["44a3cc30cacb48e9","Humira (Adalimumab) Subcutaneous Autoinjector Kit — 2 Pens, 80 mg/0.8 mL","not a mixed-strength starter kit","gl-541212",[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14],"Humira named policy (kit eligibility unverified)",[]],["6f4d72453c49480d","Humira (Adalimumab) Subcutaneous Prefilled Syringe Kit — 2 Syringes, 10 mg/0.1 mL, 20 mg/0.2 mL, 40 mg/0.4 mL","not a mixed-strength kit or autoinjector","gl-541212",[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14],"Humira named policy (kit eligibility unverified)",[]],["50e68f49403e10e7","Hysingla ER (Hydrocodone Bitartrate) 24-Hour Extended-Release Oral Tablet","numeric dispensing QL unverified","gl-620192",[0,2,5,7,9,10,11],"Brand Hysingla ER named policy (conditional MME/DUR branches)",[8]]]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product'&&b.policyId.endsWith(code));assert.equal(b.length,1);assert.deepEqual(b[0].branchIndexes,indexes);assert.equal(b[0].productLabel,scope);
  const qb=r.uhcClinicalBindings.filter(b=>b.role==='quantity'&&b.policyId.endsWith(code));assert.deepEqual(qb.flatMap(b=>b.branchIndexes),quantity);
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/16/19/20: exact Neulasta manual PFS; named CSF policy and no inferred QL.
 {
  const id='uhc-oct-complete-279b6a3662f2dc13',g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  assert(!r.uhcClinicalBindings.some(b=>b.role==='global_quantity'||b.role==='quantity'));
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product'&&b.policyId.endsWith('gl-648215'));assert.equal(b.length,1);assert.deepEqual(b[0].branchIndexes,[0,1,2,3,4,5,6,7,8,9]);
  assert(b[0].productLabel.includes('device and indication eligibility unverified'));
  const card=a.medicationGroupCard(g);assert(card.includes('Neulasta (Pegfilgrastim) 6 mg/0.6 mL Subcutaneous Prefilled Syringe'));assert(card.includes('manual use overdoses'));assert(card.includes('stem cell mobilization'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/16/19/20: exact bare Noxafil listing; no formulation-specific benefit inference.
 {
  const id='uhc-oct-complete-db87969babd96230',g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product'&&b.policyId.endsWith('gl-751212'));assert.equal(b.length,1);assert.deepEqual(b[0].branchIndexes,[8,9,10,11,14]);assert(b[0].productLabel.includes('not IV criteria'));
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));assert(!r.policyQuantityLimit);
  const card=a.medicationGroupCard(g);for(const phrase of ['Noxafil (Posaconazole) — Dosage Form Unverified','40 mg/mL oral suspension','PowderMix 300 mg packet','300 mg/16.7 mL IV injection','greater than 40 kg','at least 40 kg','exactly 40 kg','hereditary fructose intolerance','does not identify which formulation is covered'])assert(card.includes(phrase),phrase);
  assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: oral Nuzyra, independent continuation paths and duration distinct from QL.
 {
  const id='uhc-oct-complete-a8a214653d1ccd59',g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product'&&b.policyId.endsWith('gl-140701'));assert.equal(b.length,1);assert.deepEqual(b[0].branchIndexes,[0,1,2]);assert(b[0].productLabel.includes('oral listing; stage unspecified'));
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));assert(!r.policyQuantityLimit);
  const card=a.medicationGroupCard(g);for(const phrase of ['Nuzyra (Omadacycline) 150 mg Oral Tablet','distinct from the 100 mg IV formulation','independent continuation alternatives','Authorization duration is not a numeric dispensing QL','no IV benefit inference'])assert(card.includes(phrase),phrase);
  assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: Olumiant strength scope and use-specific exclusion.
 for(const [suffix,strengths,indexes,hasQL,phrase] of [["593298d1e2b0b802","1 mg, 2 mg",[0,1,2,3],true,"renewal requires positive response"],["deb365a5276facd9","4 mg",[2,3],false,"do not assign those criteria to this 4 mg listing"]]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL);assert(!r.policyQuantityLimit);
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product'&&b.policyId.endsWith('gl-324206'));assert.equal(b.length,1);assert.deepEqual(b[0].branchIndexes,indexes);
  assert(r.uhcClinicalBindings.some(b=>b.role==='duplication'&&b.policyId.endsWith('gl-733328')));
  const card=a.medicationGroupCard(g);for(const s of ['Olumiant (Baricitinib) '+strengths+' Oral Tablet',phrase,'use-specific benefit exclusion','not a blanket exclusion','age 12 since September 2026','14-day authorization'])assert(card.includes(s),s);
  assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: exact generic versus brand prerequisites and form.
 for(const [suffix,label,phrase,code,index,scope,preference] of [["3db650dbb78aa872","Icatibant (Generic Firazyr) Subcutaneous Prefilled Syringe","not generic icatibant","gl-546227",1,"Generic icatibant acute HAE policy (stage unspecified)","preferred"],["62e4bb1c3d06bdc7","Gleevec (Imatinib Mesylate) 100 mg Oral Tablet","trial/failure of preferred generic imatinib","gl-741203",0,"Brand Gleevec cancer policy (stage unspecified)","non_preferred"],["8f9b8e5073a65ff3","Imatinib Mesylate (Generic Gleevec) Oral Tablets","does not apply to generic imatinib","gl-741203",0,"Generic imatinib cancer policy (stage unspecified)","preferred"]]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,preference);
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product'&&b.policyId.endsWith(code));assert.equal(b.length,1);assert.deepEqual(b[0].branchIndexes,[index]);assert.equal(b[0].productLabel,scope);
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('numeric dispensing QL unverified')||card.includes('Numeric dispensing QL unverified'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: Jivi frequency and lacosamide formulation/prerequisites.
 for(const [suffix,label,phrase,code,index,scope,preference,hasQL,nonsolid] of [["69ac4f11b2cd9e7e","Jivi (Damoctocog Alfa Pegol) Powder for Intravenous Injection — 500, 1000, 2000, 3000 IU","not included in this PDL row","gl-716187",8,"Jivi named hemophilia A policy (stage unspecified)","non_preferred",false,false],["e73b15b47b711f87","Vimpat (Lacosamide) Oral Tablet or Solution (Payer Form Unverified)","or continuation of prior seizure therapy","gl-572198",0,"Brand Vimpat oral policy (payer form unspecified)","non_preferred",true,false],["d8e1730a52588b48","Lacosamide (Generic Vimpat) Oral Solution 10 mg/mL","the same concentration","gl-572198",0,"Generic lacosamide oral solution policy (stage unspecified)","preferred",true,true],["699ad8210001a43d","Lacosamide (Generic Vimpat) Oral Tablet","not a tablet requirement","gl-572198",0,"Generic lacosamide oral tablet policy (stage unspecified)","preferred",true,false]]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,preference);
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL);
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='nonsolid'),nonsolid);
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product'&&b.policyId.endsWith(code));assert.equal(b.length,1);assert.deepEqual(b[0].branchIndexes,[index]);assert.equal(b[0].productLabel,scope);
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: Lupron scope, depot form, use-specific exclusion and flags.
 for(const [suffix,label,phrase,indexes,preference,hasQL] of [["9e43afbe428c7e21","Lupron Depot (Leuprolide) 1-Month IM Depot Suspension Kit","exact payer strength unverified",[2,3,4,5,6,7,8,9,10],"preferred",true],["574bd69073276e99","Lupron Depot (Leuprolide) 22.5 mg 3-Month IM Depot Suspension Kit","distinct from gynecologic 11.25 mg",[5,6,7,8,9,10],"non_preferred",true],["603070689561b9d7","Lupron Depot (Leuprolide) 30 mg 4-Month IM Depot Suspension Kit","not pediatric 30 mg 3-month kit",[5,6,7,8,9,10],"non_preferred",true],["f1461e4b8f46fcb2","Lupron Depot (Leuprolide) 45 mg 6-Month IM Depot Suspension Kit","not initial",[5,6,7,8,9,10],"non_preferred",true],["7d034ab551399d27","Lupron Depot-Ped (Leuprolide) 1-Month IM Depot Suspension Kit","CPP initial",[0,1,5,6,7,8,9],"preferred",true],["df7e2017cb699106","Lupron Depot-Ped (Leuprolide) 3-Month IM Depot Suspension Kit","not initial",[0,1,5,6,7,8,9],"non_preferred",false]]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,preference);
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL);
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product'&&b.policyId.endsWith('gl-752232'));assert.equal(b.length,1);assert.deepEqual(b[0].branchIndexes,indexes);
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('not a blanket exclusion'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: Lybalvi-specific safety and separate quantity branch.
 {
  const id='uhc-oct-complete-6a6a03b0a0dddc28',g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  const b=r.uhcClinicalBindings.filter(b=>b.policyId.endsWith('gl-722200'));
  assert.deepEqual(b.filter(x=>x.role==='product')[0].branchIndexes,[1,4]);
  assert.deepEqual(b.filter(x=>x.role==='quantity')[0].branchIndexes,[10]);
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));assert(r.uhcClinicalBindings.some(b=>b.role==='nonpreferred'));
  assert(r.policyQuantityLimit.text.includes('1 tablet/day'));
  const card=a.medicationGroupCard(g);assert(card.includes("Lybalvi (Olanzapine/Samidorphan) Oral Tablet"));assert(card.includes('acute opioid withdrawal'));assert(card.includes('1 tablet/day'));assert(card.includes('stage unspecified'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // DEC-05/06/12/13/14/19/20: labeled device distinctions without extending general policy scope.
 for(const [suffix,label,phrase,code,indexes,preference,hasQL] of [
  ["49d179ce14de8e08","Xolair (Omalizumab) Subcutaneous Autoinjector","device only for age 12 or older","gl-713364",[0,1,2,3,4,5,6,7],"preferred",true],
  ["2ba862a9dacbc59b","Xolair (Omalizumab) Subcutaneous Prefilled Syringe","administration is by caregiver","gl-713364",[0,1,2,3,4,5,6,7],"preferred",true],
  ["396902bfb6ebf8b7","Xolair (Omalizumab) Powder for Subcutaneous Injection","150 mg/1.2 mL after reconstitution","gl-713364",[0,1,2,3,4,5,6,7],"preferred",true],
  ["caf5904f63f299c4","Yorvipath (Palopegteriparatide) 294 mcg/0.98 mL Subcutaneous Pen","only 15, 18 or 21 mcg doses","gl-163670",[0,1],"non_preferred",false]
 ]){
  const id='uhc-oct-complete-'+suffix,g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);assert.equal(r.pa,'required');assert.equal(r.preferred,preference);
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL);
  const b=r.uhcClinicalBindings.filter(b=>b.role==='product');assert.equal(b.length,1);assert(b[0].policyId.endsWith(code));assert.deepEqual(b[0].branchIndexes,indexes);
  assert(r.uhcClinicalBindings.some(b=>b.role===(preference==='preferred'?'duplication':'nonpreferred')));
  const card=a.medicationGroupCard(g);assert(card.includes(label));assert(card.includes(phrase));assert(card.includes('exact device/package applicability is unverified'));assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'));
 }
 // These exact listings retain administrative review but no named product PA.
 for(const [suffix,label,phrase,hasQL] of [
  ["d6b49b27961f969c","Vascepa (Icosapent Ethyl) Oral Capsule","distinct from mixed EPA/DHA",true],
  ["9e388ff3dae2c7a5","Viokace (Pancrelipase) Oral Tablet","Do not substitute other pancreatic enzyme products",false],
  ["0c501f7a157fe744","Vyzulta (Latanoprostene Bunod) Ophthalmic Solution","distinct from latanoprost",true],
  ["7654658c09b78f85","Winlevi (Clascoterone) Topical Cream","not for oral, ophthalmic or vaginal use",true],
  ["275ef9d310381264","Winrevair (Sotatercept-csrk) 2 x 45 mg Subcutaneous Injection Kit","two 45 mg single-dose vials",true],
  ["e3adddae581cbcfd","Xaciato (Clindamycin) Vaginal Gel","Avoid polyurethane condoms",true],
  ["00da649844317125","Zeposia (Ozanimod) 7-Day Oral Capsule Titration Pack","Distinct from 28- and 37-day starter kits",true],
  ["d4c999ec3fe83160","Zioptan (Tafluprost) Preservative-Free Ophthalmic Solution","0.3 mL single-use containers",true],
  ["dc190cbfa1a36c65","Zonegran (Zonisamide) Oral Capsule","distinct from zonisamide oral suspension",true],
  ["4001483fb5296830","Zypitamag (Pitavastatin Magnesium) Oral Tablet","distinct from pitavastatin calcium",true],
  ["8e34212b5a29106f","Topamax (Topiramate) Oral Tablet","distinct from sprinkle capsules",true],
  ["0b3a19b761869f8f","Tiglutik (Riluzole) Oral Suspension","PEG-tube administration",true],
  ["3be2fce160eb4e1a","Betimol (Timolol Hemihydrate) Ophthalmic Solution","distinct from timolol maleate",true],
  ["ce85f87b9d08019d","Thiola (Tiopronin) Oral Tablet","not delayed-release",false],
  ["fe1aa6c1fd02f3ed","Thiola EC (Tiopronin) Delayed-Release Oral Tablet","Avoid alcohol two hours before",true],
  ["9d8ad92e4e67aa1f","Tazorac (Tazarotene) Topical Cream or Gel (Payer Form Unspecified)","cream and gel are distinct topical formulations",true],
  ["26eaf8d3998418d6","Tezspire (Tezepelumab-ekko) Subcutaneous Prefilled Syringe","for healthcare provider administration",false],
  ["e9644f76806d0c78","Sutab (Sodium Sulfate / Magnesium Sulfate / Potassium Chloride) Oral Tablet Kit","Distinct from Suprep oral solution",false],
  ["b452a2e1e260634a","Synarel (Nafarelin) Metered Nasal Spray","distinct from injectable GnRH agonists",false],
  ["ebc77e55ddd6f0c7","Striverdi Respimat (Olodaterol) Metered Inhalation Spray","not rescue treatment",true],
  ["22171578e784f52d","Solosec (Secnidazole) Oral Granules Packet","do not dissolve in liquid",true],
  ["097bbd79f985a20c","Siklos (Hydroxyurea) Scored Oral Tablet","distinct from hydroxyurea capsules",true],
  ["ecf070f7d966f3c0","Simbrinza (Brinzolamide / Brimonidine Tartrate) Ophthalmic Suspension","distinct from either single ingredient",true],
  ["45bccbf7d28f0d2d","Rasuvo (Methotrexate) Subcutaneous Autoinjector","Once weekly, never daily",true],
  ["787fc9bd1b5d7710","Rayaldee (Calcifediol) Extended-Release Oral Capsule","distinct from calcitriol and cholecalciferol",true],
  ["0d8138a620761a85","Rezvoglar KwikPen (Insulin Glargine-aglr) Subcutaneous Prefilled Pen","Do not withdraw insulin from the pen into a syringe",true],
  ["92305bb0ac20fce9","Edurant (Rilpivirine) Oral Tablet","not substitutable mg-for-mg",true],
  ["8bbcf6cc69fead95","Rocklatan (Netarsudil / Latanoprost) Ophthalmic Solution","distinct from either single ingredient",true],
  ["94c48abf89211479","Rhopressa (Netarsudil) Ophthalmic Solution","distinct from netarsudil/latanoprost combination",true],
  ["e09ab8c74dc567df","QNASL (Beclomethasone Dipropionate) Metered Nasal Aerosol (Strength Unspecified)","does not print a strength",true],
  ["34c3d53b54b42268","Children's QNASL (Beclomethasone Dipropionate) 40 mcg/Actuation Metered Nasal Aerosol","distinct from the 80 mcg/actuation presentation",true],
  ["9e19c60da2981b4c","Radicava ORS Starter Kit (Edaravone) Oral Suspension","distinct from the 10-day continuation kit",true],
  ["4763deab6556b498","MoviPrep (PEG 3350 / Electrolytes / Ascorbate) Powder for Oral Solution","not ready-to-drink solution",true],
  ["0d5d9de3ba6af1f0","Perforomist (Formoterol Fumarate) Nebulizer Solution","not rescue treatment or an asthma indication",true],
  ["7f3a07339d47bc24","Pertzye (Pancrelipase) 8,000 / 16,000 / 24,000 Lipase Unit Delayed-Release Capsules","Not the 4,000-unit capsule",false],
  ["7fbd2d78a81af2c4","Pertzye (Pancrelipase) 4,000 Lipase Unit Delayed-Release Capsule","Only the 4,000-unit capsule",true],
  ["34f80389bb5991b1","Omnaris (Ciclesonide) Metered Nasal Spray","distinct from orally inhaled ciclesonide",true],
  ["414fa24b98ae95bf","Ongentys (Opicapone) Oral Capsule","25 and 50 mg capsules",true],
  ["27dba7fd41442c41","Onpattro (Patisiran) Lipid Complex Intravenous Infusion","IV infusion only after dilution",false],
  ["91e168afff6eb5db","Nuvessa (Metronidazole) 1.3% Vaginal Gel","distinct from 0.75% multidose vaginal gel",true],
  ["f40ecc70e4799494","Neupro (Rotigotine) Extended-Release Transdermal Patch","Remove patch before MRI or cardioversion",true],
  ["8ea52132ca0e6e33","Nevanac (Nepafenac) Ophthalmic Suspension","Distinct from Ilevro 0.3% suspension",true],
  ["b3fc8d5441814c1f","Nextstellis (Drospirenone / Estetrol) Oral Tablet Pack","not drospirenone/ethinyl estradiol",true],
  ["e8f1bcbf0e4fa7a5","Vigamox (Moxifloxacin) Ophthalmic Solution","not for systemic use or intraocular injection",true],
  ["9d0f4cda9a3a81e0","Suprep Bowel Prep Kit (Sodium / Potassium / Magnesium Sulfates) Oral Solution Concentrate","does not distinguish the kits",true],
  ["140a0740fb8177a5","Natazia (Estradiol Valerate / Dienogest) Multiphasic Oral Tablet Pack","not a single fixed-dose combination tablet",true],
  ["20d43250059212cb","Plegridy Starter Pack (Peginterferon Beta-1a) Subcutaneous Prefilled Syringe Pack","distinct from the SC pen starter pack",true],
  ["73bdfcbd8ed83459","Pred Forte (Prednisolone Acetate) Ophthalmic Suspension","not a payer duration limit",true],
  ["5084711389d55a87","Mayzent Starter Pack (Siponimod) Oral Tablet Titration Pack","does not distinguish the two starter packs",true],
  ["7ae59a9be90894fb","Lialda (Mesalamine) Delayed-Release Oral Tablet","not a mesalamine capsule, enema or suppository",true],
  ["3e5ea0bc90a6979f","Lyumjev (Insulin Lispro-aabc) Injectable Solution (Device Unspecified)","does not identify a device or concentration",true],
  ["686742f153d68e01","Lyumjev KwikPen (Insulin Lispro-aabc) Prefilled Pen (Concentration Unspecified)","does not establish which concentration is covered",true],
  ["6520d7a7c776b0eb","Livalo (Pitavastatin Calcium) Oral Tablet","distinct from pitavastatin magnesium",true],
  ["b72a09032c056ced","Lotemax SM (Loteprednol Etabonate) Ophthalmic Gel","distinct from Lotemax 0.5% formulations",true],
  ["5f08db26327b4d8e","Lotemax (Loteprednol Etabonate) Ophthalmic Form Unspecified","does not specify the form",true],
  ["8b9d3977c36fecd2","Zylet (Loteprednol Etabonate / Tobramycin) Ophthalmic Suspension","not single-agent loteprednol",true],
  ["ddac5d138221ee70","Istalol (Timolol Maleate) Once-Daily Ophthalmic Solution","once daily in the morning",true],
  ["d63c3b1ab823b361","Lo Loestrin Fe (Norethindrone Acetate / Ethinyl Estradiol / Ferrous Fumarate) Oral Tablet Pack","not equivalent to Loestrin 24 Fe",true],
  ["76eeafb86c6f7dd9","Inveltys (Loteprednol Etabonate) Ophthalmic Suspension","inflammation and pain after ocular surgery",true],
  ["e9587576b936cf5e","Eysuvis (Loteprednol Etabonate) Ophthalmic Suspension","short-term dry eye treatment",true],
  ["1de36cc0a4b8fcd4","Fiasp (Insulin Aspart) Injectable Solution (Device Unspecified)","does not establish a particular device",true],
  ["100bab6065fcfca3","Fiasp FlexTouch (Insulin Aspart) Prefilled Pen","single-patient-use prefilled pen",true],
  ["47e7ac4802b75ef8","Fiasp PenFill (Insulin Aspart) Cartridge","distinct from 1.6 mL PumpCart",true],
  ["e6a8af6fb0e528d0","Finacea (Azelaic Acid) Topical Foam","distinct from gel",true],
  ["04c2175bcaa7ee29","Flarex (Fluorometholone Acetate) Ophthalmic Suspension","distinct from fluorometholone alcohol",true],
  ["44ba8a15828b42b8","Symfi (Efavirenz / Lamivudine / Tenofovir Disoproxil Fumarate) Oral Tablet","distinct from Symfi Lo 400/300/300 mg",true],
  ["e48614a8896d1c42","Elyxyb (Celecoxib) Oral Solution","acute migraine in adults, not prevention",true],
  ["3c48b4c2b5592695","Emend (Aprepitant) Oral Capsule / Powder for Oral Suspension (Form Unspecified)","The UHC listing does not identify the oral formulation",true],
  ["42d6b65788f7e18f","Truvada (Emtricitabine / Tenofovir Disoproxil Fumarate) Oral Tablet","distinct from tenofovir alafenamide combinations",true],
  ["91cfa1e69148c0ca","Emverm (Mebendazole) Chewable Tablet","Avoid concomitant metronidazole",true],
  ["93cb1d792516d6af","Enstilar (Calcipotriene / Betamethasone Dipropionate) Topical Foam","distinct from ointment or suspension",true],
  ["8f02f89ad4d636c6","Beyaz (Drospirenone / Ethinyl Estradiol / Levomefolate) Oral Tablet Pack","Distinct from Safyral 21/7 pack",true],
  ["f142ec3c46691c32","Safyral (Drospirenone / Ethinyl Estradiol / Levomefolate) Oral Tablet Pack","Distinct from Beyaz 24/4 pack",true],
  ["4174a6295393bf8f","Duaklir Pressair (Aclidinium / Formoterol) Dry Powder Inhaler","COPD maintenance, not rescue or asthma",true],
  ["36fd5377645d6fba","Edarbyclor (Azilsartan Medoxomil / Chlorthalidone) Oral Tablet","distinct from single-agent Edarbi",true],
  ["1d35bfcfe764c083","Cycloset (Bromocriptine) Oral Tablet","Distinct from other bromocriptine products",false],
  ["8eaaa9a428e51bfe","Diazepam 2.5 mg Rectal Gel","distinct from the 10 mg and 20 mg adjustable syringes",true],
  ["92cd6d282b2fdba2","Dipentum (Olsalazine Sodium) Oral Capsule","distinct from other aminosalicylates",true],
  ["d6a9c6a4da764191","Norpace (Disopyramide Phosphate) Immediate-Release Oral Capsule","distinct from 12-hour Norpace CR",true],
  ["f99f6e23bf651e34","Cosopt (Dorzolamide / Timolol) Ophthalmic Solution","preserved multidose ophthalmic solution",true],
  ["4ffe1eab1f90ef46","Cosopt PF (Dorzolamide / Timolol) Preservative-Free Ophthalmic Solution","preservative-free single-dose 0.2 mL",false],
  ["8b9ddaaef849c561","Crysvita (Burosumab-twza) 20 mg/mL Subcutaneous Solution","Medical-benefit policy applicability to this pharmacy listing is unverified",false],
  ["8ac95e39cc071af9","Cimduo (Lamivudine / Tenofovir Disoproxil Fumarate) Oral Tablet","not tenofovir alafenamide",true],
  ["3ce934e09340ac9a","Clenpiq (Sodium Picosulfate / Magnesium Oxide / Citric Acid) Oral Solution","not a powder for reconstitution",true],
  ["65b8740769a16e55","Climara Pro (Estradiol / Levonorgestrel) Weekly Transdermal Patch","weekly system, not estradiol-only Climara or twice-weekly CombiPatch",false],
  ["013b59b93699a5c4","Onexton (Clindamycin Phosphate / Benzoyl Peroxide) Topical Gel","not oral, ophthalmic or intravaginal",true],
  ["add6e7e9261e4c8f","Clindesse (Clindamycin Phosphate) Vaginal Cream","single 5 g prefilled vaginal applicator",true],
  ["8e1f189a8596a674","CombiPatch (Estradiol / Norethindrone Acetate) Twice-Weekly Transdermal Patch","twice-weekly system, not weekly Climara Pro",true],
  ["b9ec5dd97103ff2a","Nascobal (Cyanocobalamin) Nasal Spray","not oral or injectable cyanocobalamin",true],
  ["48aa5c3126dac1f1","Besivance (Besifloxacin) Ophthalmic Suspension","not for injection into the eye",true],
  ["ccb3e29f79cd93b8","Bijuva (Estradiol / Progesterone) 1 mg / 100 mg Oral Capsule","do not transfer its benefits to the 0.5 mg / 100 mg presentation",true],
  ["c24ea1cc8b559162","Lumigan (Bimatoprost) Ophthalmic Solution","Distinct from 0.03% formulations",true],
  ["a9f6c2797d55304f","Pylera (Bismuth Subcitrate Potassium / Metronidazole / Tetracycline HCl) Oral Capsule","omeprazole is administered separately and is not included",false],
  ["ea99523e63092e14","Sorilux (Calcipotriene) Topical Foam","Contraindicated in known hypercalcemia",true],
  ["2e1dfaa167d25964","Taclonex (Calcipotriene / Betamethasone Dipropionate) Topical Form Unspecified","ointment versus topical suspension",true],
  ["604fed6ff3bba12e","Dhivy (Carbidopa / Levodopa) Functionally Scored Oral Tablet","each quarter contains 6.25 mg/25 mg",true],
  ["3030be16c6c4522a","Alphagan P (Brimonidine Tartrate) Ophthalmic Solution","not Mirvaso topical gel",true],
  ["84a578e96b55a0cf","Mirvaso (Brimonidine) 0.33% Topical Gel","Not for ophthalmic, oral or intravaginal use",true],
  ["c5aa345f96aaec5c","Combigan (Brimonidine Tartrate / Timolol) Ophthalmic Solution","not single-agent brimonidine",true],
  ["bec7f75a1db17d2b","Prolensa (Bromfenac) Ophthalmic Solution","do not transfer dosing from other bromfenac concentrations",true],
  ['9248b8305ab77197','Reyataz (Atazanavir) Oral Capsule','do not open capsules',true],
  ['101e5350ddd51acd','AzaSITE (Azithromycin) Ophthalmic Solution','for ocular use only',true],
  ['826e676ded0d2967','Edarbi (Azilsartan Medoxomil) Oral Tablet','not the azilsartan/chlorthalidone combination',true],
  ['aa50f2e41f4faa14','Apidra SoloStar (Insulin Glulisine) Prefilled Pen','3 mL single-patient-use prefilled pen',true],
  ['ad3656a231a145e1','Apidra (Insulin Glulisine) Vial for Injection','10 mL multiple-dose vial',true],
  ['b194127f86ac4236','Accrufer (Ferric Maltol) Oral Capsule','30 mg iron as ferric maltol',true],
  ['d9b404be1858112f','Angeliq (Drospirenone / Estradiol) Oral Tablet','menopausal hormone therapy, not contraception',false],
  ['ae9928afe2cbe71e','Annovera (Segesterone Acetate / Ethinyl Estradiol) Vaginal System','21 days in, 7 days out, for 13 cycles',true]
 ]){
  const id='uhc-oct-complete-'+suffix;
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);
  assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  assert(!r.uhcClinicalBindings.some(b=>b.role==='product'),id+' fabricated product PA');
  assert(r.uhcClinicalBindings.some(b=>b.role==='nonpreferred'&&b.policyId.endsWith('gl-231255')),id+' nonpreferred review lost');
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL,id+' QL scope');
  const card=a.medicationGroupCard(g);assert(card.includes(label.replace(/\x27/g,"&#39;")),id+' form');assert(card.includes(phrase),id+' distinction');assert(card.includes('Exact UHC product-specific initial/renewal criteria'),id+' hold');assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'),id+' label link');
  const out=await open(g);assert(out.ref.includes('page=1202'),id+' administrative source');if(hasQL)assert(out.ref.includes('page=702'),id+' QL source');
 }
 for(const [suffix,label,phrase,pa] of [
  ["8ea2e18a291f48b7","Vancomycin Hydrochloride 25 mg/mL Powder for Oral Solution (Generic for Firvanq)","distinct from IV vancomycin","required"],
  ["45d4feeaedf3552e","Voriconazole Oral Tablet","distinct from IV and oral suspension","required"],
  ["90702ce4eec9617a","Topiramate 15 or 25 mg Oral Sprinkle Capsule","age 8 or older","conditional"],
  ["0f013ce4207021c3","Reyataz (Atazanavir) Oral Powder Packet","age 8 or older","conditional"],
  ["c52599e942ff4716","Lamotrigine Chewable / Dispersible Tablet for Oral Suspension","age 8 or older","conditional"],
  ["2350c3053e5d6856","Lidocaine 5% Topical Ointment","not a patch or injection","required"],
  ["877751e558a7560e","Lokelma (Sodium Zirconium Cyclosilicate) Powder for Oral Suspension","separate other oral medications by 2 hours","required"]
 ]) {
  const id='uhc-oct-complete-'+suffix;
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);
  assert.equal(r.pa,pa);assert.equal(r.preferred,'preferred');
  assert(!r.uhcClinicalBindings.some(b=>b.role==='product'||b.role==='nonpreferred'),id+' fabricated product or nonpreferred PA');
  if(suffix==='8ea2e18a291f48b7')assert(r.uhcClinicalBindings.some(b=>b.role==='nonsolid'&&b.policyId.endsWith('gl-545275')),id+' nonsolid policy lost');
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'&&b.policyId.endsWith('gl-140667')));
  const card=a.medicationGroupCard(g);assert(card.includes(label),id+' form');assert(card.includes(phrase),id+' distinction');assert(card.includes('Exact UHC product-specific initial/renewal criteria'),id+' hold');
  assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'),id+' label link');
  const out=await open(g);assert(out.ref.includes('page=702'),id+' quantity source');
 }
 {const id='uhc-oct-complete-0d8138a620761a85';const g=groups.find(x=>x.records.some(r=>r.id===id));const r=g.records.find(x=>x.id===id);assert(r.uhcClinicalBindings.some(b=>b.role==='duplication'&&b.policyId.endsWith('gl-735259')),id+' duplication reference retained');}
 {const id='uhc-oct-complete-21d7009b80e338fa';const g=groups.find(x=>x.records.some(r=>r.id===id));const r=g.records.find(x=>x.id===id);assert(r.uhcClinicalBindings.some(b=>b.role==='duplication'&&b.policyId.endsWith('gl-733328')),id+' duplication reference retained');}
 const octreotideGroups=[];
 for(const [suffix,label,phrase,hasQL,hasProduct] of [
  ['f02ebb3ed15163c2','Octreotide Acetate 1000 mcg/mL Non-Depot Injection Solution','1000 mcg/mL in a 5 mL multidose vial',true,false],
  ['2365e48035c832b5','Octreotide Acetate 200 mcg/mL Non-Depot Injection Solution','200 mcg/mL in a 5 mL multidose vial',false,false],
  ['f655e03418b3c0dd','Octreotide Acetate 500 mcg/mL Non-Depot Injection Solution','single-dose 1 mL vial',true,true],
  ['8b2ff71efd223fc7','Octreotide Acetate Depot Intramuscular Injectable Suspension','gluteal intramuscular administration',false,false],
  ['cd9f5afab9cb36c4','Octreotide Acetate 50 or 100 mcg/mL Subcutaneous Prefilled Syringe','separate 1 mL single-dose prefilled syringes',false,false],
  ['1e81e13b95303948','Octreotide Acetate 500 mcg/mL Subcutaneous Prefilled Syringe','500 mcg/mL in a 1 mL single-dose prefilled syringe',true,false]
 ]) {
  const id='uhc-oct-complete-'+suffix;
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);octreotideGroups.push(g);
  const r=g.records.find(x=>x.id===id);
  assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),hasQL,id+' QL scope');
  assert.equal(r.uhcClinicalBindings.some(b=>b.role==='product'&&b.policyId.endsWith('gl-140960')),hasProduct,id+' existing class binding scope');
  assert(!r.uhcClinicalBindings.some(b=>b.role==='nonpreferred'),id+' nonpreferred review inappropriate');
  const card=a.medicationGroupCard(g);assert(card.includes(label),id+' form');assert(card.includes(phrase),id+' route or package distinction');
  assert(card.includes('Exact prescribing-option criteria remain unverified'),id+' scope hold');
  assert(card.includes('href="'+r.reviewedPresentation.labelUrl+'"'),id+' label link');
 }
 assert.equal(new Set(octreotideGroups).size,6,'Octreotide concentrations, syringes and depot must not merge');
 const lyumjevGroups=['3e5ea0bc90a6979f','686742f153d68e01'].map(s=>groups.find(g=>g.records.some(r=>r.id==='uhc-oct-complete-'+s)));
 assert(lyumjevGroups.every(Boolean));assert.notEqual(lyumjevGroups[0],lyumjevGroups[1],'Device-specific and device-unspecified insulin must remain distinct');
 assert(a.medicationGroupCard(lyumjevGroups[1]).includes('Never withdraw U-200 from the pen into a syringe'),'U-200 safety warning');
 for(const suffix of ['1648922bcbfb41de','62acb905190fdbd1']){
  const id='uhc-oct-complete-'+suffix;
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);
  assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
  assert(!r.uhcClinicalBindings.some(b=>b.role==='product'&&b.policyId.endsWith('gl-720196')),id+' generic must not inherit brand criteria');
  const card=a.medicationGroupCard(g);assert(card.includes('PA sources conflict'),id+' conflicting PA must remain visible');
  assert(card.includes('duplicate rows disagree on step therapy'),id+' ST disagreement');
  assert(card.includes('October 18, 2026 policy says generic is preferred without PA'),id+' later policy');
  assert(card.includes('Current claim requirements are unverified'),id+' hold');
  const out=await open(g);assert(out.ref.includes('page=385'),id+' dated policy reference');
 }
 {
  const id='uhc-oct-complete-a75bf7c192276842';
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);
  assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
  assert(!r.uhcClinicalBindings.some(b=>b.role==='product'&&b.policyId.endsWith('gl-720196')),id+' generic must not inherit brand criteria');
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'),id+' quantity flag retained');
  const card=a.medicationGroupCard(g);
  assert(card.includes('PA sources conflict'));assert(card.includes('October 18, 2026 policy says generic is preferred without PA'));assert(card.includes('Current claim requirements are unverified'));
  assert(!card.includes('duplicate rows disagree on step therapy'),id+' no duplicate step conflict');
  const out=await open(g);assert(out.ref.includes('page=385'),id+' dated policy reference');
 }
 const qnaslGroups=['e09ab8c74dc567df','34c3d53b54b42268'].map(s=>groups.find(g=>g.records.some(r=>r.id==='uhc-oct-complete-'+s)));
 assert(qnaslGroups.every(Boolean));assert.notEqual(qnaslGroups[0],qnaslGroups[1],'QNASL and pediatric presentation must remain distinct');
 const eyeGroups=['b72a09032c056ced','5f08db26327b4d8e','8b9d3977c36fecd2'].map(s=>groups.find(g=>g.records.some(r=>r.id==='uhc-oct-complete-'+s)));
 assert(eyeGroups.every(Boolean));assert.equal(new Set(eyeGroups).size,3,'Distinct ophthalmic products must not merge');
 {
 const packetId='uhc-oct-complete-9fcb07846f5d9ec6';
 const packetGroup=groups.find(g=>g.records.some(r=>r.id===packetId));assert(packetGroup,packetId);
 const packet=packetGroup.records.find(r=>r.id===packetId);
 assert.equal(packet.pa,'conditional');assert.equal(packet.preferred,'preferred');
 assert(!packet.uhcClinicalBindings.some(b=>b.role==='product'));
 assert(packet.uhcClinicalBindings.some(b=>b.role==='global_quantity'&&b.policyId.endsWith('gl-140667')));
 const packetCard=a.medicationGroupCard(packetGroup);
 for(const phrase of ['Isentress (Raltegravir) Granules for Oral Suspension','100 mg single-use packet','not bioequivalent','aged 2 years or older','exact product-specific criteria and numeric quantity limit are unverified'])assert(packetCard.includes(phrase),phrase);
 assert(packetCard.includes('href="'+packet.reviewedPresentation.labelUrl+'"'));
 for(const suffix of ['e638ed46994f7179','ee3c4aa312ddb6a2']){
  const other=groups.find(g=>g.records.some(r=>r.id==='uhc-oct-complete-'+suffix));assert(other,suffix);assert.notEqual(other,packetGroup,'Packet must not merge with tablet');
  assert.equal(other.records.find(r=>r.id==='uhc-oct-complete-'+suffix).pa,'not_specified');
 }
 const packetDetail=await open(packetGroup);assert(packetDetail.ref.includes('page=702'));
 }
 const beyazGroup=groups.find(g=>g.records.some(r=>r.id==='uhc-oct-complete-8f02f89ad4d636c6'));
 const safyralGroup=groups.find(g=>g.records.some(r=>r.id==='uhc-oct-complete-f142ec3c46691c32'));
 assert.notEqual(beyazGroup,safyralGroup,'Different estrogen strength and pack schedule must remain separate');
 const duaklir=groups.flatMap(g=>g.records).find(r=>r.id==='uhc-oct-complete-4174a6295393bf8f');
 assert(duaklir.uhcClinicalBindings.some(b=>b.role==='duplication'&&b.policyId.endsWith('gl-735259')),'Administrative duplication policy lost');
 const clusterId='uhc-oct-complete-50113fd01abf63b3';
 const clusterGroup=groups.find(g=>g.records.some(r=>r.id===clusterId));assert(clusterGroup,clusterId);
 const cluster=clusterGroup.records.find(r=>r.id===clusterId);
 assert.equal(cluster.pa,'required');assert.equal(cluster.preferred,'non_preferred');
 const clusterBindings=cluster.uhcClinicalBindings.filter(b=>b.role==='product');
 assert.equal(clusterBindings.length,1);assert(clusterBindings[0].policyId.endsWith('gl-720193'));
 const clusterCard=a.medicationGroupCard(clusterGroup);
 assert(clusterCard.includes('100 mg/mL Subcutaneous Prefilled Syringe (300 mg Dose)'));
 assert(clusterCard.includes('three consecutive 100 mg subcutaneous injections'));
 assert(clusterCard.includes('href="'+cluster.reviewedPresentation.labelUrl+'"'));
 const clusterOut=await open(clusterGroup);
 assert(clusterOut.html.includes('Episodic Cluster Headaches'));
 assert(clusterOut.html.includes('Initial Authorization')&&clusterOut.html.includes('Reauthorization'));
 assert(!clusterOut.html.includes('Preventive Treatment of Migraine'));
 assert(cluster.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 const sprinkleId='uhc-oct-complete-f24f86de993ce49c';
 const sprinkleGroup=groups.find(x=>x.records.some(r=>r.id===sprinkleId));assert(sprinkleGroup,sprinkleId);
 const sprinkle=sprinkleGroup.records.find(r=>r.id===sprinkleId);
 assert.equal(sprinkle.pa,'conditional');assert.equal(sprinkle.preferred,'preferred');
 assert(sprinkle.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 assert(!sprinkle.uhcClinicalBindings.some(b=>['product','nonsolid','nonpreferred'].includes(b.role)));
 const sprinkleCard=a.medicationGroupCard(sprinkleGroup);
 assert(sprinkleCard.includes('Divalproex Sodium Delayed-Release Sprinkle Oral Capsule')&&sprinkleCard.includes('aged 8 years or older')&&sprinkleCard.includes('without chewing'));
 assert(sprinkleCard.includes('href="'+sprinkle.reviewedPresentation.labelUrl+'"'));
 const calcId='uhc-oct-complete-e29a433265e8ba09';
 const calcGroup=groups.find(x=>x.records.some(r=>r.id===calcId));assert(calcGroup,calcId);
 const calcRow=calcGroup.records.find(r=>r.id===calcId);
 assert.equal(calcRow.pa,'conditional');assert.equal(calcRow.preferred,'preferred');
 assert(calcRow.uhcClinicalBindings.some(b=>b.role==='nonsolid'&&b.policyId.endsWith('gl-545275')));
 assert(!calcRow.uhcClinicalBindings.some(b=>b.role==='product'||b.role==='global_quantity'));
 const calcCard=a.medicationGroupCard(calcGroup);
 assert(calcCard.includes('Calcitriol Oral Solution')&&calcCard.includes('1 mcg/mL oral solution')&&calcCard.includes('aged 8 years or older'));
 assert(calcCard.includes('href="'+calcRow.reviewedPresentation.labelUrl+'"'));
 const felId='uhc-oct-complete-25343462b850be92';
 const felGroup=groups.find(x=>x.records.some(r=>r.id===felId));assert(felGroup,felId);
 const felRow=felGroup.records.find(r=>r.id===felId);
 assert.equal(felRow.pa,'conditional');assert.equal(felRow.preferred,'preferred');
 assert(felRow.uhcClinicalBindings.some(b=>b.role==='nonsolid'&&b.policyId.endsWith('gl-545275')));
 assert(felRow.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 assert(!felRow.uhcClinicalBindings.some(b=>b.role==='product'||b.role==='nonpreferred'));
 const felCard=a.medicationGroupCard(felGroup);
 assert(felCard.includes('Felbamate Oral Suspension')&&felCard.includes('aplastic anemia and hepatic failure')&&felCard.includes('aged 8 years or older'));
 assert(felCard.includes('href="'+felRow.reviewedPresentation.labelUrl+'"'));
 // Exact nonpreferred UHC test strip class criteria; device references are not payer NDC evidence.
 for(const [suffix,label,phrase] of [
  ['0851f010ae01a71d','Blood Glucose Test Strips (Meter Model Unspecified by UHC)','do not assume interchangeability'],
  ['b500755c2b65a98f','GLUCOCARD Expression Blood Glucose Test Strips','do not substitute Shine strips'],
  ['58ab445334122bcf','GLUCOCARD Shine Blood Glucose Test Strips','distinct from Expression'],
  ['9f988a2e077865db','Precision Xtra Blood Glucose Test Strips','not ketone strips'],
  ['6176006028f31af2','ReliOn TRUE METRIX Blood Glucose Test Strips','Confirm the exact branded package']
 ]){
  const id='uhc-oct-complete-'+suffix;
  const g=groups.find(x=>x.records.some(r=>r.id===id));assert(g,id);
  const r=g.records.find(x=>x.id===id);
  assert.equal(r.pa,'required');assert.equal(r.preferred,'non_preferred');
  const pa=r.uhcClinicalBindings.filter(b=>b.role==='product');
  assert.equal(pa.length,1);assert(pa[0].policyId.endsWith('gl-369221'));assert.deepEqual(pa[0].branchIndexes,[0]);
  const ql=r.uhcClinicalBindings.find(b=>b.role==='quantity'&&b.policyId.endsWith('gl-369221'));assert(ql);assert.deepEqual(ql.branchIndexes,[1]);
  assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
  assert(!r.policyQuantityLimit,id+' fabricated numeric QL');
  const card=a.medicationGroupCard(g);
  for(const t of [label,phrase,'authorization stage is not specified','numeric quantity limit remain unverified','Device reference'])assert(card.includes(t),id+' '+t);
  assert(card.includes('href="'+r.reviewedPresentation.deviceSourceUrl.replaceAll('&','&amp;')+'"'),id+' HTML-escaped device source link');
  const out=await open(g);
  assert(out.html.includes('Criteria source · PDF page 1686<'),id+' PA source');
  assert(out.html.includes('Criteria source · PDF page 1687<'),id+' QL source');
  assert(out.ref.includes('page=1686'),id+' source link');
 }
 const meterId='uhc-oct-complete-1c1902ab9f482601';
 const meter=groups.find(g=>g.records.some(r=>r.id===meterId));assert(meter);
 const meterRow=meter.records.find(r=>r.id===meterId);
 assert.equal(meterRow.pa,'required');assert.equal(meterRow.preferred,'non_preferred');
 assert(!meterRow.uhcClinicalBindings.some(b=>b.role==='product'));
 const meterCard=a.medicationGroupCard(meter);
 for(const t of ['TRUE METRIX AIR Blood Glucose Meter Kit','TRUE METRIX self-monitoring test strips only','NDC-level approval','Device reference'])assert(meterCard.includes(t),t);
 assert(meterCard.includes('href="'+meterRow.reviewedPresentation.deviceSourceUrl+'"'));
 const meterOut=await open(meter);assert(meterOut.ref.includes('page=1202'));assert(!meterOut.ref.includes('page=245'));
 const basId='uhc-oct-complete-180f1c7535eea5b2';
 const bas=groups.find(g=>g.records.some(r=>r.id===basId));assert(bas);
 const basRow=bas.records.find(r=>r.id===basId);
 assert.equal(basRow.pa,'required');assert.equal(basRow.preferred,'non_preferred');
 assert(!basRow.uhcClinicalBindings.some(b=>b.role==='product'));
 const basDup=basRow.uhcClinicalBindings.find(b=>b.role==='duplication'&&b.policyId.endsWith('gl-735259'));
 assert(basDup);assert.deepEqual(Array.from(basDup.branchIndexes),[0]);
 assert(basRow.uhcClinicalBindings.some(b=>b.role==='nonpreferred'));
 assert(basRow.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 const basCard=a.medicationGroupCard(bas);
 for(const phrase of ['Basaglar KwikPen (Insulin Glargine) Prefilled Pen','3 mL single-patient-use pen','Distinct from Tempo Pen and U-300 glargine','Exact UHC product-specific initial/renewal criteria'])assert(basCard.includes(phrase),phrase);
 assert(basCard.includes('href="'+basRow.reviewedPresentation.labelUrl+'"'));
 const basOut=await open(bas);assert(basOut.ref.includes('page=1712'));assert(basOut.ref.includes('page=1202'));assert(basOut.ref.includes('page=702'));
 const barId='uhc-oct-complete-c80e5c34df4eadf5';
 const bar=groups.find(g=>g.records.some(r=>r.id===barId));assert(bar);
 const barRow=bar.records.find(r=>r.id===barId);
 assert.equal(barRow.pa,'required');assert.equal(barRow.preferred,'preferred');
 assert(!barRow.uhcClinicalBindings.some(b=>b.role==='product'||b.role==='nonpreferred'));
 assert(barRow.uhcClinicalBindings.some(b=>b.role==='nonsolid'&&b.policyId.endsWith('gl-545275')));
 assert(barRow.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 const barCard=a.medicationGroupCard(bar);
 for(const phrase of ['Baraclude (Entecavir) Oral Solution','0.05 mg/mL','Boxed warnings','Exact UHC product-specific initial/renewal criteria'])assert(barCard.includes(phrase),phrase);
 assert(barCard.includes('href="'+barRow.reviewedPresentation.labelUrl+'"'));
 const barOut=await open(bar);assert(barOut.ref.includes('page=1357'));assert(barOut.ref.includes('page=702'));
 const benlysta=groups.find(g=>g.records.some(r=>r.id==='uhc-oct-complete-36c4a27401324b71'));assert(benlysta);
 const benRow=benlysta.records.find(r=>r.id==='uhc-oct-complete-36c4a27401324b71');
 assert.equal(benRow.pa,'required');assert.equal(benRow.preferred,'non_preferred');
 const benBinding=benRow.uhcClinicalBindings.find(b=>b.role==='product'&&b.policyId.endsWith('gl-140941'));
 assert(benBinding);assert.deepEqual(Array.from(benBinding.branchIndexes),[0,1,2]);assert(benRow.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 const benCard=a.medicationGroupCard(benlysta);
 for(const phrase of ['Benlysta (Belimumab) Subcutaneous Autoinjector','200 mg/mL single-dose autoinjector','pediatric SC use is autoinjector-only','Exact payer numeric quantity limit is unverified'])assert(benCard.includes(phrase),phrase);
 assert(benCard.includes('href="'+benRow.reviewedPresentation.labelUrl+'"'));
 const benOut=await open(benlysta);
 for(const page of [226,227,228])assert(benOut.html.includes('Criteria source · PDF page '+page+'<'),'Benlysta page '+page);
 assert(benOut.ref.includes('page=226'));assert(benRow.uhcClinicalBindings.some(b=>b.role==='nonpreferred'&&b.policyId.endsWith('gl-231255')));assert(!benOut.ref.includes('page=1202'),'Named criteria should not stack administrative fallback');assert(benOut.ref.includes('page=702'));
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
 for(const term of ['aa50f2e41f4faa14','ad3656a231a145e1']){const g=groups.find(g=>g.records.some(r=>r.id==='uhc-oct-complete-'+term));assert(g,term);assert(!a.medicationGroupCard(g).includes('PA is printed in at least one source row.'),'Internal PA-column notice leaked');const out=await open(g);assert(out.html.includes('THREE')&&out.html.includes('pharmacy claims'),'Nonpreferred criteria missing');assert(out.html.includes('requested dosage cannot be achieved'),'QL exception criteria missing');assert(out.ref.includes('page=1202')&&out.ref.includes('page=702'),'Wrong UHC source');}
 const qvar=groups.find(g=>/qvar/i.test(g.label)&&a.clinicalGuidanceFor(g));if(qvar){const out=await open(qvar);assert(out.html.includes('Diagnosis of asthma'),'Existing non-PA clinical guide erased by quantity-policy loading');}
 const supplies=groups.filter(g=>g.records.some(r=>r.policyQuantityLimit?.sourcePolicyId?.endsWith('gl-512232')));assert(supplies.length>5);
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
 // Three newly verified SC records also carry GL-733328 duplication references.
 const subtypeBNamed = subtypeBRows.filter(r => r.uhcClinicalBindings.some(b => b.role === 'product'));
 // Orencia SC is one additional exact named policy; its duplication binding remains.
 assert(subtypeBNamed.some(r=>r.id==='uhc-oct-complete-cb36a822ee8dc7d4'));
 assert(subtypeBNamed.some(r=>r.id==='uhc-oct-complete-be7159d568ed9f80'));
 assert(subtypeBNamed.some(r=>r.id==='uhc-oct-complete-8ae98137dd88048f'));
 assert.equal(subtypeBNamed.length, 73);
 assert(subtypeBNamed.some(r=>r.id==='uhc-oct-complete-001e5ba120fa0c78'));
 assert(subtypeBNamed.some(r=>r.id==='uhc-oct-complete-4bef2dde256711a9'));
 assert.equal(subtypeBNamed.filter(r => !scIds.has(r.id)).length, 70);
 assert.equal(subtypeBNamed.filter(r => scIds.has(r.id)).length, 3);
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
 // RFA10092: exact October Roxybond; keep policy exception scopes separate.
 const roxyId='uhc-oct-complete-ccae7c796c8a0833';
 const roxy=groups.find(g=>g.records.some(r=>r.id===roxyId));assert(roxy,roxyId);
 const roxyRow=roxy.records.find(r=>r.id===roxyId);
 assert.equal(roxyRow.pa,'required');assert.equal(roxyRow.preferred,'non_preferred');
 assert.equal(roxyRow.reviewedPresentation.dosageForm,'immediate-release oral tablet');
 const roxyNamed=roxyRow.uhcClinicalBindings.filter(b=>b.policyId.endsWith('gl-711768'));
 assert.deepEqual(roxyNamed.map(b=>[b.role,...b.branchIndexes]),[['product',1,2],['quantity',3,4,5],['concurrent_opioid_dur',0],['mme_exception',6,7,8]]);
 assert(roxyRow.uhcClinicalBindings.some(b=>b.role==='nonpreferred'));
 assert(roxyRow.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
 const roxyCard=a.medicationGroupCard(roxy);
 for(const phrase of ['Immediate-Release Abuse-Deterrent Oral Tablet (5, 15, 30 mg)','abuse-deterrent does not mean abuse-proof','labeled 10 mg presentation is not listed','routine numeric tablet quantity limit remains unverified'])assert(roxyCard.includes(phrase),phrase);
 assert(roxyCard.includes(roxyRow.reviewedPresentation.labelUrl));
 const roxyOut=await open(roxy);
 for(const phrase of ['Concurrent opioid therapy (DUR)','Cumulative MME exceptions','Quantity-limit exceptions','Initial Authorization','Reauthorization','18 years of age and older','under 18 years of age'])assert(roxyOut.html.includes(phrase),phrase);
 for(const p of [1515,1516,1517,1518,1519,1520,1521,1523])assert(roxyOut.html.includes('Criteria source · PDF page '+p+'<'),roxyId+' source page '+p);
 assert(roxyOut.ref.includes('page=1515'));
 assert(!roxyOut.ref.includes('page=1202'),'Named criteria should not stack administrative fallback');
 const opioidCases = [
  ['1d645b57ce2be32c','pain','opioid-tolerant patients'],
  ['4949e672408e143c','oud_only','not analgesia'],
  ['554823c89afb7621','oud_only','not analgesia'],
  ['c892c74d9f3426a2','oud_only','not analgesia'],
  ['aa1a241874624dc7','unmatched','product-specific criteria are unverified'],
  ['a0d71228114f9c0a','pain','does not identify an exact package']
 ];
 for(const [suffix,scope,caution] of opioidCases){
   const id='uhc-oct-complete-'+suffix;
   const g=groups.find(g=>g.records.some(r=>r.id===id));assert(g,id);
   const r=g.records.find(r=>r.id===id);
   assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
   assert.equal(r.reviewedPresentation.opioidScope,scope);
   if(suffix==='c892c74d9f3426a2'){
     assert.equal(r.reviewedPresentation.dosageForm,'tablet for oral suspension');
     assert(a.medicationGroupCard(g).includes('40 mg Tablet for Oral Suspension'));
     assert(a.recordDetails(r).includes('864978'));
   }
   assert(a.medicationGroupCard(g).includes(caution),id+' visible caution');
   assert(a.recordDetails(r).includes(caution),id+' source caution');
   assert(a.recordDetails(r).includes(r.reviewedPresentation.labelUrl),id+' label citation');
   const bindings=a.uhcGroupBindings(g),out=await open(g);
   if(scope==='pain'){
     assert(bindings.some(b=>b.role==='concurrent_opioid_dur'&&b.branchIndexes.join(',')==='0'));
     assert(bindings.some(b=>b.role==='mme_exception'&&b.branchIndexes.join(',')==='9,10,11'));
     assert(bindings.some(b=>b.role==='product'&&b.branchIndexes.join(',')==='1,4,7'));
     assert(out.html.includes('Concurrent opioid therapy (DUR)'));
     assert(out.html.includes('Cumulative MME exceptions'));
     assert(out.html.includes('Quantity-limit exceptions'));
     for(const p of [1063,1067,1073])assert(out.html.includes('Criteria source · PDF page '+p+'<'),id+' source page '+p);
   }else{
     assert(!bindings.some(b=>b.policyId.endsWith('gl-620192')&&b.role==='product'),id+' unsafe pain branch');
     assert(!out.html.includes('Criteria source · PDF page 1067<'));
     assert(out.html.includes('Approval criteria have not yet been verified'));
     if(scope==='oud_only')assert(out.ref.includes('Related UHC pain guideline'),id+' related source inaccessible');
   }
 }
 console.log('PASS: Six exact UHC opioid rows preserve benefits, label caveats, and scoped PA/DUR/MME/QL references.');
 
 {
   const id='uhc-oct-complete-9db621ca8a237769';
   const g=groups.find(g=>g.records.some(r=>r.id===id));assert(g,id);
   const r=g.records.find(r=>r.id===id);
   assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
   assert.equal(r.reviewedPresentation.dosageForm,'extended-release oral tablet');
   const b=r.uhcClinicalBindings.filter(b=>b.policyId.endsWith('gl-620192'));
   assert.deepEqual(b.map(b=>[b.role,...b.branchIndexes]),[['product',1,4,7],['quantity',8],['concurrent_opioid_dur',0],['mme_exception',9,10,11]]);
   assert(r.uhcClinicalBindings.some(b=>b.role==='global_quantity'));
   const card=a.medicationGroupCard(g),out=await open(g);
   for(const phrase of ['Morphine Sulfate Extended-Release Oral Tablet','established opioid tolerance','numeric dispensing QL unverified'])assert(card.includes(phrase),phrase);
   for(const phrase of ['Concurrent opioid therapy (DUR)','Cumulative MME exceptions','Quantity-limit exceptions','Initial Authorization','Reauthorization'])assert(out.html.includes(phrase),phrase);
   for(const page of [1063,1067,1073])assert(out.html.includes('Criteria source · PDF page '+page+'<'),id+' source page '+page);
   for(const page of [1064,1069])assert(!out.html.includes('Criteria source · PDF page '+page+'<'),id+' wrong brand/capsule branch '+page);
 }

 {
   const id='uhc-oct-complete-bfb63d261b16bc39';
   const g=groups.find(g=>g.records.some(r=>r.id===id));
   assert(g,id);
   const r=g.records.find(r=>r.id===id);
   assert.equal(r.pa,'required');assert.equal(r.preferred,'preferred');
   const card=a.medicationGroupCard(g),bindings=a.uhcGroupBindings(g),out=await open(g);
   assert(card.includes('Mifepristone 300 mg Oral Tablet'));
   assert(card.includes('Pregnancy contraindicated'));
   assert(bindings.some(b=>b.policyId.endsWith('gl-140849')&&b.role==='korlym_reference'));
   assert(!bindings.some(b=>b.policyId.endsWith('gl-434343')||(b.policyId.endsWith('gl-140849')&&b.role==='product')));
   assert(!out.html.includes('Criteria source · PDF page 224<'));
   assert(!out.html.includes('Criteria source · PDF page 1015<'));
   assert(out.html.includes('Approval criteria have not yet been verified'));
   assert(out.ref.includes('Korlym brand policy reference'));
   assert(data.policies.some(p=>p.policyCode==='GL-434343'),'Mifeprex source retained');
 }
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
    assert(r.reviewedPresentation.policyUnverified===true,id+' unresolved branch applicability');
    assert(!a.medicationGroupCard(g).includes('data-card-clinical'),id+' unsafe automatic criteria');
    assert(a.recordDetails(r).includes('Read full source text'),id+' related source inaccessible');
 }
 const infliximab=bannerGroups.find(g=>g.records.some(r=>r.id==='banner-full-719caae0c9978dca'));
 assert(infliximab);
 const infliximabRow=infliximab.records.find(r=>r.id==='banner-full-719caae0c9978dca');
 assert.equal(infliximabRow.pa,'required');assert.equal(infliximabRow.preferred,'preferred');
 assert.equal(infliximabRow.reviewedPresentation.policyUnverified,false,'Reviewed Janssen branch must be available');
 assert.equal(infliximabRow.reviewedBannerBranches.policyId,'banner-policy-12-945');
 assert.equal(infliximabRow.reviewedBannerBranches.indicationPages.length,14);
 assert(a.medicationGroupCard(infliximab).includes('data-card-clinical'));
 assert(a.medicationGroupCard(infliximab).includes('57894016001'));
 assert.match(a.medicationGroupCard(infliximab),/not (?:a )?separately licensed biosimilar/i);
 console.log('PASS: Eight exact Banner IG/infliximab options retain flags and route/product caveats.');
 const leqvio=bannerGroups.find(g=>g.records.some(r=>r.id==='banner-oct2026-j1306'));
 assert(leqvio,'Leqvio J1306 row missing');
 const leqvioRow=leqvio.records.find(r=>r.id==='banner-oct2026-j1306');
 assert.equal(leqvioRow.name,'Injection, inclisiran, 1 mg');
 assert.equal(leqvioRow.pa,'required');
 assert.equal(leqvioRow.preferred,'not_specified');
 assert.equal(leqvioRow.coverage,'not_specified');
 assert.equal(leqvioRow.sourcePage,4);
 assert(leqvioRow.reviewedPresentation.policyUnverified);
 assert(a.medicationGroupCard(leqvio).includes('284 mg/1.5 mL subcutaneous prefilled syringe'));
 assert(a.recordDetails(leqvioRow).includes('1 mg is a billing unit'));
 assert(a.recordDetails(leqvioRow).includes('Exact medical-benefit initial and renewal criteria'));
 console.log('PASS: Leqvio clinical syringe is distinguished from J1306 billing unit, with original PA and uncertainty preserved.');

 console.log('PASS: '+n+' restricted UHC cards load clinical content and source references; Apidra nonpreferred + QL; preferred/nonpreferred syringe branches; plan isolation');
})().catch(e=>{console.error(e);process.exitCode=1});
