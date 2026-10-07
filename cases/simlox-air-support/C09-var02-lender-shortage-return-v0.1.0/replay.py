"""Read-only author replay of one sealed C09.var02 control/failed-child pair.

The original native log is parsed directly. Its printed return annotation is
retained even when the measured departure-to-arrival interval differs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

from native_json import parse, table_map
from numeric_bounds import compare
from physical_ledger import physical
from report_oracle import (RESOURCE_FIELDS, RESOURCE_TOTAL_FIELDS, STOCK_FIELDS,
                           SUMMARY_FIELDS, SYSTEM_FIELDS, derive, events)

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
REPO = HERE.parents[2]
OLD = BASE / "C09-var02-lender-shortage-v1.0.7"
RUN = OLD / "runs/c09-var02-v107-shortage-ssh-20261007-01"
CONTROL = BASE / "C09-var02-lender-shortage-v1.0.2/runs/c09-var02-v102-ordinary-ssh-20261007-01"
CONTRACT = HERE / "contract.json"
TABLE_COLUMNS = {"ProblemDescription": ["PDESC"], "ResultSummary": SUMMARY_FIELDS,
                 "SystemResults": SYSTEM_FIELDS, "StockTotalResults": STOCK_FIELDS,
                 "ResourceResults": RESOURCE_FIELDS, "ResourceResultsTotal": RESOURCE_TOTAL_FIELDS}


def identity(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def assert_pin(path: Path, pin: dict) -> None:
    assert identity(path) == {"bytes": pin["bytes"], "sha256": pin["sha256"]}, str(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def literal_pins(contract: dict) -> int:
    """Check direct contract pins, with only declared root snapshot custody."""
    count = 0

    def visit(node: object) -> None:
        nonlocal count
        if isinstance(node, dict):
            if {"bytes", "sha256"} <= node.keys() and ("path" in node or "repo_relative" in node):
                text = node.get("path", node.get("repo_relative"))
                path = Path(text)
                if "repo_relative" in node:
                    path = REPO / path
                elif not path.is_absolute():
                    path = (HERE / path).resolve()
                # The root catalog is appendable. Its exact base bytes are
                # preserved under the old package; the original path, if it
                # still exists, must either match or be a valid later append.
                if text == "../publication-index-v1.json":
                    archive = OLD / "preserved-root-context/publication-index-at-base.json"
                    assert_pin(archive, node)
                    live = BASE / "publication-index-v1.json"
                    if live.exists() and identity(live) != {"bytes": node["bytes"], "sha256": node["sha256"]}:
                        before = read_json(archive)
                        after = read_json(live)
                        assert after.get("entries", [])[:len(before.get("entries", []))] == before.get("entries", [])
                elif path.parent == REPO / "tmp":
                    # Every fallback name is present as a literal pin in this
                    # contract and copied byte-for-byte into owned custody.
                    archived = HERE / "preserved-root-context" / path.name
                    assert_pin(archived, node)
                    if path.exists():
                        assert_pin(path, node)
                else:
                    assert_pin(path, node)
                count += 1
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(contract)
    return count


def inherited_source_gate() -> dict:
    """Run the pinned frozen source verifier in sealed mode, unchanged."""
    path = OLD / "verify_sources.py"
    spec = importlib.util.spec_from_file_location("v107_source_verifier", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.verify(mode="sealed_replay")
    assert result["passed"] is True
    return result["counts"]


def source_delta_docs(parent: dict, child: dict, contract: dict) -> dict:
    """Check complete object equality after only the two declared edits."""
    assert len(parent["model"]["tables"]) == len(child["model"]["tables"]) == 32
    assert sum(bool(rows) for _, instances in table_map(parent).values()
               for _, rows in instances) == 25
    expected = copy.deepcopy(parent)
    rrs = next(t for t in expected["model"]["tables"] if t["name"] == "ResourceRemoteSupport")
    assert len(rrs["instances"]) == 1
    col = [x["name"] for x in rrs["columns"]]
    hits = [r for r in rrs["instances"][0]["rows"] if
            dict(zip(col, r)).get("RID") == "P-MECH" and
            dict(zip(col, r)).get("STID") == "BASE-01" and
            dict(zip(col, r)).get("RSTID") == "BASE-02"]
    assert len(hits) == 1 and hits[0][col.index("TTRSS")] == 0.5
    hits[0][col.index("TTRSS")] = 0.125
    description = next(t for t in expected["model"]["tables"] if t["name"] == "ProblemDescription")
    assert len(description["instances"]) == 1
    assert len(description["instances"][0]["rows"]) == 1
    desc_col = [x["name"] for x in description["columns"]]
    assert desc_col == ["PDESC"]
    old_desc = description["instances"][0]["rows"][0][0]
    assert old_desc == contract["source_and_native_binding"]["exact_delta"][1]["from"]
    description["instances"][0]["rows"][0][0] = contract["source_and_native_binding"]["exact_delta"][1]["to"]
    assert expected == child, "any extra source or metadata change"
    return {"changed_cells": 2, "authored_tables": 32, "row_containing_tables": 25,
            "control_description": old_desc,
            "child_description": description["instances"][0]["rows"][0][0]}


def source_pair(contract: dict) -> dict:
    parent_path = (HERE / contract["source_and_native_binding"]["accepted_ordinary_input"]["path"]).resolve()
    child_path = (HERE / contract["source_and_native_binding"]["unchanged_child_input"]["path"]).resolve()
    assert_pin(parent_path, contract["source_and_native_binding"]["accepted_ordinary_input"])
    assert_pin(child_path, contract["source_and_native_binding"]["unchanged_child_input"])
    assert identity(RUN / "input.json") == identity(child_path)
    result = source_delta_docs(parse(parent_path), parse(child_path), contract)
    return {"control_input_sha256": identity(parent_path)["sha256"],
            "child_input_sha256": identity(child_path)["sha256"], **result}


def roundtrip(run: Path, source: Path) -> dict:
    original = parse(source)
    exported = parse(run / "roundtrip-raw.json")
    before, after = table_map(original), table_map(exported)
    assert original["model"]["database_version"] == exported["model"]["database_version"]
    assert list(before) == list(after) and len(before) == 32
    populated = 0
    placeholders = 0
    for name, (columns, instances) in before.items():
        native_columns, native_instances = after[name]
        assert columns == native_columns
        assert sorted(n for n, _ in native_instances) == sorted(n for n, _ in instances)
        if any(rows for _, rows in instances):
            populated += 1
            for instance_name, rows in instances:
                matches = [r for n, r in native_instances if n == instance_name]
                assert len(matches) == 1 and matches[0] == rows, name
        else:
            placeholders += 1
            assert all(all(value is None for value in row)
                       for _, rows in native_instances for row in rows), name
    assert populated == 25 and placeholders == 7
    for name, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!")):
        assert marker in (run / name).read_text(encoding="utf-8-sig", errors="replace")
    return {"populated_authored_tables": populated, "empty_authored_tables": placeholders,
            "export_sha256": identity(run / "roundtrip-raw.json")["sha256"]}


def output_tables_doc(doc: dict, horizon: int = 12) -> dict:
    assert set(doc) == {"report"}
    tables = doc["report"]["tables"]
    assert [table["name"] for table in tables] == list(TABLE_COLUMNS)
    out = {}
    for table in tables:
        name = table["name"]
        fields = [column["name"] for column in table["columns"]]
        assert fields == TABLE_COLUMNS[name], name
        instance = {"ProblemDescription": "", "ResultSummary": "",
                    "SystemResults": f"Total over all Units;Total over all Systems;0.00;{horizon:.2f}",
                    "StockTotalResults": f"0.00;{horizon:.2f};",
                    "ResourceResults": f"Total over all Resources;Total over all Stations;0.00;{horizon:.2f}",
                    "ResourceResultsTotal": f"Total over all Resources;Total over all Stations;0.00;{horizon:.2f}"}[name]
        assert len(table["instances"]) == 1 and table["instances"][0]["instance_name"] == instance
        rows = table["instances"][0]["rows"]
        assert len(rows) == (horizon * 2 if name in {"SystemResults", "StockTotalResults", "ResourceResults"} else 1)
        assert all(len(row) == len(fields) for row in rows)
        out[name] = [dict(zip(fields, row)) for row in rows]
    assert sum(len(row) for rows in out.values() for row in rows) == 1754
    return out


def diagnostics(text: str) -> None:
    assert "Input conversion completed. Errors: 0, Warnings: 3, Notes: 1" in text
    form, found = "", []
    for line in text.splitlines():
        if line.startswith("Form: "):
            form = line.removeprefix("Form: ").strip()
        match = re.match(r"rec (\d+): \((warning|notice) #(\d+)\)", line)
        if match:
            found.append((form, int(match.group(1)), match.group(2), int(match.group(3))))
    assert found == [("Control", 1, "warning", 108),
                     ("ResourceRemoteSupport", 1, "notice", 292),
                     ("System", 1, "warning", 126), ("System", 2, "warning", 126)], found
    assert not re.search(r"\(error #\d+\)", text, re.I)


def run_custody(contract: dict) -> dict:
    old = contract["v107_frozen_failure"]
    assert len(old["run_files"]) == 26
    for name, pin in old["run_files"].items():
        assert_pin(RUN / name, pin)
    closure = read_json(RUN / "closure.json")
    failure = read_json(RUN / "failure-seal.json")
    invocation = read_json(RUN / "invocation.json")
    steps = read_json(RUN / "steps.json")
    assert closure["run_id"] == failure["run_id"] == invocation["run_id"] == old["run_id"]
    assert closure["error"] == failure["error"] == "child OS exit=1"
    assert closure["publication_state"] != "reusable_published"
    assert len(closure["raw"]) == 23 and len(failure["files"]) == 25
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["source_hashes_before"]) == 1726
    assert closure["manifest_sha256"] == old["manifest"]["sha256"]
    assert closure["invocation_sha256"] == identity(RUN / "invocation.json")["sha256"]
    for name, record in closure["raw"].items():
        assert_pin(RUN / name, record)
    for name, record in failure["files"].items():
        assert_pin(RUN / name, record)
    assert invocation["session_id"] == 0
    assert invocation["input_sha256"] == old["input"]["sha256"]
    assert invocation["contract_sha256"] == old["contract"]["sha256"]
    assert invocation["manifest_sha256"] == old["manifest"]["sha256"]
    assert invocation["gui"] == {"pid": 13340, "session_id": 1,
                                 "start_unix_ms": 1790590196826, "responding": True}
    assert [s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert [s["exit_code"] for s in steps] == [0, 0, 0, 0, 0, 1]
    assert [s["status"] for s in steps] == ["completed"] * 5 + ["failed"]
    assert all(s["child_session_id"] == 0 and s["gui_preserved"] is True for s in steps)
    assert read_json(RUN / "author-validation.json")["passed"] is False
    raw_roundtrip = read_json(RUN / "roundtrip-validation.json")
    assert raw_roundtrip["passed"] is True and raw_roundtrip["authored_row_tables"] == 25
    assert raw_roundtrip["export_sha256"] == identity(RUN / "roundtrip-raw.json")["sha256"]
    diagnostics((RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
    return {"run_id": old["run_id"], "original_decision": "NO_GO_RUN",
            "original_checker_os_exit": 1, "captured_process_exits": [s["exit_code"] for s in steps],
            "raw_files": len(closure["raw"]), "failure_file_seals": len(failure["files"]),
            "source_before_after": len(closure["source_hashes_before"])}


def prefix(log: str, ledger: dict) -> list[tuple[float, str]]:
    stream = events(log)
    starts = [event for event in stream
              if event.time == ledger["return_start"] and event.line == ledger["return_start_line"] and
              re.search(rf"return resource transport task {ledger['return_task_id']} starts with 1 resources", event.text)]
    assert len(starts) == 1
    boundary = starts[0]
    selected = []
    for event in stream:
        if (event.time, event.line) >= (boundary.time, boundary.line):
            break
        if re.search(r"(system DIRP task|direct repair subtask|remote resource transport task|return resource transport task|"
                     r"P-MECH at|HOME-AIR|system PM task|nbr resourcewait)", event.text):
            selected.append((event.time, re.sub(r"\s+", " ", event.text).strip()))
    assert selected and any("request for:" in text and "failed" in text for _, text in selected)
    return selected


def description(source: Path) -> str:
    table = next(table for table in parse(source)["model"]["tables"] if table["name"] == "ProblemDescription")
    assert len(table["instances"]) == 1 and len(table["instances"][0]["rows"]) == 1
    return table["instances"][0]["rows"][0][0]


def arm(run: Path, source: Path, name: str) -> dict:
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ledger = physical(log, name)
    observed = output_tables_doc(parse(run / "report-raw.json"))
    expected, edges = derive(log, horizon=12, fleet=3, description=description(source), with_edges=True)
    edges["special_home_boundary_valid"] = ledger["special_home_boundary_valid"]
    errors, cells = compare(expected, observed, edges=edges, log=log)
    assert cells == 1754 and not errors, errors[:12]
    assert edges["terminal_closed"] is True
    return {"log": log, "ledger": ledger, "observed": observed,
            "expected": expected, "edges": edges, "report_cells": cells}


def difference_counts(a: dict, b: dict) -> dict:
    names = list(TABLE_COLUMNS)
    counts = {}
    for name in names:
        aa, bb = a[name], b[name]
        assert len(aa) == len(bb)
        count = 0
        for left, right in zip(aa, bb):
            assert list(left) == list(right)
            for key in left:
                if left[key] != right[key]:
                    count += 1
        counts[name] = count
    return counts


def replay() -> dict:
    contract = read_json(CONTRACT)
    assert contract["schema"] == "simlox-c09-var02-lender-shortage-return-retrospective-v010-contract/v1"
    assert contract["scope"]["new_native_runs"] == 0
    assert contract["v107_frozen_failure"]["status"].startswith("NO_GO_RUN")
    literal = literal_pins(contract)
    assert literal >= 174
    inherited = inherited_source_gate()
    source = source_pair(contract)
    custody = run_custody(contract)
    control_source = (HERE / contract["source_and_native_binding"]["accepted_ordinary_input"]["path"]).resolve()
    child_source = (HERE / contract["source_and_native_binding"]["unchanged_child_input"]["path"]).resolve()
    control_rt = roundtrip(CONTROL, control_source)
    child_rt = roundtrip(RUN, child_source)
    control = arm(CONTROL, control_source, "ordinary")
    child = arm(RUN, child_source, "shortage")
    left, right = control["ledger"], child["ledger"]
    assert prefix(control["log"], left) == prefix(child["log"], right)
    assert (left["outward_task_id"], left["return_task_id"]) == (
        right["outward_task_id"], right["return_task_id"]) == (3, 0)
    assert left["return_start"] == right["return_start"] == 9.46988
    assert left["return_arrival"] == 9.96988 and right["return_arrival"] == 9.59488
    assert left["return_printed_duration"] == right["return_printed_duration"] == 0.5
    assert left["qualifying_return_hours"] == [0.5] and right["qualifying_return_hours"] == [0.125]
    assert left["pm_completed"] == 10.2199 and right["pm_work_started"] == 9.59488
    assert right["pm_completed"] == 9.84488
    actual_diff = difference_counts(control["observed"], child["observed"])
    expected_diff = difference_counts(control["expected"], child["expected"])
    declared = contract["report_reconstruction"]["diagnostic_observed_diff_counts"]
    assert actual_diff == declared, (actual_diff, declared)
    # The source/event oracle uses printed event times. One ResourceTotal
    # NRUM difference is below report serialization precision, so the native
    # values are equal even though the two derived floating values differ.
    # Both arms already passed every cell's predeclared numeric comparator.
    assert all(expected_diff[name] >= actual_diff[name] for name in declared), expected_diff
    return {"schema": "c09-var02-return-v010-author-replay/v1", "passed": True,
            "decision": "GO_AUTHOR_REPLAY_ONLY", "classification": contract["classification_id"],
            "original_run_decision": "NO_GO_RUN", "new_native_runs": 0,
            "control_run_id": CONTROL.name, "child_run_id": RUN.name,
            "literal_pins": literal, "inherited_source_counts": inherited,
            "source": source, "run_custody": custody,
            "control_roundtrip": control_rt, "child_roundtrip": child_rt,
            "control_ledger": left, "child_ledger": right,
            "control_report_cells": control["report_cells"], "child_report_cells": child["report_cells"],
            "report_diff_cells_by_table": actual_diff,
            "oracle_raw_float_diff_cells_by_table": expected_diff,
            "control_terminal_closed": control["edges"]["terminal_closed"],
            "child_terminal_closed": child["edges"]["terminal_closed"],
            "limits": "Fixed sealed pair only; original v107 prospective gate remains failed. Independent replay and publication reviews are separate."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="write a NEW JSON file in this package")
    args = parser.parse_args()
    result = replay()
    payload = json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        target = args.output.resolve()
        assert target.parent == HERE and not target.exists()
        target.write_bytes(payload.encode("utf-8"))
    else:
        print(payload, end="")
