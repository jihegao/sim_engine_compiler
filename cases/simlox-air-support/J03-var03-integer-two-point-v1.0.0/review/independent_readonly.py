"""Independent, standard-library replay of 32 accepted J03.var03 two-point runs."""
from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "J02-determ-boundary-count-v1.0.0" / "determ-2-seed-01-input.json"
OUT = CASE / "review" / "independent-readonly-2026-10-01.json"
RUNS = {seed: CASE / "runs" / f"j03-var03-seed{seed:02d}-accepted-20261001-01" for seed in range(1, 33)}
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log",
       "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
checks = 0
failures: list[str] = []


def ck(ok: bool, label: str) -> None:
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
    output = {t["name"]: t for t in seq}
    ck(len(output) == len(seq), f"unique {root} tables")
    return output


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    output = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            ck(len(row) == len(names), f"well-formed {table['name']} row")
            output.append(dict(zip(names, row)))
    return output


def close(actual: float, expected: float, label: str, tol: float = 4e-5) -> None:
    ck(actual is not None and abs(actual - expected) <= tol, f"{label}: {actual!r} vs {expected!r}")


def occupancy(start: float, end: float, bin_start: float) -> float:
    return 2 * max(0.0, min(end, bin_start + .5) - max(start, bin_start))


def source_checks(contract: dict, diff: dict) -> dict[int, dict]:
    ck(sha(PARENT) == contract["parent_input_sha256"] == diff["parent_input_sha256"], "accepted J02.var01 parent")
    ck(sha(CASE / "panel-diff.json") == contract["panel_diff_sha256"], "frozen panel diff hash")
    ck(sha(Path(contract["source"]["manual"])) == contract["source"]["manual_sha256"], "installed manual hash")
    ck(sha(Path(contract["source"]["database_dictionary"])) == contract["source"]["database_dictionary_sha256"], "dictionary hash")
    ck(diff["seeds"] == list(RUNS) and contract["expected_observation"]["seed_range_inclusive"] == [1, 32],
       "32 declared unique seeds")
    executable_sha = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
    ck(sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")) == executable_sha and
       executable_sha in (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig"),
       "installed executable matches frozen runner pin")
    parent = tables(read(PARENT), "model")
    documents = {}
    first = None
    for seed in RUNS:
        name = f"seed-{seed:02d}-input.json"
        path = CASE / name
        ck(sha(path) == diff["input_sha256"][name], f"seed {seed} input SHA")
        doc = tables(read(path), "model")
        documents[seed] = doc
        control = rows(doc["Control"])
        ck(len(control) == 1 and control[0]["RSEED"] == str(seed) and control[0]["NREPS"] == 1 and
           control[0]["SIMPE"] == 36, f"seed {seed} Control row")
        if seed == 1:
            first = doc
            changed = {name for name in parent.keys() | doc.keys() if parent.get(name) != doc.get(name)}
            ck(changed == {"IntegerDistributions"}, "exact parent-to-seed01 table")
            for name in changed:
                if name in parent:
                    ck(doc[name]["columns"] == parent[name]["columns"] and
                       [i["instance_name"] for i in doc[name]["instances"]] ==
                       [i["instance_name"] for i in parent[name]["instances"]],
                       f"parent-to-seed01 {name} schema retained")
                else:
                    ck(False, "parent lacks expected table")
                ck((rows(parent[name]) if name in parent else None) == diff["parent_to_seed_01"][name]["before"] and
                   rows(doc[name]) == diff["parent_to_seed_01"][name]["after"], f"exact parent-to-seed01 {name}")
        else:
            changed = {name for name in first.keys() | doc.keys() if first.get(name) != doc.get(name)}
            ck(changed == {"Control"}, f"seed {seed} only Control changes")
            first_control = rows(first["Control"])[0]
            ck(doc["Control"]["columns"] == first["Control"]["columns"] and
               [i["instance_name"] for i in doc["Control"]["instances"]] ==
               [i["instance_name"] for i in first["Control"]["instances"]],
               f"seed {seed} Control schema retained")
            ck({k: v for k, v in control[0].items() if k != "RSEED"} ==
               {k: v for k, v in first_control.items() if k != "RSEED"}, f"seed {seed} only RSEED field")
            if seed == 2:
                ck(rows(first["Control"]) == diff["seed_01_to_seed_02"]["Control"]["before"] and
                   control == diff["seed_01_to_seed_02"]["Control"]["after"], "declared seed01-to-seed02 diff")
        profile, distribution, deployment = rows(doc["OperationProfile"]), rows(doc["IntegerDistributions"]), rows(doc["SystemDeployment"])
        ck(len(profile) == len(deployment) == 1 and len(distribution) == 2 and
           profile[0]["ITYPE"] == "RANDOM" and profile[0]["IQTYD"] == "COUNTD" and
           profile[0]["IPER"] == 0 and profile[0]["IDISP"] == "EQUIDIST" and
           distribution == [{"DISTID": "COUNTD", "PFAC": .5, "BASED": "<DETERM>", "PARAM1": value,
                            "PARAM2": None, "PARAM3": None, "NOTE": None} for value in (0, 2)] and
           deployment[0]["QTYPS"] == 6, f"seed {seed} two-point/profile/six-aircraft rows")
        ck(len([t for t in doc.values() if any(i["rows"] for i in t["instances"])]) == 14,
           f"seed {seed} fourteen populated tables")
    return documents


def replay(seed: int, doc: dict, contract: dict, diff: dict) -> dict:
    path = RUNS[seed]
    inv, closure, steps = (read(path / name) for name in ("invocation.json", "closure.json", "steps.json"))
    input_path = CASE / f"seed-{seed:02d}-input.json"
    ck(inv["run_id"] == closure["run_id"] == path.name and inv["seed"] == closure["seed"] == seed,
       f"seed {seed} native identity")
    ck(inv["run_id"] == path.name and closure["state"] == "native_steps_complete",
       f"seed {seed} run origin and completion")
    ck(closure["invocation_sha256"] == sha(path / "invocation.json") and closure["input_sha256"] == sha(input_path),
       f"seed {seed} invocation closure")
    manifest = read(path / "run-manifest.json")
    ck(manifest["case_id"] == "J03" and manifest["variant_id"] == "J03.var03" and
       manifest["version"] == "1.0.0" and manifest["seed"] == seed and
       manifest["run_id"] == path.name and manifest["input_sha256"] == sha(input_path) and
       manifest["closure_sha256"] == sha(path / "closure.json") and
       manifest["validation_sha256"] == sha(path / "validation.json") and
       manifest["execution_mode"] == "ssh_cli_v1", f"seed {seed} manifest reconciliation")
    fixed = {"contract.json": CASE / "contract.json", "build.py": CASE / "build.py",
             "validate.py": CASE / "validate.py", "validate_panel.py": CASE / "validate_panel.py",
             "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
             "panel-diff.json": CASE / "panel-diff.json", "parent-input.json": PARENT,
             "database-dictionary.txt": Path(contract["source"]["database_dictionary"]),
             "manual.pdf": Path(contract["source"]["manual"])}
    fixed.update({f"seed-{i:02d}-input.json": CASE / f"seed-{i:02d}-input.json" for i in RUNS})
    ck(set(closure["post_source_sha256"]) == set(fixed), f"seed {seed} complete source map")
    for name, source_path in fixed.items():
        ck(closure["post_source_sha256"].get(name) == sha(source_path), f"seed {seed} post-source {name}")
    for key, source_path in {"input_sha256": input_path, "contract_sha256": CASE / "contract.json",
                             "panel_diff_sha256": CASE / "panel-diff.json",
                             "builder_sha256": CASE / "build.py", "validator_sha256": CASE / "validate.py",
                             "panel_validator_sha256": CASE / "validate_panel.py",
                             "runner_sha256": CASE / "run_native_ssh.ps1"}.items():
        ck(inv[key] == sha(source_path), f"seed {seed} invocation {key}")
    ck(set(closure["raw"]) == RAW, f"seed {seed} eleven raw files")
    for name, meta in closure["raw"].items():
        file = path / name
        ck(file.is_file() and file.stat().st_size == meta["bytes"] and sha(file) == meta["sha256"],
           f"seed {seed} raw seal {name}")
    ck(sha(path / "input.json") == sha(input_path), f"seed {seed} raw input")
    ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"],
       f"seed {seed} session-zero SSH")
    ck(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
       inv["gui_pid"] == 13340 and
       inv["gui_start_utc"] == "2026-09-28T10:09:56.8261381Z", f"seed {seed} queue/GUI")
    ck([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"], f"seed {seed} four native steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["coexisting_gui_present_after"],
           f"seed {seed} step {step['name']}")
    ck((path / "model.sxo").stat().st_size > 4, f"seed {seed} valid SXO")
    export = tables(read(path / "roundtrip-raw.json", native=True), "model")
    for name, table in doc.items():
        if any(i["rows"] for i in table["instances"]):
            ck(export.get(name) == table, f"seed {seed} native row roundtrip {name}")
    runlog = (path / "run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog and
       sorted(re.findall(r"warning #(\d+)", runlog)) == ["108", "126", "211"] and
       not re.search(r"error #\d+", runlog, re.I), f"seed {seed} converter diagnostics")
    ck("Saving results" in runlog and "Import completed!" in (path / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (path / "export.log").read_text(encoding="utf-8-sig"), f"seed {seed} native completion")

    log = (path / "model.log").read_text(encoding="utf-8-sig")
    timed = [(float(t), line.strip()) for t, line in re.findall(r"^Time: ([0-9.]+) (.*)$", log, re.M)]
    ck(bool(timed) and all(a[0] <= b[0] for a, b in zip(timed, timed[1:])), f"seed {seed} ordered native events")
    ck(len(re.findall(r"^Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION$", log, re.M)) == 1,
       f"seed {seed} one profile order")
    pattern = r"<BASIC-MISSION,TEACH-UNIT,0,0,(\d+)>"
    created = [int(x) for x in re.findall(r"^Time: 7 " + pattern + r" mission created:", log, re.M)]
    activated = [int(x) for x in re.findall(r"^Time: 7 " + pattern + r" mission activated, systems requested: 2$", log, re.M)]
    count = len(activated)
    ck(count in (0, 2) and created == list(range(count + 1)) and activated == list(range(1, count + 1)),
       f"seed {seed} sentinel and activated mission IDs")
    alloc = [(int(mid), int(aid)) for mid, aid in re.findall(
        r"^Time: 7 " + pattern + r" mission allocates system: <TEACH-AIR-01,(\d+)>$", log, re.M)]
    expected_alloc = [(mid, aid) for mid in range(1, count + 1) for aid in (2 * mid - 2, 2 * mid - 1)]
    ck(alloc == expected_alloc and len({aid for _, aid in alloc}) == 2 * count,
       f"seed {seed} two distinct aircraft per mission, no sharing")
    for mid in range(1, count + 1):
        identity = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
        aircraft = f"<TEACH-AIR-01,{2 * mid - 2}>,<TEACH-AIR-01,{2 * mid - 1}>"
        ck(f"Time: 8 {identity} mission starting, duration: 2 : {aircraft}" in log,
           f"seed {seed} mission {mid} launch")
        ck(f"Time: 10 {identity} mission success:" in log and
           f"Time: 10 {identity} mission completed: {aircraft}" in log,
           f"seed {seed} mission {mid} success and completion")
    launched = [int(x) for x in re.findall(r"^Time: 8 " + pattern + r" mission starting, duration: 2 :", log, re.M)]
    successes = [int(x) for x in re.findall(r"^Time: 10 " + pattern + r" mission success:", log, re.M)]
    completed = [int(x) for x in re.findall(r"^Time: 10 " + pattern + r" mission completed:", log, re.M)]
    arrivals = [int(x) for x in re.findall(
        r"^Time: 10 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,(\d+)>, mission success,", log, re.M)]
    ck(launched == successes == completed == list(range(1, count + 1)) and
       arrivals == list(range(2 * count)), f"seed {seed} exact launched/successful/returned identities")
    ck(not re.search(r"mission (?:cancelled|aborted|failed):|failure occurs|shortage", log, re.I),
       f"seed {seed} no failure or shortage event")
    if count == 0:
        ck(created == [0] and not alloc and not launched and not arrivals,
           f"seed {seed} zero-count sentinel without mission activity")

    report = tables(read(path / "report-raw.json", native=True), "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"seed {seed} report tables")
    summary = rows(report["ResultSummary"])
    expected_factor = int(count > 0)
    ck(len(summary) == 1 and all(summary[0][key] == value for key, value in
       {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": expected_factor,
        "MSTF": expected_factor, "MSUF": expected_factor, "STMF": expected_factor}.items()) and
       all(summary[0][key] == 0 for key in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
       f"seed {seed} summary factors")
    system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"seed {seed} 72 System/Stock bins")
    aircraft_count = 2 * count
    for i, (sr, sk) in enumerate(zip(system, stock)):
        hour = i / 2
        assigned = aircraft_count if 7 <= hour < 10 else 0
        operating = aircraft_count if 8 <= hour < 10 else 0
        reserved = aircraft_count if 7 <= hour < 8 else 0
        expected_fields = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                           "STINT": hour, "ETINT": hour + .5, "NSYRY": 6 - assigned,
                           "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                           "NSYA": 6, "FTMO": operating / 6, "STACC": operating}
        for key, value in expected_fields.items():
            if isinstance(value, (int, float)):
                close(sr[key], value, f"seed {seed} bin {i} {key}")
            else:
                ck(sr[key] == value, f"seed {seed} bin {i} {key}")
        ck(all(value in (0, None) for key, value in sr.items() if key not in expected_fields),
           f"seed {seed} bin {i} other System")
        for key, value in {"STINT": hour, "ETINT": hour + .5, "PNB": 1}.items():
            ck(sk[key] == value, f"seed {seed} bin {i} Stock {key}")
        ck(all(value in (0, None) for key, value in sk.items() if key not in {"STINT", "ETINT", "PNB"}),
           f"seed {seed} bin {i} other Stock")
    close(sum(row["NSYMO"] * .5 for row in system), 4 * count, f"seed {seed} four aircraft-hours per mission")
    close(sum(row["STACC"] * .5 for row in system), 4 * count,
          f"seed {seed} STACC integrated flight aircraft-hours")
    ck(system[-1]["NSYRY"] == 6 and system[-1]["NSYMA"] == 0 and stock[-1]["NBO"] == 0,
       f"seed {seed} six ready at horizon")
    return {"seed": seed, "run_id": path.name, "input_sha256": sha(input_path),
            "closure_sha256": sha(path / "closure.json"), "log_sha256": sha(path / "model.log"),
            "report_sha256": sha(path / "report-raw.json"), "mission_count": count,
            "aircraft_ids": [aid for _, aid in alloc], "flight_aircraft_hours": 4 * count,
            "MTMF": summary[0]["MTMF"], "STMF": summary[0]["STMF"],
            "STACC_integrated_aircraft_hours": sum(row["STACC"] * .5 for row in system),
            "terminal_ready": system[-1]["NSYRY"]}


def main() -> None:
    contract, diff = read(CASE / "contract.json"), read(CASE / "panel-diff.json")
    documents = source_checks(contract, diff)
    runs = [replay(seed, documents[seed], contract, diff) for seed in RUNS]
    counts = [run["mission_count"] for run in runs]
    ck(counts == contract["expected_observation"]["frozen_counts_by_seed"], "frozen count sequence")
    frequencies = {str(k): v for k, v in sorted(Counter(counts).items())}
    ck(frequencies == contract["expected_observation"]["frozen_frequencies"], "frozen count frequencies")
    sample_mean = sum(counts) / len(counts)
    close(sample_mean, contract["expected_observation"]["frozen_sample_mean"], "frozen sample mean")
    sample_variance = statistics.variance(counts)
    close(sample_variance, contract["expected_observation"]["frozen_sample_variance"],
          "frozen sample variance")
    ck(set(counts) == {0, 2}, "both two-point count outcomes represented")
    probes = [p for p in (CASE / "runs").iterdir() if "-probe-" in p.name]
    ck(len(probes) == 32 and not set(probes) & set(RUNS.values()),
       "thirty-two diagnostic probe directories excluded from accepted replay")
    dictionary = Path(contract["source"]["database_dictionary"]).read_text(encoding="utf-8-sig", errors="replace")
    ck("<DETERM>" in dictionary, "dictionary lists native DETERM token")
    result = {"schema": "j03-var03-two-point-panel-independent-readonly/v1", "case": CASE.name,
              "passed": not failures, "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failures": failures, "run_count": len(runs), "raw_seal_count": len(runs) * len(RAW),
              "samples": runs, "counts_by_seed": counts, "frequencies": frequencies,
              "sample_mean": sample_mean, "sample_variance": sample_variance,
              "scope": "Thirty-two fixed-seed native runs accept two COUNTD/<DETERM> rows at PFAC 0.5 each and show either zero or two two-aircraft missions, with six aircraft ready at the horizon.",
              "limits": ["The thirty-two separate -probe runs are diagnostic and excluded from this acceptance verdict.",
                         "The observed 15 zero and 17 two draws do not establish population mixture weights or stream independence.",
                         "One draw per seed; other support points or weights, GUI-only behavior, and cross-engine parity remain untested."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks, "failures": failures[:15],
                      "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
