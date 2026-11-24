"""Combine the historical 2022 Arizona Complete Health formulary with dated source evidence."""
import collections, copy, gzip, hashlib, json, re
from pathlib import Path
from functools import lru_cache
from source_restrictions import correct_source_restrictions, correct_source_conflicts
ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://www.azcompletehealth.com/content/dam/centene/az-complete-health/json/Drugs_FAB_CNCAZCH01_AZ_Medicaid_Integrated_Formulary_eff_9-1-22_07142026131014_AZ.json'
SOURCE_SCOPE='The 2022 integrated formulary is historical. Later Arizona Complete Health notices establish only their named changes. AHCCCS listings provide statewide reference evidence. A complete current exact-plan formulary remains unverified.'
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
  for r in current:
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
  candidates.sort(key=lambda r:r.get('sourceEffective',''))
  rec=dict(id='ach-json-'+row['rxnorm_id'],recordType='formulary',planId='az-complete-health',name=name,brand=brand,category='Other',subcategory='Integrated formulary',coverage='listed',listingLabel='Covered',preferred='preferred' if p['drug_tier']=='PREFERRED' else 'not_specified',pa='required' if p['prior_authorization'] else 'not_required',paText='Prior authorization required by the JSON baseline.' if p['prior_authorization'] else '',step='specified' if p['step_therapy'] else 'not_specified',stepText='Step therapy required; the JSON does not provide the steps.' if p['step_therapy'] else '',quantityLimited=bool(p['quantity_limit']),qlAmount='',qlDays='',conditions=[],notes=SOURCE_SCOPE,sourceTitle='Arizona Complete Health official integrated JSON baseline (declared plan year 2022)',sourceEffective='',sourceUrl='/sources/ach/integrated-formulary-baseline.json.gz',sourceRow=index+1,rxnormId=row['rxnorm_id'],validation='official_json_baseline_with_later_updates',baselineSource={'url':SOURCE,'declaredPlanYears':p['years'],'row':index+1,'values':p},sourceUpdates=[])
  for r in candidates:
   rec['category']=r.get('category') or rec['category'];rec['subcategory']=r.get('subcategory') or rec['subcategory']
   # Only explicit later statements replace baseline fields; silence is not a reversal.
   if r.get('preferred') in ('preferred','non_preferred'):rec['preferred']=r['preferred']
   if r.get('preferenceUncertaintyReason'):
    rec['preferred']='not_specified';rec['preferenceUncertaintyReason']=r['preferenceUncertaintyReason']
   if r.get('pa') in ('required','conditional','not_required'):rec['pa']=r['pa'];rec['paText']=r.get('paText','')
   if r.get('paUncertaintyReason'):
    rec['pa']='not_specified';rec['paText']='';rec['paUncertaintyReason']=r['paUncertaintyReason']
   if r.get('step')=='specified':rec['step']='specified';rec['stepText']=r.get('stepText','')
   if r.get('coverage')=='explicit_not_covered':rec['coverage']='explicit_not_covered'
   for field in ['paExceptionText','ageRestrictionText','ageLimited','coverageText']:
    if field in r:rec[field]=r[field]
   if r.get('qlAmount') or r.get('qlDays'):rec['qlAmount']=r.get('qlAmount','');rec['qlDays']=r.get('qlDays','');rec['quantityLimited']=True
   if r.get('quantityUncertaintyReason'):
    rec['qlAmount']='';rec['qlDays']='';rec['quantityLimited']=False;rec['quantityUncertaintyReason']=r['quantityUncertaintyReason']
   rec['sourceUpdates'].append({k:r.get(k) for k in ['id','name','sourceTitle','sourceUrl','sourceEffective','sourcePage','preferred','pa','paText','step','stepText','qlAmount','qlDays']})
  # Conflicting rules on equally dated candidates are kept unresolved, not chosen arbitrarily.
  for field in ['preferred','pa']:
   explicit=[r for r in candidates if r.get(field) not in (None,'','not_specified')]
   if explicit:
    latest=max(r.get('sourceEffective','') for r in explicit);values={r[field] for r in explicit if r.get('sourceEffective','')==latest}
    if len(values)>1:
     rec[field]='not_specified';rec['sourceConflict']='Later same-date source rows disagree; review linked source updates.';counts['same_date_conflicts']+=1
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
  if plan['id']=='az-complete-health':plan.update(status='baseline_plus_updates',detail=f'{len(raw):,} strength-specific JSON baseline entries plus {len(current):,} later source entries. '+SOURCE_SCOPE,effective='Historical 2022 baseline and dated plan/statewide updates')
 for e in d['planEvidence']:
  if e['planId']=='az-complete-health':e.update(topic='Formulary source of truth and precedence',evidence=SOURCE_SCOPE,sourceUrl=SOURCE,sourceEffective='2022 historical baseline')
 d['meta']['asOf']='2026-11-13'
 # Counts include lazy-loaded plan datasets as in the existing export.
 d['meta']['recordCount']+=len(result)-prior_baselines
 print(json.dumps(dict(imported=len(result),existingLaterEntries=len(current),**counts)))
 return d

if __name__=='__main__':
 path=ROOT/'dist/data.json.gz'
 data=with_ach_baseline(json.loads(gzip.decompress(path.read_bytes())))
 path.write_bytes(gzip.compress(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
