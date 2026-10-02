"""Independent read-only replay for E15.var07 v1.0.1.

Standard library only; no case builder/checker/validator imports and no native calls.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
CASES = CASE.parent
DONOR = CASES / "G01-var03-du-discard-reorder-v1.0.0/native-input.json"
E02 = CASES / "E02-zero-stock-local-backorder-v1.0.0/native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
OUT = CASE / "review/independent-readonly-2026-10-02.json"
CHECKS = 0
FAILURES: list[str] = []


def check(value, label):
    global CHECKS
    CHECKS += 1
    if not value:
        FAILURES.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def models(path):
    return {x["name"]: x for x in read(path)["model"]["tables"]}


def reports(path):
    return {x["name"]: x for x in read(path)["report"]["tables"]}


def rows(table):
    names = [x["name"] for x in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def changes(before, after):
    result = {}
    for table in before:
        x, y = before[table], after[table]
        check([c["name"] for c in x["columns"]] == [c["name"] for c in y["columns"]],
              f"source column identity {table}")
        xr, yr = rows(x), rows(y)
        check(len(xr) == len(yr), f"source row cardinality {table}")
        edits = []
        for idx, (a, b) in enumerate(zip(xr, yr)):
            for field in a:
                if a[field] != b[field]:
                    edits.append({"row": idx, "field": field, "before": a[field], "after": b[field]})
        if edits:
            result[table] = edits
    return result


def close(a, b, tol=1e-5):
    return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)


def run_paths(arm):
    return (CASE / "runs" / f"e15-var07-{arm}-v101-ssh-20261002-01",
            CASE / "runs" / f"e15-var07-{arm}-item-v101-ssh-20261002-01")


def sealed_run(path, count):
    closure, invocation = read(path / "closure.json"), read(path / "invocation.json")
    check(path.name == closure["run_id"] == invocation["run_id"], f"run ID {path.name}")
    check(sha(path / "invocation.json") == closure["invocation_sha256"],
          f"invocation seal {path.name}")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] ==
          closure["source_hashes_after"], f"source stable {path.name}")
    check(len(closure["raw"]) == count, f"raw seal count {path.name}")
    for name, info in closure["raw"].items():
        file = path / name
        check(file.exists() and file.stat().st_size == info["bytes"], f"raw length {path.name}/{name}")
        check(sha(file) == info["sha256"], f"raw SHA {path.name}/{name}")
    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0,
          f"session-0 SSH {path.name}")
    check("sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]],
          f"SSH ancestor {path.name}")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"mutex {path.name}")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
          f"preserved GUI {path.name}")
    return closure, invocation


def main():
    contract, declared = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    catalog_text = (CASES / "catalog-v2.json").read_text(encoding="utf-8-sig")
    check('"variant_id": "E15.var07"' in catalog_text and
          '"planned_delta": "ISTOH缺省/显式且高于名义"' in catalog_text,
          "catalog E15.var07 plans explicit ISTOH above nominal")
    src = {arm: CASE / ("native-input-default.json" if arm == "default" else
                        "native-input-explicit-three.json") for arm in ("default", "explicit-three")}
    check(sha(DONOR) == contract["direct_behavioral_donor"]["input_sha256"], "accepted G01 donor SHA")
    check(sha(E02) == contract["catalog_parent_prerequisite"]["input_sha256"], "accepted E02 prerequisite SHA")
    check(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "installed manual SHA")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "installed dictionary SHA")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
          "installed CLI SHA")
    for arm in src:
        check(sha(src[arm]) == contract["arms"][arm]["input_sha256"], f"source SHA {arm}")
        check(sha(src[arm]) == declared["source_sha256"][arm], f"diff source SHA {arm}")
    check(sha(DONOR) == declared["source_sha256"]["donor"], "diff donor SHA")
    dm = models(DONOR)
    mm = {arm: models(path) for arm, path in src.items()}
    for arm, key in [("default", "donor_to_default"), ("explicit-three", "donor_to_explicit_three")]:
        check(set(dm) == set(mm[arm]) and len(dm) == 31, f"31 source tables {arm}")
        check(changes(dm, mm[arm]) == declared[key], f"donor exact delta {arm}")
    check(changes(mm["default"], mm["explicit-three"]) == declared["default_to_explicit_three"],
          "arm exact ISTOH/description delta")
    for arm in src:
        item = rows(mm[arm]["Item"])[0]
        depot = next(r for r in rows(mm[arm]["StockAllocation"]) if r["STID"] == "DEPOT-01")
        check(item["TRACK"] == "Y", f"tracked item source {arm}")
        check(depot["STSIZ"] == 4 and depot["ROSIZ"] == 2 and
              depot["ISTOH"] == (None if arm == "default" else 3),
              f"depot reorder source {arm}")
        if arm == "explicit-three":
            check(depot["STSIZ"] - depot["ROSIZ"] < depot["ISTOH"] < depot["STSIZ"],
                  "explicit ISTOH is above reorder point but below nominal STSIZ")

    out = {}
    for arm in src:
        native, selected = run_paths(arm)
        nc, ni = sealed_run(native, 12)
        sc, si = sealed_run(selected, 2)
        source_files = {
            "input": src[arm], "parent": DONOR, "catalog_parent": E02,
            "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
            "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "simlox_exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY,
        }
        for key, path in source_files.items():
            check(nc["source_hashes_before"][key] == sha(path), f"native source pin {arm}/{key}")
        check(nc["source_hashes_before"]["python"] == ni["python_sha256"], f"Python runtime pin {arm}")
        check(sha(native / "input.json") == sha(src[arm]), f"raw native input {arm}")
        selected_sources = {
            "sxo": native / "model.sxo",
            "settings": CASE / "runs/report-settings/item-position-results.sxs",
            "exe": EXE, "settings_builder": CASE / "make_report_settings.py",
            "runner": CASE / "report_native_ssh.ps1",
        }
        for key, path in selected_sources.items():
            check(sc["source_hashes_before"][key] == sha(path), f"selected source pin {arm}/{key}")
        check(si["source_run_id"] == native.name and
              si["source_closure_sha256"] == sha(native / "closure.json"),
              f"selected report links native closure {arm}")
        check(sc["exit_code"] == 0 and sc["error"] is None, f"selected report success {arm}")
        steps = read(native / "steps.json")
        check([x["name"] for x in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"],
              f"five ordered native steps {arm}")
        for step in steps:
            check(step["exit_code"] == 0 and step["status"] in {"completed", "calc_observed"},
                  f"native step {arm}/{step['name']}")
        exported = models(native / "roundtrip-raw.json")
        check(set(exported) >= set(mm[arm]), f"native export table coverage {arm}")
        populated = [name for name, table in mm[arm].items() if any(i["rows"] for i in table["instances"])]
        check(len(populated) == 21, f"21 populated authored tables {arm}")
        for name in populated:
            check(mm[arm][name]["columns"] == exported[name]["columns"] and
                  mm[arm][name]["instances"] == exported[name]["instances"],
                  f"exact native table roundtrip {arm}/{name}")
        runlog = (native / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
              "warning #108" in runlog, f"zero conversion errors / warning108 {arm}")
        check((native / "model.sxo").stat().st_size > 4 and "Saving results" in runlog,
              f"valid native result {arm}")
        event = (native / "model.log").read_text(encoding="utf-8-sig")
        rr = reports(native / "report-raw.json")
        ir = reports(selected / "item-report-raw.json")
        check({"ResultSummary", "SystemResults", "StockTotalResults"} <= set(rr),
              f"default report tables {arm}")
        check({"ItemResults", "ItemResultsTotal", "MissionResults"} <= set(ir),
              f"selected item/mission tables {arm}")
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            check(ir[name]["columns"] == rr[name]["columns"] and
                  rows(ir[name]) == rows(rr[name]),
                  f"selected/default report reconciliation {arm}/{name}")
        system, stock, itemrows = rows(rr["SystemResults"]), rows(rr["StockTotalResults"]), rows(ir["ItemResults"])
        check(len(system) == len(stock) == len(itemrows) == 72, f"72 half-hour bins {arm}")
        for idx, (sy, st) in enumerate(zip(system, stock)):
            hour = idx / 2
            operating = any(start <= hour < end for start, end in [(8, 10), (20, 22), (32, 34)])
            check(close(sy["STINT"], hour) and close(sy["ETINT"], hour + .5) and
                  close(st["STINT"], hour) and close(st["ETINT"], hour + .5),
                  f"system/stock bin time {arm}/{idx}")
            check(close(sy["FTMO"], int(operating)) and
                  close(sy["NSYMO"], int(operating)), f"mission occupancy {arm}/{idx}")
            check(close(sy["NFAIL"], int(hour == 9.5)), f"failure marker {arm}/{idx}")
            check(close(st["NBO"], 0) and close(st["PNB"], 1),
                  f"aggregate stock without backorders {arm}/{idx}")
        for idx, row in enumerate(itemrows):
            hour = idx / 2
            expected = (4 if hour < 10 else 3) if arm == "default" else (3 if hour < 10 else 2 if hour < 11 else 4)
            check(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01" and
                  close(row["STINT"], hour) and close(row["ETINT"], hour + .5),
                  f"depot bin identity/time {arm}/{idx}")
            check(close(row["STSZ"], 4), f"depot nominal four {arm}/{idx}")
            check(close(row["STOHA"], expected), f"depot physical on-hand {arm}/{idx}")
            check(close(row["NBO"], 0), f"depot no backorders {arm}/{idx}")
        summary = rows(rr["ResultSummary"])[0]
        check(summary["NREP"] == 1 and close(summary["MSUF"], 2 / 3), f"summary outcomes {arm}")
        check(close(sum(float(r["FTMO"] or 0) * .5 for r in system), 6), f"six flight hours {arm}")
        check(system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0,
              f"terminal ready and no aggregate BO {arm}")
        check("Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in event and
              "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in event,
              f"failure and local replacement readiness {arm}")
        for mid, start, end in [(0, 8, 10), (1, 20, 22), (2, 32, 34)]:
            check(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,{mid}> mission starting" in event,
                  f"mission starts {arm}/{mid}")
            outcome = "aborted mission completed" if mid == 0 else "mission success"
            check(f"Time: {end} <BASIC-MISSION,TEACH-UNIT,0,0,{mid}> {outcome}" in event,
                  f"mission outcome {arm}/{mid}")
        out[arm] = {"native": native, "selected": selected, "event": event,
                    "report": rr, "items": itemrows, "closure": nc, "selected_closure": sc}

    a, b = out["default"], out["explicit-three"]
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        check(a["report"][name] == b["report"][name], f"matched business report {name}")
    for arm, data in out.items():
        event = data["event"]
        base_item, mounted = ((4, 5) if arm == "default" else (3, 4))
        check(f"Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,{base_item}>" in event,
              f"local spare identity {arm}")
        check(f"Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,{mounted}>" in event,
              f"mounted discarded DU identity {arm}")
        check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>" in event and
              "Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0>" in event,
              f"depot-to-base item0 replenishment {arm}")
    check("reorder task" not in a["event"].lower(), "default arm no reorder task through horizon")
    event = b["event"]
    check(event.count("reorder task 0 started") == 1 and event.count("reorder task 0 completed") == 1,
          "exactly one explicit reorder task")
    check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1" in event and
          "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1" in event,
          "explicit reorder h10-11")
    for item in (5, 6):
        check(f"Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Put back replacement item <TEACH-DU-01,0,{item}>" in event,
              f"new reorder item identity {item}")
    check(a["items"][-1]["STOHA"] == 3 and b["items"][-1]["STOHA"] == 4,
          "terminal depot stock default3/explicit4")

    result = {
        "schema": "simlox-independent-readonly-e15-var07-v101/v1",
        "passed": not FAILURES,
        "verdict": "GO: bounded explicit ISTOH stock-trigger contrast" if not FAILURES else "NO-GO: independent replay failure",
        "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS, "failures": FAILURES,
        "accepted_runs": [p.name for arm in out.values() for p in (arm["native"], arm["selected"])],
        "evidence": {arm: {
            "input_sha256": sha(src[arm]),
            "native_closure_sha256": sha(data["native"] / "closure.json"),
            "item_closure_sha256": sha(data["selected"] / "closure.json"),
            "model_log_sha256": sha(data["native"] / "model.log"),
            "item_report_sha256": sha(data["selected"] / "item-report-raw.json"),
        } for arm, data in out.items()},
        "observed": "At depot STSZ remains 4 in both arms. Default opening STOHA 4 falls to 3 at h10 with no reorder. Explicit ISTOH=3 falls to 2 at h10, initiates one two-DU order, and reaches 4 at h11 after one-hour lead; downstream mission and system/aggregate-stock reports match.",
        "catalog_scope": "The raw replay GO applies only to default ISTOH versus explicit ISTOH=3 with STSIZ=4 and reorder point STSIZ-ROSIZ=2. Catalog E15.var07 plans default versus explicit ISTOH above nominal STSIZ; this tested explicit value is below nominal. Full catalog E15.var07 acceptance is therefore NOT established.",
        "limits": [
            "One fixed seed, discardable DU, depot/base pair, stock-based ROSIZ=2, one ordinary demand, and one-hour lead; no general trigger law inferred.",
            "No time-based, concurrent, random-lead, AINST, other-stock-level, GUI-only or cross-engine claim.",
            "v1.0.0 is excluded: it had valid native outcomes but did not expose predeclared station ItemResults because Item.TRACK was unset.",
        ],
    }
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": CHECKS, "failures": FAILURES,
                      "verdict_json": str(OUT)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
