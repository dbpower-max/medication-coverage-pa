"""Build a standalone site containing only the three provider-facing ACC plans."""
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, unquote
from link_provider_policies import attach_provider_policies
from shared_policy_pilot import attach_shared_policy

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "dist"
OUT = ROOT / "_site"
ALLOWED = {"az-complete-health", "banner-ufc", "uhc-community-az"}
subprocess.run([sys.executable, str(ROOT / 'tools/import_ach_baseline.py')], check=True)
data = json.loads(gzip.decompress((SRC / "data.json.gz").read_bytes()))
attach_provider_policies(data)
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
    assert guide["matchBrands"] and all(isinstance(b, str) and b.strip() for b in guide["matchBrands"]), "Missing unambiguous brand identity"
    for brand in guide["matchBrands"]:
        key = brand.strip().lower()
        assert key not in brand_claims, "Same brand maps to multiple unrelated clinical guides: " + brand
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
    duration = re.fullmatch(r"(\\d+)\\s+months?", guide["approvalDuration"].strip().lower())
    assert duration, "Unsupported approval length: " + guide["id"]
    assert duration.group(1) + " month(s)" in raw or duration.group(1) + " months" in raw, "Duration does not match published guideline: " + guide["id"]
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
attach_shared_policy(data)
data["planDataFiles"] = {k: v for k, v in data.get("planDataFiles", {}).items() if k in ALLOWED}
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
for name in ("index.html", "app.js", "styles.css", "favicon.svg"):
    shutil.copy2(SRC / name, OUT / name)
(OUT / ".nojekyll").touch()
# Version static assets so browsers load the matching deployed interface.
html = (OUT / "index.html").read_text()
for name in ("app.js", "styles.css"):
    version = hashlib.sha256((OUT / name).read_bytes()).hexdigest()[:12]
    html = html.replace("./" + name, "./" + name + "?v=" + version)
(OUT / "index.html").write_text(html)
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
    data["planDataFiles"][plan] = "./" + path
(OUT / "data.json.gz").write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False).encode(), mtime=0))
assert {p["id"] for p in data["plans"]} == ALLOWED
print("Three-plan provider site built; linked local assets verified:", len(seen))
print("Plan medication records:", len(data["medications"]), "Plan policy records:", len(data["policies"]))
print("Shared AHCCCS statewide drug entries:", len(data["statewideDrugList"]), "FFS PA criteria sections:", len(data["statewidePaCriteria"]))
print("Individually source-checked drug guides:", len(data["statewideClinicalGuidance"]), "distinct policy sections:", len({g["policyCode"] for g in data["statewideClinicalGuidance"]}))
