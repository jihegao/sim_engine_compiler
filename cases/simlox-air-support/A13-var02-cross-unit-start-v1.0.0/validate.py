"""Author source-bound replay of the A13.var02 explicit cross-unit pair."""
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
A13 = ROOT / "A13-start-dependence-v1.0.0" / "dependent-input.json"
A17 = ROOT / "A17-multi-unit-group-v1.0.0" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IDS = {v: f"a13-var02-cross-{v}-v100-20261001-01" for v in ("control", "dependency")}
SOURCE_SHA = {"control": "d3dc5b7a6cb59365b67c917dbc923283f3c8245b0f7547ffdbe5505a32ae9a03", "dependency": "9bd317fdbd356c039c5db85dfb75077d78b1cb524cf52e845854e5754a30472a"}
A13_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
A17_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"
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


def tables(doc: dict, root: str = "model") -> dict[str, dict]:
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for ins in table["instances"] for row in ins["rows"]]


def fields(table: dict, row: list) -> dict:
    return dict(zip((c["name"] for c in table["columns"]), row))


def event(log: str, mission: str, unit: str, phrase: str) -> list[tuple[float, str, str]]:
    rx = rf"^Time: ([0-9.]+) <({mission},{unit},0,0,[0-9]+)> {re.escape(phrase)}(.*)$"
    return [(float(t), ident, detail) for t, ident, detail in re.findall(rx, log, re.M)]


def source_gate() -> None:
    for path, expected, name in ((A13, A13_SHA, "A13"), (A17, A17_SHA, "A17"), (MANUAL, MANUAL_SHA, "manual"), (EXE, EXE_SHA, "executable")):
        ck(sha(path) == expected, f"{name} SHA")
    sources = {v: parse_native(HERE / f"{v}-input.json") for v in IDS}
    tab = {v: tables(sources[v]) for v in IDS}
    for v in IDS:
        ck(sha(HERE / f"{v}-input.json") == SOURCE_SHA[v], f"{v} source SHA")
        ck(len(populated(sources[v])) == (13 if v == "control" else 14), f"{v} populated count")
    ck("MissionDependence" not in tab["control"], "no-row topology")
    ck(set(tab["dependency"]) == set(tab["control"]) | {"MissionDependence"}, "dependency table addition")
    ck(all(tab["dependency"][n] == tab["control"][n] for n in tab["control"] if n != "ProblemDescription"), "only description differs outside dependency")
    dep = fields(tab["dependency"]["MissionDependence"], rows(tab["dependency"]["MissionDependence"])[0])
    ck((dep["DUNID"], dep["DMTID"], dep["DSTIM"], dep["PUNID"], dep["PMTID"], dep["PSTIM"], dep["DTYPE"]) == ("TEACH-UNIT-2", "FOLLOW", 10, "TEACH-UNIT", "RECON", 8, "START"), "cross-unit key")
    structural = tables(parse_native(A17))
    for name in ("Station", "Unit", "SystemDeployment"):
        ck(tab["control"][name] == structural[name], f"{name} A17 topology")
    ops = [fields(tab["control"]["Operations"], row) for row in rows(tab["control"]["Operations"])]
    ck([(x["USTID"], x["PRID"]) for x in ops] == [("TEACH-UNIT", "RECON-SCHEDULE"), ("TEACH-UNIT-2", "FOLLOW-SCHEDULE")], "separate operation owners")
    diff = parse_native(HERE / "exact-diff.json")
    ck(diff["parent_sha256"] == A13_SHA and diff["structural_source_sha256"] == A17_SHA and all(diff["variants"][v]["input_sha256"] == SOURCE_SHA[v] for v in IDS), "exact diff sources")


def replay(variant: str) -> dict:
    run = RUNS / IDS[variant]
    inv, clo, steps = (parse_native(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck(inv["run_id"] == clo["run_id"] == IDS[variant] and inv["variant"] == variant and inv["variant_id"] == "A13.var02", f"{variant} run identity")
    ck(inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], f"{variant} SSH")
    ck(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} queue/GUI")
    ck(inv["input_sha256"] == SOURCE_SHA[variant] and inv["parent_sha256"] == A13_SHA and inv["structure_sha256"] == A17_SHA, f"{variant} lineage")
    ck(sha(run / "invocation.json") == clo["invocation_sha256"] and clo["error"] is None, f"{variant} closure status")
    ck(clo["source_hashes_before"] == clo["source_hashes_after"] == inv["source_hashes_before"], f"{variant} source stability")
    paths = {
        "input": HERE / f"{variant}-input.json", "parent": A13, "structure": A17,
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
        "checker": HERE / "check_roundtrip.py", "python": PYTHON,
        "runner_script": HERE / "run_native_ssh.ps1", "simlox_exe": EXE,
    }
    for key, path in paths.items():
        ck(sha(path) == clo["source_hashes_before"][key], f"{variant} {key} SHA")
    ck(set(clo["raw"]) == {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}, f"{variant} raw set")
    for name, rec in clo["raw"].items():
        p = run / name
        ck(p.stat().st_size == rec["bytes"] and sha(p) == rec["sha256"], f"{variant} raw {name}")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} step names")
    ck([s["status"] for s in steps] == ["completed", "completed", "calc_observed", "completed", "completed"], f"{variant} step status")
    ck(all(s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps), f"{variant} step success/GUI")
    ck(all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(3)) and steps[3]["arguments"] == inv["planned_report"]["arguments"], f"{variant} exact CLI args")
    rt = check_roundtrip(run)
    ck(rt["passed"] is True and parse_native(run / "roundtrip-validation.json")["passed"] is True, f"{variant} source roundtrip")
    ck((run / "model.sxo").stat().st_size > 4 and (run / "model.log").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 4, f"{variant} valid output")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126] and not re.search(r"error #\d+", calc), f"{variant} converter")
    ck("Saving results" in calc and "Total execution time:" in calc, f"{variant} calculation completion")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    starts = {}
    ends = {}
    for mission, unit, aircraft, base, alloc_time, start_time, end_time in (
        ("RECON", "TEACH-UNIT", 0, "BASE-01", 7, 8, 12),
        ("FOLLOW", "TEACH-UNIT-2", 1, "BASE-02", 9, 12 if variant == "dependency" else 10, 14 if variant == "dependency" else 12),
    ):
        alloc = event(log, mission, unit, "mission allocates system:")
        start = event(log, mission, unit, "mission starting,")
        success = event(log, mission, unit, "mission success:")
        complete = event(log, mission, unit, "mission completed:")
        ck(len(alloc) == len(start) == len(success) == len(complete) == 1, f"{variant} {mission} cardinality")
        ck(alloc[0][1] == start[0][1] == success[0][1] == complete[0][1], f"{variant} {mission} identity")
        ck(alloc[0][0] == alloc_time and f"<TEACH-AIR-01,{aircraft}>" in alloc[0][2], f"{variant} {mission} assignment")
        ck(start[0][0] == start_time and success[0][0] == complete[0][0] == end_time, f"{variant} {mission} start/success/complete")
        ck(f"Time: {end_time} <TEACH-AIR-01,{base},0> System arrives <TEACH-AIR-01,{aircraft}>" in log, f"{variant} {mission} home-base return")
        starts[mission], ends[mission] = start_time, end_time
    ck(len(re.findall(r"mission starting,", log)) == len(re.findall(r"mission success:", log)) == len(re.findall(r"mission completed:", log)) == 2, f"{variant} only two missions")
    ck(not re.search(r"mission (?:abort|cancel|fail)", log, re.I), f"{variant} no mission loss")
    report = parse_native(run / "report-raw.json")
    summary = tables(report, "report")["ResultSummary"]
    ck(len(rows(summary)) == 1, f"{variant} summary rows")
    sm = fields(summary, rows(summary)[0])
    ck(all(sm[k] == value for k, value in {"NREP": 1, "RTILW": 0, "RTIUP": 24, "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.items()), f"{variant} summary factors")
    sy = tables(report, "report")["SystemResults"]
    st = tables(report, "report")["StockTotalResults"]
    syrows, strows = rows(sy), rows(st)
    ck(len(syrows) == len(strows) == 48, f"{variant} 48 bins")
    for i, (a, b) in enumerate(zip(syrows, strows)):
        a, b = fields(sy, a), fields(st, b)
        time = i / 2
        ck(a["STINT"] == b["STINT"] == time and a["ETINT"] == b["ETINT"] == time + .5, f"{variant} bin{i} interval")
        assigned = int(7 <= time < 12) + int(9 <= time < ends["FOLLOW"])
        operating = int(8 <= time < 12) + int(starts["FOLLOW"] <= time < ends["FOLLOW"])
        ck(a["NSYMA"] == assigned and a["NSYMO"] == operating and a["NSYRY"] == 2 - assigned, f"{variant} bin{i} aircraft ledger")
        ck(a["UNID"] == "Total over all Units" and a["SID"] == "Total over all Systems" and a["NSYA"] == 2, f"{variant} bin{i} aggregate")
        for field in ("NFAIL", "NDAM", "NPMS", "NROBT", "NRCFG"):
            ck(a[field] == 0, f"{variant} bin{i} {field}")
        for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"):
            ck(b[field] == 0, f"{variant} bin{i} {field}")
        ck(b["PNB"] == 1, f"{variant} bin{i} base stock ledger")
    syfields = [fields(sy, row) for row in syrows]
    operating_hours = sum(.5 * row["NSYMO"] for row in syfields)
    assigned_hours = sum(.5 * row["NSYMA"] for row in syfields)
    ck(operating_hours == 6 and assigned_hours == (10 if variant == "dependency" else 8), f"{variant} integrated aircraft hours")
    ck(syfields[-1]["NSYRY"] == 2 and syfields[-1]["NSYMA"] == syfields[-1]["NSYMO"] == 0, f"{variant} terminal state")
    return {"run_id": IDS[variant], "closure_sha256": sha(run / "closure.json"), "report_sha256": sha(run / "report-raw.json"), "model_log_sha256": sha(run / "model.log"), "roundtrip_tables": len(rt["populated_tables"]), "starts": starts, "ends": ends, "assigned_hours": assigned_hours, "operating_hours": operating_hours}


def main() -> int:
    try:
        source_gate()
        observed = {v: replay(v) for v in IDS}
        ck(observed["control"]["starts"]["FOLLOW"] == 10 and observed["dependency"]["starts"]["FOLLOW"] == 12, "paired launch shift")
        ck(observed["control"]["ends"]["RECON"] == observed["dependency"]["ends"]["RECON"] == 12, "paired predecessor consistency")
        reports = {v: tables(parse_native(RUNS / IDS[v] / "report-raw.json"), "report") for v in IDS}
        ck({n for n in reports["control"] if reports["control"][n] != reports["dependency"][n]} == {"ProblemDescription", "SystemResults"}, "paired report delta")
        output = {"schema": "simlox-a13-var02-cross-unit-v100-author-replay/v1", "passed": True, "checks": checks, "runs": observed, "limit": "same-time return/launch internal ordering and group-owned branch unverified"}
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as exc:
        output = {"schema": "simlox-a13-var02-cross-unit-v100-author-replay/v1", "passed": False, "checks_before_failure": checks, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
