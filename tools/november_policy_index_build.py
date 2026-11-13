"""Index complete November 2026 UHC AZ and AHCCCS FFS source chapters.
Verbatim text only; no generated coverage or approval decision is made.
"""
from pathlib import Path
import collections,datetime,hashlib,json,re,concurrent.futures
import fitz,pdfplumber
from export_data import category_for
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'audits/current_ahcccs_2026_11_12'
OUT=ROOT/'audits/november_policy_index_2026_11_12'
CONFIG=[dict(key='uhc-nov2026',filename='uhc-az-clinical-pharmacy-2026-11-01.pdf',planId='uhc-community-az',title='UnitedHealthcare Community Plan of Arizona Clinical Pharmacy Program Guidelines',url='https://www.uhcprovider.com/content/dam/provider/docs/public/commplan/az/pharmacy/AZ-Clinical-Pharmacy.pdf',hub='https://www.uhcprovider.com/en/health-plans-by-state/arizona-health-plans/az-comm-plan-home/az-cp-pharmacy/az-cp-pa-criteria.html',applicability=['Arizona AHCCCS Complete Care / Medicaid','Arizona Developmentally Disabled (DD) Program','Arizona Long-Term Care']),dict(key='ahcccs-ffs-nov2026',filename='ahcccs-ffs-pa-criteria-2026-11-01.pdf',planId='ahcccs-ffs-aihp',title='AHCCCS Fee-For-Service Program Pharmacy Prior Authorization Criteria',url='https://www.azahcccs.gov/Resources/Downloads/PharmacyUpdates/2026/AZMFileseff110126AllGuidelines.pdf',hub='https://www.azahcccs.gov/Resources/GuidesManualsPolicies/pharmacyupdates.html',applicability=['AHCCCS fee-for-service pharmacy benefit, including AIHP where this benefit applies; not all managed-care plans'])]
def clean(s):return ' '.join(s.split())
def norm(s):return re.sub(r'[^a-z0-9]','',s.lower())
def fields(text):
 name=re.search(r'Guideline\s+Name\s+(.*?)\s+Formulary',text,re.S)
 gid=re.search(r'Guideline\s+ID\s+(GL-\d+)',text)
 date=re.search(r'Effective\s+Date:\s*(\d{1,2}/\d{1,2}/\d{4})',text)
 return dict(guidelineName=clean(name[1]) if name else None,guidelineId=gid[1] if gid else None,policyEffective=datetime.datetime.strptime(date[1],'%m/%d/%Y').date().isoformat() if date else '')
def work(cfg):
 out=OUT/cfg['key'];texts=out/'text';texts.mkdir(parents=True,exist_ok=True)
 src=SRC/cfg['filename'];doc=fitz.open(src);toc=doc.get_toc();assert all(t[0]==1 for t in toc)
 starts={p for _,_,p in toc};printed=[];headers=[];page_text=[]
 for i,page in enumerate(doc):
  text=page.get_text();page_text.append(text)
  if re.search(r'Guideline\s+ID\s+GL-',text):headers.append(i+1)
  if i<toc[0][2]-1:
   for line in text.splitlines():
    m=re.match(r'(.+?)\s*\.{3,}\s*(\d+)\s*$',line)
    if m:printed.append(dict(title=clean(m[1]),page=int(m[2]),tocPhysicalPage=i+1))
 assert starts==set(headers)=={r['page'] for r in printed}
 assert len(starts)==len(toc)==len(printed)
 printed_by_page={r['page']:r for r in printed};records=[];sections=[];holds=[]
 with pdfplumber.open(src) as independent:
  for idx,(_,title,first) in enumerate(toc):
   last=toc[idx+1][2]-1 if idx+1<len(toc) else len(doc);header=page_text[first-1];meta=fields(header)
   assert norm(meta['guidelineName'])==norm(title)
   assert norm(title).endswith(norm(printed_by_page[first]['title']))
   other=independent.pages[first-1].extract_text(x_tolerance=2,y_tolerance=3) or '';other_meta=fields(other)
   verified=norm(meta['guidelineName'])==norm(other_meta['guidelineName'] or '') and meta['guidelineId']==other_meta['guidelineId'] and meta['policyEffective']==other_meta['policyEffective']
   if not verified:holds.append(dict(title=title,page=first,primary=meta,independent=other_meta));continue
   if meta['policyEffective'] and meta['policyEffective']>'2026-11-12':holds.append(dict(title=title,page=first,reason='future individual effective date'));continue
   product_names=[]
   for n in range(first-1,last):
    for m in re.finditer(r'Product\s+Name\s*:\s*(.*?)(?=\n\s*(?:Diagnosis|Approval Length|Guideline Type|Therapy Stage|Approval Criteria|Age|1\s*\.\s*Criteria)\b)',page_text[n],re.S):
     value=clean(m[1])
     if value and len(value)<500 and value not in [r['text'] for r in product_names]:product_names.append(dict(text=value,page=n+1,field='Product Name'))
   slug=meta['guidelineId'].lower();text_path=texts/(slug+'.txt');raw='\n\n'.join(f'--- PDF page {p} ---\n{page_text[p-1]}' for p in range(first,last+1));text_path.write_text(raw)
   text_url=f'/policy-text/{cfg["key"]}/{slug}.txt';source_url='/sources/'+cfg['filename']
   section=dict(title=title,firstPage=first,lastPage=last,**meta,sourceKey=cfg['key'],sourceSnapshotEffective='2026-11-01',sourceUrl=source_url,sourceTextUrl=text_url,localTextPath=str(text_path),products=product_names,boundaryValidation='Bookmark, printed TOC, Guideline ID start-page scan and independent pdfplumber header agree',individualEffectiveMissing=not bool(meta['policyEffective']))
   sections.append(section)
   note='Named Product Name fields: '+'; '.join(r['text'] for r in product_names)
   if not meta['policyEffective']:note+=' Individual policy effective date is blank in the published source.'
   records.append(dict(id=cfg['key']+'-policy-'+slug,recordType='policy_index',planId=cfg['planId'],name=title,brand='',category=category_for(title),subcategory='Clinical pharmacy policy index',coverage='policy_index',preferred='not_specified',tier='',pa='not_specified',paText='Complete current source section available. A policy section does not establish that every drug or indication requires PA.',step='not_specified',stepText='',qlAmount='',qlDays='',conditions=[],notes=note,policyCode=meta['guidelineId'],policyEffective=meta['policyEffective'],sourceTitle=cfg['title']+': '+title,sourceEffective='2026-11-01',sourcePage=first,sourceLastPage=last,sourceUrl=source_url,sourceTextUrl=text_url,validation='complete_source_index_independent_header_verified',individualEffectiveMissing=not bool(meta['policyEffective'])))
 registry=dict(cfg,sha256=hashlib.sha256(src.read_bytes()).hexdigest(),sourceSnapshotEffective='2026-11-01',retrieved='2026-11-12',pageCount=len(doc),policySectionCount=len(sections),bookmarkCount=len(toc),printedTOCCount=len(printed),guidelineHeaderStartCount=len(headers),allPolicyPositionsAccounted=len(sections)+len(holds)==len(toc),sha256TextAlgorithm='SHA-256 of original PDF bytes',warning='Index and verbatim source text only; no generated approval algorithm or patient benefit determination.')
 (out/'sections.json').write_text(json.dumps(sections,ensure_ascii=False,indent=2));(out/'proposed_policy_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));(out/'source_registry.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2));(out/'boundary_audit.json').write_text(json.dumps(dict(printedTOC=printed,bookmarks=toc,headerStarts=headers,holds=holds,missingIndividualEffective=[s for s in sections if s['individualEffectiveMissing']]),ensure_ascii=False,indent=2))
 return cfg['key'],len(sections),len(holds)
if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
  for result in pool.map(work,CONFIG):print(*result,flush=True)
