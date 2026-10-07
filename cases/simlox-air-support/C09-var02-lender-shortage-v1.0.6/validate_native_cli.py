"""Strict read-only live/sealed child replay against the accepted control."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from build import build, changes
from check_roundtrip import parse
from numeric_bounds import compare
from physical_ledger import physical
from report_oracle import (RESOURCE_FIELDS, RESOURCE_TOTAL_FIELDS, STOCK_FIELDS,
                           SUMMARY_FIELDS, SYSTEM_FIELDS, derive, events)
from verify_sources import verify as verify_sources

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "contract.json"
INPUT_SHA = "a036c16bbdd28b35047ba8a064722c6a1bde21c036435263dd5713dd710767a4"
CONTROL_SHA = "b971efb41492789f32475aae7fa9f37c0e30e9461203b48d37e08e2747e8d2e3"
TABLE_COLUMNS = {"ProblemDescription": ["PDESC"], "ResultSummary": SUMMARY_FIELDS,
                 "SystemResults": SYSTEM_FIELDS, "StockTotalResults": STOCK_FIELDS,
                 "ResourceResults": RESOURCE_FIELDS, "ResourceResultsTotal": RESOURCE_TOTAL_FIELDS}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_tables_doc(doc: dict, horizon: float = 12) -> dict[str, list[dict]]:
    assert set(doc) == {"report"}
    tables = doc["report"]["tables"]
    assert [t["name"] for t in tables] == list(TABLE_COLUMNS), "six-table report order"
    out = {}
    for t in tables:
        name = t["name"]
        fields = [c["name"] for c in t["columns"]]
        assert fields == TABLE_COLUMNS[name], (name, fields)
        instance = {"ProblemDescription": "", "ResultSummary": "",
                    "SystemResults": f"Total over all Units;Total over all Systems;0.00;{horizon:.2f}",
                    "StockTotalResults": f"0.00;{horizon:.2f};",
                    "ResourceResults": f"Total over all Resources;Total over all Stations;0.00;{horizon:.2f}",
                    "ResourceResultsTotal": f"Total over all Resources;Total over all Stations;0.00;{horizon:.2f}"}[name]
        assert len(t["instances"]) == 1 and t["instances"][0]["instance_name"] == instance, name
        rows = t["instances"][0]["rows"]
        assert len(rows) == (int(horizon * 2) if name in {"SystemResults", "StockTotalResults", "ResourceResults"} else 1)
        assert all(len(r) == len(fields) for r in rows)
        out[name] = [dict(zip(fields, r)) for r in rows]
    assert sum(len(r) for rows in out.values() for r in rows) == 1754
    return out


def diagnostics(text: str) -> None:
    assert "Input conversion completed. Errors: 0, Warnings: 3, Notes: 1" in text
    form, seen = "", []
    for line in text.splitlines():
        if line.startswith("Form: "):
            form = line.removeprefix("Form: ").strip()
        m = re.match(r"rec (\d+): \((warning|notice) #(\d+)\)", line)
        if m:
            seen.append((form, int(m.group(1)), m.group(2), int(m.group(3))))
    assert seen == [("Control", 1, "warning", 108),
                    ("ResourceRemoteSupport", 1, "notice", 292),
                    ("System", 1, "warning", 126), ("System", 2, "warning", 126)], seen
    assert not re.search(r"\(error #\d+\)", text, re.I)


def description(source: Path) -> str:
    t = next(t for t in parse(source)["model"]["tables"] if t["name"] == "ProblemDescription")
    assert len(t["instances"]) == len(t["instances"][0]["rows"]) == 1
    return t["instances"][0]["rows"][0][0]


def replay_arm(run: Path, source: Path, arm: str) -> dict:
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ledger = physical(log, arm)
    actual = output_tables_doc(parse(run / "report-raw.json"))
    expected, edges = derive(log, horizon=12, fleet=3, description=description(source), with_edges=True)
    edges["special_home_boundary_valid"] = ledger["special_home_boundary_valid"]
    errors, checked = compare(expected, actual, edges=edges, log=log)
    assert checked == 1754 and not errors, errors[:20]
    # derive() closes every typed state and pool at h12. The final report bin
    # is a time average, so a linked return within [11.5,12) may be fractional.
    assert edges["terminal_closed"] is True
    return {"log": log, "ledger": ledger, "actual": actual, "expected": expected, "edges": edges,
            "report_cells": checked}


def selected_prefix(log: str, ledger: dict) -> list[tuple[float, str]]:
    """Typed physical event tuples, never raw file-byte prefix comparison."""
    ev = events(log)
    task = ledger["return_task_id"]
    starts = [e for e in ev if e.time == ledger["return_start"] and
              e.line == ledger["return_start_line"] and
              re.search(rf"return resource transport task {task} starts with 1 resources", e.text)]
    assert len(starts) == 1
    boundary = starts[0]
    selected = []
    for e in ev:
        if (e.time, e.line) >= (boundary.time, boundary.line):
            break
        if re.search(r"(system DIRP task|direct repair subtask|remote resource transport task|return resource transport task|"
                     r"P-MECH at|HOME-AIR|system PM task|nbr resourcewait)", e.text):
            selected.append((e.time, re.sub(r"\s+", " ", e.text).strip()))
    assert selected and any("request for:" in text and "failed" in text for _, text in selected)
    assert any("return resource transport task" in text and "created" in text for _, text in selected)
    return selected


def source_shape(run: Path, contract: dict) -> None:
    expected_child, expected_diff = build()
    assert (HERE / "shortage-input.json").read_bytes() == expected_child
    assert (HERE / "exact-diff.json").read_bytes() == expected_diff
    assert sha(HERE / "shortage-input.json") == sha(run / "input.json") == INPUT_SHA
    parent = parse((HERE / contract["planned_child"]["input_parent"]["path"]).resolve())
    child = parse(run / "input.json")
    assert changes(parent, child) == json.loads(expected_diff)["changed_cells"]
    assert len(child["model"]["tables"]) == 32
    assert sum(any(i["rows"] for i in t["instances"]) for t in child["model"]["tables"]) == 25


def provenance(run: Path, contract: dict) -> dict:
    assert run.name == contract["planned_child"]["run_id"]
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    assert invocation["run_id"] == run.name and invocation["session_id"] == 0
    assert invocation["input_sha256"] == INPUT_SHA and invocation["contract_sha256"] == sha(CONTRACT)
    assert invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
    assert invocation["gui"] == {"pid": 13340, "session_id": 1, "start_unix_ms": 1790590196826, "responding": True}
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    assert [s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps[:5])
    assert all(s["child_session_id"] == 0 for s in steps[:5] if s["name"] in {"import", "export", "calc", "jsonreport"})
    closure_path = run / "closure.json"
    if closure_path.exists():
        closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run.name and not closure["error"]
        assert steps[5]["status"] == "completed" and steps[5]["exit_code"] == 0
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
        assert closure["invocation_sha256"] == sha(run / "invocation.json")
        assert closure["manifest_sha256"] == invocation["manifest_sha256"]
        for name, record in closure["raw"].items():
            p = run / name
            assert p.stat().st_size == record["bytes"] and sha(p) == record["sha256"], name
        mode = "sealed"
    else:
        assert steps[5]["status"] == "started"
        mode = "live_before_closure"
    return {"mode": mode, "step_count": len(steps), "closure_sha256": sha(closure_path) if closure_path.exists() else None}


def validate(run: Path) -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "simlox-c09-var02-lender-shortage-v106-child-contract/v1"
    source_verification = verify_sources(mode="sealed_replay" if (run / "closure.json").exists() else "live_run")
    source_shape(run, contract)
    prov = provenance(run, contract)
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    assert roundtrip["schema"] == "c09-var02-v106-roundtrip/v1"
    assert roundtrip["passed"] and roundtrip["authored_row_tables"] == 25 and not roundtrip["issues"]
    diagnostics((run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
    control_run = (HERE / contract["old_prospective_history"]["old_ordinary_closure"]["path"]).resolve().parent
    control_source = (HERE / contract["planned_child"]["input_parent"]["path"]).resolve()
    assert sha(control_source) == CONTROL_SHA
    control = replay_arm(control_run, control_source, "ordinary")
    child = replay_arm(run, HERE / "shortage-input.json", "shortage")
    a, b = control["ledger"], child["ledger"]
    assert a["special_home_boundary_valid"] and b["special_home_boundary_valid"]
    assert (a["outward_task_id"], a["return_task_id"]) == (b["outward_task_id"], b["return_task_id"])
    assert (a["outward_start"], a["outward_arrival"], a["return_start"]) == (
        b["outward_start"], b["outward_arrival"], b["return_start"])
    assert selected_prefix(control["log"], a) == selected_prefix(child["log"], b)
    assert a["qualifying_return_hours"] == [0.5] and b["qualifying_return_hours"] == [0.125]
    assert b["return_arrival"] < a["return_arrival"]
    assert b["return_arrival"] <= b["pm_work_started"] < b["pm_completed"] <= 12
    assert b["pm_work_started"] < a["pm_work_started"]
    # Conditional timing follows the matched dispatch and route. Any later
    # linked cycle is assessed by the complete event-derived report ledger.
    if abs(b["return_start"] - 9.46988) < 0.00002:
        assert abs(b["return_arrival"] - 9.59488) < 0.00002
        if b["pm_work_started"] == b["return_arrival"]:
            assert abs(b["pm_completed"] - 9.84488) < 0.00002
    return {"schema": "c09-var02-v106-author-validation/v1", "passed": True,
            "decision": "GO_BOUNDED_PROSPECTIVE_CHILD", "run_id": run.name,
            "control_run_id": control_run.name, "control_report_cells": control["report_cells"],
            "child_report_cells": child["report_cells"], "source_verification": source_verification["counts"],
            "provenance": prov, "control_ledger": a, "child_ledger": b,
            "old_pair_decision": "NO_GO_PROSPECTIVE_PAIR", "new_native_runs": 1}


if __name__ == "__main__":
    try:
        result = validate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": "c09-var02-v106-author-validation/v1", "passed": False,
                  "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    sys.exit(0 if result["passed"] else 1)
