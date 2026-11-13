"""Import source-verified guide rows; keep commercial reference distinct from benefit coverage."""
import json,sqlite3,hashlib,re,shutil,datetime,collections,gzip
from pathlib import Path
from export_data import category_for
from guide_codes import guide_codes
ROOT=Path(__file__).resolve().parents[1]
CONFIG={
'ambetter-az-essential-rx':dict(name='Ambetter from Arizona Complete Health - Essential Rx',carrier='Ambetter',market='Arizona marketplace pharmacy',effective='2026-01-01',revision='2026-11',date_label='2026 guide · updated November 2026',url='https://www.ambetterhealth.com/content/dam/centene/ambetteraz/pdfs/2026-az-formulary.pdf',hub='https://www.ambetterhealth.com/en/az/provider-resources/pharmacy/',note='November 2026 AZ Essential Rx list. Specific benefit designs may exclude products despite listing. Detailed PA approval criteria are not yet loaded.'),
'azblue-standardized':dict(name='AZ Blue - Standardized Plans formulary',carrier='Blue Cross Blue Shield of Arizona',market='Arizona ACA StandardHealth / StandardHealth',effective='2026-01-01',revision='2026-11-05',date_label='2026 guide · revised November 5, 2026',url='https://fm.formularynavigator.com/FBO/68/AZ_Blue_2026_Formulary_Standardized.pdf',hub='https://www.azblue.com/pharmacy/affordable-care-act-plans',note='Standardized formulary only, for ACA StandardHealth and StandardHealth. Does not establish other AZ Blue formularies. Detailed drug-specific coverage guidelines remain pending.'),
'uhc-commercial-reference':dict(name='UnitedHealthcare - commercial PDL reference',carrier='UnitedHealthcare',market='Commercial PDL reference · benefit mapping required',effective='2026-09-01',revision='',date_label='September 1, 2026 commercial reference',url='https://www.uhcprovider.com/content/dam/provider/docs/public/resources/pharmacy/commercial-pdl-sept-2026.pdf',hub='https://www.uhcprovider.com/en/resource-library/drug-lists-pharmacy.html',note='This published PDL explicitly does not define benefit coverage. Match the member’s actual pharmacy benefit before using its tiers or flags. E means may be excluded; it does not prove noncoverage. This is not a UMR-specific formulary or Medicaid source.')}
def main():
 d=json.loads((ROOT/'dist/data.json').read_text());old=json.loads(json.dumps(d));base=ROOT/'data/medication_coverage_v0.28.sqlite'
 if not base.exists():
  with gzip.open(str(base)+'.gz','rb') as src,base.open('wb') as dst:shutil.copyfileobj(src,dst)
 dbpath=ROOT/'data/medication_coverage_v0.29.sqlite';shutil.copy2(base,dbpath);db=sqlite3.connect(dbpath);db.execute('PRAGMA foreign_keys=ON');now=datetime.datetime.now(datetime.timezone.utc).isoformat();registry=[];counts={}
 for pid,cfg in CONFIG.items():
  file=ROOT/'audits/additional_guides'/f'{pid}.json';a=json.loads(file.read_text());assert a['validation']=='independent_pdf_text_cells';pdf=ROOT/'dist/sources'/a['file'];assert hashlib.sha256(pdf.read_bytes()).hexdigest()==a['sha256']
  plan=db.execute('INSERT INTO plans(name,carrier,product,market,geography,scope,import_status,notes) VALUES(?,?,?,?,?,?,?,?)',(cfg['name'],cfg['carrier'],cfg['name'],cfg['market'],'Arizona; exact product/benefit mapping required','exact_product','guide_import',cfg['note'])).lastrowid
  sid=db.execute('INSERT INTO sources(kind,filename,sha256,official_url,effective_date,retrieved_at,ingested_at,scope,page_count) VALUES(?,?,?,?,?,?,?,?,?)',('commercial_formulary_guide',a['file'],a['sha256'],cfg['url'],cfg['effective'],now,now,cfg['name'],a['page_count'])).lastrowid
  groups=collections.defaultdict(list)
  for r in a['rows']:groups[' '.join(r['name'].lower().split())].append(r)
  records=[];conflicts=[]
  for k,rs in groups.items():
   if len({(r['tier'],r['restrictions']) for r in rs})>1:conflicts.append(rs);continue
   r=rs[0];raw=r['restrictions'];tier=r['tier'];codes=guide_codes(pid,raw);pref='preferred' if pid=='ambetter-az-essential-rx' and tier=='2' else 'not_specified'
   pa='required' if 'PA'in codes else 'conditional' if 'H-PA'in codes else 'not_specified'
   if pa=='required' and re.search(r'\b(no PA|without PA|PA (?:is )?not required)\b',raw,re.I):pa='conditional'
   pt='PA printed in the source row.' if pa=='required' else 'Source-specific PA conditions or exceptions apply; see full source restrictions.' if pa=='conditional' else ''
   if 'Smart PA' in raw:pt='Smart PA printed; detailed Smart PA rules are not stated in this guide.'
   step='specified' if 'ST'in codes else 'not_specified';st='Step therapy is printed; detailed approval criteria must be checked.' if step=='specified' else '';ql='; '.join(re.findall(r'\bQL\s*\([^)]*\)',raw))
   if not ql and 'QL'in codes:ql='QL printed; numeric quantity not shown in this row'
   note=cfg['note'];nk=pid+':'+k
   db.execute('INSERT OR IGNORE INTO drugs(drug_name,normalized_key) VALUES(?,?)',(r['name'],nk));drug=db.execute('SELECT id FROM drugs WHERE normalized_key=?',(nk,)).fetchone()[0]
   rid=db.execute('''INSERT INTO formulary_entries(plan_id,source_id,drug_id,source_page,source_row,class_name,raw_drug_name,raw_brand,raw_notes,coverage_status,preferred_status,pa_status,pa_text,step_status,step_text,ql_amount,raw_row_json) VALUES(?,?,?,?,?,?,?,'',?,'listed',?,?,?,?,?,?,?)''',(plan,sid,drug,r['page'],r['row'],r['class_name'],r['name'],note,pref,pa,pt,step,st,ql,json.dumps(r))).lastrowid
   db.execute('INSERT INTO commercial_formulary_metadata VALUES(?,?,?,?,?)',(rid,tier,pref,raw,'source_verified_independent_cells'))
   record=dict(id=f'guide-{rid}',recordType='formulary',planId=pid,name=r['name'],brand='',notes=note,category=category_for(r['class_name']),subcategory=r['class_name'] or 'Published PDL reference',coverage='listed',preferred=pref,tier=tier,pa=pa,paText=pt,step=step,stepText=st,qlAmount=ql,qlDays='',ageLimited=bool({'AL','AG'}&codes),specialty=tier in ['SP','4'] if pid!='uhc-commercial-reference' else 'SP'in codes,conditions=[],rawRestrictions=raw,sourceTitle=cfg['name']+' — '+cfg['date_label'],sourceEffective=cfg['effective'],sourceRevision=cfg['revision'],sourcePage=r['page'],sourcePages=sorted({x['page'] for x in rs}),sourceUrl='/sources/'+a['file'],validation='source_verified_independent_cells')
   if pid=='uhc-commercial-reference':record['listingLabel']='In commercial PDL reference';record['coverageCaveat']='May be excluded' if tier=='E' or 'E'in codes else 'Benefit coverage unverified'
   elif tier=='MB':record['coverageCaveat']='Medical benefit; verify coverage'
   records.append(record)
  a['differing_duplicates_held']=conflicts;a['released_product_count']=len(records);a['source_metadata']=cfg;file.write_text(json.dumps(a,ensure_ascii=False,indent=2))
  dst='data/'+pid+'.json';(ROOT/'dist'/dst).write_text(json.dumps(records,ensure_ascii=False,separators=(',',':')));d['planDataFiles'][pid]='./'+dst
  detail=f'{len(records):,} distinct source-supported products. '+cfg['note']+f' {len(conflicts)} differing duplicate groups and {len(a["held"])} source rows remain held. Blank flags remain unspecified.'
  d['plans'].append(dict(id=pid,name=cfg['name'],market=cfg['market'],status='reference_guide_import' if pid=='uhc-commercial-reference' else 'commercial_guide_import',detail=detail,effective=cfg['date_label']))
  d['planEvidence'].append(dict(id=pid+'-source',planId=pid,topic='Preserved source guide',evidence=cfg['note'],sourceEffective=cfg['date_label'],sourcePage=1,sourceUrl='/sources/'+a['file'],notes='Every released product name, tier and restriction cell independently checked. No negative inference from an absent listing.'))
  registry.append(dict(planId=pid,officialFormulary=cfg['url'],archivedFormulary='/sources/'+a['file'],sha256=a['sha256'],effective=cfg['effective'],revision=cfg['revision'],retrieved=now,pharmacyHub=cfg['hub'],paCriteriaSource=None,paCriteriaStatus='not_loaded',stepQuantitySource=cfg['url'],epaSource=None,releaseCount=len(records),heldDuplicateGroups=len(conflicts),heldSourcePositions=len(a['held'])))
  counts[pid]=len(records)
 d['meta']['recordCount']+=sum(counts.values());assert old['medications']==d['medications'] and old['policies']==d['policies']
 db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()
 with dbpath.open('rb') as src,gzip.open(str(dbpath)+'.gz','wb',compresslevel=9) as dst:shutil.copyfileobj(src,dst)
 (ROOT/'dist/data.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')));(ROOT/'audits/additional_guides/source_registry.json').write_text(json.dumps(registry,indent=2));print(json.dumps({'counts':counts,'total':d['meta']['recordCount']},indent=2))
if __name__=='__main__':main()
