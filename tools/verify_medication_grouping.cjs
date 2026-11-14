const fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('dist/app.js','utf8');
const functions = source.slice(source.indexOf('  function medicationIdentity('), source.indexOf('  function categoryOptions('));
const context = {normalize:s=>String(s).toLowerCase().trim(),state:{planId:'test',data:{medications:[]}}};
vm.createContext(context);vm.runInContext(functions,context);
function groups(rows) {context.rows=rows.map((r,i)=>({id:String(i),planId:'test',...r})); return vm.runInContext('medicationGroups(rows)',context);}
const pair=groups([{name:'drug tablet (generic for BRAND)'},{name:'BRAND (brand for drug tablet)',pa:'required'}]);
if(pair.length!==1||pair[0].records.length!==2||pair[0].records[1].pa!=='required')throw Error('Explicit brand/generic pair lost');
if(groups([{name:'drug tablet',brand:'BRAND'},{name:'DRUG TABLET',brand:'Brand'}]).length!==1)throw Error('Duplicate identity');
if(groups([{name:'drug oral tablet'},{name:'drug subcutaneous solution'},{name:'drug oral tablet ER'},{name:'drug oral tablet 5 mg'},{name:'drug oral tablet 10 mg'}]).length!==5)throw Error('Variants incorrectly merged');
if(groups([{name:'drug',planId:'A'},{name:'drug',planId:'B'}]).length!==2)throw Error('Plans merged');
if(groups([{name:'drug tablet',brand:'REFERENCE BRAND'}])[0].records.length!==1)throw Error('Invented generic product');
console.log('PASS: explicit pair, duplicate identity, route/release/strength separation, plan isolation, original product rules retained');
