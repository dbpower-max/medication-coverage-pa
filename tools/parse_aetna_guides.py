"""Extract Aetna drug guides by drawn table cells; keep product families separate."""
import fitz,json,re,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INPUT=Path(sys.argv[1])
OUT=ROOT/'audits/aetna_guides';OUT.mkdir(exist_ok=True,parents=True)
TIERS={'CE','G','NF','NP','NPB','NPSP','PB','PG','PSP','PBSP'}
def clean(s):return ' '.join(s.split())
for file in sorted(INPUT.glob('*.pdf')):
 doc=fitz.open(file);rows=[];held=[];headers=[];cl='';dates=set();title=clean(doc[0].get_text().split('best health')[1].split('Visit www.')[0])
 for i,page in enumerate(doc):
  text=page.get_text()
  if 'Prescription Drug Name' not in text:continue
  dates.update(re.findall(r'\b\d\d/\d\d/2026\b',text))
  words=page.get_text('words');tp=page.get_textpage();rects=[]
  for d in page.get_drawings():
   for item in d['items']:
    if item[0]=='re':
     r=item[1]
     if 355<r.x0<357 and 427<r.x1<429:rects.append(r)
  seen=set()
  for rect in sorted(rects,key=lambda r:r.y0):
   k=(round(rect.y0,1),round(rect.y1,1))
   if k in seen:continue
   seen.add(k)
   def cell(x0,x1):
    ws=[w for w in words if x0<(w[0]+w[2])/2<x1 and rect.y0<(w[1]+w[3])/2<rect.y1]
    lines=[]
    for w in sorted(ws,key=lambda w:(w[1],w[0])):
     if not lines or abs(w[1]-lines[-1][0][1])>3:lines.append([w])
     else:lines[-1].append(w)
    return clean(' '.join(w[4] for line in lines for w in sorted(line,key=lambda w:w[0])))
   name=cell(32,356);tier=cell(356,428);notes=cell(428,580)
   r={'page':i+1,'row':len(rows)+len(held)+1,'y0':rect.y0,'y1':rect.y1,'name':name,'tier':tier,'restrictions':notes,'class_name':cl}
   if name=='Prescription Drug Name':continue
   if tier not in TIERS:
    if name and not tier and not notes:cl=name;headers.append({'page':i+1,'text':cl})
    else:held.append(r)
    continue
   if not name or name.count('(')!=name.count(')') or name.endswith((',', '-', '/')):held.append(r);continue
   rows.append(r)
 a={'file':file.name,'title':title,'page_count':len(doc),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'dates':sorted(dates),'rows':rows,'held':held,'headers':headers}
 (OUT/(file.stem+'.json')).write_text(json.dumps(a,ensure_ascii=False,indent=2));print(file.stem,len(rows),'held',len(held),'dates',a['dates'],flush=True)
