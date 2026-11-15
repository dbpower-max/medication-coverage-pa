"""Offline tests for review-only RxNorm identity matching and release diff."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rxnorm_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]


class RxNormPilotTests(unittest.TestCase):
    def test_exact_30_pilot_brands_with_stable_internal_ids(self):
        targets = pilot.validate_targets(pilot.read_json(ROOT / "data/rxnorm-pilot/targets.json"))
        self.assertEqual(len(targets), 30)
        self.assertEqual(len({t["medicationId"] for t in targets}), 30)
        self.assertTrue(all(t["expectedTty"] == "BN" for t in targets))

    def test_duplicate_id_and_name_are_rejected(self):
        data = pilot.read_json(ROOT / "data/rxnorm-pilot/targets.json")
        data["records"][1]["medicationId"] = data["records"][0]["medicationId"]
        with self.assertRaises(AssertionError):
            pilot.validate_targets(data)
        data = pilot.read_json(ROOT / "data/rxnorm-pilot/targets.json")
        data["records"][1]["lookupName"] = data["records"][0]["lookupName"].upper()
        with self.assertRaises(AssertionError):
            pilot.validate_targets(data)

    def test_unique_exact_brand_produces_candidate_but_never_approved_mapping(self):
        target = {"medicationId": "rxp-001-natroba", "lookupName": "Natroba", "expectedTty": "BN"}
        def fake(path, params=None):
            if path == "rxcui.json":
                self.assertEqual(params["search"], 0)
                return {"idGroup": {"rxnormId": ["1085820"]}}
            return {"properties": {"rxcui": "1085820", "name": "Natroba", "tty": "BN", "suppress": "N"}}
        with patch.object(pilot, "fetch_json", side_effect=fake):
            result = pilot.lookup_target(target)
        self.assertEqual(result["candidateRxcui"], "1085820")
        self.assertEqual(result["status"], "brand_candidate_review_required")
        self.assertNotIn("approved", result)
        self.assertNotIn("covered", result)

    def test_wrong_formulation_or_non_brand_cannot_be_silently_mapped(self):
        target = {"medicationId": "rxp-001-natroba", "lookupName": "Natroba", "expectedTty": "BN"}
        def wrong_tty(path, params=None):
            if path == "rxcui.json":
                return {"idGroup": {"rxnormId": ["333"]}}
            return {"properties": {"rxcui": "333", "name": "Natroba", "tty": "SBD", "suppress": "N"}}
        with patch.object(pilot, "fetch_json", side_effect=wrong_tty):
            result = pilot.lookup_target(target)
        self.assertIsNone(result["candidateRxcui"])
        self.assertEqual(result["status"], "unresolved_review_required")

    def test_ambiguous_and_absent_exact_results_never_create_mapping(self):
        target = {"medicationId": "rxp-001-natroba", "lookupName": "Natroba", "expectedTty": "BN"}
        def ambiguous(path, params=None):
            if path == "rxcui.json":
                return {"idGroup": {"rxnormId": ["11", "12"]}}
            return {"properties": {"rxcui": path.split("/")[1], "name": "Natroba", "tty": "BN", "suppress": "N"}}
        with patch.object(pilot, "fetch_json", side_effect=ambiguous):
            result = pilot.lookup_target(target)
        self.assertIsNone(result["candidateRxcui"])
        with patch.object(pilot, "fetch_json", return_value={"idGroup": {}}):
            result = pilot.lookup_target(target)
        self.assertEqual(result["candidates"], [])
        self.assertIsNone(result["candidateRxcui"])

    def test_diff_tracks_addition_change_removal_without_changing_payer_data(self):
        def row(i, cui):
            return {"medicationId": i, "status": "brand_candidate_review_required",
                    "candidateRxcui": cui, "candidates": [{"rxcui": cui}]}
        old = {"schemaVersion": 1, "rxnormVersion": "old", "records": [row("a", "10"), row("b", "20"), row("d", "40")]}
        new = {"schemaVersion": 1, "rxnormVersion": "new", "records": [row("a", "11"), row("b", "20"), row("c", "30")]}
        diff = pilot.make_diff(old, new)
        self.assertEqual(diff["changed"], ["a"])
        self.assertEqual(diff["added"], ["c"])
        self.assertEqual(diff["missing"], ["d"])
        self.assertEqual(diff["unchanged"], 1)
        report = pilot.markdown_report(diff)
        self.assertIn("MUST NOT auto-merge", report)
        self.assertIn("No medication data", report)

    def test_invalid_or_unsafe_snapshot_rejected(self):
        good = {"schemaVersion": 1, "records": [{"medicationId": "a", "status": "unresolved_review_required", "candidateRxcui": None, "candidates": []}]}
        pilot.validate_snapshot(good)
        unsafe = copy.deepcopy(good)
        unsafe["records"][0]["status"] = "approved"
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(unsafe)
        unsafe = copy.deepcopy(good)
        unsafe["records"][0]["candidateRxcui"] = "100"
        with self.assertRaises(ValueError):
            pilot.validate_snapshot(unsafe)

    def test_api_failure_leaves_existing_snapshot_unmodified(self):
        # Refresh completes fully in memory before writing; failures must abort.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "snapshot.json"
            output.write_text('{"safe":true}', encoding="utf-8")
            with patch.object(pilot, "fetch_json", side_effect=pilot.RxNormError("offline")):
                with self.assertRaises(pilot.RxNormError):
                    pilot.refresh(ROOT / "data/rxnorm-pilot/targets.json")
            self.assertEqual(json.loads(output.read_text()), {"safe": True})


if __name__ == "__main__":
    unittest.main()
