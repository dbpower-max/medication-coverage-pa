"""Build a standalone site containing only the three provider-facing ACC plans."""
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, unquote
from link_provider_policies import attach_provider_policies

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "dist"
OUT = ROOT / "_site"
ALLOWED = {"az-complete-health", "banner-ufc", "uhc-community-az"}
subprocess.run([sys.executable, str(ROOT / 'tools/import_ach_baseline.py')], check=True)
data = json.loads(gzip.decompress((SRC / "data.json.gz").read_bytes()))
attach_provider_policies(data)
assert ALLOWED <= {p["id"] for p in data["plans"]}
for key, identity in (("plans", "id"), ("medications", "planId"), ("policies", "planId"), ("planEvidence", "planId")):
    data[key] = [r for r in data[key] if r.get(identity) in ALLOWED]
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
print("Medication records:", len(data["medications"]), "Policy records:", len(data["policies"]))
