#!/usr/bin/env python3
"""Review-only RxNorm brand-identity pilot and monthly semantic diff.

Uses NLM RxNav (https://rxnav.nlm.nih.gov/REST/) with exact matching only.
Never mutates drug records, payer data, PA guidance, or production search.
A brand-level RxCUI is NOT an identifier for a specific strength/route/NDC.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://rxnav.nlm.nih.gov/REST"
TTYS = {"BN"}
SCHEMA_VERSION = 1


class RxNormError(Exception):
    pass


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def validate_targets(data):
    assert data.get("schemaVersion") == SCHEMA_VERSION, "Unsupported target schema"
    records = data.get("records")
    assert isinstance(records, list) and len(records) >= 1
    ids, names = set(), set()
    for row in records:
        ident = row.get("medicationId", "")
        name = row.get("lookupName", "")
        assert isinstance(ident, str) and ident.startswith("rxp-") and ident not in ids
        assert isinstance(name, str) and name.strip() and name.casefold() not in names
        assert row.get("expectedTty") in TTYS, "Only brand-level pilot targets allowed"
        assert row.get("resolution") == "review_required", "Cannot pre-approve medication mapping"
        ids.add(ident)
        names.add(name.casefold())
    return records


def fetch_json(path, params=None):
    query = "?" + urlencode(params) if params else ""
    request = Request(BASE_URL + "/" + path + query, headers={"User-Agent": "AHCCCS-RxNorm-Pilot/0.1 (review-only)", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RxNormError("RxNav HTTP status " + str(exc.code)) from exc
        except (URLError, TimeoutError, ValueError) as exc:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RxNormError("RxNav request failed: " + str(exc)) from exc
    raise RxNormError("RxNav attempts exhausted")


def get_concept(ident):
    raw = fetch_json("rxcui/" + ident + "/properties.json")
    props = raw.get("properties") or {}
    if not isinstance(props, dict) or not props.get("rxcui"):
        raise RxNormError("No valid RxNorm properties for candidate " + ident)
    return {
        "rxcui": str(props["rxcui"]),
        "name": str(props.get("name") or ""),
        "tty": str(props.get("tty") or ""),
        "suppress": str(props.get("suppress") or ""),
    }


def lookup_target(row):
    query = row["lookupName"]
    data = fetch_json("rxcui.json", {"name": query, "search": 0})
    ids = sorted(set(str(x) for x in ((data.get("idGroup") or {}).get("rxnormId") or [])))
    if len(ids) > 10:
        raise RxNormError("Unexpectedly broad exact search for " + query)
    candidates = sorted((get_concept(x) for x in ids), key=lambda c: c["rxcui"])
    exact = [c for c in candidates if c["name"].casefold() == query.casefold() and c["tty"] == row["expectedTty"] and c["suppress"] in ("", "N")]
    status = "brand_candidate_review_required" if len(candidates) == 1 and len(exact) == 1 else "unresolved_review_required"
    return {
        "medicationId": row["medicationId"],
        "lookupName": query,
        "expectedTty": row["expectedTty"],
        "status": status,
        "candidateRxcui": exact[0]["rxcui"] if status == "brand_candidate_review_required" else None,
        "candidates": candidates,
    }


def refresh(target_path):
    targets = validate_targets(read_json(target_path))
    version_data = fetch_json("version.json")
    version = version_data.get("version")
    if not isinstance(version, str) or not version.strip():
        raise RxNormError("Missing RxNorm release version")
    results = [lookup_target(row) for row in targets]
    return {"schemaVersion": SCHEMA_VERSION, "rxnormVersion": version, "mappingLevel": "BN-only; requires product-specific review", "records": results}


def validate_snapshot(snapshot):
    if snapshot.get("schemaVersion") != SCHEMA_VERSION or not isinstance(snapshot.get("records"), list):
        raise ValueError("Invalid snapshot schema")
    ids = set()
    for row in snapshot["records"]:
        ident = row.get("medicationId")
        if not ident or ident in ids:
            raise ValueError("Duplicate or missing medication ID in snapshot")
        ids.add(ident)
        status = row.get("status")
        if status not in ("brand_candidate_review_required", "unresolved_review_required"):
            raise ValueError("Unreviewed mappings cannot be marked approved")
        if status == "brand_candidate_review_required":
            if not row.get("candidateRxcui") or len(row.get("candidates", [])) != 1:
                raise ValueError("Brand candidate needs unique RxCUI")
        elif row.get("candidateRxcui") is not None:
            raise ValueError("Ambiguous or missing match must not be mapped")
    return {row["medicationId"]: row for row in snapshot["records"]}


def make_diff(old, new):
    old_ids = validate_snapshot(old)
    new_ids = validate_snapshot(new)
    added = sorted(set(new_ids) - set(old_ids))
    missing = sorted(set(old_ids) - set(new_ids))
    changed = sorted(x for x in set(old_ids) & set(new_ids) if old_ids[x] != new_ids[x])
    return {
        "oldVersion": old.get("rxnormVersion"),
        "newVersion": new.get("rxnormVersion"),
        "added": added,
        "missing": missing,
        "changed": changed,
        "unchanged": len(set(old_ids) & set(new_ids)) - len(changed),
        "needsReview": sorted(x for x, row in new_ids.items() if row["status"] == "unresolved_review_required"),
    }


def markdown_report(diff):
    lines = [
        "# RxNorm pilot monthly comparison (review only)",
        "",
        "**No medication data, clinical requirements, formulary flags or app cards were changed.**",
        "",
        "Previous RxNorm release: " + str(diff["oldVersion"] or "not yet fetched"),
        "",
        "Current RxNorm release: " + str(diff["newVersion"] or "unknown"),
        "",
        "| Change | Count |",
        "|---|---:|",
        "| New candidate identities | " + str(len(diff["added"])) + " |",
        "| Changed candidate identities | " + str(len(diff["changed"])) + " |",
        "| Missing identities | " + str(len(diff["missing"])) + " |",
        "| Unchanged identities | " + str(diff["unchanged"]) + " |",
        "| Unresolved requiring review | " + str(len(diff["needsReview"])) + " |",
        "",
    ]
    for label, key in (("Added", "added"), ("Changed", "changed"), ("Missing", "missing"), ("Unresolved", "needsReview")):
        if diff[key]:
            lines.append("## " + label)
            lines.extend("- " + x for x in diff[key])
            lines.append("")
    lines.extend([
        "## Safety gate",
        "",
        "- Every RxCUI here is a **brand-level candidate** (TTY BN), not an approved medication-to-RxCUI crosswalk.",
        "- No fuzzy/substring product matching; ambiguous and absent records are never automatically resolved.",
        "- Product strength, route, release mechanism, brand, NDC, and payer requirements require independent source verification.",
        "- This automation may propose a review PR but MUST NOT auto-merge, update insurance coverage, or deploy app behavior.",
        "",
    ])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    x = sub.add_parser("refresh", help="Fetch exact RxNorm BN candidates")
    x.add_argument("--targets", required=True)
    x.add_argument("--output", required=True)
    d = sub.add_parser("diff", help="Compare two saved snapshots")
    d.add_argument("--previous", required=True)
    d.add_argument("--current", required=True)
    d.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    if args.action == "refresh":
        result = refresh(args.targets)
        write_json(args.output, result)
        print("Fetched RxNorm", result["rxnormVersion"], "; candidates:", len(result["records"]))
    elif args.action == "diff":
        result = make_diff(read_json(args.previous), read_json(args.current))
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown_report(result), encoding="utf-8")
        print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in result.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RxNormError, AssertionError, ValueError) as exc:
        print("RxNorm pilot failed safely: " + str(exc), file=sys.stderr)
        sys.exit(1)
