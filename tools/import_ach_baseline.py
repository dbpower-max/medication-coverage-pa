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

def with_ach_baseline(d):
 src=ROOT/'dist/sources/ach/integrated-formulary-baseline.json.gz'
 raw=json.loads(gzip.decompress(src.read_bytes())); assert len(raw)==4454
 prior_baselines=sum(r.get('validation')=='official_json_baseline_with_later_updates' for r in d['medications'])
 correct_source_restrictions(d['medications'])
 correct_source_conflicts(d['medications'])
 current=[r for r in d['medications'] if r['planId']=='az-complete-health' and r.get('validation')!='official_json_baseline_with_later_updates']
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
  if pack_update:
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
  if row['rxnorm_id'] in {'835831', '835842'}:
   assert brand.lower()=='depo-testosterone' and 'testosterone cypionate' in name
   candidates.append({'name':'DEPO-TESTOSTERONE SOLN IM', 'sourceTitle':'Arizona Complete Health February 2023 Complete Care PDL',
                      'sourceEffective':'2023-02-01', 'sourceUrl':ACH_FEB_2023_PDL, 'sourcePage':13,
                      'sourceKind':'plan_formulary', 'coverage':'non_formulary', 'pa':'required',
                      'paText':'NF; PA. The plan defines NF as requiring authorization for coverage.'})
  candidates.sort(key=lambda r:r.get('sourceEffective',''))
  rec=dict(id='ach-json-'+row['rxnorm_id'],recordType='formulary',planId='az-complete-health',name=name,brand=brand,category='Other',subcategory='Integrated formulary',coverage='listed',listingLabel='Covered',preferred='preferred' if p.get('drug_tier')=='PREFERRED' else 'not_specified',pa='required' if p.get('prior_authorization') else ('not_required' if p.get('prior_authorization') is False else 'not_specified'),paText='The formulary lists prior authorization.' if p.get('prior_authorization') else '',step='specified' if p.get('step_therapy') else 'not_specified',stepText='The formulary requires step therapy but does not specify the steps.' if p.get('step_therapy') else '',quantityLimited=bool(p.get('quantity_limit')),qlAmount='',qlDays='',conditions=[],notes='',sourceTitle='Arizona Complete Health official integrated JSON baseline (declared plan year 2022)',sourceEffective='2022',sourceUrl='/sources/ach/integrated-formulary-baseline.json.gz',sourceRow=index+1,rxnormId=row['rxnorm_id'],validation='official_json_baseline_with_later_updates',baselineSource={'url':SOURCE,'declaredPlanYears':p['years'],'row':index+1,'values':p},sourceUpdates=[])
  if pack_update:
   rec['verifiedStatewidePackId'] = pack_reference
  for r in candidates:
   rec['category']=r.get('category') or rec['category'];rec['subcategory']=r.get('subcategory') or rec['subcategory']
   update={k:r.get(k) for k in ['id','name','sourceTitle','sourceUrl','sourceEffective','sourcePage','preferred','pa','paText','step','stepText','qlAmount','qlDays']}
   update['scope']='statewide_reference' if r.get('validation')=='mandated_statewide_minimum_with_plan_adoption_evidence' else 'selected_plan'
   if r.get('sourceKind'):
    update['sourceKind']=r['sourceKind']
   if r.get('rawBenefit'):
    update['rawBenefit']=r['rawBenefit']
   rec['sourceUpdates'].append(update)
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
