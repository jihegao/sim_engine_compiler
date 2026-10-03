"""Independent standard-library read-only E10.var07 native evidence replay."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUT = Path(__file__).with_name("independent-verdict.json")
RUN_IDS = {arm: f"e10-var07-{arm}-v100-ssh-20261003-01" for arm in ("det3", "exp3")}
checks = []


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native=False):
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", raw) if native else raw)


def tables(doc, root="model"):
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def field(table, row, name):
    return row[[col["name"] for col in table["columns"]].index(name)]


def at(log, hour, phrase):
    return any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines())


def near(actual, expected, tol=0.0002):
    return math.isclose(float(actual), float(expected), abs_tol=tol, rel_tol=0)


def average(start, end, segments):
    return sum(max(0.0, min(end, stop) - max(start, begin)) * count
               for begin, stop, count in segments) / (end - start)


def changed_columns(left, right):
    return {col["name"] for lr, rr in zip(rows(left), rows(right))
            for i, col in enumerate(left["columns"]) if lr[i] != rr[i]}


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    parent_pkg = ROOT / contract["accepted_parent"]["package"]
    parent_source = parent_pkg / "native-input-ondem.json"
    parent_run = parent_pkg / "runs" / contract["accepted_parent"]["run_id"]
    parent_closure = parent_run / "closure.json"
    parent_index = parent_pkg / "evidence-index.json"
    inputs = {arm: CASE / f"native-input-{arm}.json" for arm in RUN_IDS}
    check("accepted parent input/closure/index pins", sha(parent_source) == contract["accepted_parent"]["input_sha256"] and
          sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"] and
          sha(parent_index) == contract["accepted_parent"]["evidence_index_sha256"])
    check("frozen child input/diff SHA", all(sha(path) == contract["native_inputs_sha256"][arm] ==
          diff["inputs_sha256"][arm] for arm, path in inputs.items()) and
          sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"] and
          diff["parent_sha256"] == sha(parent_source))
    parent = tables(read(parent_source))
    models = {arm: tables(read(path)) for arm, path in inputs.items()}
    for arm, model in models.items():
        changed = {name for name in parent.keys() | model.keys() if parent.get(name) != model.get(name)}
        check(f"{arm} exact two-table parent delta", changed ==
              set(diff["changed_tables_parent_to_each_arm"]) and
              diff["unchanged_tables"] == len(parent) - 2)
        for name in sorted(parent.keys() - changed):
            check(f"{arm} parent table unchanged {name}", model[name] == parent[name])
        check(f"{arm} same policy schema", model["TransportPolicyProfile"]["columns"] ==
              parent["TransportPolicyProfile"]["columns"])
        check(f"{arm} exact TPTIM/TPTIMD source row", rows(parent["TransportPolicyProfile"]) ==
              [diff["parent_policy_row"]] and rows(model["TransportPolicyProfile"]) ==
              [diff[f"{arm}_policy_row"]])
        check(f"{arm} link TFRMS remains two", field(model["StationStructure"], rows(model["StationStructure"])[0], "TFRMS") ==
              diff["parent_downward_link_tfrms"] == 2)
    a, b = models["det3"], models["exp3"]
    check("arms differ only description and TPTIMD", {name for name in a.keys() | b.keys()
          if a.get(name) != b.get(name)} == set(diff["changed_tables_between_arms"]) and
          changed_columns(a["TransportPolicyProfile"], b["TransportPolicyProfile"]) == {"TPTIMD"})
    check("no authored resources", all(not rows(a[name]) for name in
          ("Resource", "ResourceAllocation", "TaskResource")))

    reports, logs, run_hashes = {}, {}, {}
    for arm in RUN_IDS:
        run = CASE / "runs" / RUN_IDS[arm]
        invocation = read(run / "invocation.json")
        closure = read(run / "closure.json")
        check(f"{arm} invocation/closure identity", invocation["run_id"] == closure["run_id"] == RUN_IDS[arm] and
              closure["invocation_sha256"] == sha(run / "invocation.json"))
        check(f"{arm} input SHA bind", invocation["input_sha256"] == sha(inputs[arm]) == sha(run / "input.json"))
        pins = closure["source_hashes_before"]
        check(f"{arm} source SHA stable before/after", pins == closure["source_hashes_after"] ==
              invocation["source_hashes_before"])
        sources = {
            "input": inputs[arm], "parent": parent_source, "parent_closure": parent_closure,
            "parent_index": parent_index, "contract": CASE / "contract.json",
            "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
            "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
            "runner_script": CASE / "run_native_ssh.ps1",
        }
        for name, path in sorted(sources.items()):
            check(f"{arm} sealed source {name}", pins[name] == sha(path))
        check(f"{arm} installed exe/manual/dictionary fingerprints", all(
              pins[name] == contract["source"][key] for name, key in
              (("simlox_exe", "simlox_exe_sha256"), ("manual", "manual_pdf_sha256"),
               ("dictionary", "dictionary_sha256"))))
        check(f"{arm} SSH0/mutex/GUI provenance", invocation["execution_mode"] == "ssh_cli_v1" and
              invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
              "sshd.exe" in invocation["ssh_ancestor_names"] and
              invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
              invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        steps = read(run / "steps.json")
        check(f"{arm} five successful guarded steps", [step["name"] for step in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"] and
              all(step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
        check(f"{arm} twelve raw SHA seals", len(closure["raw"]) == 12)
        for name, seal in sorted(closure["raw"].items()):
            path = run / name
            check(f"{arm} raw seal {name}", path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        exported = tables(read(run / "roundtrip-raw.json", native=True))
        count = 0
        for name, authored in sorted(models[arm].items()):
            if not rows(authored):
                continue
            count += 1
            native = exported.get(name)
            same = native is not None
            if same:
                width = len(authored["columns"])
                same = ([c["name"] for c in authored["columns"]] ==
                        [c["name"] for c in native["columns"][:width]] and
                        [i["rows"] for i in authored["instances"]] ==
                        [[r[:width] for r in i["rows"]] for i in native["instances"]])
            check(f"{arm} exact authored table {name}", same)
        check(f"{arm} 22 row-containing tables", count == 22)
        converter = (run / "run.log").read_text(encoding="utf-8-sig")
        check(f"{arm} converter errors0/warning108", bool(re.search(
              r"Errors:\s*0, Warnings:\s*1, Notes:\s*0", converter)) and
              re.findall(r"warning #(\d+)", converter) == ["108"])
        check(f"{arm} valid SXO/log/report", all((run / name).stat().st_size > 1000 for name in
              ("model.sxo", "model.log", "report-raw.json")))
        logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig")
        reports[arm] = tables(read(run / "report-raw.json", native=True), "report")
        run_hashes[arm] = {"closure": sha(run / "closure.json"), "model_log": sha(run / "model.log"),
                           "report": sha(run / "report-raw.json")}

    expected = {"det3": (3.0, 13.0, 13.3333), "exp3": (3.37148, 13.3715, 13.7048)}
    parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig")
    check("parent downward transport two-hour control", at(parent_log, "10", "transport task 1 starts with 1 items/systems, transport time: 2") and
          at(parent_log, "12", "transport task 1 arrives with 1 items/systems"))
    for arm, log in logs.items():
        duration, arrival, ready = expected[arm]
        arrival_text = str(arrival).rstrip("0").rstrip(".")
        ready_text = str(ready)
        check(f"{arm} first critical failure and abort match", at(log, "9.8829", "critical random failure added") and
              at(log, "9.8829", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted"))
        check(f"{arm} one local and one depot demand h10", sum("Item demand arrives" in line for line in log.splitlines()) == 2 and
              at(log, "10", "<TEACH-LRU-01,0,BASE-01,0> Item demand arrives") and
              at(log, "10", "<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives"))
        check(f"{arm} spare ID0 issue and downward request", at(log, "10", "Take replacement item <TEACH-LRU-01,0,0> from stock") and
              at(log, "10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started"))
        match = re.search(r"Time: 10  transport task 1 starts with 1 items/systems, transport time: ([\d.]+)", log)
        check(f"{arm} native downward duration matches configured observation", match is not None and
              near(float(match.group(1)), duration, 1e-5) and duration > 0)
        check(f"{arm} arrival minus departure agrees with logged duration", at(log, arrival_text,
              "transport task 1 arrives with 1 items/systems") and near(arrival - 10, duration, 0.00005))
        check(f"{arm} physical spare ID0 arrival and backorder wait", at(log, arrival_text,
              "Replacement item arrives <TEACH-LRU-01,0,0>") and at(log, arrival_text,
              f"Backorder removed, waiting time was {duration:g}"))
        check(f"{arm} unchanged upward failed ID1 transit and repair", all(at(log, t, phrase) for t, phrase in (
              ("10.1667", "transport task 2 starts with 1 items/systems, transport time: 2"),
              ("12.1667", "transport task 2 arrives with 1 items/systems"),
              ("12.1667", "Start repair of item <TEACH-LRU-01,0,1>"),
              ("13.1667", "Finished repair of item <TEACH-LRU-01,0,1>"),
              ("13.1667", "Put back replacement item <TEACH-LRU-01,0,1> to stock"))))
        check(f"{arm} fit and readiness after arrival", at(log, ready_text, "System ready <TEACH-AIR-01,0>") and
              near(ready - arrival, 1 / 3, 0.0001))
        check(f"{arm} later missions successful", all(at(log, t, phrase) for t, phrase in (
              ("20", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting"),
              ("22", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission success"),
              ("32", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting"),
              ("34", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission success"))))
        check(f"{arm} one failure, two shipped/arrived items, no resources", sum("critical random failure added" in line for line in log.splitlines()) == 1 and
              sum("starts with 1 items/systems" in line for line in log.splitlines()) ==
              sum("arrives with 1 items/systems" in line for line in log.splitlines()) == 2 and
              "books resources" not in log)
        check(f"{arm} terminal depot repaired ID1 stock and aircraft ready", "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>," in log and
              "systems ready: 1 :<TEACH-AIR-01,0>" in log)
    check("EXP arm later random clocks differ without new failures", at(logs["det3"], "20", "Next random failure will occur 23.7461") and
          at(logs["exp3"], "20", "Next random failure will occur 23.2987") and
          all(sum("critical random failure added" in line for line in log.splitlines()) == 1 for log in logs.values()))

    check("summary equality, time bins differ", reports["det3"]["ResultSummary"] == reports["exp3"]["ResultSummary"] and
          reports["det3"]["SystemResults"] != reports["exp3"]["SystemResults"] and
          reports["det3"]["StockTotalResults"] != reports["exp3"]["StockTotalResults"])
    for arm in RUN_IDS:
        report = reports[arm]
        system, stock, summary = (report[name] for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
        sy, st = rows(system), rows(stock)
        duration, arrival, ready = expected[arm]
        check(f"{arm} expected report tables", set(report) ==
              {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        check(f"{arm} 72 system and stock half-hour bins", len(sy) == len(st) == 72)
        for index, (sr, tr) in enumerate(zip(sy, st)):
            start, end = index / 2, (index + 1) / 2
            check(f"{arm} System interval {index}", near(field(system, sr, "STINT"), start, 1e-6) and
                  near(field(system, sr, "ETINT"), end, 1e-6))
            check(f"{arm} Stock interval {index}", near(field(stock, tr, "STINT"), start, 1e-6) and
                  near(field(stock, tr, "ETINT"), end, 1e-6))
            check(f"{arm} event-derived NBO {index}", near(field(stock, tr, "NBO") or 0,
                  average(start, end, [(10, arrival, 1)]), 0.0005))
            ready_segments = [(0, 7, 1), (ready, 19, 1), (22, 31, 1), (34, 36, 1)]
            check(f"{arm} event-derived NSYRY {index}", near(field(system, sr, "NSYRY") or 0,
                  average(start, end, ready_segments), 0.0005))
            check(f"{arm} NDF first-demand bin {index}", (field(stock, tr, "NDF") or 0) ==
                  (1 if start == 10 else 0))
            check(f"{arm} NFAIL first-mission bin {index}", (field(system, sr, "NFAIL") or 0) ==
                  (1 if start == 9.5 else 0))
            check(f"{arm} NREPT fitted completion bin {index}", (field(system, sr, "NREPT") or 0) ==
                  (1 if start == math.floor(ready * 2) / 2 else 0))
        result = rows(summary)[0]
        check(f"{arm} one repetition and two/three mission success", field(summary, result, "NREP") == 1 and
              field(summary, result, "RTIUP") == 36 and near(field(summary, result, "MSUF"), 2 / 3))
        check(f"{arm} WT equals observed draw", near(sum((field(stock, row, "WT") or 0) for row in st), duration, 1e-4))
        check(f"{arm} terminal ready1/backorder0", near(field(system, sy[-1], "NSYRY"), 1) and
              (field(stock, st[-1], "NBO") or 0) == 0)
    check("pair report differences confined to timing/state metrics", changed_columns(
          reports["det3"]["SystemResults"], reports["exp3"]["SystemResults"]) ==
          {"NSYRY", "NSYUA", "NSYA", "NSYRP", "NSYWI", "NREPT", "SYDT"} and
          changed_columns(reports["det3"]["StockTotalResults"], reports["exp3"]["StockTotalResults"]) ==
          {"NBO", "WT", "WTT", "WTS", "PNB"})

    failed = [entry["name"] for entry in checks if not entry["passed"]]
    result = {
        "schema": "simlox-e10-var07-independent-readonly/v1", "passed": not failed,
        "verdict": "GO_bounded_policy_time_override_and_one_EXP_draw" if not failed else "NO_GO",
        "checks_passed": len(checks) - len(failed), "checks_total": len(checks),
        "failures": failed, "checks": checks,
        "hashes": {"contract": sha(CASE / "contract.json"), "exact_diff": sha(CASE / "exact-diff.json"),
                   "parent_input": sha(parent_source), "parent_closure": sha(parent_closure),
                   "inputs": {arm: sha(path) for arm, path in inputs.items()}, "runs": run_hashes},
        "scope": "With StationStructure.TFRMS=2 unchanged, policy TPTIM=3 yields a logged 3h deterministic downward shipment and h13 delivery. Adding TPTIMD=<EXP> yields one positive finite 3.37148h logged shipment, h13.3715 arrival, equal local wait and h13.7048 readiness. Upward failed ID1 uses unchanged two-hour route/one-hour repair in both; two later missions succeed. Every half-hour stock backorder and readiness bin agrees with event times.",
        "limits": ["One seed, one demand, one ONDEM general downward link and one exponential draw; no population mean, variance or distribution-shape conclusion.",
                   "Later random-clock text differs between arms, but neither arm has a later realized failure; no common-draw stochastic equivalence claim.",
                   "No multiple requests, item-specific policy, nested profile, other distribution, GUI-only or cross-engine claim.",
                   "No resource rows or ResourceResults are authored, so no capacity result."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                      "checks_total": result["checks_total"], "failures": failed}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
