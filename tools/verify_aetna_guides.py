"""Independent PDF extraction verifies every released name/tier/restriction cell."""
import json,re,concurrent.futures,sys
from pathlib import Path
import pdfplumber
ROOT=Path(__file__).resolve().parents[1]
INPUT=Path(sys.argv[1]);OUT=ROOT/'audits/aetna_guides'
def compact(s):return re.sub(r'\s+','',s)
def work(file):
 a=json.loads(file.read_text());held=list(a['held']);passed=[]
 bypage={}
 for row in a['rows']:bypage.setdefault(row['page'],[]).append(row)
 with pdfplumber.open(INPUT/a['file']) as pdf:
  for n,rows in bypage.items():
   page=pdf.pages[n-1]
   # One independent character extraction per page, then select each drawn cell.
   chars=page.chars
   for r in rows:
    texts=[]
    for x0,x1 in [(32,356),(356,428),(428,580)]:
     cell=page.filter(lambda c:x0<(c.get('x0',0)+c.get('x1',0))/2<x1 and r['y0']<(c.get('top',0)+c.get('bottom',0))/2<r['y1'])
     texts.append(' '.join((cell.extract_text(x_tolerance=2,y_tolerance=3) or '').split()))
    if all(compact(x)==compact(r[k]) for x,k in zip(texts,['name','tier','restrictions'])):passed.append(r)
    else:held.append(dict(r,independent_cells=texts,reason='independent extraction mismatch'))
 a['rows']=passed;a['held']=held;a['validation']='independent_pdf_text_cells';file.write_text(json.dumps(a,ensure_ascii=False,indent=2))
 return a['file'],len(passed),len(held)
if __name__=='__main__':
 files=sorted(OUT.glob('2026_*.json'))
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
  for result in pool.map(work,files):print(*result,flush=True)
