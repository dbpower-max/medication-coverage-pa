const fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('dist/app.js','utf8');
const functions = source.slice(source.indexOf('  function readableMedicationName('), source.indexOf('  function categoryOptions('));
const context = {normalize:s=>String(s).toLowerCase().trim(),state:{planId:'test',data:{medications:[]}}};
vm.createContext(context);vm.runInContext(functions,context);
function groups(rows) {context.rows=rows.map((r,i)=>({id:String(i),planId:'test',...r})); return vm.runInContext('medicationGroups(rows)',context);}
const pair=groups([{name:'drug tablet (generic for BRAND)'},{name:'BRAND (brand for drug tablet)',pa:'required'}]);
if(pair.length!==1||pair[0].records.length!==2||pair[0].records[1].pa!=='required')throw Error('Explicit brand/generic pair lost');
if(groups([{name:'drug tablet',brand:'BRAND'},{name:'DRUG TABLET',brand:'Brand'}]).length!==1)throw Error('Duplicate identity');
if(groups([{name:'drug oral tablet'},{name:'drug subcutaneous solution'},{name:'drug oral tablet ER'},{name:'drug oral tablet 5 mg'},{name:'drug oral tablet 10 mg'}]).length!==5)throw Error('Variants incorrectly merged');
if(groups([{name:'drug',planId:'A'},{name:'drug',planId:'B'}]).length!==2)throw Error('Plans merged');
if(groups([{name:'drug tablet',brand:'REFERENCE BRAND'}])[0].records.length!==1)throw Error('Invented generic product');
const combined=groups([{name:'drug tablet (generic for BRAND)'},{name:'drug tablet',brand:'BRAND',pa:'required'}]);
if(combined.length!==1||combined[0].records.length!==2||combined[0].records[1].pa!=='required')throw Error('Exact generic identity did not combine records without losing PA');
if(groups([{name:'MOUNJARO',brand:'MOUNJARO'}])[0].label!=='Mounjaro')throw Error('Duplicate brand name shown');
if(groups([{name:'ATORVASTATIN CALCIUM TABLETS',brand:'LIPITOR'}])[0].label!=='Atorvastatin Calcium Tablets (Lipitor)')throw Error('Unreadable generic/brand label');
if(groups([{name:'drug tablet 5MG',brand:'BRAND'}])[0].label!=='drug tablet 5 mg (Brand)')throw Error('Strength or unit displayed incorrectly');
if(!groups([{name:'drug tablet',searchAliases:['ALIAS BRAND']}])[0].search.includes('ALIAS BRAND'))throw Error('Search aliases lost');

if(groups([{name:'INSULIN NPH SUSPENSION',brand:'HUMULIN N KWIKPEN'}])[0].label!=='Insulin NPH Suspension (Humulin N KwikPen)')throw Error('NPH or device capitalization lost');
if(groups([{name:'GLP-1 RECEPTOR AGONIST'}])[0].label!=='GLP-1 Receptor Agonist')throw Error('GLP acronym lost');
if(groups([{name:'INSULIN GLARGINE 100U/ML',brand:'LANTUS SOLOSTAR'}])[0].label!=='Insulin Glargine 100U/mL (Lantus SoloStar)')throw Error('Strength unit or SoloStar capitalization lost');
// Exact repeated brands must appear once in medication search suggestions.
const labeled=groups([{name:'chlorhexidine gluconate 1.2 mg/mL Mouthwash [Periogard]',brand:'Periogard'}]);
if(labeled[0].label!=='chlorhexidine gluconate 1.2 mg/mL Mouthwash (Periogard)')throw Error('Periogard duplicated in bracket and parenthesis');
const armour=groups([{name:'thyroid (USP) 120 mg Oral Tablet [Armour Thyroid]',brand:'Armour Thyroid'}]);
if(armour[0].label!=='thyroid (USP) 120 mg Oral Tablet (Armour Thyroid)')throw Error('Armour Thyroid duplicated or USP capitalization lost');
if(groups([{name:'drug tablet 5 mg (Brand)',brand:'Brand'}])[0].label!=='drug tablet 5 mg (Brand)')throw Error('Repeated parenthesized brand');
if(groups([{name:'drug tablet 5 mg [Brand] (Brand)',brand:'Brand'}])[0].label!=='drug tablet 5 mg (Brand)')throw Error('Multiple nested duplicate brands');
if(groups([{name:'drug tablet [OTC]',brand:'Brand'}])[0].label!=='drug tablet [OTC] (Brand)')throw Error('Meaningful unrelated bracket was deleted');
if(groups([{name:'drug tablet [Other Brand]',brand:'Brand'}])[0].label!=='drug tablet [Other Brand] (Brand)')throw Error('Distinct brand was incorrectly suppressed');
if(groups([{name:'doxylamine succinate 25 mg Oral Tablet [Wal-Som (doxylamine)]',brand:'Wal-Som (doxylamine)'}])[0].label!=='doxylamine succinate 25 mg Oral Tablet (Wal-Som (doxylamine))')throw Error('Nested brand alias duplicated');
if(groups([{name:'{28 (ivacaftor 150 mg / tezacaftor 100 mg Oral Tablet) / 28 (ivacaftor 150 mg Oral Tablet) } Pack [Symdeko (100 mg / 150 mg; 150 mg)]',brand:'Symdeko (100 mg / 150 mg; 150 mg)'}])[0].label!=='{28 (ivacaftor 150 mg / tezacaftor 100 mg Oral Tablet) / 28 (ivacaftor 150 mg Oral Tablet) } Pack (Symdeko (100 mg / 150 mg; 150 mg))')throw Error('Combination pack brand duplicated');


// Audit actual deployed provider-scope records after the site build.
const zlib = require('zlib');
function jsonAsset(path) {
  const bytes=fs.readFileSync(path);
  return JSON.parse((bytes[0]===31 && bytes[1]===139 ? zlib.gunzipSync(bytes) : bytes).toString('utf8'));
}
if (fs.existsSync('_site/data.json.gz')) {
  const data=jsonAsset('_site/data.json.gz');
  const rows=[...data.medications];
  for (const url of Object.values(data.planDataFiles||{})) {
    const path='_site/'+String(url).split('?')[0].replace(/^\.\//,'').replace(/^\//,'');
    rows.push(...jsonAsset(path));
  }
  const formulary=rows.filter(r=>r.recordType==='formulary');
  const normalizeBrand=s=>String(s||'').trim().toLowerCase();
  const duplicatedRaw=formulary.filter(r=>{
    const match=String(r.name||'').match(/\[([^\[\]]+)\]\s*$/);
    return match && normalizeBrand(r.brand)===normalizeBrand(match[1]);
  });
  context.rows=formulary;
  const grouped=vm.runInContext('medicationGroups(rows)',context);
  const duplicatedDisplay=grouped.filter(g=>/\[([^\]]+)\]\s*\(\1\)/i.test(g.label));

  console.log('LIVE DATA AUDIT: '+formulary.length+' formulary records; '+grouped.length+' search groups; '+duplicatedRaw.length+' source rows with repeated bracketed brand; '+duplicatedDisplay.length+' redundant search labels.');
  if (duplicatedDisplay.length) throw Error('Unfixed duplicate search display labels: '+duplicatedDisplay.slice(0,4).map(g=>g.label).join('; '));
  console.log('SAMPLE RAW DUPLICATES: '+JSON.stringify(duplicatedRaw.slice(0,4).map(r=>({name:r.name,brand:r.brand,planId:r.planId}))));
}


// Medication autocomplete must not discard the selected/typed term just
// because the dropdown arrow was pressed.
const dropdownSource=source.slice(source.indexOf('  function renderComboboxOptions('),source.indexOf('  function updateActiveOption('));
if (!source.includes("if (opening) renderComboboxOptions(name, name !== 'medication');")) throw Error('Medication toggle still requests all names');
const wrapper={setAttribute(){}};
const input={value:'Mounjaro',setAttribute(){},closest(){return wrapper}};
const dropdown={hidden:true,innerHTML:''};
const menuContext={
  normalize:s=>String(s).trim().toLowerCase(),
  comboIds:{medication:['medicationInput','medicationOptions']},
  el:{medicationInput:input,medicationOptions:dropdown},
  valuesForCombo:()=>['Mounjaro','Valtoco','{1 (0.1 mL) diazepam } Pack','Omisirge'],
  rankedValues:(values,q)=>values.filter(value=>value.toLowerCase().includes(q)),
  escapeHtml:s=>String(s),
  closeAllComboboxes(){},
  comboState:{medication:{activeIndex:-1,showAll:false}}
};
vm.createContext(menuContext);
vm.runInContext(dropdownSource,menuContext);
vm.runInContext("renderComboboxOptions('medication', true)",menuContext);
if(!dropdown.innerHTML.includes('Mounjaro')||dropdown.innerHTML.includes('Valtoco')||dropdown.innerHTML.includes('Omisirge'))throw Error('Selected medication dropdown contains unrelated drugs');
input.value='';
vm.runInContext("renderComboboxOptions('medication', true)",menuContext);
if(!dropdown.innerHTML.includes('Type a brand or generic name')||dropdown.innerHTML.includes('Valtoco'))throw Error('Empty medication dropdown still exposes raw catalog');
input.value='Valt';
vm.runInContext("renderComboboxOptions('medication', false)",menuContext);
if(!dropdown.innerHTML.includes('Valtoco')||dropdown.innerHTML.includes('Mounjaro'))throw Error('Medication query suggestions incorrect');
console.log('PASS: autocomplete respects entered medication, empty-search prompt, and filtered results');

console.log('PASS: brand/generic labels, aliases, duplicate prevention, precise grouping, preserved coverage restrictions');
