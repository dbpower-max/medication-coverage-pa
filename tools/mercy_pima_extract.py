"""Full Mercy Care integrated PDF table extraction with independent cell verification."""
import fitz,pdfplumber,json,re,hashlib,collections,sys
from pathlib import Path
from ffs_complete_extract import clean,compact,words_cell
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/mercy_pima_2026_11_12';PDF=OUT/'Mercy_Care_Formulary_Guide.pdf'
def main():
 d=fitz.open(PDF);rows=[];heads=[];mismatches=[];fragments=[];cl=''
 with pdfplumber.open(PDF) as second:
  for n in range(6,239):
   p=d[n];words=second.pages[n].extract_words(x_tolerance=1,y_tolerance=1.5)
   for ti,t in enumerate(p.find_tables().tables,1):
    if t.col_count!=3:raise ValueError((n+1,t.col_count))
    for ri,(cs,tr) in enumerate(zip(t.extract(),t.rows),1):
     cells=list(map(clean,cs));r=dict(page=n+1,table=ti,row=ri,cells=cells,class_name=cl,bounds=tr.cells)
     if cells[0]=='Drug Name':continue
     if not any(cells):continue
     independently=[words_cell(words,b) for b in tr.cells]
     if any(compact(a)!=compact(b) for a,b in zip(cells,independently)):mismatches.append(dict(r,independent=independently))
     if cells[0] and not any(cells[1:]) and cells[0].endswith('*'):
      cl=cells[0].strip('*');heads.append(r);continue
     r['class_name']=cl
     if cells[0]:rows.append(r)
     else:fragments.append(r)
   if n%20==0:print('page',n+1,'rows',len(rows),'differences',len(mismatches),flush=True)
 result=dict(source=dict(filename=PDF.name,official_url='https://www.mercycareaz.org/content/dam/mercycare/pdf/Mercy_Care_Formulary_Guide.pdf',sha256=hashlib.sha256(PDF.read_bytes()).hexdigest(),effective='2026-10-01',pages=len(d)),rows=rows,headings=heads,fragments=fragments,independent_mismatches=mismatches)
 (OUT/'extracted.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('FINAL',len(rows),len(heads),len(fragments),len(mismatches))
if __name__=='__main__':main()
