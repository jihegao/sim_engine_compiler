"""Read-only independent contract pin and feasibility check for B03.var01 v0.1.1."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = next(p for p in HERE.parents if (p / ".git").exists())
CASES = REPO / "cases" / "simlox-air-support"
EXPECTED = "3c487385f4a160b7994b9533deaacba8c4a91de6cdf032812316bb6a2ca287c8"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def check(path, pin):
    data = path.read_bytes()
    assert len(data) == pin["bytes"] and digest(data) == pin["sha256"], str(path)


def native_json(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def main():
    path = HERE / "contract.json"
    assert digest(path.read_bytes()) == EXPECTED
    c = json.loads(path.read_bytes())
    old = json.loads((CASES / "B03-var01-cold-first-full-report-v0.1.0" / "contract.json").read_bytes())
    assert c["accepted_source_files"] == old["accepted_source_files"]
    assert c["parent_runs"] == old["parent_runs"]
    assert c["prerequisites"] == old["prerequisites"]
    assert c["typed_event_gate"] == old["typed_event_gate"]
    assert c["source_and_roundtrip_gates"] == old["source_and_roundtrip_gates"]
    assert c["full_report_gate"]["numeric_rule"] == old["full_report_gate"]["numeric_rule"]
    assert c["full_report_gate"]["total_cells"] == 4044
    for pin in c["excluded_v010"]["files"]:
        original = REPO / pin["original_path"]
        copy = HERE / pin["inert_copy_path"]
        check(original, pin)
        check(copy, pin)
    assert len(c["excluded_v010"]["files"]) == 6
    for pin in c["accepted_source_files"]:
        check(REPO / pin["path"], pin["local_disk"])
        blob = subprocess.run(["git", "show", c["base_commit"] + ":" + pin["path"]],
                              cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True).stdout
        assert len(blob) == pin["published_git_at_base"]["bytes"]
        assert digest(blob) == pin["published_git_at_base"]["sha256"]
    for pin in c["installed"].values():
        check(Path(pin["path"]), pin)
    for run in c["parent_runs"]:
        root = Path(run["original_directory"])
        check(root / "closure.json", run["closure"])
        check(root / "invocation.json", run["invocation"])
        closure = json.loads((root / "closure.json").read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run["run_id"] and closure["raw"] == run["raw"]
        for name, pin in run["raw"].items():
            check(root / name, pin)
        for name, pin in run["other_local_files"].items():
            check(root / name, pin)
    accepted = Path(c["parent_runs"][1]["original_directory"])
    tables = native_json(accepted / "report-raw.json")["report"]["tables"]
    gate = c["full_report_gate"]
    assert [t["name"] for t in tables] == [t["name"] for t in gate["native_tables_in_order"]]
    assert sum(len(t["columns"]) * sum(len(i["rows"]) for i in t["instances"]) for t in tables) == 4044
    for t in tables:
        assert len(t["instances"]) == 1
        assert t["instances"][0]["instance_name"] == gate["instance_names_exact"][t["name"]]
        assert [x["name"] for x in t["columns"]] == gate["column_order_exact"][t["name"]]
    sys = next(t for t in tables if t["name"] == "SystemResults")
    cols = [x["name"] for x in sys["columns"]]
    rows = sys["instances"][0]["rows"]
    expected = gate["system_integrals_h"]
    for field, name in (("NSYRY", "NSYRY_unassigned_ready"),
                        ("NSYMR", "NSYMR_assigned_prepared_waiting"),
                        ("NSYMP", "NSYMP_active_preparation"),
                        ("NSYMO", "NSYMO_operation"),
                        ("NSYMA", "NSYMA_total_assigned"),
                        ("NSYA", "NSYA_total_aircraft"),
                        ("FTMO", "FTMO_operation_for_one_aircraft")):
        actual = sum(r[cols.index(field)] * 0.5 for r in rows)
        assert abs(actual - expected[name]) < 5e-8, (field, actual, expected[name])
    stock = next(t for t in tables if t["name"] == "StockTotalResults")
    stock_cols = [x["name"] for x in stock["columns"]]
    zero = {"NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"}
    nullable = {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS"}
    for row in stock["instances"][0]["rows"]:
        assert all(row[stock_cols.index(k)] == 0 for k in zero)
        assert all(row[stock_cols.index(k)] is None for k in nullable)
        assert row[stock_cols.index("PNB")] == 1
    print(json.dumps({"decision": "PASS_CONTRACT_ONLY_PINS_AND_GATE_FEASIBILITY",
                      "dual_source": len(c["accepted_source_files"]), "raw": 22,
                      "old_excluded_triplets": 6, "report_cells": 4044,
                      "state_integrals": expected}, sort_keys=True))


if __name__ == "__main__":
    main()
