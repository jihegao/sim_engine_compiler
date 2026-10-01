"""Independent standard-library raw replay for G02.var01; never invokes SIMLOX."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
RAW = {"report-export.log", "roundtrip-validation.json", "import.log", "model.log",
       "model.sxo", "run.log", "report-raw.json", "roundtrip-raw.json", "input.json",
       "export.log", "model.sxi", "steps.json"}
failures: list[str] = []
checks = 0


def ck(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False) -> dict:
    data = path.read_text(encoding="utf-8-sig")
    if native:
        data = re.sub(r",\s*([}\]])", r"\1", data)
    return json.loads(data)


def tables(doc: dict, root: str) -> dict:
    source = doc[root]["tables"]
    result = {t["name"]: t for t in source}
    ck(len(result) == len(source), f"unique {root} table names")
    return result


def rows(table: dict) -> list[dict]:
    cols = [c["name"] for c in table["columns"]]
    result = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            ck(len(cols) == len(row), f"well-formed {table['name']} row")
            result.append(dict(zip(cols, row)))
    return result


def near(value: float, expected: float, label: str, tolerance: float = 2e-4) -> None:
    ck(value is not None and abs(value - expected) <= tolerance,
       f"{label}: {value!r} versus {expected!r}")


def overlap(start: float, end: float, left: float, right: float) -> float:
    return max(0.0, min(end, right) - max(start, left)) / (right - left)


def source_checks(contract: dict, diff: dict) -> dict:
    source_path = CASE / "native-input.json"
    ck(sha(PARENT) == contract["parent"]["input_sha256"] == diff["parent_input_sha256"],
       "accepted D06 parent fingerprint")
    ck(sha(source_path) == contract["input_sha256"] == diff["candidate_input_sha256"],
       "frozen G02 child input fingerprint")
    ck(sha(MANUAL) == contract["source"]["manual_sha256"] and
       sha(DICTIONARY) == contract["source"]["dictionary_sha256"] and
       sha(EXE) == contract["source"]["exe_sha256"],
       "installed manual/dictionary/executable fingerprints")
    parent, child = tables(read(PARENT), "model"), tables(read(source_path), "model")
    changed = {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}
    ck(changed == set(diff["changed_tables"]) ==
       {"ProblemDescription", "FailureMode", "CMLocation"}, "exact three-table delta")
    for name in changed:
        ck(parent[name]["columns"] == child[name]["columns"] and
           [i["instance_name"] for i in parent[name]["instances"]] ==
           [i["instance_name"] for i in child[name]["instances"]],
           f"{name} schema and instance preserved")
    pf, cf = parent["FailureMode"]["instances"][0]["rows"], child["FailureMode"]["instances"][0]["rows"]
    pc, cc = parent["CMLocation"]["instances"][0]["rows"], child["CMLocation"]["instances"][0]["rows"]
    ck(cf == pf + [diff["added_failure_mode"]] and cc == pc + [diff["added_cm_location"]],
       "exact appended FM-POS-B and local CM rows")
    ck(pf[0][0] == "FM-POS-A" and pf[0][2] == "POS-A" and pf[0][3] == 300000 and
       cf[-1][0] == "FM-POS-B" and cf[-1][2] == "POS-B" and cf[-1][3] == 600000 and
       cc[-1][:4] == ["FM-POS-B", "TEACH-AIR-01", "BASE-01", .5],
       "position-specific rates and half-hour local CM")
    ck(len(parent["ProblemDescription"]["instances"][0]["rows"]) ==
       len(child["ProblemDescription"]["instances"][0]["rows"]) == 1 and
       parent["ProblemDescription"]["instances"][0]["rows"] !=
       child["ProblemDescription"]["instances"][0]["rows"],
       "provenance description changed")
    ck(len([t for t in child.values() if any(i["rows"] for i in t["instances"])]) == 18,
       "eighteen populated business tables")
    ck([r[0] for r in child["MaterielPosition"]["instances"][0]["rows"]] ==
       ["POS-A", "POS-B"] and
       len(child["MaterielStructure"]["instances"][0]["rows"]) == 4,
       "two installed position topology")
    return child


def event_checks(run_id: str, log: str) -> list[dict]:
    waves = [(0, 7.0, 8.0, 8.62763, 9.12763, 9.62763, "B"),
             (1, 19.0, 20.0, 20.8222, 21.3222, 21.8222, "B"),
             (2, 31.0, 32.0, 33.0996, 33.5996, 34.0996, "A")]
    ck(len(re.findall(r"critical CM failure mode added", log)) == 3 and
       len(re.findall(r"mission aborted:", log)) == 3 and
       len(re.findall(r"aborted mission completed:", log)) == 3 and
       not re.search(r"mission success:|stock demand|replacement", log, re.I),
       f"{run_id} exactly three failures/aborts and no stock/replacement")
    results = []
    for mid, order, launch, failure, returned, repaired, position in waves:
        identity = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
        fm = f"FM-POS-{position}"
        ck(f"Time: {order:g} <TEACH-UNIT> mission ordered: BASIC-MISSION" in log and
           f"Time: {order:g} {identity} mission created:" in log and
           f"Time: {order:g} {identity} mission allocates system: <TEACH-AIR-01,0>" in log and
           f"Time: {launch:g} {identity} mission starting, duration: 2 : <TEACH-AIR-01,0>" in log,
           f"{run_id} mission {mid} allocation/launch")
        ck(f"Time: {failure:g} <TEACH-AIR-01,0> critical CM failure mode added" in log and
           f"Failure Mode: {fm} on materiel: <POS-{position},0>" in log and
           f"Time: {failure:g} {identity} mission aborted:" in log,
           f"{run_id} mission {mid} failure position attribution")
        ck(f"Time: {returned:g} {identity} aborted mission completed:" in log and
           f"Time: {returned:g} <TEACH-AIR-01,BASE-01,0> System arrives" in log and
           f"Time: {returned:g}  system CM task {mid} on <TEACH-AIR-01,0> FMID: {fm}" in log and
           f"Time: {returned:g}  subtask {mid} seqno 0 within system CM task {mid} on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in log and
           f"Time: {repaired:g}  system CM task {mid} on <TEACH-AIR-01,0> completed" in log and
           f"Time: {repaired:g} <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log,
           f"{run_id} mission {mid} return/CM/recovery")
        near(returned - failure, .5, f"{run_id} mission {mid} abort-to-return", 1e-5)
        near(repaired - returned, .5, f"{run_id} mission {mid} CM duration", 1e-5)
        results.append({"mission_id": mid, "position": position, "fmid": fm,
                        "failure_hour": failure, "return_hour": returned,
                        "repair_end_hour": repaired})
    return results


def report_checks(run_id: str, report: dict) -> dict:
    t = tables(report, "report")
    ck(set(t) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{run_id} report table set")
    summary = rows(t["ResultSummary"])
    ck(len(summary) == 1 and summary[0]["NREP"] == 1 and
       summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36 and
       summary[0]["MSTF"] == 1 and summary[0]["MSUF"] == 0 and
       summary[0]["MTMF"] == summary[0]["STMF"] and
       all(summary[0][n] == 0 for n in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
       f"{run_id} one-replication summary")
    near(summary[0]["MTMF"], .6748974919319153, f"{run_id} MTMF")
    system, stock = rows(t["SystemResults"]), rows(t["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{run_id} 72 System/Stock bins")
    waves = [(7, 8, 8.62763, 9.12763, 9.62763),
             (19, 20, 20.8222, 21.3222, 21.8222),
             (31, 32, 33.0996, 33.5996, 34.0996)]
    for index, (sr, st) in enumerate(zip(system, stock)):
        left, right = index / 2, (index + 1) / 2
        assigned = sum(overlap(order, returned, left, right) for order, _, _, returned, _ in waves)
        operating = sum(overlap(launch, returned, left, right) for _, launch, _, returned, _ in waves)
        reserved = sum(overlap(order, launch, left, right) for order, launch, _, _, _ in waves)
        repair = sum(overlap(returned, repaired, left, right) for _, _, _, returned, repaired in waves)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": left, "ETINT": right, "NSYRY": 1 - assigned - repair,
                    "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                    "NSYUA": repair, "NSYA": 1 - repair, "FTMO": operating,
                    "NSYRP": repair, "STACC": operating,
                    "NFAIL": sum(left <= failure < right for _, _, failure, _, _ in waves),
                    "NREPT": sum(left <= repaired < right for _, _, _, _, repaired in waves),
                    "NSYDT": sum(left <= returned < right for _, _, _, returned, _ in waves),
                    "SYDT": .5 if any(left <= returned < right for _, _, _, returned, _ in waves) else None}
        for field, value in expected.items():
            if isinstance(value, (int, float)):
                near(sr[field], value, f"{run_id} bin {index} {field}")
            else:
                ck(sr[field] == value, f"{run_id} bin {index} {field}")
        ck(all(value in (0, None) for field, value in sr.items() if field not in expected),
           f"{run_id} bin {index} other System fields")
        ck(st["STINT"] == left and st["ETINT"] == right and st["PNB"] == 1 and
           all(value in (0, None) for field, value in st.items()
               if field not in {"STINT", "ETINT", "PNB"}),
           f"{run_id} bin {index} Stock ledger")
    near(sum(r["NSYMO"] * .5 for r in system),
         sum(r - launch for _, launch, _, r, _ in waves),
         f"{run_id} integrated flight hours", 1e-4)
    near(sum(r["NSYRP"] * .5 for r in system), 1.5,
         f"{run_id} integrated direct-CM hours", 1e-4)
    ck(system[-1]["NSYRY"] == 1 and system[-1]["NSYMA"] == 0 and
       stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       f"{run_id} terminal aircraft ready and unchanged stock")
    return {"nrep": summary[0]["NREP"], "mtmf": summary[0]["MTMF"],
            "failure_count": int(sum(r["NFAIL"] for r in system)),
            "repair_count": int(sum(r["NREPT"] for r in system)),
            "terminal_ready": system[-1]["NSYRY"]}


def replay(run_id: str, source: dict, contract: dict, accepted: bool) -> dict:
    p = CASE / "runs" / run_id
    invocation, closure, steps = (read(p / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck(invocation["run_id"] == closure["run_id"] == run_id and
       invocation["input_sha256"] == sha(CASE / "native-input.json") and
       invocation["parent_sha256"] == sha(PARENT) and
       closure["invocation_sha256"] == sha(p / "invocation.json") and
       closure["error"] is None and closure["scope"] == "four_step_native_candidate",
       f"{run_id} invocation/closure")
    sources = {"input": CASE / "native-input.json", "parent": PARENT, "manual": MANUAL,
               "dictionary": DICTIONARY, "contract": CASE / "contract.json",
               "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
               "python": PYTHON, "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": EXE}
    ck(closure["source_hashes_before"] == closure["source_hashes_after"] and
       set(closure["source_hashes_before"]) == set(sources),
       f"{run_id} frozen source map")
    for name, path in sources.items():
        value = sha(path)
        ck(invocation.get({"input": "input_sha256", "parent": "parent_sha256",
                            "contract": "contract_sha256", "builder": "builder_sha256",
                            "checker": "checker_sha256", "python": "python_sha256",
                            "runner_script": "runner_script_sha256", "simlox_exe": "simlox_exe_sha256"}.get(name, ""), value) == value and
           closure["source_hashes_before"][name] == value,
           f"{run_id} source/invocation seal {name}")
    ck(set(closure["raw"]) == RAW, f"{run_id} twelve raw seals")
    for name, meta in closure["raw"].items():
        path = p / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"],
           f"{run_id} raw {name}")
    ck(sha(p / "input.json") == sha(CASE / "native-input.json") and
       (p / "model.sxi").stat().st_size > 4 and (p / "model.sxo").stat().st_size > 4,
       f"{run_id} input copy/valid SXI/SXO")
    ck(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
       "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
       invocation["gui"] == {"pid": 13340, "session_id": 1,
                             "start_utc": "2026-09-28T10:09:56.8261381Z"},
       f"{run_id} SSH/mutex/GUI guard")
    ck([s["name"] for s in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(s["exit_code"] == 0 and s["gui_preserved"] and s["status"] == "completed" for s in steps) and
       "-threads 1 -calc" in steps[2]["arguments"], f"{run_id} guarded native and checker steps")
    ck([x["name"] for x in invocation["planned_commands"]] ==
       ["import", "export", "calc", "jsonreport"] and
       "-threads 1 -calc" in invocation["planned_commands"][2]["arguments"],
       f"{run_id} planned command binding")
    exported = tables(read(p / "roundtrip-raw.json", native=True), "model")
    for name, table in source.items():
        if any(i["rows"] for i in table["instances"]):
            ck(exported.get(name) == table, f"{run_id} exact native roundtrip {name}")
    runlog = (p / "run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       re.findall(r"warning #(\d+)", runlog) == ["108"] and
       not re.search(r"error #\d+", runlog, re.I) and "Saving results" in runlog,
       f"{run_id} converter/calculation")
    ck("Import completed!" in (p / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (p / "export.log").read_text(encoding="utf-8-sig"),
       f"{run_id} import/export")
    events = event_checks(run_id, (p / "model.log").read_text(encoding="utf-8-sig"))
    metrics = report_checks(run_id, read(p / "report-raw.json", native=True))
    if accepted:
        manifest = read(p / "run-manifest.json")
        ck(manifest["run_id"] == run_id and manifest["input_sha256"] == sha(CASE / "native-input.json") and
           manifest["closure_sha256"] == sha(p / "closure.json") and
           manifest["validation_sha256"] == sha(p / "validation.json") and
           manifest["report_sha256"] == sha(p / "report-raw.json") and
           manifest["model_log_sha256"] == sha(p / "model.log") and
           manifest["validator_sha256"] == sha(CASE / "validate.py"),
           f"{run_id} accepted manifest binding")
    else:
        ck(not (p / "run-manifest.json").exists() and not (p / "validation.json").exists(),
           f"{run_id} diagnostic probe excluded from acceptance")
    return {"run_id": run_id, "closure_sha256": sha(p / "closure.json"),
            "input_sha256": sha(p / "input.json"), "report_sha256": sha(p / "report-raw.json"),
            "log_sha256": sha(p / "model.log"), "events": events, **metrics}


def main() -> None:
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    source = source_checks(contract, diff)
    accepted_ids = [f"g02-var01-two-position-accepted-20261001-{i:02d}" for i in (1, 2)]
    accepted = [replay(rid, source, contract, True) for rid in accepted_ids]
    ck(accepted[0]["report_sha256"] == accepted[1]["report_sha256"] and
       accepted[0]["log_sha256"] == accepted[1]["log_sha256"],
       "accepted pair byte-exact report and log")
    probe = replay("g02-var01-two-position-probe-20261001-01", source, contract, False)
    ck(probe["report_sha256"] == accepted[0]["report_sha256"] and
       probe["log_sha256"] == accepted[0]["log_sha256"],
       "excluded probe corroborates outcomes")
    result = {"schema": "g02-var01-position-modes-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failures": failures, "accepted_runs": accepted,
              "excluded_probe": {k: v for k, v in probe.items() if k != "events"},
              "accepted_raw_seal_count": 2 * len(RAW),
              "scope": "In one seed, both POS-B and POS-A explicit modes produce position-labelled failures, mission aborts, and separate half-hour local system CM tasks; two accepted guarded runs have identical logs and reports.",
              "limits": ["Three observed failures (B, B, A) do not establish population frequencies or rate propagation from FRQ values.",
                         "No QTYPM/ENVF propagation, position-specific PM, replacement, invalid reference, GUI visual, or cross-engine claim follows.",
                         "The earlier probe is source-sealed corroboration only and excluded from accepted pair."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
