"""Extract and independently verify the current AHCCCS FFS dual non-Part D list."""
import json,re,hashlib,collections,fitz,pdfplumber
from pathlib import Path
from ffs_complete_extract import words_cell,clean,compact
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/ffs_dual_2026_11_12';PDF=OUT/'AHCCCS_DUAL_DrugList-4-1-26.pdf'
URL='https://www.azahcccs.gov/Resources/Downloads/PharmacyUpdates/2026/AHCCCS_DUAL_DrugList-4-1-26.pdf'
def main():
 doc=fitz.open(PDF);rows=[];heads=[];fragments=[];mismatches=[];cl=''
 with pdfplumber.open(PDF) as other:
  for pn,page in enumerate(doc,1):
   words=other.pages[pn-1].extract_words(x_tolerance=1,y_tolerance=1.5)
   for tn,tab in enumerate(page.find_tables().tables,1):
    assert tab.col_count==5,(pn,tab.col_count)
    for rn,(raw,trow) in enumerate(zip(tab.extract(),tab.rows),1):
     c=list(map(clean,raw));pos=dict(page=pn,table=tn,row=rn,cells=c,class_name=cl,bounds=trow.cells)
     if not any(c):continue
     if 'AHCCCS Fee-For-Service' in c[0] or c[0]=='Drug Class/Drug Name':continue
     if c[0] and not any(c[1:]) and c[0].endswith('*'):cl=c[0].rstrip('*');heads.append(pos);continue
     pos['class_name']=cl;ind=[words_cell(words,b) for b in trow.cells];pos['independent_cells']=ind
     if [compact(v) for v in c]!=[compact(v) for v in ind]:mismatches.append(pos)
     if c[0]:rows.append(pos)
     else:fragments.append(pos)
   print('Page',pn,'products',len(rows),'mismatch',len(mismatches),flush=True)
 assert len(rows)==328 and len(heads)==111 and not mismatches and not fragments,(len(rows),len(heads),len(mismatches),len(fragments))
 groups=collections.defaultdict(list)
 for r in rows:groups[(r['cells'][0],r['cells'][1])].append(r)
 assert len(groups)==328
 records=[]
 for key,rs in groups.items():
  r=rs[0];c=r['cells'];pa='not_specified'
  if re.search(r'PA\s+Required',c[2],re.I):pa='conditional' if re.search(r'(?:for|<|>|years|age)',c[2],re.I) else 'required'
  ident=hashlib.sha256('|'.join(key).encode()).hexdigest()[:16]
  records.append(dict(id='ffs-dual-'+ident,recordType='formulary',planId='ahcccs-ffs-dual',name=c[0],brand=c[1],notes='AHCCCS FFS dual non-Part D drug list only; this is not the member’s Medicare Part D formulary and does not establish an individual Part D exclusion. The PDF states effective April 1, 2026; the current website link says UpdatedMarch 1, 2026. Generic preference legend does not establish reference-brand coverage.',subcategory=r['class_name'],coverage='listed',preferred='not_specified',pa=pa,paText=c[2],step='not_specified',stepText='',qlAmount=c[3],qlDays=c[4],conditions=[],ageLimited=bool(re.search(r'(?:years|age)',c[2],re.I)),listingLabel='On FFS dual non-Part D list',coverageCaveat='Not a Medicare Part D formulary',sourceTitle='AHCCCS Fee-For-Service Dual Eligible Members Drug List',sourceEffective='2026-04-01',sourcePage=r['page'],sourcePages=[x['page'] for x in rs],sourceUrl='/sources/ahcccs-ffs-dual-2026-04-01.pdf',validation='independent_source_table_cells',rawSourceRows=rs))
 registry=dict(filename=PDF.name,official_url=URL,archive_url='/sources/ahcccs-ffs-dual-2026-04-01.pdf',sha256=hashlib.sha256(PDF.read_bytes()).hexdigest(),page_count=9,effective_date='2026-04-01',retrieved='2026-11-12',hub='https://www.azahcccs.gov/Resources/GuidesManualsPolicies/pharmacyupdates.html',hub_label='AHCCCS Dual Eligible Drug List - Updated March 1, 2026',date_conflict='PDF footer states 4/1/2026; website link label says UpdatedMarch 1, 2026. Retain document date and disclose discrepancy.',scope='AHCCCS FFS dual non-Part D Medicaid benefit; not Medicare Part D coverage',pa_criteria_source='AHCCCS FFS criteria only as applicable to this Medicaid benefit',scope_sources=[dict(url='https://www.azahcccs.gov/PlansProviders/Downloads/FFSProviderManual/FFS_Chap12Pharmacy.pdf',pages='4–5'),dict(url='https://www.azahcccs.gov/PlansProviders/Downloads/IHS-TribalManual/IHS-Chap10Pharmacy.pdf',pages='15–16')])
 audit=dict(printed_product_positions=len(rows),distinct_records=len(records),class_headings=len(heads),independent_cell_discrepancies=0,fragments=0,duplicate_conflicts=0,pa_counts=dict(collections.Counter(r['pa'] for r in records)),source=registry)
 (OUT/'extracted.json').write_text(json.dumps(dict(rows=rows,headings=heads),ensure_ascii=False,indent=2));(OUT/'proposed_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));(OUT/'source_registry.json').write_text(json.dumps(registry,indent=2));(OUT/'audit.json').write_text(json.dumps(audit,indent=2));print(audit)
if __name__=='__main__':main()
