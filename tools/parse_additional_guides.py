"""Parse drawn formulary cells for Ambetter AZ, AZ Blue Standardized and UHC commercial.
Preserve raw tier columns; ambiguous tier cells and name fragments remain held.
"""
import fitz,re,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];INPUT=Path(sys.argv[1]);OUT=ROOT/'audits/additional_guides';OUT.mkdir(parents=True,exist_ok=True)
CONFIGS=[dict(file='ambetter-az-2026.pdf',id='ambetter-az-essential-rx',cols=[(30,178,218,303),(309,457,497,582)],tiers=['0','1A','1B','2','3','4','6']),dict(file='azblue-standardized-2026.pdf',id='azblue-standardized',cols=[(32,278.25,409.75,579)],tiers=['$0','1','2','3','SP','MB','Tier 7','T1','T2','T3']),dict(file='uhc-commercial-sept-2026.pdf',id='uhc-commercial-reference',cols=[(36,196.06,227.74,300.41),(312,472.06,503.74,576.41)],tiers=['1','2','3','4','E'])]
def celltext(words,x0,x1,y0,y1):
 ws=[w for w in words if x0<(w[0]+w[2])/2<x1 and y0<(w[1]+w[3])/2<y1];lines=[]
 for w in sorted(ws,key=lambda w:(w[1],w[0])):
  if not lines or abs(w[1]-lines[-1][0][1])>3:lines.append([w])
  else:lines[-1].append(w)
 return ' '.join(w[4] for l in lines for w in sorted(l,key=lambda w:w[0]))
for cfg in CONFIGS:
 f=INPUT/cfg['file'];doc=fitz.open(f);rows=[];held=[];cl='';dates=set()
 for i,p in enumerate(doc):
  text=p.get_text()
  if not re.search(r'Drug\s+[Nn]ame',text):continue
  words=p.get_text('words');rects=[it[1] for d in p.get_drawings() for it in d['items'] if it[0]=='re']
  for ci,col in enumerate(cfg['cols']):
   x0,x1,x2,x3=col;rs=[r for r in rects if abs(r.x0-(x1+0.5 if cfg['id']=='ambetter-az-essential-rx' else x1))<1 and abs(r.x1-x2)<1]
   if cfg['id']=='azblue-standardized':rs=[r for r in rects if abs(r.x0-278.5)<1 and abs(r.x1-343.76)<1]
   fullstart=x0
   rs += [r for r in rects if abs(r.x0-fullstart)<1 and abs(r.x1-x3)<1]
   seen=set()
   for rect in sorted(rs,key=lambda r:r.y0):
    k=(round(rect.y0,1),round(rect.y1,1))
    if k in seen:continue
    seen.add(k)
    if rect.width>x3-x0-3:
     heading=celltext(words,fullstart,x3,*k)
     if heading and 'Drug Name' not in heading and 'Drug name' not in heading:cl=heading
     continue
    name=celltext(words,x0,x1,*k);tier=celltext(words,x1,x2,*k);raw=celltext(words,x2,x3,*k)
    tier_source=tier
    if cfg['id']=='azblue-standardized':
     values=[v for v in [celltext(words,x1,344,*k),celltext(words,344,x2,*k)] if v]
     if values and len(set(values))==1:tier=values[0]
    if name.lower()=='drug name' or tier.lower() in ['drug tier','brand generic']:continue
    r=dict(page=i+1,row=len(rows)+len(held)+1,column=ci,bounds=[x0,x1,x2,x3,rect.y0,rect.y1],name=name,tier=tier,tier_source=tier_source,restrictions=raw,class_name=cl)
    if tier not in cfg['tiers']:
     if name and not tier and not raw:cl=name
     else:held.append(dict(r,reason='tier cell requires review'))
     continue
    if not name or name.count('(')!=name.count(')') or name.endswith((',', '-', '/')):held.append(dict(r,reason='name fragment requires review'));continue
    rows.append(r)
 a=dict(cfg,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),page_count=len(doc),rows=rows,held=held)
 (OUT/(cfg['id']+'.json')).write_text(json.dumps(a,ensure_ascii=False,indent=2));print(cfg['id'],len(rows),'held',len(held),flush=True)
