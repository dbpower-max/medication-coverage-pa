"""Connect explicit product identities to existing same-plan policy sources.
Links are navigation aids; they never change coverage, PA, preference, or approval.
"""
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def norm(s):return re.sub('[^a-z0-9]+',' ',s.lower()).strip()

def attach_provider_policies(data):
 policies={p['id']:p for p in data['policies']}
 # These identities are explicitly named as covered products in the archived policy text.
 ach_aliases={
  'AZ.CP.PMN.05':['rifapentine','Priftin'],
  'AZ.CP.PHAR.1020':['Lemtrada','mitoxantrone'],
  'AZ.CP.PHAR.228':['Herceptin','Herceptin Hylecta','trastuzumab','trastuzumab-hyaluronidase-oysk'],
  'AZ.CP.PMN.1002':['rabeprazole','Aciphex','dexlansoprazole','Dexilant','esomeprazole strontium','Nexium 24HR','omeprazole sodium bicarbonate','Zegerid'],
 }
 for p in policies.values():
  if p['planId']=='az-complete-health':
   if p['id']=='ach-current-policy-5':
    text=(ROOT/'dist'/p['sourceTextUrl'].lstrip('./')).read_text()
    assert 'Reference Number: AZ. CP.PHAR.493' in text
    p['policyCode']='AZ.CP.PHAR.493';p['searchAliases']=['AZ.CP.PHAR.493','Infusion Site of Care Optimization']
   if p['policyCode'] in ach_aliases:p['searchAliases']=list(dict.fromkeys(p.get('searchAliases',[])+ach_aliases[p['policyCode']]))
 count=0;records=set()
 for r in data['medications']:
  if r['planId'] not in ('uhc-community-az','az-complete-health'):continue
  # Reference-brand labels do not establish that a particular branded formulation is covered.
  identities=[norm(r['name'])]
  if r.get('baselineSource'):
   identities.append(norm(re.sub(r'\[[^]]+\]','',r['name'])))
   identities += [norm(v) for v in re.findall(r'\[([^]]+)\]',r['name'])]
  for p in policies.values():
   if p['planId']!=r['planId']:continue
   if r['planId']=='az-complete-health' and p['policyCode'] not in ach_aliases:continue
   aliases=p.get('searchAliases',[])
   matches=[a for a in aliases if len(norm(a))>=5 and any(i==norm(a) or i.startswith(norm(a)+' ') for i in identities)]
   if not matches:continue
   if not p.get('sourceTextUrl') or not p.get('sourcePage'):continue
   textpath=ROOT/'dist'/p['sourceTextUrl'].lstrip('./');assert textpath.is_file()
   link=dict(policyId=p['id'],title=p['name'],policyCode=p['policyCode'],firstPage=p['sourcePage'],lastPage=p.get('sourceLastPage',p['sourcePage']),url=p['sourceUrl'],textUrl=p['sourceTextUrl'],effective=p.get('policyEffective') or p.get('sourceEffective',''),matchedProduct=matches[0],scope='Related same-plan source; verify formulation, indication, age, and authorization branch.')
   links=r.setdefault('policySources',[])
   if not any(x.get('policyId')==p['id'] for x in links):links.append(link);count+=1;records.add(r['id'])
 # Exact Banner November source branches independently reviewed against the
 # archived text and October formulary rows. These are navigation bindings,
 # not new benefit flags or a machine-generated approval algorithm.
 banner_reviewed = {
  "banner-full-3896cdde40e8e8a1": ("banner-policy-12-237", "GL-396211", "Mvasi", "BEVACIZUMAB-AWWB INJECTION", "Mvasi (Bevacizumab-awwb) Injection", "The named October 2025 guideline identifies Mvasi and Zirabev as preferred. The October 2026 formulary does not specify preference for this row. Exact package eligibility is unverified."),
  "banner-full-6c72cfb332a399ef": ("banner-policy-12-237", "GL-396211", "Zirabev", "BEVACIZUMAB-BVZR INJECTION", "Zirabev (Bevacizumab-bvzr) Injection", "The named October 2025 guideline identifies Mvasi and Zirabev as preferred. The October 2026 formulary does not specify preference for this row. Exact package eligibility is unverified."),
  "banner-full-96013cd1d8204447": ("banner-policy-12-1754", "GL-99771", "generic bexarotene caps", "BEXAROTENE CAPSULES", "Bexarotene Capsules (Banner Formulary)", "The named guideline includes both capsules and Targretin gel. This formulary row is capsules only. Separate CTCL and NCCN initial and renewal criteria apply; gel coverage is not established by this row."),
  "banner-full-04d6c166dbdc7a8a": ("banner-policy-12-1422", "GL-700354", "generic bosentan tablet for", "BOSENTAN TABLETS SOLUBLE", "Bosentan Tablets for Oral Suspension (Tracleer Reference)", "The September 2026 guideline identifies generic tablets for oral suspension as preferred, but brand Tracleer and generic conventional tablets as nonpreferred. Exact brand/package eligibility is unverified."),
  'banner-full-df471ac18a4edcdf': ('banner-policy-12-1422', 'GL-700354', 'generic ambrisentan', 'AMBRISENTAN TABLETS', 'Ambrisentan Tablets (Letairis Reference)', 'The September 1 policy identifies generic ambrisentan as preferred and brand Letairis as nonpreferred. The October formulary lists ambrisentan tablets with Letairis as the reference brand. Exact brand/package eligibility is unverified.'),
  'banner-full-42e11b3c0513cedb': ('banner-policy-12-259', 'GL-99541', 'generic anastrozole', 'ANASTROZOLE TABLETS', 'Anastrozole Tablets (Arimidex Reference)', 'The October formulary lists PA and does not specify preference. The named policy has a breast cancer branch and separate NCCN initial and renewal branches; review the applicable branch.'),
 }
 found_banner=set()
 for r in data['medications']:
  if r['id'] not in banner_reviewed:continue
  pid,code,product,original,label,note=banner_reviewed[r['id']]
  assert r['planId']=='banner-ufc' and r['name']==original and r['pa']=='required'
  p=policies[pid];assert p['planId']=='banner-ufc'
  raw=(ROOT/'dist'/p['sourceTextUrl'].lstrip('./')).read_text()
  assert code in raw and product.lower() in raw.lower()
  link=dict(policyId=pid,title=p['name'],policyCode=code,firstPage=p['sourcePage'],lastPage=p.get('sourceLastPage',p['sourcePage']),url=p['sourceUrl'],textUrl=p['sourceTextUrl'],effective=p.get('policyEffective') or p.get('sourceEffective',''),matchedProduct=product,scope='Named same-plan policy; review the applicable product, indication and stage.')
  links=r.setdefault('policySources',[])
  if not any(x.get('policyId')==pid or x.get('textUrl')==link['textUrl'] for x in links):links.insert(0,link);count+=1;records.add(r['id'])
  r['reviewedPresentation']={'separate':True,'label':label,'note':note}
  found_banner.add(r['id'])
 assert found_banner==set(banner_reviewed), 'Missing reviewed Banner formulary row'
 print(f'Added {count} same-plan policy links across {len(records)} medication records')
 return count
