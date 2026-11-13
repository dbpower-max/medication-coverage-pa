"""Index complete Banner policy sections, preserving verbatim source page text."""
from pathlib import Path
import collections,json,re,sqlite3
import fitz
from export_data import category_for
ROOT=Path(__file__).resolve().parents[1]
UPLOAD=Path('/workspace/scratch/71b3a5b0d7a8/upload')
OUT=ROOT/'dist/banner-policy-text';OUT.mkdir(exist_ok=True)
def norm(v):return re.sub(r'[^A-Z0-9]','',v.upper())
def main():
 audit=json.loads((ROOT/'audits/banner_full/audit.json').read_text());data_path=ROOT/'dist/data.json';data=json.loads(data_path.read_text())
 db=sqlite3.connect(ROOT/'data/medication_coverage_v0.25.sqlite')
 db.execute('CREATE TABLE IF NOT EXISTS banner_policy_links(site_record_id TEXT,policy_source_id INTEGER,first_page INTEGER,link_basis TEXT,PRIMARY KEY(site_record_id,policy_source_id,first_page))')
 db.execute('DELETE FROM banner_policy_links')
 records=[];sections=[]
 for src in [audit['sources'][1],audit['sources'][3]]:
  doc=fitz.open(UPLOAD/src['filename']);toc=[t for t in doc.get_toc() if t[0]==1]
  internal=src['kind']=='internal_criteria'
  if internal:
   toc=[v for v in toc if v[2]<23]+[[1,'GLIC016 Ozurdex (dexamethasone implant)',20],[1,'GLIC017 Eohilia (budesonide suspension) continuation therapy',22],[1,'Lifetime approvals',23],[1,'References',24]]
  toc.sort(key=lambda v:v[2]);assert all(1<=v[2]<=len(doc) for v in toc)
  for i,(_,title,start) in enumerate(toc):
   end=toc[i+1][2]-1 if i+1<len(toc) else len(doc)
   assert end>=start
   sid=src['source_id'];key=f'{sid}-{start}'
   text='\n\n'.join(f'=== PDF PAGE {j} ===\n'+doc[j-1].get_text() for j in range(start,end+1))
   (OUT/f'{key}.txt').write_text(text)
   # The current applicability date is the cover date, not internal guideline review dates.
   note='Full source text; indication, initial/renewal criteria, exceptions and duration must be read together. Clinical criteria have not been summarized or clinician-approved.'
   rec=dict(id=f'banner-policy-{key}',recordType='policy_index',planId='banner-ufc',name=title,brand='',category=category_for(title),subcategory='Banner internal criteria' if internal else 'Banner November PA criteria',coverage='policy_only',preferred='not_specified',pa='not_specified',paText='',step='not_specified',stepText='',qlAmount='',qlDays='',notes=note,conditions=[],sourceTitle=title,sourceEffective=src['effective'],sourcePage=start,sourceLastPage=end,sourceUrl=src['url'],sourceTextUrl=f'/banner-policy-text/{key}.txt',validation='source_section_indexed',policyCode='Banner internal' if internal else 'Banner November 2026')
   records.append(rec);sections.append(dict(rec,text=text,source_id=sid,internal=internal))
   db.execute('INSERT OR IGNORE INTO policy_sections(source_id,title,first_page,last_page) VALUES(?,?,?,?)',(sid,title,start,end))
 # Reviewed class-to-title relationships. Actual drug name/brand must also occur in section text.
 class_rules=[
  ('GLP-1 Agonists - AZM',('TRULICITY','OZEMPIC','VICTOZA','BYETTA','BYDUREON')),
  ('Combination Basal Insulin/GLP-1 Receptor Agonist',('SOLIQUA','XULTOPHY')),
  ('SGLT-2 Inhibitors - AZM',('JARDIANCE','FARXIGA','INVOKANA','STEGLATRO','BRENZAVVY','TRIJARDY XR','SYNJARDY','XIGDUO XR')),
  ('Anxiolytics - AZM',('BUSPIRONE','ALPRAZOLAM','LORAZEPAM','CLONAZEPAM','DIAZEPAM','OXAZEPAM','CHLORDIAZEPOXIDE')),
  ('Antidepressants - AZM',('ANTIDEPRESS','SSRI','SNRI','TRICYCLIC','SEROTONIN','NDRI')),
  ('Anticonvulsants - AZM',('ANTICONVULS','HYDANTOIN','SUCCINIMIDE','VALPROIC','GABA')),
  ('ADHD Agents - AZM',('ADHD','AMPHETAMINE','METHYLPHENIDATE','ATOMOXETINE','GUANFACINE','CLONIDINE HCL (ADHD)')),
  ('Antipsychotics - AZM',('ANTIPSYCHOTIC',)),
  ('GLIC001 Behavioral Health Medications Guideline',('ANTIPSYCHOTIC',)),
  ('Insulins, Concentrated- Arizona',('U-500','TOUJEO')),
  ('Ranolazine products',('RANOLAZINE',)),
  ('Inhaled Corticosteroids - AZM',('STEROID INHALANTS',)),
  ('Anthelmintics - Arizona',('ANTHELMINTIC',)),
 ]
 links=[]
 for m in data['medications']:
  if m['planId']!='banner-ufc':continue
  m.pop('policySources',None)
  found=[];namebrand=norm(m['name']+' '+m['brand']);class_text=(m['name']+' '+m['brand']+' '+m['subcategory']).upper()
  for s in sections:
   title=s['name'];basis=''
   # Literal full-brand title matches are candidates only, avoiding generic words.
   brand=re.sub(r'\s*\([^)]*\)','',m['brand']).strip()
   if len(brand)>=5 and brand not in {'VARIOUS','AUTHORIZED GENERIC','BRAND ONLY'} and norm(brand) in norm(title):basis='Exact printed brand in section title'
   if not basis:
    for target,tokens in class_rules:
     if title==target and any(token in class_text for token in tokens):
      # Never infer membership from the class name alone if the product isn't mentioned.
      ingredient=re.split(r'\s|\(',m['name'])[0]
      if (len(brand)>4 and norm(brand) in norm(s['text'])) or (len(ingredient)>5 and norm(ingredient) in norm(s['text'])):basis='Reviewed class/title rule and literal product mention in source section'
   if basis:
    found.append(s);links.append(dict(record_id=m['id'],name=m['name'],brand=m['brand'],policy=title,first_page=s['sourcePage'],basis=basis))
    db.execute('INSERT OR REPLACE INTO banner_policy_links VALUES(?,?,?,?)',(m['id'],s['source_id'],s['sourcePage'],basis))
  if found:m['policySources']=[dict(title=s['name'],url=s['sourceUrl'],firstPage=s['sourcePage'],lastPage=s['sourceLastPage'],effective=s['sourceEffective'],textUrl=s['sourceTextUrl'],status='Related source section; read full applicability and indication') for s in found]
 data['policies']=[p for p in data['policies'] if p['planId']!='banner-ufc']+records
 for e in data['planEvidence']:
  if e['id']=='banner-nov26-pa':e['evidence']=f'All {sum(not s["internal"] for s in sections)} bookmarked November policy sections indexed, with full source text and exact PDF page ranges. Product links identify related source sections; no approval summary or benefit determination is inferred.'
  if e['id']=='banner-internal-june2026':e['evidence']='All 12 internal guidelines, lifetime approvals and references indexed. Ozurdex and Eohilia are included even though their PDF bookmarks were missing. Supplemental source; conflicts with general criteria require review.'
 plan=next(p for p in data['plans'] if p['id']=='banner-ufc');plan['detail']=re.sub(r' \d+ policy/source sections indexed;.*$','',plan['detail']);plan['detail']+=f' {len(records)} policy/source sections indexed; {len({l["record_id"] for l in links})} formulary records have related policy links. Detailed clinical criteria remain source text, without clinician-approved summaries.'
 data['categories']=sorted({m['category'] for m in data['medications']+data['policies']});data['subcategories']={c:sorted({m['subcategory'] for m in data['medications']+data['policies'] if m['category']==c}) for c in data['categories']}
 data_path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
 db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()
 audit['policy_index_count']=len(records);audit['november_policy_sections']=sum(not s['internal'] for s in sections);audit['internal_source_sections']=sum(s['internal'] for s in sections);audit['policy_linked_medications']=len({l['record_id'] for l in links});audit['policy_links']=links
 (ROOT/'audits/banner_full/audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
 print({k:audit[k] for k in ['policy_index_count','november_policy_sections','internal_source_sections','policy_linked_medications']})
if __name__=='__main__':main()
