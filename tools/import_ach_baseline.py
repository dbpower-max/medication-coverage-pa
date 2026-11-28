"""Combine the historical 2022 Arizona Complete Health formulary with dated source evidence."""
import collections, copy, gzip, hashlib, json, re
from pathlib import Path
from functools import lru_cache
from source_restrictions import correct_source_restrictions, correct_source_conflicts
ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://www.azcompletehealth.com/content/dam/centene/az-complete-health/json/Drugs_FAB_CNCAZCH01_AZ_Medicaid_Integrated_Formulary_eff_9-1-22_07142026131014_AZ.json'
# Exact branded anticoagulant starter packs in the 2022 JSON and November 2026
# statewide list. Ordinary tablet rows in the same class are separate options.
STARTER_PACK_REFERENCES = {'1992428': 'formulary-9832', '1549683': 'formulary-9835'}
SOURCE_SCOPE='Use the 2022 Arizona Complete Health formulary as the presumed baseline. Later applicable sources update only the fields they address. AHCCCS listings identify statewide benefits. A complete current plan formulary remains unverified.'
STOP=set('w soln pref syr bitartrate bromide oral topical inhalation subcutaneous intramuscular intramusc intraven intravenous injection injectable nasal sublingual subcutane intrav sub q tablet tablets tab capsule capsules solution suspension cream ointment gel patch syringe syringes vial vials pen pens kit spray powder aerosol elixir suppository chewable chew chewable disintegrating odt er xr cr dr extended release delayed controlled hr hour hours 24 12 72 hcl hydrochloride hydrobromide sulfate sulphate mesylate sodium potassium mg mcg ml gm g % per actuation actuat metered dose inhaler nebulizer autoinjector cartridge prefilled pref pack pak various cf ag authorized generic only brand'.split())
@lru_cache(maxsize=None)
def tokens(s):
 # Parentheses can contain active ingredients in RxNorm combination packs.
 # Never discard that content as if every parenthesis were a route qualifier.
 s=re.sub(r'\((?:ADHD|SICKLE CELL DISEASE|CHEMOTHERAPY|USP|RX ONLY)\)',' ',s,flags=re.I)
 s=s.lower();s=re.sub(r'\d+(?:\.\d+)?',' ',s)
 return set(re.findall(r'[a-z]+',s))-STOP-{'usp'}

@lru_cache(maxsize=None)
def forms(s):
 s=s.lower(); f=set()
 for key,pattern in {'tablet':r'tablet|\btab\b|odt','capsule':r'capsule','granules':r'granul|pellet','liquid':r'solution|suspension|elixir','cream':r'cream','ointment':r'ointment','patch':r'patch','gel':r'\bgel\b','injection':r'inject|subcut|intramusc|intraven|intraven|\bintrav\b|syringe|\bsyr\b|\bvial\b|\bpen\b','nasal':r'nasal','inhalation':r'inhal|nebulizer','rectal':r'suppositor|rectal','ophthalmic':r'ophthalmic|ocular','otic':r'\botic\b','vaginal':r'vaginal'}.items():
  if re.search(pattern,s):f.add(key)
 return f

def compatible(a,b):
 fa,fb=forms(a),forms(b)
 if fa and fb and not fa&fb:return False
 if ('injection' in fa) != ('injection' in fb) and fa and fb:return False
 devices=lambda s:{kind for kind,pattern in {
  'vial':r'\bvial\b', 'syringe':r'syringe|\bpref\s+syr\b',
  'autoinjector':r'auto.?inj|clickject', 'pen':r'\bpen\b'
 }.items() if re.search(pattern,s,re.I)}
 da,db=devices(a),devices(b)
 if da and db and not da&db:return False
 routes=lambda s:{kind for kind,pattern in {
  'iv':r'intraven|\biv\b', 'sc':r'subcut|sub-q|\bsc\b|\bsq\b',
  'im':r'intramusc|\bim\b', 'intrathecal':r'intrathecal', 'intravitreal':r'intravitreal'
 }.items() if re.search(pattern,s,re.I)}
 ra,rb=routes(a),routes(b)
 if ra and rb and not ra&rb:return False
 # Shared words such as "solution" do not make different routes equivalent.
 for route in ['nasal','inhalation','rectal','ophthalmic','otic','vaginal']:
  if (route in fa)!=(route in fb):return False
 # Do not transfer a rule across immediate/extended release formulations.
 extended=lambda s:bool(re.search(r'\b(er|xr|cr|dr)\b|extended|delayed|controlled|24.hour|12.hour',s,re.I))
 if extended(a)!=extended(b):return False
 period=lambda s:re.search(r'\b(12|24|72)\s*[- ]?(?:hr|hour)\b',s,re.I)
 pa,pb=period(a),period(b)
 if pa and pb and pa[1]!=pb[1]:return False
 delayed=lambda s:bool(re.search(r'\bdr\b|delayed|enteric',s,re.I))
 if delayed(a)!=delayed(b):return False
 return True

def explicit_brand_match(brand, source):
 """A named brand needs named-brand evidence, not ingredient equivalence."""
 norm=lambda s:re.sub(r'\s+',' ',s).strip().casefold()
 if norm(brand)==norm(source.get('brand','')):return True
 name=source['name']
 # Notices may put the brand in the name and a route in parentheses.
 name=re.sub(r'\s*\((?:subcutane\.?|subcutaneous|oral|topical|inhalation|nasal|intravenous|intramuscular)\)\s*$','',name,flags=re.I)
 # The RxNorm baseline abbreviates the marketed TUDORZA PRESSAIR name.
 # DailyMed identifies this as aclidinium bromide inhalation powder; this
 # alias is valid only for the explicit inhalation notice, never another route.
 if norm(brand)=='tudorza' and norm(name)=='tudorza pressair' and 'inhalation' in forms(source['name']):return True
 return norm(brand)==norm(name)

def apply_benefit_updates(record, candidates):
 """Resolve each benefit independently and keep the source of the displayed value."""
 baseline = 'presumed_2022'
 origins = dict.fromkeys(('coverage', 'preferred', 'pa', 'step', 'quantityLimited'), baseline)
 groups = (
  ('coverage', ('coverage', 'coverageText'), None),
  ('preferred', ('preferred',), 'preferenceUncertaintyReason'),
  ('pa', ('pa', 'paText', 'paExceptionText'), 'paUncertaintyReason'),
  ('step', ('step', 'stepText'), 'stepUncertaintyReason'),
  ('quantityLimited', ('quantityLimited', 'qlAmount', 'qlDays'), 'quantityUncertaintyReason'),
  ('ageLimited', ('ageLimited', 'ageRestrictionText'), 'ageLimitedUncertaintyReason'),
 )
 for field, keys, uncertainty in groups:
  relevant = [r for r in candidates if r.get(uncertainty) or
              r.get(field) not in (None, '', False, 'not_specified') or
              (field == 'quantityLimited' and (r.get('qlAmount') or r.get('qlDays'))) or
              (field == 'ageLimited' and r.get('ageRestrictionText'))]
  if not relevant:
   continue
  # A plan notice establishes the plan's field. A statewide statement retains
  # its own attribution, even when it is the only newer source for that field.
  exact = [r for r in relevant if r.get('validation') != 'mandated_statewide_minimum_with_plan_adoption_evidence']
  scope = 'selected_plan' if exact else 'statewide_reference'
  applicable = exact or relevant
  date = max(r['sourceEffective'] for r in applicable)
  latest = [r for r in applicable if r['sourceEffective'] == date]
  def values(r):
   vals = [r.get(k) for k in keys]
   if field == 'quantityLimited':
    vals[0] = bool(r.get('quantityLimited') or r.get('qlAmount') or r.get('qlDays'))
   if field == 'ageLimited':
    vals[0] = bool(r.get('ageLimited') or r.get('ageRestrictionText'))
   return tuple(v if v is not None else '' for v in vals)
  options = {values(r) for r in latest}
  reasons = [r[uncertainty] for r in latest if r.get(uncertainty)]
  if reasons or len(options) > 1:
   for key in keys:
    record[key] = ''
   record[field] = False if field in ('quantityLimited', 'ageLimited') else 'not_specified'
   reason = ' '.join(dict.fromkeys(reasons)) or f'Same-date sources disagree about {field}.'
   record[uncertainty or 'sourceConflict'] = reason
   record['sourceConflict'] = reason
  else:
   record.update(zip(keys, options.pop()))
  origins[field] = scope
 record['benefitSources'] = origins
 record['auditScope'] = baseline if not candidates else 'mixed_sources'

ACH_FEB_2023_PDL = ('https://www.azcompletehealth.com/content/dam/centene/az-complete-health/pdf/provider/formulary/'
                    'AZ%20Integrated%20English%20CNCAZCH01_19108_2023-01-25-Final%20508C%20PDF%20-%20Feb%202023.pdf')
ACH_APR_2023_PDL = ('https://www.azcompletehealth.com/content/dam/centene/az-complete-health/pdf/provider/formulary/'
                    'AZ%20Integrated%20English%20CNCAZCH01_19108_Final%20508C%20PDF%20-%20April%202023%202nd%20run.pdf')
# Printed pages 20–21, PDF pages 25–26. F denotes formulary, not preference.
ACH_DAILY_INSULIN_LIMITS = {
 '311027': ('NOVOLIN N SUSP',26),
 '311033': ('NOVOLIN R SOLN IJ',26),
 '311040': ('INSULIN ASPART SOLN IJ',26),
 '1653202': ('INSULIN ASPART FLEXPEN SOPN',26),
 '242120': ('INSULIN LISPRO SOLN IJ',26),
 '1652639': ('INSULIN LISPRO KWIKPEN SOPN',26),
 '1926331': ('INSULIN LISPRO JUNIOR KWIKPEN SOPN',26),
 '285018': ('LANTUS SOLN',26),
 '847232': ('LANTUS SOLOSTAR SOPN',26),
 '106892': ('HUMULIN 70/30 SUSP 70 UNIT/ML-30 UNIT/ML',25),
 '847189': ('HUMULIN 70/30 KWIKPEN SUPN 30 UNIT/ML-70 UNIT/ML',26),
}

# Exact brand, strength, route and device mappings in the October 2026 ACC bulletin.
# Do not extend these to other forms by ingredient or by a similar product name.
ACH_OCT_NOTICE_MATCH = {
 '1111642': ('ach-notice-13943', 'COPAXONE 20 MG/ML (SUBCUTANEOUS)'),
 '1876385': ('ach-notice-13945', 'OCREVUS (INTRAVEN.)'),
 '2693465': ('ach-notice-13946', 'OCREVUS ZUNOVO VIAL (SUBCUTANEOUS)'),
 '2705603': ('ach-notice-13875', 'YESINTEK VIAL (SUBCUTANEOUS)'),
 '2705597': ('ach-notice-13874', 'YESINTEK SYRINGE (SUBCUTANEOUS)'),
 '2705600': ('ach-notice-13874', 'YESINTEK SYRINGE (SUBCUTANEOUS)'),
 '847913': ('ach-notice-13905', 'BYETTA PENS (SUBCUTANEOUS)'),
 '847917': ('ach-notice-13905', 'BYETTA PENS (SUBCUTANEOUS)'),
}
ACH_OCT_NOTICE_URL = 'https://www.azcompletehealth.com/newsroom/PU26135.html'
AHCCCS_MAY_MEMO = 'https://www.azahcccs.gov/Resources/Downloads/PharmacyUpdates/2026/Contractor_Memo_May_2026_PT_MeetingFinal.pdf'

# Exact ACC notice and AHCCCS rows independently matched to labeled rescue presentations.
# An SCD for an injection solution does not establish the container or OTC status.
NALOXONE_SOURCES = {
 '1191234': ('naloxone hcl soct', None, ()),
 '1659929': ('naloxone hcl soln .4 mg/ml, 4 mg/10ml', None, ()),
 '1191222': ('naloxone hcl soln .4 mg/ml, 4 mg/10ml', None, ()),
 '1191250': ('naloxone hcl sosy', 13954, (9693,)),
 '2679504': ('naloxone hcl sosy', 13954, (9693,)),
 '1725059': (None, None, (9694,)),
 '1725064': ('NARCAN LIQD (naloxone hcl)', 13957, (9694,10016)),
 '2540709': ('KLOXXADO LIQD', 13953, (9695,10015)),
 '2680741': (None, 13958, (10016,)),
}

def naloxone_updates(rx, sources, statewide):
 printed,notice,ref_ids=NALOXONE_SOURCES[rx]
 updates=[]
 if printed:
  updates.append({'name':printed,'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL',
                  'sourceUrl':ACH_APR_2023_PDL,'sourceEffective':'2023-04-01','sourcePage':19,
                  'sourceKind':'plan_formulary','coverage':'listed','rawBenefit':'F; restrictions blank.'})
 if notice:
  updates.append(sources['ach-notice-'+str(notice)])
 for n in ref_ids:
  ref=sources['ach-mandated-formulary-'+str(n)]
  updates.append({**ref, **ref['statewideReference'],
                  'rawBenefit':' | '.join([ref['name'],ref['brand'],statewide['formulary-'+str(n)]['notes'],ref['preferred'],
                                           str(ref['statewideReference'].get('qlAmount','')),str(ref['statewideReference'].get('qlDays',''))])})
 return updates

# Grouped by the exact conventional/ODT source rows, never merely by ingredient.
ACH_ANTIPSYCHOTIC_FORMS = [
 ('clozapine',False,'197536 429212 197535 309374',13820,10210,'883b5d43-0339-7dc1-f775-93791fb9b978'),
 ('clozapine',True,'721773 476179 476177 1006801 996921',13819,10209,'6fccf4f7-2e30-4272-9800-225aaef20584'),
 ('olanzapine',False,'200034 312078 312079 314154 312077 283639',13823,10215,'6077f5c4-01d7-4c1d-97a0-cb859f98ce68'),
 ('olanzapine',True,'314155 312076 351107 351108',13822,10214,'df43938a-3469-40eb-8166-f0a2fd29d6d8'),
 ('risperidone',False,'312828 312829 312830 312831 312832 314211',13828,10220,'43aa2a4f-1123-4f86-800b-9218882f7bcd'),
 ('risperidone',True,'645037 403825 401953 401954 616698 616705',13826,10218,'58b7504f-c4a3-ef1b-e063-6394a90ac0f3'),
]
ACH_ANTIPSYCHOTIC_OPTIONS={rx:(drug,odt,notice,state,label)
 for drug,odt,ids,notice,state,label in ACH_ANTIPSYCHOTIC_FORMS for rx in ids.split()}

def antipsychotic_option(rx,name,sources):
 drug,odt,notice,state,label=ACH_ANTIPSYCHOTIC_OPTIONS[rx]
 assert name.startswith(drug+' ') and ('Disintegrating' in name)==odt and name.endswith('Oral Tablet')
 strength=re.search(r'([\d.]+) MG',name)[1]
 age=18 if drug=='clozapine' else 6
 printed=drug+(' tbdp' if odt else ' tabs')
 if drug=='clozapine':
  daily=5
 elif drug=='olanzapine':
  daily=2 if strength in ('5','10') else 1
  printed+=' '+('5 mg, 10 mg' if daily==2 else '15 mg, 20 mg' if odt else '2.5 mg, 7.5 mg, 15 mg, 20 mg')
 elif odt:
  daily=2
 else:
  daily=4 if strength in ('0.25','0.5') else 3 if strength in ('1','2') else 2
  printed+=' '+{4:'.25 mg, .5 mg',3:'1 mg, 2 mg',2:'3 mg, 4 mg'}[daily]
 dated={'name':printed,'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL','sourceUrl':ACH_APR_2023_PDL,
        'sourcePage':25,'sourceEffective':'2023-04-01','sourceKind':'plan_formulary','coverage':'listed',
        'quantityLimited':True,'qlAmount':str(daily)+' tablets','qlDays':'1','ageLimited':True,
        'ageRestrictionText':f'At least {age} yrs old','rawBenefit':f'F; QL({daily} ea daily); AL(At least {age} yrs old).'}
 ref=sources['ach-mandated-formulary-'+str(state)]
 source={**ref, **ref['statewideReference']}
 raw=source['qlAmount']
 monthly=re.search(r'(?<!\d)'+strength+r'MG: (\d+)',raw)[1] if state==10214 else raw
 assert all(v=='30' for v in source['qlDays'].split()) and monthly.isdigit() and source['pa']=='conditional'
 source.update(qlAmount=monthly,qlDays='30',rawBenefit=f"{source['name']} | {source['brand']} | PREFERRED DRUG | QL {raw}, days {ref['statewideReference']['qlDays']}.")
 display={'prescribingHeading':f"{drug.capitalize()} {strength} mg "+('orally disintegrating tablet' if odt else 'oral tablet'),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,'identityRxcui':int(rx),
          'statewideMonthlyLimit':monthly,'statewideAge':age,
          'note':f"AHCCCS Statewide requires PA below age {age}. At age {age} and older, PA is waived when prescribed by a psychiatric clinician, a developmental pediatrician or another prescriber approved by the MCO."}
 return [dated,sources['ach-notice-'+str(notice)],source],display

# April 2023 integrated PDL, printed pp. 10 and 22. The November statewide
# reference distinguishes oral solids, prepared liquid and extended release.
ACH_ISENTRESS = {
 '1235591':('ISENTRESS CHEW',10298,'Isentress 100 mg chewable tablet'),
 '1235595':('ISENTRESS CHEW',10298,'Isentress 25 mg chewable tablet'),
 '1486841':('ISENTRESS PACK',10299,'Isentress 100 mg granules for oral suspension, single-dose packet'),
 '744846':('ISENTRESS TABS',10300,'Isentress 400 mg film-coated oral tablet'),
 '1924315':('ISENTRESS HD TABS',None,'Isentress HD 600 mg film-coated oral tablet'),
}
ACH_LAMOTRIGINE = [
 ('850087 900164 850091','lamotrigine tb24 25 mg, 50 mg, 100 mg',9880,'24-hour extended-release oral tablet',3,'260dc37d-6e64-4688-82dc-10a1a428af17'),
 ('900156 1146690 1098608','lamotrigine tb24 200 mg, 250 mg, 300 mg',9880,'24-hour extended-release oral tablet',2,'260dc37d-6e64-4688-82dc-10a1a428af17'),
 ('103968 252479 198430 252478','lamotrigine tbdp',9881,'orally disintegrating tablet',None,'df34faa4-829e-413a-a230-cbec604eead9'),
 ('198427 198428 198429 282401','lamotrigine tabs',None,'oral tablet',None,'3dfdcc2d-b7c5-7abf-e063-6394a90a24a6'),
 ('311264 311265','lamotrigine chew',9878,'chewable, dispersible tablet for oral suspension',None,'50fcf452-2d21-493e-a1dd-0c6ea9ac6184'),
]
LAMOTRIGINE_OPTIONS={rx:(printed,state,form,limit,label) for ids,printed,state,form,limit,label in ACH_LAMOTRIGINE for rx in ids.split()}

def verified_oral_form(rx,name,sources):
 limit=None
 if rx in ACH_ISENTRESS:
  printed,state,heading=ACH_ISENTRESS[rx]
  assert '[Isentress]' in name and name.startswith('raltegravir ')
  page=27
  label='89a5ec53-d956-4329-8004-0f40f51c88a3'
  note='The chewable tablets and oral suspension have different pharmacokinetics from the film-coated tablets. Do not substitute either for the 400 mg Isentress or 600 mg Isentress HD film-coated tablet.'
  if state is None:
   note+=' The statewide tablet listing does not specify the HD presentation.'
 else:
  printed,state,form,limit,label=LAMOTRIGINE_OPTIONS[rx]
  assert 'lamotrigine' in name and '[' not in name
  strength=re.search(r'([\d.]+) MG',name)[1]
  heading=f'Lamotrigine {strength} mg {form}'
  page=15
  note='Disperse the tablet only as directed in the product labeling. The statewide suspension entry describes a separate product.' if state==9878 else ''
 dated={'name':printed,'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL','sourceUrl':ACH_APR_2023_PDL,
        'sourceEffective':'2023-04-01','sourcePage':page,'sourceKind':'plan_formulary','coverage':'listed','rawBenefit':'F; restrictions blank.'}
 if limit:
  dated.update(quantityLimited=True,qlAmount=f'{limit} tablets',qlDays='1',rawBenefit=f'F; QL({limit} ea daily).')
 updates=[dated]
 if state:
  ref=sources['ach-mandated-formulary-'+str(state)]
  updates.append({**ref, **ref['statewideReference'],
                  'rawBenefit':' | '.join((ref['name'],ref['brand'],'PREFERRED DRUG' if ref['preferred']=='preferred' else 'Preference blank'))})
 return updates,{'prescribingHeading':heading,'identityRxcui':int(rx),'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,'note':note}

ACH_CLONAZEPAM = {
 '349194':(9758,9856), '349195':(9759,9857), '349198':(9760,9858),
 '349196':(9761,9859), '349197':(9762,9860), '197527':(9755,9853),
 '197528':(9756,9854), '197529':(9757,9855),
}

def clonazepam_option(rx,name,sources):
 assert name.startswith('clonazepam ') and name.endswith('Oral Tablet')
 odt='Disintegrating' in name
 strength=re.search(r'([\d.]+) MG',name)[1]
 daily=2 if strength=='2' else 4
 printed='clonazepam '+('tbdp ' if odt else 'tabs ')+('2 mg' if daily==2 else '.125 mg, .25 mg, .5 mg, 1 mg' if odt else '.5 mg, 1 mg')
 dated={'name':printed,'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL','sourceUrl':ACH_APR_2023_PDL,
        'sourcePage':14,'sourceEffective':'2023-04-01','sourceKind':'plan_formulary','coverage':'listed','quantityLimited':True,
        'qlAmount':f'{daily} tablets','qlDays':'1','rawBenefit':f'F; QL({daily} ea daily)'+('' if odt else '; AL(At least 6 yrs old)')}
 if not odt:
  dated.update(ageLimited=True,ageRestrictionText='At least 6 yrs old')
 updates=[dated]
 for n,category in zip(ACH_CLONAZEPAM[rx],('Antianxiety agents','Anticonvulsants')):
  ref=sources['ach-mandated-formulary-'+str(n)]
  state={**ref,**ref['statewideReference']}
  assert state['sourcePage'] in (5,7,8) and state['qlDays']=='30'
  assert state['qlAmount']==('60' if strength=='2' else '120')
  state['rawBenefit']=f"{category}: {state['name']} | {state['brand']} | preference blank | QL {state['qlAmount']} per 30 days, unit blank."
  updates.append(state)
 anxiety='Antianxiety listing: PA for more than one anxiolytic in 30 days.' if odt else 'Antianxiety listing: PA for age under 6 or more than one anxiolytic in 30 days.'
 qualifier=anxiety+' Anticonvulsant listing: PA for age under 6 or more than one anxiolytic in 30 days.'
 display={'prescribingHeading':f'Clonazepam {strength} mg '+('orally disintegrating tablet' if odt else 'oral tablet'),
          'identityRxcui':int(rx),'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+('1aef0069-80ea-483d-ac70-c8d485462c5b' if odt else '34366dd2-432c-4fa9-8fab-832cca781b84'),
          'scopedMonthlyLabel':f"QL: {state['qlAmount']} tablets per 30 days",
          'scopedStatePa':'PA by indication, age or anxiolytic count' if odt else 'PA if age <6 or >1 anxiolytic in 30 days',
          'note':'AHCCCS Statewide. '+qualifier}
 return updates,display

ACH_TRULICITY_PENS={'1551300':'0.75','1551306':'1.5','2395779':'3','2395785':'4.5'}
ACH_XOLAIR_DEVICES={
 '2058946':('prefilled syringe','150 mg/1 mL'), '2058950':('prefilled syringe','75 mg/0.5 mL'),
 '2663918':('prefilled syringe','300 mg/2 mL'), '2663923':('auto-injector','300 mg/2 mL'),
 '2673761':('auto-injector','150 mg/1 mL'), '2673763':('auto-injector','75 mg/0.5 mL'),
 '1657212':('single-dose vial','150 mg/1.2 mL after reconstitution'),
}

def injectable_notice_option(rx,name,sources):
 is_trulicity=rx in ACH_TRULICITY_PENS
 if is_trulicity:
  assert '[Trulicity]' in name and 'Auto-Injector' in name
  printed='TRULICITY ((SUBCUTANEOUS)*'
  heading='Trulicity '+ACH_TRULICITY_PENS[rx]+' mg/0.5 mL subcutaneous injection, single-dose pen'
  label='463050bd-2b1c-40f5-b3c3-0a04bb433309'
  memo_page=7
  state_id=9972
  earlier='TRULICITY'
  note=''
 else:
  assert '[Xolair]' in name
  device,amount=ACH_XOLAIR_DEVICES[rx]
  vial=device=='single-dose vial'
  heading=f'Xolair {amount} '+('subcutaneous injection powder, single-dose vial' if vial else 'subcutaneous injection solution, '+device)
  label='7f6a2191-adfb-48b9-9bfa-0d9920479f0d'
  printed='XOLAIR VIAL (SUB-Q)' if vial else 'XOLAIR SYRINGE/AUTOINJ ((SUBCUTANEOUS)*'
  memo_page=8
  state_id=9792 if vial else 9793 if device=='auto-injector' else 9794
  earlier='XOLAIR SOLR' if vial else 'XOLAIR SOSY' if rx in ('2058946','2058950') else None
  note='Boxed warning for anaphylaxis. Initiate treatment in a healthcare setting equipped to manage anaphylaxis.'
  if device=='auto-injector':
   note+=' The label specifies the auto-injector for patients aged 12 years and older.'
 notice={'name':printed,'sourceTitle':'Arizona Complete Health October 2026 Medicaid formulary update PU26135',
         'sourceUrl':ACH_OCT_NOTICE_URL,'sourceEffective':'2026-10-01','coverage':'listed','preferred':'preferred',
         'rawBenefit':f'Preferred column, table 1 data row {13 if is_trulicity else 14}. The asterisk identifies statewide listing.'}
 if not is_trulicity and vial:
  notice=sources['ach-notice-13917']
 ref=sources['ach-mandated-formulary-'+str(state_id)]
 assert ref['brand']==('TRULICITY' if is_trulicity else 'XOLAIR') and ref['pa']=='required'
 state={**ref,**ref['statewideReference'],'rawBenefit':('' if is_trulicity else 'BRAND ONLY | ')+'PREFERRED DRUG | PA REQUIRED | ST and QL blank.'}
 updates=[notice,state]
 display={'prescribingHeading':heading,'identityRxcui':int(rx),'note':note,'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,
          'sourceReferences':[[f'AHCCCS Statewide · June 8 contractor memo · p. {memo_page}',AHCCCS_MAY_MEMO+f'#page={memo_page}']]}
 if not is_trulicity and device=='auto-injector':
  display.update(separate=True,label=heading)
 if earlier:
  dated={'name':earlier,'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL','sourceUrl':ACH_APR_2023_PDL,
         'sourceEffective':'2023-04-01','sourcePage':18 if is_trulicity else 13,'sourceKind':'plan_formulary','coverage':'listed',
         'pa':'required','paText':'The plan formulary lists PA.','rawBenefit':'F; SP; PA.'}
  if is_trulicity:
   dated.update(qlAmount='2 mL',qlDays='28',quantityLimited=True,rawBenefit='F; QL(2 ml per 28 days retail); PA.')
   display['planRetailLimit']={'amount':'2 mL','days':'28'}
  updates.append(dated)
 return updates,display

# Printed constituent order in the April PDL varies. Use both verified amounts.
ACH_OUD_COMBINATIONS = {
 '351266': ('2', '0.5', '0.5 mg-2 mg', 16),
 '1010603': ('2', '0.5', '0.5 MG-2 MG', 16),
 '1307058': ('4', '1', '1 MG-4 MG, 4 MG-1 MG', 8),
 '1010606': ('8', '2', '2 MG-8 MG', 4),
 '1307063': ('12', '3', '3 MG-12 MG', 2),
}

def oud_combination_updates(rx,name,sources):
 bup,nal,printed,limit = ACH_OUD_COMBINATIONS[rx]
 film=rx!='351266'
 form='Film [Suboxone]' if film else 'Tablet'
 assert name==f'buprenorphine {bup} MG / naloxone {nal} MG Sublingual {form}'
 unit='films' if film else 'tablets'
 drug='SUBOXONE FILM SL' if film else 'buprenorphine hcl-naloxone hcl dihydrate subl'
 earlier={'name':drug+' '+printed,'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL',
          'sourceUrl':ACH_APR_2023_PDL,'sourceEffective':'2023-04-01','sourcePage':10,'sourceKind':'plan_formulary',
          'coverage':'listed','quantityLimited':True,'qlAmount':f'{limit} {unit}','qlDays':'1',
          'rawBenefit':f'F; QL({limit} ea daily); AL(At least 6 yrs old)' if film else 'F; Tablet Formulation; QL(16 ea daily).'}
 notice=sources['ach-notice-13948' if film else 'ach-notice-13947']
 updates=[earlier,{**notice,'rawBenefit':'Preferred column, opioid dependence treatments. '+('BRAND PREFERRED OVER GENERIC.' if film else 'BUPRENORPHINE/NALOXONE TAB (SUBLINGUAL).')}]
 heading=f'Suboxone {bup} mg/{nal} mg sublingual film' if film else f'Buprenorphine {bup} mg/naloxone {nal} mg sublingual tablet'
 display={'prescribingHeading':heading,'identityRxcui':int(rx),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+('8a5edcf9-828c-4f97-b671-268ab13a8ecd' if film else '17b63f10-c9df-44be-80fa-6f1c305583b8')}
 if film:
  earlier.update(ageLimited=True,ageRestrictionText='Arizona Complete Health April 2023 formulary age limit: ≥6 years.')
  ref=sources['ach-mandated-formulary-9699']
  assert ref['brand']=='SUBOXONE FILM' and ref['sourcePage']==3
  updates.append({**ref,**ref['statewideReference'],'rawBenefit':'SUBOXONE FILM | BRAND ONLY | PREFERRED DRUG | PA, ST and quantity fields blank.'})
  display['planAgeBadge']='Age ≥6 years'
  display['note']='Arizona Complete Health lists brand Suboxone film as preferred over generic film.'
 return updates,display

ACH_ENOXAPARIN = {
 '854228':('30 mg/0.3 mL',9839), '854235':('40 mg/0.4 mL',9841),
 '854238':('60 mg/0.6 mL',9842), '854241':('80 mg/0.8 mL',9843),
 '854248':('100 mg/1 mL',9836), '854245':('120 mg/0.8 mL',9837),
 '854252':('150 mg/1 mL',9838), '854255':('100 mg/mL',9836),
}
ACH_MONTELUKAST = {
 '200224':('10 mg oral tablet','tabs',9803), '242438':('5 mg chewable tablet','chew',9801),
 '311759':('4 mg chewable tablet','chew',9801), '351246':('4 mg oral granules, single-dose packet','pack',9802),
}

def april_formulary(name,page,raw,**fields):
 return {'name':name,'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL','sourceUrl':ACH_APR_2023_PDL,
         'sourceEffective':'2023-04-01','sourceKind':'plan_formulary','sourcePage':page,'coverage':'listed','rawBenefit':raw,**fields}

def statewide_option(sources,number,raw):
 ref=sources['ach-mandated-formulary-'+str(number)]
 return {**ref,**ref['statewideReference'],'rawBenefit':raw}

def enoxaparin_option(rx,name,sources):
 dose,number=ACH_ENOXAPARIN[rx]
 state=statewide_option(sources,number,'VARIOUS VIAL OR SYRINGE | PREFERRED DRUG | PA and ST blank | QL 60, days 30, unit blank.')
 assert state['qlAmount']=='60' and state['qlDays']=='30' and state['sourcePage']==7
 syringe=rx!='854255'
 assert ('Prefilled Syringe' in name)==syringe and 'enoxaparin sodium' in name
 heading='Enoxaparin '+dose+(' injection solution, single-dose prefilled syringe' if syringe else ' injection solution')
 display={'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d978e06e-b758-460b-81d3-69f7a5b89b00',
          'scopedMonthlyLabel':'QL: 60 per 30 days (unit unspecified)',
          'note':'Boxed warning for spinal or epidural hematoma with neuraxial anesthesia or spinal puncture.'}
 updates=[state]
 if syringe:
  amount='48 mL' if rx=='854245' else '60 mL'
  printed='120 mg/0.8ml' if rx=='854245' else '30 mg/0.3ml, 40 mg/0.4ml, 60 mg/0.6ml, 80 mg/0.8ml, 100 mg/ml, 150 mg/ml'
  updates.append(april_formulary('enoxaparin sodium sosy '+printed,14,f'F; QL({amount.lower()} per 30 days retail); SP.',
                                quantityLimited=True,qlAmount=amount,qlDays='30'))
  display['planRetailLimit']={'amount':amount,'days':'30'}
 else:
  display['note']+=' The labeled 300 mg/3 mL multidose vial contains benzyl alcohol. The April 2023 plan limit of 180 mL per 30 days at retail names this vial strength. Confirm the dispensed container.'
  display['sourceReferences']=[['Arizona Complete Health · 300 mg/3 mL injection solution · April 2023 · p. 14',ACH_APR_2023_PDL+'#page=14']]
 return updates,display

def montelukast_option(rx,sources):
 heading,printed,number=ACH_MONTELUKAST[rx]
 packet=rx=='351246'
 unit='packet' if packet else 'tablet'
 state=statewide_option(sources,number,('PA IS NOT REQUIRED for < 4 Years of Age | preference blank' if packet else 'PREFERRED DRUG | PA blank')+' | ST blank | QL 30, days 30, unit blank.')
 assert state['sourcePage']==6 and state['qlAmount']=='30' and state['qlDays']=='30'
 dated=april_formulary('montelukast sodium '+printed,13,'F; QL(1 ea daily).',quantityLimited=True,qlAmount='1 '+unit,qlDays='1')
 display={'prescribingHeading':'Montelukast '+heading,'identityRxcui':int(rx),'scopedMonthlyLabel':f'QL: 30 {unit}s per 30 days',
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+('9a3bfc59-0ca6-4433-abf5-41659bfe0a8f' if packet else '49669ac0-0bb5-4576-bed5-9e85e0d76a44'),
          'note':'Boxed warning for serious neuropsychiatric events. For allergic rhinitis, reserve montelukast for patients with inadequate response or intolerance to alternatives.'}
 if packet:
  dated.update(pa='conditional',paText='The plan requires PA for granules starting at age 4.',
               rawBenefit='F; age 4 and up requires PA; QL(1 ea daily); AL(Up to 3 yrs old).')
  display['planConditionalLabel']='PA if age ≥4'
 return [dated,state],display

ACH_BRAND_ANTICOAGULANTS = {
 '1364441':('Eliquis','2.5',9831), '1364447':('Eliquis','5',9831), '1992428':('Eliquis','pack',9832),
 '1114202':('Xarelto','10',9834), '1232084':('Xarelto','15',9834), '1232088':('Xarelto','20',9834),
 '2059017':('Xarelto','2.5',9834), '1549683':('Xarelto','pack',9835),
}

def brand_anticoagulant(rx,name,sources):
 brand,strength,number=ACH_BRAND_ANTICOAGULANTS[rx]
 pack=strength=='pack'
 assert brand in name and ('} Pack' in name)==pack
 ref=statewide_option(sources,number,'BRAND ONLY | PREFERRED DRUG | PA and ST blank.')
 assert ref['sourcePage']==7 and ref['preferred']=='preferred'
 ref['rawBenefit']+=f" | QL {ref['qlAmount']}, days {ref['qlDays']}, unit blank."
 display={'identityRxcui':int(rx),'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+(
          'e9481622-7cc6-418a-acb6-c5450daae9b0' if brand=='Eliquis' else '10db92f9-2300-4a80-836b-673e1ae91610'),
          'scopedMonthlyLabel':f"QL: {ref['qlAmount']} tablets per {ref['qlDays']} days"}
 title=brand.upper()+(' STARTER PACK TBPK' if pack else ' TABS')
 if not pack:
  raw,amount,days='QL(2 ea daily)','2 tablets','1'
  heading=f'{brand} {strength} mg oral tablet'
 elif brand=='Eliquis':
  raw,amount,days='QL(74 ea per 365 days retail)','74 tablets','365'
  heading='Eliquis 30-Day Starter Pack — 74 oral tablets of 5 mg'
  display['planRetailLimit']={'amount':amount,'days':days}
 else:
  raw,amount,days='51 per month;; QL(1.7 ea daily)','1.7 tablets','1'
  heading='Xarelto Starter Pack — 42 oral tablets of 15 mg and 9 of 20 mg'
  display['planDailyAndRetailLabel']='QL: 51 tablets per month (1.7 tablets per day)'
 display['prescribingHeading']=heading
 if pack:
  display['note']='Quantity limits count the tablets supplied in the starter pack. See prescribing information for the dosing schedule.'
 dated=april_formulary(title,14,'F; '+raw,quantityLimited=True,qlAmount=amount,qlDays=days)
 return [dated,ref],display

ACH_RESPIRATORY_DEVICES = {
 '1487528':('Anoro','30',9828,13843), '1487524':('Anoro','7',9828,13843),
 '2166928':('Stiolto','10',9827,13844), '1651275':('Stiolto','60',9827,13844),
 '1190225':('Combivent','120',9824,13842),
}

def respiratory_device(rx,name,sources):
 brand,count,number,notice_id=ACH_RESPIRATORY_DEVICES[rx]
 assert brand in name and name.startswith(count+' ACTUAT')
 ref=statewide_option(sources,number,'PREFERRED DRUG | '+('PA; QL 1 per 30 days, unit blank; ST blank.' if brand!='Combivent' else 'PA, ST and QL blank.'))
 notice=sources['ach-notice-'+str(notice_id)]
 assert ref['sourcePage']==7 and notice['preferred']=='preferred'
 display={'identityRxcui':int(rx)}
 fields={}
 if brand=='Anoro':
  title='ANORO ELLIPTA 25 MCG/INH-62.5 MCG/INH'
  heading=f'Anoro Ellipta 62.5/25 mcg per inhalation dry powder inhaler, {count} blisters'
  raw,amount,days='QL(2 ea daily)','2','1'
  display['planDailyAndRetailLabel']='QL: 2 per day (unit unspecified)'
  label='2dbd0671-c565-40c5-bf0f-e324db26799c'
 elif brand=='Stiolto':
  title='STIOLTO RESPIMAT 2.5 MCG/ACT-2.5 MCG/ACT'
  heading=f'Stiolto Respimat 2.5/2.5 mcg per actuation metered inhalation spray, {count} actuations'
  raw,amount,days='QL(1 gm daily); PA','1 g','1'
  fields={'pa':'required','paText':'The Arizona Complete Health formulary lists PA.'}
  label='01e15aee-40e0-23f3-537f-c96dd63e2cb1'
 else:
  title='COMBIVENT RESPIMAT AERS 20 MCG/ACT-100 MCG/ACT'
  heading='Combivent Respimat 20/100 mcg per actuation metered inhalation spray, 120 actuations'
  raw,amount,days='1 rtl pack lmt amt; 30 rtl pack lmt day(s)','1 pack','30'
  display['planRetailLimit']={'amount':amount,'days':days}
  label='9832312e-0310-4ab6-8501-afa976fc7eb2'
 if brand!='Combivent':
  assert ref['pa']=='required' and ref['qlAmount']=='1' and ref['qlDays']=='30'
  display['scopedMonthlyLabel']='QL: 1 per 30 days (unit unspecified)'
 display.update(prescribingHeading=heading,labelUrl='https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label)
 dated=april_formulary(title,13,'F; '+raw,quantityLimited=True,qlAmount=amount,qlDays=days,**fields)
 return [dated,notice,ref],display

def hormone_identity(rx,sources):
 label='https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='
 april=ACH_APR_2023_PDL
 state='./sources/ahcccs-drug-list-2026-11-01.pdf'
 display={'identityRxcui':int(rx),'separate':True}
 if rx=='310169':
  heading='Estradiol 0.01% vaginal cream (0.1 mg/g)'
  display.update(labelUrl=label+'f76232ed-b109-43d1-bf2e-d41b6420c37d',
                 note='Each gram of the labeled cream contains 0.1 mg estradiol.')
  updates=[april_formulary('estradiol vaginal crea',78,'F'),
           statewide_option(sources,11031,'ESTRADIOL VAGINAL CREAM 0.01% | ESTRACE CREAM | preference, PA, ST and QL blank.')]
 elif rx=='1597076':
  heading='Testosterone 1.62% transdermal gel pump — 20.25 mg/1.25 g per actuation, 60 actuations'
  display.update(labelUrl=label+'0d84e5a6-11e9-4940-8991-21c611c4c32f',
                 note='AHCCCS Statewide lists the authorized generic pump as preferred with PA. The Prasco 88 g pump (NDC 66993-951-88) is a labeled authorized generic. Confirm the manufacturer and package. Boxed warning for secondary exposure to testosterone in children.',
                 sourceReferences=[['AHCCCS Statewide · authorized generic 1.62% pump only · p. 3',state+'#page=3'],
                                   ['Arizona Complete Health · pharmacy and AHCCCS criteria','https://www.azcompletehealth.com/providers/pharmacy.html']])
  updates=[april_formulary('testosterone gel td 1 %, 1.62 %, 20.25 mg/1.25gm, 25 mg/2.5gm, 40.5 mg/2.5gm, 50 mg/5gm',
                           10,'F; PA',pa='required',paText='The plan formulary lists PA for transdermal testosterone gel.')]
 else:
  yuvafem=rx=='1797113'
  heading='Yuvafem 10 mcg vaginal tablet in a single-use applicator' if yuvafem else 'Estradiol 10 mcg vaginal insert — product form varies'
  display['labelUrl']=label+('d20abc9a-8f47-e274-c9b1-b71c9489761f' if yuvafem else '6247e329-e20e-4ea5-9cc1-b593bd494577')
  display['sourceReferences']=[['Arizona Complete Health · estradiol vaginal tablets · April 2023 · p. 78',april+'#page=78']]
  if yuvafem:
   display['note']='Yuvafem is a film-coated tablet supplied in a disposable applicator. The April 2023 formulary gives 58 tablets per 168 days at retail for its estradiol vaginal tablet listing. It does not name the Yuvafem package.'
  else:
   display['note']='The same generic RxNorm concept includes an applicator-delivered tablet and a manually inserted softgel. The April 2023 retail limit of 58 per 168 days applies to the tablet listing. Confirm the prescribed presentation.'
   display['sourceReferences'].append(['Imvexxy softgel insert · FDA label',label+'6ce645c0-a550-4ae9-8dbd-3853ee8b7d26'])
  updates=[]
 display.update(prescribingHeading=heading,label=heading)
 return updates,display

ACH_ANTICONVULSANT_FORMS = {
 '1099596':('125','sprinkle',9910,None), '1099563':('250','extended',9911,None),
 '1099569':('500','extended',9911,None), '1099625':('125','delayed',9912,16),
 '1099678':('250','delayed',9912,16), '1099870':('500','delayed',9912,8),
 '198358':('400','tablet',9902,9), '198359':('600','tablet',9902,6), '310285':('600 mg/5 mL','suspension',9901,None),
}

def anticonvulsant_option(rx,name,sources):
 strength,form,number,limit=ACH_ANTICONVULSANT_FORMS[rx]
 ref=statewide_option(sources,number,'Preference, PA, ST and QL blank.')
 assert ref['sourcePage']==8 and ref['preferred']=='not_specified' and not ref['qlAmount'] and not ref['qlDays']
 labels={'extended':'0dc024ce-efc8-4690-7cb5-639c728fccac','delayed':'08a65cf4-7749-4ceb-6895-8f4805e2b01f',
         'sprinkle':'4619aff4-0f80-444f-858d-42e4137aa809','felbamate':'2f522701-397a-11de-8a39-0800200c9a66'}
 if form in ('tablet','suspension'):
  assert 'felbamate' in name
  heading=f'Felbamate {strength} mg oral tablet' if limit else 'Felbamate 600 mg/5 mL oral suspension'
  printed=f'felbamate tabs {strength} mg' if limit else 'felbamate susp'
  label=labels['felbamate']
  note='Boxed warnings for aplastic anemia and acute liver failure.'
 else:
  assert 'divalproex' in name
  form_label={'sprinkle':'delayed-release oral sprinkle capsule','extended':'24-hour extended-release oral tablet',
              'delayed':'delayed-release oral tablet'}[form]
  heading=f'Divalproex sodium {strength} mg {form_label}'
  printed={'sprinkle':'divalproex sodium csdr','extended':'divalproex sodium tb24',
           'delayed':'divalproex sodium tbec '+('500 mg' if strength=='500' else '125 mg, 250 mg')}[form]
  label=labels[form]
  note='Boxed warnings for hepatotoxicity, fetal risk and pancreatitis.'
 dated=april_formulary(printed,15,f'F; QL({limit} ea daily)' if limit else 'F')
 if limit:
  dated.update(quantityLimited=True,qlAmount=f'{limit} tablets',qlDays='1')
 return [dated,ref],{'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
                     'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,'note':note}

ACH_ANXIOLYTIC_OPTIONS = {
 '197464':('Clorazepate dipotassium','15',9763,2), '197465':('Clorazepate dipotassium','3.75',9764,4),
 '197466':('Clorazepate dipotassium','7.5',9765,4), '197900':('Lorazepam','0.5',9772,4),
 '197901':('Lorazepam','1',9773,4), '197902':('Lorazepam','2',9774,2), '311376':('Lorazepam','2 mg/mL',9771,2),
 '198057':('Oxazepam','10',9775,2), '312134':('Oxazepam','15',9776,2), '198059':('Oxazepam','30',9777,2),
}

# Reviewed salt, release and route distinctions on ACH April pp14–15.
ACH_SEIZURE_FORMS={
 '1313112':('phenytoin susp',9906,'Phenytoin 125 mg/5 mL oral suspension','093fd736-5971-47af-b4ef-08c1696cebe8'),
 '1313885':('phenytoin chew',9904,'Phenytoin 50 mg chewable tablet','78b38e7b-1460-4adc-b738-320ffa6259c2'),
 '855671':('phenytoin sodium extended',9905,'Phenytoin sodium 100 mg extended-release oral capsule','36262a4c-33f1-40a5-e063-6394a90ad36a'),
 '855861':('phenytoin sodium extended',9905,'Phenytoin sodium 200 mg extended-release oral capsule','c40f66cc-6f4a-4b29-84ba-d265e4848735'),
 '855873':('phenytoin sodium extended',9905,'Phenytoin sodium 300 mg extended-release oral capsule','c40f66cc-6f4a-4b29-84ba-d265e4848735'),
 '855871':('DILANTIN',9905,'Dilantin (phenytoin sodium) 30 mg extended-release oral capsule','86dd27d1-9cee-48ae-b55d-e2d2f7dbc593'),
}
for ids,printed,number,form,label in [
 ([('388311',100),('200133',200),('200131',300)],'cp12',9869,'12-hour extended-release oral capsule','2676f950-48b4-4bef-a792-ea4570de9aa6'),
 ([('199378',100),('402505',200),('402506',400)],'tb12',9872,'12-hour extended-release oral tablet','726a127b-03b2-44e8-a63d-078b35e27525'),
 ([('308973',100)],'chew',9868,'chewable tablet','0526a054-3eda-49b4-b390-7d5d16e30af8'),
 ([('308979',200)],'tabs',9871,'immediate-release oral tablet','0526a054-3eda-49b4-b390-7d5d16e30af8'),
 ([('308976','100 mg/5 mL')],'susp',9870,'oral suspension','0526a054-3eda-49b4-b390-7d5d16e30af8'),
]:
 for rx,strength in ids:
  dose=f'{strength} mg' if isinstance(strength,int) else strength
  ACH_SEIZURE_FORMS[rx]=('carbamazepine '+printed,number,f'Carbamazepine {dose} {form}',label)

def seizure_form_option(rx,name,sources):
 printed,number,heading,label=ACH_SEIZURE_FORMS[rx]
 carb='carbamazepine' in name.lower()
 assert carb or 'phenytoin' in name.lower()
 ref=statewide_option(sources, number,'Preference, PA, ST and QL blank.')
 assert ref['sourcePage']==8 and ref['pa']=='not_specified' and ref['step']=='not_specified' and not ref['qlAmount'] and not ref['qlDays']
 if rx=='855871':assert 'DILANTIN' in ref.get('brand','').upper()
 note=''
 if not carb:
  note='The suspension and chewable tablet contain phenytoin free acid. The extended-release capsules contain phenytoin sodium. The free-acid form has approximately 8% more drug content. A switch between forms may require dose adjustment and serum level monitoring.'
 elif number==9869:
  note='The extended-release capsule may be opened and the beads sprinkled on soft food. Swallow the beads without crushing or chewing.'
 elif number==9872:
  note='Swallow the extended-release tablet whole. Do not crush, chew or break.'
 display={'label':heading,'prescribingHeading':heading,'separate':True,'identityRxcui':int(rx),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,'note':note}
 return [april_formulary(printed,14 if carb else 15,'F'),ref],display

ACH_EMERGENCY_CONTRACEPTION={
 '1005928':('Ella','2bf93d23-cddd-4613-9066-5b5fa090404b'),
 '1736014':('Option 2','7d7b9e61-9f3d-477d-b74d-b0cc725f9bba'),
 '1922759':('My Choice','500d9418-69a8-f4f3-e063-6394a90a9b66'),
 '2003710':('New Day','9e8c96f6-ab51-4721-b276-1ca02a712510')
}
def emergency_tablet(rx,name,sources):
 brand,label=ACH_EMERGENCY_CONTRACEPTION[rx]
 ella=rx=='1005928'
 assert '['+brand+']' in name and ('ulipristal acetate 30 MG' if ella else 'levonorgestrel 1.5 MG') in name
 heading=brand+' ('+('ulipristal acetate) 30 mg' if ella else 'levonorgestrel) 1.5 mg')+' emergency contraception oral tablet'
 display={'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
   'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label}
 updates=[]
 if ella:
  ref=statewide_option(sources,10444,'ELLA | PREFERRED | PA/ST blank | QL 1, days 5, unit blank.')
  assert ref['sourcePage']==22 and ref['qlAmount']=='1' and ref['qlDays']=='5'
  dated=april_formulary('ELLA',31,'F; QL(1 ea per 5 days retail)',quantityLimited=True,qlAmount='1 tablet',qlDays='5')
  updates=[dated,ref]
  display.update(planRetailLimit={'amount':'1 tablet','days':'5'},scopedMonthlyLabel='QL: 1 tablet per 5 days',
    note='Label: take within 120 hours. Wait at least 5 days after taking Ella before starting or resuming hormonal contraception.')
 else:
  display.update(note='OTC label: take within 72 hours.',sourceReferences=[['Arizona Complete Health · April 2023 · generic levonorgestrel emergency contraception 1.5 mg tablet listing',ACH_APR_2023_PDL+'#page=31']])
  if rx=='1736014':
   ref=statewide_option(sources,10443,'OPTION 2 | PREFERRED | PA, ST and QL blank.')
   assert ref['sourcePage']==22 and 'OPTION 2' in ref['brand'].upper()
   updates=[ref]
 return updates,display

ACH_LEVETIRACETAM={'403884':100,'387003':1000,'311288':250,'311289':500,'311290':750,'807832':500,'846378':750,'1731020':500}

def levetiracetam_option(rx,name,sources):
 strength=ACH_LEVETIRACETAM[rx]
 assert 'levetiracetam' in name and f'{strength} MG' in name
 if rx=='403884':
  number,printed=9882,'levetiracetam soln or 100 mg/ml, 500 mg/5ml'
  title='Levetiracetam 100 mg/mL oral solution (500 mg/5 mL)'
  label='0bc8468f-832c-4e71-95a2-db464d4d54bc'
  note='Use a calibrated measuring device.'
 elif 'Extended Release' in name:
  number,printed=9884,'levetiracetam tb24'
  title=f'Levetiracetam {strength} mg 24-hour extended-release oral tablet'
  label='3e32f341-9926-47a3-a942-d8b9bfa7a55b'
  note='Swallow the extended-release tablet whole. Do not crush or chew.'
 else:
  number,printed=9883,'levetiracetam tabs'
  title=('Roweepra (levetiracetam)' if rx=='1731020' else 'Levetiracetam')+f' {strength} mg immediate-release oral tablet'
  label='e662bf5b-c81c-4bcd-ba2e-552df95ca6f9' if rx=='1731020' else '1d71212b-ac97-4a61-8192-8e8303540019'
  note=''
 ref=statewide_option(sources,number,'Preference, PA, ST and QL blank.')
 assert ref['sourcePage']==8 and ref['preferred']==ref['pa']==ref['step']=='not_specified' and not ref['qlAmount'] and not ref['qlDays']
 display={'label':title,'prescribingHeading':title,'separate':True,'identityRxcui':int(rx),'note':note,
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label}
 if rx=='1731020':
  assert 'ROWEEPRA' in ref['brand'].upper() and '[Roweepra]' in name
  return [ref],display
 return [april_formulary(printed,15,'F'),ref],display

ACH_DIAZEPAM_ORAL={
 '197589':('10',9768), '197590':('2',9769), '197591':('5',9770),
 '309844':('5',9766), '309843':('1',9767),
}
ACH_LACOSAMIDE={'993856':10,'809987':100,'809992':150,'809996':200,'810000':50}

def diazepam_oral(rx,name,sources):
 strength,number=ACH_DIAZEPAM_ORAL[rx]
 liquid=rx in ('309843','309844')
 unit='mL' if liquid else 'tablets'
 age='Up to 6 yrs old' if liquid else 'At least 6 yrs old'
 daily=2 if rx=='309844' else 10 if liquid else 4
 printed='diazepam conc' if rx=='309844' else 'diazepam soln or 5 mg/5ml' if liquid else 'diazepam tabs'
 raw='F; QL('+str(daily)+(' ml daily; 60 ml per 30 days retail' if rx=='309844' else ' ml daily' if liquid else ' ea daily')+'); AL('+age+')'
 dated=april_formulary(printed,12,raw,quantityLimited=True,qlAmount=f'{daily} {unit}',qlDays='1',ageLimited=True,ageRestrictionText=age)
 ref=statewide_option(sources,number,'Preference and ST blank.')
 assert ref['sourcePage']==5 and ref['pa']=='conditional' and 'Ages < 6 years' in ref['paText'] and '> 1 Anxiolytic' in ref['paText']
 assert ref['qlAmount']==str(daily*30) and ref['qlDays']=='30'
 ref['rawBenefit']+=f" | {ref['paText']} | QL {ref['qlAmount']}, days 30, unit blank."
 if rx=='309844':
  heading='Diazepam 5 mg/mL concentrate for oral solution'
  label='1aaf9375-ae3d-4fed-9cd1-24102e00be1a';product='diazepam conc'
 elif liquid:
  heading='Diazepam 5 mg/5 mL oral solution (1 mg/mL)'
  label='167ee280-be68-4a28-a7d8-de41df14bc48';product='diazepam oral soln'
 else:
  heading=f'Diazepam {strength} mg oral tablet'
  label='8b51f4b3-a5e8-4400-b624-ac0c47630c86';product='generic diazepam tabs'
 assert 'diazepam' in name.lower() and ('oral' in name.lower())
 display={'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,
          'scopedStatePa':'PA if age <6 or >1 anxiolytic in 30 days','planAgeBadge':'Age up to 6 years' if liquid else 'Age ≥6 years',
          'scopedMonthlyLabel':f"QL: {ref['qlAmount']} {unit} per 30 days",'anxiolyticPolicyProduct':product,
          'note':'Boxed warnings for concomitant opioid use, abuse, misuse, addiction, dependence and withdrawal.'}
 if rx=='309844':display['planDailyAndRetailLabel']='QL: 2 mL per day and 60 mL per 30 days at retail'
 return [dated,ref],display

ACH_RUFINAMIDE={'824295':'200 mg oral tablet','824301':'400 mg oral tablet','1092357':'40 mg/mL oral suspension'}

def rufinamide_option(rx,name,sources):
 liquid=rx=='1092357'
 assert name=='rufinamide '+('40 MG/ML Oral Suspension' if liquid else ACH_RUFINAMIDE[rx].upper().replace('ORAL TABLET','Oral Tablet'))
 heading='Rufinamide '+ACH_RUFINAMIDE[rx]
 dated=april_formulary('rufinamide '+('susp' if liquid else 'tabs'),15,'F; SP; PA',pa='required',paText='The Arizona Complete Health formulary lists PA.')
 ref=statewide_option(sources,9891 if liquid else 9892,'PA REQUIRED | Preference, ST and QL blank.')
 assert ref['sourcePage']==8 and ref['pa']=='required' and not ref['qlAmount'] and not ref['qlDays']
 policy='https://www.azcompletehealth.com/content/dam/centene/policies/pharmacy-policies/pmn/CP.PMN.157.pdf'
 refs=[['Centene Medicaid · CP.PMN.157 · reviewed August 2026 · initial request',policy+'#page=1'],
       ['Centene Medicaid · CP.PMN.157 · continued therapy',policy+'#page=2']]
 if not liquid:refs.append(['AHCCCS Statewide · Fee-for-service · generic tablet request','./sources/ahcccs-ffs-pa-criteria-2026-11-01.pdf#page=114'])
 spl='e2ba061a-49f0-4330-b0f0-00f2c3725625' if liquid else 'afe24968-e078-46d6-a776-b2608734e03e'
 return [dated,ref],{'label':heading,'separate':True,'prescribingHeading':heading,'identityRxcui':int(rx),
    'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+spl,'sourceReferences':refs,
    'rufinamideRequest':'suspension' if liquid else 'tablet','note':'Arizona Complete Health lists PA. The controlling ACC approval and renewal criteria are unverified.'}

def lacosamide_option(rx,name,sources):
 liquid=rx=='993856'
 strength=ACH_LACOSAMIDE[rx]
 assert name.startswith('lacosamide') and str(strength) in name and ('Oral Solution' if liquid else 'Oral Tablet') in name
 printed='lacosamide soln or 10 mg/ml' if liquid else 'lacosamide tabs'
 dated=april_formulary(printed,15,'F; PA',pa='required',paText='The Arizona Complete Health formulary lists PA.')
 ref=statewide_option(sources,9876 if liquid else 9877,'PA REQUIRED | Preference, ST and QL blank.')
 assert ref['sourcePage']==8 and ref['pa']=='required' and not ref['qlAmount'] and not ref['qlDays']
 heading='Lacosamide 10 mg/mL oral solution' if liquid else f'Lacosamide {strength} mg immediate-release oral tablet'
 label='e265fd09-8149-4423-a317-5760d34b8e9b' if liquid else 'c5b91128-f838-4e98-9684-5f477fc7af06'
 return [dated,ref],{'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
    'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,'lacosamideReference':True,
    'sourceReferences':[['AHCCCS Statewide · Fee-for-service · seizure diagnoses','./sources/ahcccs-ffs-pa-criteria-2026-11-01.pdf#page=108'],['AHCCCS Statewide · Fee-for-service · continuation','./sources/ahcccs-ffs-pa-criteria-2026-11-01.pdf#page=109']],
    'note':'The exact Arizona Complete Health generic lacosamide approval criteria are unverified.'}

def anxiolytic_option(rx,name,sources):
 family,strength,number,daily=ACH_ANXIOLYTIC_OPTIONS[rx]
 liquid=rx=='311376'
 capsule=family=='Oxazepam'
 unit='mL' if liquid else 'capsules' if capsule else 'tablets'
 if liquid:
  printed='lorazepam conc'
  heading='Lorazepam 2 mg/mL concentrate for oral solution'
  label='73bfaeab-94db-48c2-a194-8b173025de78'
 elif capsule:
  printed='oxazepam caps'
  heading=f'Oxazepam {strength} mg oral capsule'
  label='bb6d9142-3647-4591-8f84-31b61b755634'
 else:
  if family=='Lorazepam':
   printed='lorazepam tabs '+('2 mg' if rx=='197902' else '.5 mg, 1 mg')
   label='6b0619c5-b9e9-47e7-97b5-7e581e67cf5f'
  else:
   printed='clorazepate dipotassium tabs '+('15 mg' if strength=='15' else '3.75 mg, 7.5 mg')
   label='11b72861-64c9-4cdc-9289-c7fa9ea23bf6'
  heading=f'{family} {strength} mg oral tablet'
 assert family.lower() in name
 raw='F; '+('Limit 1 anxiolytic per 30 days; ' if rx=='197902' else '')
 raw+=f"QL({daily} {'ml' if liquid else 'ea'} daily"+('; 60 ea per 30 days retail' if capsule else '')+'); AL(At least 6 yrs old)'
 dated=april_formulary(printed,12,raw,quantityLimited=True,qlAmount=f'{daily} {unit}',qlDays='1',
                       ageLimited=True,ageRestrictionText='At least 6 yrs old')
 ref=statewide_option(sources,number,'Preference and ST blank.')
 assert ref['sourcePage']==(6 if number==9777 else 5) and ref['pa']=='conditional'
 assert 'Ages < 6 years' in ref['paText'] and '> 1 Anxiolytic' in ref['paText']
 assert ref['qlAmount']==str(daily*30) and ref['qlDays']=='30'
 ref['rawBenefit']+=f" | {ref['paText']} | QL {ref['qlAmount']}, days 30, unit blank."
 note='Boxed warnings for concomitant opioid use, abuse, misuse, addiction, dependence and withdrawal.'
 if rx=='197902':
  note+=' The Arizona Complete Health formulary also lists a limit of one anxiolytic per 30 days.'
 display={'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,
          'scopedStatePa':'PA if age <6 or >1 anxiolytic in 30 days','planAgeBadge':'Age ≥6 years',
          'scopedMonthlyLabel':f"QL: {ref['qlAmount']} {unit} per 30 days",'note':note,
          'anxiolyticPolicyProduct':'lorazepam conc' if liquid else 'generic '+family.lower()}
 if capsule:
  display['planDailyAndRetailLabel']='QL: 2 capsules per day and 60 capsules per 30 days at retail'
 return [dated,ref],display

ACH_DULERA = {'1246310':(100,120),'1660934':(100,60),'1246313':(200,120),'1660938':(200,60),'2196592':(50,120)}
ACH_MIRTAZAPINE = {'283406','311725','283407','314111','283485','311726','476809'}

ACH_SPIRIVA_SPRAYS={'1667882':('1.25',60),'2166204':('2.5',10),'1552004':('2.5',60)}

def spiriva_spray(rx,name,sources):
 strength,count=ACH_SPIRIVA_SPRAYS[rx]
 assert name.startswith(f'{count} ACTUAT ') and name.endswith('Inhalation Spray [Spiriva]')
 ref=statewide_option(sources,9798,'SPIRIVA RESPIMAT | PREFERRED DRUG | PA, ST and QL blank.')
 assert ref['sourcePage']==6 and ref['preferred']=='preferred' and not ref['qlAmount']
 notice=sources['ach-notice-13840']
 assert notice['name']=='SPIRIVA RESPIMAT (INHALATION)' and notice['preferred']=='preferred'
 heading=f'Spiriva Respimat {strength} mcg per actuation metered inhalation spray, {count} actuations'
 display={'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=7b656b14-fcaa-2741-f6f0-e0be48971c02'}
 if count==10:
  display['note']='The 10-actuation presentation is labeled for institutional use.'
 updates=[ref]
 if strength=='2.5':
  updates.append({**notice,'rawBenefit':'Preferred column: SPIRIVA RESPIMAT (INHALATION), COPD Agents, Antimuscarinics – Long-Acting.'})
 return updates,display

def dulera_option(rx,name,sources):
 strength,count=ACH_DULERA[rx]
 assert name.startswith(f'{count} ACTUAT ') and name.endswith('Metered Dose Inhaler [Dulera]')
 ref=statewide_option(sources,9823,'BRAND ONLY | PREFERRED DRUG | PA and ST blank | QL 6 per 90 days, unit blank.')
 assert ref['sourcePage']==7 and ref['qlAmount']=='6' and ref['qlDays']=='90' and ref['preferred']=='preferred'
 heading=f'Dulera {strength}/5 mcg per actuation metered-dose inhaler, {count} actuations'
 display={'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=8f399784-f257-4f31-b3dc-368bf2a1864d',
          'scopedMonthlyLabel':'QL: 6 per 90 days (unit unspecified)',
          'note':'The 60-actuation canister is labeled for institutional use.' if count==60 else 'Labeled 120-actuation canister.'}
 return [april_formulary('DULERA',13,'F'),ref],display

def mirtazapine_option(rx,name,sources):
 odt='Disintegrating' in name
 strength=re.fullmatch(r'mirtazapine ([\d.]+) MG (?:Disintegrating )?Oral Tablet',name)[1]
 ref=statewide_option(sources,9916 if odt else 9915,'PA REQUIRED for Ages < 6 years of age | QL 30, days 30, unit blank | preference and ST blank.')
 assert ref['qlAmount']=='30' and ref['qlDays']=='30' and ref['pa']=='conditional' and ref['sourcePage']==8
 printed='mirtazapine tbdp' if odt else 'mirtazapine tabs '+('7.5 mg' if strength=='7.5' else '15 mg, 30 mg, 45 mg')
 age=strength!='7.5'
 dated=april_formulary(printed,15,'F; QL(1 ea daily); '+('AL(At least 6 yrs old); ' if age else '')+'MP',
                       quantityLimited=True,qlAmount='1 tablet',qlDays='1')
 if age:
  dated.update(ageLimited=True,ageRestrictionText='At least 6 yrs old')
 heading=f'Mirtazapine {strength} mg '+('orally disintegrating tablet' if odt else 'oral tablet')
 display={'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+('5127517f-b8d0-4af1-8a2f-5225719600bc' if odt else 'b4b9b66e-87a1-4dbb-9eaf-71221bcb2265'),
          'scopedMonthlyLabel':'QL: 30 tablets per 30 days','scopedStatePa':'PA if age <6',
          'pediatricAntidepressantProduct':'generic mirtazapine tabs/ODT','note':'Boxed warning for suicidal thoughts and behaviors in pediatric and young adult patients.'}
 if age:
  display['planAgeBadge']='Age ≥6 years'
 return [dated,ref],display

ACH_BUPROPION = {'993503':('SR',100),'993687':('IR',100),'993518':('SR',150),'993541':('XL',150),
                 '1801289':('cessation',150),'993536':('SR',200),'993557':('XL',300),'993691':('IR',75)}

def bupropion_option(rx,name,sources):
 form,strength=ACH_BUPROPION[rx]
 smoking=form=='cessation'
 assert ('Smoking Cessation' in name)==smoking and f'{strength} MG ' in name
 assert ('12 HR' in name)==(form in ('SR','cessation')) and ('24 HR' in name)==(form=='XL')
 number,limit,form_label,label={
  'IR':(9919,4,'immediate-release oral tablet','9a3b97be-afa3-49e6-962f-662b6807e607'),
  'SR':(9920,2,'12-hour sustained-release oral tablet','093c4a61-02d9-4b55-b612-569aa25d3f2a'),
  'XL':(9921,1,'24-hour extended-release oral tablet','b2e6c30f-a33c-4854-ab19-bc9f65880374'),
  'cessation':(10962,2,'12-hour sustained-release oral tablet for smoking cessation','a591e33a-52f0-41c8-a00b-4a1afcc3dc4c')
 }[form]
 heading=f'Bupropion hydrochloride {strength} mg {form_label}'
 display={'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
          'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,
          'note':'Boxed warning for suicidal thoughts and behaviors in children, adolescents and young adults.'}
 printed={'IR':'bupropion hcl tabs','SR':'bupropion hcl tb12','XL':'bupropion hcl tb24 150 mg, 300 mg','cessation':'bupropion hcl (smoking deterrent)'}[form]
 raw='F; '+('84 rtl MAX day(s) supply; 180 rtl lmt day(s); ' if smoking else '')+f'QL({limit} ea daily)'+('' if smoking else '; AL(At least 6 yrs old); MP')
 dated=april_formulary(printed,72 if smoking else 15,raw,quantityLimited=True,qlAmount=f"{limit} tablet"+('s' if limit!=1 else ''),qlDays='1')
 ref=statewide_option(sources,number,'Preference and ST blank.')
 if smoking:
  assert ref['pa']=='not_specified' and ref['qlAmount']=='84-day supply' and ref['qlDays']=='180'
  ref['rawBenefit']+=' | PA blank; 84-day supply per 180 days.'
  display['scopedMonthlyLabel']='QL: 84-day supply per 180 days'
  display['planDailyAndRetailLabel']='QL: 2 tablets per day and 84-day supply per 180 days at retail'
  display['policyUnverified']=True
 else:
  assert ref['pa']=='conditional' and ref['sourcePage']==9 and ref['qlAmount']==str(limit*30) and ref['qlDays']=='30'
  ref['rawBenefit']+=f" | {ref['paText']} | QL {ref['qlAmount']}, days 30, unit blank."
  dated.update(ageLimited=True,ageRestrictionText='At least 6 yrs old')
  display.update(planAgeBadge='Age ≥6 years',scopedStatePa='PA if age <6',scopedMonthlyLabel=f"QL: {ref['qlAmount']} tablets per 30 days",
                 pediatricAntidepressantProduct='bupropion tabs/SR tabs/XL tabs (150 and 300mg)')
 return [dated,ref],display

ACH_TWISTHALER = {'790284':(110,30),'746804':(220,120),'746811':(220,14),'746813':(220,30),'746815':(220,60)}
ACH_SALMETEROL_POLICY = ('https://www.azcompletehealth.com/content/dam/centene/az-complete-health/policies/'
                         'pharm_pol/508_AZ.CP.PMN.1022.pdf')

def respiratory_powder(rx,name,sources):
 serevent=rx=='866049'
 if serevent:
  assert name=='60 ACTUAT salmeterol 0.05 MG/ACTUAT Dry Powder Inhaler [Serevent]'
  heading='Serevent Diskus 50 mcg per inhalation dry powder inhaler, 60 blisters'
  dated=april_formulary('SEREVENT DISKUS',13,'F; PA',pa='required',paText='The Arizona Complete Health formulary lists PA.')
  ref=statewide_option(sources,9826,'PREFERRED DRUG | PA REQUIRED | ST and QL blank.')
  assert ref['sourcePage']==7 and ref['pa']=='required'
  label='12d9728e-6b5c-4aee-bfb0-745e542ed2e4'
  note='For asthma, concurrent inhaled corticosteroid treatment is required. Contraindicated in severe milk protein hypersensitivity. The current applicability of the January 2020 Arizona Complete Health policy is unverified.'
  references=[['Arizona Complete Health · AZ.CP.PMN.1022 · January 2020 · initial asthma or COPD',ACH_SALMETEROL_POLICY+'#page=1'],
              ['Arizona Complete Health · AZ.CP.PMN.1022 · January 2020 · continued therapy',ACH_SALMETEROL_POLICY+'#page=2']]
  guide='gl-99495-serevent'
  pages=[('asthma',1574),('exercise-induced bronchospasm',1575),('COPD bronchospasm',1576)]
 else:
  strength,count=ACH_TWISTHALER[rx]
  assert name.startswith(f'{count} ACTUAT ') and name.endswith('Dry Powder Inhaler [Asmanex]')
  heading=f'Asmanex Twisthaler {strength} mcg per metered dose, dry powder inhaler, {count} doses'
  dated=april_formulary(f'ASMANEX TWISTHALER {count} METERED DOSES AEPB',13,'F')
  ref=statewide_option(sources,9811,'BRAND ONLY | PREFERRED DRUG | PA, ST and QL blank.')
  assert ref['sourcePage']==6 and ref['preferred']=='preferred' and not ref['qlAmount']
  label='10b36fb2-6b0d-4f20-b197-3564d6f594b9'
  note=f'The mouthpiece delivers {100 if strength==110 else 200} mcg per actuation. Contraindicated in known milk protein hypersensitivity.'
  if count==14:
   note+=' The 14-dose inhaler is labeled for institutional use.'
  references=[]
  guide='gl-589212-asmanex'
  pages=[('preferred Asmanex asthma request',968)]
 ffs='./sources/ahcccs-ffs-pa-criteria-2026-11-01.pdf'
 references.extend([['AHCCCS Statewide · Fee-for-service · '+indication,ffs+'#page='+str(page)] for indication,page in pages])
 return [dated,ref],{'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),
                    'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,
                    'note':note,'sourceReferences':references,'respiratoryGuideId':guide}

SEIZURE_RESCUE_KITS={'2272622':(10,1),'2272636':(15,2),'2272624':(20,2),'2272630':(5,1)}

def seizure_nasal_presentation(rx):
 nayzilam=rx=='2173500'
 brand='Nayzilam' if nayzilam else 'Valtoco'
 if nayzilam:
  heading='Nayzilam 5 mg/0.1 mL single-dose nasal spray'
  note='Each device delivers one spray. The carton contains two devices.'
  label='2b29422e-54d5-4a49-8522-e9cf752368c3'
 else:
  dose,devices=SEIZURE_RESCUE_KITS[rx]
  per_device=f'{dose/devices:g}'
  heading=f'Valtoco {dose} mg dose kit — {devices} single-use nasal '+('spray' if devices==1 else 'sprays')+f' ({per_device} mg/0.1 mL each)'
  note=('One spray delivers the dose.' if devices==1 else 'One dose uses two devices, one spray in each nostril.')+' The label lists two-dose and five-dose cartons.'
  label='1a8bcc90-68fa-474d-832c-0df01e825f39'
 return {'prescribingHeading':heading,'label':heading,'separate':True,'identityRxcui':int(rx),'nasalRescueProduct':brand,
         'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label,'note':note}

def ach_seizure_rescue(rx,name,sources):
 if rx in ('801961','801966'):
  size=10 if rx=='801961' else 20
  assert 'Rectal Gel' in name and '5 MG/ML' in name
  ref=statewide_option(sources,9861,'GENERIC ONLY | preference, PA, ST blank | QL 2 per 30 days, unit blank.')
  disp={'prescribingHeading':f'Diazepam {size} mg adjustable rectal gel delivery system (5 mg/mL)',
        'identityRxcui':int(rx),'separate':True,'scopedMonthlyLabel':'QL: 2 per 30 days (unit unspecified)',
        'planRetailLimit':{'amount':'2','days':'30'},
        'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=652714c7-25c4-4d05-979d-8eee3b6f2f4d',
        'note':('Selectable doses: 5, 7.5 or 10 mg.' if size==10 else 'Selectable doses: 12.5, 15, 17.5 or 20 mg.')+' The retail limit is printed as 2 each per 30 days. The payer does not distinguish syringes from cartons.'}
  disp['label']=disp['prescribingHeading']
  dated=april_formulary('diazepam (anticonvulsant) gel'+(' 2.5 mg, 20 mg' if size==20 else ''),14,
       'F; QL(2 ea per 30 days retail)',quantityLimited=True,qlAmount='2',qlDays='30')
  return [dated,ref],disp
 disp=seizure_nasal_presentation(rx)
 assert disp['nasalRescueProduct'] in name
 ref=statewide_option(sources,9864 if rx=='2173500' else 9863,'Preference, PA and ST blank; QL amount and days printed without a dispensing unit.')
 assert ref['sourcePage']==8 and ref['qlDays']=='30' and ref['qlAmount']==('4' if rx=='2173500' else '2')
 ref['rawBenefit']+=f" {ref['qlAmount']} per 30 days."
 disp['scopedMonthlyLabel']=f"QL: {ref['qlAmount']} per 30 days (unit unspecified)"
 return [ref],disp

def with_ach_baseline(d):
 src=ROOT/'dist/sources/ach/integrated-formulary-baseline.json.gz'
 raw=json.loads(gzip.decompress(src.read_bytes())); assert len(raw)==4454
 prior_baselines=sum(r.get('validation')=='official_json_baseline_with_later_updates' for r in d['medications'])
 correct_source_restrictions(d['medications'])
 correct_source_conflicts(d['medications'])
 current=[r for r in d['medications'] if r['planId']=='az-complete-health' and r.get('validation')!='official_json_baseline_with_later_updates']
 statewide_sources={r['id']:r for r in d['medications'] if r['planId']=='ahcccs-statewide'}
 indexed_sources={r['id']:r for r in current}
 result=[];counts=collections.Counter()
 for index,row in enumerate(raw):
  assert len(row['plans'])==1
  p=row['plans'][0]; name=row['drug_name'];brand=re.search(r'\[([^]]+)\]',name);brand=brand.group(1) if brand else ''
  generic=re.sub(r'\[[^]]+\]','',name); nt=tokens(generic)
  candidates=[];held_pa=[]
  pack_reference = STARTER_PACK_REFERENCES.get(row['rxnorm_id'])
  pack_update = None
  for r in current:
   if pack_reference and r.get('validation') == 'mandated_statewide_minimum_with_plan_adoption_evidence':
    if r['id'] == 'ach-mandated-' + pack_reference:
     pack_update = r
    continue
   rn=r['name']; rb=r.get('brand','')
   if '(AG)' in rn or 'AUTHORIZED' in rn.upper():continue
   branded=bool(brand and tokens(brand) and tokens(brand) <= tokens(rn))
   ingredient=nt==tokens(rn) and bool(nt)
   if not (branded or ingredient):continue
   if not compatible(name,rn):continue
   strengths=re.findall(r'\d+(?:\.\d+)?\s*(?:mg|mcg)(?:\s*/\s*ml)?',rn,re.I)
   compact=lambda s:re.sub(r'\s+','',s.lower())
   if strengths:
    # A one-ingredient strength list contains alternatives, not a requirement
    # that one RxNorm product contain every listed strength simultaneously.
    alternative_strengths=len(tokens(rn))==1 and bool(re.search(r'[,;&]',rn))
    strength_match=any if alternative_strengths else all
    if not strength_match(compact(v) in compact(name) for v in strengths):continue
   if brand and not explicit_brand_match(brand,r):
    if ingredient and rb.strip().lower() in ('','various') and r.get('pa') in ('required','conditional'):
     held_pa.append({k:r.get(k) for k in ['id','name','brand','sourceUrl','sourceEffective','sourcePage','pa','paText']})
    continue
   if not brand and re.search(r'brand\s*only',r.get('brandGenericNotes','')+' '+r.get('notes',''),re.I):continue
   candidates.append((branded,r))
  if any(b for b,r in candidates):candidates=[(b,r) for b,r in candidates if b]
  candidates=[r for b,r in candidates]
  if row['rxnorm_id'] in NALOXONE_SOURCES:
   candidates=naloxone_updates(row['rxnorm_id'],indexed_sources,statewide_sources)
  if row['rxnorm_id'] in ACH_OCT_NOTICE_MATCH:
   notice_id, printed_name = ACH_OCT_NOTICE_MATCH[row['rxnorm_id']]
   notice = next(r for r in current if r['id'] == notice_id)
   assert notice['name'] == printed_name and notice['sourceUrl'] == ACH_OCT_NOTICE_URL
   if all(r['id'] != notice_id for r in candidates):
    candidates.append(notice)
  if row['rxnorm_id'] in {'847910', '847915'}:
   assert not brand and '60 ACTUAT exenatide' in name and 'Pen Injector' in name
   candidates.append({'name':'EXENATIDE PEN (SUBCU SUBCUTANEOUS)*', 'sourceTitle':'Arizona Complete Health Complete Care PU26135, GLP-1 table',
                      'sourceUrl':ACH_OCT_NOTICE_URL, 'sourceEffective':'2026-10-01', 'coverage':'listed',
                      'preferred':'non_preferred', 'pa':'required', 'paText':'The notice directs nonpreferred drugs through the PA process.',
                      'rawBenefit':'Nonpreferred column. Continuation of nonformulary medication: No. Route confirmed by the AHCCCS June 8 contractor memo, p. 8.'})
  if row['rxnorm_id'] == '2705588':
   assert '[Yesintek]' in name and '26 ML' in name and '5 MG/ML' in name
   candidates.append({'name':'YESINTEK VIAL (INTRAVENOUS)', 'sourceTitle':'AHCCCS Statewide June 8, 2026 contractor memo',
                      'validation':'mandated_statewide_minimum_with_plan_adoption_evidence', 'sourceUrl':AHCCCS_MAY_MEMO,
                      'sourcePage':6, 'sourceEffective':'2026-10-01', 'preferred':'non_preferred',
                      'rawBenefit':'Cytokine and CAM antagonists: products moving to nonpreferred. The ACH October notice repeats the subcutaneous vial.'})
  if row['rxnorm_id'] in {'2535249', '2535243'}:
   # Both named devices are preferred, but each has its own statewide quantity.
   is_pen = row['rxnorm_id'] == '2535249'
   notice_id = 'ach-notice-13882' if is_pen else 'ach-notice-13883'
   state_id = 'ach-mandated-formulary-9963' if is_pen else 'ach-mandated-formulary-9964'
   notice = next(r for r in current if r['id'] == notice_id)
   reference = next(r for r in current if r['id'] == state_id)
   assert ('AUTOINJECTOR' if is_pen else 'SYRINGE') in notice['name'] and brand == 'Zegalogue'
   assert reference['brand'] == 'ZEGALOGUE' and notice['preferred'] == 'preferred'
   candidates = [notice, {**reference, **reference['statewideReference'],
                           'rawBenefit': 'Brand only; preferred; PA and ST blank; dispensing unit unspecified.'}]
  if row['rxnorm_id'] in {'349094', '351109', '252559'}:
   # The baseline expresses concentration; the state prints total dose in each 2 mL ampule.
   assert 'Inhalation Suspension' in name
   suspension = next(r for r in current if r['id'] == 'ach-mandated-formulary-9805')
   assert 'SUSPENSION 0.25MG, 0.50MG & 1.0MG' in suspension['name']
   candidates = [r for r in candidates if r['id'] not in {'ach-mandated-formulary-9805', 'ach-mandated-formulary-9806'}]
   candidates.extend([suspension, {'name':'budesonide (inhalation) susp', 'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL',
                                   'sourceEffective':'2023-04-01','sourceUrl':ACH_APR_2023_PDL,'sourcePage':13,
                                   'sourceKind':'plan_formulary','coverage':'listed','rawBenefit':'F; restriction fields blank.'}])
  oral_display=None
  if row["rxnorm_id"] in ACH_ISENTRESS or row["rxnorm_id"] in LAMOTRIGINE_OPTIONS:
   candidates,oral_display=verified_oral_form(row["rxnorm_id"],name,indexed_sources)
  if row['rxnorm_id'] in ACH_ANTIPSYCHOTIC_OPTIONS:
   candidates,oral_display=antipsychotic_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in {'1797113','310169','884707','1597076'}:
   candidates,oral_display=hormone_identity(row['rxnorm_id'],indexed_sources)
  if row['rxnorm_id'] in ACH_SPIRIVA_SPRAYS:
   candidates,oral_display=spiriva_spray(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_BUPROPION:
   candidates,oral_display=bupropion_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in SEIZURE_RESCUE_KITS or row['rxnorm_id'] in ('2173500','801961','801966'):
   candidates,oral_display=ach_seizure_rescue(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id']=='866049' or row['rxnorm_id'] in ACH_TWISTHALER:
   candidates,oral_display=respiratory_powder(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_DULERA:
   candidates,oral_display=dulera_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_MIRTAZAPINE:
   candidates,oral_display=mirtazapine_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_EMERGENCY_CONTRACEPTION:
   candidates,oral_display=emergency_tablet(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_LEVETIRACETAM:
   candidates,oral_display=levetiracetam_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_SEIZURE_FORMS:
   candidates,oral_display=seizure_form_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_DIAZEPAM_ORAL:
   candidates,oral_display=diazepam_oral(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_RUFINAMIDE:
   candidates,oral_display=rufinamide_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_LACOSAMIDE:
   candidates,oral_display=lacosamide_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_ANXIOLYTIC_OPTIONS:
   candidates,oral_display=anxiolytic_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_ANTICONVULSANT_FORMS:
   candidates,oral_display=anticonvulsant_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_BRAND_ANTICOAGULANTS:
   candidates,oral_display=brand_anticoagulant(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_RESPIRATORY_DEVICES:
   candidates,oral_display=respiratory_device(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_ENOXAPARIN:
   candidates,oral_display=enoxaparin_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_MONTELUKAST:
   candidates,oral_display=montelukast_option(row['rxnorm_id'],indexed_sources)
  if row['rxnorm_id'] in ACH_OUD_COMBINATIONS:
   candidates,oral_display=oud_combination_updates(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in {'351264','351265'}:
   dose,limit=('2',16) if row['rxnorm_id']=='351264' else ('8',4)
   assert name==f'buprenorphine {dose} MG Sublingual Tablet'
   ref=indexed_sources['ach-mandated-formulary-9698']
   assert ref['pa']=='conditional' and 'pregnant or nursing' in ref['paText']
   candidates=[ref,{'name':f'buprenorphine hcl subl {dose} mg','sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL',
                    'sourceUrl':ACH_APR_2023_PDL,'sourceEffective':'2023-04-01','sourcePage':10,'sourceKind':'plan_formulary',
                    'coverage':'listed','quantityLimited':True,'qlAmount':f'{limit} tablets','qlDays':'1','pa':'conditional',
                    'paText':'PA required unless pregnant or nursing. The plan requires the specified diagnosis code on the prescription.',
                    'rawBenefit':f"F; PA Req’d unless member is pregnant or nursing; Prescriber must note ICD-10 diagnosis code on prescription.; O09.91; O09.92; O09.93; QL({limit} ea daily)."},
                   {'name':'BUPRENORPHINE HCL (SUBLINGUAL)*','sourceTitle':'Arizona Complete Health October 2026 Medicaid formulary update PU26135',
                    'sourceUrl':ACH_OCT_NOTICE_URL,'sourceEffective':'2026-10-01','coverage':'listed','preferred':'preferred',
                    'rawBenefit':'Table 1 data row 17, preferred column. The asterisk identifies statewide listing.'}]
   oral_display={'prescribingHeading':f'Buprenorphine {dose} mg sublingual tablet','identityRxcui':int(row['rxnorm_id']),
                 'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1408cd8f-a0b5-6be7-e063-6394a90a0b41',
                 'planConditionalLabel':'PA unless pregnant or nursing',
                 'sourceReferences':[['AHCCCS Statewide · June 8 contractor memo · p. 9',AHCCCS_MAY_MEMO+'#page=9']]}
  if row['rxnorm_id'] in ACH_TRULICITY_PENS or row['rxnorm_id'] in ACH_XOLAIR_DEVICES:
   candidates,oral_display=injectable_notice_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id'] in ACH_CLONAZEPAM:
   candidates,oral_display=clonazepam_option(row['rxnorm_id'],name,indexed_sources)
  if row['rxnorm_id']=='199387':
   assert name=='risperidone 1 MG/ML Oral Solution'
   state=indexed_sources['ach-mandated-formulary-10219']
   ref={**state,**state['statewideReference']}
   assert ref['qlAmount']=='240' and ref['qlDays']=='30' and ref['sourcePage']==16
   ref['rawBenefit']='RISPERIDONE ORAL SOLUTION | RISPERDAL | PREFERRED DRUG | 240 per 30 days, unit blank.'
   dated={'name':'risperidone soln','sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL',
          'sourceUrl':ACH_APR_2023_PDL,'sourceEffective':'2023-04-01','sourcePage':25,'sourceKind':'plan_formulary',
          'coverage':'listed','quantityLimited':True,'qlAmount':'8 mL','qlDays':'1','ageLimited':True,
          'ageRestrictionText':'At least 6 yrs old','rawBenefit':'F; QL(8 ml daily; 240 ml per 30 days retail); AL(At least 6 yrs old).'}
   candidates=[dated,indexed_sources['ach-notice-13827'],ref]
   oral_display={'prescribingHeading':'Risperidone 1 mg/mL oral solution','identityRxcui':199387,'statewideAge':6,
                 'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=3cc027f0-3462-4a2f-925b-d8a529bcb3c3',
                 'scopedMonthlyLabel':'QL: 240 mL per 30 days','planDailyAndRetailLabel':'QL: 8 mL per day and 240 mL per 30 days at retail',
                 'note':'AHCCCS Statewide requires PA below age 6. At age 6 and older, PA is waived for a psychiatric clinician, developmental pediatrician or other MCO-approved prescriber.'}
  if pack_update and not any(r.get('id')==pack_update['id'] for r in candidates):
   candidates.append(pack_update)
  if row['rxnorm_id'] in ACH_DAILY_INSULIN_LIMITS:
   printed,page = ACH_DAILY_INSULIN_LIMITS[row['rxnorm_id']]
   candidates.append({'name':printed, 'sourceTitle':'Arizona Complete Health February 2023 Complete Care PDL',
                      'sourceEffective':'2023-02-01','sourceUrl':ACH_FEB_2023_PDL,'sourcePage':page,
                      'quantityLimited':True,'qlAmount':'1 mL','qlDays':'1'})
  if row['rxnorm_id'] in {'727316', '1870207'}:
   assert name.startswith('NDA019430 0.3 ML epinephrine') and name.endswith('Auto-Injector')
   candidates.append({'name':'epinephrine (anaphylaxis) soaj', 'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL',
                      'sourceEffective':'2023-04-01', 'sourceUrl':ACH_APR_2023_PDL, 'sourcePage':78,
                      'sourceKind':'plan_formulary', 'quantityLimited':True, 'qlAmount':'0.067 each', 'qlDays':'1',
                      'rawBenefit':'F; QL(0.067 ea daily).'})
  if row['rxnorm_id'] in {'848330', '848333', '848343'}:
   assert brand in {'Estring','Femring'}
   ring_update = {'name':'ESTRING RING' if brand=='Estring' else 'FEMRING',
                  'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL', 'sourceEffective':'2023-04-01',
                  'sourceUrl':ACH_APR_2023_PDL, 'sourcePage':78, 'sourceKind':'plan_formulary',
                  'coverage':'listed', 'rawBenefit':'F' if brand=='Estring' else 'F; PA.'}
   if brand=='Femring':
    ring_update['pa']='required'
   candidates.append(ring_update)
  if row['rxnorm_id'] in {'835829', '2047882', '835840', '835809'}:
   ester = 'enanthate' if row['rxnorm_id'] == '835809' else 'cypionate'
   assert not brand and 'testosterone '+ester in name
   candidates.append({'name':'testosterone '+ester+' soln im', 'sourceTitle':'Arizona Complete Health April 2023 Complete Care PDL',
                      'sourceEffective':'2023-04-01', 'sourceUrl':ACH_APR_2023_PDL, 'sourcePage':10,
                      'sourceKind':'plan_formulary', 'coverage':'listed', 'pa':'required', 'rawBenefit':'F; PA.'})
  if row['rxnorm_id'] in {'835831', '835842'}:
   assert brand.lower()=='depo-testosterone' and 'testosterone cypionate' in name
   candidates.append({'name':'DEPO-TESTOSTERONE SOLN IM', 'sourceTitle':'Arizona Complete Health February 2023 Complete Care PDL',
                      'sourceEffective':'2023-02-01', 'sourceUrl':ACH_FEB_2023_PDL, 'sourcePage':13,
                      'sourceKind':'plan_formulary', 'coverage':'non_formulary', 'pa':'required',
                      'paText':'NF; PA. The plan defines NF as requiring authorization for coverage.'})
  candidates.sort(key=lambda r:r.get('sourceEffective',''))
  rec=dict(id='ach-json-'+row['rxnorm_id'],recordType='formulary',planId='az-complete-health',name=name,brand=brand,category='Other',subcategory='Integrated formulary',coverage='listed',listingLabel='Covered',preferred='preferred' if p.get('drug_tier')=='PREFERRED' else 'not_specified',pa='required' if p.get('prior_authorization') else ('not_required' if p.get('prior_authorization') is False else 'not_specified'),paText='The formulary lists prior authorization.' if p.get('prior_authorization') else '',step='specified' if p.get('step_therapy') else 'not_specified',stepText='The formulary requires step therapy but does not specify the steps.' if p.get('step_therapy') else '',quantityLimited=bool(p.get('quantity_limit')),qlAmount='',qlDays='',conditions=[],notes='',sourceTitle='Arizona Complete Health official integrated JSON baseline (declared plan year 2022)',sourceEffective='2022',sourceUrl='/sources/ach/integrated-formulary-baseline.json.gz',sourceRow=index+1,rxnormId=row['rxnorm_id'],validation='official_json_baseline_with_later_updates',baselineSource={'url':SOURCE,'declaredPlanYears':p['years'],'row':index+1,'values':p},sourceUpdates=[])
  if oral_display:
   rec['reviewedPresentation']=oral_display
  if pack_update:
   rec['verifiedStatewidePackId'] = pack_reference
  if row['rxnorm_id'] in {'349094', '351109', '252559'}:
   rec['excludedStatewidePolicyCode'] = 'GL-99451'
  for r in candidates:
   rec['category']=r.get('category') or rec['category'];rec['subcategory']=r.get('subcategory') or rec['subcategory']
   update={k:r.get(k) for k in ['id','name','sourceTitle','sourceUrl','sourceEffective','sourcePage','preferred','pa','paText','step','stepText','qlAmount','qlDays']}
   update['scope']='statewide_reference' if r.get('validation')=='mandated_statewide_minimum_with_plan_adoption_evidence' else 'selected_plan'
   if r.get('sourceKind'):
    update['sourceKind']=r['sourceKind']
   if r.get('rawBenefit'):
    update['rawBenefit']=r['rawBenefit']
   rec['sourceUpdates'].append(update)
  # Different indication headings specify different conditions. Retain both raw rows
  # in Sources and use an indication-qualified value for the single display field.
  if row['rxnorm_id'] in ACH_CLONAZEPAM:
   candidates=[{**r,'paText':oral_display['note']} if r.get('pa')=='conditional' else r for r in candidates]
  apply_benefit_updates(rec, candidates)
  if rec['coverage']=='non_formulary' and rec['benefitSources']['preferred']=='presumed_2022':
   rec['preferred']='not_specified'
   rec['benefitSources']['preferred']='selected_plan'
   rec['listingLabel']='Nonformulary'

  if rec['pa']=='not_required' and held_pa and not any(r.get('pa') in ('required','conditional','not_required') for r in candidates):
   rec['pa']='not_specified'
   rec['heldSourceUpdates']=held_pa
   rec['paUncertaintyReason']='Later generic-product PA evidence exists; its application to this named brand is not established.'
  counts['with_later_updates' if candidates else 'baseline_only']+=1
  result.append(rec)
 for r in current:
  if r.get('coverageCaveat')=='Additional plan products not fully published':r.pop('coverageCaveat')
  if r.get('validation')=='mandated_statewide_minimum_with_plan_adoption_evidence':
   r['sourceTitle']='AHCCCS drug list adopted as ACH minimum';r['notes']='Statewide minimum listing. Exact-plan product restrictions require separate verification.'
 d['medications']=[r for r in d['medications'] if r['planId']!='az-complete-health']+current+result
 for plan in d['plans']:
  if plan['id']=='az-complete-health':plan.update(status='baseline_plus_updates',detail='A complete current Arizona Complete Health formulary has not been verified.',effective='Arizona Complete Health formulary and updates')
 for e in d['planEvidence']:
  if e['planId']=='az-complete-health':e.update(topic='Arizona Complete Health formulary',evidence='Original product listings and benefit flags.',sourceUrl=SOURCE,sourceEffective='2022')
 d['meta']['achFormularyEvidenceRule']=SOURCE_SCOPE
 d['meta']['asOf']='2026-11-13'
 # Counts include lazy-loaded plan datasets as in the existing export.
 d['meta']['recordCount']+=len(result)-prior_baselines
 print(json.dumps(dict(imported=len(result),existingLaterEntries=len(current),**counts)))
 return d

if __name__=='__main__':
 path=ROOT/'dist/data.json.gz'
 data=with_ach_baseline(json.loads(gzip.decompress(path.read_bytes())))
 path.write_bytes(gzip.compress(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
