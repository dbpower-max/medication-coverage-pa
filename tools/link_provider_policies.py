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
  "banner-full-b20b5312833f8841": ("banner-policy-12-1193", "GL-715190", "Avonex", "INTERFERON BETA-1A AUTO-INJECTOR KIT", "required", "not_specified", "Avonex is named in the preferred MS initial branch (page 1193), 12 months; positive clinical response for renewal (page 1195), 12 months. October formulary preference is unspecified. Exact device/package eligibility is unverified; nonpreferred step does not apply to the named preferred branch."),
  "banner-full-46cc6b2b57f100b3": ("banner-policy-12-1193", "GL-715190", "Avonex", "INTERFERON BETA-1A PREFILLED SYRINGE KIT", "required", "not_specified", "Avonex is named in the preferred MS initial branch (page 1193), 12 months; positive clinical response for renewal (page 1195), 12 months. October formulary preference is unspecified. Exact device/package eligibility is unverified; nonpreferred step does not apply to the named preferred branch."),
  "banner-full-fe7518236db69cb0": ("banner-policy-12-1193", "GL-715190", "Rebif", "INTERFERON BETA-1A SOLN AUTO-INJ", "required", "not_specified", "Rebif is named in the preferred MS initial branch (page 1193), 12 months; positive clinical response for renewal (page 1195), 12 months. October formulary preference is unspecified. Exact device/package eligibility is unverified; nonpreferred step does not apply to the named preferred branch."),
  "banner-full-5fb305c6fb16021c": ("banner-policy-12-721", "GL-734191", "Eligard", "LEUPROLIDE ACETATE (3 MONTH) INJECTABLE", "required", "not_specified", "Eligard is named in the advanced or metastatic prostate-cancer branch, page 734; 12 months. Preferred in guideline, preference unspecified in October row. Do not apply Lupron Depot nonpreferred step or CPP criteria."),
  "banner-full-fd34a1dfbfb6a466": ("banner-policy-12-721", "GL-734191", "Eligard", "LEUPROLIDE ACETATE (4 MONTH) KIT", "required", "not_specified", "Eligard is named in the advanced or metastatic prostate-cancer branch, page 734; 12 months. Preferred in guideline, preference unspecified in October row. Do not apply Lupron Depot nonpreferred step or CPP criteria."),
  "banner-full-01c3982354a89897": ("banner-policy-12-721", "GL-734191", "Eligard", "LEUPROLIDE ACETATE (6 MONTH) KIT", "required", "not_specified", "Eligard is named in the advanced or metastatic prostate-cancer branch, page 734; 12 months. Preferred in guideline, preference unspecified in October row. Do not apply Lupron Depot nonpreferred step or CPP criteria."),
  "banner-full-79cf3f8c029341a9": ("banner-policy-12-721", "GL-734191", "Fensolvi", "LEUPROLIDE ACETATE (CPP) (6 MONTH) KIT", "required", "not_specified", "CPP initial and renewal branches, pages 721–724; 12 months each. Preferred in guideline; October preference unspecified. Age limits for gender dysphoria in the separate October 14, 2026 policy do not apply to CPP. Other indications require their own branch; not a blanket coverage determination."),
  "banner-full-81df8d84d1f32707": ("banner-policy-12-721", "GL-734191", "Lupron Depot-Ped (1-month)", "LEUPROLIDE ACETATE (CPP) KIT", "required", "not_specified", "CPP initial and renewal branches, pages 721–724; 12 months each. Preferred in guideline; October preference unspecified. Age limits for gender dysphoria in the separate October 14, 2026 policy do not apply to CPP. Other indications require their own branch; not a blanket coverage determination."),
  "banner-full-b720c6ff93fb1ac3": ("banner-policy-12-1576", "GL-709190", "generic hydromorphone tablets", "HYDROMORPHONE HCL TABLETS", "conditional", "not_specified", "Printed PA applies to more than two short-acting opioids in 30 days. Corresponding policy branch pp1578–1579 covers dose adjustment, replacement, or documented necessity; duration up to 12 months. Generic tablets preferred in guideline; brand Dilaudid nonpreferred. Other DUR/MME/QL branches separate."),
  "banner-full-852b41b52868cf72": ("banner-policy-12-78", "GL-105169", "Intron A", "INTERFERON ALFA-2B SOLUTION", "required", "not_specified", "Intron A branch pp78–80: documentation of one of the listed indications, 12 months. No distinct renewal; do not apply Alferon N criteria. Current package availability unverified."),
  "banner-full-30fc4f26a9ae9605": ("banner-policy-12-78", "GL-105169", "Alferon N", "INTERFERON ALFA-N3 SOLUTION", "required", "not_specified", "Alferon N branch pp80–81: refractory or recurrent external HPV condylomata acuminata, documented; eight weeks. No distinct renewal; do not apply Intron A criteria. Current package availability unverified."),
  "banner-full-0272cfe23aa2123e": ("banner-policy-12-1365", "GL-105258", "Sklice", "IVERMECTIN LOTION", "required", "not_specified", "Topical head lice branch, 30 days. Generic spinosad failure requirement applies to brand Natroba only. No separate renewal; exact package eligibility unverified."),
  "banner-full-24223240af77db72": ("banner-policy-12-1321", "GL-731214", "Imbruvica", "IBRUTINIB CAPSULES", "required", "not_specified", "Oral oncology NCCN category 1, 2A or 2B; 12 months. Capsule package not specified; the separate imatinib brand step does not apply."),
  "banner-full-3562c19cd796ad78": ("banner-policy-12-1321", "GL-731214", "Imbruvica", "IBRUTINIB SUSPENSION", "required", "not_specified", "Oral oncology NCCN category 1, 2A or 2B; 12 months. Suspension package not specified; the separate imatinib brand step does not apply."),
  "banner-full-1ae1517495876514": ("banner-policy-12-811", "GL-525295", "Generic icatibant", "ICATIBANT ACETATE SOLUTION", "required", "preferred", "Preferred generic acute HAE branch, age 18 or older; 12 months. Nonpreferred-agent step does not apply. Exact package eligibility unverified."),
  "banner-full-559d389f3b8ed5ff": ("banner-policy-12-1321", "GL-731214", "Brand Gleevec, generic imatinib, Imkeldi", "IMATINIB MESYLATE TABLETS", "required", "not_specified", "Cancer NCCN category 1, 2A or 2B; 12 months. The additional generic imatinib failure requirement applies to brand Gleevec or Imkeldi requests only. This tablet row does not establish brand eligibility."),
  "banner-full-2a684512a53f1ec8": ("banner-policy-12-1321", "GL-731214", "Brand Tykerb, generic lapatinib", "LAPATINIB DITOSYLATE TABLETS", "required", "not_specified", "Named oral oncology cancer branch; NCCN category 1, 2A or 2B; 12 months. The separate imatinib step does not apply. Exact package eligibility unverified."),
  "banner-full-21719e40e35b7441": ("banner-policy-12-1321", "GL-731214", "Brand Revlimid, generic lenalidomide", "LENALIDOMIDE CAPSULE", "required", "not_specified", "Named oral oncology cancer branch; NCCN category 1, 2A or 2B; 12 months. October brand-only restriction retained; the generic mention in the guideline does not establish generic coverage."),
  "banner-full-a485618380e6e997": ("banner-policy-12-1071", "GL-427190", "Leucovorin tablets", "LEUCOVORIN CALCIUM TABLETS", "required", "not_specified", "Tablet policy: methotrexate toxicity prophylaxis, hematologic toxicity from folic acid antagonists, or documented cerebral folate deficiency. Twelve months; no separate renewal. Do not transfer to injection."),
  "banner-full-1710dea660c37719": ("banner-policy-12-468", "GL-357222", "Xiidra", "LIFITEGRAST SOLUTION", "required", "not_specified", "Xiidra preferred in guideline; October preference unspecified. Separate 12-month initial and renewal branches. Initial requires qualifying diagnosis, documented testing, lubricant trial, specialist and brand Restasis single-dose trial unless contraindicated; renewal requires positive response."),
  "banner-full-a4a289cc6cd11b2a": ("banner-policy-12-379", "GL-715189", "Linzess", "LINACLOTIDE CAPSULES", "required", "not_specified", "Separate 12-month initial and renewal. IBS-C age 7 or older; CIC age 18 or older; functional constipation age 2–17 only for 72 mcg requests. Generic lubiprostone and prucalopride steps both apply to new starts only. Exact package eligibility unverified."),
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
 # Named chapter reference only; route and indication applicability remain scoped.
 banner_ig_scope = {
  "banner-full-3a476647011e0ef8": ("IMMUNE GLOBULIN (HUMAN) IV OR SUBCUTANEOUS SOLUTION", "not_specified", "Gammagard liquid", "Gammagard Liquid, Gammaked and Gamunex-C named. PI branch distinguishes IV and SC dosing (pp929–931); MMN (pp910–912) and DM/PM (pp889–891) are IVIG-specific. FDA-labeled adult MMN applies to Gammagard Liquid, not Liquid ERC or all grouped products. Exact brand/package and indication require separate verification."),
  "banner-full-b99ccac646481857": ("IMMUNE GLOBULIN (HUMAN) IV SOLUTION", "preferred", "Bivigam", "Shared IV product row. Octagam 5% labeled PI; 10% labeled adult ITP/dermatomyositis. DM/PM (pp889–891), MMN (pp910–912) and PI (pp929–931) have separate criteria; no blanket transfer to every IV product. Exact package/indication unverified."),
  "banner-full-31c646f5de1a7360": ("IMMUNE GLOBULIN (HUMAN) IV SOLUTION RECONSTITUTED", "preferred", "Gammagard S-D", "Gammagard S/D is a reconstituted IV product, distinct from Liquid and Liquid ERC. PI pp929–931; broad MMN and DM/PM branches do not establish a labeled indication or benefit for S/D."),
  "banner-full-8e1bca979c1c79f5": ("IMMUNE GLOBULIN (HUMAN) SUBCUTANEOUS SOLN PREF SYR", "preferred", "Hizentra", "Hizentra SC prefilled syringe: PI pp929–931 uses labeled SC dosing. CIDP initial pp885–886, DM/PM pp889–891 and MMN pp910–912 specify IVIG dosing; do not transfer that dosing to SC. Hizentra adult CIDP maintenance label does not resolve payer SC CIDP criteria. Exact package unverified."),
  "banner-full-3393fbf3661bfb25": ("IMMUNE GLOBULIN (HUMAN) SUBCUTANEOUS SOLUTION", "preferred", "Hizentra", "Hizentra SC solution: PI pp929–931 uses labeled SC dosing. CIDP initial pp885–886, DM/PM pp889–891 and MMN pp910–912 specify IVIG dosing; do not transfer that dosing to SC. Hizentra adult CIDP maintenance label does not resolve payer SC CIDP criteria. Exact package unverified."),
  "banner-full-449f33903bd3010c": ("IMMUNE GLOBULIN (HUMAN)- HIPP SOLUTION", "not_specified", "Cutaquig", "Cutaquig 16.5% SC, labeled PI. PI pp929–931 distinguishes SC dosing; CIDP, DM/PM and MMN branches specify IVIG dosing and cannot be transferred to this SC product. Exact package and other indications unverified."),
  "banner-full-20163d7b5f42cae1": ("IMMUNE GLOBULIN (HUMAN)- KLHW SOLUTION", "preferred", "Xembify", "Xembify 20% SC, labeled PI. PI pp929–931 distinguishes SC dosing; CIDP, DM/PM and MMN branches specify IVIG dosing and cannot be transferred to this SC product. Exact package and other indications unverified."),
 }
 for rid,(name,pref,product,note) in banner_ig_scope.items():
  banner_exact_links[rid]=('banner-policy-12-877','GL-525296',product,name,'required',pref,note)
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
  same=next((i for i,x in enumerate(links) if x.get('policyId')==pid or x.get('textUrl')==link['textUrl']),None)
  if same is None:links.insert(0,link);count+=1;records.add(r['id'])
  else:links[same]={**links[same],**link}
  found.add(r['id'])
 assert found==set(banner_exact_links), 'Missing exact Banner policy-linked row'
 # Keep broad chapter source references, but make route-specific cautions visible at the prescribing option.
 # No additional structured approval rule or preference inference is introduced.
 seen_ig=set()
 seen_infliximab=False
 for r in data['medications']:
  if r['id'] in banner_ig_scope:
   name,pref,product,note=banner_ig_scope[r['id']]
   assert r['planId']=='banner-ufc' and r['name']==name and r['pa']=='required' and r['preferred']==pref
   r['reviewedPresentation']={**r.get('reviewedPresentation',{}),'note':note}
   seen_ig.add(r['id'])
  if r['id']=='banner-full-719caae0c9978dca':
   assert r['planId']=='banner-ufc' and r['name']=='INFLIXIMAB SOLUTION RECONSTITUTED' and r['pa']=='required' and r['preferred']=='preferred'
   r['reviewedPresentation']={**r.get('reviewedPresentation',{}),'separate':True,'label':'Infliximab (Janssen unbranded Remicade reference) IV powder for reconstitution','note':'October formulary prints Janssen authorized biosimilar only. The manufacturer identifies unbranded infliximab as Remicade under the same BLA, not a separately licensed biosimilar. Reference label: 100 mg IV single-use vial. Exact covered package and Banner indication/stage policy remain unverified; do not transfer preference to separate biosimilars or SC products.','labelUrl':'https://www.dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=a0a046c1-056d-45a9-bfd9-13b47c24f257','policyUnverified':True}
   seen_infliximab=True
 assert seen_ig==set(banner_ig_scope) and seen_infliximab, 'Missing reviewed IG or infliximab source row'

 # Preserve the exact payer's pediatric PA exception without presenting it as clinical endorsement.
 cough_safety={
  "banner-full-71027bfebf274e67": ("GUAIFENESIN-CODEINE SYRUP", "Guaifenesin / Codeine Oral Syrup"),
  "banner-full-997a2746536fd44b": ("HYDROCODONE W/ HOMATROPINE SYRUP", "Hydrocodone / Homatropine Oral Syrup"),
  "banner-full-a17980fe85989bde": ("HYDROCODONE W/ HOMATROPINE TABLETS", "Hydrocodone / Homatropine Oral Tablets"),
 }
 seen_cough=set()
 for r in data['medications']:
  if r['id'] not in cough_safety:continue
  name,label=cough_safety[r['id']]
  assert r['planId']=='banner-ufc' and r['name']==name and r['pa']=='conditional' and r['preferred']=='not_specified'
  r['reviewedPresentation']={**r.get('reviewedPresentation',{}),'separate':True,'label':label,'note':"FDA labeling for prescription opioid cough products limits use to adults 18 and older. The payer's under-18 PA exception is not FDA-labeled pediatric use or a prescribing recommendation. Exact package eligibility unverified.",'labelUrl':"https://www.fda.gov/drugs/postmarket-drug-safety-information-patients-and-providers/codeine-information"}
  seen_cough.add(r['id'])
 assert seen_cough==set(cough_safety), 'Missing exact cough safety row'
 # Keep concentration-specific PA unresolved rather than applying Lidoderm 5% criteria.
 topical_holds={
  "banner-full-53ebd7131685b7bf": ("LIDOCAINE PATCH", "Lidocaine Topical Patch (ZTlido Reference)", "Formulary PA applies only to 1.8% and 3.5% strengths. The named Lidoderm 5% policy is not verified for those concentrations; exact product-specific criteria are unavailable. Printed conditional PA and quantity limit retained."),
  "banner-full-89f80c3b6125808a": ("LIDOCAINE HCL LOTION", "Lidocaine HCl Topical Lotion (Lido-Sorb Reference)", "Formulary PA applies only to 3% lotion. Exact concentration-specific policy is unavailable; do not apply patch criteria. Printed conditional PA retained."),
 }
 found_topical=set()
 for r in data['medications']:
  if r['id'] not in topical_holds:continue
  name,label,note=topical_holds[r['id']]
  assert r['planId']=='banner-ufc' and r['name']==name and r['pa']=='conditional' and r['preferred']=='not_specified'
  r['reviewedPresentation']={**r.get('reviewedPresentation',{}),'separate':True,'label':label,'note':note,'policyUnverified':True}
  found_topical.add(r['id'])
 assert found_topical==set(topical_holds), 'Missing topical PA hold row'
 # Distinct labeled depot products and unresolved exact kit presentations.
 depot_presentations={
  "banner-full-5fb305c6fb16021c": ("LEUPROLIDE ACETATE (3 MONTH) INJECTABLE", "Eligard Reference — Leuprolide 3-Month SC Depot Injection", "Eligard is named in the advanced or metastatic prostate-cancer branch, page 734; 12 months. Preferred in guideline, preference unspecified in October row. Do not apply Lupron Depot nonpreferred step or CPP criteria. FDA-labeled Eligard 3-month depot is 22.5 mg subcutaneous; exact covered package is unverified. Not interchangeable with IM Lupron Depot.", "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b7b679a9-6823-4ef8-8d31-3ab5058ffcfc", False),
  "banner-full-fd34a1dfbfb6a466": ("LEUPROLIDE ACETATE (4 MONTH) KIT", "Eligard Reference — Leuprolide 4-Month SC Depot Injection Kit", "Eligard is named in the advanced or metastatic prostate-cancer branch, page 734; 12 months. Preferred in guideline, preference unspecified in October row. Do not apply Lupron Depot nonpreferred step or CPP criteria. FDA-labeled Eligard 4-month depot is 30 mg subcutaneous; exact covered package is unverified. Not interchangeable with IM Lupron Depot.", "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b7b679a9-6823-4ef8-8d31-3ab5058ffcfc", False),
  "banner-full-01c3982354a89897": ("LEUPROLIDE ACETATE (6 MONTH) KIT", "Eligard Reference — Leuprolide 6-Month SC Depot Injection Kit", "Eligard is named in the advanced or metastatic prostate-cancer branch, page 734; 12 months. Preferred in guideline, preference unspecified in October row. Do not apply Lupron Depot nonpreferred step or CPP criteria. FDA-labeled Eligard 6-month depot is 45 mg subcutaneous; exact covered package is unverified. Not interchangeable with IM Lupron Depot or CPP formulations.", "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b7b679a9-6823-4ef8-8d31-3ab5058ffcfc", False),
  "banner-full-79cf3f8c029341a9": ("LEUPROLIDE ACETATE (CPP) (6 MONTH) KIT", "Fensolvi Reference — Leuprolide 6-Month SC CPP Injection Kit", "CPP initial and renewal branches, pages 721–724; 12 months each. Preferred in guideline; October preference unspecified. Age limits for gender dysphoria in the separate October 14, 2026 policy do not apply to CPP. Other indications require their own branch; not a blanket coverage determination. FDA-labeled Fensolvi is 45 mg subcutaneous every 6 months for CPP; exact covered package unverified. Distinct from IM Lupron Depot-Ped.", "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=2c311700-edf4-4f2a-a468-9875489a6cc7", False),
  "banner-full-81df8d84d1f32707": ("LEUPROLIDE ACETATE (CPP) KIT", "Lupron Depot-Ped Reference — Leuprolide 1-Month IM CPP Injection Kit", "CPP initial and renewal branches, pages 721–724; 12 months each. Preferred in guideline; October preference unspecified. Age limits for gender dysphoria in the separate October 14, 2026 policy do not apply to CPP. Other indications require their own branch; not a blanket coverage determination. FDA-labeled 1-month Lupron Depot-Ped strengths are 7.5, 11.25 and 15 mg IM; 3- and 6-month products have different release schedules. Exact covered strength/package unverified.", "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e99f47d2-da10-3127-ecb3-e5d942ae6e81", False),
  "banner-full-ed9523c0d8429e9e": ("LEUPROLIDE ACETATE (3 MONTH) KIT", "Leuprolide 3-Month Injection Kit (Product Unverified)", "October formulary does not identify strength, route or exact depot product. The named 22.5 mg prostate-cancer policy branch cannot be assigned to this unspecified kit; no transfer from Eligard or Lupron Depot.", None, True),
  "banner-full-44032f1d9f0702a8": ("LEUPROLIDE ACETATE KIT", "Lupron Depot Reference — Leuprolide IM Depot Injection Kit", "October formulary does not specify strength or release schedule. Lupron Depot IM presentations have different strengths and indication-specific policies; monthly and longer-release strengths are not interchangeable. Exact benefit and branch unresolved.", "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=cbc8f94e-7330-4465-05ad-16d64493a5dd", True),
 }
 found_depot=set()
 for r in data['medications']:
  if r['id'] not in depot_presentations:continue
  name,label,note,url,hold=depot_presentations[r['id']]
  assert r['planId']=='banner-ufc' and r['name']==name and r['pa']=='required' and r['preferred']=='not_specified'
  presentation={**r.get('reviewedPresentation',{}),'separate':True,'label':label,'note':note,'policyUnverified':hold}
  if url:presentation['labelUrl']=url
  r['reviewedPresentation']=presentation
  found_depot.add(r['id'])
 assert found_depot==set(depot_presentations), 'Missing depot presentation row'
 # The October formulary and November guideline disagree at exactly age six.
 age_six_ingredients = {
     'AMITRIPTYLINE', 'AMOXAPINE', 'BUPROPION', 'CITALOPRAM', 'CLOMIPRAMINE',
     'DESIPRAMINE', 'DESVENLAFAXINE', 'DOXEPIN', 'DULOXETINE', 'ESCITALOPRAM',
     'FLUOXETINE', 'FLUVOXAMINE', 'IMIPRAMINE', 'MIRTAZAPINE', 'NORTRIPTYLINE',
     'PAROXETINE', 'PROTRIPTYLINE', 'SERTRALINE', 'TRAZODONE', 'TRIMIPRAMINE', 'VENLAFAXINE',
 }
 held_presentations = {
     'banner-full-0265ef7d56628527': (
         'MIGLUSTAT(AG) ORAL', 'Miglustat oral (authorized generic only)', 1312,
         'Banner lists PA for the authorized generic. The row omits strength, dosage form and reference product. The Opfolda criteria cannot be verified for this listing.'),
     'banner-full-cc76cd1e0045dbf1': (
         'VALBENAZINE TOSYLATE CAP THER PACK', 'Valbenazine capsule therapy pack', 957,
         'Banner lists PA and a therapy-pack quantity limit. Its Ingrezza guideline does not identify this pack. Exact pack criteria are unverified.'),
     'banner-full-a1e8bea060c802c9': (
         'VALBENAZINE TOSYLATE CAPSULE SPRINKLE', 'Valbenazine sprinkle capsule', 957,
         'Banner lists PA and a quantity limit for the sprinkle capsule. Its Ingrezza guideline does not identify the sprinkle presentation. Exact criteria are unverified.'),
 }
 seen_holds = set()
 for record in data['medications']:
     ingredient = record['name'].split()[0]
     if (record['planId'] == 'banner-ufc' and record.get('sourceEffective') == '2026-10-01'
         and '< 6 years' in record.get('paText', '')
         and any(link.get('firstPage') == 122 for link in record.get('policySources', []))
         and (ingredient in age_six_ingredients or ingredient == 'MAPROTILINE')):
         policy = next(p for p in data['policies'] if p['id'] == 'banner-policy-12-122')
         if ingredient == 'MAPROTILINE':
             page = 126
             note = 'Banner lists PA below age 6. Its November guideline lists maprotiline under nonpreferred drugs, without that age threshold. Exact age applicability is unresolved.'
         else:
             page = 123
             note = 'Banner lists PA below age 6. Its November guideline includes age 6 for the listed preferred presentations. The PA requirement at exactly age 6 is unresolved.'
         record['agePolicyConflict'] = {'note': note, 'page': page,
                                        'url': policy['sourceUrl'].split('#')[0] + f'#page={page}'}
     elif record['id'] in held_presentations:
         name, label, chapter, note = held_presentations[record['id']]
         assert record['name'] == name and record['pa'] == 'required' and record['planId'] == 'banner-ufc'
         record['reviewedPresentation'] = {
             **record.get('reviewedPresentation', {}), 'separate': True, 'label': label,
             'note': note, 'policyUnverified': True,
         }
         record['policySources'] = [link for link in record.get('policySources', [])
                                    if link.get('textUrl') != f'./banner-policy-text/12-{chapter}.txt']
         seen_holds.add(record['id'])
 assert seen_holds == set(held_presentations)
 print(f'Added {count} same-plan policy links across {len(records)} medication records')
 return count
