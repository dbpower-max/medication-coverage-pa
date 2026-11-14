"""Use the official linked JSON plus later sources under the user's provisional completeness assumption."""
import collections, copy, gzip, hashlib, json, re
from pathlib import Path
from functools import lru_cache
ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://www.azcompletehealth.com/content/dam/centene/az-complete-health/json/Drugs_FAB_CNCAZCH01_AZ_Medicaid_Integrated_Formulary_eff_9-1-22_07142026131014_AZ.json'
ASSUMPTION='Working assumption approved November 13, 2026: the officially linked JSON (declared plan year 2022) plus subsequent official updates is treated as the complete current integrated formulary. Completeness is not insurer-confirmed. Later applicable sources take precedence; source dates and baseline values remain available.'
STOP=set('w soln pref syr bitartrate bromide oral topical inhalation subcutaneous intramuscular intramusc intraven intravenous injection injectable nasal sublingual subcutane intrav sub q tablet tablets tab capsule capsules solution suspension cream ointment gel patch syringe syringes vial vials pen pens kit spray powder aerosol elixir suppository chewable chew chewable disintegrating odt er xr cr dr extended release delayed controlled hr hour hours 24 12 72 hcl hydrochloride hydrobromide sulfate sulphate mesylate sodium potassium mg mcg ml gm g % per actuation actuat metered dose inhaler nebulizer autoinjector cartridge prefilled pref pack pak various cf ag authorized generic only brand'.split())
@lru_cache(maxsize=None)
def tokens(s):
 s=re.sub(r'\([^)]*\)', ' ',s.lower());s=re.sub(r'\d+(?:\.\d+)?',' ',s)
 return set(re.findall(r'[a-z]+',s))-STOP

@lru_cache(maxsize=None)
def forms(s):
 s=s.lower(); f=set()
 for key,pattern in {'tablet':r'tablet|\btab\b|odt','capsule':r'capsule','liquid':r'solution|suspension|elixir','cream':r'cream','ointment':r'ointment','patch':r'patch','gel':r'\bgel\b','injection':r'inject|subcut|intramusc|intraven|intraven|\bintrav\b|syringe|\bsyr\b|\bvial\b|\bpen\b','nasal':r'nasal','inhalation':r'inhal|nebulizer'}.items():
  if re.search(pattern,s):f.add(key)
 return f

def compatible(a,b):
 fa,fb=forms(a),forms(b)
 if fa and fb and not fa&fb:return False
 if ('injection' in fa) != ('injection' in fb) and fa and fb:return False
 # Do not transfer a rule across immediate/extended release formulations.
 extended=lambda s:bool(re.search(r'\b(er|xr|cr|dr)\b|extended|delayed|controlled|24.hour|12.hour',s,re.I))
 return extended(a)==extended(b)

def main():
 src=ROOT/'dist/sources/ach/integrated-formulary-baseline.json.gz'
 raw=json.loads(gzip.decompress(src.read_bytes())); assert len(raw)==4454
 d=json.loads(gzip.decompress((ROOT/'dist/data.json.gz').read_bytes()))
 current=[r for r in d['medications'] if r['planId']=='az-complete-health' and r.get('validation')!='official_json_baseline_with_later_updates']
 result=[];counts=collections.Counter()
 for index,row in enumerate(raw):
  assert len(row['plans'])==1
  p=row['plans'][0]; name=row['drug_name'];brand=re.search(r'\[([^]]+)\]',name);brand=brand.group(1) if brand else ''
  generic=re.sub(r'\[[^]]+\]','',name); nt=tokens(generic)
  candidates=[]
  for r in current:
   rn=r['name']; rb=r.get('brand','')
   if '(AG)' in rn or 'AUTHORIZED' in rn.upper():continue
   branded=bool(brand and tokens(brand) and tokens(brand) <= tokens(rn))
   ingredient=nt==tokens(rn) and bool(nt)
   if not (branded or ingredient):continue
   if not compatible(name,rn):continue
   strengths=re.findall(r'\d+(?:\.\d+)?\s*(?:mg|mcg)(?:\s*/\s*ml)?',rn,re.I)
   compact=lambda s:re.sub(r'\s+','',s.lower())
   if strengths and not all(compact(v) in compact(name) for v in strengths):continue
   if not brand and re.search(r'brand\s*only',r.get('brandGenericNotes','')+' '+r.get('notes',''),re.I):continue
   candidates.append((branded,r))
  if any(b for b,r in candidates):candidates=[(b,r) for b,r in candidates if b]
  candidates=[r for b,r in candidates]
  candidates.sort(key=lambda r:r.get('sourceEffective',''))
  rec=dict(id='ach-json-'+row['rxnorm_id'],recordType='formulary',planId='az-complete-health',name=name,brand=brand,category='Other',subcategory='Integrated formulary',coverage='listed',listingLabel='Covered',preferred='preferred' if p['drug_tier']=='PREFERRED' else 'not_specified',pa='required' if p['prior_authorization'] else 'not_required',paText='Prior authorization required by the JSON baseline.' if p['prior_authorization'] else '',step='specified' if p['step_therapy'] else 'not_specified',stepText='Step therapy required; the JSON does not provide the steps.' if p['step_therapy'] else '',quantityLimited=bool(p['quantity_limit']),qlAmount='',qlDays='',conditions=[],notes=ASSUMPTION,sourceTitle='Arizona Complete Health official integrated JSON baseline (declared plan year 2022)',sourceEffective='',sourceUrl='/sources/ach/integrated-formulary-baseline.json.gz',sourceRow=index+1,rxnormId=row['rxnorm_id'],validation='official_json_baseline_with_later_updates',baselineSource={'url':SOURCE,'declaredPlanYears':p['years'],'row':index+1,'values':p},sourceUpdates=[])
  for r in candidates:
   rec['category']=r.get('category') or rec['category'];rec['subcategory']=r.get('subcategory') or rec['subcategory']
   # Only explicit later statements replace baseline fields; silence is not a reversal.
   if r.get('preferred') in ('preferred','non_preferred'):rec['preferred']=r['preferred']
   if r.get('pa') in ('required','conditional','not_required'):rec['pa']=r['pa'];rec['paText']=r.get('paText','')
   if r.get('step')=='specified':rec['step']='specified';rec['stepText']=r.get('stepText','')
   if r.get('qlAmount') or r.get('qlDays'):rec['qlAmount']=r.get('qlAmount','');rec['qlDays']=r.get('qlDays','');rec['quantityLimited']=True
   rec['sourceUpdates'].append({k:r.get(k) for k in ['id','name','sourceTitle','sourceUrl','sourceEffective','sourcePage','preferred','pa','paText','step','stepText','qlAmount','qlDays']})
  # Conflicting rules on equally dated candidates are kept unresolved, not chosen arbitrarily.
  for field in ['preferred','pa']:
   explicit=[r for r in candidates if r.get(field) not in (None,'','not_specified')]
   if explicit:
    latest=max(r.get('sourceEffective','') for r in explicit);values={r[field] for r in explicit if r.get('sourceEffective','')==latest}
    if len(values)>1:
     rec[field]='not_specified';rec['sourceConflict']='Later same-date source rows disagree; review linked source updates.';counts['same_date_conflicts']+=1
  counts['with_later_updates' if candidates else 'baseline_only']+=1
  result.append(rec)
 for r in current:
  if r.get('coverageCaveat')=='Additional plan products not fully published':r.pop('coverageCaveat')
  if r.get('validation')=='mandated_statewide_minimum_with_plan_adoption_evidence':
   r['sourceTitle']='AHCCCS drug list adopted as ACH minimum';r['notes']=r['notes'].replace('This is not the complete exact-plan formulary. Other plan products and restrictions may apply.', 'Additional plan entries are supplied by the official JSON baseline under the documented completeness assumption.')
 d['medications']=[r for r in d['medications'] if r['planId']!='az-complete-health']+current+result
 for plan in d['plans']:
  if plan['id']=='az-complete-health':plan.update(status='baseline_plus_updates',detail=f'{len(raw):,} strength-specific JSON baseline entries plus {len(current):,} later source entries. '+ASSUMPTION,effective='Official JSON baseline + official October/November 2026 updates')
 for e in d['planEvidence']:
  if e['planId']=='az-complete-health':e.update(topic='Formulary source of truth and precedence',evidence=ASSUMPTION,sourceUrl=SOURCE,sourceEffective='Baseline declared 2022; updates October/November 2026')
 d['meta']['asOf']='2026-11-13'
 # Counts include lazy-loaded plan datasets as in the existing export.
 old=json.loads(gzip.decompress((ROOT/'dist/data.json.gz').read_bytes()));d['meta']['recordCount']=old['meta']['recordCount']+len(result)-sum(r.get('validation')=='official_json_baseline_with_later_updates' for r in old['medications'])
 (ROOT/'dist/data.json.gz').write_bytes(gzip.compress(json.dumps(d,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
 print(json.dumps(dict(imported=len(result),existingLaterEntries=len(current),**counts)))
if __name__=='__main__':main()
