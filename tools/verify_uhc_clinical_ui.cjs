const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const load=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=load('_site/data.json.gz');for(const f of Object.values(data.planDataFiles||{}))data.medications.push(...load('_site/'+f.split('?')[0].replace(/^\.\//,'')));delete data.planDataFiles;
const ctx={Intl,console,document:{addEventListener:()=>{}},fetch:async url=>({ok:true,json:async()=>load('_site/'+url.split('?')[0].replace(/^\.\//,'')),text:async()=>fs.readFileSync('_site/'+url.split('?')[0].replace(/^\.\//,''),'utf8')})};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('_site/app.js','utf8').replace("document.addEventListener('DOMContentLoaded', init);",'globalThis.api={state,planMedicationGroups,medicationGroupCard,populateCardClinical,uhcGroupBindings};'),ctx);
const a=ctx.api;a.state.data=data;a.state.planId='uhc-community-az';
async function open(g){const content={innerHTML:'',isConnected:true},ref={innerHTML:''};a.medicationGroupCard(g);const d={open:true,dataset:{cardClinical:g.key||g.label},querySelector:s=>s==='.card-pa-references'?ref:content};await a.populateCardClinical(d);assert.equal(d.dataset.loaded,'true',g.label+' did not load');return {html:content.innerHTML,ref:ref.innerHTML};}
(async()=>{
 const groups=a.planMedicationGroups().filter(g=>g.records.some(r=>r.planId==='uhc-community-az'&&!r.isStatewideReference&&(['required','conditional'].includes(r.pa)||r.qlAmount||r.qlDays)));
 const mounjaro=a.planMedicationGroups().find(g=>/mounjaro/i.test(g.label));assert(a.medicationGroupCard(mounjaro).includes('uhc-az-clinical-pharmacy-2026-11-01.pdf'),'Initial UHC reference incorrectly points to statewide criteria');
 let n=0;
 for(const g of groups){const out=await open(g);assert(out.html.trim(),g.label+' empty');assert(out.ref.includes('href='),g.label+' no policy/formulary reference');assert(!out.html.includes('Formatted criteria for this medication are not available'),'Empty template remains');n++;}
 for(const term of ['Apidra SoloStar','Apidra Vial']){const g=groups.find(g=>g.label.toLowerCase()===term.toLowerCase());assert(g,term);assert(!a.medicationGroupCard(g).includes('PA is printed in at least one source row.'),'Internal PA-column notice leaked');const out=await open(g);assert(out.html.includes('THREE')&&out.html.includes('pharmacy claims'),'Nonpreferred criteria missing');assert(out.html.includes('requested dosage cannot be achieved'),'QL exception criteria missing');assert(out.ref.includes('page=1202')&&out.ref.includes('page=702'),'Wrong UHC source');}
 const supplies=groups.filter(g=>g.records.some(r=>r.policyQuantityLimit));assert(supplies.length>5);
 for(const g of supplies){const out=await open(g);assert(out.html.includes('more frequent delivery of insulin'));const card=a.medicationGroupCard(g);assert(card.includes('6 pen needles per day and 6 syringes per day.'));if(g.records.every(r=>r.preferred==='preferred'))assert(!out.html.includes('unable to use a preferred'),'Preferred product got nonpreferred PA');}
 a.state.planId='banner-ufc';assert.equal(a.uhcGroupBindings(groups[0]).length,0,'UHC policy leaked across plans');
 console.log('PASS: '+n+' restricted UHC cards load clinical content and source references; Apidra nonpreferred + QL; preferred/nonpreferred syringe branches; plan isolation');
})().catch(e=>{console.error(e);process.exitCode=1});
