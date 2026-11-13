"""Attach program-specific source registries to the current release master."""
import json,sqlite3,gzip,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'dist';d=json.loads((D/'data.json').read_text());out=ROOT/'audits/ahcccs_release_2026_11_12';entries=[]
for p in d['plans']:
 if p.get('marketGroup')!='ahcccs':continue
 pid=p['id'];item=dict(planId=pid,product=p['name'],sourceVersion=p['effective'],sourceChecked='2026-11-12',epaSource=None,epaStatus='No electronic submission attempted or member benefit determination performed',completePublishedExactPlanFormulary=pid not in ['az-complete-health','az-complete-health-rbha'])
 if pid.startswith('mercy-'):
  item.update(officialFormulary=['https://www.mercycareaz.org/content/dam/mercycare/pdf/Mercy_Care_Formulary_Guide.pdf'],pharmacyHub='https://www.mercycareaz.org/providers/pharmacy.html',priorAuthorizationSourceRegistry='audits/mercy_pima_2026_11_12/source_registry.json',stepQuantitySource='Current Mercy PDL rows and separately published step/PA sources')
 elif pid.startswith('banner-'):
  item.update(officialFormulary=['https://www.bannerhealth.com/bhpprovider/resources/pharmacy/medicaid'],pharmacyHub='https://www.bannerhealth.com/bhpprovider/resources/pharmacy/medicaid',priorAuthorizationSourceRegistry='audits/banner_full/source_registry.json',stepQuantitySource='Archived October Banner PDL and November/current internal criteria',sourceIdentityExceptions=2)
 elif pid.startswith('uhc-'):
  item.update(officialFormulary=['https://www.uhcprovider.com/content/dam/provider/docs/public/commplan/az/pharmacy/AZ-Preferred-Drug-List-Medicaid.pdf'],pharmacyHub='https://www.uhcprovider.com/en/health-plans-by-state/arizona-health-plans/az-comm-plan-home/az-cp-pharmacy.html',priorAuthorizationSourceRegistry='audits/november_policy_index_2026_11_12/uhc-nov2026/source_registry.json',stepQuantitySource='Archived October UHC PDL and November guidelines; old front-matter examples not treated as current clinical rules',differences='25 differing exact-name PDF groups retained; undated machine-readable feed cannot resolve them')
 elif pid.startswith('az-complete-health'):
  item.update(officialFormulary=['https://www.azcompletehealth.com/providers/pharmacy.html'],pharmacyHub='https://www.azcompletehealth.com/providers/pharmacy.html',priorAuthorizationSourceRegistry='audits/ach_current_2026_11_12/public_source_registry.json',stepQuantitySource='Exact-plan notice/BHDL rows where stated; statewide QL/ST displayed only as reference for mandated-minimum overlay',outstanding='Additional integrated-plan products and unpublished drug-specific criteria still require payer documents' if pid!='az-complete-health-bh-only' else 'BHDL review date differs between linked PDF and hub labels; preserved')
 else:
  item.update(officialFormulary=['https://www.azahcccs.gov/Resources/GuidesManualsPolicies/pharmacyupdates.html'],pharmacyHub='https://www.azahcccs.gov/Resources/GuidesManualsPolicies/pharmacyupdates.html',priorAuthorizationSourceRegistry='audits/november_policy_index_2026_11_12/ahcccs-ffs-nov2026/source_registry.json',stepQuantitySource='Exact current FFS list or supplemental dual list, separately scoped')
  if pid=='ahcccs-statewide':item['completePublishedExactPlanFormulary']=False;item['outstanding']='Statewide reference is not an exact managed-care benefit.'
 entries.append(item)
p=out/'source_registry.json';p.write_text(json.dumps(entries,indent=2))
c=sqlite3.connect(ROOT/'data/medication_coverage_v0.30.sqlite');c.execute('CREATE TABLE IF NOT EXISTS source_registry(plan_id TEXT PRIMARY KEY REFERENCES plans(id),official_formulary TEXT,prior_authorization_sources TEXT,step_quantity_sources TEXT,pharmacy_hub TEXT,source_version TEXT,epa_source TEXT,payload TEXT NOT NULL)')
for e in entries:c.execute('INSERT OR REPLACE INTO source_registry VALUES(?,?,?,?,?,?,?,?)',(e['planId'],json.dumps(e['officialFormulary']),e['priorAuthorizationSourceRegistry'],e['stepQuantitySource'],e['pharmacyHub'],e['sourceVersion'],e['epaSource'],json.dumps(e)))
c.commit();c.close()
with (ROOT/'data/medication_coverage_v0.30.sqlite').open('rb') as src,gzip.open(ROOT/'data/medication_coverage_v0.30.sqlite.gz','wb',compresslevel=9) as dst:shutil.copyfileobj(src,dst)
print('Registered',len(entries),'AHCCCS references/programs with distinct source applicability.')
