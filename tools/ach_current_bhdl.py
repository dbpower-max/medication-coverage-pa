"""Extract currently posted ACH BHDL for its separate eligible population only."""
import fitz,pdfplumber,json,re,hashlib,collections,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'));from ffs_complete_extract import words_cell,clean,compact
OUT=ROOT/'audits/ach_current_2026_11_12';PDF=OUT/'originals/AzCH-CCP-BHPDL_1.09.2026-rev8.5.26.pdf'
url='https://www.azcompletehealth.com/content/dam/centene/az-complete-health/pdf/provider/formulary/'+PDF.name
rows=[];heads=[];mismatches=[];cl=''
with fitz.open(PDF) as doc,pdfplumber.open(PDF) as second:
 for pn,page in enumerate(doc,1):
  words=second.pages[pn-1].extract_words(x_tolerance=1,y_tolerance=1.5)
  for tn,table in enumerate(page.find_tables().tables,1):
   assert table.col_count==8,(pn,table.col_count)
   for rn,(cells,trow) in enumerate(zip(table.extract(),table.rows),1):
    c=list(map(clean,cells));ind=[words_cell(words,b) for b in trow.cells]
    if c[0]=='Drug Class/Drug Name':continue
    if not any(c):continue
    pos=dict(page=pn,table=tn,row=rn,cells=c,class_name=cl,bounds=trow.cells)
    dif=[dict(column=i,primary=x,independent=y) for i,(x,y) in enumerate(zip(c,ind)) if compact(x)!=compact(y)]
    if dif:pos['differences']=dif;mismatches.append(pos)
    if c[0] and not any(c[1:]):cl=c[0];heads.append(pos);continue
    assert c[0],pos
    pos['class_name']=cl;rows.append(pos)
print('positions',len(rows),'heads',len(heads),'mismatches',len(mismatches));assert not mismatches
# Retain all differing occurrences; no blank-as-nonpreferred inference.
groups=collections.defaultdict(list)
for r in rows:groups[(r['cells'][0].lower(),r['cells'][1].lower())].append(r)
records=[];conflicts=[]
for k,rs in groups.items():
 r=rs[0];c=r['cells'];texts=lambda n:list(dict.fromkeys(x['cells'][n] for x in rs if x['cells'][n]))
 pa_text=' | '.join(texts(4));require=bool(re.search(r'\bPA\s+REQUIRED\b',pa_text,re.I));pa='conditional' if require and re.search(r'\bunless\b|\bfor\s+Ages\b|\bage\b|[<>]',pa_text,re.I) else 'required' if require else 'not_specified'
 pref='preferred' if all(x['cells'][3]=='PREFERRED DRUG' for x in rs) else 'not_specified';step=' | '.join(texts(5));ql=texts(6);days=texts(7)
 differs=len({tuple(x['cells'][2:]) for x in rs})>1
 conflict='Multiple printed listings have differing restrictions or blank versus printed fields; read all source rows. Blank is not an explicit negative.' if differs else ''
 if differs:conflicts.append(rs)
 digest=hashlib.sha256(('|'.join(k)).encode()).hexdigest()[:16]
 record=dict(id='ach-bhdl-'+digest,recordType='formulary',planId='az-complete-health-bh-only',name=c[0],brand=c[1],category='Mental Health / Neurology',subcategory=r['class_name'],coverage='listed',preferred=pref,pa=pa,paText=pa_text,step='specified' if step else 'not_specified',stepText=step,qlAmount=ql[0] if len(ql)==1 else '',qlDays=days[0] if len(days)==1 else '',conditions=[],notes='This BHDL applies to Title19/21 members enrolled only in the ACH behavioral-health plan, plus specified non-Title19/21 SMI/SED populations. It is not the integrated Complete Care formulary. Printed review January9,2026 differs from provider-hub August2026 and member-hub September2026 review labels; printed date retained. '+(' | '.join(texts(2))),sourceTitle='ACH separate Behavioral Health Drug List — currently posted PDF',sourceEffective='',sourceReviewed='2026-01-09',sourcePage=r['page'],sourcePages=sorted({x['page'] for x in rs}),sourceUrl='/sources/ach/'+PDF.name,sourceConflict=conflict,sourceRows=[dict(page=x['page'],row=x['row'],preference=x['cells'][3],pa=x['cells'][4],step=x['cells'][5],quantity=x['cells'][6],qlDays=x['cells'][7]) for x in rs] if differs else [],validation='source_table_independently_verified',populationScope='Title19/21 behavioral-health-only; not integrated Complete Care')
 records.append(record)
(OUT/'proposed_bhdl_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
(OUT/'bhdl_audit.json').write_text(json.dumps(dict(source=dict(url=url,sha256=hashlib.sha256(PDF.read_bytes()).hexdigest(),pages=11,printedReview='2026-01-09',hubReviewLabels=['2026-08','2026-09'],completeIntegratedFormulary=False),printedProductPositions=len(rows),distinctProducts=len(records),classHeadings=len(heads),conflictingGroups=len(conflicts),independentCellMismatches=mismatches,rows=rows,conflicts=conflicts),ensure_ascii=False,indent=2))
print('products',len(records),'conflicts',len(conflicts))
