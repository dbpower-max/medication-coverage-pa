"""Project fully validated October PDL rows; retain all differing source variants."""
import json,re,collections,hashlib,sys,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/uhc_complete_2026_11_12';sys.path.insert(0,str(ROOT/'tools'));from export_data import category_for
key=lambda t:re.sub(r'\s+',' ',t).strip().lower()
a=json.loads((OUT/'validated.json').read_text());assert not a['mismatches'] and len(a['rows'])==3946
byname=collections.defaultdict(list)
for n,r in enumerate(a['rows'],1):r['position_id']=n;byname[key(r['name'])].append(r)
records=[];duplicates=[];projection=[]
for k,rs in sorted(byname.items()):
 r=rs[0];flags=set(c for x in rs for c in x['codes']);raw=' || '.join(dict.fromkeys(x['raw_restrictions'] for x in rs));prose='; '.join(dict.fromkeys(x['raw_restrictions'] for x in rs))
 differing=len({(x['column'],x['tier'],x['raw_restrictions']) for x in rs})>1
 pref=rs[0]['column'] if len({x['column'] for x in rs})==1 else 'not_specified';tier=rs[0]['tier'] if len({x['tier'] for x in rs})==1 else ''
 explicit_conditional=bool(re.search(r'will require PA|may require prior authorization|no PA for|Prior Authorization is not required',prose,re.I))
 pa='conditional' if explicit_conditional or ('PA'in flags and '*'in flags) else 'required' if 'PA'in flags else 'not_specified'
 pat=[]
 if 'PA'in flags:pat.append('PA is printed in at least one source row.')
 if explicit_conditional:pat.append('Read the exact age, prescriber or concurrent-treatment conditions in the full source restriction text.')
 if '*'in flags:pat.append('Source legend: available without PA for participating Behavioral Health Prescribers. This does not establish a general exemption for other prescribers.')
 if pa=='not_specified' and not pat:pat=[]
 note='Complete October source position independently checked against a second PDF text extractor.'
 if differing:note+=' Different printed variants are retained below. An omitted flag does not cancel an explicit restriction in another row.'
 conflict=''
 kinds=[]
 if len({x['column'] for x in rs})>1:kinds.append('preferred/nonpreferred columns')
 if len({x['tier'] for x in rs})>1:kinds.append('tiers')
 if len({x['raw_restrictions'] for x in rs})>1:kinds.append('restrictions')
 if differing:conflict='Printed listings differ in '+', '.join(kinds)+'. Use all source variants; unresolved identity or plan handling requires review.'
 rid='uhc-oct-complete-'+hashlib.sha256(k.encode()).hexdigest()[:16]
 ql='QL printed; numeric limit not shown in this PDL row' if 'QL'in flags else ''
 qlprose=re.search(r'QL for [^;]+',prose)
 if qlprose:ql=qlprose[0]
 rec=dict(id=rid,recordType='formulary',planId='uhc-community-az',name=r['name'],brand='',notes=note,category=category_for(r['class_name']),subcategory=r['class_name'],coverage='listed',preferred=pref,tier=tier,pa=pa,paText=' '.join(pat),step='specified' if 'ST'in flags else 'not_specified',stepText='ST printed; read linked criteria for the exact product and indication.' if 'ST'in flags else '',qlAmount=ql,qlDays='',ageLimited='AL'in flags,specialty='SP'in flags,diagnosisRequired='DX2RX'in flags,conditions=[],rawRestrictions=raw,sourceConflict=conflict,sourceConflictKind=kinds,sourceTitle='UnitedHealthcare Community Plan Arizona October 2026 Preferred Drug List',sourceEffective='2026-10-01',sourcePage=r['page'],sourcePages=sorted({x['page'] for x in rs}),sourceUrl='/sources/uhc-az-medicaid-pdl-2026-10-01.pdf',validation='complete_source_positions_independently_verified',sourcePositionIds=[x['position_id'] for x in rs],policySource=None)
 if differing:
  rec['conflictSources']=[dict(page=x['page'],column=x['column'],codes=x['raw_restrictions'],positionId=x['position_id']) for x in rs];duplicates.append(dict(record_id=rid,name=r['name'],kinds=kinds,rows=rs))
 if 'Coverable through Medical Benefit' in raw:rec['coverageCaveat']='Medical benefit; verify coverage'
 if 'Individual packets are not covered' in raw:rec['coverageCaveat']='Bulk containers only; packets excluded'
 if 'ONLY powder bottle' in raw:rec['coverageCaveat']='Powder bottle only'
 if 'NDC starting' in raw or 'labelers' in raw:rec['coverageCaveat']='Manufacturer or NDC restriction'
 records.append(rec)
 for x in rs:projection.append(dict(position_id=x['position_id'],record_id=rid,page=x['page'],column=x['column'],source_text=x['source_text'],y=x['y'],end_y=x['end_y']))
assert len(records)==3921 and len(duplicates)==25 and len(projection)==3946
old=json.loads((ROOT/'dist/data.json').read_text());old_uhc=[x for x in old['medications'] if x['planId']=='uhc-community-az'];historic=[x for x in old_uhc if x['sourceEffective']=='2026-07-01'];current=[x for x in old_uhc if x['sourceEffective']=='2026-10-01'];assert len(historic)==137
currentkeys={key(x['name']) for x in records}
history=[]
for r in historic:
 stripped=re.sub(r'\s*\((?:generic|brand) for.*','',key(r['name'])).strip()
 candidates=[x['name'] for x in records if key(x['name']).startswith(stripped+' ') or key(x['name']).startswith(stripped+' (')]
 history.append(dict(record=r,octoberExactNameMatched=key(r['name'])in currentkeys,reason='Historical July listing does not repeat the same exact full product identity in October. Do not infer coverage or carry July restrictions forward.',possibleBroaderNarrowerOctoberNames=candidates[:20],candidateIdentitiesVerified=False))
assert not any(x['octoberExactNameMatched'] for x in history)
retired=[x for x in current if key(x['name'])not in currentkeys]
summary=dict(sourcePdf='dist/sources/uhc-az-medicaid-pdl-2026-10-01.pdf',sourceSha256=hashlib.sha256((ROOT/'dist/sources/uhc-az-medicaid-pdl-2026-10-01.pdf').read_bytes()).hexdigest(),printedProductPositions=len(projection),distinctProducts=len(records),differingDuplicateGroups=len(duplicates),independentTextMismatches=0,parseHolds=0,complexProsePositions=sum(not re.fullmatch(r'Tier [12](?:;\s*(?:PA|QL|AL|SP|ST|DX2RX|\*))*',x['raw_restrictions']) for x in a['rows']),oldCurrentExactNamesRetained=len(current)-len(retired),retiredOldCurrentEntries=retired,archivedHistoricalJulyCount=len(history),historicalJulyExactOctoberMatches=0,notes=['Blank flags remain unspecified. Positive restrictions from a differing duplicate are not canceled by an omitted flag.','Do not label duplicate variants NDC-specific without direct NDC evidence.','November PA guidelines must be joined separately; old mutable-source page pointers have not been carried forward.'])
for filename,data in [('proposed_medications.json',records),('duplicate_groups.json',duplicates),('source_position_projection.json',projection),('historical_july_reconciliation.json',history),('summary.json',summary)]:
 (OUT/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='retiredOldCurrentEntries'},indent=2))
