"""Recover current ACH source registry and mandated minimum; no full-plan inference."""
import json,re,hashlib,urllib.request,urllib.parse,concurrent.futures,copy
from pathlib import Path
from lxml import html
import fitz
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/ach_current_2026_11_12';ORIG=OUT/'originals';TEXT=OUT/'policy-text';TEXT.mkdir(exist_ok=True)
BASE='https://www.azcompletehealth.com'
HUB=BASE+'/providers/pharmacy.html';MANUAL=BASE+'/providers/resources/provider-manual/pm_section_4.html'
tree=html.parse(str(ORIG/'provider-pharmacy.html'));links=[]
for a in tree.xpath('//a[@href]'):
 u=urllib.parse.urljoin(BASE,a.get('href'));label=' '.join(a.text_content().split())
 if '/policies/' in u and '.pdf' in u:links.append((label,u,'policy'))
 if any(s in label for s in ['Behavioral Health Preferred Drug List - English','Crisis Preferred Drug List (PDF)','SABG) Medication List','OTC Drug List for Dual Eligibles']):links.append((label,u,'population_supplement'))
 if 'Integrated Drug List (JSON)' in label:links.append((label,u,'historical_json'))
def fetch(item):
 label,u,kind=item;n=urllib.parse.unquote(u.split('/')[-1]);n=re.sub('[^A-Za-z0-9._-]+','-',n);path=ORIG/n
 b=urllib.request.urlopen(u,timeout=45).read();path.write_bytes(b)
 entry=dict(label=label,url=u,kind=kind,filename=n,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),retrieved='2026-11-12')
 if b.startswith(b'%PDF'):
  doc=fitz.open(path);entry.update(pages=len(doc),bookmarks=doc.get_toc());page_text=[p.get_text() for p in doc];entry['first_page_text']=page_text[0]
  txt=TEXT/(path.stem+'.txt');txt.write_text('\n\n'.join(f'PDF PAGE {i+1}\n{t}' for i,t in enumerate(page_text)));entry['textFile']=str(txt.relative_to(ROOT))
 return entry
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:entries=list(ex.map(fetch,links))
(OUT/'public_source_registry.json').write_text(json.dumps(entries,indent=2));print('sources',len(entries),'policies',sum(e['kind']=='policy' for e in entries),'policy pages',sum(e.get('pages',0) for e in entries if e['kind']=='policy'))
# Supporting material is archived independently of drug coverage assertions.
manual=html.parse(str(ORIG/'provider-manual-section4.html'));manual_text=' '.join(manual.getroot().text_content().split());passages=[]
for needle in ['4.13.4','4.13.8','1-888-788-4408','PA and Age Limit','prior authorize']:
 for m in list(re.finditer(re.escape(needle),manual_text,re.I))[:4]:passages.append(dict(source=MANUAL,needle=needle,text=manual_text[max(0,m.start()-200):m.start()+1600]))
doc=fitz.open(ORIG/'current-acc-rbha-handbook.pdf');passages.append(dict(source=BASE+'/content/dam/centene/az-complete-health/pdf/member/handbooks/6608356_AZ7CADMHBENG_M_0CCP_Final.pdf',pdfPage=78,text=doc[77].get_text()))
(OUT/'supporting_passages.json').write_text(json.dumps(passages,indent=2))
data=json.load(open(ROOT/'dist/data.json'));state=[r for r in data['medications'] if r['planId']=='ahcccs-statewide'];overlay=[]
for row in state:
 r=copy.deepcopy(row);r['id']='ach-mandated-'+row['id'];r['planId']='az-complete-health';r['listingLabel']='AHCCCS-mandated minimum';r['coverageCaveat']='Additional plan products not fully published';r['validation']='mandated_statewide_minimum_with_plan_adoption_evidence'
 r['notes']='AHCCCS list membership/preference minimum adopted by the ACH handbook. The current provider manual requires PA for drugs marked PA or age-limited on AHCCCS lists. This is not the complete exact-plan formulary. Other plan products and restrictions may apply.'
 r['statewideReference']={k:row.get(k) for k in ['step','stepText','qlAmount','qlDays','sourceTitle','sourceEffective','sourcePage','sourceUrl']}
 r['step']='not_specified';r['stepText']='';r['qlAmount']='';r['qlDays']='';r['planAdoptionSources']=[MANUAL,BASE+'/content/dam/centene/az-complete-health/pdf/member/handbooks/6608356_AZ7CADMHBENG_M_0CCP_Final.pdf'];r['sourceTitle']='AHCCCS drug list adopted as ACH minimum; additional plan products remain incomplete'
 overlay.append(r)
assert len(overlay)==1449
(OUT/'proposed_mandated_overlay.json').write_text(json.dumps(overlay,ensure_ascii=False,indent=2))
policies=[]
for i,e in enumerate(x for x in entries if x['kind']=='policy'):
 text=e['first_page_text'];code=re.search(r'(?:Policy/Criteria\s*(?:Number|#)?\s*[:#]?|Reference\s*Number\s*:)\s*([A-Z][A-Z.]+[.\d]+)',text,re.I)
 code=code.group(1) if code else (re.search(r'AZ\.CP\.[A-Z]+\.\d+',text).group() if re.search(r'AZ\.CP\.[A-Z]+\.\d+',text) else '')
 r=dict(id='ach-current-policy-'+str(i+1),recordType='policy_index',planId='az-complete-health',name=e['label'].replace(' (PDF)',''),brand='',category='Other',subcategory='ACH exact-plan policy source',coverage='policy_index',preferred='not_specified',pa='not_specified',paText='',step='not_specified',stepText='',qlAmount='',qlDays='',conditions=[],notes='Official currently linked plan policy. Read applicability, indication, approval and renewal criteria together. A policy source does not establish drug coverage or approval.',sourceTitle=e['label'],sourceEffective='',sourcePage=1,sourceLastPage=e['pages'],sourceUrl='/sources/ach/'+e['filename'],sourceTextUrl='/policy-text/ach/'+Path(e['textFile']).name,validation='official_current_plan_policy_archived',policyCode=code,searchAliases=[code])
 if 'Skin Substitutes' in r['name']:
  r['notes']+=' The pharmacy hub labels PHAR.185 but the PDF prints AZ.CP.MP.185 and is a medical-benefit policy; verify applicability.';r['coverageCaveat']='Medical-benefit policy; hub code differs'
 if 'SABG' in r['name']:r['notes']+=' SABG population-specific policy; do not apply automatically to integrated Title19/21 pharmacy coverage.'
 if 'Infusion' in r['name']:r['notes']+=' Source line of business includes Arizona Medicaid and Arizona HIM; read the correct product branch.'
 policies.append(r)
assert len(policies)==11
(OUT/'proposed_exact_plan_policy_index.json').write_text(json.dumps(policies,indent=2))
findings=dict(status='current_public_minimum_and_notices_only',completeExactPlanFormulary=False,mandatedMinimumCount=len(overlay),exactNoticeCount=175,contactPhone='1-888-788-4408',officialRequestSource=MANUAL,requestText='Please provide the complete current Arizona Complete Health-Complete Care integrated preferred drug list, including additional plan products beyond the AHCCCS statewide list, with effective/revision date, PA, age, step-therapy and quantity-limit flags; also provide current drug-specific PA criteria for products not covered by the publicly posted criteria. The currently linked JSON declares 2022 and omits current named products.',noMemberInformationNeeded=True)
(OUT/'findings.json').write_text(json.dumps(findings,indent=2))
print('overlay',len(overlay),'policy records',len(policies))
