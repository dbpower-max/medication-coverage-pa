import fitz,re,json,collections
from pathlib import Path
root=Path(__file__).resolve().parents[1];doc=fitz.open(root/'dist/sources/uhc-az-medicaid-pdl-2026-10-01.pdf')
rows=[];held=[];category='';codes_re=r'(?:PA|QL|AL|SP|ST|DX2RX|\*)'
def emit(lines,col,cl):
 if not lines:return
 text=' '.join(x[2] for x in lines).strip()
 m=re.fullmatch(r'(.+?)\s+-\s+Tier\s+([12])((?:;\s*'+codes_re+r')*)',text)
 r={'page':lines[0][0],'y':lines[0][1],'end_y':lines[-1][1]+13.2,'column':col,'class_name':cl,'source_text':text}
 if not m or ';' in m[1] or '||' in m[1]:held.append(r);return
 r.update(name=m[1],tier=m[2],codes=re.findall(codes_re,m[3]));rows.append(r)
for i in range(56,239):
 page=doc[i];lines=[]
 for b in page.get_text('dict')['blocks']:
  for l in b.get('lines',[]):
   s=l['spans'][0];x,y=s['bbox'][:2]
   if 47<y<545:lines.append((x,y,s['size'],''.join(s['text'] for s in l['spans']).strip()))
 headings=[l for l in lines if l[2]>12]
 # Each heading group shares a class and parent heading. Use all printed headings, no inferred class.
 sections=sorted(set(round(l[1],1) for l in headings))
 for col in ['preferred','non_preferred']:
  pending=[];cl=category;inheading=False
  for x,y,size,text in sorted(lines,key=lambda l:(l[1],l[0])):
   if size>12:
    emit(pending,col,cl);pending=[];cl=(cl+' / '+text) if inheading else text;inheading=True;continue
   if (x<385)!=(col=='preferred'):continue
   inheading=False
   if pending:
    old=' '.join(a[2] for a in pending)
    complete=bool(re.search(r' - Tier\s+[12]',old))
    codeonly=bool(re.fullmatch(codes_re+r'(?:;\s*'+codes_re+r')*;?',text))
    if complete and not old.endswith(';') and not codeonly:
     emit(pending,col,cl);pending=[]
   pending.append((i+1,round(y,2),text))
  emit(pending,col,cl)
 if headings:category=headings[-1][3]
print('ROWS',len(rows),'HELD',len(held));print('held examples',held[:12])
(root/'audits/uhc_october_expansion/parsed.json').write_text(json.dumps({'rows':rows,'held':held},indent=2))
existing=json.load(open(root/'dist/data.json'))['medications'];existing=[r for r in existing if r['planId']=='uhc-community-az' and r['sourceEffective']=='2026-10-01']
def key(n):return re.sub(r'\s+',' ',n).strip().lower()
known={key(r['name']) for r in existing};new=[r for r in rows if key(r['name']) not in known];print('NEW',len(new),'distinct',len({key(r['name']) for r in new}));print('existing missing',len(known-{key(r['name']) for r in rows}));print('NEWEX',new[:3])
