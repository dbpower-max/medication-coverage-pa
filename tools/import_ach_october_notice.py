"""Import only explicitly named products in ACH's October 2026 update notice.
No status is inferred for unnamed 'remaining agents'. Source typos stay held.
"""
import json,re,hashlib,sqlite3
from pathlib import Path
from lxml import html
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'dist/sources/ach-october-2026-formulary-notice.html'
URL='https://www.azcompletehealth.com/newsroom/PU26135.html'
SKIP=('Remaining Agents','N/A','No New Preferred','Antimuscarinics -','Beta Agonist/','Dipeptidyl Peptidase','Glucagon-Like Peptide','Buprenorphine/Naloxone Products','Buprenorphine Products','Alpha Agonist Products','Naloxone Products','Naltrexone Products')
def extract():
 tree=html.parse(str(SOURCE));rows=[];held=[]
 for ti,table in enumerate(tree.xpath('//table')):
  for ri,tr in enumerate(table.xpath('.//tr')[1:],1):
   cells=tr.xpath('./td');cl=' '.join(cells[0].text_content().split())
   for ci,pref in [(1,'preferred'),(2,'non_preferred')]:
    texts=[' '.join(t.split()) for t in cells[ci].xpath('.//text()') if t.strip()]
    for raw in texts:
     if raw.startswith(SKIP):continue
     # Explicit separators between a route/annotation and the next named product.
     pieces=re.split(r'(?<=\*)\s*(?=[A-Z])|(?<=\))\s+(?=[A-Z][A-Z])|(?<=\(new\))\s+(?=[A-Z])',raw)
     for piece in pieces:
      if not piece.strip():continue
      if '((' in piece or 'SUBCU SUBCUTANEOUS' in piece:held.append({'text':piece,'class':cl,'reason':'source route typo'});continue
      name=re.sub(r'\s*\(new\)','',piece).replace('*','').strip()
      note='Explicitly named in the October update notice. This notice is not a complete formulary. An asterisk marks the statewide drug list, not prior authorization.'
      if '^' in name:name=name.replace('^','').replace('(BRAND PREFERRED OVER GENERIC)','').strip();note+=' Brand preferred over generic.'
      if name=='(BRAND PREFERRED OVER GENERIC)':continue
      if pref=='non_preferred':note+=' The notice says nonpreferred drugs are available through the PA process; approval is not guaranteed.'
      if name=='BUPRENORPHINE HCL (SUBLINGUAL)':
       # Hold until the separate tablet-specific pregnancy/nursing exception is joined.
       held.append({'text':piece,'class':cl,'reason':'separate conditional PA instructions require reconciliation'});continue
      rows.append(dict(name=name,preferred=pref,subcategory=cl,raw=piece,table=ti,row=ri,column=ci,notes=note))
 groups={}
 for r in rows:groups.setdefault(r['name'].lower(),[]).append(r)
 return [rs[0] for rs in groups.values()],held
if __name__=='__main__':
 rows,held=extract();out=ROOT/'audits/ach_october_notice';out.mkdir(exist_ok=True,parents=True)
 (out/'audit.json').write_text(json.dumps({'url':URL,'effective':'2026-10-01','sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'released':rows,'held':held},indent=2))
 print('ACH named products',len(rows),'held',len(held))
