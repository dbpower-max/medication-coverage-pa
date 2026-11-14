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
console.log('PASS: brand/generic labels, aliases, duplicate prevention, precise grouping, preserved coverage restrictions');
