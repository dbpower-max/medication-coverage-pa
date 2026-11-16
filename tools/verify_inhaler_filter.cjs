const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const load=p=>{const b=fs.readFileSync(p);return JSON.parse(b[0]===31?zlib.gunzipSync(b):b)};
const data=load('_site/data.json.gz');
for(const f of Object.values(data.planDataFiles||{}))data.medications.push(...load('_site/'+f.split('?')[0].replace(/^\.\//,'')));
delete data.planDataFiles;
const ctx={Intl,console,document:{querySelectorAll:()=>[]}};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('_site/app.js','utf8').replace("document.addEventListener('DOMContentLoaded', init);",'globalThis.api={state,el,isInhaler,matchesCategory,categoryOptions,subcategoryOptions,render};'),ctx);
const a=ctx.api;a.state.data=data;
for(const id of ['criteriaSearch','criteriaCount','criteriaResults','criteriaLibrary','planStatus','planEvidence','evidenceList','loadingState','resultCount','effectiveDate','emptyState','resultGrid','showMore'])a.el[id]={value:'',innerHTML:'',textContent:'',hidden:false};
for(const plan of data.plans){
 a.state.planId=plan.id;a.state.category='Inhalers';a.state.term='';
 assert(a.categoryOptions().includes('Inhalers'));
 const groups=a.render();assert(groups.length>15,'Missing inhaler groups: '+plan.id);
 assert(groups.every(g=>g.records.some(a.isInhaler)),'Non-inhaler card: '+plan.id);
 for(const brand of ['Qvar','Spiriva','Advair']) assert(groups.some(g=>new RegExp(brand,'i').test(g.label)),brand+' absent: '+plan.id);
 assert(!groups.some(g=>/nebuliz|syrup|nasal|spacer/i.test(g.label)),'Wrong formulation included');
 const all=groups.map(g=>g.label).join('\n');console.log(plan.id+': '+groups.length+' inhaler cards');
 a.state.term='albuterol';assert(a.render().length>0,'Generic search broken');
 a.state.term='Qvar';assert(a.render().length>0,'Brand search broken');
 a.state.term='';a.state.subcategory=a.subcategoryOptions()[0];assert(a.render().length>0,'Subcategory broken');a.state.subcategory='';
 a.state.category='Respiratory / Allergy';assert(a.render().length>groups.length,'Broad category replaced');
}
for(const name of ['albuterol Inhalation Solution','ALBUTEROL SULFATE NEBULIZED','budesonide nebulization suspension','albuterol Oral Syrup','fluticasone Nasal Spray','inhaler spacer'])assert(!a.isInhaler({name,recordType:'formulary'}),name+' misclassified');
assert(!a.isInhaler({name:'Qvar inhaler',recordType:'policy_index'}),'Internal source classified as medication');
assert(a.isInhaler({name:'Insulin inhalable powder',recordType:'formulary',category:'Diabetes'}),'Inhaled insulin excluded');
assert(fs.readFileSync('_site/index.html','utf8').includes('data-category="Inhalers"'));
console.log('PASS: inhaler-only category/quick filter, 3 plans, brand/generic searches, subcategories; nebulizers/oral/nasal/accessories excluded; existing categories retained');
