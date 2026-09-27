"""Static contract tests only; no native or independent engine execution."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2] / "cases/simlox-air-support/c03-contract-prep-v1"
spec = importlib.util.spec_from_file_location("c03_prep", ROOT / "prepare.py")
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class C03PreparationTests(unittest.TestCase):
    def setUp(self):
        self.parameters = prep.read(ROOT / "parameters.json")
        self.one = prep.read(ROOT / "hand-ledger-capacity-1.json")
        self.two = prep.read(ROOT / "hand-ledger-capacity-2.json")

    def test_checked_six_candidates_are_reproducible(self):
        for case, cap in [(c, 2) for c in prep.CASES[:-1]] + [("C03", 1), ("C03", 2)]:
            with self.subTest(case=case, cap=cap):
                self.assertEqual((ROOT / "inputs" / f"{case}-capacity-{cap}.json").read_bytes(), prep.encoded(prep.build(case, cap)))

    def test_units_references_and_types_fail_explicitly(self):
        changes = [lambda p: p["units"].update(time="second"),
                   lambda p: p["units"].update(conversion=True),
                   lambda p: p["resources"][0].update(capacity=1),
                   lambda p: p["resources"][1].update(capacity=0),
                   lambda p: p["resources"][1].update(capacity=3),
                   lambda p: p["resources"][1].update(capacity=True),
                   lambda p: p["resources"][1].update(capacity=1.5),
                   lambda p: p["steps"][0].update(duration_minutes=float("nan")),
                   lambda p: p["steps"][1]["demands"].update(UNKNOWN=1),
                   lambda p: p["steps"][1]["demands"].update({"E-SHARED": 2}),
                   lambda p: p["missions"][0].update(aircraft_id="missing"),
                   lambda p: p.update(unknown_policy="cancel")]
        for change in changes:
            p = copy.deepcopy(self.parameters); change(p)
            with self.subTest(parameters=p), self.assertRaises(ValueError): prep.validate_parameters(p)

    def test_empty_demand_cannot_stand_in_for_resources(self):
        self.parameters["steps"][0]["demands"] = {}
        with self.assertRaisesRegex(ValueError, "empty resource"): prep.validate_parameters(self.parameters)

    def test_native_unsupported_flags_types_and_refs_rejected(self):
        mutations = [("System", "FRT", 1), ("Control", "ENPM", "Y"),
                     ("MissionPreparation", "DURND", "UNKNOWN"),
                     ("ResourceAllocation", "RQTY", 3),
                     ("SubTaskResource", "RID", "missing"),
                     ("TaskBreakDown", "DURN", -1),
                     ("Resource", "TYPE", "PERSONNEL"),
                     ("MissionType", "DURN", 1.5)]
        for table, column, value in mutations:
            model = prep.build()
            target = prep.writer.table(model, table)
            index = [c["name"] for c in target["columns"]].index(column)
            target["instances"][0]["rows"][0][index] = value
            with self.subTest(table=table, column=column), self.assertRaises(ValueError): prep.validate_native(model)

    def test_capacity_change_is_only_one_named_support_field(self):
        self.assertEqual(prep.capacity_delta(prep.build("C03", 1), prep.build("C03", 2)),
                         {"table": "ResourceAllocation", "key": {"POINT": "RESOURCE-AIR", "RID": "E-SHARED", "STID": "BASE-01"}, "column": "RQTY", "before": 1, "after": 2})
        with self.assertRaises(ValueError): prep.capacity_delta(prep.build("C02", 2), prep.build("C03", 2))

    def test_parent_candidates_retain_real_positive_work(self):
        for case in prep.CASES:
            rows = prep.validate_native(prep.build(case, 2))
            self.assertEqual([r["DURN"] * 60 for r in rows["TaskBreakDown"]], [10] if case == "B01" else [10, 40])
            self.assertEqual(len(rows["Resource"]), 0 if case in ("B01", "B02") else 1 if case == "C01" else 2)
            self.assertEqual(len(rows["SubTaskResource"]), 0 if case in ("B01", "B02") else 2 if case == "C01" else 3)
            self.assertEqual(rows["TaskResource"], [])

    def test_hand_ledger_wait_and_integrals(self):
        for ledger, wait in [(self.one, 20), (self.two, 0)]:
            result = prep.validate_ledger(ledger)
            self.assertFalse(result["native_verified"])
            self.assertEqual(result["waiting_minutes"], wait)
            self.assertEqual(result["resource_count_minutes"], {"P-SPECIALIST": 100, "E-SHARED": 80})

    def test_overallocation_and_false_zero_wait_are_rejected(self):
        self.one["jobs"]["MISSION-B"]["steps"][1].update(acquire=450, release=490)
        self.one["jobs"]["MISSION-B"].update(launch=500, **{"return": 560})
        self.one["waiting_minutes"] = 0
        with self.assertRaisesRegex(ValueError, "capacity conservation"): prep.validate_ledger(self.one)

    def test_early_release_and_launch_are_rejected(self):
        for field in ("release", "launch"):
            value = copy.deepcopy(self.one)
            if field == "release": value["jobs"]["MISSION-B"]["steps"][1][field] = 500
            else: value["jobs"]["MISSION-B"][field] = 500
            with self.subTest(field=field), self.assertRaises(ValueError): prep.validate_ledger(value)

    def test_observation_cut_does_not_cancel_or_release(self):
        before = copy.deepcopy(self.one)
        at455 = prep.observe_ledger(self.one, 455)
        self.assertEqual([x["mission"] for x in at455["active"]], ["MISSION-A"])
        self.assertEqual([x["mission"] for x in at455["waiting"]], ["MISSION-B"])
        self.assertFalse(at455["cancelled_by_observation"])
        self.assertEqual(self.one, before)
        left = prep.observe_ledger(self.one, 510, "left")
        right = prep.observe_ledger(self.one, 510, "right")
        self.assertEqual([x["mission"] for x in left["active"]], ["MISSION-B"])
        self.assertEqual(right["active"], [])

    def test_equal_totals_do_not_hide_different_progress(self):
        self.assertEqual(self.one["resource_count_minutes"], self.two["resource_count_minutes"])
        self.assertEqual(prep.observe_ledger(self.one, 470)["active"][0]["release"], 510)
        self.assertEqual(prep.observe_ledger(self.two, 470)["active"][0]["release"], 490)

    def test_cli_refuses_to_overwrite_an_existing_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "input.json"
            command = [sys.executable, str(ROOT / "prepare.py"), "--output", str(target)]
            first = subprocess.run(command, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = target.read_bytes()
            again = subprocess.run(command, capture_output=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
