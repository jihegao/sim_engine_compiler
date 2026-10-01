"""Standalone stdlib replay of J04.var04 threads-one/two native evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "J04-var03-nreps-cap-v1.0.0"
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
failures: list[str] = []
checks = 0


def ck(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False) -> dict:
    value = path.read_text(encoding="utf-8-sig")
    if native:
        value = re.sub(r",\s*([}\]])", r"\1", value)
    return json.loads(value)


def tables(document: dict, root: str) -> dict:
    source = document[root]["tables"]
    result = {t["name"]: t for t in source}
    ck(len(result) == len(source), f"unique {root} table names")
    return result


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    result = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            ck(len(names) == len(values), f"well-formed {table['name']} row")
            result.append(dict(zip(names, values)))
    return result


def near(value: float, expected: float, label: str, tolerance: float = 5e-5) -> None:
    ck(value is not None and abs(value - expected) <= tolerance,
       f"{label}: {value!r} versus {expected!r}")


def source_checks(contract: dict, diff: dict) -> dict:
    parent_input, child_input = PARENT / "probe-input.json", CASE / "probe-input.json"
    ck(sha(parent_input) == sha(child_input) == contract["parent_input_sha256"] ==
       contract["input_sha256"] == diff["parent_input_sha256"] == diff["input_sha256"],
       "byte-identical accepted parent/child source input")
    ck(sha(CASE / "probe-diff.json") == contract["exact_diff_sha256"] and
       diff["model_byte_delta"] == "none" and
       diff["native_cli_delta"] == {"calc_threads_parent": 1, "calc_threads_probe": 2},
       "frozen exact no-model diff and CLI thread delta")
    for path, expected in ((Path(contract["source"]["manual"]), contract["source"]["manual_sha256"]),
                           (Path(contract["source"]["database_dictionary"]),
                            contract["source"]["database_dictionary_sha256"])):
        ck(sha(path) == expected, f"installed {path.name} SHA")
    executable = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
    exe_sha = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
    ck(sha(executable) == exe_sha and
       all(exe_sha in (c / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
           for c in (PARENT, CASE)), "common installed executable pin")
    parent_runner = (PARENT / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    child_runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck(bool(re.search(r"-threads 1 -calc", parent_runner)) and
       not re.search(r"-threads 2 -calc", parent_runner) and
       bool(re.search(r"-threads 2 -calc", child_runner)) and
       not re.search(r"-threads 1 -calc", child_runner),
       "source-bound native calc CLI threads 1 versus 2")
    parent = tables(read(parent_input), "model")
    child = tables(read(child_input), "model")
    ck(parent == child, "all business tables equal")
    populated = [name for name, t in child.items() if any(i["rows"] for i in t["instances"])]
    ck(len(populated) == 14, "fourteen populated business tables")
    control = rows(child["Control"])
    ck(len(control) == 1 and control[0]["NREPS"] == 32 and control[0]["TCLEV"] == .09 and
       control[0]["RSEED"] == "1" and control[0]["ENLOG"] == "Y" and
       control[0]["SIMPE"] == 36 and control[0]["RCINT"] == .5,
       "identical NREPS32/TCLEV.09/seed1 input semantics")
    expected = contract["expected_observation"]
    ck(expected["run_ids"] == [f"j04-var04-thread2-accepted-20261001-{n:02d}" for n in (2, 3)] and
       expected["parent_thread_one_run_ids"] ==
       [f"j04-var03-nreps-cap-accepted-20261001-{n:02d}" for n in (1, 2)] and
       expected["calc_threads"] == 2 and expected["parent_calc_threads"] == 1,
       "frozen four-run comparison and thread counts")
    return child


def replay(case: Path, run_id: str, threads: int, source: dict, contract: dict) -> dict:
    p = case / "runs" / run_id
    invocation, closure, steps = (read(p / n) for n in ("invocation.json", "closure.json", "steps.json"))
    input_path = case / "probe-input.json"
    ck(invocation["run_id"] == closure["run_id"] == run_id and
       invocation["input_sha256"] == closure["input_sha256"] == sha(input_path) and
       closure["invocation_sha256"] == sha(p / "invocation.json") and
       closure["state"] == "native_steps_complete", f"{run_id} invocation/closure")
    if threads == 2:
        ck(invocation["calc_threads"] == 2, f"{run_id} invocation calc_threads 2")
    else:
        ck("calc_threads" not in invocation, f"{run_id} one-thread parent invocation schema")
    manifest = read(p / "run-manifest.json")
    ck(manifest["run_id"] == run_id and manifest["input_sha256"] == sha(input_path) and
       manifest["closure_sha256"] == sha(p / "closure.json") and
       manifest["validation_sha256"] == sha(p / "validation.json") and
       manifest["execution_mode"] == "ssh_cli_v1" and
       (manifest.get("calc_threads") == 2 if threads == 2 else "calc_threads" not in manifest),
       f"{run_id} manifest binding")
    fixed = {"contract.json": case / "contract.json", "build.py": case / "build.py",
             "probe-diff.json": case / "probe-diff.json", "run_native_ssh.ps1": case / "run_native_ssh.ps1",
             "validate.py": case / "validate.py", "validate_pair.py": case / "validate_pair.py",
             "probe-input.json": input_path, "parent-input.json": PARENT / "probe-input.json" if threads == 2
             else CASE.parent / "J04-var02-confidence-stop-v1.0.0" / "probe256-input.json",
             "manual.pdf": Path(contract["source"]["manual"]),
             "database-dictionary.txt": Path(contract["source"]["database_dictionary"])}
    ck(set(closure["post_source_sha256"]) == set(fixed), f"{run_id} full source map")
    for name, path in fixed.items():
        ck(closure["post_source_sha256"].get(name) == sha(path),
           f"{run_id} source seal {name}")
    for key, name in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"),
                      ("validator_sha256", "validate.py"), ("pair_validator_sha256", "validate_pair.py"),
                      ("runner_sha256", "run_native_ssh.ps1")):
        ck(invocation[key] == sha(fixed[name]), f"{run_id} invocation {key}")
    ck(set(closure["raw"]) == RAW, f"{run_id} eleven raw seals")
    for name, meta in closure["raw"].items():
        path = p / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"],
           f"{run_id} raw seal {name}")
    ck(sha(p / "input.json") == sha(input_path), f"{run_id} raw input copy")
    ck(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
       invocation["gui_pid"] == 13340 and
       invocation["gui_start_utc"] == "2026-09-28T10:09:56.8261381Z",
       f"{run_id} SSH/mutex/GUI guard")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport"] and
       all(s["exit_code"] == 0 and s["coexisting_gui_present_after"] for s in steps),
       f"{run_id} four completed native steps")
    ck((p / "model.sxo").stat().st_size > 4, f"{run_id} valid SXO")
    exported = tables(read(p / "roundtrip-raw.json", native=True), "model")
    for name, table in source.items():
        if any(i["rows"] for i in table["instances"]):
            ck(exported.get(name) == table, f"{run_id} exact business roundtrip {name}")
    runlog = (p / "run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog and
       sorted(re.findall(r"warning #(\d+)", runlog)) == ["108", "126", "211"] and
       not re.search(r"error #\d+", runlog, re.I) and "Saving results" in runlog and
       "Target confidence level will be continuously evaluated." in runlog,
       f"{run_id} converter and calculation")
    ck("Import completed!" in (p / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (p / "export.log").read_text(encoding="utf-8-sig"),
       f"{run_id} import/export")
    log = (p / "model.log").read_text(encoding="utf-8-sig")
    ck("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2" in log and
       "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success:" in log and
       "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed:" in log and
       not re.search(r"mission (?:cancelled|failed|aborted):", log, re.I),
       f"{run_id} first-only successful two-aircraft mission")
    report = tables(read(p / "report-raw.json", native=True), "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{run_id} report table set")
    summary = rows(report["ResultSummary"])
    ck(len(summary) == 1 and all(summary[0][name] == value for name, value in
       {"NREP": 32, "RTILW": 0, "RTIUP": 36,
        "MTMF": .84375, "MSTF": .84375, "MSUF": .84375, "STMF": .84375,
        "RSMTMF": .11425267904996872, "RSMSTF": .11425267904996872,
        "RSMSUF": .11425267904996872, "RSSTMF": .11425267904996872}.items()),
       f"{run_id} summary metrics")
    system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{run_id} 72 System/Stock bins")
    for index, (sr, st) in enumerate(zip(system, stock)):
        hour = index / 2
        assigned = 3.5 if 7 <= hour < 10 else 0
        operating = 3.5 if 8 <= hour < 10 else 0
        reserved = 3.5 if 7 <= hour < 8 else 0
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": hour, "ETINT": hour + .5, "NSYRY": 12 - assigned,
                    "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                    "NSYA": 12, "FTMO": operating / 12, "STACC": operating}
        for name, value in expected.items():
            if isinstance(value, (int, float)):
                near(sr[name], value, f"{run_id} bin{index} {name}")
            else:
                ck(sr[name] == value, f"{run_id} bin{index} {name}")
        ck(all(value in (0, None) for name, value in sr.items() if name not in expected),
           f"{run_id} bin{index} other System fields")
        ck(st["STINT"] == hour and st["ETINT"] == hour + .5 and st["PNB"] == 1 and
           all(value in (0, None) for name, value in st.items()
               if name not in {"STINT", "ETINT", "PNB"}), f"{run_id} bin{index} Stock")
    hours = sum(r["NSYMO"] * .5 for r in system)
    near(hours, 7, f"{run_id} mean aircraft flight hours")
    near(sum(r["STACC"] * .5 for r in system), hours, f"{run_id} STACC aircraft hours")
    ck(system[-1]["NSYRY"] == 12 and system[-1]["NSYMA"] == 0 and stock[-1]["NBO"] == 0,
       f"{run_id} terminal twelve ready")
    return {"run_id": run_id, "calc_threads": threads,
            "input_sha256": sha(input_path), "closure_sha256": sha(p / "closure.json"),
            "report_sha256": sha(p / "report-raw.json"), "log_sha256": sha(p / "model.log"),
            "nrep": summary[0]["NREP"], "rsmtmf": summary[0]["RSMTMF"],
            "hour8_operating_aircraft": system[16]["NSYMO"],
            "average_aircraft_flight_hours": hours, "terminal_ready": system[-1]["NSYRY"]}


def diagnostic_checks(contract: dict) -> dict:
    probe = CASE / "runs" / "j04-var04-thread2-probe-20261001-01"
    first = CASE / "runs" / "j04-var04-thread2-accepted-20261001-01"
    old = CASE / "review" / "superseded-first-acceptance"
    probe_inv, probe_cl = read(probe / "invocation.json"), read(probe / "closure.json")
    first_inv, first_cl = read(first / "invocation.json"), read(first / "closure.json")
    ck(probe_inv["calc_threads"] == first_inv["calc_threads"] == 2 and
       probe_cl["state"] == first_cl["state"] == "native_steps_complete" and
       [s["name"] for s in read(probe / "steps.json")] ==
       [s["name"] for s in read(first / "steps.json")] ==
       ["import", "export", "calc", "jsonreport"],
       "excluded probe and superseded first acceptance completed native steps")
    ck(not (first / "validation.json").exists() and not (first / "run-manifest.json").exists(),
       "superseded first acceptance lacks validator/manifest")
    ck(first_cl["invocation_sha256"] == sha(first / "invocation.json") and
       probe_cl["invocation_sha256"] == sha(probe / "invocation.json"),
       "excluded closure invocation SHA bindings")
    for p, closure in ((probe, probe_cl), (first, first_cl)):
        ck(set(closure["raw"]) == RAW, f"{p.name} eleven raw seals")
        for name, meta in closure["raw"].items():
            path = p / name
            ck(path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"],
               f"{p.name} raw {name}")
    ck(first_cl["post_source_sha256"]["contract.json"] == sha(old / "contract.json") and
       first_cl["post_source_sha256"]["build.py"] == sha(old / "build.py") and
       first_cl["post_source_sha256"]["run_native_ssh.ps1"] == sha(old / "run_native_ssh.ps1") and
       first_inv["contract_sha256"] == sha(old / "contract.json") and
       first_inv["builder_sha256"] == sha(old / "build.py") and
       first_inv["runner_sha256"] == sha(old / "run_native_ssh.ps1") and
       sha(old / "contract.json") != sha(CASE / "contract.json"),
       "superseded run binds archived original source")
    ck("def table(" not in (old / "build.py").read_text(encoding="utf-8-sig") and
       "def table(" in (CASE / "build.py").read_text(encoding="utf-8-sig") and
       "build.table(" in (old / "validate.py").read_text(encoding="utf-8-sig"),
       "archived builder missing helper required by sealed validator")
    probe_fixed = {"probe-contract.json": CASE / "probe-contract.json",
                   "build.py": old / "build.py", "probe-diff.json": CASE / "probe-diff.json",
                   "probe_native_ssh.ps1": CASE / "probe_native_ssh.ps1",
                   "probe-input.json": CASE / "probe-input.json",
                   "parent-input.json": PARENT / "probe-input.json",
                   "database-dictionary.txt": Path(contract["source"]["database_dictionary"]),
                   "manual.pdf": Path(contract["source"]["manual"])}
    ck(set(probe_cl["post_source_sha256"]) == set(probe_fixed), "probe source map")
    for name, path in probe_fixed.items():
        ck(probe_cl["post_source_sha256"].get(name) == sha(path), f"probe source seal {name}")
    ck(probe_inv["runner_sha256"] == sha(CASE / "probe_native_ssh.ps1") and
       probe_inv["builder_sha256"] == sha(old / "build.py") and
       probe_inv["contract_sha256"] == sha(CASE / "probe-contract.json"),
       "probe invocation source pins")
    ck(all(sha(p / "report-raw.json") == contract["expected_observation"]["parent_report_raw_sha256"] and
           sha(p / "model.log") == contract["expected_observation"]["parent_first_replication_log_sha256"]
           for p in (probe, first)), "excluded native outputs equal parent but not accepted")
    return {"probe_run_id": probe.name, "superseded_run_id": first.name,
            "probe_closure_sha256": sha(probe / "closure.json"),
            "superseded_closure_sha256": sha(first / "closure.json"),
            "superseded_validation_and_manifest_absent": True}


def main() -> None:
    contract, diff = read(CASE / "contract.json"), read(CASE / "probe-diff.json")
    source = source_checks(contract, diff)
    expected = contract["expected_observation"]
    parent_contract = read(PARENT / "contract.json")
    parent = [replay(PARENT, rid, 1, source, parent_contract)
              for rid in expected["parent_thread_one_run_ids"]]
    child = [replay(CASE, rid, 2, source, contract) for rid in expected["run_ids"]]
    all_runs = parent + child
    ck(len({r["report_sha256"] for r in all_runs}) == 1 and
       {r["report_sha256"] for r in all_runs} == {expected["parent_report_raw_sha256"]},
       "four byte-identical native JSON reports")
    ck(len({r["log_sha256"] for r in all_runs}) == 1 and
       {r["log_sha256"] for r in all_runs} == {expected["parent_first_replication_log_sha256"]},
       "four byte-identical first-replication event logs")
    diagnostic = diagnostic_checks(contract)
    result = {"schema": "j04-var04-thread-repro-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failures": failures, "parent_one_thread_runs": parent,
              "accepted_two_thread_runs": child, "excluded_diagnostics": diagnostic,
              "raw_seal_count_four_accepted": 4 * len(RAW),
              "scope": "This seed-one model and installation produced byte-identical reports and first-only event logs in two accepted one-thread and two fresh two-thread CLI runs. All four report NREP32, RSMTMF0.114252679, seven mean aircraft flight hours, and terminal twelve ready.",
              "limits": ["The two-thread probe is diagnostic, and the first accepted-ID attempt completed native steps but lacked validation/manifest owing to a missing archived builder helper; both are excluded.",
                         "ENLOG exposes only the first replication; other thirty-one event histories and counts are unavailable.",
                         "The result does not establish general parallel determinism, scaling, other thread counts, seeds, GUI visual behavior, or cross-engine parity."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:15], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
