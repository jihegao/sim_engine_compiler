"""Audit every J35 LRU across canonical source, Plan, aircraft, and shared stock."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/spare_mvp/j35-amd128-0e709bd"
EXPECTED = {
    "execution-plan.json": "44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb",
    "simulation-inputs.json": "30c20086cbf400dd35e132f71498c1d05c256d74a1384355b703ccc713601559",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> tuple[list[dict], dict]:
    for name, expected in EXPECTED.items():
        actual = sha256(FIXTURE / name)
        if actual != expected:
            raise ValueError(f"{name} SHA-256 {actual}, expected {expected}; check Windows checkout line endings")
    plan = json.loads((FIXTURE / "execution-plan.json").read_text(encoding="utf-8"))
    canonical = json.loads((FIXTURE / "simulation-inputs.json").read_text(encoding="utf-8"))
    components = plan["components"]
    by_index = {c["index"]: c for c in components}
    by_canonical_id = {c["id"]: c for c in canonical["equipment_tree"]["components"]}
    tails = [a["tail_number"] for a in plan["aircraft"]]
    assert tails == [f"J35-{i:02}" for i in range(1, 9)]
    inventory = [dict(node["inventory"]) for node in plan["resource_nodes"]]
    assert len(inventory) == 2
    assert len(plan["supply_routes"]) == 1
    route = plan["supply_routes"][0]
    assert (route["source_node_index"], route["destination_node_index"], route["capacity"], route["transport_minutes"]) == (0, 1, 1, 120)
    repair_activities = {a["index"]: a for a in plan["activities"] if a["kind"] == "repair"}
    out = []
    for c in components:
        if c["product_type"] != "LRU":
            continue
        source = by_canonical_id[c["component_id"]]
        assert source["product_type"] == "LRU" and source["product_id"] == c["product_id"]
        assert c["aircraft_indexes"] == list(range(8)) and c["quantity"] == 1 and c["failure_threshold"] == 1
        chain = []
        parent = c
        while parent["parent_index"] != -1:
            parent = by_index[parent["parent_index"]]
            chain.append(parent["component_id"])
            assert parent["failure_threshold"] == 1
        assert parent["product_type"] == "whole"
        activity = repair_activities[c["repair_activity_index"]]
        assert activity["maintenance_methods"] == ["replacement"] and activity["replacement_ratio"] == 1
        assert len(activity["steps"]) == 1 and not activity["steps"][0]["spares"]
        step = activity["steps"][0]
        assert c["product_id"] in inventory[0] and c["product_id"] in inventory[1]
        assert inventory[0][c["product_id"]] == 0
        out.append({
            "source_path": c["source_path"],
            "canonical_component_id": c["component_id"],
            "product_id": c["product_id"],
            "product_type": c["product_type"],
            "component_parent_id": by_index[c["parent_index"]]["component_id"],
            "parent_chain_to_aircraft": "|".join(chain),
            "depth_from_aircraft": len(chain),
            "installed_tail_numbers": "|".join(tails),
            "per_tail_slot_quantity": c["quantity"],
            "failure_rate_per_flight_hour": c["failure_rate_per_hour"],
            "failure_threshold": c["failure_threshold"],
            "failure_impact": "propagates through OR-like threshold-1 parents to aircraft root",
            "replacement_boundary_in_current_plan": "failed LRU component; one product unit injected into its repair step",
            "repair_activity_id": activity["activity_id"],
            "repair_minutes": step["duration_minutes"],
            "repair_personnel": step["personnel"],
            "repair_equipment": step["equipment"],
            "repair_node_id": plan["resource_nodes"][activity["resource_node_index"]]["node_id"],
            "depot_node_id": plan["resource_nodes"][0]["node_id"],
            "depot_initial_stock": inventory[0][c["product_id"]],
            "base_node_id": plan["resource_nodes"][1]["node_id"],
            "base_initial_stock": inventory[1][c["product_id"]],
            "transport_capacity": route["capacity"],
            "transport_minutes": route["transport_minutes"],
            "age_counter": "per-tail/per-component flight-exposure failure_remaining; resample on repair completion",
            "native_secondary_reclassification": "unverified; changes SIMLOX replacement/workshop transaction",
        })
    assert len(out) == 403 and len({r["product_id"] for r in out}) == 403
    assert len({r["canonical_component_id"] for r in out}) == 403
    assert len({r["source_path"] for r in out}) == 403
    non_lru = [c for c in components if c["product_type"] == ""]
    assert len(non_lru) == 20
    summary = {
        "sources_sha256": EXPECTED,
        "upstream_revision": "0e709bdcc2d692d9cfed49b9037c76ef71aefe33",
        "lru_count": len(out),
        "lru_depths": dict(Counter(r["depth_from_aircraft"] for r in out)),
        "lru_direct_system_children": sum(r["depth_from_aircraft"] == 1 for r in out),
        "lru_distinct_product_ids": len({r["product_id"] for r in out}),
        "lru_per_tail_component_slots": len(out),
        "lru_eight_tail_component_instances_inferred": len(out) * len(tails),
        "intermediate_untyped_count": len(non_lru),
        "intermediate_positive_failure_rate": sum(c["failure_rate_per_hour"] > 0 for c in non_lru),
        "initial_depot_stock": sum(inventory[0].values()),
        "initial_base_stock": sum(inventory[1].values()),
        "positive_base_product_count": sum(v > 0 for v in inventory[1].values()),
        "shared_stock_pool_count": len(inventory),
        "shared_resource_nodes": [{"node_id": n["node_id"], "personnel_capacity": n["personnel_capacity"], "equipment_capacity": n["equipment_capacity"]} for n in plan["resource_nodes"]],
        "supply_route": {"source_node_id": plan["resource_nodes"][route["source_node_index"]]["node_id"], "destination_node_id": plan["resource_nodes"][route["destination_node_index"]]["node_id"], "capacity": route["capacity"], "transport_minutes": route["transport_minutes"]},
        "runtime_observable_conservation": "initial inventory + recorded external arrivals - spare_consumed = end inventory + reservations + transit, subject to explicit ledger definitions; installed good/bad units and repair returns are not exposed as physical stock states",
        "source_physical_replacement_boundary": "not explicit in canonical component parent relation; needs upstream business decision",
    }
    return out, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/simlox")
    args = parser.parse_args()
    rows, summary = audit()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "j35-lru-static-mapping.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output_dir / "j35-lru-static-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "runtime_observable_conservation"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
