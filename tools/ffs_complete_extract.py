"""Extract every printed FFS/AIHP November 2026 product position independently."""
import fitz,pdfplumber,re,json,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/ffs_complete_2026_11_12';PDF=OUT/'AHCCCSFFSDrugList_11_1_2026.pdf'
def clean(v):return ' '.join((v or '').split())
def compact(v):return re.sub(r'\s+','',v)
def words_cell(words,bounds):
 if not bounds:return ''
 x0,y0,x1,y1=bounds;ws=[w for w in words if x0<(w['x0']+w['x1'])/2<x1 and y0<(w['top']+w['bottom'])/2<y1];ls=[]
 for w in sorted(ws,key=lambda w:(w['top'],w['x0'])):
  if not ls or abs(w['top']-ls[-1][0]['top'])>2:ls.append([w])
  else:ls[-1].append(w)
 return clean(' '.join(w['text'] for l in ls for w in sorted(l,key=lambda w:w['x0'])))
def main():
 doc=fitz.open(PDF);raw=[];heads=[];fragments=[];mismatches=[];current='';counter=0
 with pdfplumber.open(PDF) as second:
  for pn,page in enumerate(doc,1):
   words=second.pages[pn-1].extract_words(x_tolerance=1,y_tolerance=1.5)
   tables=page.find_tables()
   for tn,tab in enumerate(tables.tables,1):
    assert tab.col_count==9,(pn,tab.col_count)
    for rn,(cells,trow) in enumerate(zip(tab.extract(),tab.rows),1):
     c=list(map(clean,cells));pos=dict(page=pn,table=tn,row=rn,cells=c,class_name=current,bounds=trow.cells)
     if 'Drug Class/Drug Name' in c[0]:continue
     if c[0] and not any(c[1:]) and c[0].endswith('*'):
      current=c[0].rstrip('*');heads.append(pos);continue
     pos['class_name']=current
     if not any(c):continue
     counter+=1;pos['source_position']=counter
     independent=[words_cell(words,b) for b in trow.cells]
     missing=[dict(column=i,primary=x,independent=y) for i,(x,y) in enumerate(zip(c,independent)) if compact(x)!=compact(y)]
     if missing:pos['independent_differences']=missing;mismatches.append(pos)
     pos['independent_cells']=independent
     if c[0]:raw.append(pos)
     else:fragments.append(pos)
   print('page',pn,'products',len(raw),'mismatches',len(mismatches),flush=True)
 a=dict(source=dict(filename=PDF.name,sha256=hashlib.sha256(PDF.read_bytes()).hexdigest(),official_url='https://www.azahcccs.gov/Resources/Downloads/PharmacyUpdates/2026/AHCCCSFFSDrugList_11_1_2026.pdf',effective='2026-11-01',retrieved='2026-11-12',pages=len(doc),scope='AHCCCS Fee-For-Service Acute/Long Term Care Program, official AIHP drug list'),printed_candidate_positions=counter,rows=raw,headings=heads,fragments=fragments,independent_mismatches=mismatches)
 (OUT/'extracted.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print('FINAL',len(raw),len(fragments),len(heads),len(mismatches))
if __name__=='__main__':main()
