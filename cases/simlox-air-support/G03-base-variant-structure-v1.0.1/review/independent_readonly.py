"""Independent read-only replay for the G03 v1.0.1 BSID variants."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
RESULT = CASE / "review" / "independent-readonly-2026-10-01.json"
EXPECTED = {
    "add": ("TEACH-VAR-ADD", "82e7b380402fc1e91afa3ffb104b6e99220094cf2fe3139a6c13a74e4a6327ad"),
    "exclude": ("TEACH-VAR-EX", "79622dcc60d7172b3d09812f82e581d2e8a9f779790f24ab236508916a3875c2"),
}
checks = 0
failures: list[str] = []


def ck(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", raw))


def tables(path: Path, root: str) -> dict[str, dict]:
    return {table["name"]: table for table in load(path)[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table: dict) -> list[dict]:
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for row in rows(table)]


def main() -> None:
    contract = load(CASE / "contract.json")
    exact = load(CASE / "exact-diff.json")
    parent = AIR / "A01-single-aircraft-single-mission" / "native-input.json"
    ck(sha(parent) == contract["parent_source_sha256"] ==
       "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7", "accepted A01 parent")
    ptab = tables(parent, "model")
    reports = {}
    for variant, (sid, expected_input_sha) in EXPECTED.items():
        source = CASE / f"{variant}-input.json"
        ctab = tables(source, "model")
        ck(sha(source) == expected_input_sha == contract["variants"][variant]["input_sha256"], f"{variant} source sha")
        changed = {name for name in ptab if ptab[name] != ctab[name]}
        ck(changed == set(exact[variant]) == {"ProblemDescription", "System", "Item", "ItemStructure", "SystemDeployment", "Unit"}, f"{variant} exact changed tables")
        for name in exact[variant]:
            ck(rows(ptab[name]) == exact[variant][name]["parent"] and rows(ctab[name]) == exact[variant][name]["child"], f"{variant} exact diff {name}")
        sysrows = records(ctab["System"])
        ck(len(sysrows) == 2 and sysrows[1]["SID"] == sid and sysrows[1]["BSID"] == "TEACH-AIR-01" and sysrows[1]["CBSID"] is None, f"{variant} BSID variant")
        ck(records(ctab["SystemDeployment"]) == [{**records(ptab["SystemDeployment"])[0], "SID": sid}], f"{variant} variant only deployed")
        structure = records(ctab["ItemStructure"])
        ck(len(structure) == 2 and structure[0]["IID"] == "TEACH-LRU-BASE" and structure[0]["MID"] == "TEACH-AIR-01" and structure[0]["QTYPM"] == 1, f"{variant} base item")
        if variant == "add":
            ck(structure[1]["IID"] == "TEACH-LRU-ADD" and structure[1]["MID"] == sid and structure[1]["QTYPM"] == 1, f"{variant} additional item")
        else:
            ck(structure[1]["IID"] == "TEACH-LRU-BASE" and structure[1]["MID"] == sid and structure[1]["QTYPM"] == 0, f"{variant} excluded item")
        ck(all(not rows(ctab[name]) for name in ("Resource", "ResourceAllocation", "TaskResource", "StockAllocation", "SystemRepair", "ItemRepair", "MaterielPM")), f"{variant} no resource/repair/stock demand")
        run = CASE / "runs" / f"g03-{variant}-v101-20261001-01"
        inv, closure = load(run / "invocation.json"), load(run / "closure.json")
        ck(closure["run_id"] == inv["run_id"] == run.name and closure["error"] is None, f"{variant} run identity")
        ck(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} invocation seal")
        ck(inv["input_sha256"] == sha(source) == sha(run / "input.json"), f"{variant} copied source seal")
        ck(inv["parent_sha256"] == sha(parent), f"{variant} parent seal")
        ck(inv["contract_sha256"] == sha(CASE / "contract.json"), f"{variant} contract seal")
        ck(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], f"{variant} session0 ssh")
        ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} mutex")
        ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} GUI identity")
        ck(inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], f"{variant} source stable")
        pinned = {
            "input": source, "parent": parent, "contract": CASE / "contract.json", "builder": CASE / "build.py",
            "exact_diff": CASE / "exact-diff.json", "diff_checker": CASE / "describe_diff.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
        }
        for key, path in pinned.items():
            ck(inv["source_hashes_before"][key] == sha(path), f"{variant} pinned {key}")
        ck(inv["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", f"{variant} runtime sha")
        for name, meta in closure["raw"].items():
            path = run / name
            ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"{variant} raw {name}")
        steps = load(run / "steps.json")
        ck([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} five steps")
        for step in steps:
            ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and step["error"] is None, f"{variant} {step['name']} step")
        exported = tables(run / "roundtrip-raw.json", "model")
        populated = {name for name in ctab if rows(ctab[name])}
        ck(len(populated) == 15, f"{variant} 15 source tables")
        for name in populated:
            ck(name in exported and ctab[name]["columns"] == exported[name]["columns"] and rows(ctab[name]) == rows(exported[name]), f"{variant} exact roundtrip {name}")
        runlog = (run / "run.log").read_text(errors="replace")
        ck("Input conversion completed. Errors: 0" in runlog, f"{variant} zero conversion errors")
        ck("warning #108" in runlog and "warning #2053" in runlog, f"{variant} expected zero-FRT warnings")
        ck((run / "model.sxo").stat().st_size > 100000, f"{variant} valid SXO")
        log = (run / "model.log").read_text(errors="replace")
        mission = "BASIC-MISSION,TEACH-UNIT,0,0,0"
        expected_lines = [
            f"Time: 0 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<{sid},0>",
            f"Time: 7 <{mission}> mission allocates system: <{sid},0>",
            f"Time: 8 <{mission}> mission starting, duration: 2 : <{sid},0>",
            f"Time: 10 <{mission}> mission success:",
            f"Time: 10 <{mission}> mission completed: <{sid},0>",
            f"Time: 10 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<{sid},0>",
        ]
        for line in expected_lines:
            ck(line in log, f"{variant} event {line[:38]}")
        ck("mission aborted:" not in log and "mission cancelled:" not in log, f"{variant} no abort/cancel")
        report = tables(run / "report-raw.json", "report")
        reports[variant] = report
        ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{variant} native report tables")
        summary = records(report["ResultSummary"])
        ck(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36 and all(summary[0][x] == 1 for x in ("MTMF", "MSTF", "MSUF", "STMF")), f"{variant} mission factors")
        system = records(report["SystemResults"])
        stock = records(report["StockTotalResults"])
        ck(len(system) == len(stock) == 72, f"{variant} 72 bins")
        for i, (sr, st) in enumerate(zip(system, stock)):
            h = i / 2
            ready = int(h < 7 or h >= 10)
            prep = int(7 <= h < 8)
            mission_count = int(8 <= h < 10)
            ck((sr["STINT"], sr["ETINT"], st["STINT"], st["ETINT"]) == (h, h + .5, h, h + .5), f"{variant} bin time {i}")
            ck((sr["NSYRY"], sr["NSYMA"], sr["NSYMR"], sr["NSYMO"], sr["NSYA"], sr["FTMO"], sr["STACC"]) ==
               (ready, 1 - ready, prep, mission_count, 1, mission_count, mission_count), f"{variant} system ledger {i}")
            ck(all(value in (0, None) for key, value in sr.items() if key not in
                   {"UNID", "SID", "STINT", "ETINT", "NSYRY", "NSYMA", "NSYMR", "NSYMO", "NSYA", "FTMO", "STACC"}), f"{variant} other system metrics zero {i}")
            ck(st["PNB"] == 1 and all(value in (0, None) for key, value in st.items() if key not in
               {"STINT", "ETINT", "PNB"}), f"{variant} stock ledger {i}")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        ck(records(reports["add"][name]) == records(reports["exclude"][name]), f"pair report equality {name}")
    output = {
        "schema": "simlox-g03-v101-independent-review/v1", "passed": not failures,
        "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
        "failure_count": len(failures), "failures": failures,
        "scope": "Native source roundtrip, converter acceptance, and one variant aircraft mission for each BSID add/exclude input; 36-hour system/stock results.",
        "limits": ["The default report and zero-failure logs do not observe effective inherited item composition.",
                   "No failure-rate or repair aggregation, GUI rendering, other seeds, or cross-engine inference."],
    }
    RESULT.write_bytes((json.dumps(output, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": output["passed"], "checks": checks, "failures": failures, "result": str(RESULT)}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
