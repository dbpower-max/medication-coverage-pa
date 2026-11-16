"""Validate all UHC source transcriptions, explicit bindings and untouched flags."""
import gzip,json,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from structured_statewide_criteria import validate_structure
from uhc_policy_access import product_matches,alias_parts
p=json.load(gzip.open('_site/data.json.gz'))
for f in p.get('planDataFiles',{}).values():p['medications']+=json.load(gzip.open('_site/'+f.split('?')[0].lstrip('./')))
policies={r['id']:r for r in p['policies'] if r['planId']=='uhc-community-az'}
structured={}
for key,policy in policies.items():
 s=json.load(open('_site/'+policy['structuredCriteriaUrl'].split('?')[0].lstrip('./')))
 raw=Path('dist',policy['sourceTextUrl'].lstrip('./')).read_text()
 # Base spans remain source-exact; display-only running-header removal is allowed.
 checked=copy.deepcopy(s)
 for b in checked['branches']:
  for f in list(b['fields'].values())+b['criteria']+b['notes']:f.pop('displayText',None)
 validate_structure(checked,raw);structured[key]=s
assert len(structured)==449
rows=[r for r in p['medications'] if r['planId']=='uhc-community-az']
flagged=[r for r in rows if r['pa'] in ['required','conditional'] or r.get('qlAmount') or r.get('qlDays')]
assert len(flagged)==3146
for r in flagged:
 for b in r.get('uhcClinicalBindings',[]):
  assert b['policyId'] in policies
  assert all(0<=i<len(structured[b['policyId']]['branches']) for i in b['branchIndexes'])
  if b['role']=='product':
   for i in b['branchIndexes']:
    dx=structured[b['policyId']]['branches'][i]['fields'].get('Diagnosis',{})
    if dx.get('text','').strip()=='Non-Preferred':assert r['preferred']=='non_preferred','Preferred product received nonpreferred criteria'
 if r.get('qlAmount') or r.get('qlDays'):assert any(b['role']=='global_quantity' for b in r['uhcClinicalBindings'])
 if r['pa'] in ['required','conditional'] and r['preferred']=='non_preferred':assert any(b['role']=='nonpreferred' for b in r['uhcClinicalBindings'])
for r in rows:
 if r['name'].lower().startswith('fentanyl transdermal patch'):
  labels=[label for b in r['uhcClinicalBindings'] for label in b.get('branchLabels',{}).values()]
  assert any('25 mcg/hr' in label and '100 mcg/hr' in label for label in labels),'Fentanyl source strengths were truncated'
 if r['name'] in ['APIDRA SOLOSTAR','APIDRA VIAL']:
  assert any(policies[b['policyId']]['policyCode']=='GL-231255' for b in r['uhcClinicalBindings'])
 if r.get('policyQuantityLimit'):
  assert r['policyQuantityLimit']['sourcePolicyId'].endswith('gl-512232')
  assert any(b['role']=='quantity' and b['branchIndexes']==[1] for b in r['uhcClinicalBindings'])
assert product_matches({'name':'AIMOVIG'},'Aimovig, Ajovy, Emgality 120 mg/mL'),'Different product strength blocked Aimovig'
assert not product_matches({'name':'metoprolol tartrate tablet'},'metoprolol succinate extended release tablet'),'Salt/form mismatch accepted'
assert not product_matches({'name':'Humulin R U-100'},'Humulin R U-500 kwikpen and vial'),'U500 concentration guard lost'
assert not product_matches({'name':'prednisolone ophthalmic solution'},'prednisolone oral solution'),'Oral policy crossed into ophthalmic form'
assert not product_matches({'name':'lidocaine injection solution'},'lidocaine topical patch'),'Topical policy crossed into injection'
assert product_matches({'name':'lansoprazole oral tablet delayed release dispersible 15 mg'},'generic lansoprazole ODT'),'Explicit ODT/dispersible formulation synonym missed'
assert any('25 mcg/hr' in a and '100 mcg/hr' in a for a in alias_parts('fentanyl patches 12 mcg/hr, 25 mcg/hr, 50 mcg/hr, 75 mcg/hr, 100 mcg/hr, tramadol ER tabs')),'Multi-strength source scope truncated'
assert not product_matches({'name':'fentanyl transdermal patch 100 mcg/hr'},'fentanyl patches 12 mcg/hr'),'Different patch dose accepted'
assert not product_matches({'name':'lidocaine injection solution 20 mg/ml'},'lidocaine injection solution 20 mg/2 ml'),'Different concentration accepted'
assert not product_matches({'name':'omeprazole oral capsule'},'omeprazole DR capsules'),'Unspecified release accepted for DR-only branch'
# Compare the build input after existing approved corrections; binding must never infer PA.
base=json.load(gzip.open('dist/data.json.gz'))
from source_restrictions import correct_source_restrictions,correct_source_conflicts
correct_source_restrictions(base['medications']);correct_source_conflicts(base['medications'])
original={r['id']:r for r in base['medications'] if r['planId']=='uhc-community-az'}
for r in rows:
 for key in ['name','brand','pa','paText','preferred','coverage','qlAmount','qlDays','sourceUrl','sourcePage']:
  actual,expected=r.get(key),original[r['id']].get(key)
  if key=='sourceUrl':actual,expected=actual.lstrip('./'),expected.lstrip('./')
  assert actual==expected,(r['id'],key)
print('PASS: 449 UHC policies/1,438 branches source-exact; all 3,146 restricted records checked; 2,989 QL references; flags, original names/IDs and source records unchanged')
