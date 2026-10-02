"""Read-only E15.var07 above-nominal replay; no author-code imports or SIMLOX calls."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent
CASES = CASE.parent
PARENT = CASES / "E15-var07-explicit-istoh-v1.0.1"
PARENT_SOURCE = PARENT / "native-input-default.json"
PARENT_NATIVE = PARENT / "runs/e15-var07-default-v101-ssh-20261002-01"
PARENT_ITEM = PARENT / "runs/e15-var07-default-item-v101-ssh-20261002-01"
NATIVE = CASE / "runs/e15-var07-above-nominal-v100-ssh-20261002-01"
ITEM = CASE / "runs/e15-var07-above-nominal-item-v100-ssh-20261002-01"
SOURCE = CASE / "native-input.json"
OUT = CASE / "independent-verdict.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
E02 = CASES / "E02-zero-stock-local-backorder-v1.0.0/native-input.json"
CHECKS = 0
FAILURES: list[str] = []


def check(ok, name):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(name)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path, kind):
    return {x["name"]: x for x in read(path)[kind]["tables"]}


def rows(table):
    cols = [x["name"] for x in table["columns"]]
    return [dict(zip(cols, row)) for instance in table["instances"] for row in instance["rows"]]


def near(a, b, tol=1e-5):
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=tol)


def seal(path, expected_raw):
    c, i = read(path / "closure.json"), read(path / "invocation.json")
    check(path.name == c["run_id"] == i["run_id"], f"run identity {path.name}")
    check(sha(path / "invocation.json") == c["invocation_sha256"], f"invocation SHA {path.name}")
    check(i["source_hashes_before"] == c["source_hashes_before"] == c["source_hashes_after"],
          f"source stability {path.name}")
    check(len(c["raw"]) == expected_raw, f"raw count {path.name}")
    for filename, evidence in c["raw"].items():
        file = path / filename
        check(file.exists() and file.stat().st_size == evidence["bytes"],
              f"raw byte length {path.name}/{filename}")
        check(sha(file) == evidence["sha256"], f"raw SHA {path.name}/{filename}")
    check(i["execution_mode"] == "ssh_cli_v1" and i["session_id"] == 0,
          f"session-0 SSH {path.name}")
    check("sshd.exe" in [x.lower() for x in i["ssh_ancestor_names"]],
          f"SSH ancestor {path.name}")
    check(i["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"mutex {path.name}")
    check(i["gui"]["pid"] == 13340 and i["gui"]["session_id"] == 1,
          f"preserved GUI identity {path.name}")
    return c, i


def source_delta(parent, child):
    delta = []
    for name in parent:
        a, b = parent[name], child[name]
        check(a["columns"] == b["columns"], f"source columns {name}")
        ar, br = rows(a), rows(b)
        check(len(ar) == len(br), f"source row count {name}")
        for index, (before, after) in enumerate(zip(ar, br)):
            for key, value in before.items():
                if value != after[key]:
                    delta.append({"table": name, "row": index, "field": key,
                                  "before": value, "after": after[key]})
    return sorted(delta, key=lambda x: (x["table"], x["row"], x["field"]))


def main():
    contract, declared = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(PARENT_SOURCE) == contract["parent"]["input_sha256"] == declared["parent_sha256"],
          "accepted default parent source SHA")
    check(sha(PARENT_NATIVE / "closure.json") == contract["parent"]["native_closure_sha256"],
          "accepted parent native closure SHA")
    check(sha(PARENT_ITEM / "closure.json") == contract["parent"]["selected_item_report_closure_sha256"],
          "accepted parent item closure SHA")
    check(sha(E02) == contract["instructional_prerequisite"]["input_sha256"], "E02 prerequisite SHA")
    check(sha(SOURCE) == contract["native_input_sha256"] == declared["child_sha256"],
          "child source SHA")
    check(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "installed manual SHA")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "installed dictionary SHA")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
          "installed CLI SHA")
    parent_model, child_model = tables(PARENT_SOURCE, "model"), tables(SOURCE, "model")
    check(set(parent_model) == set(child_model) and len(child_model) == 31,
          "same 31 business tables")
    check(source_delta(parent_model, child_model) ==
          sorted(declared["changes"], key=lambda x: (x["table"], x["row"], x["field"])),
          "exact two-cell parent-child delta")
    check(sum(parent_model[k] == child_model[k] for k in parent_model) == 29,
          "29 unchanged tables")
    pstock = next(x for x in rows(parent_model["StockAllocation"]) if x["STID"] == "DEPOT-01")
    cstock = next(x for x in rows(child_model["StockAllocation"]) if x["STID"] == "DEPOT-01")
    check(pstock["ISTOH"] is None and cstock["ISTOH"] == 6 and
          pstock["STSIZ"] == cstock["STSIZ"] == 4 and
          pstock["ROSIZ"] == cstock["ROSIZ"] == 2,
          "isolated above-nominal ISTOH6 source")

    nc, ni = seal(NATIVE, 12)
    ic, ii = seal(ITEM, 2)
    pc, pi = seal(PARENT_NATIVE, 12)
    qc, qi = seal(PARENT_ITEM, 2)
    native_files = {
        "input": SOURCE, "parent": PARENT_SOURCE, "catalog_parent": E02,
        "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
        "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
        "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
        "simlox_exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY,
    }
    for key, path in native_files.items():
        check(nc["source_hashes_before"][key] == sha(path), f"native source pin {key}")
    check(nc["source_hashes_before"]["python"] == ni["python_sha256"],
          "native Python runtime pin")
    item_files = {
        "sxo": NATIVE / "model.sxo", "settings": CASE / "runs/report-settings/item-position-results.sxs",
        "exe": EXE, "settings_builder": CASE / "make_report_settings.py",
        "runner": CASE / "report_native_ssh.ps1",
    }
    for key, path in item_files.items():
        check(ic["source_hashes_before"][key] == sha(path), f"selected item source pin {key}")
    check(ii["source_run_id"] == NATIVE.name and
          ii["source_closure_sha256"] == sha(NATIVE / "closure.json"),
          "selected item bound to native closure")
    check(qi["source_closure_sha256"] == sha(PARENT_NATIVE / "closure.json"),
          "parent selected report bound to parent native closure")
    check(ic["exit_code"] == 0 and ic["error"] is None, "selected item export completed")
    check(sha(NATIVE / "input.json") == sha(SOURCE), "raw input matches frozen source")
    steps = read(NATIVE / "steps.json")
    check([s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"],
          "five native steps in order")
    for step in steps:
        check(step["exit_code"] == 0 and step["status"] in {"completed", "calc_observed"} and
              step["gui_preserved"] is True, f"native step success and GUI {step['name']}")
    exported = tables(NATIVE / "roundtrip-raw.json", "model")
    populated = [name for name, t in child_model.items() if any(i["rows"] for i in t["instances"])]
    check(len(populated) == 21 and set(exported) >= set(child_model),
          "21 authored row-containing tables and native table coverage")
    for name in populated:
        check(child_model[name]["columns"] == exported[name]["columns"] and
              child_model[name]["instances"] == exported[name]["instances"],
              f"exact native roundtrip {name}")
    runlog = (NATIVE / "run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
          "warning #108" in runlog, "zero converter errors and only #108 warning")
    check("Saving results" in runlog and (NATIVE / "model.sxo").stat().st_size > 4,
          "valid nontrivial SXO")

    child_default = tables(NATIVE / "report-raw.json", "report")
    parent_default = tables(PARENT_NATIVE / "report-raw.json", "report")
    child_selected = tables(ITEM / "item-report-raw.json", "report")
    parent_selected = tables(PARENT_ITEM / "item-report-raw.json", "report")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        check(child_default[name] == parent_default[name], f"matched parent default report {name}")
        check(child_selected[name]["columns"] == child_default[name]["columns"] and
              rows(child_selected[name]) == rows(child_default[name]),
              f"selected versus default child report {name}")
    for name in ("MissionResults", "MissionResultsTotal", "FixedMissionResults",
                 "FixedMissionResultsTotal"):
        check(rows(child_selected[name]) == rows(parent_selected[name]),
              f"parent-child selected mission report {name}")
    cr, pr = rows(child_selected["ItemResults"]), rows(parent_selected["ItemResults"])
    system = rows(child_default["SystemResults"])
    stock = rows(child_default["StockTotalResults"])
    check(len(cr) == len(pr) == len(system) == len(stock) == 72,
          "72 selected item and default System/Stock bins")
    for idx, (a, b, sy, st) in enumerate(zip(cr, pr, system, stock)):
        hour = idx / 2
        child_onhand = 6 if hour < 10 else 5
        parent_onhand = 4 if hour < 10 else 3
        check(a["IID"] == b["IID"] == "TEACH-DU-01" and
              a["STID"] == b["STID"] == "DEPOT-01" and
              all(near(r["STINT"], hour) and near(r["ETINT"], hour + .5)
                  for r in (a, b, sy, st)), f"half-hour row identity/time {idx}")
        check(near(a["STSZ"], 4) and near(b["STSZ"], 4), f"nominal depot four {idx}")
        check(near(a["STOHA"], child_onhand) and near(b["STOHA"], parent_onhand) and
              near(a["STOHA"] - b["STOHA"], 2), f"above-nominal physical stock {idx}")
        check(near(a["NBO"], 0) and near(b["NBO"], 0) and near(st["NBO"], 0),
              f"zero depot/aggregate backorder {idx}")
        operating = any(start <= hour < end for start, end in [(8, 10), (20, 22), (32, 34)])
        check(near(sy["FTMO"], int(operating)) and near(sy["NSYMO"], int(operating)),
              f"mission occupancy {idx}")
    item_total = rows(child_selected["ItemResultsTotal"])[0]
    check(item_total["NRO"] == 0 and item_total["STSZ"] == 4 and
          5 < item_total["STOHA"] < 6, "item total no reorder and average (not terminal) stock")
    summary = rows(child_default["ResultSummary"])[0]
    check(summary["NREP"] == 1 and near(summary["MSUF"], 2 / 3),
          "one replication and two of three missions successful")
    check(near(sum(float(x["FTMO"] or 0) * .5 for x in system), 6) and
          system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0,
          "six flight hours and terminal ready/no backorder")

    child_log = (NATIVE / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (PARENT_NATIVE / "model.log").read_text(encoding="utf-8-sig")
    check("reorder task" not in child_log.lower() and "reorder task" not in parent_log.lower(),
          "no reorder in either arm")
    for log, initial, local, mounted, label in [
        (child_log, 6, 6, 7, "child"), (parent_log, 4, 4, 5, "parent")
    ]:
        check(f"Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: {initial} Items:" in log,
              f"physical opening depot stock {label}")
        check(f"Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,{local}>" in log and
              "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>" in log,
              f"local/depot issue {label}")
        check(f"Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,{mounted}>" in log and
              "Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0>" in log,
              f"discard and base replenishment {label}")
        check("Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in log and
              "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in log,
              f"first mission failure and readiness {label}")
        for number, start, end in [(0, 8, 10), (1, 20, 22), (2, 32, 34)]:
            check(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,{number}> mission starting" in log,
                  f"mission launch {label}/{number}")
            outcome = "aborted mission completed" if number == 0 else "mission success"
            check(f"Time: {end} <BASIC-MISSION,TEACH-UNIT,0,0,{number}> {outcome}" in log,
                  f"mission outcome {label}/{number}")
    check(cr[-1]["STOHA"] == 5 and pr[-1]["STOHA"] == 3,
          "physical terminal depot stock 5 versus 3")

    result = {
        "schema": "simlox-independent-readonly-e15-var07-above-nominal/v1",
        "passed": not FAILURES,
        "verdict": "GO: bounded above-nominal ISTOH=6 contrast" if not FAILURES else
                   "NO-GO: independent replay failure",
        "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS,
        "failures": FAILURES,
        "runs": [NATIVE.name, ITEM.name],
        "comparison_runs": [PARENT_NATIVE.name, PARENT_ITEM.name],
        "evidence": {
            "child_source_sha256": sha(SOURCE),
            "native_closure_sha256": sha(NATIVE / "closure.json"),
            "selected_item_closure_sha256": sha(ITEM / "closure.json"),
            "child_item_report_sha256": sha(ITEM / "item-report-raw.json"),
            "parent_item_report_sha256": sha(PARENT_ITEM / "item-report-raw.json"),
        },
        "finding": "The only business change is depot ISTOH omitted to 6 above nominal STSIZ4. At h0-10 the child depot has six physical items versus four in the parent; one h10 issue leaves five versus three through h36. Neither arm orders because both remain above reorder point two. Three mission outcomes and default System/Stock summaries match.",
        "limits": [
            "One DU, depot, seed, demand, stock-based ROSIZ2, fixed lead1 and 36-hour horizon; no arbitrary high-ISTOH or reorder-trigger law.",
            "ItemResultsTotal.STOHA is an interval average, not terminal physical stock.",
            "AINST, periodic ordering, multiple orders, random lead, transfers, GUI-only behavior and cross-engine parity untested.",
        ],
    }
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": CHECKS,
                      "failures": FAILURES, "verdict_json": str(OUT)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
