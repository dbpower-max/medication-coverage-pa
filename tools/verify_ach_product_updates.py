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
  # These literal brand names omit the nasal route on the printed source row.
  nasal_aliases={'ach-json-2540709':{'KLOXXADO LIQD','NALOXONE'},'ach-json-1725064':{'NARCAN LIQD (naloxone hcl)'}}
  if update['name'] in nasal_aliases.get(row['id'],set()):
   assert 'Nasal Spray' in row['name'] and (update.get('id')=='ach-mandated-formulary-10015' or update['sourcePage']==19 and update['sourceEffective']=='2023-04-01')
   continue
  divalproex={
   '1099563':('divalproex sodium tb24', 'Extended Release Oral Tablet'), '1099569':('divalproex sodium tb24', 'Extended Release Oral Tablet'),
   '1099596':('divalproex sodium csdr', 'Delayed Release Oral Capsule'),
   '1099625':('divalproex sodium tbec 125 mg, 250 mg','Delayed Release Oral Tablet'),
   '1099678':('divalproex sodium tbec 125 mg, 250 mg','Delayed Release Oral Tablet'),
   '1099870':('divalproex sodium tbec 500 mg','Delayed Release Oral Tablet')}
  if row['rxnormId'] in divalproex and (update['sourcePage']==15 or update.get('id')=='ach-mandated-formulary-9912'):
   printed,form=divalproex[row['rxnormId']]
   assert row['name'].endswith(form)
   if update['sourcePage']==15:
    assert update['name']==printed and update['sourceEffective']=='2023-04-01'
   else:
    assert form=='Delayed Release Oral Tablet' and update['name']=='DIVALPROEX SODIUM TABLET ENTERIC COATED'
   continue
  if row['rxnormId']=='1801289':
   assert row['name']=='Smoking Cessation 12 HR bupropion hydrochloride 150 MG Extended Release Oral Tablet'
   assert ((update['name']=='bupropion hcl (smoking deterrent)' and update['sourcePage']==72 and update['sourceEffective']=='2023-04-01')
           or (update.get('id')=='ach-mandated-formulary-10962' and update['sourcePage']==33 and update['sourceEffective']=='2026-11-01'))
   continue
  if update['name'] in ('bupropion hcl tb12','bupropion hcl tb24 150 mg, 300 mg'):
   sr=update['name']=='bupropion hcl tb12'
   assert row['rxnormId'] in ({'993503','993518','993536'} if sr else {'993541','993557'})
   assert row['name'].startswith('12 HR' if sr else '24 HR') and update['sourcePage']==15 and update['sourceEffective']=='2023-04-01'
   continue
  if update['name'].startswith('lamotrigine tb24 '):
   assert row['rxnormId'] in {'850087','900164','850091','900156','1146690','1098608'} and 'Extended Release' in row['name'] and update['sourcePage']==15
   continue
  if update.get('id')=='ach-mandated-formulary-9972' and row['rxnormId'] in {'1551300','1551306','2395779','2395785'}:
   assert row['name'].endswith('Auto-Injector [Trulicity]') and update['name']=='DULAGLUTIDE SOLUTION PEN-INJECTION' and update['sourcePage']==10
   continue
  if row['rxnormId']=='1657212' and update.get('id')=='ach-mandated-formulary-9792':
   assert row['name']=='omalizumab 150 MG Injection [Xolair]' and update['name']=='OMALIZUMAB SOLUTION RECONSTITUTED' and update['sourcePage']==6
   continue
  devices={'1190225':('COMBIVENT RESPIMAT','9824'),'1487524':('ANORO ELLIPTA','9828'),'1487528':('ANORO ELLIPTA','9828'),
           '1651275':('STIOLTO RESPIMAT','9827'),'2166928':('STIOLTO RESPIMAT','9827')}
  if row['rxnormId'] in {'866049','790284','746804','746811','746813','746815'}:
   assert 'Dry Powder Inhaler' in row['name']
   serevent=row['rxnormId']=='866049'
   if update['sourcePage']==13:
    expected='SEREVENT DISKUS' if serevent else 'ASMANEX TWISTHALER '+row['name'].split()[0]+' METERED DOSES AEPB'
    assert update['name']==expected and update['sourceEffective']=='2023-04-01'
   else:
    assert update.get('id')=='ach-mandated-formulary-'+('9826' if serevent else '9811') and update['sourceEffective']=='2026-11-01'
   continue
  if row['rxnormId'] in {'1246310','1660934','1246313','1660938','2196592'}:
   assert row['name'].endswith('Metered Dose Inhaler [Dulera]')
   assert (update['name']=='DULERA' and update['sourceEffective']=='2023-04-01' and update['sourcePage']==13
    or update.get('id')=='ach-mandated-formulary-9823' and update['sourceEffective']=='2026-11-01' and update['sourcePage']==7)
   continue
  if row['rxnormId'] in {'1667882','2166204','1552004'} and update.get('id')=='ach-mandated-formulary-9798':
   assert row['name'].endswith('Inhalation Spray [Spiriva]') and update['name']=='TIOTROPIUM BROMIDE MONOHYDRATE AEROSOL SOLUTION'
   assert update['sourceEffective']=='2026-11-01' and update['sourcePage']==6
   continue
  if row['rxnormId'] in devices and update['sourcePage'] in (13,7):
   product,number=devices[row['rxnormId']]
   assert 'Inhal' in row['name'] and product.split()[0].lower() in row['name'].lower()
   if update['sourcePage']==13:
    assert update['sourceEffective']=='2023-04-01' and update['name'].startswith(product+' ')
   else:
    assert update['sourceEffective']=='2026-11-01' and update.get('id')=='ach-mandated-formulary-'+number
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

# PU26135 addresses these exact products and the generic twice-daily pen.
products = {r['id']:r for r in data['medications']}
for rx in ('1111642', '1876385', '2693465', '2705597', '2705600', '2705603', '847910', '847915'):
 row = products['ach-json-' + rx]
 assert row['preferred'] == 'non_preferred' and row['pa'] == 'required'
 assert row['benefitSources']['preferred'] == 'selected_plan'
 assert any(u.get('sourceUrl','').endswith('PU26135.html') for u in row['sourceUpdates'])
 assert row['baselineSource']['values']['drug_tier'] == 'PREFERRED'
iv = products['ach-json-2705588']
assert iv['benefitSources']['preferred'] == 'statewide_reference'
assert not any(u.get('sourceUrl','').endswith('PU26135.html') for u in iv['sourceUpdates'])
assert all(products['ach-json-' + rx]['preferred'] == 'preferred' for rx in ('847913', '847917'))

for rx in ('1191234','1191222','1659929','1191250','2679504','1725059','1725064','2540709','2680741'):
 row=next(r for r in baseline if r['rxnormId']==rx)
 ids={u['id'] for u in row['sourceUpdates']}
 assert ('ach-mandated-formulary-10015' in ids)==(rx=='2540709')
 assert ('ach-notice-13954' in ids)==(rx in ('1191250','2679504'))
 assert 'ach-notice-13955' not in ids
 nasal='Nasal Spray' in row['name']
 assert (str(row['qlAmount']),str(row['qlDays']))==(('2','1') if nasal else ('',''))
 assert row['reviewedPresentation']['identityRxcui']==int(rx)
 assert ('deviceSafety' in row['reviewedPresentation'])==(rx=='1191234')

 for u in row['sourceUpdates']:
  if u['id'] in ('ach-mandated-formulary-10015','ach-mandated-formulary-10016'):
   assert 'BRAND ONLY' in u['rawBenefit']
  if u['id']=='ach-mandated-formulary-9694':
   assert 'OVER-THE-COUNTER & PRESCRIPTION ONLY' in u['rawBenefit']

# Exact-plan daily quantity and statewide 30-day quantities remain distinct for every form.
reviewed=[r for r in baseline if r.get('reviewedPresentation',{}).get('statewideMonthlyLimit')]
assert len(reviewed)==31
for r in reviewed:
 d=r['reviewedPresentation']
 state,= [u for u in r['sourceUpdates'] if u['scope']=='statewide_reference']
 notice,= [u for u in r['sourceUpdates'] if u.get('sourceUrl','').endswith('PU26135.html')]
 plan,= [u for u in r['sourceUpdates'] if u.get('sourcePage')==25]
 odt='Disintegrating' in r['name']
 assert odt==('ODT' in notice['name'])==('DISPERSABLE' in state['name'])==('tbdp' in plan['name'])
 assert r['qlDays']=='1' and r['qlAmount']==plan['qlAmount'] and r['benefitSources']['quantityLimited']=='selected_plan'
 assert state['qlDays']=='30' and state['qlAmount']==d['statewideMonthlyLimit']
 assert r['pa']=='conditional' and r['benefitSources']['pa']=='statewide_reference' and r['step']=='not_specified'

from import_ach_baseline import ACH_ISENTRESS, LAMOTRIGINE_OPTIONS
for rx in set(ACH_ISENTRESS)|set(LAMOTRIGINE_OPTIONS):
 row=next(r for r in baseline if r['rxnormId']==rx)
 state=ACH_ISENTRESS[rx][1] if rx in ACH_ISENTRESS else LAMOTRIGINE_OPTIONS[rx][1]
 assert [u['id'] for u in row['sourceUpdates'] if u['scope']=='statewide_reference']==(['ach-mandated-formulary-'+str(state)] if state else [])
 assert row['reviewedPresentation']['identityRxcui']==int(rx)
 if rx in LAMOTRIGINE_OPTIONS:
  limit=LAMOTRIGINE_OPTIONS[rx][3]
  assert row['qlAmount']==(f'{limit} tablets' if limit else '') and row['qlDays']==('1' if limit else '')
  assert row['pa']!='conditional'
 else:
  assert 'Do not substitute' in row['reviewedPresentation']['note']

from import_ach_baseline import ACH_CLONAZEPAM
for rx,ids in ACH_CLONAZEPAM.items():
 row=next(r for r in baseline if r['rxnormId']==rx)
 state=[u for u in row['sourceUpdates'] if u['scope']=='statewide_reference']
 assert [u['id'] for u in state]==['ach-mandated-formulary-'+str(n) for n in ids]
 assert row['pa']=='conditional' and not row.get('sourceConflict')
 assert ('< 6 years' in state[0]['paText'])==('Disintegrating' not in row['name'])
 assert '< 6 years' in state[1]['paText'] and 'Anticonvulsant' in row['paText']
solution=next(r for r in baseline if r['rxnormId']=='199387')
assert solution['qlAmount']=='8 mL' and 'retail' in solution['reviewedPresentation']['planDailyAndRetailLabel']

from import_ach_baseline import ACH_TRULICITY_PENS, ACH_XOLAIR_DEVICES
for rx in set(ACH_TRULICITY_PENS)|set(ACH_XOLAIR_DEVICES):
 row=next(r for r in baseline if r['rxnormId']==rx)
 assert row['pa']=='required' and row['preferred']=='preferred' and row['benefitSources']['preferred']=='selected_plan'
 assert row['reviewedPresentation']['identityRxcui']==int(rx)
 state,=[u for u in row['sourceUpdates'] if u['scope']=='statewide_reference']
 if rx in ACH_TRULICITY_PENS:
  assert row['qlAmount']=='2 mL' and row['qlDays']=='28' and state['sourcePage']==10
 else:
  assert state['id'].endswith({'single-dose vial':'9792','auto-injector':'9793','prefilled syringe':'9794'}[ACH_XOLAIR_DEVICES[rx][0]])
  assert row['qlAmount']=='' and row['qlDays']==''

for rx,limit in [('351264','16 tablets'),('351265','4 tablets')]:
 r=next(r for r in baseline if r['rxnormId']==rx)
 assert r['qlAmount']==limit and r['qlDays']=='1' and r['pa']=='conditional'
 assert r['benefitSources']['preferred']==r['benefitSources']['pa']==r['benefitSources']['quantityLimited']=='selected_plan'
 assert len(r['sourceUpdates'])==3 and r['achProviderRule']['effectiveDate'] is None

from import_ach_baseline import ACH_OUD_COMBINATIONS
for rx,(_bup,_nal,_printed,limit) in ACH_OUD_COMBINATIONS.items():
 row=next(r for r in baseline if r['rxnormId']==rx)
 film=rx!='351266'
 assert row['qlAmount']==str(limit)+(' films' if film else ' tablets') and row['qlDays']=='1'
 assert row['benefitSources']['quantityLimited']==row['benefitSources']['preferred']=='selected_plan'
 assert bool(row.get('ageLimited'))==film and 'achProviderRule' not in row and row['pa'] not in ('required','conditional')
 assert {u['id'] for u in row['sourceUpdates'] if u['scope']=='statewide_reference'}==({'ach-mandated-formulary-9699'} if film else set())

from import_ach_baseline import ACH_ENOXAPARIN, ACH_MONTELUKAST
for rx,(dose,number) in ACH_ENOXAPARIN.items():
 r=next(r for r in baseline if r['rxnormId']==rx)
 state,=[u for u in r['sourceUpdates'] if u['scope']=='statewide_reference']
 assert state['id']=='ach-mandated-formulary-'+str(number) and state['qlAmount']=='60' and state['qlDays']=='30'
 assert r['qlAmount']==('60' if rx=='854255' else '48 mL' if rx=='854245' else '60 mL')
 assert '180 mL' not in r['qlAmount'] and r['reviewedPresentation']['identityRxcui']==int(rx)
for rx,(heading,printed,number) in ACH_MONTELUKAST.items():
 r=next(r for r in baseline if r['rxnormId']==rx)
 assert [u['id'] for u in r['sourceUpdates'] if u['scope']=='statewide_reference']==['ach-mandated-formulary-'+str(number)]
 assert (r['pa']=='conditional')==(rx=='351246') and r['qlDays']=='1'
