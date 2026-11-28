"""Build a standalone site containing only the three provider-facing ACC plans."""
from codecs import BOM_UTF8
import gzip
import hashlib
import json
import re
import shutil
from import_ach_baseline import with_ach_baseline
from medication_dosage_forms import attach_dosage_forms
from pathlib import Path
from urllib.parse import urlsplit, unquote
from link_provider_policies import attach_provider_policies
from shared_policy_pilot import attach_shared_policy
from source_restrictions import correct_source_restrictions, correct_source_conflicts
from structured_statewide_criteria import publish_structured_criteria
from rxnorm_display_names import attach_rxnorm_display_names
from uhc_policy_access import publish_uhc_policy_access

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "dist"
OUT = ROOT / "_site"
ALLOWED = {"az-complete-health", "banner-ufc", "uhc-community-az"}
data = json.loads(gzip.decompress((SRC / 'data.json.gz').read_bytes()))
# Dated plan notices establish only the listed product preference and billing route.
for brand, ingredient, preference, payer_name, label_id in (
    ('Prolia', 'denosumab', 'non_preferred', 'Prolia (SC)',
     '49e5afe9-a0c7-40c4-af9f-f287a80c5c88'),
    ('Bildyos', 'denosumab-nxxp', 'preferred', 'Bildyos syringe (SC)',
     'b9e32bf7-d70a-4083-8577-c15751c7f769'),
):
    data['medications'].append({
        'id': 'ach-apr2026-' + brand.lower(), 'planId': 'az-complete-health',
        'recordType': 'formulary', 'name': payer_name, 'brand': brand,
        'category': 'Bone Resorption Suppression and Related Agents',
        'subcategory': 'Denosumab products', 'coverage': 'listed', 'preferred': preference,
        'pa': 'not_specified', 'step': 'not_specified', 'conditions': [],
        'sourceEffective': '2026-04-01', 'sourceTitle': 'Arizona Complete Health April formulary notice',
        'sourceUrl': 'https://www.azcompletehealth.com/newsroom/PU26023.html',
        'reviewedPresentation': {
            'label': f'{brand} ({ingredient}) subcutaneous prefilled syringe',
            'policyUnverified': True,
            'scope': 'Arizona Complete Health · April 1, 2026',
            'note': 'Labeled strength: 60 mg/mL. Pharmacy billing only. Pharmacy PA criteria and quantity limits are unverified.',
            'billingUrl': 'https://www.azcompletehealth.com/newsroom/PU26021.html',
            'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
        },
    })
data = with_ach_baseline(data)
# DEC-06/07/08/19/20, RFA3857-3859, 498/500: distinguish label
# presentation from the dated payer preference and raw source benefit fields.
# The current provider special note has no printed effective date; retain
# it as separately attributed exact-plan rule evidence, not a dated override.
ach_oud_rows = {
    'ach-json-1996189': ('Sublocade 100 mg/0.5 mL Extended-Release Subcutaneous Injection', '100 mg/0.5 mL'),
    'ach-json-1996193': ('Sublocade 300 mg/1.5 mL Extended-Release Subcutaneous Injection', '300 mg/1.5 mL'),
    'ach-notice-13951': ('Sublocade Extended-Release Subcutaneous Injection (Plan Notice; Strength Unspecified)', None),
}
ach_oud_seen = set()
for record in data['medications']:
    rid = record['id']
    if rid in ach_oud_rows:
        assert record['planId'] == 'az-complete-health'
        label, dose = ach_oud_rows[rid]
        if dose:
            assert record['baselineSource']['values']['prior_authorization'] is True
            note = f'FDA label: {dose} prefilled single-dose syringe (200 mg/mL), extended-release subcutaneous injection only; never administer intravenously. REMS distribution. The October preference notice does not specify a strength. Exact plan initial/renewal criteria are unverified.'
        else:
            assert record['sourceEffective'] == '2026-10-01'
            note = 'The October plan notice names the subcutaneous product without specifying a strength or PA field. Refer to the separate 100 mg/0.5 mL and 300 mg/1.5 mL presentations for product-level benefit evidence. FDA label: extended-release SC injection only; never administer intravenously. REMS distribution.'
        record['reviewedPresentation'] = {
            'separate': True, 'label': label, 'dosageForm': 'extended-release subcutaneous injection',
            'note': note, 'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=6189fb21-9432-45f8-8481-0bfaf3ccde95',
        }
        ach_oud_seen.add(rid)
    elif rid in ('ach-json-351264', 'ach-json-351265'):
        assert record['planId'] == 'az-complete-health' and 'naloxone' not in record['name'].lower()
        record['achProviderRule'] = {
            'sourceUrl': 'https://www.azcompletehealth.com/providers/pharmacy.html',
            'sourceTitle': 'Integrated Preferred Drug List: Special Note on Buprenorphine tablets',
            'effectiveDate': None, 'observedDate': '2026-11-27',
            'rawText': 'PA REQUIRED unless the member is pregnant or nursing.',
            'text': 'Arizona Complete Health provider pharmacy page: PA is required except for pregnancy or nursing, with specified diagnosis codes on the prescription to enable the pharmacy override. The rule has no printed effective date.',
        }
        ach_oud_seen.add(rid)
assert ach_oud_seen == set(ach_oud_rows) | {'ach-json-351264', 'ach-json-351265'}
# Exact ACH baseline SBDs identify distinct devices. Keep statewide rows and
# field-specific benefits separate when a shared brand spans a vial and pens.
ach_insulin_devices = {
    '1670016': ('Tresiba FlexTouch (insulin degludec) 100 units/mL prefilled pen',
                '3 mL single-patient-use pen. Dials in 1-unit increments.'),
    '1670023': ('Tresiba FlexTouch (insulin degludec) 200 units/mL prefilled pen',
                '3 mL single-patient-use pen. Dials in 2-unit increments.'),
    '2107522': ('Tresiba (insulin degludec) 100 units/mL multidose vial',
                'Labeled 10 mL multidose vial.'),
    '1731317': ('Humulin R U-500 KwikPen (regular insulin) 500 units/mL prefilled pen',
                '3 mL single-patient-use pen. Dial in 5-unit increments. Never withdraw insulin from the pen into a syringe. Exact Arizona Complete Health authorization criteria are unverified.'),
}
for record in data['medications']:
    rx = record['id'].removeprefix('ach-json-')
    if rx not in ach_insulin_devices:
        continue
    assert record['planId']=='az-complete-health' and str(record['rxnormId'])==rx and record['baselineSource']
    u500 = rx=='1731317'
    heading,note = ach_insulin_devices[rx]
    label_id = 'b60e8dd0-1d48-4dc9-87fd-e14675255e8c' if u500 else '456c5e87-3dfd-46fa-8ac0-c6128d4c97c6'
    record['reviewedPresentation'] = {
        'separate': True, 'label': heading, 'dosageForm': 'solution for injection', 'note': note,
        'identityRxcui': int(rx), 'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label_id,
    }
    if u500:
        record['reviewedPresentation']['policyUnverified'] = True
        record['sourceUpdates'] = [*record.get('sourceUpdates', []), {
            'name':'Arizona Complete Health Complete Care PDL, printed p. 21 (PDF p. 26)',
            'sourceEffective':'2023-02-01', 'paText':'Humulin R U-500 KwikPen: F; PA.',
            'sourceUrl':'https://www.azcompletehealth.com/content/dam/centene/az-complete-health/pdf/provider/formulary/AZ%20Integrated%20English%20CNCAZCH01_19108_2023-01-25-Final%20508C%20PDF%20-%20Feb%202023.pdf#page=26',
        }]
ach_insulin_labels = {
 '311027': ('Novolin N (human NPH insulin) 100 units/mL multidose vial', 'injectable suspension', 'Labeled 10 mL multidose vial.', '82f1445c-b2c6-445a-82cf-ba8825fac776'),
 '311033': ('Novolin R (regular human insulin) 100 units/mL multidose vial', 'solution for injection', 'Labeled 10 mL multidose vial.', 'aee7f1f3-612c-4027-8ce9-4fd1f41eed71'),
 '311040': ('Insulin aspart 100 units/mL multidose vial', 'solution for injection', 'Labeled 10 mL multidose vial.', 'bee5b358-c863-420b-be73-ced2e920c499'),
 '1653202': ('Insulin aspart 100 units/mL prefilled pen', 'solution for injection', 'Labeled FlexPen: 3 mL single-patient-use pen.', 'bee5b358-c863-420b-be73-ced2e920c499'),
 '285018': ('Lantus (insulin glargine) 100 units/mL multidose vial', 'solution for injection', 'Labeled 10 mL multidose vial.', 'd5e07a0c-7e14-4756-9152-9fea485d654a'),
 '847232': ('Lantus SoloStar (insulin glargine) 100 units/mL prefilled pen', 'solution for injection', '3 mL single-patient-use pen.', 'd5e07a0c-7e14-4756-9152-9fea485d654a'),
 '106892': ('Humulin 70/30 (human NPH/regular insulin) 100 units/mL multidose vial', 'injectable suspension', 'Labeled 10 mL multidose vial.', 'e245e0c5-b2d6-418b-baa4-1c3324292885'),
 '847189': ('Humulin 70/30 KwikPen (human NPH/regular insulin) 100 units/mL prefilled pen', 'injectable suspension', '3 mL single-patient-use pen.', 'e245e0c5-b2d6-418b-baa4-1c3324292885'),
 '351926': ('NovoLog (insulin aspart) 100 units/mL multidose vial', 'solution for injection', 'Labeled 10 mL multidose vial.', '3a1e73a2-3009-40d0-876c-b4cb2be56fc5'),
 '1653198': ('NovoLog PenFill (insulin aspart) 100 units/mL cartridge', 'solution for injection', '3 mL cartridge for a compatible PenFill insulin delivery device.', '3a1e73a2-3009-40d0-876c-b4cb2be56fc5'),
 '1653204': ('NovoLog FlexPen (insulin aspart) 100 units/mL prefilled pen', 'solution for injection', '3 mL single-patient-use pen.', '3a1e73a2-3009-40d0-876c-b4cb2be56fc5'),
 '977842': ('NovoLog Mix 70/30 (insulin aspart protamine/insulin aspart) 100 units/mL multidose vial', 'injectable suspension', 'Labeled 10 mL multidose vial.', '1861fcee-7673-4afe-a206-08fa05c0add2'),
 '977840': ('NovoLog Mix 70/30 FlexPen (insulin aspart protamine/insulin aspart) 100 units/mL prefilled pen', 'injectable suspension', '3 mL single-patient-use pen.', '1861fcee-7673-4afe-a206-08fa05c0add2'),
}
for record in data['medications']:
    rx=record['id'].removeprefix('ach-json-')
    if rx in ach_insulin_labels:
        assert record['planId']=='az-complete-health' and record['baselineSource'] and str(record['rxnormId'])==rx
        heading,form,note,label_id=ach_insulin_labels[rx]
        record['reviewedPresentation']={'label':heading,'dosageForm':form,'note':note,'identityRxcui':int(rx),'separate':True,
                                        'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+label_id}
correct_source_restrictions(data['medications'])
correct_source_conflicts(data['medications'])
attach_provider_policies(data)
attach_rxnorm_display_names(data)
assert ALLOWED <= {p["id"] for p in data["plans"]}
# A single current AHCCCS core is shared by all three ACC plan views.
# These are source records, not synthesized plan claims.
statewide_drugs = [r for r in data["medications"] if r["planId"] == "ahcccs-statewide"]
statewide_pa = [r for r in data["policies"]
                if r["planId"] == "ahcccs-ffs-aihp"
                and r.get("sourceEffective") == "2026-11-01"
                and r.get("recordType") == "policy_index"]
assert 1400 <= len(statewide_drugs) <= 1500, "November AHCCCS drug list not found"
assert len(statewide_pa) >= 400, "November AHCCCS PA criteria index not found"
assert all(r["sourceEffective"] == "2026-11-01" for r in statewide_drugs)
data["statewideDrugList"] = statewide_drugs
data["statewidePaCriteria"] = statewide_pa
# Only release clinically meaningful rules individually checked against the
# November AHCCCS full-text guideline. The other indexed sections remain links,
# not machine-inferred clinical approval requirements.
clinical_guidance = json.loads((ROOT / "tools/provider_statewide_clinical_guidance.json").read_text())
assert clinical_guidance["sourceEffective"] == "2026-11-01"
indexed_by_code = {p["policyCode"]: p for p in statewide_pa}
assert len(clinical_guidance["guides"]) >= 9, "Previously reviewed guide entries unexpectedly lost"
ids = [g["id"] for g in clinical_guidance["guides"]]
assert len(ids) == len(set(ids)), "Duplicate clinical guideline identity"
brand_claims = set()
def check_rule_list(rules):
    assert isinstance(rules, list) and rules, "Empty clinical requirement branch"
    for item in rules:
        if isinstance(item, str):
            assert item.strip(), "Empty clinical requirement"
        else:
            assert isinstance(item, dict) and len(item) == 1, "Ambiguous clinical logic shape"
            key = next(iter(item))
            assert key in ("all", "any"), "Unknown AND/OR group"
            check_rule_list(item[key])

for guide in clinical_guidance["guides"]:
    policy = indexed_by_code.get(guide["policyCode"])
    assert policy, "No current AHCCCS index section for " + guide["policyCode"]
    assert policy["sourceEffective"] == clinical_guidance["sourceEffective"]
    assert policy["sourcePage"] <= guide["sourcePage"] <= guide["sourceLastPage"] <= policy["sourceLastPage"]
    assert policy["sourceTextUrl"] == guide["sourceTextUrl"]
    raw = " ".join((SRC / guide["sourceTextUrl"].lstrip("/")).read_text().split()).lower()
    assert guide["policyCode"].lower() in raw
    if guide.get("matchFormulationWords"):
        assert isinstance(guide["matchFormulationWords"], list)
        assert all(isinstance(w, str) and w.isalpha() for w in guide["matchFormulationWords"])
    brands = guide.get("matchBrands", [])
    generic_names = guide.get("matchNames", [])
    # The product matcher must enforce source-confirmed strength restrictions.
    if "matchStrengthMg" in guide:
        strength = guide["matchStrengthMg"]
        assert type(strength) in (int, float) and strength > 0, "Invalid guide strength: " + guide["id"]
        amount = str(int(strength)) if float(strength).is_integer() else str(strength)
        assert amount + "mg" in raw.replace(" mg", "mg"), "Strength absent from original policy: " + guide["id"]
    assert brands or generic_names, "Guide must have an exact product brand or medication-name key"
    for kind, identity in (("brand", brands), ("name", generic_names)):
        for value in identity:
            assert isinstance(value, str) and value.strip(), "Invalid product identity"
            key = kind + ":" + value.strip().lower()
            assert key not in brand_claims, "Product identity maps to multiple clinical guides: " + value
            brand_claims.add(key)
    pathways, stages = guide.get("pathways"), guide.get("stages")
    assert bool(pathways) != bool(stages), "Exactly one of indication pathways or treatment stages required"
    for pathway in pathways or []:
        assert pathway["title"].strip()
        check_rule_list(pathway["all"])
    for stage in stages or []:
        assert stage["title"].strip()
        check_rule_list(stage["all"])
    source_checks = guide.get("sourceChecks")
    assert isinstance(source_checks, list) and len(source_checks) >= 3, "Insufficient independent source phrases for " + guide["id"]
    for phrase in source_checks:
        assert isinstance(phrase, str) and phrase.strip() and " ".join(phrase.split()).lower() in raw, "Source phrase mismatch: " + guide["id"] + " / " + str(phrase)
    duration = re.fullmatch(r"(\d+)\s+(months?|weeks?|days?)", guide["approvalDuration"].strip().lower())
    assert duration, "Unsupported approval length: " + guide["id"]
    duration_value = duration.group(1)
    duration_unit = duration.group(2).removesuffix("s")
    assert (
        duration_value + " " + duration_unit + "(s)" in raw
        or duration_value + " " + duration_unit + "s" in raw
        or duration_value + " " + duration_unit in raw
    ), "Duration does not match published guideline: " + guide["id"]
    # Per-indication or per-stage durations are mandatory on EVERY branch
    # when a source gives more than one approval period for a product.
    duration_branches = pathways or stages or []
    if any("approvalDuration" in branch for branch in duration_branches):
        assert all("approvalDuration" in branch for branch in duration_branches), (
            "Mixed annotated/unannotated approval branches: " + guide["id"])
        for branch in duration_branches:
            branch_duration = re.fullmatch(
                r"(\d+)\s+(months?|weeks?|days?)",
                branch["approvalDuration"].strip().lower())
            assert branch_duration, "Invalid branch duration: " + guide["id"]
            val = branch_duration.group(1)
            unit = branch_duration.group(2).removesuffix("s")
            assert any(val + " " + suffix in raw for suffix in (
                unit + "(s)", unit + "s", unit
            )), "Branch duration missing from original policy: " + guide["id"]
    if guide["policyCode"] == "GL-589207":
        assert "product name:jardiance" in raw and "brand farxiga, generic dapagliflozin" in raw
        assert "1500mg daily for 90 days" in raw
        assert "heart failure" in raw and "chronic kidney disease" in raw
        assert "patient is 10 years of age or older" in raw
        assert "generic dapagliflozin requests only" in raw and "brand farxiga" in raw
    if guide["policyCode"] == "GL-154074":
        assert "humulin r u-500 vial and kwikpen" in raw
        assert "insulin aspart or insulin lispro" in raw and "lantus" in raw
        assert "special circumstance" in raw
    if guide["policyCode"] == "GL-749236":
        assert "preferred drugs: mounjaro, trulicity, brand victoza" in raw
        assert "baseline a1c greater than or equal to 6.5%" in raw
        assert "lab report must be submitted" in raw
        assert "verified via paid claims" in raw
        assert "1500 milligrams (mg) daily for 90 days" in raw
        assert "patient is 10 years of age or older" in raw
        assert "not being used for weight loss" in raw
        assert "dpp-4" in raw and "not being co-administered with another glp-1" in raw
    if guide["policyCode"] == "GL-669273":
        assert "product name:awiqli" in raw
        assert "therapy stage initial authorization" in raw
        assert "therapy stage reauthorization" in raw
        assert "90-day supply" in raw
        assert "two of the following basal insulin" in raw
        assert "visual impairment" in raw
        assert "patient or caregiver has been counseled" in raw
        assert "patient demonstrates positive clinical response" in raw
    if guide["policyCode"] == "GL-398215":
        assert "product name:soliqua" in raw and "product name:xultophy" in raw
        assert "therapy stage initial authorization" in raw and "therapy stage reauthorization" in raw
        assert "inadequately controlled on both of the following" in raw
        assert "history of failure, intolerance, or contraindication to soliqua" in raw
        assert "documentation of positive clinical response" in raw
        assert "dpp-4" in raw
data["statewideClinicalGuidance"] = clinical_guidance["guides"]
data["statewideSourceInfo"] = {
    "drugListEffective": "2026-11-01",
    "paCriteriaEffective": "2026-11-01",
    "drugListOfficialUrl": "https://www.azahcccs.gov/Resources/Downloads/PharmacyUpdates/2026/AHCCCSDrugListEffective2026-11-01.pdf",
    "paCriteriaOfficialUrl": "https://www.azahcccs.gov/Resources/Downloads/PharmacyUpdates/2026/AZMFileseff110126AllGuidelines.pdf",
    "policyUrl": "https://www.azahcccs.gov/shared/Downloads/MedicalPolicyManual/300/310-V.pdf",
    "policyEffective": "2026-10-09"
}
# The 1,449 copied statewide minimum rows in the ACH view are replaced
# by the one shared reference above, without modifying the source archive.
data["medications"] = [r for r in data["medications"]
    if r.get("validation") != "mandated_statewide_minimum_with_plan_adoption_evidence"]
for key, identity in (("plans", "id"), ("medications", "planId"), ("policies", "planId"), ("planEvidence", "planId")):
    data[key] = [r for r in data[key] if r.get(identity) in ALLOWED]
data['medications'].append({
    'id': 'banner-oct2026-j1306', 'planId': 'banner-ufc', 'recordType': 'formulary',
    'name': 'Injection, inclisiran, 1 mg', 'brand': 'Leqvio', 'category': 'Cardiovascular',
    'subcategory': 'Lipid lowering', 'preferred': 'not_specified', 'pa': 'required',
    'coverage': 'not_specified', 'listingLabel': 'Injectable PA grid', 'step': 'not_specified',
    'conditions': [], 'sourceEffective': '2026-10-01', 'sourcePage': 4,
    'sourceTitle': 'Banner University Family Care ACC pharmacy PA grid',
    'sourceUrl': 'https://www.bannerhealth.com/bhpprovider/-/media/files/project/bhpprovider/prior-auth/pa-grids/2026/prov_bufc-pa-grid_eff10012026_en.pdf?hash=BED5B049AF66FBC2888AF8A45747E496&sc_lang=en',
    'reviewedPresentation': {
        'label': 'Leqvio (inclisiran) 284 mg/1.5 mL subcutaneous prefilled syringe',
        'dosageForm': 'solution',
        'policyUnverified': True,
        'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=6fc0afca-4513-4c35-b594-6544aee29a44',
        'note': 'FDA-labeled 284 mg/1.5 mL (189 mg/mL) single-dose syringe, administered by a healthcare professional. Banner processes J1306; 1 mg is a billing unit, not a dose or package. Exact medical-benefit initial and renewal criteria and application of the pharmacy guideline remain unverified.',
    },
})
# PU25143 lists four prescribing options and seven package identifiers.
# Quantity in a package is separate from a dispensing limit.
guide_options = [
    ('test', 'ACCU-CHEK GUIDE TEST', 'Accu-Chek Guide blood glucose test strips', [
        (1, '65702070195', '50'), (2, '65702071910', '50'), (3, '65702071110', '50'), (4, '65702071210', '100')]),
    ('control', 'ACCU-CHEK GUIDE CONTROL', 'Accu-Chek Guide glucose control solution', [(5, '65702071310', '1 bottle')]),
    ('meter', 'ACCU-CHEK GUIDE', 'Accu-Chek Guide blood glucose meter kit', [(6, '65702072910', '1 per 365 days')]),
    ('me-meter', 'ACCU-CHEK GUIDE ME', 'Accu-Chek Guide Me blood glucose meter kit', [(7, '65702073110', '1 per 365 days')]),
]
for option, payer_name, heading, packages in guide_options:
    strips = option == 'test'
    meter = option in ('meter', 'me-meter')
    guide = {
        'id': 'ach-pu25143-' + option, 'planId': 'az-complete-health', 'recordType': 'formulary',
        'name': payer_name, 'brand': 'Accu-Chek', 'category': 'Diabetes supplies',
        'subcategory': 'Diabetes - Glucose Monitoring', 'coverage': 'listed',
        'preferred': 'preferred' if strips else 'not_specified', 'pa': 'not_specified', 'step': 'not_specified',
        'conditions': [], 'sourceEffective': '2025-11-01',
        'sourceTitle': 'Arizona Complete Health Complete Care · blood glucose testing product notice PU25143',
        'sourceUrl': 'https://www.azcompletehealth.com/newsroom/PU25143.html',
        'searchAliases': [ndc for _, ndc, _ in packages],
        'payerPackages': [{'row': row, 'ndc': ndc, 'quantity': quantity} for row, ndc, quantity in packages],
        'reviewedPresentation': {'label': heading, 'separate': True, 'scope': 'Arizona Complete Health · Complete Care'},
    }
    guide['reviewedPresentation']['deviceSourceUrl'] = ('https://www.accu-chek.com/products/control-solution/guide'
                                                       if option == 'control' else 'https://www.accu-chek.com/products/strips/guide')
    if strips:
        guide.update(quantityLimited=True, verifiedQuantityLabel='QL by insulin use',
                     rawRestrictions='Insulin Users: Max of 150 per 30 days. Non-Insulin Users: 50 per 30 days or 100 per 90 days.')
        guide['reviewedPresentation']['note'] = 'Insulin users: up to 150 strips per 30 days. Non-insulin users: 50 strips per 30 days or 100 strips per 90 days. Compatible with Guide and Guide Me meters.'
    elif meter:
        guide.update(quantityLimited=True, qlAmount='1', qlDays='365', verifiedQuantityLabel='QL: 1 meter per 365 days')
        guide['reviewedPresentation']['note'] = 'Use Accu-Chek Guide test strips with this meter.'
    else:
        guide['reviewedPresentation']['note'] = 'Control solution for Accu-Chek Guide systems. The notice lists one bottle and gives no dispensing interval.'
    data['medications'].append(guide)

# The 2023 PDL establishes class coverage. PU26022 supplies the later conditional limits.
ach_supply_pdl = ('https://www.azcompletehealth.com/content/dam/centene/az-complete-health/pdf/provider/formulary/'
                  'AZ%20Integrated%20English%20CNCAZCH01_19108_Final%20508C%20PDF%20-%20April%202023%202nd%20run.pdf#page=46')
supply_policy = './sources/ach/AZ.CP.PMN.1018-Quantity-Limits--Alcohol-Swabs-Lancets-12.25_R.pdf'
for key, heading, original, cap, prerequisite, renewal_page in [
    ('lancets', 'Blood glucose lancets', 'LANCETS AND LANCET DEVICES', 26,
     'blood glucose test strips in quantities above 100 per 30 days', 1),
    ('swabs', 'Alcohol swabs', 'ALCOHOL SWABS', 15,
     'more than 100 injections or blood glucose tests per 30 days', 2),
]:
    supply = 'lancets' if key == 'lancets' else 'alcohol swabs'
    data['medications'].append({
        'id': 'ach-pu26022-' + key, 'planId': 'az-complete-health', 'recordType': 'formulary',
        'name': heading, 'category': 'Diabetes supplies', 'subcategory': 'Diabetes - Glucose Monitoring',
        'coverage': 'listed', 'preferred': 'not_specified', 'step': 'not_specified', 'pa': 'conditional',
        'conditions': [], 'quantityLimited': True, 'qlAmount': '210', 'qlDays': '30',
        'verifiedQuantityLabel': f'QL: 7 {supply} per day and 210 per 30 days',
        'sourceTitle': 'Arizona Complete Health Complete Care · quantity and high-dollar limits PU26022',
        'sourceUrl': 'https://www.azcompletehealth.com/newsroom/PU26022.html', 'sourceEffective': '2026-04-01',
        'supplyAuthorization': {
            'initial': f'Document medical necessity for the requested quantity and an approval on file for {prerequisite}.',
            'renewal': f'The member must currently receive {supply} through a previous authorization.',
            'cap': cap, 'initialUrl': supply_policy + '#page=1', 'renewalUrl': supply_policy + f'#page={renewal_page}',
        },
        'reviewedPresentation': {
            'label': heading, 'separate': True, 'scope': 'Arizona Complete Health · Complete Care',
            'paBadge': 'PA if >7/day or >210 per 30 days',
            'sourceReferences': [
                [f'April 2023 Complete Care formulary · PDF p. 46 · {original} · F (formulary)', ach_supply_pdl],
                ['AZ.CP.PMN.1018 · initial criteria · p. 1', supply_policy + '#page=1'],
                [f'AZ.CP.PMN.1018 · continuation · p. {renewal_page}', supply_policy + f'#page={renewal_page}'],
            ],
        },
    })

# Display the exact verified dosage forms without changing card identities.
ach_pref_labels = {
    'Ocrevus': '9da42362-3bb5-4b83-b4bb-b59fd4e55f0d',
    'Ocrevus Zunovo': 'b216af61-99d0-42a3-afc2-b5bf86df1ec0',
    'Copaxone': 'aa88f583-4f5f-433b-80b4-1f4c9fb28357',
    'Yesintek': '12a75613-ee33-d30a-215b-2a51cfa19b00',
    'Exenatide': 'e6cb5c8f-e97f-4a6a-95a4-939fd2393949',
}
ach_pref_options = [
    (['ach-json-1876385', 'ach-notice-13945'], 'Ocrevus', '300 mg/10 mL IV infusion solution, single-dose vial', 1876385),
    (['ach-json-2693465', 'ach-notice-13946'], 'Ocrevus Zunovo', '40 mg/mL ocrelizumab and 1,000 units/mL hyaluronidase, 23 mL single-dose vial for subcutaneous injection', 2693465),
    (['ach-json-1111642','ach-notice-13943'], 'Copaxone', '20 mg/mL subcutaneous injection solution, prefilled syringe', 1111642),
    (['ach-notice-13944'], 'Copaxone', '40 mg/mL subcutaneous injection solution, prefilled syringe', 1487363),
    (['ach-json-2705603','ach-notice-13875'], 'Yesintek', '45 mg/0.5 mL subcutaneous injection solution, single-dose vial', 2705603),
    (['ach-json-2705597'], 'Yesintek', '45 mg/0.5 mL subcutaneous injection solution, prefilled syringe', 2705597),
    (['ach-json-2705600'], 'Yesintek', '90 mg/mL subcutaneous injection solution, prefilled syringe', 2705600),
    (['ach-json-2705588'], 'Yesintek', '130 mg/26 mL IV infusion solution, single-dose vial', 2705588),
    (['ach-json-847910'], 'Exenatide', '250 mcg/mL subcutaneous injection solution, 10 mcg/dose multidose pen', 847910),
    (['ach-json-847915'], 'Exenatide', '250 mcg/mL subcutaneous injection solution, 5 mcg/dose multidose pen', 847915),
]
ach_records = {r['id']: r for r in data['medications'] if r['planId'] == 'az-complete-health'}
memo_url = 'https://www.azahcccs.gov/Resources/Downloads/PharmacyUpdates/2026/Contractor_Memo_May_2026_PT_MeetingFinal.pdf'
infusion_policy = './sources/ach/508_AZ.CP.PHAR.493-Infusion-SOC-Optimization-final.pdf'
for ids, product, description, rx in ach_pref_options:
    for record_id in ids:
        record = ach_records[record_id]
        display = {'prescribingHeading': product + ' ' + description, 'identityRxcui': rx,
                   'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + ach_pref_labels[product]}
        if product == 'Ocrevus':
            display['note'] = 'Arizona Complete Health evaluates the infusion site separately from authorization of the drug.'
            display['sourceReferences'] = [
                ['ACH infusion site criteria · pp. 1–2', infusion_policy + '#page=1'],
                ['ACH site-of-care policy Appendix B · J2350 Ocrevus · p. 5', infusion_policy + '#page=5']]
        elif product == 'Ocrevus Zunovo':
            display['note'] = 'The 23 mL vial contains 920 mg ocrelizumab and 23,000 units hyaluronidase.'
        elif product == 'Copaxone':
            display['note'] = 'Arizona Complete Health lists this strength as nonpreferred with PA. The November AHCCCS Statewide list shows Copaxone prefilled syringes as preferred with PA without specifying the strength.'
            display['sourceReferences'] = [['AHCCCS Statewide · November 2026 list · p. 33', './sources/ahcccs-drug-list-2026-11-01.pdf#page=33']]
        elif rx == 2705588:
            display['note'] = 'AHCCCS Statewide lists the IV vial as nonpreferred effective October 1. The 2022 Arizona Complete Health formulary listed it as preferred; the October plan notice repeats only the subcutaneous vial.'
            display['sourceReferences'] = [['AHCCCS Statewide · contractor obligations · p. 1', memo_url + '#page=1'],
                                           ['AHCCCS Statewide · IV vial decision · p. 6', memo_url + '#page=6']]
        elif product == 'Exenatide':
            record['searchAliases'] = [*record.get('searchAliases', []), 'EXENATIDE PEN (SUBCU SUBCUTANEOUS)']
            display['sourceReferences'] = [['AHCCCS Statewide · generic exenatide pen · p. 8', memo_url + '#page=8']]
        record['reviewedPresentation'] = display
ach_records['ach-notice-13874']['reviewedPresentation'] = {
    'prescribingHeading': 'Yesintek subcutaneous injection solution, prefilled syringe',
    'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + ach_pref_labels['Yesintek'],
    'labelProductExamples': [['45 mg/0.5 mL prefilled syringe', 2705597], ['90 mg/mL prefilled syringe', 2705600]],
}

naloxone_presentations = {
    '1191234': ('Naloxone 0.4 mg/1 mL injection solution, Carpuject cartridge', 'b598c237-032d-4bb5-0e92-50eabd863dac',
                'The 2.5 mL cartridge contains a 1 mL fill and requires a reusable Carpuject holder. The October plan notice names syringes and vials. Coverage of the holder is unverified.'),
    '1659929': ('Naloxone 0.4 mg/1 mL injection solution', '8535cc84-ad4a-4d67-8480-fb5a2e3406f8',
                'The linked label includes a 1 mL single-dose vial. Confirm the dispensed container before applying vial-specific coverage.'),
    '1191222': ('Naloxone 0.4 mg/mL injection solution', '8535cc84-ad4a-4d67-8480-fb5a2e3406f8',
                'Labeled vial presentations include 0.4 mg/1 mL single-dose and 4 mg/10 mL multidose. Confirm the dispensed container.'),
    '1191250': ('Naloxone 2 mg/2 mL injection solution, prefilled syringe', '201fdedf-1736-4e52-9d7d-de14292547fd', '1 mg/mL in a 2 mL prefilled syringe.'),
    '2679504': ('Naloxone 0.4 mg/1 mL injection solution, prefilled syringe', '201fdedf-1736-4e52-9d7d-de14292547fd', '0.4 mg/mL in a 1 mL prefilled syringe.'),
    '1725059': ('Naloxone 4 mg/0.1 mL single-dose nasal spray', '8091a73d-9ecd-4578-a57b-5d85a2c5a16a',
                'The October plan notice names OTC spray. Confirm the dispensing package for that listing.'),
    '1725064': ('Narcan 4 mg/0.1 mL single-dose nasal spray', 'a0ebc83d-2892-40de-bc0a-775ce90b30db',
                'The October plan notice specifies the OTC presentation. The statewide listing also names prescription spray.'),
    '2540709': ('Kloxxado 8 mg/0.1 mL single-dose nasal spray', 'ebf0f833-c1c0-487c-8f29-01fa8c61b6cb', ''),
    '2680741': ('Rextovy 4 mg/0.25 mL single-dose nasal spray', 'fe9735db-c57e-44a8-bffb-b87a84c2a6f3', 'Prescription nasal spray.'),
}
for rx,(heading,set_id,note) in naloxone_presentations.items():
    display={'prescribingHeading':heading,'identityRxcui':int(rx),'note':note,
             'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+set_id}
    if rx == '1191234':
        warning='https://www.fda.gov/media/191737/download'
        display['deviceSafety']={'text':'Pfizer’s March 27, 2026 warning lists lot NH9362, unit NDC 0409-1782-03, carton 0409-1782-69, expiring July 31, 2027. Inspect before use and discard a unit with a hole at the needle-sheath tip.',
                                 'link':warning+'#page=2','linkLabel':'FDA-hosted prescribing notice · inspection instructions · p. 2'}
        display['sourceReferences']=[['Pfizer · affected naloxone cartridge lot · p. 6',warning+'#page=6']]
    if rx == '1725059':
        display['sourceReferences']=[['Arizona Complete Health · October OTC spray listing','https://www.azcompletehealth.com/newsroom/PU26135.html']]
    if 'nasal spray' in heading:
        display['statewideDailyLimit']='2'
    ach_records['ach-json-'+rx]['reviewedPresentation']=display

# The statewide brand-only wording identifies the marketed 8 mg nasal product.
# Copy prescribing identity only. Keep each source record's benefit fields intact.
kloxxado_state=next(r for r in statewide_drugs if r['id']=='formulary-10015')
assert kloxxado_state['brand']=='KLOXXADO' and kloxxado_state['notes']=='BRAND ONLY'
kloxxado_banner=next(r for r in data['medications'] if r['id']=='banner-full-4eb997968790cb7c')
assert (kloxxado_banner['sourcePage'],kloxxado_banner['brand'],kloxxado_banner['notes'])==(11,'KLOXXADO','BRAND ONLY')
for record,rx in [(kloxxado_state,'2540709'),(kloxxado_banner,'2540709'),(ach_records['ach-notice-13953'],'2540709'),
                  (ach_records['ach-notice-13957'],'1725064'),(ach_records['ach-notice-13958'],'2680741')]:
    original=ach_records['ach-json-'+rx]['reviewedPresentation']
    record['reviewedPresentation']={k:original[k] for k in ('prescribingHeading','identityRxcui','labelUrl')}
    if record['id']=='ach-notice-13957':
        record['reviewedPresentation']['prescribingHeading']='Narcan OTC 4 mg/0.1 mL single-dose nasal spray'

attach_dosage_forms(data["medications"] + statewide_drugs)
attach_shared_policy(data)
data["planDataFiles"] = {k: v for k, v in data.get("planDataFiles", {}).items() if k in ALLOWED}
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
for name in ("index.html", "app.js", "styles.css", "favicon.svg"):
    shutil.copy2(SRC / name, OUT / name)
(OUT / ".nojekyll").touch()
criteria_release = json.loads((ROOT / 'tools/structured_criteria_release.json').read_text())
assert criteria_release['sourceEffective'] == clinical_guidance['sourceEffective']
criteria_codes = {g['policyCode'] for g in clinical_guidance['guides']} | set(criteria_release['additionalPolicyCodes'])
data['structuredCriteriaCount'] = publish_structured_criteria(statewide_pa, SRC, OUT, criteria_codes)
assert data['structuredCriteriaCount'] == criteria_release.get('expectedStructuredCount', len(criteria_codes))
publish_uhc_policy_access(data, SRC, OUT)
# DEC-04/05/07/08/09/18/19/20. Exact UHC October listings and label presentations.
# Vial concepts describe the drug product. The printed listing and SPL establish the container.
insulin_labels = {
    'Humulin N': ('human NPH insulin', 'injectable suspension', 'f6edd793-440b-40c2-96b5-c16133b7a921'),
    'Novolin 70/30': ('human NPH/regular insulin 70/30', 'injectable suspension', '508a2763-3cb7-4be5-9e53-544e84cd9b1f'),
    'Novolin N': ('human NPH insulin', 'injectable suspension', '82f1445c-b2c6-445a-82cf-ba8825fac776'),
    'Novolin R': ('regular human insulin', 'solution for injection', 'aee7f1f3-612c-4027-8ce9-4fd1f41eed71'),
    'NovoLog Mix 70/30': ('insulin aspart protamine/insulin aspart 70/30', 'injectable suspension', '1861fcee-7673-4afe-a206-08fa05c0add2'),
    'NovoLog': ('insulin aspart', 'solution for injection', '3a1e73a2-3009-40d0-876c-b4cb2be56fc5'),
}
# Electronic file row numbers (one-based) refer to UCSAZQ3 entries. The electronic
# file omits NDCs. Preserve both variants where an RxCUI has multiple plan entries.
insulin_devices = {
    '9d5d5dcd15aacbe5': ('Humulin N', 'KwikPen', 847199, 7454),
    'eb2cb3d5df295b3a': ('Humulin N', 'vial', 311026, 6772),
    'dc926ea3a037d052': ('Novolin 70/30', 'FlexPen', 2049380, 5048),
    '6a8410666a95f39f': ('Novolin 70/30', 'vial', 213442, 1234),
    '561e64d0e04ddba8': ('Novolin N', 'FlexPen', 2206099, 4460),
    '2e61212e8b4a7198': ('Novolin N', 'vial', 311027, 2047),
    '989f61316edaade8': ('Novolin R', 'FlexPen', 2206092, 282),
    '3f6b79d26bf90161': ('Novolin R', 'vial', 311033, 9863),
    '6c62c1d66fc1ba6f': ('NovoLog Mix 70/30', 'vial', 977842, 2218),
    'b6bad750052e8c96': ('NovoLog', 'vial', 351926, 8666),
    '00c9a85a6b9e582d': ('NovoLog', 'FlexPen', 1653204, 4928),
    '32fe3d13f9623a7f': ('NovoLog', 'FlexPen ReliOn', 1653204, 4928),
    '3593e59ad9ff6053': ('NovoLog', 'PenFill cartridge', 1653198, 3637),
    '539ff04df27e00e4': ('NovoLog Mix 70/30', 'FlexPen', 977840, 6370),
    '91e996f2f036b4ef': ('NovoLog Mix 70/30', 'FlexPen ReliOn', 977840, 6370),
}
relion_listings = {
    '3425a56e25a00dc0': ('Novolin 70/30', 213442, 2049380),
    '0355c1cc6877f195': ('NovoLog Mix 70/30', 977842, 977840),
    '4245cf9695f76981': ('NovoLog', 351926, 1653204),
}
electronic_formulary = json.loads((ROOT / 'audits/uhc_complete_2026_11_12/official_machine_readable.json').read_text())
# Named UHC basal listings. An unsuffixed printed name cannot select one package.
basal_labels = {
    'glargine-yfgn':'3ac85ebb-5594-59c8-77fd-df254329d151',
    'Semglee':'8cf5544f-87d6-468b-f6ae-898b1fdb5d80',
    'Lantus':'d5e07a0c-7e14-4756-9152-9fea485d654a',
    'Tresiba':'456c5e87-3dfd-46fa-8ac0-c6128d4c97c6',
    'Toujeo':'c9561d96-124d-48ca-982f-0aa1575bff36',
}
basal_presentations = {
    '4270f8a1ce19e554': ('glargine-yfgn','Insulin glargine-yfgn 100 units/mL subcutaneous prefilled pen','3 mL single-patient-use pen. The electronic file contains preferred and nonpreferred variants with different step requirements. The printed pen listing is preferred; eligible packages are unverified.',[(5117,2563971,'3 mL pen')]),
    '96922f638bb987d2': ('glargine-yfgn','Insulin glargine-yfgn 100 units/mL subcutaneous solution (device unspecified)','The printed solution listing does not name the device. The 10 mL vial is a labeled presentation. The November 16 electronic file has no matching entry for RxCUI 2563976.',[(4483,2563976,'Solution formulation')]),
    '8adc25a96356b867': ('Lantus','Lantus SoloStar (insulin glargine) 100 units/mL prefilled pen','3 mL single-patient-use pen.',[(8397,847232,'3 mL pen')]),
    '749c738dcab2dcdd': ('Lantus','Lantus (insulin glargine) 100 units/mL multidose vial','Labeled 10 mL multidose vial.',[(1393,285018,'Vial formulation')]),
    '31c74f821a4c856f': ('Semglee','Semglee (insulin glargine-yfgn) 100 units/mL solution for injection (device unspecified)','The label identifies a 10 mL multidose vial and a 3 mL prefilled pen. The printed listing does not identify the covered device.',[(2838,2563977,'Vial formulation'),(7855,2563973,'3 mL pen')]),
    '4bbdff08522d2939': ('Tresiba','Tresiba (insulin degludec) solution for injection (device unspecified)','The printed listing does not select a concentration or device. Labeled products include a 100 units/mL vial and FlexTouch pens in two concentrations.',[(5374,2107522,'100 units/mL vial'),(3320,1670016,'100 units/mL pen'),(1102,1670023,'200 units/mL pen')]),
    '2785ed0256f35226': ('Tresiba','Tresiba FlexTouch (insulin degludec) 100 units/mL or 200 units/mL prefilled pen','Both pens contain 3 mL. The 100 units/mL pen dials in 1-unit increments; the 200 units/mL pen dials in 2-unit increments.',[(3320,1670016,'100 units/mL pen'),(1102,1670023,'200 units/mL pen')]),
    'fdfe8892e218f00d': ('Toujeo','Toujeo Max SoloStar (insulin glargine) 300 units/mL prefilled pen','3 mL pen, 900 units total. Dials in 2-unit increments, up to 160 units per injection.',[(7766,2002420,'3 mL Max SoloStar')]),
    'c04f64c23aca9188': ('Toujeo','Toujeo SoloStar (insulin glargine) 300 units/mL prefilled pen','1.5 mL pen, 450 units total. Dials in 1-unit increments, up to 80 units per injection.',[(1716,1604544,'1.5 mL SoloStar')]),
}
for record in data['medications']:
    suffix=record['id'].removeprefix('uhc-oct-complete-')
    if suffix not in basal_presentations:
        continue
    family,heading,note,products=basal_presentations[suffix]
    assert record['planId']=='uhc-community-az' and record['sourceEffective']=='2026-10-01'
    evidence=[]
    conflict=record['pa']=='required'
    for position,rx,description in products:
        source=electronic_formulary[position-1]
        assert int(source['rxnorm_id'])==rx
        entries=[v for v in source['plans'] if v['plan_id']=='UCSAZQ3']
        assert entries and all(2026 in v['years'] and v['quantity_limit'] and not v['prior_authorization'] for v in entries)
        assert not conflict or all(v['step_therapy'] for v in entries)
        flags=', '.join(v['drug_tier']+' (PA: no, ST: '+('yes' if v['step_therapy'] else 'no')+', QL: yes)' for v in entries)
        evidence.append(f'Row {position}, RxCUI {rx}: {flags}.')
    if conflict:
        note+=' UHC’s printed list specifies PA. Its October electronic file reports no PA and lists step therapy. Current requirements are unverified.'
    record['reviewedPresentation']={
        'label':heading,'dosageForm':'solution for injection','separate':True,'note':note,'paSourceConflict':conflict,
        'labelUrl':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+basal_labels[family],
        'labelProductExamples':[[desc,rx] for _,rx,desc in products],'electronicEvidence':evidence,
    }
reviewed_insulin_ids = set()
for record in data['medications']:
    suffix = record['id'].removeprefix('uhc-oct-complete-')
    if suffix not in insulin_devices and suffix not in relion_listings:
        continue
    assert record['planId'] == 'uhc-community-az' and record['sourceEffective'] == '2026-10-01'
    if suffix in relion_listings:
        family, vial, pen = relion_listings[suffix]
        assert 'RELION' in record['name'] and 'FLEXPEN' not in record['name']
        device = 'ReliOn'
        presentation = {
            'note': 'The label lists a 10 mL multidose vial and a 3 mL single-patient-use FlexPen. The printed ReliOn listing does not identify the device or covered package.',
            'labelProductExamples': [['Vial formulation', vial], ['3 mL prefilled pen', pen]],
        }
    else:
        family, device, rxcui, position = insulin_devices[suffix]
        assert device.split()[0].upper() in record['name']
        source_row = electronic_formulary[position - 1]
        assert int(source_row['rxnorm_id']) == rxcui
        variants = [r for r in source_row['plans'] if r['plan_id'] == 'UCSAZQ3']
        assert variants and all(2026 in r['years'] and r['quantity_limit'] and not r['prior_authorization'] for r in variants)
        electronic_steps = {r['step_therapy'] for r in variants}
        note = ('Labeled 10 mL multidose vial.' if device == 'vial' else
                '3 mL cartridge for a compatible PenFill insulin delivery device.' if device == 'PenFill cartridge' else
                '3 mL single-patient-use prefilled pen.')
        if family == 'NovoLog' and device.startswith('FlexPen'):
            note += ' The pen dials in 1-unit increments.'
            if device == 'FlexPen ReliOn':
                note += ' The electronic entry identifies the pen formulation. It does not distinguish the ReliOn package.'
        discrepancy = record['pa'] == 'required'
        if electronic_steps == {True, False}:
            note += ' The UHC electronic formulary has preferred and nonpreferred entries with differing step therapy for this RxCUI. Exact package eligibility and requirements are unverified.'
        if discrepancy:
            note += ' The printed formulary lists PA. The electronic formulary reports no PA and lists step therapy for the nonpreferred entry. Current requirements are unverified.'
        presentation = {'identityRxcui': rxcui, 'electronicRow': position, 'note': note, 'paSourceConflict': discrepancy}
    ingredient, form, label_id = insulin_labels[family]
    record['reviewedPresentation'] = {
        **presentation, 'separate': True, 'dosageForm': form,
        'label': f'{family} {device} ({ingredient}) 100 units/mL {form}',
        'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
    }
    reviewed_insulin_ids.add(suffix)
assert reviewed_insulin_ids == set(insulin_devices) | set(relion_listings)
# DEC-04/05/08/09/12/13/14/19/20: reviewed October UHC prescribing rows.
# Keep raw source wording, benefit fields and original policy bindings intact.
# Label evidence is not confirmation of the payer's exact package or OUD benefit.
opioid_reviews = {
    '1d645b57ce2be32c': (
        'fentanyl transdermal patch 72 hour 100 mcg/hr, 12 mcg/hr, 25 mcg/hr, 50 mcg/hr, 75 mcg/hr',
        'Fentanyl 72-hour transdermal patch (12, 25, 50, 75, 100 mcg/hr)',
        'patch', '2a2238e9-4b5d-c56d-8663-dd354ff9ae0c', 'pain',
        'FDA labeling restricts fentanyl patches to opioid-tolerant patients with severe persistent pain; not for acute, postoperative or as-needed pain. UHC lists these five delivery rates; intermediate rates are separate. The payer pain criteria do not override the label. Exact package and numeric quantity limit are unverified.'),
    '4949e672408e143c': (
        'METHADOSE ORAL CONCENTRATE 10 MG/ML (brand for methadone hcl)',
        'Methadose 10 mg/mL oral concentrate (cherry-flavored)',
        'oral concentrate', '808a9d0b-720b-4034-a862-5122ff514608', 'oud_only',
        'FDA labeling is for opioid addiction detoxification and maintenance, not analgesia; opioid treatment program distribution conditions apply. UHC GL-620192 names Methadose in pain criteria, but this does not establish an appropriate pain indication or an OUD authorization pathway. Exact package and OUD benefit are unverified.'),
    '554823c89afb7621': (
        'METHADOSE SUGAR-FREE (brand for methadone hcl)',
        'Methadose Sugar-Free oral concentrate (10 mg/mL per label)',
        'oral concentrate', '808a9d0b-720b-4034-a862-5122ff514608', 'oud_only',
        'FDA labeling is for opioid addiction detoxification and maintenance, not analgesia; opioid treatment program distribution conditions apply. UHC GL-620192 names Methadose in pain criteria, but this does not establish an appropriate pain indication or an OUD authorization pathway. Sugar-free, dye-free and unflavored; exact package and OUD benefit are unverified.'),
    # DEC-05/06/12/13/14/19/20: exact soluble-tablet row; FDA label is OUD-only.
    'c892c74d9f3426a2': (
        'methadose oral tablet soluble (generic for METHADOSE)',
        'Methadone HCl 40 mg Tablet for Oral Suspension (Methadose reference)',
        'tablet for oral suspension', '544483e6-6f9d-4371-9e93-313e54e0ea05', 'oud_only',
        'FDA labeling: 40 mg tablet for dispersion in liquid for opioid addiction detoxification and maintenance, not analgesia; opioid treatment program distribution conditions apply. UHC GL-620192 pain criteria do not establish OUD authorization. Label SCD 864978; reference brand SBD 864980. Exact payer package, OUD benefit and numeric quantity limit are unverified.'),
    'aa1a241874624dc7': (
        'methadone hcl intensol (generic for METHADONE HCL INTENSOL)',
        'Methadone HCl Intensol oral concentrate (generic listing)',
        'oral concentrate', 'd0e6a966-179a-45e0-8444-4c1b8523f8d2', 'unmatched',
        'The Intensol reference label describes a 10 mg/mL oral concentrate with pain and opioid addiction indications and distinct distribution conditions. This generic payer alias does not identify an exact package. UHC lists PA; product-specific criteria are unverified. Pain criteria cannot establish an OUD authorization pathway.'),
    'a0d71228114f9c0a': (
        'methadone hcl oral (generic for METHADONE HCL INTENSOL)',
        'Methadone HCl oral concentrate (Intensol reference)',
        'oral concentrate', 'd0e6a966-179a-45e0-8444-4c1b8523f8d2', 'pain',
        'The Intensol reference label describes a 10 mg/mL oral concentrate with pain and opioid addiction indications and distinct distribution conditions. This generic payer alias does not identify an exact package. The linked pain criteria do not establish an OUD authorization pathway.'),
}
opioid_seen = set()
for record in data['medications']:
    rid = record['id'].removeprefix('uhc-oct-complete-')
    if rid not in opioid_reviews:
        continue
    name, label, form, label_id, scope, note = opioid_reviews[rid]
    assert record['id'] == 'uhc-oct-complete-' + rid and record['planId'] == 'uhc-community-az'
    assert record['name'].lower() == name.lower() and record['sourceEffective'] == '2026-10-01'
    assert record['preferred'] == 'preferred' and record['pa'] == 'required'
    relevant = [b for b in record.get('uhcClinicalBindings', []) if b['policyId'].endswith('gl-620192')]
    if scope == 'unmatched':
        assert not relevant
    else:
        assert any(b['role'] == 'product' and b['branchIndexes'] == [0, 1, 4, 7, 9, 10, 11] for b in relevant)
        assert any(b['role'] == 'quantity' and b['branchIndexes'] == [8] for b in relevant)
    record['reviewedPresentation'] = {
        **record.get('reviewedPresentation', {}), 'separate': True, 'label': label,
        'dosageForm': form, 'opioidScope': scope, 'note': note,
        'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
    }
    opioid_seen.add(rid)
assert opioid_seen == set(opioid_reviews), 'Missing exact UHC opioid review row'
# Keep the printed payer alias as evidence, but exclude it from device identity.
guardian_suffix = ' (brand for guardian sensor 3)'
for record in data['medications']:
    if record['planId'] != 'uhc-community-az':
        continue
    name = record['name']
    if name.endswith(guardian_suffix):
        record['displayName'] = name.removesuffix(guardian_suffix)
        if record['displayName'] == 'GUARDIAN SENSOR (3)':
            record['searchAliases'] = [*record.get('searchAliases', []), 'Guardian Sensor 3']
    if record['id'] == 'uhc-oct-complete-fe3ff8d27057990e':
        record['scopedPolicyReference'] = {
            'id': 'uhc-nov2026-policy-gl-140734',
            'scope': 'Nonpreferred Contour NEXT EZ listing only. The policy requires visual impairment and NDC-level approval for 12 months. The preferred listing and numeric quantity limit are separate.',
        }

uhc_utf8_assets = {
    f'policy-text/uhc-nov2026/gl-{code}.txt'
    for code in ('140734', '369221', '503307', '683417', '720196')
}
seen = set()
# Large PDF remains on its official payer host; indexed full policy text is bundled.
EXTERNAL_SOURCES = {
    "sources/prov-bufc_pharmacy-pa-criteria_eff11012026_en.pdf":
    "https://www.bannerhealth.com/bhpprovider/-/media/files/project/bhpprovider/pharmacy/medicaid/prov-bufc_pharmacy-pa-criteria_eff11012026_en.pdf?hash=383206F074F0B301767EC09CEC9F35FA&sc_lang=en"
}
def copy_asset(url):
    path = unquote(urlsplit(url).path).removeprefix("./").lstrip("/")
    if not path or path in seen:
        return
    source = (SRC / path).resolve()
    if not source.is_relative_to(SRC.resolve()):
        raise ValueError("Asset outside site: " + path)
    if not source.is_file():
        raise FileNotFoundError("Missing linked asset: " + path)
    seen.add(path)
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if path in uhc_utf8_assets:
        # Serve self-identifying Unicode even when plain text has no charset.
        target.write_bytes(BOM_UTF8 + source.read_bytes().removeprefix(BOM_UTF8))
    else:
        shutil.copy2(source, target)
def visit(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and ("url" in key.lower() or key in ("file", "path")):
                parts = urlsplit(item)
                if not parts.scheme and not parts.netloc and parts.path.startswith(("/sources/", "/policy-text/", "/banner-policy-text/", "./sources/", "./policy-text/", "./banner-policy-text/", "sources/", "policy-text/", "banner-policy-text/")):
                    local_path = parts.path.lstrip("/").removeprefix("./")
                    if local_path in EXTERNAL_SOURCES:
                        value[key] = EXTERNAL_SOURCES[local_path] + ("#" + parts.fragment if parts.fragment else "")
                    else:
                        copy_asset(item)
                        value[key] = "./" + item.lstrip("/").removeprefix("./")
            else:
                visit(item)
    elif isinstance(value, list):
        for item in value:
            visit(item)
visit(data)
for plan, url in data["planDataFiles"].items():
    path = urlsplit(url).path.lstrip("/").removeprefix("./")
    raw = (SRC / path).read_bytes()
    records = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    assert all(r["planId"] == plan for r in records)
    visit(records)
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(records, ensure_ascii=False).encode()
    target.write_bytes(gzip.compress(payload, mtime=0) if path.endswith(".gz") else payload)
    version = hashlib.sha256(target.read_bytes()).hexdigest()[:12]
    data["planDataFiles"][plan] = "./" + path + "?v=" + version
(OUT / "data.json.gz").write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False).encode(), mtime=0))
# Version data as well as scripts: a cached old dataset must never accompany
# new PA logic. Hash scripts after injecting the exact built data version.
version = hashlib.sha256((OUT / 'data.json.gz').read_bytes()).hexdigest()[:12]
script = (OUT / 'app.js').read_text()
assert "fetch('./data.json.gz')" in script, 'Dataset fetch location changed'
(OUT / 'app.js').write_text(script.replace("fetch('./data.json.gz')", f"fetch('./data.json.gz?v={version}')"))
html = (OUT / 'index.html').read_text()
for name in ('app.js', 'styles.css'):
    version = hashlib.sha256((OUT / name).read_bytes()).hexdigest()[:12]
    html = html.replace('./' + name, './' + name + '?v=' + version)
(OUT / 'index.html').write_text(html)
assert {p["id"] for p in data["plans"]} == ALLOWED
print("Three-plan provider site built; linked local assets verified:", len(seen))
print("Plan medication records:", len(data["medications"]), "Plan policy records:", len(data["policies"]))
print("Shared AHCCCS statewide drug entries:", len(data["statewideDrugList"]), "FFS PA criteria sections:", len(data["statewidePaCriteria"]))
print("Individually source-checked drug guides:", len(data["statewideClinicalGuidance"]), "distinct policy sections:", len({g["policyCode"] for g in data["statewideClinicalGuidance"]}))
