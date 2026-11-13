"""Release source-verified UHC additions and explicit ACH notice entries.
Run once against v0.26; preserves every prior browser record.
"""
import json,sqlite3,shutil,re,hashlib,datetime
from pathlib import Path
from export_data import category_for
ROOT=Path(__file__).resolve().parents[1]
def key(s):return re.sub(r'\s+',' ',s).strip().lower()
def main():
 d=json.loads((ROOT/'dist/data.json').read_text());old=json.loads(json.dumps(d))
 dbpath=ROOT/'data/medication_coverage_v0.27.sqlite';shutil.copy2(ROOT/'data/medication_coverage_v0.26.sqlite',dbpath)
 db=sqlite3.connect(dbpath);db.execute('PRAGMA foreign_keys=ON')
 def insert(r,plan,source,page,row,cl,notes,preferred,pa,pa_text,step,step_text,ql,raw):
  nk='plan-expansion:'+key(r)
  db.execute('INSERT OR IGNORE INTO drugs(drug_name,normalized_key) VALUES(?,?)',(r,nk))
  drug=db.execute('SELECT id FROM drugs WHERE normalized_key=?',(nk,)).fetchone()[0]
  cur=db.execute('''INSERT INTO formulary_entries(plan_id,source_id,drug_id,source_page,source_row,class_name,raw_drug_name,raw_brand,raw_notes,coverage_status,preferred_status,pa_status,pa_text,step_status,step_text,ql_amount,raw_row_json) VALUES(?,?,?,?,?,?,?,'',?,'listed',?,?,?,?,?,?,?)''',(plan,source,drug,page,row,cl,r,notes,'preferred' if preferred=='preferred' else 'not_specified',pa,pa_text,step,step_text,ql,json.dumps(raw)))
  return cur.lastrowid
 a=json.loads((ROOT/'audits/uhc_october_expansion/audit.json').read_text())
 for n,rs in enumerate(a['released_groups'],100000):
  r=rs[0];codes=r['codes'];pa='required' if 'PA' in codes else 'not_specified';pa_text='PA printed' if 'PA' in codes else ''
  note='Column and complete wrapped row verified with independent PDF text extraction.'
  if '*' in codes:note+=' Source legend: available without PA for participating Behavioral Health Prescribers.'
  step='specified' if 'ST' in codes else 'not_specified';st='ST printed; linked criteria must be checked' if 'ST' in codes else '';ql='QL printed; numeric limit not shown in this PDL row' if 'QL' in codes else ''
  rid=insert(r['name'],4,8,r['page'],n,r['class_name'],note,r['column'],pa,pa_text,step,st,ql,r)
  db.execute('INSERT INTO formulary_plan_metadata VALUES(?,?,?,?,?,?,?,?,?)',(rid,r['column'],r['tier'],int('DX2RX'in codes),int('SP'in codes),int('AL'in codes),int('QL'in codes),'Tier '+r['tier']+''.join('; '+c for c in codes),'source_verified'))
  d['medications'].append(dict(id=f'uhc-formulary-{rid}',recordType='formulary',planId='uhc-community-az',name=r['name'],brand='',notes=note,category=category_for(r['class_name']),subcategory=r['class_name'],coverage='listed',preferred=r['column'],sourceConflict='',policySource=None,tier=r['tier'],pa=pa,paText=pa_text,step=step,stepText=st,qlAmount=ql,qlDays='',ageLimited='AL'in codes,specialty='SP'in codes,diagnosisRequired='DX2RX'in codes,rawRestrictions='Tier '+r['tier']+''.join('; '+c for c in codes),conditions=[],sourceTitle='UHC Arizona Medicaid October 2026 Preferred Drug List',sourceEffective='2026-10-01',sourcePage=r['page'],sourceUrl='/sources/uhc-az-medicaid-pdl-2026-10-01.pdf',validation='source_verified_independent_text'))
 a2=json.loads((ROOT/'audits/ach_october_notice/audit.json').read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 sid=db.execute('INSERT INTO sources(kind,filename,sha256,official_url,effective_date,retrieved_at,ingested_at,scope,page_count) VALUES(?,?,?,?,?,?,?,?,?)',('plan_formulary_update_notice','ach-october-2026-formulary-notice.html',a2['sha256'],a2['url'],'2026-10-01',now,now,'Arizona Complete Health-Complete Care Plan',1)).lastrowid
 for n,r in enumerate(a2['released'],1):
  pa='required' if r['preferred']=='non_preferred' else 'not_specified';pt='Nonpreferred drugs are available through the PA process, per the notice.' if pa=='required' else ''
  rid=insert(r['name'],2,sid,1,n,r['subcategory'],r['notes'],r['preferred'],pa,pt,'not_specified','','',r)
  db.execute('INSERT INTO formulary_plan_metadata VALUES(?,?,?,?,?,?,?,?,?)',(rid,r['preferred'],None,0,0,0,0,r['raw'],'source_verified'))
  d['medications'].append(dict(id=f'ach-notice-{rid}',recordType='formulary',planId='az-complete-health',name=r['name'],brand='',notes=r['notes'],category=category_for(r['subcategory']),subcategory=r['subcategory'],coverage='listed',preferred=r['preferred'],pa=pa,paText=pt,step='not_specified',stepText='',qlAmount='',qlDays='',conditions=[],sourceTitle='Arizona Complete Health-Complete Care October 2026 formulary update notice (partial)',sourceEffective='2026-10-01',sourcePage=None,sourceUrl=a2['url'],validation='explicit_plan_notice_table',rawRestrictions=r['raw']))
 for p in d['plans']:
  if p['id']=='uhc-community-az':
   p['detail']='3,831 October 2026 source-supported products, including 1,302 newly verified complete rows. Eight previously resolved source conflicts retain conservative status. Another 137 July records remain historical. Complex rows and differing duplicates remain held; this is not a complete or member-specific benefit determination.';p['effective']='3,831 October rows · 137 unresolved historical July rows'
  if p['id']=='az-complete-health':
   p['status']='partial_notice_import';p['detail']='175 explicitly named products from the plan’s October 1, 2026 update notice. This is a partial import, not the complete formulary. Four source items remain held. PA and limits are unspecified unless explicitly stated; an asterisk means statewide-list inclusion, not PA. Eleven separate plan policy sources remain indexed.';p['effective']='2026-10-01 update notice · partial'
 d['planEvidence'].append(dict(id='ach-october-notice-import',planId='az-complete-health',topic='October 2026 named-product import',evidence='175 explicitly named products imported from this exact-plan update notice. Remaining-agent statements do not identify additional drugs. Four items held for route/conditional-rule review.',sourceEffective='2026-10-01',sourcePage=None,sourceUrl=a2['url'],notes='Partial notice only. Asterisks identify statewide drug-list inclusion, not PA requirements.'))
 d['meta']['recordCount']=len(d['medications']);d['meta']['policyCount']=len(d['policies'])
 d['categories']=sorted(set(m['category'] for m in d['medications']+d['policies']))
 # Existing subcategory representation is maintained and extended below.
 if isinstance(d['subcategories'],list):d['subcategories']=sorted(set(d['subcategories'])|{m['subcategory'] for m in d['medications']})
 elif isinstance(d['subcategories'],dict):
  for m in d['medications']:d['subcategories'][m['category']]=sorted(set(d['subcategories'].get(m['category'],[]))|{m['subcategory']})
 assert d['medications'][:len(old['medications'])]==old['medications']
 assert d['policies']==old['policies']
 assert len({m['id'] for m in d['medications']})==len(d['medications'])
 db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()
 (ROOT/'dist/data.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')))
 print('Released',len(d['medications'])-len(old['medications']),'new records; total',len(d['medications']))
if __name__=='__main__':main()
