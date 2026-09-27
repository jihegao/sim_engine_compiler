"""Executable checks for J35 source coverage and the observable spare ledger.

These checks establish properties of the fixed Plan and Python baseline. They do
not claim native SIMLOX conformance or physical repair-return conservation.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sim_engine_compiler.compiler import compile_aircraft_support
from sim_engine_compiler.reference import SimpyReferenceRuntime


def load_script(name: str):
    path = ROOT / "scripts" / "simlox" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class J35ContractProbeTests(unittest.TestCase):
    def test_native_analyzers_require_exact_ordered_four_step_evidence(self):
        complete = [
            {"name": name, "exit_code": 0}
            for name in ("import", "export", "calc", "jsonreport")
        ]
        incomplete = complete[:-1]
        reordered = [complete[1], complete[0], *complete[2:]]
        duplicated = [*complete, complete[-1]]
        failed = [*complete[:2], {"name": "calc", "exit_code": 1}, complete[-1]]

        for script in ("analyze_j35_cancel_matrix.py", "analyze_j35_stock_repair.py"):
            analyzer = load_script(script)
            with self.subTest(script=script, evidence="complete"):
                analyzer.require_complete_native_steps(complete, case="probe")
            for evidence, steps in (
                ("incomplete", incomplete),
                ("reordered", reordered),
                ("duplicated", duplicated),
                ("failed", failed),
            ):
                with self.subTest(script=script, evidence=evidence):
                    with self.assertRaisesRegex(ValueError, "probe:.*native step|probe: expected native steps"):
                        analyzer.require_complete_native_steps(steps, case="probe")

    def test_all_lru_products_keep_stable_source_and_shared_pools(self):
        rows, summary = load_script("audit_j35_lru_contract.py").audit()
        self.assertEqual((len(rows), summary["lru_count"]), (403, 403))
        self.assertEqual(Counter(row["depth_from_aircraft"] for row in rows), {2: 167, 3: 236})
        self.assertEqual(len({row["source_path"] for row in rows}), 403)
        self.assertEqual(len({row["product_id"] for row in rows}), 403)
        self.assertEqual(summary["lru_eight_tail_component_instances_inferred"], 3224)
        self.assertEqual(summary["shared_stock_pool_count"], 2)
        self.assertEqual(summary["initial_base_stock"], 501)
        self.assertEqual(summary["initial_depot_stock"], 0)
        self.assertEqual(summary["shared_resource_nodes"][1]["personnel_capacity"], 40)
        self.assertEqual(summary["shared_resource_nodes"][1]["equipment_capacity"], 60)
        self.assertTrue(all(row["installed_tail_numbers"] == "|".join(f"J35-{n:02}" for n in range(1, 9)) for row in rows))

    def test_diff_reports_float_value_without_rounding_and_structural_changes(self):
        diff = load_script("compare_j35_run_results.py").differences(
            {"sample_requests": [{"value_minutes": 1.0}], "trace": [1]},
            {"sample_requests": [{"value_minutes": 1.0 + 2**-52}], "trace": [1, 2], "new": True},
        )
        self.assertEqual([item["kind"] for item in diff], ["missing", "value", "length"])
        self.assertEqual(diff[1]["path"], "$.sample_requests[0].value_minutes")
        self.assertEqual(diff[1]["absolute_difference"], 2**-52)

    def test_historical_native_roundtrip_preserves_every_business_row(self):
        prior = Path("C:/Users/user/Documents/Codex/2026-09-26/simlox-j35-event-parity/workspace/evidence/phase7/sid8-pm-first20")
        if not prior.exists():
            self.skipTest("4700-3 prior native evidence is local and intentionally absent from Git")
        report = load_script("verify_native_roundtrip.py").compare(
            prior / "sid8-pm-first20.json", prior / "sid8-pm-first20-roundtrip.json"
        )
        self.assertTrue(report["all_equal"])
        self.assertEqual(len(report["tables"]), 32)

    def test_local_cancel_matrix_has_provenance_for_every_changed_field(self):
        maker = load_script("make_j35_cancel_matrix.py")
        if not maker.SOURCE.exists() or not maker.OUTPUT.exists():
            self.skipTest("4700-3 raw cancellation matrix is intentionally outside Git")
        source = json.loads(maker.SOURCE.read_text(encoding="utf-8"))
        inputs = sorted(maker.OUTPUT.glob("p1-*/p1-*.json"))
        self.assertEqual(len(inputs), 12)
        for path in inputs:
            with self.subTest(case=path.parent.name):
                model = json.loads(path.read_text(encoding="utf-8"))
                provenance = json.loads((path.parent / "provenance.json").read_text(encoding="utf-8"))
                self.assertEqual(maker.sha256(path), provenance["input_sha256"])
                self.assertEqual(maker.field_diff(source, model), provenance["changes_from_source"])
                self.assertEqual(len(maker.rows(maker.table(model, "MissionSystem"))), 2)
                self.assertTrue(all(row["FRT"] == 0 for row in maker.rows(maker.table(model, "Item"))))

    def test_valid_native_matrix_separates_missing_system_from_resource_delay(self):
        analyzer = load_script("analyze_j35_cancel_matrix.py")
        base = analyzer.BASE
        if not (base / "coordinator-p1-before" / "validity.json").exists():
            self.skipTest("4700-3 native coordinator evidence is intentionally outside Git")
        cases = {
            path.name.removeprefix("coordinator-"): analyzer.analyze_case(path)
            for path in sorted(base.glob("coordinator-p1-*"))
        }
        self.assertEqual(len(cases), 12)
        # PMLocation.PMT was changed, but actual PM task duration stayed 24h.
        self.assertEqual({event["time_hours_printed"] for case in cases.values() for event in case["events"] if event["kind"] == "pm_completed"}, {"48"})
        self.assertEqual(cases["p1-before"]["pm_location_pmt_hours"], [29.95])
        self.assertEqual(cases["p1-before"]["pm_task_step_durn_hours"], [24.0])
        self.assertEqual([(event["kind"], event["time_hours_printed"]) for event in cases["p1-before"]["outcomes"]], [("mission_started", "56")])
        constrained = cases["p1-resource-one"]
        self.assertEqual([(event["kind"], event["time_hours_printed"]) for event in constrained["outcomes"]], [("mission_cancelled", "56.3333")])
        self.assertTrue(any("Systems in prep: <J35-B,1>" in line for line in constrained["outcomes"][0]["snapshot"]))
        self.assertTrue(any(event["kind"] == "step_stopped" and event["time_hours_printed"] == "56.3333" for event in constrained["events"]))
        self.assertTrue(any(event["kind"] == "resource_released" and event["line"] > constrained["outcomes"][0]["line"] and event["time_hours_printed"] == "56.3333" for event in constrained["events"]))
        adjacent = cases["p1-next-wave"]
        self.assertEqual([(event["kind"], event["time_hours_printed"]) for event in adjacent["outcomes"]], [("mission_cancelled", "54.9667"), ("mission_started", "56")])
        self.assertEqual([row["STIM"] for row in adjacent["operation_profile"]], [56, 57])

    def test_corrected_pm_matrix_changes_actual_task_duration(self):
        maker = load_script("make_j35_cancel_matrix.py")
        files = sorted(path for path in maker.OUTPUT.glob("p1v2-*/p1v2-*.json") if path.stem == path.parent.name)
        if not files:
            self.skipTest("4700-3 corrected native inputs are intentionally outside Git")
        self.assertEqual(len(files), 8)
        for path in files:
            with self.subTest(case=path.parent.name):
                model = json.loads(path.read_text(encoding="utf-8"))
                manifest = json.loads((path.parent / "provenance.json").read_text(encoding="utf-8"))
                self.assertEqual(maker.sha256(path), manifest["input_sha256"])
                pm_rows = [row for row in maker.rows(maker.table(model, "TaskBreakDown")) if row["TID"] == "PM_25H"]
                self.assertEqual(len(pm_rows), 1)
                self.assertEqual(pm_rows[0]["DURN"], manifest["probe_parameters"]["pm_step_duration_hours"])
                self.assertEqual(maker.rows(maker.table(model, "PMLocation"))[0]["PMT"], 24)

    def test_corrected_native_pm_cutoff_uses_remaining_preparation(self):
        analyzer = load_script("analyze_j35_cancel_matrix.py")
        base = analyzer.BASE
        if not (base / "p1v2-pm-before" / "validity.json").exists():
            self.skipTest("Corrected native runs require the coordinator SSH launch context")
        expected = {
            "p1v2-pm-before": "mission_started", "p1v2-pm-tie": "mission_cancelled",
            "p1v2-pm-after": "mission_cancelled", "p1v2-pm-dtim40-before": "mission_started",
            "p1v2-pm-dtim40-after": "mission_cancelled", "p1v2-pm-step-short": "mission_started",
            "p1v2-zero-before": "mission_started", "p1v2-zero-after": "mission_cancelled",
        }
        for stem, outcome in expected.items():
            with self.subTest(case=stem):
                case = analyzer.analyze_case(base / stem)
                self.assertEqual([e["kind"] for e in case["outcomes"]], [outcome])
                wait = next(e for e in case["events"] if e["kind"] == "mission_waiting")
                profile = case["operation_profile"][0]
                prep = case["preparation_durn_hours"][0]
                printed_timeout = float(wait["text"].rsplit("timeout at ", 1)[1])
                self.assertAlmostEqual(printed_timeout, profile["STIM"] + profile["DTIM"] - prep, delta=0.0001)
        before = analyzer.analyze_case(base / "p1v2-pm-before")
        ready = next(e for e in before["events"] if e["kind"] == "pm_completed")
        self.assertAlmostEqual(float(before["outcomes"][0]["time_hours_printed"]), float(ready["time_hours_printed"]) + before["preparation_durn_hours"][0], delta=0.0001)
        tie = analyzer.analyze_case(base / "p1v2-pm-tie")
        pm = next(e for e in tie["events"] if e["kind"] == "pm_completed")
        self.assertEqual(tie["outcomes"][0]["time_hours_printed"], pm["time_hours_printed"])
        self.assertLess(tie["outcomes"][0]["line"], pm["line"])

    def test_compact_native_event_index_matches_validated_logs(self):
        analyzer = load_script("analyze_j35_cancel_matrix.py")
        index = json.loads((ROOT / "docs/simlox/j35-cancel-matrix-evidence.json").read_text(encoding="utf-8"))
        cases = {case["case"]: case for case in index["cases"]}
        self.assertEqual(len(cases), 20)
        if not (analyzer.BASE / "p1v2-pm-before" / "validity.json").exists():
            self.skipTest("The native logs are retained only on 4700-3")
        for stem in ("p1v2-pm-before", "p1v2-pm-tie", "p1v2-pm-after", "coordinator-p1-resource-one"):
            with self.subTest(case=stem):
                raw = analyzer.analyze_case(analyzer.BASE / stem)
                self.assertEqual(cases[stem]["input_sha256"], raw["input_sha256"])
                self.assertEqual(cases[stem]["enlog_sha256"], raw["enlog_sha256"])
                self.assertEqual(cases[stem]["sxo_sha256"], raw["sxo_sha256"])
                self.assertEqual(
                    [(event["kind"], event["line"], event["time_hours_printed"]) for event in cases[stem]["outcomes"]],
                    [(event["kind"], event["line"], event["time_hours_printed"]) for event in raw["outcomes"]],
                )

    def test_stock_probe_inputs_keep_one_shared_spare_and_repeat_identity(self):
        maker = load_script("make_j35_stock_repair_probes.py")
        directory = maker.OUT
        if not (directory / "p2c-two-repair" / "provenance.json").exists():
            self.skipTest("4700-3 native mechanism inputs are intentionally outside Git")
        hashes = {}
        for stem in ("p2c-one-no-repair", "p2c-one-repair", "p2c-one-repair-repeat", "p2c-two-no-repair", "p2c-two-repair", "p2c-two-repair-repeat"):
            with self.subTest(case=stem):
                path = directory / stem / f"{stem}.json"
                model = json.loads(path.read_text(encoding="utf-8"))
                provenance = json.loads((path.parent / "provenance.json").read_text(encoding="utf-8"))
                self.assertEqual(maker.sha256(path), provenance["input_sha256"])
                stock = maker.rows(maker.table(model, "StockAllocation"))
                self.assertEqual(sum(row["STSIZ"] for row in stock), 1)
                self.assertEqual([(row["IID"], row["STID"]) for row in stock if row["STSIZ"]], [("B-TOP-PRU", "BASE")])
                self.assertEqual(maker.rows(maker.table(model, "SystemDeployment"))[0]["QTYPS"], provenance["system_count"])
                self.assertEqual(maker.rows(maker.table(model, "MissionType"))[0]["NOS"], provenance["system_count"])
                self.assertEqual(maker.rows(maker.table(model, "Control"))[0]["RSEED"], "1")
                self.assertEqual(maker.rows(maker.table(model, "System"))[0]["FRT"], 4000000)
                self.assertEqual({row["FRT"] for row in maker.rows(maker.table(model, "Item"))}, {4000000})
                hashes[stem] = provenance["input_sha256"]
        self.assertEqual(hashes["p2c-one-repair"], hashes["p2c-one-repair-repeat"])
        self.assertEqual(hashes["p2c-two-repair"], hashes["p2c-two-repair-repeat"])

    def test_stock_parser_preserves_historical_fault_and_return_timeline(self):
        parser = load_script("analyze_j35_stock_repair.py")
        log = Path("C:/Users/user/Documents/Codex/2026-09-26/simlox-j35-event-parity/workspace/evidence/phase6/b-zero-stock-repair/b-zero-stock-repair.log")
        if not log.exists():
            self.skipTest("4700-3 historical native ENLOG is intentionally outside Git")
        events = parser.parse_log(log)
        fault = next(e for e in events if e["kind"] == "fault")
        repair = next(e for e in events if e["kind"] == "direct_repair_duration")
        returned = next(e for e in events if e["kind"] == "replacement_arrived" and "B-TOP-PRU" in e["text"])
        ready = next(e for e in events if e["kind"] == "system_ready" and float(e["time_hours_printed"]) > 8)
        self.assertEqual((fault["time_hours_printed"], fault["line"]), ("8.14122", 573))
        self.assertIn("planned to last for 2 hours", repair["text"])
        self.assertEqual((returned["time_hours_printed"], returned["line"]), ("14.7824", 698))
        self.assertEqual(ready["time_hours_printed"], "16.2824")

    def test_rejected_stock_probes_are_not_treated_as_native_event_evidence(self):
        base = ROOT / "data/local/j35-contract-probes"
        first = base / "p2-one-repair" / "roundtrip-check.json"
        second = base / "p2b-one-repair" / "validity.json"
        if not first.exists() or not second.exists():
            self.skipTest("4700-3 rejected native probes are retained only locally")
        mismatch = json.loads(first.read_text(encoding="utf-8-sig"))
        self.assertFalse(mismatch["all_equal"])
        control = next(row for row in mismatch["tables"] if row["table"] == "Control")
        self.assertIn('"RSEED": 1', control["input_only"][0])
        self.assertIn('"RSEED": "1"', control["export_only"][0])
        invalid = json.loads(second.read_text(encoding="utf-8-sig"))
        self.assertEqual((invalid["valid"], invalid["conversion_errors"], invalid["sxo_bytes"]), (False, 2, 4))
        run_log = (base / "p2b-one-repair" / "run.log").read_text(encoding="utf-8-sig")
        self.assertIn("error #2050", run_log)

    def test_native_shared_spare_backorder_and_repair_return(self):
        parser = load_script("analyze_j35_stock_repair.py")
        index = json.loads((ROOT / "docs/simlox/j35-stock-repair-evidence.json").read_text(encoding="utf-8"))
        cases = {case["case"]: case for case in index["cases"]}
        self.assertEqual(len(cases), 6)
        if not (parser.BASE / "p2c-two-repair" / "validity.json").exists():
            self.skipTest("The native logs are retained only on 4700-3")
        for stem in cases:
            with self.subTest(case=stem):
                raw = parser.analyze_case(parser.BASE / stem)
                self.assertEqual((cases[stem]["input_sha256"], cases[stem]["enlog_sha256"]), (raw["input_sha256"], raw["enlog_sha256"]))
                self.assertTrue(cases[stem]["validation"]["roundtrip_all_equal"])
                self.assertEqual(cases[stem]["validation"]["conversion_errors"], 0)
        self.assertTrue(all(check["input_sha256_equal"] and check["selected_events_equal"] for check in index["repeat_checks"]))
        repaired = cases["p2c-two-repair"]["events"]
        stranded = cases["p2c-two-no-repair"]["events"]
        def matching(events, kind, item):
            return [event for event in events if event["kind"] == kind and item in event["text"]]
        self.assertEqual([e["time_hours_printed"] for e in matching(repaired, "fault", "critical random failure")][:2], ["8.14122", "8.23494"])
        self.assertEqual([(e["time_hours_printed"], e["line"]) for e in matching(repaired, "stock_taken", "B-TOP-PRU")][:1], [("8.28243", 1012)])
        self.assertEqual([(e["time_hours_printed"], e["line"]) for e in matching(repaired, "backorder_added", "B-TOP-PRU")][:1], [("8.28243", 1033)])
        self.assertEqual([(e["time_hours_printed"], e["line"]) for e in matching(repaired, "backorder_removed", "B-TOP-PRU")][:1], [("14.7824", 1246)])
        self.assertTrue(any("<J35,1>" in e["text"] and e["time_hours_printed"] == "14.7824" for e in matching(repaired, "replacement_received", "B-TOP-PRU")))
        self.assertTrue(any("<B-TOP-PRU,0,3>" in e["text"] for e in matching(repaired, "stock_returned", "B-TOP-PRU")))
        self.assertEqual(matching(stranded, "backorder_removed", "B-TOP-PRU"), [])
        self.assertEqual(matching(stranded, "repair_finished", "B-TOP-PRU"), [])
        self.assertEqual(len([e for e in stranded if e["kind"] == "mission_cancelled"]), 2)

    def test_reference_transport_consumes_one_unit_without_creating_stock(self):
        source = json.loads((ROOT / "tests/fixtures/synthetic/b3-upstream-transport.json").read_text(encoding="utf-8"))
        result = SimpyReferenceRuntime(compile_aircraft_support(source), seed=0).run()
        trace = result["trace"]
        requested = sum(event["details"]["demand_quantity"] for event in trace if event["kind"] == "spare_request")
        consumed = sum(event["details"]["quantity"] for event in trace if event["kind"] == "spare_consumed")
        arrivals = [event for event in trace if event["kind"] == "transport_arrived"]
        stock = sum(sum(node["inventory"].values()) for node in result["terminal_state"]["resources"])
        initial_stock = sum(sum(node["inventory"].values()) for node in source["support_network"]["nodes"])
        self.assertEqual((requested, consumed, len(arrivals)), (1, 1, 1))
        self.assertEqual(initial_stock, stock + consumed)
        self.assertEqual(result["metrics"]["spare_demand_total"], requested)
        self.assertEqual(result["metrics"]["spare_consumed_total"], consumed)
        self.assertEqual(result["metrics"]["transport_in_transit_count"], 0)


if __name__ == "__main__":
    unittest.main()
