"""Independent stdlib replay of J04.var02 sealed CLI evidence; never runs SIMLOX."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "J04-var01-fixed-replications-v1.0.0" / "probe-input.json"
PARENT_LOG = (BASE / "J04-var01-fixed-replications-v1.0.0" / "runs" /
              "j04-var01-fixed-reps-accepted-20261001-03" / "model.log")
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
failures: list[str] = []
count = 0


def ck(ok: bool, label: str) -> None:
    global count
    count += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False) -> dict:
    value = path.read_text(encoding="utf-8-sig")
    if native:
        value = re.sub(r",\s*([}\]])", r"\1", value)
    return json.loads(value)


def tables(document: dict, root: str) -> dict:
    values = document[root]["tables"]
    result = {table["name"]: table for table in values}
    ck(len(result) == len(values), f"unique {root} table names")
    return result


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    result = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            ck(len(values) == len(names), f"well-formed {table['name']} row")
            result.append(dict(zip(names, values)))
    return result


def near(actual: float, expected: float, label: str, tolerance: float = 5e-5) -> None:
    ck(actual is not None and abs(actual - expected) <= tolerance,
       f"{label}: {actual!r} versus {expected!r}")


def source_case(stem: str, nreps: int, tclev: float, contract_name: str, diff_name: str) -> dict:
    source = CASE / f"{stem}-input.json"
    contract, diff = read(CASE / contract_name), read(CASE / diff_name)
    source_hash = sha(source)
    ck(source_hash == diff["input_sha256"] == contract.get("input_sha256", contract.get("probe_input_sha256")),
       f"{stem} input SHA")
    ck(sha(CASE / diff_name) == contract.get("exact_diff_sha256", contract.get("probe_diff_sha256")),
       f"{stem} diff SHA")
    ck(sha(PARENT) == diff["parent_input_sha256"] == contract["parent_input_sha256"],
       f"{stem} accepted parent SHA")
    before, after = tables(read(PARENT), "model"), tables(read(source), "model")
    ck({name for name in before.keys() | after.keys() if before.get(name) != after.get(name)} == {"Control"},
       f"{stem} Control-only table delta")
    ck(before["Control"]["columns"] == after["Control"]["columns"] and
       [i["instance_name"] for i in before["Control"]["instances"]] ==
       [i["instance_name"] for i in after["Control"]["instances"]],
       f"{stem} Control shape")
    old, new = rows(before["Control"]), rows(after["Control"])
    ck(old == diff["before"] and new == diff["after"], f"{stem} exact declared row diff")
    ck(len(old) == len(new) == 1 and
       {name for name in old[0] if old[0][name] != new[0][name]} == {"NREPS", "TCLEV"} and
       old[0]["NREPS"] == 16 and old[0]["TCLEV"] == 0 and
       new[0]["NREPS"] == nreps and new[0]["TCLEV"] == tclev and
       new[0]["RSEED"] == "1" and new[0]["ENLOG"] == "Y",
       f"{stem} exact Control field changes")
    ck(len([t for t in after.values() if any(i["rows"] for i in t["instances"])]) == 14,
       f"{stem} fourteen populated business tables")
    return after


def replay(run_id: str, stem: str, document: dict, expected_nrep: int,
           expected_error: float, expected_aircraft: float, accepted: bool) -> dict:
    p = CASE / "runs" / run_id
    invocation, closure, steps = [read(p / name) for name in
                                  ("invocation.json", "closure.json", "steps.json")]
    source = CASE / f"{stem}-input.json"
    ck(invocation["run_id"] == closure["run_id"] == run_id and
       invocation["input_sha256"] == closure["input_sha256"] == sha(source) and
       closure["invocation_sha256"] == sha(p / "invocation.json") and
       closure["state"] == "native_steps_complete", f"{run_id} closure binding")
    suffix = stem.removeprefix("probe")
    contract_name = "contract.json" if accepted else (f"probe{suffix}-contract.json" if suffix else "probe-contract.json")
    diff_name = f"{stem}-diff.json"
    runner_name = "run_native_ssh.ps1" if accepted else (f"probe{suffix}_native_ssh.ps1" if suffix else "probe_native_ssh.ps1")
    builder_name = "build_256.py" if accepted else (f"build_{suffix}.py" if suffix else "build.py")
    fixed = {contract_name: CASE / contract_name, builder_name: CASE / builder_name,
             diff_name: CASE / diff_name, runner_name: CASE / runner_name,
             f"{stem}-input.json": source, "parent-input.json": PARENT,
             "database-dictionary.txt": Path(read(CASE / "contract.json")["source"]["database_dictionary"]),
             "manual.pdf": Path(read(CASE / "contract.json")["source"]["manual"])}
    if accepted:
        fixed.update({"validate.py": CASE / "validate.py", "validate_pair.py": CASE / "validate_pair.py"})
    ck(set(closure["post_source_sha256"]) == set(fixed), f"{run_id} source map")
    for name, path in fixed.items():
        ck(closure["post_source_sha256"].get(name) == sha(path), f"{run_id} source seal {name}")
    for key, path in {"contract_sha256": fixed[contract_name], "builder_sha256": fixed[builder_name],
                      "runner_sha256": fixed[runner_name]}.items():
        ck(invocation[key] == sha(path), f"{run_id} invocation {key}")
    if accepted:
        ck(invocation["validator_sha256"] == sha(CASE / "validate.py") and
           invocation["pair_validator_sha256"] == sha(CASE / "validate_pair.py"),
           f"{run_id} validator source binding only")
        manifest = read(p / "run-manifest.json")
        ck(manifest["run_id"] == run_id and manifest["input_sha256"] == sha(source) and
           manifest["closure_sha256"] == sha(p / "closure.json") and
           manifest["validation_sha256"] == sha(p / "validation.json") and
           manifest["execution_mode"] == "ssh_cli_v1", f"{run_id} manifest binding")
    ck(set(closure["raw"]) == RAW, f"{run_id} eleven raw seals")
    for name, meta in closure["raw"].items():
        path = p / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"],
           f"{run_id} raw {name}")
    ck(sha(p / "input.json") == sha(source), f"{run_id} raw input copy")
    ck(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
       invocation["gui_pid"] == 13340 and
       invocation["gui_start_utc"] == "2026-09-28T10:09:56.8261381Z",
       f"{run_id} SSH/mutex/GUI identity")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport"] and
       all(s["exit_code"] == 0 and s["coexisting_gui_present_after"] for s in steps),
       f"{run_id} four native steps")
    ck((p / "model.sxo").stat().st_size > 4, f"{run_id} valid SXO")
    exported = tables(read(p / "roundtrip-raw.json", native=True), "model")
    for name, table in document.items():
        if any(i["rows"] for i in table["instances"]):
            ck(exported.get(name) == table, f"{run_id} exact business roundtrip {name}")
    runlog = (p / "run.log").read_text(encoding="utf-8-sig")
    warnings = sorted(re.findall(r"warning #(\d+)", runlog))
    expected_warnings = ["108", "126", "211"] if stem != "probe030" else ["104", "108", "126", "211"]
    ck(warnings == expected_warnings and
       f"Errors: 0, Warnings: {len(expected_warnings)}, Notes: 0" in runlog and
       "Target confidence level will be continuously evaluated." in runlog and
       "Saving results" in runlog and not re.search(r"error #\d+", runlog, re.I),
       f"{run_id} converter/calculation diagnostics")
    ck("Import completed!" in (p / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (p / "export.log").read_text(encoding="utf-8-sig"),
       f"{run_id} import/export")
    ck(sha(p / "model.log") == sha(PARENT_LOG), f"{run_id} first-only ENLOG parent equality")
    log = (p / "model.log").read_text(encoding="utf-8-sig")
    ck("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2" in log and
       "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success:" in log and
       "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed:" in log and
       not re.search(r"mission (?:cancelled|failed|aborted):", log, re.I),
       f"{run_id} first-rep successful mission")
    report = tables(read(p / "report-raw.json", native=True), "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{run_id} report tables")
    summary = rows(report["ResultSummary"])
    ck(len(summary) == 1 and summary[0]["NREP"] == expected_nrep and
       summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36,
       f"{run_id} actual replication count and horizon")
    for field in ("MTMF", "MSTF", "MSUF", "STMF"):
        near(summary[0][field], expected_error[0], f"{run_id} {field}")
    for field in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF"):
        near(summary[0][field], expected_error[1], f"{run_id} {field}")
    system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{run_id} 72 System/Stock bins")
    for index, (sr, st) in enumerate(zip(system, stock)):
        hour = index / 2
        assigned = expected_aircraft if 7 <= hour < 10 else 0
        operating = expected_aircraft if 8 <= hour < 10 else 0
        reserved = expected_aircraft if 7 <= hour < 8 else 0
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
    hours = sum(row["NSYMO"] * .5 for row in system)
    near(hours, 2 * expected_aircraft, f"{run_id} mean aircraft flight hours")
    near(sum(row["STACC"] * .5 for row in system), hours,
         f"{run_id} STACC aircraft-hours")
    ck(system[-1]["NSYRY"] == 12 and system[-1]["NSYMA"] == 0 and
       stock[-1]["NBO"] == 0, f"{run_id} terminal twelve ready")
    return {"run_id": run_id, "source_sha256": sha(source), "closure_sha256": sha(p / "closure.json"),
            "log_sha256": sha(p / "model.log"), "report_sha256": sha(p / "report-raw.json"),
            "actual_nrep": summary[0]["NREP"], "rsmtmf": summary[0]["RSMTMF"],
            "hour8_operating_aircraft": system[16]["NSYMO"],
            "mean_aircraft_flight_hours": hours, "terminal_ready_aircraft": system[-1]["NSYRY"]}


def main() -> None:
    contract = read(CASE / "contract.json")
    ck(sha(Path(contract["source"]["manual"])) == contract["source"]["manual_sha256"],
       "installed manual SHA")
    ck(sha(Path(contract["source"]["database_dictionary"])) ==
       contract["source"]["database_dictionary_sha256"], "installed dictionary SHA")
    ck(sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")) ==
       "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
       "installed executable SHA")
    ck("fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0" in
       (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig"), "runner executable pin")
    ck(contract["expected_observation"]["run_ids"] ==
       [f"j04-var02-confidence-stop-accepted-20261001-{i:02d}" for i in (1, 2)],
       "predeclared accepted IDs")
    diagnostic = []
    for stem, run_id, nreps, level, actual, relative, aircraft, mtmf in [
        ("probe", "j04-var02-confidence-stop-probe-20261001-01", 32, .01, 32,
         .11425267904996872, 3.5, .84375),
        ("probe009", "j04-var02-confidence-stop-009-probe-20261001-01", 32, .09, 32,
         .11425267904996872, 3.5, .84375),
        ("probe030", "j04-var02-confidence-stop-030-probe-20261001-01", 32, .3, 19,
         .15095184743404388, 3.1578948497772217, .8421052694320679),
        ("probe256", "j04-var02-confidence-stop-256-probe-20261001-01", 256, .09, 81,
         .07954545319080353, 3.209876537322998, .8148148059844971),
    ]:
        d = source_case(stem, nreps, level,
                        f"{stem}-contract.json" if stem != "probe" else "probe-contract.json",
                        f"{stem}-diff.json")
        diagnostic.append(replay(run_id, stem, d, actual, (mtmf, relative), aircraft, False))
    document = source_case("probe256", 256, .09, "contract.json", "probe256-diff.json")
    accepted = [replay(run_id, "probe256", document, 81,
                       (.8148148059844971, .07954545319080353),
                       3.209876537322998, True)
                for run_id in contract["expected_observation"]["run_ids"]]
    ck(accepted[0]["log_sha256"] == accepted[1]["log_sha256"] and
       accepted[0]["report_sha256"] == accepted[1]["report_sha256"],
       "accepted pair byte-identical log/report")
    ck(accepted[0]["report_sha256"] == diagnostic[-1]["report_sha256"] and
       accepted[0]["log_sha256"] == diagnostic[-1]["log_sha256"],
       "accepted same-source diagnostic semantic repeat")
    ck(accepted[0]["actual_nrep"] < 256 and accepted[0]["rsmtmf"] < .09,
       "observed below cap and final error below target")
    result = {"schema": "j04-var02-confidence-stop-independent-readonly/v1",
              "case": CASE.name, "passed": not failures, "verdict": "GO" if not failures else "NO-GO",
              "check_count": count, "failures": failures,
              "accepted_runs": accepted, "excluded_diagnostics": diagnostic,
              "accepted_raw_seal_count": 2 * len(RAW),
              "scope": "Two fresh sealed CLI runs with NREPS256/TCLEV0.09 each report NREP81 and final RSMTMF0.07954545; 72-bin mean aircraft and stock ledgers reconcile and the pair repeats exactly.",
              "limits": ["The three cap32 thresholds and same-input cap256 precursor are excluded diagnostics.",
                         "The rolling ten-replication condition cannot be checked directly from aggregate reports or first-only ENLOG; early stopping is observed and consistent with the manual rule.",
                         "Other eighty accepted replication mission histories, precision of all metrics, other seeds, GUI visual behavior, and cross-engine parity remain unobserved."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "check_count": count,
                      "failures": failures[:15], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
