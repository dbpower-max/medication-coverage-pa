"""Build current distinct FFS/AIHP records after full independent cell validation.
Never applies this FFS formulary to managed-care plans. Keeps PA type prose verbatim.
"""
import json,re,hashlib,collections,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from export_data import category_for
OUT=ROOT/'audits/ffs_complete_2026_11_12'
def main():
 a=json.loads((OUT/'extracted.json').read_text());assert not a['fragments'] and not a['independent_mismatches']
 rows=[];corrections=[];miotics=False
 for r in a['rows']:
  if r['cells']==['MIOTICS']+['']*8:
   corrections.append(dict(position=[r[k] for k in ['page','table','row']],kind='unmarked_class_heading',evidence='Page41 grey shaded class row, verified in page41-review.png',cells=r['cells']));miotics=True;continue
  if miotics and r['page']==41:
   if r['cells'][0]=='PILOCARPINE HCL SOLUTION':r['class_name']='MIOTICS';miotics=False
  rows.append(r)
 groups=collections.OrderedDict()
 for r in rows:groups.setdefault(tuple(r['cells'][:2]),[]).append(r)
 records=[];conflicts=[];identity_held=[]
 for (name,brand),rs in groups.items():
  if len({tuple(r['cells'][2:]) for r in rs})>1:conflicts.append(rs);continue
  r=rs[0];c=r['cells'];pa_text=c[4];positive=bool(re.search(r'\bPA\s+REQUIRED\b',pa_text,re.I))
  if positive:
   pa='conditional' if re.search(r'\bFOR\b|\bUNLESS\b|[<>]|\bONLY\b|\bAGES?\b|\bYEARS?\b|not required|\bif member\b',pa_text,re.I) else 'required'
  elif re.search(r'\b(?:PA|Prior Authorization)\b',pa_text,re.I):pa='conditional'
  else:pa='not_specified'
  pref='preferred' if c[3]=='PREFERRED DRUG' else 'not_specified'
  note=c[2]
  caveats=[]
  if c[3] and c[3]!='PREFERRED DRUG':note+=' Printed preference qualifier: '+c[3]+'.';caveats.append('NDC-specific preference' if 'NDC' in c[3] else 'Age-dependent preference')
  if pa_text and not positive and pa=='not_specified':note+=' Source restriction (not a printed PA requirement): '+pa_text
  if 'Covered for Members' in pa_text or 'Minimum Patient Age' in pa_text:caveats.append('Age-specific coverage')
  if 'Opioid Treatment Program' in pa_text:caveats.append('Restricted treatment site')
  if 'buy and bill a medical claim' in pa_text:caveats.append('Medical buy-and-bill')
  if c[8]=='X':note+=' Maintenance indicator X: source permits 90-day supply for maintenance drugs; printed quantity and other restrictions still apply.'
  if not positive and pa=='conditional':note+=' The row states a conditional PA exception; it does not establish a general exemption or a PA requirement outside that exception.'
  record=dict(id='ffs-nov-'+hashlib.sha256((name+'|'+brand).encode()).hexdigest()[:16],recordType='formulary',planId='ahcccs-ffs-aihp',name=name,brand=brand,notes=note.strip(),category=category_for(r['class_name'],name,brand),subcategory=r['class_name'],coverage='listed',preferred=pref,pa=pa,paText=pa_text,step='specified' if c[5] else 'not_specified',stepText=c[5],qlAmount=c[6],qlDays=c[7],ageLimited=bool(re.search(r'\bAge|\bYear',pa_text,re.I)),maintenanceIndicator=c[8]=='X',sourcePreferenceText=c[3],brandGenericNotes=c[2],conditions=[],sourceTitle='AHCCCS Fee-For-Service Acute/Long Term Care Program Drug List',sourceEffective='2026-11-01',sourcePage=r['page'],sourcePages=sorted({v['page'] for v in rs}),sourceUrl='/sources/ahcccs-ffs-aihp-2026-11-01.pdf',validation='source_table_verified_independent_cells',sourcePositions=[{k:v[k] for k in ['page','table','row']} for v in rs],sourceConflict='')
  if caveats:record['coverageCaveat']='; '.join(caveats)
  records.append(record)
 assert len(records)==1810 and len(rows)==1813 and not conflicts
 assert all(r['pa']!='required' for r in records if r['paText'].startswith(('Covered for Members','Minimum Patient')) and 'PA REQUIRED' not in r['paText'])
 registry=dict(planId='ahcccs-ffs-aihp',product='AHCCCS Fee-For-Service / American Indian Health Program',effectiveDate='2026-11-01',retrieved='2026-11-12',officialFormulary=a['source']['official_url'],archivedFormulary='/sources/ahcccs-ffs-aihp-2026-11-01.pdf',sha256=a['source']['sha256'],pageCount=48,pharmacyHub='https://www.azahcccs.gov/Resources/GuidesManualsPolicies/pharmacyupdates.html',paCriteriaSource='https://www.azahcccs.gov/Resources/Downloads/PharmacyUpdates/2026/AZMFileseff110126AllGuidelines.pdf',stepQuantitySource=a['source']['official_url'],epaSource=None,adoptionSources=[dict(url='https://www.azahcccs.gov/PlansProviders/RatesAndBilling/FFS/formulary.html',evidence='Official page defines FFS formulary for FFS program members; explicitly not applicable to health-plan members.'),dict(url='https://www.azahcccs.gov/Resources/GuidesManualsPolicies/pharmacyupdates.html',evidence='Official AIHP Drug Lists section links the exact November1,2026 FFS PDF as AHCCCS American Indian Health Plan Drug List.'),dict(url='https://www.azahcccs.gov/AmericanIndians/Providers/',evidence='AIHP is acute FFS. Official FAQ identifies Tribal ALTCS, including Pascua Yaqui and Tohono Oodham, as FFS programs, subject to member enrollment and service/billing context.')],scopeCaveat='This FFS list must not substitute for an MCO formulary. Medicare dual-eligible/PartD benefits and Tribal/IHS dispensing/billing require applicable program rules; no automatic MCO or PartD mapping.')
 report=dict(source=a['source'],rawCandidatePositions=a['printed_candidate_positions'],additionalClassHeadings=corrections,printedProductPositions=len(rows),distinctReleasedProducts=len(records),identicalDuplicateGroups=[dict(name=k[0],brand=k[1],positions=[{f:r[f] for f in ['page','table','row']} for r in rs]) for k,rs in groups.items() if len(rs)>1],conflictingDuplicateGroups=conflicts,heldIdentityRows=identity_held,independentCellDifferences=0,paCounts=dict(collections.Counter(r['pa'] for r in records)),preferenceCounts=dict(collections.Counter(r['preferred'] for r in records)),maintenanceCount=sum(r['maintenanceIndicator'] for r in records),limitations=['Complete published FFS drug-list extraction, not a claim that all potential benefits or member-specific coverage are verified.','Detailed PA approval/renewal criteria are a separate November PDF handled by root.','Two conditional preferred-status cells preserve NDC/age qualifiers; no universal preference inferred.','Vaccine age restrictions and treatment-site notes are not automatically converted into PA requirements.'])
 (OUT/'proposed_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));(OUT/'source_registry.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2));(OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:report[k] for k in ['printedProductPositions','distinctReleasedProducts','paCounts','preferenceCounts','maintenanceCount']},indent=2))
if __name__=='__main__':main()
