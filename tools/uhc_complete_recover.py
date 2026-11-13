import fitz,re,json,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/uhc_complete_2026_11_12';OUT.mkdir(exist_ok=True,parents=True)
doc=fitz.open(ROOT/'dist/sources/uhc-az-medicaid-pdl-2026-10-01.pdf');rows=[];held=[];cl=''
C=r'(?:PA|QL|AL|SP|ST|DX2RX|\*)'
def completed(t):
 m=re.search(r' - Tier\s+([12])(.*)$',t)
 if not m:return False
 rest=m[2].strip()
 if not rest:return True
 if re.fullmatch(r'(?:;\s*'+C+r')*',rest):return True
 return bool(re.search(r';\s*'+C+r'(?:;\s*'+C+r')*$',rest)) or rest.endswith('Individual packets are not covered')
def emit(lines,col,cl):
 if not lines:return
 text=' '.join(l['text'] for l in lines).strip();m=re.fullmatch(r'(.+?)\s+-\s+Tier\s+([12])(.*)',text)
 r={'page':lines[0]['page'],'y':lines[0]['y'],'end_y':lines[-1]['bottom'],'column':col,'class_name':cl,'source_text':text,'lines':lines}
 if not m or ';'in m[1] or '||'in m[1]:held.append(r);return
 r.update(name=m[1],tier=m[2],raw_restrictions=('Tier '+m[2]+m[3]).strip(),codes=re.findall(r'(?:^|;\s*)('+C+r')(?=;|$)',m[3]));rows.append(r)
for i in range(56,239):
 lines=[]
 for b in doc[i].get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   s=l['spans'][0];x,y=s['bbox'][:2]
   if 47<y<545:lines.append(dict(x=x,y=y,bottom=max(s['bbox'][3] for s in l['spans']),size=s['size'],text=''.join(s['text'] for s in l['spans']).strip(),page=i+1))
 headings=[l for l in lines if l['size']>12]
 for col in ['preferred','non_preferred']:
  pending=[];current=cl;inheader=False
  for l in sorted(lines,key=lambda l:(l['y'],l['x'])):
   if l['size']>12:
    emit(pending,col,current);pending=[];current=current+' / '+l['text'] if inheader else l['text'];inheader=True;continue
   if (l['x']<385)!=(col=='preferred'):continue
   inheader=False
   if pending:
    old=' '.join(v['text'] for v in pending)
    codeonly=bool(re.fullmatch(C+r'(?:;\s*'+C+r')*;?',l['text']))
    if completed(old) and not codeonly:emit(pending,col,current);pending=[]
   pending.append(l)
  emit(pending,col,current)
 if headings:
  lastgroup=[];previous_header=False
  for line in sorted(lines,key=lambda l:(l['y'],l['x'])):
   if line['size']>12:
    if not previous_header:lastgroup=[]
    lastgroup.append(line['text']);previous_header=True
   else:previous_header=False
  cl=' / '.join(lastgroup)
(OUT/'initial.json').write_text(json.dumps({'rows':rows,'held':held},indent=2));print('ROWS',len(rows),'HELD',len(held));
for r in held:print(r['page'],r['column'],r['source_text'])
