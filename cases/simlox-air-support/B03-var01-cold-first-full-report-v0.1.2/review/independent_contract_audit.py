"""Independent read-only preimplementation audit of B03.var01 v0.1.2."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = next(p for p in HERE.parents if (p / ".git").exists())
CASES = REPO / "cases" / "simlox-air-support"
EXPECTED = "28765ddfeb99c595318d63cc0bd9e6a364bd2122d8a592b2fdd81a4d0a4cea44"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(path, pin):
    raw = path.read_bytes()
    assert len(raw) == pin["bytes"] and sha(raw) == pin["sha256"], str(path)
    return raw


def git_blob(commit, path):
    return subprocess.run(["git", "show", f"{commit}:{path}"], cwd=REPO,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def native_json(raw):
    text = raw.decode("utf-8-sig")
    result = []
    quoted = escaped = False
    for i, char in enumerate(text):
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            result.append(char)
        elif char == ',':
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j == len(text) or text[j] not in "]}":
                result.append(char)
        else:
            result.append(char)
    assert not quoted
    return json.loads("".join(result))


def main():
    contract = json.loads(check(HERE / "contract.json", {"bytes": 61776, "sha256": EXPECTED}))
    old = json.loads((CASES / "B03-var01-cold-first-full-report-v0.1.1" / "contract.json").read_bytes())
    assert contract["case_id"] == "B03" and contract["variant_id"] == "B03.var01"
    assert contract["version"] == "0.1.2" and contract["base_commit"] == old["base_commit"]
    for name in ("accepted_source_files", "parent_runs", "prerequisites", "typed_event_gate",
                 "source_and_roundtrip_gates", "installed"):
        assert contract[name] == old[name], name
    new_gate, old_gate = contract["full_report_gate"], old["full_report_gate"]
    for name in ("native_tables_in_order", "total_cells", "report_interval_h", "collection",
                 "summary_expected", "system_integrals_h", "system_event_counts", "stock",
                 "field_classes", "expected_hot_context", "system_state_partition",
                 "instance_names_exact", "column_order_exact"):
        assert new_gate[name] == old_gate[name], name
    assert new_gate["total_cells"] == 4044
    assert [x["cells"] for x in new_gate["native_tables_in_order"]] == [1, 11, 2880, 1152]
    assert "1.1e-4" in new_gate["numeric_rule"] and "Exact zero, whole-bin" in new_gate["numeric_rule"]
    assert "no candidate numeric cell" in new_gate["metadata_basis"].lower()
    basis = new_gate["system_zero_field_basis"]
    present = basis["bounded_native_presentation_fields"]
    assert present == {"NSYAL": 0, "STREQ": 0, "STF": 0, "STLOW": 0, "SYDTU": 0}
    assert basis["bounded_native_presentation_cells"] == 72 * len(present) == 360
    zeros = set(basis["source_event_zero_fields"])
    assert len(zeros) == 20 and not zeros.intersection(present)
    columns = set(new_gate["column_order_exact"]["SystemResults"])
    derived = {"UNID", "SID", "STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "NSYMP",
               "NSYMR", "NSYA", "FTMO", "STACC", "SYDT", "NPSTA", "NPSUC"}
    assert columns == zeros | set(present) | derived and len(columns) == 40
    assert "Any other unknown" in new_gate["strict"]
    assert contract["preservation_and_limits"]["no_new_native"] is True
    assert len(contract["excluded_v010"]["files"]) == 6
    for pin in contract["excluded_v010"]["files"]:
        check(REPO / pin["original_path"], pin)
        check(HERE / pin["inert_copy_path"], pin)
    archived = contract["excluded_v011"]["files"]
    assert len(archived) == 48
    seal_pin = contract["excluded_v011"]["root_no_go_seal"]
    seal = json.loads(check(REPO / seal_pin["original_path"], seal_pin))
    check(HERE / seal_pin["inert_copy_path"], seal_pin)
    assert seal["decision"] == "NO_GO_FULL_REPORT_FORMULA_SCOPE"
    assert len(seal["files"]) == 48
    assert {(p["original_path"], p["bytes"], p["sha256"]) for p in archived} == {
        (p["path"], p["bytes"], p["sha256"]) for p in seal["files"]}
    for pin in archived:
        check(REPO / pin["original_path"], pin)
        check(HERE / pin["inert_copy_path"], pin)
    assert len(contract["excluded_v011"]["root_probe_context"]) == 5
    for pin in contract["excluded_v011"]["root_probe_context"]:
        check(REPO / pin["original_path"], pin)
        check(HERE / pin["inert_copy_path"], pin)
    for pin in contract["accepted_source_files"]:
        check(REPO / pin["path"], pin["local_disk"])
        blob = git_blob(contract["base_commit"], pin["path"])
        assert len(blob) == pin["published_git_at_base"]["bytes"]
        assert sha(blob) == pin["published_git_at_base"]["sha256"]
    for pin in contract["installed"].values():
        check(Path(pin["path"]), pin)
    for run in contract["parent_runs"]:
        root = Path(run["original_directory"])
        check(root / "closure.json", run["closure"])
        check(root / "invocation.json", run["invocation"])
        closure = json.loads((root / "closure.json").read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run["run_id"] and closure["raw"] == run["raw"]
        for name, pin in run["raw"].items():
            check(root / name, pin)
        for name, pin in run["other_local_files"].items():
            check(root / name, pin)
    control = new_gate["B02_format_corroboration"]
    assert "format context only" in control["role"]
    control_raw = check(Path(control["original_path"]), control["local_disk"])
    context_path = REPO / control["publication_context"]
    assert control["local_disk"]["sha256"] in context_path.read_text(encoding="utf-8")
    assert context_path.read_bytes() == git_blob(contract["base_commit"], control["publication_context"])
    control_table = next(t for t in native_json(control_raw)["report"]["tables"]
                         if t["name"] == "SystemResults")
    control_cols = [x["name"] for x in control_table["columns"]]
    for row in control_table["instances"][0]["rows"]:
        assert all(row[control_cols.index(name)] == 0 for name in present)
    assert any(row[control_cols.index("NSYA")] == 1 and row[control_cols.index("STACC")] == 1
               for row in control_table["instances"][0]["rows"])
    accepted = Path(contract["parent_runs"][1]["original_directory"])
    tables = native_json((accepted / "report-raw.json").read_bytes())["report"]["tables"]
    assert [t["name"] for t in tables] == [t["name"] for t in new_gate["native_tables_in_order"]]
    assert sum(len(t["columns"]) * len(t["instances"][0]["rows"]) for t in tables) == 4044
    for table in tables:
        assert len(table["instances"]) == 1
        assert table["instances"][0]["instance_name"] == new_gate["instance_names_exact"][table["name"]]
        assert [x["name"] for x in table["columns"]] == new_gate["column_order_exact"][table["name"]]
    system = next(t for t in tables if t["name"] == "SystemResults")
    syscols = [x["name"] for x in system["columns"]]
    sysrows = system["instances"][0]["rows"]
    for field, name in (("NSYRY", "NSYRY_unassigned_ready"),
                        ("NSYMR", "NSYMR_assigned_prepared_waiting"),
                        ("NSYMP", "NSYMP_active_preparation"),
                        ("NSYMO", "NSYMO_operation"),
                        ("NSYMA", "NSYMA_total_assigned"),
                        ("NSYA", "NSYA_total_aircraft"),
                        ("FTMO", "FTMO_operation_for_one_aircraft")):
        observed = sum(row[syscols.index(field)] * 0.5 for row in sysrows)
        assert abs(observed - new_gate["system_integrals_h"][name]) < 5e-8
    assert all(all(row[syscols.index(name)] == 0 for name in present) for row in sysrows)
    stock = next(t for t in tables if t["name"] == "StockTotalResults")
    stockcols = [x["name"] for x in stock["columns"]]
    for row in stock["instances"][0]["rows"]:
        assert row[stockcols.index("PNB")] == 1
        assert all(row[stockcols.index(name)] == 0 for name in
                   ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"))
        assert all(row[stockcols.index(name)] is None for name in
                   ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"))
    print(json.dumps({"decision": "PASS_CONTRACT_ONLY", "contract_sha256": EXPECTED,
                      "source_local_git_pairs": 38, "parent_raw": 22, "archived_v011": 48,
                      "root_context": 5, "bounded_system_presentation_cells": 360,
                      "required_report_cells": 4044}, sort_keys=True))


if __name__ == "__main__":
    main()
