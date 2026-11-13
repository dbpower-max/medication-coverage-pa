"""Banner October 2026 full-table import; November criteria kept as separate evidence."""
import collections,hashlib,json,re,shutil,sqlite3,sys
from pathlib import Path
import pdfplumber,fitz
ROOT=Path(__file__).resolve().parents[1]
UPLOAD=Path('/workspace/scratch/71b3a5b0d7a8/upload')
OUT=ROOT/'audits/banner_full'
OUT.mkdir(parents=True,exist_ok=True)
def clean(v):return ' '.join((v or '').split())
def extract():
 rows=[];headings=[];other=[];current='';pending=[]
 with pdfplumber.open(UPLOAD/'bufc_formulary_eff10012026_en.pdf') as pdf:
  for pn,page in enumerate(pdf.pages,1):
   # Embedded page labels are 6pt at (392,601), while the table text is 12pt.
   page=page.filter(lambda o:not(o.get('object_type')=='char' and o.get('size',99)<7))
   for tn,table in enumerate(page.extract_tables(),1):
    assert all(len(r)==8 for r in table),(pn,tn)
    for rn,r in enumerate(table,1):
     c=list(map(clean,r));name,brand=c[:2]
     pos={'page':pn,'table':tn,'row':rn,'class':current,'cells':c}
     if 'Drug Class/Drug Name' in name:continue
     if not name and (brand in {'','Name'}) and c[2] in {'Notes','Brand Only/Generic Notes',''} and c[3] in {'Status',''} and c[5] in {'Requirements',''} and not c[4] and c[6] in {'','(QL)'}:continue
     if name and brand:
      if pending:current=' '.join(pending);pending=[]
      pos['class']=current;rows.append(pos)
     elif not any(c[1:]) and name:
      pending.append(name);headings.append(pos)
     elif name=='COVID AT-HOME TEST KITS':
      pos['class']=current;rows.append(pos)
     else:other.append(pos)
 (OUT/'extracted.json').write_text(json.dumps({'rows':rows,'headings':headings,'other':other},indent=2))
 print('rows',len(rows),'other',len(other))
 for r in other:print('OTHER',r)
 return rows,other
if __name__=='__main__' and '--extract' in sys.argv:extract()

def repaired_rows():
 x=json.loads((OUT/'extracted.json').read_text());rows=x['rows'];others=x['other'];repairs=[]
 def row(p,t,r):return next(v for v in rows if (v['page'],v['table'],v['row'])==(p,t,r))
 def other(p,t,r):return next(v for v in others if (v['page'],v['table'],v['row'])==(p,t,r))
 def prepend(src,target,columns):
  for c in columns:target['cells'][c]=clean(src['cells'][c]+' '+target['cells'][c])
  target.setdefault('continuations',[]).append(src);repairs.append({'kind':'page_boundary','source':src,'target_position':[target[k] for k in ['page','table','row']]})
 # Text fragments are visibly separated by physical page breaks in the PDF.
 for source,target,cols in [((2,2,49),(3,1,1),[4]),((4,2,28),(5,1,1),[4]),((5,2,25),(6,1,1),[4]),((15,2,33),(16,1,1),[4]),((16,3,4),(17,1,1),[4]),((17,2,5),(18,1,1),[4])]:prepend(other(*source),row(*target),cols)
 # Venlafaxine's first two strength-specific QLs occur at the foot of page 9.
 prepend(other(9,2,33),row(10,1,1),[6,7])
 # Complete the insulin presentation from the top of page 11.
 target=row(10,2,48);frag=other(11,1,1)
 target['cells'][0]+=' '+frag['cells'][0];target['cells'][2]+=' '+frag['cells'][2];target['continuations']=[frag]
 # Albuterol brand cross-reference spans pages 6–7; preserve NDC-specific scope.
 target=row(6,2,53);frag=other(7,1,1);target['cells'][1]+=' '+frag['cells'][1];target['continuations']=[frag]
 # Name-only fragments at the prior page foot are not therapeutic headings.
 for pn,fragment in [(19,'ELVITEGRAVIR-COBICISTAT-EMTRICITABINE-TENOFOVIR'),(22,'NORETHINDRONE-ETH ESTRADIOL (TRIPHASIC)')]:
  target=row(pn,1,1);target['cells'][0]=fragment+' '+target['cells'][0]
  target['class']='ANTIRETROVIRALS' if pn==19 else 'COMBINATION CONTRACEPTIVES - ORAL'
  target['continuations']=[{'page':pn-1,'cells':[fragment]+['']*7}]
 target=next(r for r in rows if r['cells'][0]=='IBUPROFEN SUSPENSION (RX')
 target['cells'][0]+=' ONLY)';target['continuations']=[{'page':2,'cells':['ONLY)']+['']*7}]
 # The name cell has a broken table border; independent text and page-21 image agree.
 target=other(21,2,28);target['cells'][0]='NORETHINDRONE ACETATE-ETHINYL ESTRADIOL-FE TABLET';target['class']='COMBINATION CONTRACEPTIVES - ORAL';rows.append(target)
 # The source prints these as a generic-only class heading, not a product.
 for r in rows:
  if r['class']=='ONLY)':r['class']='NONSTEROIDAL ANTI-INFLAMMATORY AGENTS (NSAIDS)'
  if r['class']=='ELVITEGRAVIR-COBICISTAT-EMTRICITABINE-TENOFOVIR':r['class']='ANTIRETROVIRALS'
  if r['class']=='NORETHINDRONE-ETH ESTRADIOL (TRIPHASIC)':r['class']='COMBINATION CONTRACEPTIVES - ORAL'
  if r['cells'][0].startswith(('SILDENAFIL CITRATE (PULMONARY','TADALAFIL (PULMONARY')):
   r['class']='PULMONARY HYPERTENSION - PHOSPHODIESTERASE INHIBITORS'
   r['cells'][2]=clean(r['cells'][2]+' GENERIC ONLY (class heading)')
 (OUT/'boundary_repairs.json').write_text(json.dumps(repairs,indent=2))
 return rows

def import_full():
 from export_data import category_for
 datafile=ROOT/'dist/data.json';before=json.loads(datafile.read_text());data=json.loads(datafile.read_text())
 rows=repaired_rows();groups=collections.OrderedDict();held=[]
 mismatches={'HUMULIN N KWIKPEN':'Printed regular insulin and NPH reference brand disagree',
 'LANTUS SOLOSTAR':'Printed suspension and glargine pen formulation disagree',
 'CRESTOR':'Printed ROUVASTATIN spelling requires identity review',
 'GLUCATROL XL':'Printed reference-brand spelling requires identity review'}
 for r in rows:
  c=r['cells'];name,brand=c[:2]
  reason=mismatches.get(brand) if (brand not in {'CRESTOR'} or name.startswith('ROUVASTATIN')) else None
  if '+A1294' in name:reason='Spreadsheet cell reference appears inside the printed product name'
  if reason:held.append(dict(r,reason=reason));continue
  groups.setdefault((name,brand),[]).append(r)
 # Every product is independently present in PyMuPDF's text extraction of its source page(s).
 doc=fitz.open(UPLOAD/'bufc_formulary_eff10012026_en.pdf')
 def compact(t):return re.sub(r'\s+','',t).upper()
 page_text={i+1:compact(p.get_text()) for i,p in enumerate(doc)}
 independent=[]
 for key,rr in list(groups.items()):
  for r in rr:
   pages={r['page']}|{v['page'] for v in r.get('continuations',[])}
   corpus=''.join(page_text[p] for p in sorted(pages))
   # Wrapped cell text may be separated by other columns; verify each token independently.
   missing=[v for c in r['cells'] for v in c.split() if compact(v) not in corpus and v not in {'(class','heading)'}]
   if missing:independent.append({'position':[r['page'],r['table'],r['row']],'missing':missing,'cells':r['cells']})
 if independent:
  (OUT/'independent_exceptions.json').write_text(json.dumps(independent,indent=2))
  raise ValueError(f'Independent extraction exceptions: {len(independent)}')
 sources=[]
 source_specs=[('bufc_formulary_eff10012026_en.pdf','2026-10-01','drug_list','https://www.bannerhealth.com/medicaid/acc/find-care'),
 ('prov-bufc_pharmacy-pa-criteria_eff11012026_en.pdf','2026-11-01','pa_guidelines','https://www.bannerhealth.com/bhpprovider/resources/pharmacy/medicaid'),
 ('prov-bufc_pharmacy-pa-criteria_v2_eff10012026_en.pdf','2026-10-01','pa_guidelines_historical','https://www.bannerhealth.com/bhpprovider/resources/pharmacy/medicaid'),
 ('prov-bufc_medicaid-internal-criteria_eff061526_en.pdf','2026-06-15','internal_criteria','https://www.bannerhealth.com/bhpprovider/resources/pharmacy/medicaid')]
 for filename,effective,kind,hub in source_specs:
  p=UPLOAD/filename;pdf=fitz.open(p);sha=hashlib.sha256(p.read_bytes()).hexdigest()
  dst=ROOT/'dist/sources'/filename;shutil.copyfile(p,dst)
  sources.append(dict(filename=filename,effective=effective,kind=kind,sha256=sha,pages=len(pdf),url='/sources/'+filename,official_hub=hub))
 old=[m for m in before['medications'] if m['planId']=='banner-ufc']
 def norm(s):return re.sub(r'\s+','',s).upper()
 def old_match(name,brand):
  exact=next((m for m in old if m['name']==name and m['brand']==brand),None)
  if exact:return exact
  for m in old:
   if norm(m['brand'])==norm(brand) and norm(m['name'])==norm(name):return m
   if brand=='BYETTA' and m['brand']==brand:return m
   if brand=='DULERA' and m['brand']==brand:return m
  return None
 meds=[];conflicts=[]
 for (name,brand),rr in groups.items():
  columns=list(zip(*(r['cells'] for r in rr)))
  unique=lambda i:list(dict.fromkeys(v for v in columns[i] if v))
  pa_text=' | '.join(unique(4));step=' | '.join(unique(5));notes=' | '.join(unique(2))
  prefs=[re.sub(r'\s+','',v).upper() for v in columns[3]]
  conflict=len({tuple(r['cells'][2:]) for r in rr})>1
  pref='preferred' if all(v=='PREFERREDDRUG' for v in prefs) else 'not_specified'
  if conflict and pref!='preferred' and any(v=='PREFERREDDRUG' for v in prefs):pref='non_preferred'
  if any(v and re.sub(r'\s+','',v).upper()!='PREFERREDDRUG' for v in columns[3]):notes=clean(notes+' Source preferred-status wording: '+' | '.join(unique(3)))
  pa=('conditional' if re.search(r'AGES?|YEARS?|\bFOR\b|WHEN|NOT REQUIRED|>|<',pa_text,re.I) else 'required') if pa_text else 'not_specified'
  limits=list(dict.fromkeys((r['cells'][6],r['cells'][7]) for r in rr if r['cells'][6] or r['cells'][7]))
  ql,days=limits[0] if limits else ('','')
  if len(limits)>1:
   # Preserve every source limit; choose a single strictest value only for simple comparable quantities.
   if all(re.fullmatch(r'\d+(?:\.\d+)?',v) and re.fullmatch(r'\d+',d) and int(d)>0 for v,d in limits):ql,days=min(limits,key=lambda z:(float(z[0])/int(z[1]),int(z[1])))
   notes=clean(notes+' All printed quantity limits: '+'; '.join(f'{v} per {d} days' for v,d in limits))
  pages=sorted({r['page'] for r in rr}|{v['page'] for r in rr for v in r.get('continuations',[])})
  prior=old_match(name,brand)
  record=dict(id=prior['id'] if prior else 'banner-full-'+hashlib.sha256((name+'|'+brand).encode()).hexdigest()[:16],recordType='formulary',planId='banner-ufc',name=name,brand=brand,notes=notes,
   category=prior['category'] if prior else category_for(rr[0]['class'],name,brand),subcategory=rr[0]['class'] or 'Unclassified formulary row',coverage='explicit_not_covered' if 'NOT COVERED' in pa_text.upper() else 'listed',preferred=pref,pa=pa,paText=pa_text,step='specified' if step else 'not_specified',stepText=step,qlAmount=ql,qlDays=days,conditions=[],sourceTitle='Banner - University Family Care Acute–Long Term Care Drug List',sourceEffective='2026-10-01',sourcePage=rr[0]['page'],sourcePages=pages,sourceUrl=sources[0]['url'],validation='source_table_verified_independent_text',sourceConflict='Conflicting duplicate listings; least-covered preference and all printed restrictions retained.' if conflict else '',
   sourceRows=[dict(page=r['page'],row=r['row'],table=r['table'],preference=r['cells'][3] or 'Preferred not shown',pa=r['cells'][4],step=r['cells'][5],quantity=f"{r['cells'][6]} per {r['cells'][7]} days" if r['cells'][6] else '') for r in rr] if conflict else [])
  if record['coverage']=='explicit_not_covered':record['pa']='not_specified'
  if brand=='BYETTA':record['name']='EXENATIDE SOLN PEN-INJ';record['notes']=clean(notes+' Printed source note: *Byetta will be Obsolete 2027 03-07')
  meds.append(record)
  if conflict:conflicts.append(dict(name=name,brand=brand,rows=rr,result=record))
 # Preserve all non-Banner data and all original Banner records in the audit history.
 data['medications']=[m for m in data['medications'] if m['planId']!='banner-ufc']+meds
 assert [m for m in data['medications'] if m['planId']!='banner-ufc']==[m for m in before['medications'] if m['planId']!='banner-ufc']
 assert len({m['id'] for m in data['medications']})==len(data['medications'])
 snapshot=OUT/'prior_133_records.json'
 if not snapshot.exists():snapshot.write_text(json.dumps(old,indent=2))
 initial_count=len(json.loads(snapshot.read_text()))
 # Persist the full source import alongside existing statewide/UHC history.
 dbpath=ROOT/'data/medication_coverage_v0.25.sqlite';dbpath.parent.mkdir(exist_ok=True)
 if not dbpath.exists():shutil.copyfile('/workspace/scratch/1bb2343635da/work/medication_coverage_v0.24.sqlite',dbpath)
 db=sqlite3.connect(dbpath);db.execute('PRAGMA foreign_keys=ON')
 db.execute('CREATE TABLE IF NOT EXISTS banner_source_pages(source_id INTEGER REFERENCES sources(id),page INTEGER,text TEXT NOT NULL,PRIMARY KEY(source_id,page))')
 db.execute('CREATE TABLE IF NOT EXISTS banner_import_review(source_id INTEGER,source_position TEXT,reason TEXT,raw_json TEXT,PRIMARY KEY(source_id,source_position))')
 for s in sources:
  found=db.execute('SELECT id FROM sources WHERE sha256=?',(s['sha256'],)).fetchone()
  sid=found[0] if found else db.execute("INSERT INTO sources(kind,filename,sha256,official_url,effective_date,retrieved_at,ingested_at,scope,page_count) VALUES(?,?,?,?,?,datetime('now'),datetime('now'),'Banner ACC and ALTCS; imported under ACC only',?)",(s['kind'],s['filename'],s['sha256'],s['official_hub'],s['effective'],s['pages'])).lastrowid
  s['source_id']=sid;db.execute('INSERT OR IGNORE INTO plan_sources VALUES(3,?,?)',(sid,s['kind']))
  pdf=fitz.open(UPLOAD/s['filename'])
  db.executemany('INSERT OR IGNORE INTO banner_source_pages VALUES(?,?,?)',[(sid,i+1,p.get_text()) for i,p in enumerate(pdf)])
 sid=sources[0]['source_id']
 db.execute('DELETE FROM formulary_entries WHERE plan_id=3 AND source_id=?',(sid,))
 for record in meds:
  rr=groups[next(key for key in groups if (key[0]==record['name'] or key[1]=='BYETTA' and record['brand']=='BYETTA') and key[1]==record['brand'])]
  key=json.dumps([record['name'],record['brand'],record['notes'].upper()],ensure_ascii=False)
  found=db.execute('SELECT id FROM drugs WHERE normalized_key=?',(key,)).fetchone()
  did=found[0] if found else db.execute('INSERT INTO drugs(drug_name,reference_brand,notes,normalized_key) VALUES(?,?,?,?)',(record['name'],record['brand'],record['notes'],key)).lastrowid
  first=rr[0]
  db.execute('''INSERT OR IGNORE INTO formulary_entries(plan_id,source_id,drug_id,source_page,source_row,class_name,raw_drug_name,raw_brand,raw_notes,coverage_status,preferred_status,pa_status,pa_text,step_status,step_text,ql_amount,ql_days,raw_row_json) VALUES(3,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(sid,did,first['page'],first['table']*1000+first['row'],record['subcategory'],record['name'],record['brand'],record['notes'],record['coverage'],'not_specified' if record['preferred']=='non_preferred' else record['preferred'],record['pa'],record['paText'],record['step'],record['stepText'],record['qlAmount'],record['qlDays'],json.dumps({'rows':rr,'resolved_preference':record['preferred'],'site_record':record})))
 for h in held:db.execute('INSERT OR REPLACE INTO banner_import_review VALUES(?,?,?,?)',(sid,f"{h['page']}:{h['table']}:{h['row']}",h['reason'],json.dumps(h)))
 db.execute("UPDATE plans SET import_status='full_formulary_with_held_rows',notes=? WHERE id=3",(f'October full-table extraction; {len(meds)} released products; {len(held)} positions held. November PA source indexed separately.',))
 db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()
 for k in ['categories','subcategories']:
  if k=='categories':data[k]=sorted({m['category'] for m in data['medications']+data['policies']})
  else:data[k]={c:sorted({m['subcategory'] for m in data['medications']+data['policies'] if m['category']==c}) for c in data['categories']}
 plan=next(p for p in data['plans'] if p['id']=='banner-ufc');plan.update(status='full_formulary_with_held_rows',effective='Formulary 2026-10-01 · PA criteria 2026-11-01',detail=f'Full 34-page October formulary processed: {len(meds):,} distinct released products; {len(held)} source positions held for identity review. {len(conflicts)} differing duplicate groups use conservative status. Blank PA/preference cells remain unspecified. November PA criteria and separate June internal rules retained.')
 for e in data['planEvidence']:
  if e['id']=='banner-oct26-formulary':e.update(evidence=plan['detail'],sourceUrl=sources[0]['url'],sourcePage=1,notes='Uploaded original archived and hashed; physical PDF page links retained.')
  if e['id']=='banner-oct26-pa':e.update(sourceUrl=sources[2]['url'])
  if e['id']=='banner-nov26-pa':e.update(sourceUrl=sources[1]['url'])
 data['planEvidence']=[e for e in data['planEvidence'] if e['id']!='banner-internal-june2026']
 data['planEvidence'].append(dict(id='banner-internal-june2026',planId='banner-ufc',topic='Separate Banner internal criteria',evidence='Supplemental internal rules effective June 15, 2026, including behavioral health, Omnipod and lifetime approvals. Do not assume the November general criteria replace this separate document.',sourcePage=1,sourceEffective='2026-06-15',sourceUrl=sources[3]['url'],notes='Source text indexed separately; conflicts require review.'))
 data['meta']['recordCount']=len(data['medications']);data['meta']['asOf']='2026-11-10'
 datafile.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
 audit=dict(sources=sources,printed_product_positions=len(rows),released_products=len(meds),released_positions=sum(map(len,groups.values())),held=held,conflicts=conflicts,site_medication_count=len(data['medications']),prior_banner_count=initial_count,non_banner_unchanged=True,original_banner_preserved='prior_133_records.json',independent_text_validation='All cell tokens checked using a separate PDF extraction engine; visual samples and source-boundary review recorded',source_formulary_effective='2026-10-01',current_pa_effective='2026-11-01')
 (OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
 print({k:v for k,v in audit.items() if k not in ['sources','held','conflicts']});print('held',len(held),'conflicts',len(conflicts))

if __name__=='__main__' and '--import' in sys.argv:import_full()
