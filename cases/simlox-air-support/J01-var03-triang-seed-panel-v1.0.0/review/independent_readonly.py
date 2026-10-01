"""Independent, standard-library replay of twelve J01.var03 TRIANG native runs."""
from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "J01-var01-determ-preparation-v1.0.0" / "native-input.json"
OUT = CASE / "review" / "independent-readonly-2026-10-01.json"
RUNS = {seed: CASE / "runs" / f"j01-var03-seed{seed:02d}-v100-20261001-01" for seed in range(1, 13)}
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
            ck(len(row) == len(names), f"triangular {table['name']} row")
            output.append(dict(zip(names, row)))
    return output


def close(actual: float, expected: float, label: str, tol: float = 4e-5) -> None:
    ck(actual is not None and abs(actual - expected) <= tol, f"{label}: {actual!r} vs {expected!r}")


def occupancy(start: float, end: float, bin_start: float) -> float:
    return 2 * max(0.0, min(end, bin_start + .5) - max(start, bin_start))


def source_checks(contract: dict, diff: dict) -> dict[int, dict]:
    ck(sha(PARENT) == contract["parent_input_sha256"] == diff["parent_input_sha256"], "accepted J01.var01 parent")
    ck(sha(CASE / "panel-diff.json") == contract["panel_diff_sha256"], "frozen panel diff hash")
    ck(sha(Path(contract["source"]["manual"])) == contract["source"]["manual_sha256"], "installed manual hash")
    ck(sha(Path(contract["source"]["database_dictionary"])) == contract["source"]["database_dictionary_sha256"], "dictionary hash")
    ck(contract["seeds"] == diff["seed_panel"] == list(RUNS), "twelve declared unique seeds")
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
            ck(changed == {"MissionPreparation", "TimeDistributions"}, "exact parent-to-seed01 tables")
            for name in changed:
                ck(doc[name]["columns"] == parent[name]["columns"] and
                   [i["instance_name"] for i in doc[name]["instances"]] ==
                   [i["instance_name"] for i in parent[name]["instances"]],
                   f"parent-to-seed01 {name} schema retained")
                ck(rows(parent[name]) == diff["parent_to_seed_01"][name]["before"] and
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
        prep, distribution = rows(doc["MissionPreparation"]), rows(doc["TimeDistributions"])
        ck(len(prep) == len(distribution) == 1 and prep[0]["DURN"] == .5 and prep[0]["DURND"] == "PREP-TRI" and
           distribution[0] == {"DISTID": "PREP-TRI", "PFAC": 1, "BASED": "<TRIANG>", "PARAM1": .25,
                               "PARAM2": .5, "PARAM3": .75, "NOTE": None}, f"seed {seed} TRIANG row/reference")
        ck(len([t for t in doc.values() if any(i["rows"] for i in t["instances"])]) == 16,
           f"seed {seed} sixteen populated tables")
    return documents


def replay(seed: int, doc: dict, contract: dict, diff: dict) -> dict:
    path = RUNS[seed]
    inv, closure, steps = (read(path / name) for name in ("invocation.json", "closure.json", "steps.json"))
    input_path = CASE / f"seed-{seed:02d}-input.json"
    ck(inv["run_id"] == closure["run_id"] == path.name and inv["seed"] == closure["seed"] == seed,
       f"seed {seed} native identity")
    ck(inv["case_id"] == closure["case_id"] == "J01" and inv["variant_id"] == closure["variant_id"] == "J01.var03" and
       inv["case_version"] == closure["case_version"] == "1.0.0", f"seed {seed} case identity")
    ck(inv["original_run_dir"].lower() == str(path).lower() and inv["execution_mode"] == "ssh_cli_v1" and
       closure["state"] == "native_steps_complete", f"seed {seed} run origin and completion")
    ck(closure["invocation_sha256"] == sha(path / "invocation.json") and closure["input_sha256"] == sha(input_path),
       f"seed {seed} invocation closure")
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
                             "parent_input_sha256": PARENT, "panel_diff_sha256": CASE / "panel-diff.json",
                             "builder_sha256": CASE / "build.py", "validator_sha256": CASE / "validate.py",
                             "panel_validator_sha256": CASE / "validate_panel.py",
                             "runner_sha256": CASE / "run_native_ssh.ps1",
                             "simlox_exe_sha256": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}.items():
        ck(inv[key] == sha(source_path), f"seed {seed} invocation {key}")
    ck(set(closure["raw"]) == RAW, f"seed {seed} eleven raw files")
    for name, meta in closure["raw"].items():
        file = path / name
        ck(file.is_file() and file.stat().st_size == meta["bytes"] and sha(file) == meta["sha256"],
           f"seed {seed} raw seal {name}")
    ck(sha(path / "input.json") == sha(input_path), f"seed {seed} raw input")
    ck(inv["session_id"] == 0 and inv["ssh_connection_present"] and inv["ssh_client_present"] and
       "sshd.exe" in inv["ssh_ancestor_names"], f"seed {seed} session-zero SSH")
    gui = inv["coexisting_gui"]
    ck(inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["allow_existing_gui"] and
       gui["pid"] == 13340 and gui["session_id"] == 1 and gui["responding_at_preflight"], f"seed {seed} queue/GUI")
    ck([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"], f"seed {seed} four native steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["coexisting_gui_present_after"] and
           step["started_utc"] <= step["completed_utc"], f"seed {seed} step {step['name']}")
    ck((path / "model.sxo").stat().st_size > 4, f"seed {seed} valid SXO")
    export = tables(read(path / "roundtrip-raw.json", native=True), "model")
    for name, table in doc.items():
        if any(i["rows"] for i in table["instances"]):
            ck(export.get(name) == table, f"seed {seed} native row roundtrip {name}")
    runlog = (path / "run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog and
       sorted(re.findall(r"warning #(\d+)", runlog)) == ["108", "126"] and
       not re.search(r"error #\d+", runlog, re.I), f"seed {seed} converter diagnostics")
    ck("Saving results" in runlog and "Import completed!" in (path / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (path / "export.log").read_text(encoding="utf-8-sig"), f"seed {seed} native completion")

    log = (path / "model.log").read_text(encoding="utf-8-sig")
    identity, aircraft = "<BASIC-MISSION,TEACH-UNIT,0,0,0>", "<TEACH-AIR-01,0>"
    start_match = re.findall(r"^Time: ([0-9.]+)  subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for ([0-9.]+) hours$", log, re.M)
    end_match = re.findall(r"^Time: ([0-9.]+) <TEACH-AIR-01,0> preparation ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>$", log, re.M)
    ck(len(start_match) == len(end_match) == 1, f"seed {seed} unique preparation sample")
    planned = float(start_match[0][1]) if start_match else float("nan")
    end_time = float(end_match[0]) if end_match else float("nan")
    ck(start_match[0][0] == "7" and .25 <= planned <= .75 and
       abs(end_time - (7 + planned)) < 2e-5, f"seed {seed} TRIANG support and preparation end")
    expected = [(7, f"{identity} mission allocates system: {aircraft}"),
                (7, f"{aircraft} preparation started, mission: {identity}"),
                (end_time, f"subtask 0 seqno 0 within system preparation task 0 on {aircraft} completed"),
                (8, f"{identity} mission starting, duration: 2 : {aircraft}"),
                (10, f"{identity} mission success:"),
                (10, f"{identity} mission completed: {aircraft}"),
                (10, f"System arrives {aircraft}, mission success")]
    timed = [(float(t), line.strip()) for t, line in re.findall(r"^Time: ([0-9.]+) (.*)$", log, re.M)]
    ck(bool(timed) and all(a[0] <= b[0] for a, b in zip(timed, timed[1:])), f"seed {seed} event order")
    for hour, phrase in expected:
        ck(any(abs(t - hour) < 1e-5 and phrase in line for t, line in timed), f"seed {seed} event {phrase}")
    ck(len(re.findall(r"preparation started,", log)) == len(re.findall(r"preparation ended,", log)) ==
       len(start_match) == len(re.findall(r"mission starting, duration:", log)) ==
       len(re.findall(r"mission success:", log)) == len(re.findall(r"mission completed:", log)) == 1 and
       not re.search(r"mission (?:cancelled|aborted|failed):|failure occurs", log, re.I),
       f"seed {seed} one positive prep and successful mission")

    report = tables(read(path / "report-raw.json", native=True), "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"seed {seed} report tables")
    summary = rows(report["ResultSummary"])
    ck(len(summary) == 1 and all(summary[0][key] == value for key, value in
       {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.items()),
       f"seed {seed} summary")
    system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"seed {seed} 72 System/Stock bins")
    for i, (sr, sk) in enumerate(zip(system, stock)):
        hour = i / 2
        operating = int(8 <= hour < 10)
        expected_fields = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                           "STINT": hour, "ETINT": hour + .5, "NSYRY": 1 - int(7 <= hour < 10),
                           "NSYMA": int(7 <= hour < 10), "NSYMO": operating,
                           "NSYMP": occupancy(7, end_time, hour), "NSYMR": occupancy(end_time, 8, hour),
                           "NSYA": 1, "FTMO": operating, "STACC": operating,
                           "NPSTA": int(hour == 7), "NPSUC": int(hour == int(end_time * 2) / 2)}
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
    observed = sum(row["NSYMP"] * .5 for row in system)
    close(observed, planned, f"seed {seed} report preparation integral")
    close(sum(row["NSYMO"] * .5 for row in system), 2, f"seed {seed} flight hours")
    ck(system[-1]["NSYRY"] == 1 and system[-1]["NSYMA"] == 0 and stock[-1]["NBO"] == 0,
       f"seed {seed} terminal ready")
    return {"seed": seed, "run_id": path.name, "input_sha256": sha(input_path),
            "closure_sha256": sha(path / "closure.json"), "log_sha256": sha(path / "model.log"),
            "report_sha256": sha(path / "report-raw.json"), "log_sample_hours": planned,
            "report_integrated_prep_hours": observed, "preparation_end_hour": end_time}


def main() -> None:
    contract, diff = read(CASE / "contract.json"), read(CASE / "panel-diff.json")
    documents = source_checks(contract, diff)
    runs = [replay(seed, documents[seed], contract, diff) for seed in RUNS]
    sample = [run["report_integrated_prep_hours"] for run in runs]
    ck(len(sample) == 12 and len(set(round(value, 5) for value in sample)) >= 2, "twelve variable samples")
    ck(all(.25 <= value <= .75 for value in sample), "all report samples within declared support")
    dictionary = Path(contract["source"]["database_dictionary"]).read_text(encoding="utf-8-sig", errors="replace")
    ck("<TRIANG>" in dictionary, "dictionary lists native TRIANG token")
    result = {"schema": "j01-var03-triang-panel-independent-readonly/v1", "case": CASE.name,
              "passed": not failures, "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failures": failures, "run_count": len(runs), "raw_seal_count": len(runs) * len(RAW),
              "samples": runs, "sample_min_hours": min(sample), "sample_max_hours": max(sample),
              "sample_mean_hours": statistics.mean(sample),
              "scope": "Twelve fixed-seed one-mission native runs accept PREP-TRI/<TRIANG> and show varied observed prep durations within [0.25, 0.75] hours.",
              "limits": ["The installed manual prints <TRIANGULAR> while the dictionary and exact native roundtrip use <TRIANG>; this evidence supports the latter token in this input only.",
                         "Observed support and descriptive sample statistics do not establish a probability law, mode, endpoint attainment or independence.",
                         "One draw per seed; other parameters, distribution families, GUI-only behavior and cross-engine parity remain untested."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks, "failures": failures[:15],
                      "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
