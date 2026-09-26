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
