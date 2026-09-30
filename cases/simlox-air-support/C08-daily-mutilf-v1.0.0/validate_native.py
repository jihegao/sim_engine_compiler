"""Author replay of four guarded daily MUTILF native runs."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
PARENT_SHA = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"
INPUT_SHA = {
    "no-shift-control": "9fab93b5101e77a156f7b04d8d15039fc05ec3c81de965695ff2fd5e46baefcf",
    "zero-budget": "09c54340d7afbe501e01967ec94276c14f346fbbba3268f3e05378c9ae7d72ec",
    "finite-budget": "4b08b2ca4469d9f12a601b766607173f22b730837e9839880d712b40d9508322",
    "station-override": "86e0919d4a4063d95829fcdb26d5a48eb32e912ebfff10536055e9bd795cddc5",
}
DIRECT_PARENT = {
    "no-shift-control": PARENT,
    "zero-budget": HERE / "no-shift-control-input.json",
    "finite-budget": HERE / "no-shift-control-input.json",
    "station-override": HERE / "finite-budget-input.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    item = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in item["columns"]], [r for ins in item["instances"] for r in ins["rows"]]


def tables(path: Path) -> dict:
    return {t["name"]: t for t in parse_native(path)["model"]["tables"]}


def check() -> dict:
    issues: list[str] = []
    def demand(ok: bool, label: str) -> None:
        if not ok:
            issues.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    exact = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    demand(sha(PARENT) == PARENT_SHA == contract["parent_input_sha256"] == exact["accepted_parent_sha256"], "accepted C07 parent")
    demand(sha(HERE / "exact-diff.json") == "ded327c20f9d614f8197fb72aacaa7f908af5356d6841b6d497f6530d0eb18b5", "exact diff frozen")
    observed: dict[str, dict] = {}
    reports: dict[str, dict] = {}
    logs: dict[str, bytes] = {}
    for variant, fingerprint in INPUT_SHA.items():
        run_id = f"c08-{variant}-20260930-01"
        run = HERE / "runs" / run_id
        source = HERE / f"{variant}-input.json"
        direct = DIRECT_PARENT[variant]
        before, after = tables(direct), tables(source)
        changed = sorted(n for n in before if before[n] != after[n])
        item = exact["variants"][variant]
        demand(before.keys() == after.keys() and changed == item["changed_tables"] and item["parent_sha256"] == sha(direct), f"{variant}: exact direct-parent delta")
        demand(sha(source) == sha(run / "input.json") == fingerprint == contract["input_sha256"][variant] == item["input_sha256"], f"{variant}: frozen input")
        demand(after["ResourceStationData"]["instances"][0]["rows"][0][9] is None, f"{variant}: shift profile unlinked")
        expected_resource = {"no-shift-control": None, "zero-budget": 0.0, "finite-budget": 0.03125, "station-override": 0.03125}[variant]
        expected_station = 1.0 if variant == "station-override" else None
        demand(after["Resource"]["instances"][0]["rows"][0][6] == expected_resource and after["ResourceStationData"]["instances"][0]["rows"][0][4] == expected_station, f"{variant}: MUTILF source values")
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        demand(invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant and invocation["case_id"] == "C08", f"{variant}: run identity")
        demand(invocation["parent_sha256"] == sha(direct) and invocation["accepted_parent_sha256"] == PARENT_SHA and invocation["input_sha256"] == fingerprint, f"{variant}: parent/input bindings")
        demand(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant}: session-zero SSH and mutex")
        demand(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant}: GUI identity")
        demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], f"{variant}: source seals")
        for key, path in {"input": source, "parent": direct, "accepted_parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
            demand(closure["source_hashes_before"][key] == sha(path), f"{variant}: runtime {key}")
        demand(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant}: invocation seal")
        demand([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant}: five steps")
        for name, raw in closure["raw"].items():
            path = run / name
            demand(path.is_file() and path.stat().st_size == raw["bytes"] and sha(path) == raw["sha256"], f"{variant}: raw {name}")
        demand(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], f"{variant}: roundtrip checker")
        imported, exported = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        demand(len(imported) == 24 and all(exported.get(n) == t for n, t in imported.items()), f"{variant}: 24 row-containing source tables")
        demand(exported["Resource"]["rows"][0][6] == expected_resource and exported["ResourceStationData"]["rows"][0][4] == expected_station and exported["ResourceStationData"]["rows"][0][9] is None, f"{variant}: native MUTILF/SHPID roundtrip")
        calc = (run / "run.log").read_text(encoding="utf-8-sig")
        demand(re.findall(r"error\s+#(\d+)", calc, re.I) == [] and set(re.findall(r"warning\s+#(\d+)", calc, re.I)) == {"108", "126"} and "Errors: 0, Warnings: 2, Notes: 0" in calc, f"{variant}: zero-error conversion")
        demand((run / "model.sxo").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 4, f"{variant}: valid output")
        log_bytes = (run / "model.log").read_bytes()
        log = log_bytes.decode("utf-8-sig")
        demand("resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period" in log and "resource shift 1 created" not in log, f"{variant}: no active shift")
        reports[variant], logs[variant] = parse_native(run / "report-raw.json"), log_bytes
        cols, rr = rows(reports[variant], "ResourceResultsTotal")
        expected_work, expected_wait = {"no-shift-control": (4, 0), "zero-budget": (0, 7), "finite-budget": (2.5, 8.5), "station-override": (4, 0)}[variant]
        demand(len(rr) == 1 and rr[0][cols.index("NR")] == 2 and math.isclose(rr[0][cols.index("NRUM")], expected_work / 36, abs_tol=1e-6) and math.isclose(rr[0][cols.index("NRW")], expected_wait / 36, abs_tol=1e-6), f"{variant}: resource totals")
        cols, rr = rows(reports[variant], "ResourceResults")
        demand(len(rr) == 72 and all(row[cols.index("NR")] == 2 for row in rr) and math.isclose(sum(row[cols.index("NRUM")] * .5 for row in rr), expected_work, abs_tol=1e-6) and math.isclose(sum(row[cols.index("NRW")] * .5 for row in rr), expected_wait, abs_tol=1e-6), f"{variant}: 72-bin work/wait ledger")
        work_bins = {i: row[cols.index("NRUM")] for i, row in enumerate(rr) if row[cols.index("NRUM")]}
        wait_bins = {i: row[cols.index("NRW")] for i, row in enumerate(rr) if row[cols.index("NRW")]}
        expected_work_bins = {"no-shift-control": {47:2,48:2,49:2,50:2}, "zero-budget": {}, "finite-budget": {47:2,48:2,49:1}, "station-override": {47:2,48:2,49:2,50:2}}[variant]
        expected_wait_bins = {"no-shift-control": {}, "zero-budget": {i:2 for i in range(47,54)}, "finite-budget": {49:1, **{i:2 for i in range(50,58)}}, "station-override": {}}[variant]
        demand(work_bins == expected_work_bins and wait_bins == expected_wait_bins, f"{variant}: exact nonzero resource bins")
        cols, rr = rows(reports[variant], "SystemResults")
        expected_mission = [2,2] if variant in ("no-shift-control", "station-override") else [0,0]
        demand(len(rr) == 72 and rr[-1][cols.index("NSYRY")] == 2 and all(row[cols.index("NFAIL")] == 0 for row in rr) and [rr[i][cols.index("NSYMO")] for i in (56,57)] == expected_mission, f"{variant}: system/mission ledger")
        cols, rr = rows(reports[variant], "StockTotalResults")
        demand(len(rr) == 72 and all(row[cols.index(n)] == 0 for row in rr for n in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant}: stock zeros")
        if variant in ("no-shift-control", "station-override"):
            demand(all(f"Time: 25.5 <TEACH-AIR-01,{i}> preparation ended" in log for i in (0,1)) and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log and "out of utilisation time" not in log, f"{variant}: continuous prep and success")
        elif variant == "zero-budget":
            demand("Time: 27 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled" in log and "starts performing" not in log and "mission success" not in log, "zero-budget: no positive work/cancellation")
        else:
            demand("Time: 24  Start of day no 1" in log and "Time: 24.75  <P-CREW at <BASE-01,0>> out of utilisation time" in log and all(f"Time: 24.75  subtask {i} seqno 1 within system preparation task {i} on <TEACH-AIR-01,{i}> is stopped due to resource time-out, time left= 0.75" in log for i in (0,1)) and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled" in log and "mission success" not in log, "finite-budget: daily reset/timeout/cancellation")
        observed[variant] = {"run_id": run_id, "input_sha256": fingerprint, "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"), "report_raw_sha256": sha(run / "report-raw.json"), "crew_hours_worked": expected_work, "resource_hours_waiting": expected_wait}

    control_tables = {t["name"]: t for t in reports["no-shift-control"]["report"]["tables"]}
    override_tables = {t["name"]: t for t in reports["station-override"]["report"]["tables"]}
    demand(logs["no-shift-control"] == logs["station-override"] and control_tables.keys() == override_tables.keys() and sorted(n for n in control_tables if control_tables[n] != override_tables[n]) == ["ProblemDescription"], "station MUTILF override restores control")
    return {"schema": "simlox-c08-daily-mutilf-author-validation/v1", "passed": not issues, "issues": issues, "exact_diff_sha256": sha(HERE / "exact-diff.json"), "observed": observed, "scope": "one no-shift two-crew daily MUTILF zero/finite/station-override comparison"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
