"""Prevent cross-brand, route, release-period and combination update leakage."""
import gzip
import json
from pathlib import Path
from import_ach_baseline import compatible, tokens, explicit_brand_match

assert not compatible('acetaminophen 32 mg/mL Oral Solution', 'ACETAMINOPHEN SUPPOSITORY')
assert not compatible('nicotine 4 mg Inhalation Solution', 'NICOTINE NASAL SOLUTION')
assert not compatible('12 HR pseudoephedrine Extended Release Oral Tablet', 'PSEUDOEPHEDRINE TABLET 24-HOUR')
assert not compatible('omeprazole Delayed Release capsule', 'omeprazole Extended Release capsule')
assert not compatible('tacrolimus oral capsule', 'TACROLIMUS OINTMENT')
assert compatible('atorvastatin Oral Tablet', 'ATORVASTATIN TABLETS')
assert not explicit_brand_match('Triesence', {'name':'TRIAMCINOLONE ACETONIDE SUSPENSION (INJECTABLE)','brand':'KENALOG-10'})
assert explicit_brand_match('Victoza', {'name':'VICTOZA (SUBCUTANE.)','brand':''})
assert explicit_brand_match('Qvar Redihaler', {'name':'BECLOMETHASONE','brand':'QVAR REDIHALER'})
assert explicit_brand_match('Tudorza', {'name':'TUDORZA PRESSAIR (INHALATION)','brand':''})
assert not compatible('glecaprevir/pibrentasvir oral tablet','MAVYRET PELLET PACK (ORAL)')
assert tokens('{28 (estrogens conjugated (USP) 0.3 mg / medroxyprogesterone acetate 1.5 mg Oral Tablet) } Pack') != tokens('MEDROXYPROGESTERONE ACETATE TABLETS')

root=Path(__file__).resolve().parents[1]
data=json.loads(gzip.decompress((root/'_site/data.json.gz').read_bytes()))
for row in data['medications']:
 if not row.get('baselineSource'):continue
 for update in row['sourceUpdates']:
  assert compatible(row['name'],update['name']), 'Incompatible source applied: '+row['id']+' / '+update['name']
 if '[Triesence]' in row['name']:
  assert not any('KENALOG' in str(u).upper() for u in row['sourceUpdates'])
 if '[Prempro' in row['name']:
  assert not any(u['name']=='MEDROXYPROGESTERONE ACETATE TABLETS' for u in row['sourceUpdates'])
 if row.get('heldSourceUpdates'):
  assert row['pa']=='not_specified','Brand-specific uncertainty became confirmed no-PA'
 if row['name'].startswith('24 HR guanfacine') or row['name'].startswith('12 HR clonidine'):
  assert row['pa']=='conditional','Indication qualifier dropped a valid age-dependent PA rule'
 if row['name'].startswith('24 HR bupropion'):
  assert not any('12-HOUR' in u['name'] for u in row['sourceUpdates'])
 if '[Mavyret]' in row['name'] and 'Oral Tablet' in row['name']:
  assert row['pa']=='required','Explicit current tablet PA requirement missing'
print('PASS: ACH later updates preserve brand identity, route, combination ingredients and release period; verified actual source assignments')
