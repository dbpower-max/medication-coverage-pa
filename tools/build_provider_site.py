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
