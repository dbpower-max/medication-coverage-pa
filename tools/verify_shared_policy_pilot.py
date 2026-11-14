"""Exercise shared updates, isolated reassignment and invalid-reference rejection."""
import gzip,json
from copy import deepcopy
from shared_policy_pilot import resolve, validate_shared_policy
from pathlib import Path
x=json.loads(gzip.decompress(Path('_site/data.json.gz').read_bytes()))
meds=[m for m in x['medications'] if m.get('paPolicyAssignments')]
assert len(meds)==4
for m in meds:
 assert resolve(x,m)[0]['requirements']
before={m['id']:resolve(x,m) for m in meds}
y=deepcopy(x); y['sharedPolicies'][0]['guide']['requirements'][0]='TEST shared revision'
assert all(resolve(y,m)[0]['requirements'][0]=='TEST shared revision' for m in meds)
y=deepcopy(x); changed=next(m for m in y['medications'] if m['id']==meds[0]['id'])
changed['paPolicyAssignments'][0]['branchId']='banner-guide-glp-oral'
assert resolve(y,changed)!=before[changed['id']]
assert all(resolve(y,m)==before[m['id']] for m in meds[1:])
for field,value in [('version','invalid'),('branchId','missing')]:
 y=deepcopy(x); next(m for m in y['medications'] if m.get('paPolicyAssignments'))['paPolicyAssignments'][0][field]=value
 try: validate_shared_policy(y)
 except (AssertionError,KeyError): pass
 else: raise AssertionError('Invalid assignment accepted')
y=deepcopy(x); next(m for m in y['medications'] if m.get('paPolicyAssignments'))['planId']='uhc-community-az'
try: validate_shared_policy(y)
except AssertionError: pass
else: raise AssertionError('Wrong-plan assignment accepted')
print('PASS: 4 assignments; shared update; isolated reassignment; plan, version and branch guards')
