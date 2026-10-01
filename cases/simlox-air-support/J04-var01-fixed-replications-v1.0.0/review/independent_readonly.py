"""Independent standard-library replay of the corrected J04.var01 accepted pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "J02-var03-poisson-formation-count-v1.0.0" / "seed-01-input.json"
PARENT_LOG = (BASE / "J02-var03-poisson-formation-count-v1.0.0" / "runs" /
              "j02-var03-seed01-accepted-20261001-01" / "model.log")
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
checks = 0
failures: list[str] = []


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
    result = {table["name"]: table for table in source}
    ck(len(result) == len(source), f"unique {root} table names")
    return result


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    result = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            ck(len(values) == len(names), f"well-formed {table['name']} row")
            result.append(dict(zip(names, values)))
    return result


def near(actual: float, expected: float, label: str, tolerance: float = 4e-5) -> None:
    ck(actual is not None and abs(actual - expected) <= tolerance,
       f"{label}: {actual!r} versus {expected!r}")


def source_checks(contract: dict, difference: dict) -> dict:
    ck(sha(PARENT) == contract["parent_input_sha256"] == difference["parent_input_sha256"],
       "accepted J02.var03 seed-one parent SHA")
    source_path = CASE / "probe-input.json"
    ck(sha(source_path) == contract["input_sha256"] == difference["input_sha256"] and
       sha(CASE / "probe-diff.json") == contract["exact_diff_sha256"],
       "frozen input/exact-diff SHAs")
    for file_path, expected in ((Path(contract["source"]["manual"]),
                                 contract["source"]["manual_sha256"]),
                                (Path(contract["source"]["database_dictionary"]),
                                 contract["source"]["database_dictionary_sha256"])):
        ck(sha(file_path) == expected, f"installed source {file_path.name} pin")
    executable_sha = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
    ck(sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")) == executable_sha and
       executable_sha in (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig"),
       "installed executable/frozen runner pin")
    expected = contract["expected_observation"]
    ck(expected["run_ids"] == [f"j04-var01-fixed-reps-accepted-20261001-{number:02d}"
                               for number in (3, 4)] and
       expected["nrep"] == 16 and expected["seed"] == "1" and expected["tclev"] == 0 and
       expected["average_operating_aircraft_at_hour_8"] == 3.125 and
       expected["inferred_average_two_aircraft_formations_at_hour_8"] == 1.5625,
       "corrected predeclared accepted IDs and aircraft/formation units")
    parent, child = tables(read(PARENT), "model"), tables(read(source_path), "model")
    changed = {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}
    ck(changed == {"Control"} == {difference["changed_table"]}, "only Control table changes")
    ck(child["Control"]["columns"] == parent["Control"]["columns"] and
       [x["instance_name"] for x in child["Control"]["instances"]] ==
       [x["instance_name"] for x in parent["Control"]["instances"]],
       "Control schema and instance preserved")
    before, after = rows(parent["Control"]), rows(child["Control"])
    ck(before == difference["before"] and after == difference["after"],
       "exact declared Control row delta")
    changed_fields = {name for name in before[0] if before[0][name] != after[0][name]}
    ck(changed_fields == {"NREPS", "TCLEV"} and before[0]["NREPS"] == 1 and
       after[0]["NREPS"] == 16 and before[0]["TCLEV"] is None and
       after[0]["TCLEV"] == 0 and after[0]["RSEED"] == "1" and
       after[0]["ENLOG"] == "Y", "NREP16/TCLEV0 source semantics")
    ck(len([table for table in child.values() if any(i["rows"] for i in table["instances"])]) == 14,
       "fourteen populated source tables")
    formation = rows(child["MissionType"])
    ck(len(formation) == 1 and formation[0]["NOS"] == formation[0]["MNOS"] == 2 and
       formation[0]["DURN"] == 2, "two-aircraft two-hour formation source")
    return child


def replay(run_id: str, document: dict, contract: dict) -> dict:
    path = CASE / "runs" / run_id
    invocation, closure, steps = (read(path / name) for name in
                                  ("invocation.json", "closure.json", "steps.json"))
    source_path = CASE / "probe-input.json"
    ck(invocation["run_id"] == closure["run_id"] == run_id and
       invocation["input_sha256"] == closure["input_sha256"] == sha(source_path) and
       closure["invocation_sha256"] == sha(path / "invocation.json") and
       closure["state"] == "native_steps_complete", f"{run_id} invocation/closure")
    manifest = read(path / "run-manifest.json")
    ck(manifest["case_id"] == "J04" and manifest["variant_id"] == "J04.var01" and
       manifest["version"] == "1.0.0" and manifest["run_id"] == run_id and
       manifest["input_sha256"] == sha(source_path) and
       manifest["closure_sha256"] == sha(path / "closure.json") and
       manifest["validation_sha256"] == sha(path / "validation.json") and
       manifest["execution_mode"] == "ssh_cli_v1", f"{run_id} manifest reconciliation")
    fixed = {"contract.json": CASE / "contract.json", "build.py": CASE / "build.py",
             "probe-diff.json": CASE / "probe-diff.json",
             "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
             "validate.py": CASE / "validate.py", "validate_pair.py": CASE / "validate_pair.py",
             "probe-input.json": source_path, "parent-input.json": PARENT,
             "database-dictionary.txt": Path(contract["source"]["database_dictionary"]),
             "manual.pdf": Path(contract["source"]["manual"])}
    ck(set(closure["post_source_sha256"]) == set(fixed), f"{run_id} full source map")
    for name, file_path in fixed.items():
        ck(closure["post_source_sha256"].get(name) == sha(file_path),
           f"{run_id} source seal {name}")
    for name, file_path in (("contract_sha256", CASE / "contract.json"),
                            ("builder_sha256", CASE / "build.py"),
                            ("validator_sha256", CASE / "validate.py"),
                            ("pair_validator_sha256", CASE / "validate_pair.py"),
                            ("runner_sha256", CASE / "run_native_ssh.ps1")):
        ck(invocation[name] == sha(file_path), f"{run_id} invocation {name}")
    ck(set(closure["raw"]) == RAW, f"{run_id} eleven sealed raw files")
    for name, metadata in closure["raw"].items():
        file_path = path / name
        ck(file_path.is_file() and file_path.stat().st_size == metadata["bytes"] and
           sha(file_path) == metadata["sha256"], f"{run_id} raw seal {name}")
    ck(sha(path / "input.json") == sha(source_path), f"{run_id} raw input copy")
    ck(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
       invocation["gui_pid"] == 13340 and
       invocation["gui_start_utc"] == "2026-09-28T10:09:56.8261381Z",
       f"{run_id} session-zero SSH/GUI/mutex")
    ck([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"] and
       all(step["exit_code"] == 0 and step["coexisting_gui_present_after"] for step in steps),
       f"{run_id} four guarded native steps")
    ck((path / "model.sxo").stat().st_size > 4, f"{run_id} valid SXO")
    exported = tables(read(path / "roundtrip-raw.json", native=True), "model")
    populated = [name for name, table in document.items() if any(i["rows"] for i in table["instances"])]
    ck(len(populated) == 14, f"{run_id} fourteen populated business tables")
    for name in populated:
        ck(exported.get(name) == document[name], f"{run_id} exact native row roundtrip {name}")
    runlog = (path / "run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog and
       sorted(re.findall(r"warning #(\d+)", runlog)) == ["108", "126", "211"] and
       not re.search(r"error #\d+", runlog, re.I) and "Saving results" in runlog,
       f"{run_id} converter and calculation")
    ck("Import completed!" in (path / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (path / "export.log").read_text(encoding="utf-8-sig"),
       f"{run_id} import/export complete")
    log = (path / "model.log").read_text(encoding="utf-8-sig")
    ck(sha(path / "model.log") == sha(PARENT_LOG),
       f"{run_id} first-replication ENLOG byte equality to accepted parent")
    identity = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
    ck(len(re.findall(r"^Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION$", log, re.M)) == 1 and
       len(re.findall(r"^Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission activated, systems requested: 2$",
                      log, re.M)) == 1 and
       f"Time: 8 {identity} mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log and
       f"Time: 10 {identity} mission success:" in log and
       f"Time: 10 {identity} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log and
       not re.search(r"mission (?:cancelled|aborted|failed):", log, re.I),
       f"{run_id} first-replication one successful two-aircraft mission")
    report = tables(read(path / "report-raw.json", native=True), "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{run_id} native report tables")
    summary = rows(report["ResultSummary"])
    ck(len(summary) == 1 and all(summary[0][name] == value for name, value in
       {"NREP": 16, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "MSTF": 1,
        "MSUF": 1, "STMF": 1, "RSMTMF": 0, "RSMSTF": 0,
        "RSMSUF": 0, "RSSTMF": 0}.items()), f"{run_id} NREP16 summary/relative errors")
    system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{run_id} 72 System/Stock bins")
    operating_aircraft = contract["expected_observation"]["average_operating_aircraft_at_hour_8"]
    near(operating_aircraft / 2,
         contract["expected_observation"]["inferred_average_two_aircraft_formations_at_hour_8"],
         f"{run_id} average formation inference from two aircraft")
    for index, (sr, st) in enumerate(zip(system, stock)):
        hour = index / 2
        assigned = operating_aircraft if 7 <= hour < 10 else 0
        operating = operating_aircraft if 8 <= hour < 10 else 0
        reserved = operating_aircraft if 7 <= hour < 8 else 0
        fields = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                  "STINT": hour, "ETINT": hour + .5, "NSYRY": 12 - assigned,
                  "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                  "NSYA": 12, "FTMO": operating / 12, "STACC": operating}
        for name, value in fields.items():
            if isinstance(value, (int, float)):
                near(sr[name], value, f"{run_id} bin {index} {name}")
            else:
                ck(sr[name] == value, f"{run_id} bin {index} {name}")
        ck(all(value in (0, None) for name, value in sr.items() if name not in fields),
           f"{run_id} bin {index} other System fields")
        ck(st["STINT"] == hour and st["ETINT"] == hour + .5 and st["PNB"] == 1 and
           all(value in (0, None) for name, value in st.items()
               if name not in {"STINT", "ETINT", "PNB"}),
           f"{run_id} bin {index} Stock ledger")
    aircraft_hours = sum(row["NSYMO"] * .5 for row in system)
    near(aircraft_hours, contract["expected_observation"]["average_aircraft_flight_hours"],
         f"{run_id} mean aircraft flight hours")
    near(sum(row["STACC"] * .5 for row in system), aircraft_hours,
         f"{run_id} STACC aircraft flight hours")
    ck(system[-1]["NSYRY"] == 12 and system[-1]["NSYMA"] == 0 and
       stock[-1]["NBO"] == 0, f"{run_id} terminal twelve ready")
    return {"run_id": run_id, "input_sha256": sha(source_path),
            "closure_sha256": sha(path / "closure.json"),
            "log_sha256": sha(path / "model.log"), "report_sha256": sha(path / "report-raw.json"),
            "nrep": summary[0]["NREP"], "hour8_operating_aircraft": system[16]["NSYMO"],
            "inferred_hour8_two_aircraft_formations": system[16]["NSYMO"] / 2,
            "average_aircraft_flight_hours": aircraft_hours,
            "terminal_ready": system[-1]["NSYRY"]}


def main() -> None:
    contract, difference = read(CASE / "contract.json"), read(CASE / "probe-diff.json")
    document = source_checks(contract, difference)
    accepted_ids = contract["expected_observation"]["run_ids"]
    runs = [replay(run_id, document, contract) for run_id in accepted_ids]
    ck(runs[0]["log_sha256"] == runs[1]["log_sha256"] and
       runs[0]["report_sha256"] == runs[1]["report_sha256"],
       "fresh accepted pair byte-identical first-rep logs and native reports")
    probe1 = CASE / "runs" / "j04-var01-fixed-reps-probe-20261001-01"
    probe2 = CASE / "runs" / "j04-var01-fixed-reps-probe-20261001-02"
    old_runner = CASE / "review" / "probe_native_ssh_unsealed_initial.ps1"
    probe1_invocation = read(probe1 / "invocation.json")
    probe1_steps = read(probe1 / "steps.json")
    ck(not (probe1 / "closure.json").exists() and
       probe1_invocation["runner_sha256"] == sha(old_runner) and
       [step["name"] for step in probe1_steps] == ["import", "export", "calc", "jsonreport"] and
       all(step["exit_code"] == 0 for step in probe1_steps) and
       "$input" in old_runner.read_text(encoding="utf-8-sig"),
       "excluded first probe native-complete but unsealed runner diagnostic")
    old_contract = CASE / "review" / "superseded-first-acceptance" / "contract.json"
    old_ids = [f"j04-var01-fixed-reps-accepted-20261001-{number:02d}" for number in (1, 2)]
    ck((probe2 / "closure.json").exists() and
       read(probe2 / "closure.json")["state"] == "native_steps_complete" and
       all(read(CASE / "runs" / run_id / "closure.json")["post_source_sha256"]["contract.json"] ==
           sha(old_contract) != sha(CASE / "contract.json") for run_id in old_ids),
       "corrected diagnostic and superseded first accepted pair retained, excluded")
    result = {"schema": "j04-var01-fixed-replications-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failures": failures, "accepted_run_count": len(runs),
              "raw_seal_count": len(runs) * len(RAW), "accepted_runs": runs,
              "populated_source_table_count": 14,
              "scope": "Two fresh corrected-source session-zero CLI runs report NREP16, byte-identical aggregate native reports and first-replication logs, mean 3.125 operating aircraft (inferred 1.5625 two-aircraft formations) at hour 8, and 6.25 mean aircraft flight hours.",
              "limits": ["The first probe and second probe are diagnostics; accepted IDs 01/02 are superseded by the corrected contract and excluded.",
                         "ENLOG exposes only the first replication; aggregate averages do not reveal the other fifteen mission counts or event timelines.",
                         "RSMTMF zero at MTMF one does not estimate mission-count variance or prove a population law.",
                         "TCLEV above zero, nonconvergent NREPS stopping, thread changes, GUI visual behavior, and cross-engine parity remain untested."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
