"""Preserve official Mercy Care applicability and policy sources."""
import urllib.request,urllib.parse,concurrent.futures,hashlib,json,re,fitz
from lxml import html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/mercy_pima_2026_11_12';POL=OUT/'policies';POL.mkdir(exist_ok=True)
x=html.parse(str(OUT/'provider-pharmacy.html'));links=[];started=False;forms=[]
for a in x.xpath('//a[@href]'):
 text=' '.join(a.text_content().split());href=a.get('href');url=urllib.parse.urljoin('https://www.mercycareaz.org',href)
 if 'Criteria for Non-Preferred Drugs' in text:started=True
 if started and 'Universal Pharmacy' in text:started=False
 if started and '.pdf' in href:links.append(dict(title=text,url=url))
 if '.pdf' in href and ('Request-Form-MCAZ' in href or 'MCAZ-DCSCHP' in href):forms.append(dict(title=text,url=url))
seen=set();links=[r for r in links if not(r['url'] in seen or seen.add(r['url']))]
def download(r):
 b=urllib.request.urlopen(r['url'],timeout=60).read();filename=urllib.parse.unquote(r['url'].split('/')[-1]);p=POL/filename;p.write_bytes(b);d=fitz.open(p);text='\n\n'.join(f'PDF page {i+1}\n'+q.get_text() for i,q in enumerate(d));(POL/(p.stem+'.txt')).write_text(text)
 r.update(filename=filename,sha256=hashlib.sha256(b).hexdigest(),pages=len(d),text_file=p.stem+'.txt',scope='Mercy Care Medicaid policy linked by common provider pharmacy hub; review exact policy terms and product population',effective_statements=re.findall(r'(?im)^.{0,30}(?:effective|revised|reviewed|revision).{0,90}$',text)[:12]);return r
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
 for r in ex.map(download,links):results.append(r);print(r['title'],r['pages'],flush=True)
text=' '.join(x.getroot().text_content().split());phrase='Formulary for Mercy Care ACC-RBHA, DCS CHP, Long Term Care and Developmental Disabilities';i=text.find(phrase)
registry=dict(retrieved='2026-11-12',source_hub='https://www.mercycareaz.org/providers/pharmacy.html',applicability_evidence=text[i:i+1000],applicable_products=['Mercy Care Long Term Care (ALTCS)','Mercy Care Developmental Disabilities','Mercy Care DCS Comprehensive Health Plan'],out_of_area_excluded=['Mercy Care general ACC-RBHA'],policies=results,forms=[dict(t) for t in {r['url']:r for r in forms}.values()],machine_feed_limitations=[dict(url='https://www.mercycareaz.org/content/dam/mercycare/pdf/mercycare_formulary.json',status='Prior retrieval truncated mid-record; invalid JSON, not ingested'),dict(url='https://fm.formularynavigator.com/FBO/111/RBHA_Formulary.json',status='Prior valid version79 feed effective2026-10-01 omits current PDF additions including Mounjaro/Ajovy/Dupixent/Incruse/Starjemza. Not used to override source PDF.')],ffs_fallback='Official common pharmacy hub links AHCCCS FFS guidelines for medications without Mercy-specific guideline; preserve exact applicability and policy precedence, do not automatically map every FFS policy to every drug.')
(OUT/'source_registry.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
policies=[]
for i,r in enumerate(results,1):
 policies.append(dict(id=f'mercy-policy-{i}',recordType='policy_index',planId='mercy-common',name=r['title'].removesuffix(' (PDF)'),brand='',category='Other',subcategory='Mercy Care pharmacy policy source',coverage='policy_index',preferred='not_specified',pa='not_specified',paText='',step='not_specified',stepText='',qlAmount='',qlDays='',notes='Current official Mercy Care policy source. Read full scope, approval and renewal criteria; this is not an automated clinical approval determination.',conditions=[],sourceTitle=r['title'],sourceEffective='Currently linked; see printed policy date',sourcePage=1,sourceLastPage=r['pages'],sourceUrl='/sources/mercy/'+r['filename'],sourceTextUrl='/policy-text/mercy/'+r['text_file'],validation='official_policy_source_preserved'))
(OUT/'proposed_policy_records.json').write_text(json.dumps(policies,ensure_ascii=False,indent=2));print('POLICIES',len(results))
