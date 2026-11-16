const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),assert=require('node:assert/strict');
const data=JSON.parse(zlib.gunzipSync(fs.readFileSync('_site/data.json.gz')));
const script=fs.readFileSync('_site/app.js','utf8');
const start=script.indexOf('  function policySourceBranches('),end=script.indexOf('  function bindCriteriaLibrary(',start);
assert(start>0&&end>start);
const ctx={escapeHtml:s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')};
vm.createContext(ctx);vm.runInContext(script.slice(start,end),ctx);
let policies=0,branches=0,stageBranches=0;
for(const policy of [...data.statewidePaCriteria,...data.policies]) {
 if(!policy.sourceTextUrl)continue;
 const text=fs.readFileSync('_site/'+policy.sourceTextUrl.replace(/^\.\//,''),'utf8');
 const parsed=ctx.policySourceBranches(text);
 assert.equal(parsed.intro+parsed.branches.map(b=>b.text).join(''),text,'Clinical source changed: '+policy.id);
 if(policy.planId==='ahcccs-ffs-aihp')assert(parsed.branches.length,'Statewide source lost all product branches: '+policy.id);
 for(const b of parsed.branches){
  assert(b.product);if(b.stage){assert(/initial authorization|reauthorization/i.test(b.stage));stageBranches++;}
 }
 const html=ctx.policySourceBranchMarkup(text);
 if(parsed.branches.length){assert(html.includes('Complete unformatted source'));assert(html.includes(ctx.escapeHtml(text)));}
 policies++;branches+=parsed.branches.length;
}
const unsafe=ctx.policySourceBranchMarkup('Product Name:<script>bad()</script>\nApproval Length\n12 month(s)\nA AND B OR C');
const wrapped=ctx.policySourceBranches('Product Name:Preferred: Drug A;\nNon-Preferred: Drug B\nApproval Length\n12 month(s)\nA AND B OR C');
assert(wrapped.branches[0].product.includes('Non-Preferred: Drug B'),'Wrapped product scope lost from branch heading');
assert(!unsafe.includes('<script>')&&unsafe.includes('&lt;script&gt;'));
assert(unsafe.includes('A AND B OR C'));
assert(stageBranches>50);
console.log('PASS: '+policies+' source sections; '+branches+' lossless product branches; '+stageBranches+' explicit treatment stages; original AND/OR, source notes and text retained');
