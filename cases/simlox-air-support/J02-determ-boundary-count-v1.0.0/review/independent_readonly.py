"""Independent standard-library replay of the five accepted J02 count arms."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "J02-var02-irect-formation-count-v1.0.0" / "seed-01-input.json"
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
ARMS = {
    "determ-2-seed-01": "j02-determ-2-seed01-accepted-20261001-01",
    "determ-2-seed-02": "j02-determ-2-seed02-accepted-20261001-01",
    "zero-six": "j02-zero-six-accepted-20261001-01",
    "four-eight": "j02-four-eight-accepted-20261001-01",
    "four-six": "j02-four-six-accepted-20261001-01",
}
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
    text = path.read_text(encoding="utf-8-sig")
    if native:
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def tables(document: dict, root: str) -> dict:
    sequence = document[root]["tables"]
    result = {table["name"]: table for table in sequence}
    ck(len(result) == len(sequence), f"unique {root} table names")
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


def source_checks(contract: dict, difference: dict) -> dict[str, dict]:
    ck(sha(PARENT) == contract["parent_input_sha256"] == difference["parent_input_sha256"],
       "accepted J02.var02 parent SHA")
    ck(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff SHA")
    for key, hash_key in (("manual", "manual_sha256"),
                          ("database_dictionary", "database_dictionary_sha256")):
        ck(sha(Path(contract["source"][key])) == contract["source"][hash_key],
           f"installed {key} fingerprint")
    dictionary = Path(contract["source"]["database_dictionary"]).read_text(
        encoding="utf-8-sig", errors="replace")
    ck("<DETERM>" in dictionary and "IntegerDistributions" in dictionary,
       "native integer deterministic token and table")
    executable_sha = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
    ck(sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")) == executable_sha and
       executable_sha in (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig"),
       "installed executable matches frozen runner pin")
    ck(set(contract["arms"]) == set(difference["arms"]) == set(ARMS), "five frozen arms")
    parent = tables(read(PARENT), "model")
    documents = {}
    for arm, metadata in contract["arms"].items():
        input_path = CASE / f"{arm}-input.json"
        ck(sha(input_path) == metadata["input_sha256"] == difference["arms"][arm]["input_sha256"],
           f"{arm} source SHA")
        current = tables(read(input_path), "model")
        documents[arm] = current
        delta = difference["arms"][arm]["parent_delta"]
        changed = {name for name in parent.keys() | current.keys() if parent.get(name) != current.get(name)}
        ck(changed == set(delta), f"{arm} exact changed tables")
        for name in changed:
            ck(current[name]["columns"] == parent[name]["columns"] and
               [x["instance_name"] for x in current[name]["instances"]] ==
               [x["instance_name"] for x in parent[name]["instances"]],
               f"{arm} {name} schema and instance identities")
            ck(rows(parent[name]) == delta[name]["before"] and
               rows(current[name]) == delta[name]["after"], f"{arm} {name} exact row delta")
        ctl = rows(current["Control"])[0]
        dist = rows(current["IntegerDistributions"])
        profile = rows(current["OperationProfile"])
        deployment = rows(current["SystemDeployment"])
        ck(ctl["RSEED"] == str(metadata["seed"]) and ctl["SIMPE"] == 36 and
           ctl["RCINT"] == .5 and ctl["NREPS"] == 1, f"{arm} Control")
        ck(dist == [{"DISTID": "COUNTD", "PFAC": 1, "BASED": "<DETERM>",
                     "PARAM1": metadata["count"], "PARAM2": None, "PARAM3": None, "NOTE": None}],
           f"{arm} deterministic count row")
        ck(len(profile) == 1 and profile[0]["ITYPE"] == "RANDOM" and
           profile[0]["IQTYD"] == "COUNTD" and profile[0]["IPER"] == 0 and
           profile[0]["IDISP"] == "EQUIDIST" and profile[0]["STIM"] == 8 and
           abs(profile[0]["DTIM"] - 1 / 3) < 1e-12, f"{arm} mission profile")
        ck(len(deployment) == 1 and deployment[0]["QTYPS"] == metadata["deployed_aircraft"],
           f"{arm} deployed aircraft")
        ck(len([t for t in current.values() if any(i["rows"] for i in t["instances"])]) == 14,
           f"{arm} fourteen populated source tables")
    first, second = documents["determ-2-seed-01"], documents["determ-2-seed-02"]
    ck({n for n in first if first[n] != second[n]} == {"Control"} and
       rows(first["Control"]) == difference["determ_seed_delta"]["Control"]["before"] and
       rows(second["Control"]) == difference["determ_seed_delta"]["Control"]["after"],
       "deterministic seed pair differs only in Control.RSEED")
    full, limited = documents["four-eight"], documents["four-six"]
    ck({n for n in full if full[n] != limited[n]} == {"SystemDeployment"} and
       rows(full["SystemDeployment"]) == difference["capacity_delta"]["SystemDeployment"]["before"] and
       rows(limited["SystemDeployment"]) == difference["capacity_delta"]["SystemDeployment"]["after"],
       "four-count capacity pair differs only in QTYPS")
    return documents


def replay(arm: str, document: dict, metadata: dict, contract: dict) -> dict:
    path = CASE / "runs" / ARMS[arm]
    invocation = read(path / "invocation.json")
    closure = read(path / "closure.json")
    steps = read(path / "steps.json")
    input_path = CASE / f"{arm}-input.json"
    ck(invocation["arm"] == closure["arm"] == arm and
       invocation["run_id"] == closure["run_id"] == path.name and
       invocation["seed"] == metadata["seed"], f"{arm} run identity")
    ck(invocation["input_sha256"] == closure["input_sha256"] == sha(input_path) and
       closure["invocation_sha256"] == sha(path / "invocation.json") and
       closure["state"] == "native_steps_complete", f"{arm} input/invocation closure")
    manifest = read(path / "run-manifest.json")
    ck(manifest["case_id"] == "J02" and manifest["variant_id"] == metadata["variant_id"] and
       manifest["version"] == "1.0.0" and manifest["arm"] == arm and
       manifest["run_id"] == path.name and manifest["input_sha256"] == sha(input_path) and
       manifest["closure_sha256"] == sha(path / "closure.json") and
       manifest["validation_sha256"] == sha(path / "validation.json") and
       manifest["execution_mode"] == "ssh_cli_v1", f"{arm} run manifest reconciliation")
    fixed = {"contract.json": CASE / "contract.json", "build.py": CASE / "build.py",
             "validate.py": CASE / "validate.py", "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
             "exact-diff.json": CASE / "exact-diff.json", "parent-input.json": PARENT,
             "manual.pdf": Path(contract["source"]["manual"]),
             "database-dictionary.txt": Path(contract["source"]["database_dictionary"])}
    fixed.update({f"{a}-input.json": CASE / f"{a}-input.json" for a in ARMS})
    ck(set(closure["post_source_sha256"]) == set(fixed), f"{arm} complete frozen source map")
    for name, source_path in fixed.items():
        ck(closure["post_source_sha256"].get(name) == sha(source_path), f"{arm} source seal {name}")
    for key, source_path in (("contract_sha256", CASE / "contract.json"),
                             ("builder_sha256", CASE / "build.py"),
                             ("validator_sha256", CASE / "validate.py"),
                             ("runner_sha256", CASE / "run_native_ssh.ps1")):
        ck(invocation[key] == sha(source_path), f"{arm} invocation {key}")
    ck(set(closure["raw"]) == RAW, f"{arm} eleven declared raw files")
    for name, file_meta in closure["raw"].items():
        file_path = path / name
        ck(file_path.is_file() and file_path.stat().st_size == file_meta["bytes"] and
           sha(file_path) == file_meta["sha256"], f"{arm} raw seal {name}")
    ck(sha(path / "input.json") == sha(input_path), f"{arm} raw source copy")
    ck(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["gui_pid"] == 13340 and invocation["gui_start_utc"] ==
       "2026-09-28T10:09:56.8261381Z" and
       invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue",
       f"{arm} session-zero SSH, GUI identity, queue mutex")
    ck([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"],
       f"{arm} four native steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["coexisting_gui_present_after"],
           f"{arm} successful guarded {step['name']}")
    ck((path / "model.sxo").stat().st_size > 4, f"{arm} valid SXO")
    exported = tables(read(path / "roundtrip-raw.json", native=True), "model")
    populated = [name for name, table in document.items() if any(i["rows"] for i in table["instances"])]
    ck(len(populated) == 14, f"{arm} populated business table count")
    for name in populated:
        ck(exported.get(name) == document[name], f"{arm} exact native roundtrip {name}")
    runlog = (path / "run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog and
       sorted(re.findall(r"warning #(\d+)", runlog)) == ["108", "126", "211"] and
       not re.search(r"error #\d+", runlog, re.I), f"{arm} converter warnings 108/126/211")
    ck("Saving results" in runlog and
       "Import completed!" in (path / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (path / "export.log").read_text(encoding="utf-8-sig"),
       f"{arm} native conversion/calculation complete")

    log = (path / "model.log").read_text(encoding="utf-8-sig")
    times = [float(value) for value in re.findall(r"^Time: ([\d.]+) ", log, re.M)]
    ck(bool(times) and times == sorted(times), f"{arm} chronological native events")
    ck(len(re.findall(r"^Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION$", log, re.M)) == 1,
       f"{arm} one operation order")
    identity = r"<BASIC-MISSION,TEACH-UNIT,0,0,(\d+)>"
    collect = lambda time, text: [int(x) for x in re.findall(
        rf"^Time: {time} " + identity + text, log, re.M)]
    count = metadata["count"]
    starts = metadata["starts"]
    created = collect("7", r" mission created:")
    activated = collect("7", r" mission activated, systems requested: 2$")
    launched = collect("8", r" mission starting, duration: 2 :")
    successes = collect("10", r" mission success:")
    completed = collect("10", r" mission completed:")
    cancelled = collect(r"8\.33333", r" mission cancelled:")
    ck(created == list(range(count + 1)) and activated == list(range(1, count + 1)),
       f"{arm} sentinel and exact activated identities")
    ck(launched == successes == completed == list(range(1, starts + 1)) and
       cancelled == ([4] if arm == "four-six" else []), f"{arm} launch/success/cancel identities")
    allocations = [(int(mid), int(aid)) for mid, aid in re.findall(
        r"^Time: 7 " + identity + r" mission allocates system: <TEACH-AIR-01,(\d+)>$", log, re.M)]
    expected = [(mid, aid) for mid in range(1, starts + 1)
                for aid in (2 * mid - 2, 2 * mid - 1)]
    ck(allocations == expected and len({aid for _, aid in allocations}) == 2 * starts,
       f"{arm} two distinct aircraft per started mission")
    for mid in range(1, starts + 1):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
        aircraft = f"<TEACH-AIR-01,{2 * mid - 2}>,<TEACH-AIR-01,{2 * mid - 1}>"
        ck(f"Time: 8 {mission} mission starting, duration: 2 : {aircraft}" in log and
           f"Time: 10 {mission} mission completed: {aircraft}" in log,
           f"{arm} mission {mid} launch and completion aircraft")
    arrivals = [int(aid) for aid in re.findall(
        r"^Time: 10 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,(\d+)>, mission success,", log, re.M)]
    ck(arrivals == list(range(2 * starts)), f"{arm} exact aircraft returns")
    ck(("mission waiting:  timeout at 8.33333" in log) == (arm == "four-six"),
       f"{arm} timeout contrast")
    ck(not re.search(r"failure occurs|mission aborted|mission failed", log, re.I),
       f"{arm} no failure/abort")
    if count == 0:
        ck(created == [0] and not activated and not allocations and not launched and
           not arrivals, f"{arm} zero-count sentinel without activity")

    report = tables(read(path / "report-raw.json", native=True), "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{arm} report tables")
    summary = rows(report["ResultSummary"])
    factor = starts / count if count else 0
    ck(len(summary) == 1 and all(summary[0][name] == value for name, value in
       {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": factor, "MSTF": factor,
        "MSUF": factor, "STMF": factor}.items()) and
       all(summary[0][name] == 0 for name in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
       f"{arm} mission/system summary factors")
    system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{arm} 72 report bins")
    active_aircraft = 2 * starts
    total_aircraft = metadata["deployed_aircraft"]
    for bin_no, (sr, st) in enumerate(zip(system, stock)):
        hour = bin_no / 2
        assigned = active_aircraft if 7 <= hour < 10 else 0
        flying = active_aircraft if 8 <= hour < 10 else 0
        reserved = active_aircraft if 7 <= hour < 8 else 0
        fields = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                  "STINT": hour, "ETINT": hour + .5, "NSYRY": total_aircraft - assigned,
                  "NSYMA": assigned, "NSYMO": flying, "NSYMR": reserved,
                  "NSYA": total_aircraft, "FTMO": flying / total_aircraft, "STACC": flying}
        for name, value in fields.items():
            if isinstance(value, (int, float)):
                near(sr[name], value, f"{arm} system bin {bin_no} {name}")
            else:
                ck(sr[name] == value, f"{arm} system bin {bin_no} {name}")
        ck(all(value in (0, None) for name, value in sr.items() if name not in fields),
           f"{arm} system bin {bin_no} other fields")
        ck(st["STINT"] == hour and st["ETINT"] == hour + .5 and st["PNB"] == 1 and
           all(value in (0, None) for name, value in st.items()
               if name not in {"STINT", "ETINT", "PNB"}), f"{arm} stock bin {bin_no}")
    near(sum(row["NSYMO"] * .5 for row in system), 4 * starts,
         f"{arm} integrated aircraft flight hours")
    ck(system[-1]["NSYRY"] == total_aircraft and system[-1]["NSYMA"] == 0 and
       stock[-1]["NBO"] == 0, f"{arm} terminal aircraft ready and no backorder")
    return {"arm": arm, "run_id": path.name, "source_sha256": sha(input_path),
            "closure_sha256": sha(path / "closure.json"), "model_log_sha256": sha(path / "model.log"),
            "report_sha256": sha(path / "report-raw.json"), "activated": len(activated),
            "started": len(launched), "successful": len(successes), "cancelled": len(cancelled),
            "aircraft_flight_hours": 4 * starts, "terminal_ready": total_aircraft}


def main() -> None:
    contract, difference = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    documents = source_checks(contract, difference)
    results = [replay(arm, documents[arm], contract["arms"][arm], contract) for arm in ARMS]
    probes = [path for path in (CASE / "runs").iterdir() if "-probe-" in path.name]
    ck(len(probes) == 5 and not set(probes) &
       {CASE / "runs" / name for name in ARMS.values()},
       "five diagnostic probes excluded")
    result = {"schema": "j02-determ-boundary-independent-readonly/v1", "case": CASE.name,
              "passed": not failures, "verdict": "GO" if not failures else "NO-GO",
              "check_count": checks, "failures": failures, "run_count": len(results),
              "raw_seal_count": len(results) * len(RAW), "arms": results,
              "scope": "Five fresh fixed-input native CLI runs support deterministic counts 0, 2, and 4; four requested missions with six aircraft yield three successes and one timeout cancellation, while eight aircraft support all four.",
              "limits": ["Five earlier probe runs are diagnostic and excluded from acceptance.",
                         "Two deterministic seeds do not establish general seed invariance.",
                         "A single capacity contrast does not establish other shortage policies, GUI-only behavior, or cross-engine parity."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
