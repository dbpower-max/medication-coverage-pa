"""Independent verification of each drawn source cell, holding mismatches."""
import json,re,sys,concurrent.futures
from pathlib import Path
import pdfplumber
ROOT=Path(__file__).resolve().parents[1];INPUT=Path(sys.argv[1]);OUT=ROOT/'audits/additional_guides'
def compact(s):return re.sub(r'\s+','',s)
def work(file):
 a=json.loads(file.read_text());held=list(a['held']);passed=[];bypage={}
 for r in a['rows']:bypage.setdefault(r['page'],[]).append(r)
 with pdfplumber.open(INPUT/a['file']) as pdf:
  for page,rows in bypage.items():
   p=pdf.pages[page-1];chars=p.chars
   for r in rows:
    x0,x1,x2,x3,y0,y1=r['bounds'];texts=[]
    for lo,hi in [(x0,x1),(x1,x2),(x2,x3)]:
     cell=p.filter(lambda c:lo<(c.get('x0',0)+c.get('x1',0))/2<hi and y0<(c.get('top',0)+c.get('bottom',0))/2<y1)
     texts.append(' '.join((cell.extract_text(x_tolerance=2,y_tolerance=3) or '').split()))
    if all(compact(x)==compact(r[k]) for x,k in zip(texts,['name','tier_source','restrictions'])):passed.append(r)
    else:held.append(dict(r,reason='independent extraction mismatch',independent_cells=texts))
 a['rows']=passed;a['held']=held;a['validation']='independent_pdf_text_cells';file.write_text(json.dumps(a,ensure_ascii=False,indent=2));return a['id'],len(passed),len(held)
if __name__=='__main__':
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as ex:
  for r in ex.map(work,sorted(OUT.glob('*.json'))):print(*r,flush=True)
