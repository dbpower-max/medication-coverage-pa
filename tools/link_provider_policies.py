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
  assert code in raw and product.lower() in ' '.join(raw.lower().split())
  link=dict(policyId=pid,title=p['name'],policyCode=code,firstPage=p['sourcePage'],lastPage=p.get('sourceLastPage',p['sourcePage']),url=p['sourceUrl'],textUrl=p['sourceTextUrl'],effective=p.get('policyEffective') or p.get('sourceEffective',''),matchedProduct=product,scope='Named same-plan policy; review the applicable product, indication and stage.')
  links=r.setdefault('policySources',[])
  if not any(x.get('policyId')==pid or x.get('textUrl')==link['textUrl'] for x in links):links.insert(0,link);count+=1;records.add(r['id'])
  r['reviewedPresentation']={'separate':True,'label':label,'note':note}
  found_banner.add(r['id'])
 assert found_banner==set(banner_reviewed), 'Missing reviewed Banner formulary row'
 # Exact source rows with reviewed named policy; retain existing renderer presentation.
 banner_exact_links = {
  "banner-full-015b1506addec038": ("banner-policy-12-351", "GL-356254", "famciclovir tabs", "FAMCICLOVIR TABLETS", "required", "not_specified", "Named famciclovir tablet branch, 12-month approval; separate renewal stage not specified. Do not infer brand eligibility."),
  "banner-full-b1b2bf86bd6d4857": ("banner-policy-12-1099", "GL-611235", "fentanyl transdermal", "FENTANYL PATCH 72-HOUR 12mcg, 25mcg, 50mcg, 75mcg & 100mcg", "required", "preferred", "Preferred transdermal patch rates: 12, 25, 50, 75 and 100 mcg/hr; distinct cancer/hospice and noncancer initial/renewal pathways and separate DUR, MME and quantity-review branches. This is not the transmucosal fentanyl policy."),
  "banner-full-e6a1b62352bfbc70": ("banner-policy-12-351", "GL-356254", "Foscavir inj", "FOSCARENT SODIUM", "required", "not_specified", "Named Foscavir injection criteria; CMV and compendium-supported covered indications; 12-month approval, separate renewal stage not specified. Original payer spelling retained."),
  "banner-full-d17bd539fa8f578f": ("banner-policy-12-305", "GL-734190", "Emgality 120 mg/ml", "GALCANEZUMAB-GNLM SOLN AUTO-INJ", "required", "preferred", "120 mg/mL prefilled pen for adult migraine prevention; 6-month initial and 12-month renewal. The pediatric branch is Ajovy only; the 100 mg/mL cluster headache branch is syringe only. Exact package eligibility unverified."),
  "banner-full-f4e7ff20751921ce": ("banner-policy-12-305", "GL-734190", "Emgality 100 mg/mL", "GALCANEZUMAB-GNLM SOLN PREF SYR", "required", "preferred", "Adult migraine prevention uses the 120 mg/mL syringe (6-month initial, 12-month renewal); episodic cluster headache uses the 100 mg/mL syringe (3-month initial, 12-month renewal). Exact covered strength and package not printed."),
  "banner-full-3426a5ee04aae9ee": ("banner-policy-12-351", "GL-356254", "Cytovene inj, generic ganciclovir inj", "GANCICLOVIR SODIUM", "required", "not_specified", "Named ganciclovir injection branch; CMV and compendium-supported covered indications; 12-month approval, separate renewal stage not specified."),
  "banner-full-0b18cd1fd8a34f98": ("banner-policy-12-129", "GL-620204", "granisetron tablet", "GRANISETRON HCL TABLETS", "required", "not_specified", "Tablet branch; chemotherapy, radiotherapy and postoperative prevention have different approval lengths. Granisol oral solution-only swallowing and ondansetron ODT criteria do not apply to tablets."),
  "banner-full-40d2ce2b10232236": ("banner-policy-12-1413", "GL-242221", "generic lansoprazole ODT", "LANSOPRAZOLE ORALLY DISPERSABLE TABLET (ODT)", "conditional", "preferred", "October formulary prints PA for age greater than 18; November policy distinguishes under 18 from 18 and older, including inability to swallow solid forms for the latter. Exact handling at age 18 is unresolved. No self-step through lansoprazole ODT; generic policy only."),
  "banner-full-dc42f2a6c586a16a": ("banner-policy-12-357", "GL-642203", "Nivestym", "FILGRASTIM-AAFI SOLN PREF SYR", "required", "preferred", "Nivestym is a named preferred product in the shared CSF policy. The exact syringe and indication must be checked separately; the shared policy includes off-label uses and does not establish interchangeability or package eligibility."),
  "banner-full-5446ad5479340eeb": ("banner-policy-12-357", "GL-642203", "Nivestym", "FILGRASTIM-AAFI SOLUTION", "required", "preferred", "Nivestym is a named preferred product in the shared CSF policy. The exact solution presentation and indication must be checked separately; the shared policy includes off-label uses and does not establish interchangeability or package eligibility."),
  "banner-full-73d3701a5467c050": ("banner-policy-12-357", "GL-642203", "Releuko", "FILGRASTIM-AYOW", "required", "preferred", "Releuko is a named preferred product in the shared CSF policy. The formulary does not specify its presentation; exact product, indication and package must be verified. Shared criteria include off-label uses."),
  "banner-full-f0147593c0e3df11": ("banner-policy-12-305", "GL-734190", "Ajovy", "FREMANEZUMAB-VFRM SOLN AUTO-INJ", "required", "preferred", "Migraine prevention: separate initial and renewal branches; pediatric eligibility applies only to episodic migraine for Ajovy ages 6–17 and weight at least 45 kg. Verify age-specific device labeling; the policy does not establish exact package eligibility."),
  "banner-full-1216731a2ac10ef5": ("banner-policy-12-305", "GL-734190", "Ajovy", "FREMANEZUMAB-VFRM SOLN PREF SYR", "required", "preferred", "Migraine prevention: separate initial and renewal branches; pediatric eligibility applies only to episodic migraine for Ajovy ages 6–17 and weight at least 45 kg. Verify age-specific device labeling; the policy does not establish exact package eligibility."),
  "banner-full-146f9141864dbe2a": ("banner-policy-12-1321", "GL-731214", "Brand Iressa, generic gefitinib", "GEFITINIB TABLETS", "required", "not_specified", "Named oral oncology cancer branch: NCCN category 1, 2A or 2B. Do not apply the separate imatinib step requirement. No separately stated renewal stage; exact package eligibility unverified."),
  "banner-full-dfa5cdbe92a21695": ("banner-policy-12-798", "GL-371191", "Mavyret", "GLECAPREVIR-PIBRENTASVIR PACKETS", "conditional", "preferred", "Preferred one-time lifetime course without PA; retreatment requires PA. Preserve printed packet-specific 280 per lifetime limit; do not transfer tablet quantities. Policy names Mavyret, not the exact packet package."),
  "banner-full-d4b82dd7596688b0": ("banner-policy-12-798", "GL-371191", "Mavyret", "GLECAPREVIR-PIBRENTASVIR TABLETS", "conditional", "preferred", "Preferred one-time lifetime course without PA; retreatment requires PA. Preserve printed tablet-specific 168 per lifetime limit; do not transfer packet quantities. Policy names Mavyret, not the exact tablet package."),
  "banner-full-f0dac8422def3d7b": ("banner-policy-12-1896", "GL-450243", "Brand Ravicti", "GLYCEROL PHENYLBUTYRATE LIQUID", "required", "not_specified", "Urea cycle disorder initial and renewal branches; generic glycerol phenylbutyrate alone has the additional brand Ravicti failure/intolerance requirement. October brand-only flag is retained; no separate generic eligibility inferred."),
  "banner-full-1ecc15f32d5c5aa0": ("banner-policy-12-1193", "GL-715190", "generic dalfampridine", "DALFAMPRIDINE TABLET ER 12HR", "required", "not_specified", "MS guideline: generic dalfampridine is preferred; brand Ampyra is nonpreferred. Separate initial and renewal branches. The formulary row does not specify preference; exact brand/package eligibility is unverified."),
  "banner-full-c3c6e41b892ea1d1": ("banner-policy-12-681", "GL-731220", "Bildyos", "DENOSUMAB-NXXP SOLN PREF SYR", "required", "not_specified", "Bildyos osteoporosis branch; preferred in the guideline, preference unspecified in the formulary. Separate initial and renewal criteria. The shared renewal text refers to cumulative PTH analog use, not a verified Bildyos lifetime cap."),
  "banner-full-b93efaf3c38dcf21": ("banner-policy-12-183", "GL-155386", "Austedo XR", "DEUTETRABENAZINE TABLET ER 24HR", "required", "not_specified", "Austedo XR tablet: separate tardive dyskinesia and Huntington chorea initial and renewal criteria. One active strength PA; titration-kit eligibility is not established. Preserve the XR tablet quantity limit."),
  "banner-full-13ebf33d7a321470": ("banner-policy-12-1193", "GL-715190", "generic dimethyl fumarate capsules", "DIMETHYL FUMARATE CAPSULE DELAYED RELEASE", "required", "not_specified", "Generic dimethyl fumarate capsules are preferred in the guideline, branded Tecfidera capsules and starter packs are nonpreferred. Formulary preference and exact brand/package eligibility are unverified."),
  "banner-full-c144470bcd338e8c": ("banner-policy-12-811", "GL-525295", "Kalbitor", "ECALLANTIDE SOLUTION", "required", "preferred", "Preferred acute HAE branch: age 12 or older; nonpreferred-agent step requirements do not apply. Exact package eligibility is unverified."),
  "banner-full-30fc49366041be95": ("banner-policy-12-601", "GL-642233", "Afinitor Disperz", "EVEROLIMUS SOLUBLE TABLET", "required", "not_specified", "Generic tablet for oral suspension preferred in the guideline; brand Afinitor Disperz nonpreferred. Preferred product approval is NDC-specific. Exact package eligibility is unverified; do not transfer transplant or conventional-tablet coverage."),
  'banner-full-ea0529db441446f6': ('banner-policy-12-811', 'GL-525295', 'Berinert', 'C1 ESTERASE INHIBITOR (HUMAN) SOLUTION', 'required', 'preferred', 'Acute HAE branch; product-specific age and step conditions must not be transferred.'),
  'banner-full-81af49ca953b804f': ('banner-policy-12-811', 'GL-525295', 'Cinryze, Haegarda', 'C1 ESTERASE INHIBITOR (HUMAN) SOLUTION RECONSTITUTED', 'required', 'not_specified', 'Prophylaxis branch names both; acute off-label branch names Cinryze only. Individual package eligibility is unverified.'),
  'banner-full-f1d24c36af2451fa': ('banner-policy-12-105', 'GL-545202', 'Xcopri', 'CENOBAMATE TAB THER PACK', 'required', 'not_specified', 'Named Xcopri policy; therapeutic pack not separately named.'),
  'banner-full-b2b56363cbca0ab9': ('banner-policy-12-105', 'GL-545202', 'Xcopri', 'CENOBAMATE TABLET', 'required', 'not_specified', 'Named Xcopri policy; other agents have different criteria.'),
  'banner-full-ffeacef3b187fde3': ('banner-policy-12-156', 'GL-126970', 'generic clorazepate dipotassium', 'CLORAZEPATE DIPOTASSIUM TAB 15 MG', 'conditional', 'not_specified', 'Under-six or concurrent anxiolytic DUR branches; preserve printed quantity limit.'),
  'banner-full-289217947e14a99e': ('banner-policy-12-156', 'GL-126970', 'generic clorazepate dipotassium', 'CLORAZEPATE DIPOTASSIUM TAB 3.75 MG', 'conditional', 'not_specified', 'Under-six or concurrent anxiolytic DUR branches; preserve printed quantity limit.'),
  'banner-full-08918817a94bbfa0': ('banner-policy-12-156', 'GL-126970', 'generic clorazepate dipotassium', 'CLORAZEPATE DIPOTASSIUM TAB 7.5 MG', 'conditional', 'not_specified', 'Under-six or concurrent anxiolytic DUR branches; preserve printed quantity limit.'),
 }
 found=set()
 for r in data['medications']:
  if r['id'] not in banner_exact_links:continue
  pid,code,product,original,pa,preference,scope=banner_exact_links[r['id']]
  assert r['planId']=='banner-ufc' and r['name']==original and r['pa']==pa and r['preferred']==preference
  p=policies[pid];assert p['planId']=='banner-ufc'
  raw=(ROOT/'dist'/p['sourceTextUrl'].lstrip('./')).read_text()
  assert code in raw and product.lower() in ' '.join(raw.lower().split())
  link=dict(policyId=pid,title=p['name'],policyCode=code,firstPage=p['sourcePage'],lastPage=p.get('sourceLastPage',p['sourcePage']),url=p['sourceUrl'],textUrl=p['sourceTextUrl'],effective=p.get('policyEffective') or p.get('sourceEffective',''),matchedProduct=product,scope=scope)
  links=r.setdefault('policySources',[])
  if not any(x.get('policyId')==pid or x.get('textUrl')==link['textUrl'] for x in links):links.insert(0,link);count+=1;records.add(r['id'])
  found.add(r['id'])
 assert found==set(banner_exact_links), 'Missing exact Banner policy-linked row'
 print(f'Added {count} same-plan policy links across {len(records)} medication records')
 return count
