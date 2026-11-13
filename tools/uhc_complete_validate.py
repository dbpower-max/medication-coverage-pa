import json,re,hashlib,collections,sys,datetime
from pathlib import Path
import pdfplumber
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/uhc_complete_2026_11_12';a=json.loads((OUT/'initial.json').read_text());passed=[];mismatches=[]
compact=lambda t:re.sub(r'\s+','',t)
with pdfplumber.open(ROOT/'dist/sources/uhc-az-medicaid-pdl-2026-10-01.pdf') as pdf:
 for r in a['rows']:
  p=pdf.pages[r['page']-1];x0,x1=(33,384) if r['column']=='preferred' else (388,763);y0,y1=r['y'],r['end_y']
  cell=p.filter(lambda c:x0<(c.get('x0',0)+c.get('x1',0))/2<x1 and y0<(c.get('top',0)+c.get('bottom',0))/2<y1)
  t=cell.extract_text(x_tolerance=1,y_tolerance=2) or ''
  if compact(t)!=compact(r['source_text']):mismatches.append(dict(r,independent_text=t))
  else:passed.append(r)
print('Passed',len(passed),'mismatches',len(mismatches),flush=True)
(OUT/'validated.json').write_text(json.dumps({'rows':passed,'mismatches':mismatches},indent=2))
if mismatches:print(json.dumps(mismatches[:2],indent=2));sys.exit(1)
