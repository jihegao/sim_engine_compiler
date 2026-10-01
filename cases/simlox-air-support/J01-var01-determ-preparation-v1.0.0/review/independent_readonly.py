"""Independent standard-library replay of J01.var01 native raw evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
RUN = CASE / "runs" / "j01-var01-determ-probe-20261001-02"
PARENT = BASE / "B01-fixed-preparation-v1.0.1" / "native-input.json"
OUT = CASE / "review" / "independent-readonly-2026-10-01.json"
failures: list[str] = []
checks = 0


def check(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


def tables(doc: dict, root: str) -> dict:
    seq = doc[root]["tables"]
    result = {table["name"]: table for table in seq}
    check(len(result) == len(seq), f"unique {root} tables")
    return result


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    result = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            check(len(row) == len(names), f"rectangular {table['name']} row")
            result.append(dict(zip(names, row)))
    return result


def event(lines: list[tuple[float, str]], hour: float, phrase: str) -> bool:
    return any(abs(t - hour) < 1e-5 and phrase in line for t, line in lines)


def main() -> None:
    contract = read(CASE / "contract.json")
    declared = read(CASE / "parent-diff.json")
    source_path = CASE / "native-input.json"
    source, parent = tables(read(source_path), "model"), tables(read(PARENT), "model")
    check(sha(PARENT) == contract["parent_input_sha256"] == declared["parent_input_sha256"], "accepted B01 parent hash")
    check(sha(source_path) == contract["input_sha256"] == declared["child_input_sha256"], "child hash")
    check(sha(CASE / "parent-diff.json") == contract["parent_diff_sha256"], "frozen diff hash")
    check(sha(Path(contract["source"]["manual"])) == contract["source"]["manual_sha256"], "installed manual hash")
    check(sha(Path(contract["source"]["database_dictionary"])) == contract["source"]["database_dictionary_sha256"], "installed dictionary hash")
    check(set(source) - set(parent) == {"TimeDistributions"} and set(parent) - set(source) == set(), "only new TimeDistributions table")
    check({name for name in parent if source.get(name) != parent[name]} == {"MissionPreparation"}, "only changed parent table")
    check(all(source[name] == parent[name] for name in parent if name != "MissionPreparation"), "all other parent tables exact")
    old_prep, prep = rows(parent["MissionPreparation"]), rows(source["MissionPreparation"])
    dist = rows(source["TimeDistributions"])
    check(old_prep == declared["mission_preparation"]["parent_rows"] and prep == declared["mission_preparation"]["child_rows"], "exact declared preparation rows")
    check(dist == declared["time_distributions"] and len(dist) == 1, "exact declared distribution row")
    check({k: v for k, v in prep[0].items() if k != "DURND"} == {k: v for k, v in old_prep[0].items() if k != "DURND"}, "DURND only preparation change")
    check(old_prep[0]["DURND"] is None and prep[0]["DURND"] == "PREP-DET" and prep[0]["DURN"] == .5, "reference and fixed duration")
    check(dist[0] == {"DISTID": "PREP-DET", "PFAC": 1, "BASED": "<DETERM>", "PARAM1": .5, "PARAM2": None, "PARAM3": None, "NOTE": None}, "deterministic row semantics")
    check(declared["modified_tables_only"] == ["MissionPreparation"] and declared["added_tables_only"] == ["TimeDistributions"] and declared["added_rows"] == 1 and declared["removed_rows"] == 0, "declared delta scope")

    inv, closure, steps = (read(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    run_id = RUN.name
    check(inv["run_id"] == closure["run_id"] == run_id and inv["case_id"] == closure["case_id"] == "J01", "run identity")
    check(inv["original_run_dir"].lower() == str(RUN).lower() and inv["execution_mode"] == "ssh_cli_v1", "native run origin")
    check(closure["state"] == "native_steps_complete" and closure["input_sha256"] == sha(source_path), "completed closure source")
    check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation closure seal")
    mapping = {"native-input.json": source_path, "contract.json": CASE / "contract.json", "build.py": CASE / "build.py",
               "validate.py": CASE / "validate.py", "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
               "parent-diff.json": CASE / "parent-diff.json", "parent-input.json": PARENT,
               "database-dictionary.txt": Path(contract["source"]["database_dictionary"]),
               "manual.pdf": Path(contract["source"]["manual"])}
    check(set(closure["post_source_sha256"]) == set(mapping), "complete post-source hash map")
    for key, path in mapping.items():
        check(closure["post_source_sha256"].get(key) == sha(path), f"post-source {key}")
    for key, path in {"input_sha256": source_path, "contract_sha256": CASE / "contract.json",
                      "parent_input_sha256": PARENT, "parent_diff_sha256": CASE / "parent-diff.json",
                      "builder_sha256": CASE / "build.py", "validator_sha256": CASE / "validate.py",
                      "runner_sha256": CASE / "run_native_ssh.ps1",
                      "simlox_exe_sha256": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}.items():
        check(inv[key] == sha(path), f"invocation {key}")
    raw_expected = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log",
                    "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
    check(set(closure["raw"]) == raw_expected, "complete raw artifact set")
    for name, meta in closure["raw"].items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw seal {name}")
    check(sha(RUN / "input.json") == sha(source_path), "run input exact source")
    check(inv["session_id"] == 0 and inv["ssh_connection_present"] and inv["ssh_client_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "session-zero SSH")
    gui = inv["coexisting_gui"]
    check(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["allow_existing_gui"] and gui["pid"] == 13340 and gui["session_id"] == 1 and gui["responding_at_preflight"], "queue and preserved GUI")
    check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"], "four native steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["coexisting_gui_present_after"] and step["started_utc"] <= step["completed_utc"], f"{step['name']} exit and GUI")
    check((RUN / "model.sxo").stat().st_size > 4 and (RUN / "report-raw.json").stat().st_size > 4, "usable native result")
    exported = tables(read(RUN / "roundtrip-raw.json", native=True), "model")
    populated = {name: table for name, table in source.items() if rows(table)}
    check(len(populated) == 16, "16 populated source tables")
    for name, table in populated.items():
        check(exported.get(name) == table, f"exact populated roundtrip {name}")
    check(rows(exported["TimeDistributions"]) == dist and rows(exported["MissionPreparation"]) == prep,
          "native distribution and reference retained")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog and
          sorted(re.findall(r"warning #(\d+)", runlog)) == ["108", "126"] and not re.search(r"error #\d+", runlog, re.I),
          "zero converter errors and allowlisted warnings")
    check("Saving results" in runlog and "Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig") and
          "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig"), "conversion and report stages completed")

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    timed = [(float(t), line.strip()) for t, line in re.findall(r"^Time: ([0-9.]+) (.*)$", log, re.M)]
    check(bool(timed) and all(a[0] <= b[0] for a, b in zip(timed, timed[1:])), "ordered native event times")
    identity = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    aircraft = "<TEACH-AIR-01,0>"
    expected_events = [(7, f"{identity} mission allocates system: {aircraft}"),
                       (7, f"{aircraft} preparation started, mission: {identity}"),
                       (7, f"subtask 0 seqno 0 within system preparation task 0 on {aircraft} starts performing, planned to last for 0.5 hours"),
                       (7.5, f"subtask 0 seqno 0 within system preparation task 0 on {aircraft} completed"),
                       (7.5, f"{aircraft} preparation ended, mission: {identity}"),
                       (8, f"{identity} mission starting, duration: 2 : {aircraft}"),
                       (10, f"{identity} mission success:"),
                       (10, f"{identity} mission completed: {aircraft}"),
                       (10, f"System arrives {aircraft}, mission success")]
    for hour, phrase in expected_events:
        check(event(timed, hour, phrase), f"event {hour} {phrase}")
    check(len(re.findall(r"preparation started,", log)) == len(re.findall(r"preparation ended,", log)) ==
          len(re.findall(r"starts performing, planned to last for 0.5 hours", log)) == 1, "one positive preparation")
    check(len(re.findall(r"mission starting, duration:", log)) == len(re.findall(r"mission success:", log)) ==
          len(re.findall(r"mission completed:", log)) == 1 and not re.search(r"mission (?:cancelled|aborted|failed):|failure occurs", log, re.I),
          "one successful mission, no failure")
    report = tables(read(RUN / "report-raw.json", native=True), "report")
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "native report table set")
    summary = rows(report["ResultSummary"])
    check(len(summary) == 1 and all(summary[0][key] == val for key, val in
          {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.items()), "summary factors")
    system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    check(len(system) == len(stock) == 72, "72 System and Stock half-hour bins")
    for i, (sr, sk) in enumerate(zip(system, stock)):
        hour = i / 2
        assigned = int(7 <= hour < 10)
        operating = int(8 <= hour < 10)
        preparing = int(hour == 7)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": hour,
                    "ETINT": hour + .5, "NSYRY": 1 - assigned, "NSYMA": assigned, "NSYMO": operating,
                    "NSYMP": preparing, "NSYMR": int(hour == 7.5), "NSYA": 1, "FTMO": operating,
                    "STACC": operating, "NPSTA": preparing, "NPSUC": int(hour == 7.5)}
        for key, val in expected.items():
            check(sr[key] == val, f"system bin {i} {key}")
        check(all(val in (0, None) for key, val in sr.items() if key not in expected), f"system bin {i} other fields")
        stock_expected = {"STINT": hour, "ETINT": hour + .5, "PNB": 1}
        for key, val in stock_expected.items():
            check(sk[key] == val, f"stock bin {i} {key}")
        check(all(val in (0, None) for key, val in sk.items() if key not in stock_expected), f"stock bin {i} other fields")
    check(sum(row["NSYMP"] * .5 for row in system) == .5 and
          sum(row["NSYMO"] * .5 for row in system) == 2, "half-hour preparation and two flight hours")
    check(system[-1]["NSYRY"] == 1 and system[-1]["NSYMA"] == 0 and stock[-1]["NBO"] == 0,
          "terminal ready with no backorder")
    result = {"schema": "j01-var01-independent-readonly/v1", "case": CASE.name,
              "run_id": run_id, "passed": not failures, "verdict": "GO" if not failures else "NO-GO",
              "check_count": checks, "failures": failures, "input_sha256": sha(source_path),
              "closure_sha256": sha(RUN / "closure.json"), "model_log_sha256": sha(RUN / "model.log"),
              "native_report_sha256": sha(RUN / "report-raw.json"),
              "scope": "One B01-derived mission with PREP-DET/<DETERM>/PARAM1=0.5 accepted and observed 7–7.5 preparation",
              "limits": ["One fixed-seed workload and one observed preparation do not establish a statistical distribution law.",
                         "Other distribution families, parameter values, GUI-only behavior, and cross-engine parity remain untested.",
                         "The aborted -01 SSH preflight created no run directory and provides no native behavior evidence."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks, "failures": failures,
                      "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
