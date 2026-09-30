"""Author replay of two rejected shift overlaps and one warning/clamp run."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
UP = HERE.parent / "C07-repeat-nested-v1.0.0"
PARENTS = {"explicit": (UP / "explicit-input.json", "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"),
           "repeated": (UP / "repeated-input.json", "32f79158605a426edc80052f1188ec0c65f91d468d10a07ab748b7f0839c053e")}
RUNS = {"overlap": "c07-overlap-20260930-01", "repeated-overlap": "c07-repeated-overlap-20260930-01",
        "over-capacity": "c07-over-capacity-20260930-01"}
INPUT_SHA = {"overlap": "b44334b8850d090d1456123f571315864801c25ae9cb25ccfa9677f1e2a1dd10",
             "repeated-overlap": "730d4e30fbb6ce4202d3e53d8d27ed4789bb6f2eca491c790dc6b86fb55f65ac",
             "over-capacity": "4a0a996203e494de5892aa30f7e6cd720b3079ed6433022e9f40f42830c165b3"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in parse_native(path)["model"]["tables"]}


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    item = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in item["columns"]], [r for ins in item["instances"] for r in ins["rows"]]


def check() -> dict:
    issues: list[str] = []
    def demand(condition: bool, label: str) -> None:
        if not condition:
            issues.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    exact = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    for name, (path, fingerprint) in PARENTS.items():
        demand(sha(path) == fingerprint == contract["parent_input_sha256"][name] == exact["parent_sha256"][name], f"{name}: accepted parent")
    observed: dict[str, dict] = {}
    for variant, run_id in RUNS.items():
        run = HERE / "runs" / run_id
        source = HERE / f"{variant}-input.json"
        parent_name = "repeated" if variant == "repeated-overlap" else "explicit"
        parent, parent_sha = PARENTS[parent_name]
        before, child = tables(parent), tables(source)
        changed = sorted(n for n in before if before[n] != child[n])
        expected = ["ProblemDescription", "ShiftResource"] if variant == "over-capacity" else ["ProblemDescription", "ShiftProfile"]
        demand(before.keys() == child.keys() and changed == expected == exact["variants"][variant]["changed_tables"], f"{variant}: exact delta")
        demand(exact["variants"][variant]["parent"] == parent_name, f"{variant}: parent selection")
        demand(sha(source) == sha(run / "input.json") == INPUT_SHA[variant] == contract["input_sha256"][variant] == exact["variants"][variant]["sha256"], f"{variant}: source fingerprint")
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        demand(invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant and invocation["parent_sha256"] == parent_sha, f"{variant}: identity")
        demand(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant}: session-0 SSH")
        demand(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant}: queue and GUI")
        demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], f"{variant}: source seal")
        runner = HERE / ("run_capacity_ssh.ps1" if variant == "over-capacity" else "run_rejection_ssh.ps1")
        for key, path in {"input": source, "parent": parent, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": runner}.items():
            demand(closure["source_hashes_before"][key] == sha(path), f"{variant}: {key} run-time hash")
        demand(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant}: invocation seal")
        names = [s["name"] for s in steps]
        expected_steps = ["import", "export", "calc", "jsonreport", "check_import_export"] if variant == "over-capacity" else ["import", "export", "calc", "check_import_export"]
        demand(names == expected_steps, f"{variant}: planned steps")
        statuses = ["completed"] * len(expected_steps)
        if variant != "over-capacity":
            statuses[2] = "expected_rejection"
        demand([s["status"] for s in steps] == statuses and all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant}: step status and GUI")
        for name, item in closure["raw"].items():
            path = run / name
            demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"{variant}: raw seal {name}")
        demand(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], f"{variant}: roundtrip checker")
        imported = populated(parse_native(run / "input.json"))
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        demand(len(imported) == 24 and all(exported.get(n) == t for n, t in imported.items()), f"{variant}: 24 source business tables")
        calc = (run / "run.log").read_text(encoding="utf-8-sig")
        warnings = set(re.findall(r"warning\s+#(\d+)", calc, re.I))
        errors = re.findall(r"error\s+#(\d+)", calc, re.I)
        if variant == "over-capacity":
            demand(errors == [] and warnings == {"60", "108", "126"} and "Errors: 0, Warnings: 3, Notes: 0" in calc, "capacity: warning #60, zero errors")
            demand(child["ShiftResource"]["instances"][0]["rows"][0][3] == 3 and exported["ShiftResource"]["rows"][0][3] == 3, "capacity: QTY3 source preserved")
            control = UP / "runs" / "c07-explicit-pair-20260930-01"
            demand((run / "model.log").read_bytes() == (control / "model.log").read_bytes(), "capacity: control event-log equality")
            report, reference = parse_native(run / "report-raw.json"), parse_native(control / "report-raw.json")
            current_tables = {t["name"]: t for t in report["report"]["tables"]}
            control_tables = {t["name"]: t for t in reference["report"]["tables"]}
            demand(current_tables.keys() == control_tables.keys() and sorted(n for n in control_tables if current_tables[n] != control_tables[n]) == ["ProblemDescription"], "capacity: report equality except description")
            cols, rr = rows(report, "ResourceResultsTotal")
            demand(len(rr) == 1 and rr[0][cols.index("NR")] == 2 and math.isclose(rr[0][cols.index("NRUM")], 4 / 36, abs_tol=1e-6) and math.isclose(rr[0][cols.index("NRW")], 2 / 36, abs_tol=1e-6), "capacity: effective two crew totals")
            cols, rr = rows(report, "ResourceResults")
            demand(len(rr) == 72 and all(x[cols.index("NR")] == 2 for x in rr) and [rr[i][cols.index("NRUM")] for i in range(47, 54)] == [2, 2, 2, 0, 0, 2, 0] and [rr[i][cols.index("NRW")] for i in range(47, 54)] == [0, 0, 0, 2, 2, 0, 0], "capacity: 72-bin resource ledger")
            cols, rr = rows(report, "SystemResults")
            demand(len(rr) == 72 and rr[-1][cols.index("NSYRY")] == 2 and all(x[cols.index("NFAIL")] == 0 for x in rr) and [rr[i][cols.index("NSYMO")] for i in range(56, 59)] == [2, 2, 0], "capacity: system ledger")
            cols, rr = rows(report, "StockTotalResults")
            demand(len(rr) == 72 and all(x[cols.index(n)] == 0 for x in rr for n in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), "capacity: stock zeros")
            demand("Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in (run / "model.log").read_text(encoding="utf-8-sig"), "capacity: mission success")
        else:
            expected_errors = ["250"] if variant == "overlap" else ["249", "250"]
            demand(errors == expected_errors and warnings == {"108", "126"} and f"Errors: {len(expected_errors)}, Warnings: 2, Notes: 0" in calc, f"{variant}: exact rejection diagnostics")
            demand((run / "model.sxo").stat().st_size == 4 and not (run / "report-raw.json").exists(), f"{variant}: unusable output, no report export")
            demand(not (run / "model.log").exists(), f"{variant}: no event log")
        observed[variant] = {"run_id": run_id, "input_sha256": INPUT_SHA[variant], "closure_sha256": sha(run / "closure.json"),
                             "run_log_sha256": sha(run / "run.log"), "warnings": sorted(warnings), "errors": errors}
    return {"schema": "simlox-c07-invalid-shifts-author-validation/v1", "passed": not issues, "issues": issues,
            "exact_diff_sha256": sha(HERE / "exact-diff.json"), "observed": observed,
            "scope": "two overlap converter rejections and one warning/clamp at nominal two crew"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
