"""Release independently verified Aetna guides as separate on-demand plan files."""
import json,sqlite3,hashlib,re,shutil,datetime,collections
from pathlib import Path
from export_data import category_for
ROOT=Path(__file__).resolve().parents[1]
def clean(s):return re.sub(r'\s+',' ',s).strip()
def main():
 d=json.loads((ROOT/'dist/data.json').read_text());old=json.loads(json.dumps(d));out=ROOT/'dist/data';out.mkdir(exist_ok=True)
 dbpath=ROOT/'data/medication_coverage_v0.28.sqlite';shutil.copy2(ROOT/'data/medication_coverage_v0.27.sqlite',dbpath)
 db=sqlite3.connect(dbpath);db.execute('PRAGMA foreign_keys=ON');db.execute('CREATE TABLE commercial_formulary_metadata(formulary_entry_id INTEGER PRIMARY KEY REFERENCES formulary_entries(id), tier TEXT NOT NULL, preferred_status TEXT NOT NULL, raw_restrictions TEXT NOT NULL, validation TEXT NOT NULL)');now=datetime.datetime.now(datetime.timezone.utc).isoformat();registry=[];counts={};total=0
 d.setdefault('planDataFiles',{})
 for file in sorted((ROOT/'audits/aetna_guides').glob('2026_*.json')):
  a=json.loads(file.read_text());assert a['validation']=='independent_pdf_text_cells' and a['dates']==['10/01/2026']
  slug=file.stem.removeprefix('2026_').lower().replace('_','-');pid='aetna-'+slug
  import fitz
  pdf=ROOT/'dist/sources/aetna'/a['file'];doc=fitz.open(pdf);title=doc[20].get_text().splitlines()[0];doc.close();a['title']=title
  url='https://fm.formularynavigator.com/FBO/41/'+a['file'];local='/sources/aetna/'+a['file']
  assert hashlib.sha256(pdf.read_bytes()).hexdigest()==a['sha256']
  plan=db.execute('INSERT INTO plans(name,carrier,product,market,geography,scope,import_status,notes) VALUES(?,?,?,?,?,?,?,?)',('Aetna - '+title,'Aetna',title,'Commercial pharmacy formulary','Employer/benefit formulary reference; verify exact pharmacy plan for Tucson/Pima member','exact_product','guide_import','Exact formulary family required. Employer-specific benefit changes and exclusions may apply. Detailed PA criteria not yet loaded.')).lastrowid
  sid=db.execute('INSERT INTO sources(kind,filename,sha256,official_url,effective_date,retrieved_at,ingested_at,scope,page_count) VALUES(?,?,?,?,?,?,?,?,?)',('commercial_formulary_guide',a['file'],a['sha256'],url,'2026-10-01',now,now,'Aetna - '+title,a['page_count'])).lastrowid
  groups=collections.defaultdict(list)
  for r in a['rows']:groups[clean(r['name']).lower()].append(r)
  released=[];conflicts=[]
  for k,rs in groups.items():
   if len({(r['tier'],r['restrictions']) for r in rs})!=1:conflicts.append(rs);continue
   r=rs[0];tier=r['tier'];raw=r['restrictions'];codes=set(re.findall(r'(?:^|;\s*)(PA|ST|QL|QLR|AL|IBC|SPC|N10)(?=\s|;|$|\()',raw))
   pref='preferred' if tier in ['PG','PB','PSP','PBSP'] else 'non_preferred' if tier in ['NP','NPB','NPSP'] else 'not_specified'
   coverage='explicit_not_covered' if tier=='NF' else 'listed';pa='required' if 'PA'in codes else 'not_specified';step='specified' if 'ST'in codes else 'not_specified'
   note='Exact pharmacy formulary must match the member’s benefit documents. Detailed PA approval criteria are not yet loaded.'
   if tier=='NF':note+=' NF means nonformulary; an approved exception is required for coverage.'
   if tier=='CE':note+=' CE is a copay exception available to some members; see source and benefit terms.'
   if 'SPC'in codes or 'N10'in codes or 'Select OTC'in raw:note+=' Coverage is limited to selected plans or benefit programs; verify eligibility.'
   pt='PA printed in this formulary row' if pa=='required' else '';st='ST printed; detailed step requirements must be checked' if step=='specified' else ''
   ql=next((clean(x) for x in re.findall(r'\bQL\s*\([^)]*\)',raw)), '')
   if not ql and 'QL'in codes:ql='QL printed; see full source restrictions'
   nk=pid+':'+k;db.execute('INSERT OR IGNORE INTO drugs(drug_name,normalized_key) VALUES(?,?)',(r['name'],nk));drug=db.execute('SELECT id FROM drugs WHERE normalized_key=?',(nk,)).fetchone()[0]
   rid=db.execute('''INSERT INTO formulary_entries(plan_id,source_id,drug_id,source_page,source_row,class_name,raw_drug_name,raw_brand,raw_notes,coverage_status,preferred_status,pa_status,pa_text,step_status,step_text,ql_amount,raw_row_json) VALUES(?,?,?,?,?,?,?,'',?,?,?,?,?,?,?,?,?)''',(plan,sid,drug,r['page'],r['row'],r['class_name'],r['name'],note,coverage,'preferred' if pref=='preferred' else 'not_specified',pa,pt,step,st,ql,json.dumps(r))).lastrowid
   db.execute('INSERT INTO commercial_formulary_metadata VALUES(?,?,?,?,?)',(rid,tier,pref,raw,'source_verified_independent_cells'))
   record=dict(id=f'aetna-guide-{rid}',recordType='formulary',planId=pid,name=r['name'],brand='',notes=note,category=category_for(r['class_name']),subcategory=r['class_name'],coverage=coverage,preferred=pref,tier=tier,pa=pa,paText=pt,step=step,stepText=st,qlAmount=ql,qlDays='',ageLimited='AL'in codes,specialty=tier in ['PSP','NPSP','PBSP'],conditions=[],rawRestrictions=raw,sourceTitle='Aetna '+title+' — October 2026 drug guide',sourceEffective='2026-10-01',sourcePage=r['page'],sourcePages=sorted({x['page'] for x in rs}),sourceUrl=local,validation='source_verified_independent_cells')
   if 'SPC'in codes or 'N10'in codes or 'Select OTC'in raw:record['coverageCaveat']='Selected-plan coverage'
   elif 'N8'in raw:record['coverageCaveat']='NDC restriction'
   elif 'IBC'in codes:record['coverageCaveat']='Indication-based coverage'
   released.append(record)
  a['differing_duplicates_held']=conflicts;a['released_product_count']=len(released);file.write_text(json.dumps(a,ensure_ascii=False,indent=2))
  filename=f'data/{pid}.json';(ROOT/'dist'/filename).write_text(json.dumps(released,ensure_ascii=False,separators=(',',':')));d['planDataFiles'][pid]='./'+filename
  detail=f'{len(released):,} distinct products from the October 2026 drug guide. Match the exact pharmacy formulary name in the member’s benefit documents; an Aetna insurance card alone does not identify it. '
  detail+='The guide’s PA/ST/QL flags are imported where printed; blank fields do not establish no PA. Detailed approval criteria remain pending. '
  if not any(r['pa']=='required' for r in released):detail+='This guide does not provide a comprehensive PA flag list. '
  if conflicts or a['held']:detail+=f'{len(conflicts)} differing duplicate groups and {len(a["held"])} source rows remain held.'
  d['plans'].append(dict(id=pid,name='Aetna - '+title,market='Commercial · exact pharmacy formulary required',status='commercial_guide_import',detail=detail,effective='2026-10-01 guide'))
  d['planEvidence'].append(dict(id=pid+'-guide',planId=pid,topic='Exact pharmacy formulary source',evidence='Complete guide table extracted and independently checked cell by cell. Benefit selection and employer changes must be verified. Detailed approval criteria are not yet loaded.',sourceEffective='2026-10-01',sourcePage=21,sourceUrl=local,notes='NF means nonformulary unless an exception is approved. G alone does not establish preferred status.'))
  registry.append(dict(planId=pid,formularyTitle=title,officialFormulary=url,archivedFormulary=local,sha256=a['sha256'],effective='2026-10-01',retrieved=now,pharmacyHub='https://www.aetna.com/individuals-families/find-a-medication.html',paCriteriaSource=None,paCriteriaStatus='not_loaded',stepQuantitySource=url,epaSource=None,benefitMapping='Exact pharmacy plan name required; no carrier-wide inference',releasedProducts=len(released),heldDuplicateGroups=len(conflicts)))
  counts[pid]=len(released);total+=len(released)
 d['meta']['recordCount']=len(d['medications'])+total
 assert d['medications']==old['medications'] and d['policies']==old['policies']
 db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()
 (ROOT/'audits/aetna_guides/source_registry.json').write_text(json.dumps(registry,indent=2));(ROOT/'dist/data.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')))
 print(json.dumps({'added':total,'total':d['meta']['recordCount'],'plans':counts},indent=2))
if __name__=='__main__':main()
