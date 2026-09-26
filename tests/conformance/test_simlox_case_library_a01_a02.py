"""Pure validator tests plus optional checks of retained 4700-3 native evidence."""
from __future__ import annotations

import importlib.util
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "cases/simlox-air-support"
TOOLS = LIB / "tools"
sys.path.insert(0, str(TOOLS))


def module(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


generator = module("generate_native")
catalog = module("build_catalog")
delta = module("diff_native")
validator = module("validate_native")
collection = module("validate_collection")
margin = module("validate_horizon")


class CaseLibraryTests(unittest.TestCase):
    def test_catalog_has_26_entries_but_only_two_implemented(self):
        entries = catalog.build()["cases"]
        self.assertEqual(len(entries), 26)
        self.assertEqual(len({entry["case_id"] for entry in entries}), 26)
        self.assertEqual([entry["case_id"] for entry in entries if entry["version"]], ["A01", "A02"])
        self.assertTrue(all(entry["status"] == "planned" for entry in entries[2:]))
        self.assertTrue(all(entry["status"] == "cli_behavior_verified_gui_pending" for entry in entries[:2]))

    def test_frozen_generator_rejects_invalid_contract_values_and_types(self):
        original = json.loads((generator.DIRS["A01"] / "parameters.json").read_text(encoding="utf-8"))
        for key, value in (("mission_duration_hours", -1.0), ("mission_duration_hours", 3.0),
                           ("repetitions", 2), ("native_seed_text", 1),
                           ("version", "2.0.0"), ("horizon_hours", float("nan"))):
            changed = copy.deepcopy(original)
            changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                generator.build(changed)

    def test_generated_inputs_keep_single_aircraft_and_only_add_two_wave_rows(self):
        for case_id, directory in generator.DIRS.items():
            parameters = json.loads((directory / "parameters.json").read_text(encoding="utf-8"))
            model = generator.build(parameters)
            checked = json.loads((directory / "native-input.json").read_text(encoding="utf-8"))
            self.assertEqual(model, checked)
            self.assertEqual(generator.table(model, "SystemDeployment")["instances"][0]["rows"][0][2], 1)
            self.assertEqual(generator.table(model, "Item")["instances"][0]["rows"], [])
            self.assertEqual(generator.table(model, "TaskResource")["instances"][0]["rows"], [])
            self.assertEqual(generator.table(model, "StockAllocation")["instances"][0]["rows"], [])
        changes = delta.compare()["changed_tables"]
        self.assertEqual(list(changes), ["OperationProfile"])
        self.assertEqual(changes["OperationProfile"]["removed"], [])
        self.assertEqual([row["STIM"] for row in changes["OperationProfile"]["added"]], [20.0, 32.0])

    def test_hand_calculation_and_minute_conversion(self):
        for case_id, directory in generator.DIRS.items():
            contract = json.loads((directory / "contract.json").read_text(encoding="utf-8"))
            hand = contract["hand_expected"]
            starts = contract["mission"]["schedule_hours"]
            self.assertEqual(contract["hours_to_minutes"], 60)
            self.assertEqual(hand["notification_hours"], [start - 1 for start in starts])
            self.assertEqual(hand["actual_end_hours"], [start + 2 for start in starts])
            self.assertEqual(hand["flight_hours_integral"] * 60, 120 * len(starts))
            self.assertEqual((hand["planned_waves"], hand["sorties"], hand["unfinished_at_horizon"]),
                             (len(starts), len(starts), 0))

    def test_generated_bytes_reproduce_frozen_native_inputs(self):
        for case_id, directory in generator.DIRS.items():
            parameters = json.loads((directory / "parameters.json").read_text(encoding="utf-8"))
            encoded = (json.dumps(generator.build(parameters), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            self.assertEqual(encoded, (directory / "native-input.json").read_bytes())

    def test_observed_window_clips_actual_mission_interval(self):
        self.assertEqual(collection.clipped_flight_hours(8, 10, 7.5), 0)
        self.assertEqual(collection.clipped_flight_hours(8, 10, 9), 1)
        self.assertAlmostEqual(collection.clipped_flight_hours(8, 10, 9.9999), 1.9999)
        self.assertEqual(collection.clipped_flight_hours(8, 10, 10), 2)
        self.assertEqual(collection.clipped_flight_hours(8, 10, 10.0001), 2)
        self.assertEqual(collection.clipped_flight_hours(8, None, 9), 1)

    def test_native_collection_window_matrix_if_available(self):
        base = REPO / "data/local/simlox-case-library/v1/collection-runs"
        expected = {"before_launch": (0, 1, 0, 0, 0), "in_flight": (1, 0, 1, 0, 1),
                    "before_completion": (1.9999, 0, 1, 0, 1),
                    "printed_tie": (2, 0, 0, 1, 1), "after_completion": (2, 0, 0, 1, 1)}
        if not all((base / f"a01-collection-{name.replace('_', '-')}-20260927-01/validation.json").exists()
                   for name in expected):
            self.skipTest("native collection-window evidence is local to 4700-3")
        for name, (hours, unlaunched, in_flight, completed, summary_fraction) in expected.items():
            with self.subTest(variant=name):
                run = base / f"a01-collection-{name.replace('_', '-')}-20260927-01"
                result = collection.validate(run, name, write=False)
                obs = result["observation"]
                self.assertEqual(result["conversion"]["errors"], 0)
                self.assertAlmostEqual(obs["flight_hours_clipped_from_events"], hours, places=5)
                self.assertAlmostEqual(obs["native_ftmo_interval_integral_hours"], hours, places=5)
                self.assertEqual((obs["planned_unlaunched_at_collection_end"],
                                  obs["in_flight_at_collection_end"], obs["completed_by_collection_end"]),
                                 (unlaunched, in_flight, completed))
                self.assertEqual(obs["native_summary_window_hours"], [0, 36])
                self.assertEqual(obs["native_summary_mstf_msuf"], [summary_fraction, summary_fraction])

    def test_native_short_simulation_period_is_invalid_if_available(self):
        base = REPO / "data/local/simlox-case-library/v1/horizon-runs"
        names = ("before-launch", "in-flight", "before-completion", "printed-tie", "after-completion")
        if not all((base / f"a01-horizon-{name}-20260927-01/model.sxo").exists() for name in names):
            self.skipTest("native SIMPE-boundary evidence is local to 4700-3")
        for name in names:
            with self.subTest(variant=name):
                run = base / f"a01-horizon-{name}-20260927-01"
                self.assertEqual((run / "model.sxo").stat().st_size, 4)
                self.assertIn("(error #204)", (run / "run.log").read_text(encoding="utf-8"))
                self.assertTrue(validator.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])

    def test_native_positive_simulation_margin_controls_if_available(self):
        base = REPO / "data/local/simlox-case-library/v1/simpe-margin-runs"
        names = ("margin_10p5", "margin_12")
        if not all((base / f"a01-simpe-{name.replace('_', '-')}-20260927-01/validation.json").exists() for name in names):
            self.skipTest("native SIMPE positive controls are local to 4700-3")
        for name, end in (("margin_10p5", 10.5), ("margin_12", 12)):
            with self.subTest(variant=name):
                run = base / f"a01-simpe-{name.replace('_', '-')}-20260927-01"
                result = margin.validate(run, name, write=False)
                self.assertEqual(result["status"], "native_probe_recorded")
                self.assertEqual(result["conversion"]["errors"], 0)
                self.assertEqual(result["observation"]["native_summary_window_hours"], [0, end])
                self.assertEqual(result["observation"]["starts_hours_printed"], [8])
                self.assertEqual(result["observation"]["completions_hours_printed"], [10])
                self.assertGreater((run / "model.sxo").stat().st_size, 4)

    def test_roundtrip_detects_one_business_field_mutation(self):
        source = LIB / "A01-single-aircraft-single-mission/native-input.json"
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "changed.json"
            model = json.loads(source.read_text(encoding="utf-8"))
            table = generator.table(model, "MissionType")
            names = [column["name"] for column in table["columns"]]
            table["instances"][0]["rows"][0][names.index("DURN")] = 3
            changed.write_text(json.dumps(model), encoding="utf-8")
            self.assertFalse(validator.compare_roundtrip(source, changed)["all_equal"])
            self.assertIn("MissionType", validator.compare_roundtrip(source, changed)["changed"])

    def test_report_trailing_comma_normalizer_respects_quoted_text(self):
        raw = b'{"text":"literal ,}","values":[1,2,],}'
        result = json.loads(validator.remove_trailing_commas(raw))
        self.assertEqual(result, {"text": "literal ,}", "values": [1, 2]})

    def test_native_initial_inert_row_is_rejected_for_no_preparation_contract(self):
        base = REPO / "data/local/simlox-case-library/v1"
        for case_id, stem in (("A01", "a01-initial-20260927-01"), ("A02", "a02-initial-20260927-01")):
            run = base / case_id / stem
            if not (run / "model.sxo").exists():
                self.skipTest("4700-3 native evidence is intentionally local")
            with self.subTest(case_id=case_id):
                contract = json.loads((generator.DIRS[case_id] / "contract.json").read_text(encoding="utf-8"))
                report = json.loads(validator.remove_trailing_commas((run / "report-raw.json").read_bytes()))
                behavior = validator.expected_behavior(validator.parse_log(run / "model.log"), contract, report)
                self.assertFalse(behavior["passed"])
                self.assertEqual(behavior["flight_hours_from_system_results"], 2 if case_id == "A01" else 6)
                self.assertEqual(behavior["native_zero_duration_preparation_count"], 1 if case_id == "A01" else 3)
                self.assertEqual(behavior["differences"][0]["field"], "unintended_native_preparation_count")

    def test_final_native_cases_and_independent_replays_if_available(self):
        base = REPO / "data/local/simlox-case-library/v1"
        names = {"A01": ("a01-final-20260927-01", "a01-replay-20260927-02"),
                 "A02": ("a02-final-20260927-01", "a02-replay-20260927-02")}
        if not all((base / case / run / "validation.json").exists() for case, runs in names.items() for run in runs):
            self.skipTest("fresh 4700-3 native replay is still pending")
        for case_id, runs in names.items():
            signatures = []
            for run_name in runs:
                run = base / case_id / run_name
                result = validator.validate(run, case_id, write=False)
                self.assertEqual(result["status"], "cli_behavior_verified")
                self.assertEqual(result["behavior"]["native_zero_duration_preparation_count"], 0)
                self.assertEqual(result["artifacts"]["input.json"]["sha256"], generator.sha256(generator.DIRS[case_id] / "native-input.json"))
                signatures.append([(event["kind"], event["time_hours_printed"], event["text"])
                                   for event in result["event_index"] if event["kind"] in {"notification", "start", "success", "completion", "ready_increased"}])
            self.assertEqual(signatures[0], signatures[1])

    def test_native_conversion_error_is_rejected(self):
        source = REPO / "data/local/simlox-case-library/v1/A01/a01-final-20260927-01"
        if not (source / "model.sxo").exists():
            self.skipTest("4700-3 native evidence is intentionally local")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            for name in ("input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json", "run.log", "model.log", "steps.json"):
                shutil.copy2(source / name, target / name)
            log = (target / "run.log").read_text(encoding="utf-8")
            (target / "run.log").write_text(log.replace("Errors: 0", "Errors: 1"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native conversion/roundtrip invalid"):
                validator.validate(target, "A01", write=False)

    def test_native_missing_short_and_mixed_artifacts_are_rejected(self):
        source = REPO / "data/local/simlox-case-library/v1/A01/a01-final-20260927-01"
        if not (source / "model.sxo").exists():
            self.skipTest("4700-3 native evidence is intentionally local")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            for path in source.iterdir():
                if path.is_file():
                    shutil.copy2(path, target / path.name)
            (target / "model.sxo").write_bytes(b"ABCD")
            with self.assertRaisesRegex(ValueError, "missing/invalid native artifact"):
                validator.validate(target, "A01", write=False)
            shutil.copy2(source / "model.sxo", target / "model.sxo")
            shutil.copy2(REPO / "data/local/simlox-case-library/v1/A02/a02-final-20260927-01/input.json", target / "input.json")
            with self.assertRaisesRegex(ValueError, "input differs from checked"):
                validator.validate(target, "A01", write=False)

    def test_native_duplicate_event_wrong_identity_and_truncation_are_rejected(self):
        source = REPO / "data/local/simlox-case-library/v1/A01/a01-final-20260927-01"
        if not (source / "model.sxo").exists():
            self.skipTest("4700-3 native evidence is intentionally local")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            for name in ("input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json", "run.log", "model.log", "steps.json"):
                shutil.copy2(source / name, target / name)
            baseline = (target / "model.log").read_text(encoding="utf-8")
            cases = {
                "duplicate": (baseline.replace(" mission starting, duration:", " mission starting, duration:", 1) +
                              next(line for line in baseline.splitlines() if " mission starting, duration:" in line) + "\n", "start"),
                "wrong_sid": (baseline.replace("mission completed: <TEACH-AIR-01,0>", "mission completed: <OTHER-SID,0>"), "completion_identity"),
                "truncated": ("\n".join(line for line in baseline.splitlines() if " mission completed:" not in line) + "\n", "completion"),
            }
            for name, (log, field) in cases.items():
                with self.subTest(name=name):
                    (target / "model.log").write_text(log, encoding="utf-8")
                    result = validator.validate(target, "A01", write=False)
                    self.assertEqual(result["status"], "cli_behavior_mismatch")
                    self.assertIn(field, [difference["field"] for difference in result["behavior"]["differences"]])


if __name__ == "__main__":
    unittest.main()
