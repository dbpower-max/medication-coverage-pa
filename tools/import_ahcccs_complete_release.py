"""Rebuild the current AHCCCS reference from independently verified source projections.
All prior source snapshots remain archived. Incomplete payer publication is disclosed.
"""
import json,sqlite3,hashlib,gzip,shutil,subprocess,re,copy
from pathlib import Path
from export_data import category_for
from november_policy_index_candidates import aliases
ROOT=Path(__file__).resolve().parents[1];DIST=ROOT/'dist';AUD=ROOT/'audits';OUT=AUD/'ahcccs_release_2026_11_12';OUT.mkdir(exist_ok=True)
def read(p):return json.loads((ROOT/p).read_text())
def write(p,v):
 p=ROOT/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,separators=(',',':')))
def clone(records,pid):
 result=copy.deepcopy(records)
 for r in result:
  r['id']=pid+':'+r['id'];r['planId']=pid
  if 'approvalGuideIds'in r:r['approvalGuideIds']=[pid+':'+x for x in r['approvalGuideIds']]
 return result
def complete(r):
 r.setdefault('category',category_for(r.get('subcategory',''),r.get('name','')))
 if r['category']=='Other':r['category']=category_for(r.get('subcategory',''),r.get('name',''))
 for key,val in {'recordType':'formulary','brand':'','notes':'','preferred':'not_specified','pa':'not_specified','paText':'','step':'not_specified','stepText':'','qlAmount':'','qlDays':'','conditions':[]}.items():r.setdefault(key,val)
 return r
def copyfile(src,target):
 p=DIST/target.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,p)
def add_plan(d,pid,name,detail,effective,status='verified_published_source',market='AHCCCS Medicaid'):
 p=next((p for p in d['plans'] if p['id']==pid),None)
 obj=dict(id=pid,name=name,market=market,marketGroup='ahcccs',status=status,detail=detail,effective=effective)
 if p:p.update(obj)
 else:d['plans'].append(obj)
def main():
 d=json.loads(subprocess.check_output(['git','show','e7bad015f4db61db48c9043f198c161e9f3ad443:dist/data.json'],cwd=ROOT));baseline=copy.deepcopy(d)
 write('audits/ahcccs_release_2026_11_12/prior_medicaid_records.json',[r for r in d['medications'] if r['planId'] in ['uhc-community-az','az-complete-health','banner-ufc','ahcccs-statewide']])
 oldpol=[r for r in d['policies'] if r['planId'] in ['uhc-community-az','ahcccs-statewide','az-complete-health']]
 write('dist/history/pre-november-current-policy-records.json',oldpol)
 olduhc=[r for r in d['medications'] if r['planId']=='uhc-community-az'];write('dist/history/uhc-pre-reconciliation-records.json',olduhc)
 d['policies']=[r for r in d['policies'] if r['planId'] not in ['uhc-community-az','ahcccs-statewide','az-complete-health']]
 d['medications']=[r for r in d['medications'] if r['planId']!='uhc-community-az']
 uhc=read('audits/uhc_complete_2026_11_12/proposed_medications.json');assert len(uhc)==3921
 for r in uhc:r.pop('policySource',None);complete(r)
 d['medications']+=uhc
 # Banner source errors are visible as unresolved source records, never coverage assertions.
 fixes=read('audits/banner_exception_review_2026_11_12/summary.json')['preference_conflict_corrections']
 for f in fixes:
  r=next(r for r in d['medications'] if r['id']==f.get('record_id',f.get('id')));r['preferred']='not_specified';r['sourceConflict']='Duplicate preference fields differ: one says preferred and another is blank. Blank does not establish nonpreferred status. Both printed rows are retained.'
 banner_new=[complete(r) for r in read('audits/banner_exception_review_2026_11_12/proposed_source_rows.json')];assert len(banner_new)==5;d['medications']+=banner_new
 fields=read('audits/banner_exception_review_2026_11_12/policy_product_name_search_terms.json');byid={x.get('policy_id',x.get('id')):x for x in fields}
 for p in d['policies']:
  if p['id'] in byid:p['searchAliases']=byid[p['id']].get('searchAliases',[]);p['notes']+=' Named-product terms support source searching; confirm formulation, indication and branch in the full policy.'
 # Complete current source indexes, replacing all stale mutable-URL page offsets.
 for key in ['uhc-nov2026','ahcccs-ffs-nov2026']:
  records=read(f'audits/november_policy_index_2026_11_12/{key}/proposed_policy_records.json');sections=read(f'audits/november_policy_index_2026_11_12/{key}/sections.json');section_by={s['guidelineId'].lower():s for s in sections}
  for p in records:
   sec=section_by[p['policyCode'].lower()];p['searchAliases']=[a['alias'] for a in aliases(sec)];p['notes']+=' Policy product-field matches are search aids; read all formulation and indication branches.'
  d['policies']+=records
  target=DIST/'policy-text'/key;target.mkdir(parents=True,exist_ok=True)
  for f in (AUD/'november_policy_index_2026_11_12'/key/'text').glob('*.txt'):shutil.copy2(f,target/f.name)
 for name in ['uhc-az-clinical-pharmacy-2026-11-01.pdf','ahcccs-ffs-pa-criteria-2026-11-01.pdf']:copyfile(AUD/'current_ahcccs_2026_11_12'/name,'/sources/'+name)
 # Exact FFS and supplemental dual lists stay separate from every MCO and Part D.
 ffs=read('audits/ffs_complete_2026_11_12/proposed_records.json');dual=read('audits/ffs_dual_2026_11_12/proposed_records.json');assert len(ffs)==1810 and len(dual)==328
 copyfile(AUD/'ffs_complete_2026_11_12/AHCCCSFFSDrugList_11_1_2026.pdf','/sources/ahcccs-ffs-aihp-2026-11-01.pdf')
 copyfile(AUD/'ffs_dual_2026_11_12/AHCCCS_DUAL_DrugList-4-1-26.pdf','/sources/ahcccs-ffs-dual-2026-04-01.pdf')
 sets={'ahcccs-ffs-aihp':ffs,'ahcccs-ffs-dual':dual}
 add_plan(d,'ahcccs-ffs-aihp','AHCCCS Fee-for-Service / AIHP','Complete current published 48-page FFS list: 1,810 products from 1,813 positions, all cells independently checked. Includes 481 current FFS policy sections. This benefit does not replace an MCO or Medicare Part D formulary.','Drug list and criteria 2026-11-01')
 add_plan(d,'ahcccs-ffs-dual','AHCCCS FFS Dual Eligible — non-PartD drugs','All 328 products in the currently posted 9-page supplemental FFS dual list independently checked. PDF effective April 1, 2026; website label says March 1. This is not a Medicare Part D formulary.','PDF 2026-04-01 · website-date discrepancy retained')
 # ACH adoption provides a mandated minimum, never an invented complete exact-plan list.
 for notice in d['medications']:
  if notice['planId']=='az-complete-health':
   notice['coverageCaveat']='Exact-plan preference notice'
   if notice['pa']=='not_specified':notice['paUnknownLabel']='PA not addressed by notice'
 overlay=read('audits/ach_current_2026_11_12/proposed_mandated_overlay.json');d['medications']+=overlay
 achpol=read('audits/ach_current_2026_11_12/proposed_exact_plan_policy_index.json');d['policies']+=achpol
 bh=read('audits/ach_current_2026_11_12/proposed_bhdl_records.json');sets['az-complete-health-bh-only']=bh
 originals=AUD/'ach_current_2026_11_12/originals'
 for r in achpol+bh:
  if r.get('sourceUrl','').startswith('/'):
   src=originals/Path(r['sourceUrl']).name
   if src.exists():copyfile(src,r['sourceUrl'])
  if r.get('sourceTextUrl'):
   src=AUD/'ach_current_2026_11_12/policy-text'/Path(r['sourceTextUrl']).name
   if src.exists():copyfile(src,r['sourceTextUrl'])
 ach=[r for r in d['medications'] if r['planId']=='az-complete-health'];assert len(ach)==1624
 add_plan(d,'az-complete-health','Arizona Complete Health — Complete Care','1,449 AHCCCS-mandated minimum products plus 175 exact-plan notice entries. PA/age rules follow explicit plan adoption; statewide QL/ST remain separately labeled references. Full additional-plan PDL and unpublished drug-specific criteria remain unavailable. Call 888-788-4408 for current complete PDL; 866-796-0542 for missing criteria.','Statewide November 2026 + October notice + current plan manual','mandated_minimum_incomplete')
 add_plan(d,'az-complete-health-bh-only','Arizona Complete Health — Behavioral Health only','262 distinct products in the current separately posted BHDL, independently checked. Applies to eligible Title19/21 behavioral-health-only members and specified non-Title populations, not general integrated Complete Care. Printed review Jan9,2026 conflicts with hub Aug/Sep2026 labels.','Currently linked BHDL · printed review 2026-01-09','verified_published_source')
 sets['az-complete-health-rbha']=clone(ach,'az-complete-health-rbha');d['policies']+=clone(achpol,'az-complete-health-rbha')
 add_plan(d,'az-complete-health-rbha','Arizona Complete Health — ACC-RBHA integrated','Integrated ACC-RBHA program: same documented mandated minimum and notice sources, with program-specific current handbook adoption. Not the behavioral-health-only list. Additional plan products and unpublished criteria remain incomplete.','Current handbook 2026-10-01–2027-09-30; drug sources November/October 2026','mandated_minimum_incomplete')
 # The provider hubs explicitly share these sources among the following separate products.
 banner=[r for r in d['medications'] if r['planId']=='banner-ufc'];bpol=[r for r in d['policies'] if r['planId']=='banner-ufc']
 sets['banner-altcs']=clone(banner,'banner-altcs');d['policies']+=clone(bpol,'banner-altcs')
 add_plan(d,'banner-ufc','Banner — University Family Care ACC','All 1,489 printed formulary positions accounted: 1,451 identifiable products plus 2 explicit insulin identity conflicts. No coverage/PA inference for those conflicts. Four preference errors corrected; all current PA/internal source sections searchable.','Formulary 2026-10-01 · criteria 2026-11-01')
 add_plan(d,'banner-altcs','Banner — University Family Care ALTCS','Shares the explicitly published acute/long-term-care list and criteria. All source positions accounted; two payer insulin identity conflicts remain visible without coverage assertions.','Formulary 2026-10-01 · criteria 2026-11-01')
 upol=[r for r in d['policies'] if r['planId']=='uhc-community-az']
 for pid,title in [('uhc-altcs','UnitedHealthcare — AHCCCS Long-Term Care'),('uhc-dd','UnitedHealthcare — AHCCCS Developmental Disabilities')]:
  sets[pid]=clone(uhc,pid);d['policies']+=clone(upol,pid);add_plan(d,pid,title,'Official UHC hub explicitly shares the Medicaid PDL and clinical guidelines with this program. Complete 3,946 printed positions → 3,921 products; 25 differing duplicate groups retained. All 449 current policy sections available.','PDL 2026-10-01 · criteria 2026-11-01')
 add_plan(d,'uhc-community-az','UnitedHealthcare — AHCCCS Complete Care','Complete current PDL processed: all 3,946 printed positions → 3,921 products; 25 differing duplicate groups shown conservatively. All 449 November policy sections indexed. The 137 unmatched July entries are archived, not presented as current.','PDL 2026-10-01 · criteria 2026-11-01')
 mercy=read('audits/mercy_pima_2026_11_12/proposed_common_records.json');mpol=read('audits/mercy_pima_2026_11_12/proposed_policy_records.json');assert len(mercy)==5106
 copyfile(AUD/'mercy_pima_2026_11_12/Mercy_Care_Formulary_Guide.pdf','/sources/mercy-integrated-2026-10-01.pdf')
 for r in mpol:
  src=AUD/'mercy_pima_2026_11_12/policies'/Path(r['sourceUrl']).name
  if src.exists():copyfile(src,r['sourceUrl'])
  if r.get('sourceTextUrl'):
   choices=list((AUD/'mercy_pima_2026_11_12').rglob(Path(r['sourceTextUrl']).name))
   if choices:copyfile(choices[0],r['sourceTextUrl'])
 for pid,title in [('mercy-altcs','Mercy Care — Long-Term Care'),('mercy-dd','Mercy Care — Developmental Disabilities'),('mercy-dcs','Mercy Care — DCS Comprehensive Health Plan')]:
  sets[pid]=clone(mercy,pid);d['policies']+=clone(mpol,pid);add_plan(d,pid,title,'Official Mercy hub explicitly shares this PDL with this program. Complete 5,110 drug positions → 5,106 products, independently checked. F means formulary, not preferred; reference brands do not establish brand coverage. Differing source restrictions retained. Twelve current linked PA/ST policy sources available.','PDL 2026-10-01 · policy dates retained individually')
 # Current evidence replaces stale page pointers; all originals/history remain preserved.
 refreshed={'ahcccs-statewide','uhc-community-az','banner-ufc','az-complete-health'}|set(sets)
 d['planEvidence']=[e for e in d['planEvidence'] if e['planId'] not in refreshed]
 for p in d['plans']:
  if p['id'] in refreshed:
   p['marketGroup']='ahcccs';d['planEvidence'].append(dict(id=p['id']+'-verified-current-sources',planId=p['id'],topic='Current source scope and verification',evidence=p['detail'],sourceEffective=p.get('effective',''),sourceUrl='https://www.azahcccs.gov/Members/ProgramsAndCoveredServices/availablehealthplans.html',sourcePage=None,notes='Exact benefit/program matters. Original source pages and limitations are retained on each record.'))
 # Archive paths are available from the UHC plan evidence.
 d['planEvidence'].append(dict(id='uhc-historical-archive',planId='uhc-community-az',topic='Historical source archive',evidence='July records and superseded policy offsets are excluded from current search results and retained for audit.',sourceUrl='/history/uhc-pre-reconciliation-records.json',sourcePage=None,sourceEffective='Historical snapshots',notes='Not current benefit evidence.'))
 allmed=d['medications'][:]
 for pid,rs in sets.items():
  rs=[complete(r) for r in rs];file=f'data/{pid}.json';write('dist/'+file,rs);d['planDataFiles'][pid]='./'+file;allmed+=rs
 for pid,file in baseline['planDataFiles'].items():allmed+=read('dist/'+file.removeprefix('./'))
 for r in d['medications']+d['policies']:complete(r)
 assert len({r['id'] for r in allmed+d['policies']})==len(allmed)+len(d['policies'])
 d['meta'].update(asOf='2026-11-12',recordCount=len(allmed),policyCount=len(d['policies']))
 d['categories']=sorted({r['category'] for r in allmed+d['policies']});d['subcategories']={cat:sorted({r['subcategory'] for r in allmed+d['policies'] if r['category']==cat and r.get('subcategory')}) for cat in d['categories']}
 write('dist/data.json',d)
 # Current structured master with full lossless source payloads and separate history.
 dbfile=ROOT/'data/medication_coverage_v0.30.sqlite'
 if dbfile.exists():dbfile.unlink()
 db=sqlite3.connect(dbfile);db.executescript('''PRAGMA foreign_keys=ON; PRAGMA user_version=30;
 CREATE TABLE plans(id TEXT PRIMARY KEY,name TEXT NOT NULL,market TEXT,market_group TEXT,status TEXT,detail TEXT,effective TEXT,payload TEXT NOT NULL);
 CREATE TABLE medications(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL REFERENCES plans(id),record_type TEXT,name TEXT NOT NULL,brand TEXT,category TEXT,subcategory TEXT,coverage TEXT,preferred TEXT,pa_status TEXT,pa_text TEXT,step_status TEXT,step_text TEXT,ql_amount TEXT,ql_days TEXT,source_url TEXT,source_effective TEXT,source_page INTEGER,payload TEXT NOT NULL);
 CREATE INDEX drug_lookup ON medications(plan_id,name,brand); CREATE INDEX status_lookup ON medications(plan_id,coverage,preferred,pa_status);
 CREATE TABLE policy_sections(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL REFERENCES plans(id),title TEXT,policy_code TEXT,policy_effective TEXT,source_snapshot_effective TEXT,source_url TEXT,first_page INTEGER,last_page INTEGER,source_text_url TEXT,payload TEXT NOT NULL);
 CREATE TABLE historical_records(id INTEGER PRIMARY KEY,kind TEXT,reason TEXT,payload TEXT NOT NULL);
 CREATE TABLE release_audit(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
 ''')
 for p in d['plans']:db.execute('INSERT INTO plans VALUES(?,?,?,?,?,?,?,?)',(p['id'],p['name'],p['market'],p.get('marketGroup',''),p['status'],p['detail'],p.get('effective',''),json.dumps(p)))
 for r in allmed:db.execute('INSERT INTO medications VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(r['id'],r['planId'],r['recordType'],r['name'],r.get('brand',''),r['category'],r.get('subcategory',''),r['coverage'],r['preferred'],r['pa'],r['paText'],r['step'],r['stepText'],r['qlAmount'],r['qlDays'],r['sourceUrl'],r.get('sourceEffective',''),r.get('sourcePage'),json.dumps(r,ensure_ascii=False)))
 for r in d['policies']:db.execute('INSERT INTO policy_sections VALUES(?,?,?,?,?,?,?,?,?,?,?)',(r['id'],r['planId'],r['name'],r.get('policyCode',''),r.get('policyEffective',''),r.get('sourceEffective',''),r['sourceUrl'],r.get('sourcePage'),r.get('sourceLastPage'),r.get('sourceTextUrl',''),json.dumps(r,ensure_ascii=False)))
 for r in oldpol+olduhc:db.execute('INSERT INTO historical_records(kind,reason,payload) VALUES(?,?,?)',(r['recordType'],'Superseded/reconciled source retained; not a current coverage assertion',json.dumps(r)))
 summary=dict(asOf='2026-11-12',medicationRecords=len(allmed),policyRecords=len(d['policies']),planCounts={p['id']:sum(r['planId']==p['id'] for r in allmed) for p in d['plans']},blockers=['ACH complete additional-plan formulary and unpublished drug-specific criteria','Two Banner insulin source identity conflicts require payer clarification'],clinicalApprovalNotInferred=True)
 for k,v in summary.items():db.execute('INSERT INTO release_audit VALUES(?,?)',(k,json.dumps(v)))
 db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()
 with dbfile.open('rb') as src,gzip.open(str(dbfile)+'.gz','wb',compresslevel=9) as dst:shutil.copyfileobj(src,dst)
 write('audits/ahcccs_release_2026_11_12/summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
