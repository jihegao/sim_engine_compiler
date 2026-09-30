"""Source-bound author replay of three immutable A13.var01 native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated, validate as check_roundtrip

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = HERE / "runs"
PARENT = ROOT / "A13-start-dependence-v1.0.0" / "dependent-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
RUN_IDS = {v: f"a13-var01-{v}-v100-20261001-01" for v in ("control", "single", "multiple")}
SOURCES = {
    "control": "dad6d27f7b565235e9fcfedde9862c84596c8360fd32bb191959e0d6d32ab82a",
    "single": "d816f5de462263c746a7094603417c7fdc618c03374685b8ead484f545bae030",
    "multiple": "1d2226850d07d7caf5f58e825bb2d3fdf498f7626fb58e4a6ed4bcfa469d18ae",
}
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
checks = 0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ck(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        raise ValueError(label)


def table_rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    rows = [r for instance in table["instances"] for r in instance["rows"]]
    return columns, rows


def mission_events(log: str, mission: str, phrase: str) -> list[tuple[float, str, str]]:
    pattern = rf"^Time: ([0-9.]+) <({mission},TEACH-UNIT,0,0,[0-9]+)> {re.escape(phrase)}(.*)$"
    return [(float(time), identity, detail) for time, identity, detail in re.findall(pattern, log, re.M)]


def static_sources() -> None:
    ck(sha(PARENT) == PARENT_SHA, "parent SHA")
    ck(sha(MANUAL) == MANUAL_SHA, "manual SHA")
    ck(sha(EXE) == EXE_SHA, "native executable SHA")
    docs = {v: json.loads((HERE / f"{v}-input.json").read_text(encoding="utf-8")) for v in RUN_IDS}
    tabs = {v: {t["name"]: t for t in docs[v]["model"]["tables"]} for v in RUN_IDS}
    for v in RUN_IDS:
        ck(sha(HERE / f"{v}-input.json") == SOURCES[v], f"{v} input SHA")
        ck(len(populated(docs[v])) == (13 if v == "control" else 14), f"{v} table count")
    ck("MissionDependence" not in tabs["control"], "control dependence absent")
    for v, count in (("single", 1), ("multiple", 2)):
        rows = tabs[v]["MissionDependence"]["instances"][0]["rows"]
        ck(len(rows) == count, f"{v} dependence count")
        ck([r[4] for r in rows] == (["EARLY"] if v == "single" else ["EARLY", "LATE"]), f"{v} precedent identities")
        ck(all(r[:4] == ["TEACH-UNIT", "FOLLOW", 10.0, "TEACH-UNIT"] and r[5:7] == [8.0, "START"] for r in rows), f"{v} dependence keys")
    ck(all(tabs["single"][n] == tabs["multiple"][n] for n in tabs["single"] if n not in ("MissionDependence", "ProblemDescription")), "single/multiple non-dependence tables")
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    ck(diff["parent_sha256"] == PARENT_SHA and all(diff["variants"][v]["input_sha256"] == SOURCES[v] for v in RUN_IDS), "exact diff fingerprints")


def replay_one(variant: str) -> dict:
    run = RUNS / RUN_IDS[variant]
    inv = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    ck(inv["run_id"] == closure["run_id"] == RUN_IDS[variant] and inv["variant"] == variant, f"{variant} identity")
    ck(inv["case_id"] == "A13" and inv["variant_id"] == "A13.var01", f"{variant} case identity")
    ck(inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], f"{variant} SSH identity")
    ck(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} queue/GUI")
    ck(inv["input_sha256"] == SOURCES[variant] and inv["parent_sha256"] == PARENT_SHA, f"{variant} source identity")
    ck(sha(run / "invocation.json") == closure["invocation_sha256"], f"{variant} invocation SHA")
    ck(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"], f"{variant} source stability")
    expected_paths = {
        "input": HERE / f"{variant}-input.json", "parent": PARENT, "contract": HERE / "contract.json",
        "builder": HERE / "build.py", "exact_diff": HERE / "exact-diff.json",
        "diff_checker": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
        "python": PYTHON, "runner_script": HERE / "run_native_ssh.ps1", "simlox_exe": EXE,
    }
    for key, path in expected_paths.items():
        ck(sha(path) == closure["source_hashes_before"][key], f"{variant} {key} source SHA")
    ck(all((run / name).is_file() and (run / name).stat().st_size == item["bytes"] and sha(run / name) == item["sha256"] for name, item in closure["raw"].items()), f"{variant} raw hashes")
    ck(set(closure["raw"]) == {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}, f"{variant} complete raw set")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} step list")
    ck(all(s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps), f"{variant} step exits and GUI")
    ck([s["status"] for s in steps] == ["completed", "completed", "calc_observed", "completed", "completed"], f"{variant} step states")
    ck(all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(3)) and steps[3]["arguments"] == inv["planned_report"]["arguments"], f"{variant} CLI arguments")
    roundtrip = check_roundtrip(run)
    ck(roundtrip["passed"] is True and json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"] is True, f"{variant} source roundtrip")
    ck((run / "model.sxo").stat().st_size > 4 and (run / "model.log").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 4, f"{variant} valid nonempty output")
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog and sorted(map(int, re.findall(r"warning #(\d+)", runlog))) == [108, 126] and not re.search(r"error #\d+", runlog), f"{variant} converter status")
    ck("Saving results" in runlog and "Total execution time:" in runlog, f"{variant} calculation completion")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    starts = {}
    ends = {}
    allocations = {}
    for mission, expected_start, expected_end, aircraft in (
        ("EARLY", 8, 9, 0), ("LATE", 8, 12, 1),
        ("FOLLOW", 12 if variant == "multiple" else 10, 14 if variant == "multiple" else 12, 2),
    ):
        alloc = mission_events(log, mission, "mission allocates system:")
        start = mission_events(log, mission, "mission starting,")
        success = mission_events(log, mission, "mission success:")
        complete = mission_events(log, mission, "mission completed:")
        ck(len(alloc) == len(start) == len(success) == len(complete) == 1, f"{variant} {mission} event cardinality")
        ck(alloc[0][1] == start[0][1] == success[0][1] == complete[0][1], f"{variant} {mission} mission identity")
        ck(alloc[0][0] == (9 if mission == "FOLLOW" else 7) and f"<TEACH-AIR-01,{aircraft}>" in alloc[0][2], f"{variant} {mission} assignment")
        ck(start[0][0] == expected_start and success[0][0] == complete[0][0] == expected_end, f"{variant} {mission} timing")
        ck(f"Time: {expected_end} <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,{aircraft}>" in log, f"{variant} {mission} return")
        starts[mission], ends[mission], allocations[mission] = expected_start, expected_end, alloc[0][0]
    ck(len(re.findall(r"mission starting,", log)) == len(re.findall(r"mission success:", log)) == len(re.findall(r"mission completed:", log)) == 3, f"{variant} only three missions")
    ck(not re.search(r"mission (?:abort|cancel|fail)", log, re.I), f"{variant} no mission failure")
    report = parse_native(run / "report-raw.json")
    cols, summary_rows = table_rows(report, "ResultSummary")
    ck(len(summary_rows) == 1, f"{variant} summary cardinality")
    summary = dict(zip(cols, summary_rows[0]))
    ck(all(summary[k] == v for k, v in {"NREP": 1, "RTILW": 0, "RTIUP": 24, "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.items()), f"{variant} summary metrics")
    scols, system = table_rows(report, "SystemResults")
    tcols, stock = table_rows(report, "StockTotalResults")
    ck(len(system) == len(stock) == 48, f"{variant} 48 bins")
    si, ti = ({c: i for i, c in enumerate(cols)} for cols in (scols, tcols))
    for i, (sy, st) in enumerate(zip(system, stock)):
        start = i / 2
        end = start + .5
        ck(sy[si["STINT"]] == st[ti["STINT"]] == start and sy[si["ETINT"]] == st[ti["ETINT"]] == end, f"{variant} bin {i} times")
        operating = sum(a <= start < b for a, b in ((8, 9), (8, 12), (starts["FOLLOW"], ends["FOLLOW"])))
        assigned = sum(a <= start < b for a, b in ((7, 9), (7, 12), (9, ends["FOLLOW"])))
        ck(sy[si["NSYMO"]] == operating and sy[si["NSYMA"]] == assigned and sy[si["NSYRY"]] == 3 - assigned, f"{variant} bin {i} aircraft ledger")
        ck(all(sy[si[k]] == 0 for k in ("NFAIL", "NDAM", "NPMS", "NROBT", "NRCFG")), f"{variant} bin {i} no failures/maintenance")
        ck(all(st[ti[k]] == 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant} bin {i} stock ledger")
    operating_hours = sum((r[si["ETINT"]] - r[si["STINT"]]) * r[si["NSYMO"]] for r in system)
    assigned_hours = sum((r[si["ETINT"]] - r[si["STINT"]]) * r[si["NSYMA"]] for r in system)
    ck(operating_hours == 7 and assigned_hours == (12 if variant == "multiple" else 10), f"{variant} integrated aircraft hours")
    ck(system[-1][si["NSYRY"]] == 3 and system[-1][si["NSYMA"]] == system[-1][si["NSYMO"]] == 0, f"{variant} terminal state")
    return {"run_id": RUN_IDS[variant], "closure_sha256": sha(run / "closure.json"), "report_sha256": sha(run / "report-raw.json"), "model_log_sha256": sha(run / "model.log"), "roundtrip_tables": len(roundtrip["populated_tables"]), "starts": starts, "ends": ends, "allocated_hours": assigned_hours, "operating_hours": operating_hours}


def main() -> int:
    try:
        static_sources()
        observed = {v: replay_one(v) for v in RUN_IDS}
        ck(observed["control"]["starts"]["FOLLOW"] == observed["single"]["starts"]["FOLLOW"] == 10, "early-only contrast")
        ck(observed["multiple"]["starts"]["FOLLOW"] == 12 and observed["multiple"]["ends"]["LATE"] == 12, "multiple-predecessor boundary")
        ck(observed["control"]["model_log_sha256"] == observed["single"]["model_log_sha256"], "control/single event log identity")
        reports = {v: parse_native(RUNS / RUN_IDS[v] / "report-raw.json") for v in RUN_IDS}
        report_tables = {v: {t["name"]: t for t in reports[v]["report"]["tables"]} for v in RUN_IDS}
        ck({n for n in report_tables["control"] if report_tables["control"][n] != report_tables["single"][n]} == {"ProblemDescription"}, "control/single report equality except description")
        ck({n for n in report_tables["single"] if report_tables["single"][n] != report_tables["multiple"][n]} == {"ProblemDescription", "SystemResults"}, "single/multiple report delta")
        output = {"schema": "simlox-a13-var01-multiple-predecessors-v100-author-replay/v1", "passed": True, "checks": checks, "runs": observed, "limit": "same-time late return and FOLLOW launch do not establish internal event order"}
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as exc:
        output = {"schema": "simlox-a13-var01-multiple-predecessors-v100-author-replay/v1", "passed": False, "checks_before_failure": checks, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
