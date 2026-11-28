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
assert not compatible('0.9 ML tocilizumab-aazg 180 MG/ML Prefilled Syringe','TOCILIZUMAB-AAZG VIAL')
assert not compatible('2 ML naloxone hydrochloride 1 MG/ML Prefilled Syringe','NALOXONE VIAL (INJECTION)')
assert not compatible('abatacept subcutaneous injection','abatacept intravenous injection')
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
  # Their printed proprietary names omit the vaginal route. The linked labels
  # verify only these three plan rows on the specified formulary page.
  ring_names={'ach-json-848330':'ESTRING RING','ach-json-848333':'FEMRING','ach-json-848343':'FEMRING'}
  if row['id'] in ring_names and update.get('sourceEffective')=='2023-04-01' and update.get('sourcePage')==78:
   assert update['name']==ring_names[row['id']] and 'Vaginal System' in row['name']
   assert update['sourceUrl'].endswith('April%202023%202nd%20run.pdf')
   continue
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
  assert row['pa']=='conditional' and 'treated previously' in row['paText'],'Prior-DAA treatment condition lost from tablet PA rule'
print('PASS: ACH later updates preserve brand identity, route, combination ingredients and release period; verified actual source assignments')

# Compare every presumed row to its own archived formulary entry.
archive=json.loads(gzip.decompress((root/'dist/sources/ach/integrated-formulary-baseline.json.gz').read_bytes()))
baseline=[r for r in data['medications'] if r.get('baselineSource')]
assert len(baseline)==len(archive)==4454
for row in baseline:
 original=archive[row['sourceRow']-1]
 assert original['rxnorm_id']==row['rxnormId']
 flags=original['plans'][0]
 assert flags==row['baselineSource']['values']
 origins=row['benefitSources']
 if origins['preferred']=='presumed_2022':
  assert row['preferred']==('preferred' if flags['drug_tier']=='PREFERRED' else 'not_specified')
 if origins['pa']=='presumed_2022' and not row.get('heldSourceUpdates'):
  assert row['pa']==('required' if flags['prior_authorization'] else 'not_required')
 if origins['quantityLimited']=='presumed_2022':
  assert row['quantityLimited']==flags['quantity_limit']
 if origins['step']=='presumed_2022':
  assert (row['step']=='specified')==flags['step_therapy']
print('PASS: all 4,454 baseline entries preserve archived source flags and documented exceptions')
