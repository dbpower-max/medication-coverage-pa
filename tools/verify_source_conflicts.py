import gzip
import json
from pathlib import Path
from source_restrictions import correct_source_conflicts

root=Path(__file__).resolve().parents[1]
data=json.loads(gzip.decompress((root/'_site/data.json.gz').read_bytes()))
rows=data['medications']+data['statewideDrugList']
for name in ['CLONIDINE HCL (ADHD) TABLET 12-HOUR','MEDROXYPROGESTERONE ACETATE TABLETS','PROGESTERONE MICRONIZED CAPSULES','PIMECROLIMUS CREAM']:
 r=next(r for r in data['statewideDrugList'] if r['name']==name)
 assert r['preferred']=='not_specified', 'Unprinted nonpreferred status: '+name
 assert len(r['sourceRows'])>=2, 'Original differing rows lost'
for r in rows:
 if r['name']=='PIMECROLIMUS CREAM' and r['planId'] in ('ahcccs-statewide','banner-ufc'):
  assert r['pa']=='not_specified' and r.get('paUncertaintyReason')
held=[r for r in data['medications'] if r['planId']=='uhc-community-az' and r.get('paUncertaintyReason')]
assert len(held)==7, 'Unexpected UHC conflict-resolution count'
assert all(r['pa']=='not_specified' and len(r['conflictSources'])>=2 for r in held)
step_held=[r for r in data['medications'] if r['planId']=='uhc-community-az' and r.get('stepUncertaintyReason')]
assert len(step_held)==8 and all(r['step']=='not_specified' and not r['stepText'] for r in step_held)
quantity_held=[r for r in rows if r.get('quantityUncertaintyReason')]
assert len(quantity_held)>=4 and all(not r['qlAmount'] and not r['qlDays'] for r in quantity_held)
dx_held=[r for r in rows if r.get('diagnosisRequiredUncertaintyReason')]
assert len(dx_held)==4 and all(not r['diagnosisRequired'] for r in dx_held)
assert next(r for r in data['statewideDrugList'] if r['brand']=='HUMULIN R U-500 KWIKPEN')['pa']=='required'
assert correct_source_conflicts(rows)==0, 'Conflict correction not idempotent'
print('PASS: unsupported preference/PA/ST/QL/diagnosis assertions remain unknown; all original source variants retained; corrections idempotent')
