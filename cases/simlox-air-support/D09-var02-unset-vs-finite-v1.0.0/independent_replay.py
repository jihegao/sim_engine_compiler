"""Independent read-only replay of D09.var02 unset versus finite NCFTL."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent
CASES = CASE.parent
PARENT = CASES / "D09-var01-calendar-vs-operational-v1.0.0"
D08 = CASES / "D08-var03-criticality-v1.0.0"
PARENT_SOURCE = PARENT / "native-input-calendar.json"
PARENT_RUN = PARENT / "runs/d09-var01-calendar-v100-ssh-20261002-01"
D08_SOURCE = D08 / "native-input-traditional.json"
D08_RUN = D08 / "runs/d08-var03-traditional-v100-ssh-20261002-01"
SOURCE = CASE / "native-input-unset.json"
RUN = CASE / "runs/d09-var02-unset-v100-ssh-20261002-01"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
OUT = CASE / "independent-verdict.json"
CHECKS = 0
FAILURES: list[str] = []


def check(ok, label):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path, kind):
    return {t["name"]: t for t in read(path)[kind]["tables"]}


def rows(table):
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def near(a, b, tol=1e-4):
    return math.isclose(float(a or 0), float(b), abs_tol=tol, rel_tol=0)


def fraction(start, end, hour):
    return max(0, min(end, hour + .5) - max(start, hour)) / .5


def main():
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(PARENT_SOURCE) == contract["accepted_finite_parent"]["input_sha256"] ==
          diff["parent_input_sha256"], "accepted finite-calendar source SHA")
    check(sha(PARENT_RUN / "closure.json") ==
          contract["accepted_finite_parent"]["native_closure_sha256"],
          "accepted finite-calendar closure SHA")
    check(sha(D08_SOURCE) == contract["earlier_noncritical_prerequisite"]["input_sha256"],
          "D08 noncritical prerequisite source")
    check(sha(D08_RUN / "closure.json") ==
          contract["earlier_noncritical_prerequisite"]["native_closure_sha256"],
          "D08 noncritical prerequisite closure")
    check(sha(SOURCE) == contract["arms"]["unset_candidate"]["input_sha256"] ==
          diff["child_input_sha256"], "unset source SHA")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen diff SHA")
    check(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "manual SHA")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary SHA")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
          "installed CLI SHA")
    pm, cm = tables(PARENT_SOURCE, "model"), tables(SOURCE, "model")
    check(set(pm) == set(cm) and len(pm) == 31, "same 31 parent/child source tables")
    found = {}
    for name in pm:
        a, b = pm[name], cm[name]
        check(a["columns"] == b["columns"], f"source columns {name}")
        ar, br = rows(a), rows(b)
        check(len(ar) == len(br), f"source row count {name}")
        changes = {}
        for x, y in zip(ar, br):
            for field, value in x.items():
                if value != y[field]:
                    changes[field] = {"before": value, "after": y[field]}
        if changes:
            found[name] = changes
    check(found == diff["changed_tables"] and
          sum(pm[name] == cm[name] for name in pm) == diff["identical_tables"],
          "exact NCFTL and description delta")
    item = rows(cm["Item"])[0]
    check(item["NCFTL"] is None and item["NCFTT"] == "CALENDAR" and item["CRIT"] == 0 and
          rows(cm["StockAllocation"])[0]["STSIZ"] == 0,
          "unset tolerance with fixed calendar token and zero stock")

    closure, invocation = read(RUN / "closure.json"), read(RUN / "invocation.json")
    check(closure["run_id"] == invocation["run_id"] == RUN.name, "run identity")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation SHA")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] ==
          closure["source_hashes_after"], "stable run source pins")
    check(len(closure["raw"]) == 12, "12 raw seals")
    for name, spec in closure["raw"].items():
        path = RUN / name
        check(path.exists() and path.stat().st_size == spec["bytes"], f"raw length {name}")
        check(sha(path) == spec["sha256"], f"raw SHA {name}")
    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and
          "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],
          "session-0 SSH provenance")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
          "mutex and preserved GUI")
    source_files = {
        "input": SOURCE, "parent": PARENT_SOURCE, "parent_closure": PARENT_RUN / "closure.json",
        "prerequisite": D08_SOURCE, "prerequisite_closure": D08_RUN / "closure.json",
        "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
        "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
        "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
        "simlox_exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY,
    }
    for key, path in source_files.items():
        check(closure["source_hashes_before"][key] == sha(path), f"source seal {key}")
    check(closure["source_hashes_before"]["python"] == invocation["python_sha256"],
          "Python runtime pin")
    check(sha(RUN / "input.json") == sha(SOURCE), "raw input equals frozen source")
    steps = read(RUN / "steps.json")
    check([s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"],
          "five ordered native steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["status"] in {"completed", "calc_observed"} and
              step["gui_preserved"] is True, f"native step success and GUI {step['name']}")
    exported = tables(RUN / "roundtrip-raw.json", "model")
    populated = [name for name, t in cm.items() if any(inst["rows"] for inst in t["instances"])]
    check(len(populated) == 18 and set(exported) >= set(cm), "18 authored populated tables")
    for name in populated:
        check(cm[name]["columns"] == exported[name]["columns"] and
              cm[name]["instances"] == exported[name]["instances"],
              f"exact native roundtrip {name}")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
          "warning #108" in runlog, "zero converter errors and warning108")
    check("Saving results" in runlog and (RUN / "model.sxo").stat().st_size > 4,
          "valid nontrivial SXO/report")

    rr = tables(RUN / "report-raw.json", "report")
    parent_report = tables(PARENT_RUN / "report-raw.json", "report")
    check({"ResultSummary", "SystemResults", "StockTotalResults"} <= set(rr),
          "native report tables")
    sy, st = rows(rr["SystemResults"]), rows(rr["StockTotalResults"])
    psy, pst = rows(parent_report["SystemResults"]), rows(parent_report["StockTotalResults"])
    check(len(sy) == len(st) == len(psy) == len(pst) == 72,
          "72 child and accepted control report bins")
    for idx, (a, b, p, q) in enumerate(zip(sy, st, psy, pst)):
        hour = idx / 2
        check(all(near(row["STINT"], hour) and near(row["ETINT"], hour + .5)
                  for row in (a, b, p, q)), f"half-hour report interval {idx}")
        flight = int(any(start <= hour < end for start, end in [(8, 10), (20, 22), (32, 34)]))
        check(near(a["NSYMO"], flight) and near(a["FTMO"], flight),
              f"three successful mission occupancy {idx}")
        check(near(a["NFAIL"], int(hour == 9.5)), f"one fault report marker {idx}")
        ready = int(not any(start <= hour < end for start, end in [(7, 10), (19, 22), (31, 34)]))
        check(near(a["NSYRY"], ready) and near(a["NSYA"], 1),
              f"aircraft ready/available despite pending task {idx}")
        check(near(a["NSYRP"], 0) and near(a["NSYWI"], 0),
              f"no physical system repair/wait report {idx}")
        check(near(b["NBO"], int(hour >= 10)) and near(b["PNB"], int(hour < 10)),
              f"unresolved stock backorder {idx}")
        check(near(p["NSYRP"], fraction(10.0829, 10.3329, hour) +
                   fraction(11.3329, 11.5829, hour)),
              f"finite control physical repair contrasted {idx}")
        check(near(q["NBO"], fraction(10, 11.3329, hour)),
              f"finite control backorder clearance contrasted {idx}")
    summary = rows(rr["ResultSummary"])[0]
    check(summary["NREP"] == 1 and near(summary["MSUF"], 1),
          "all three child missions successful summary")
    check(near(sum((x["FTMO"] or 0) * .5 for x in sy), 6) and
          near(sum((x["NBO"] or 0) * .5 for x in st), 26),
          "six flight hours and 26 backorder-hours")
    check(near(sy[-1]["NSYRY"], 1) and near(st[-1]["NBO"], 1),
          "terminal ready aircraft with unresolved backorder")

    event = (RUN / "model.log").read_text(encoding="utf-8-sig")
    finite_event = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    for fragment in [
        "Time: 9.8829 <TEACH-AIR-01,0> noncritical random failure added",
        "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives",
        "item requiring maintenance is <TEACH-LRU-01,0,0>",
        "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added",
        "Time: 10  system SURP task 0 on <TEACH-AIR-01,0> wait for subitem",
        "Time: 19 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> paused",
        "Time: 22 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> continued",
        "Time: 31 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> paused",
        "Time: 34 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> continued",
    ]:
        check(fragment in event, f"unset noncritical pending event {fragment[:65]}")
    for number, start, end in [(0, 8, 10), (1, 20, 22), (2, 32, 34)]:
        check(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,{number}> mission starting" in event,
              f"mission start {number}")
        check(f"Time: {end} <BASIC-MISSION,TEACH-UNIT,0,0,{number}> mission success" in event,
              f"mission success {number}")
    check("failure becomes critical" not in event and "changed to critical" not in event and
          "starts performing" not in event and "Backorder removed" not in event and
          "mission aborted" not in event,
          "no escalation, physical repair, BO clearance or abort")
    check("Time: 10.0829 <TEACH-AIR-01,0> failure becomes critical" in finite_event and
          "Time: 11.3329 <TEACH-LRU-01,0,BASE-01,0> Backorder removed" in finite_event and
          "Time: 11.5829 <TEACH-AIR-01,BASE-01,0> System ready" in finite_event,
          "accepted finite control escalation and repair")

    result = {
        "schema": "simlox-independent-readonly-d09-var02/v1",
        "passed": not FAILURES,
        "verdict": "GO: bounded unset-versus-finite NCFTL contrast" if not FAILURES else
                   "NO-GO: independent replay failed",
        "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS,
        "failures": FAILURES,
        "evidence": {
            "input_sha256": sha(SOURCE), "native_closure_sha256": sha(RUN / "closure.json"),
            "model_log_sha256": sha(RUN / "model.log"),
            "report_sha256": sha(RUN / "report-raw.json"),
            "accepted_finite_closure_sha256": sha(PARENT_RUN / "closure.json"),
        },
        "finding": "With Item.NCFTL unset and NCFTT CALENDAR unchanged, the h9.8829 noncritical LRU fault leaves SURP waiting for a zero-stock spare from h10 through h36. The task pauses at h19/h31 and resumes at h22/h34 while all three missions succeed; no critical escalation or physical repair occurs. The aircraft is ready at the horizon with one unresolved local backorder. The accepted 0.2-hour finite control escalates at h10.0829, repairs the same LRU and clears its backorder at h11.3329.",
        "limits": [
            "One aircraft/LRU/seed, 36-hour horizon, zero local stock and unset versus 0.2 calendar hours; no general infinite-tolerance law.",
            "A started waiting SURP task is not positive repair work; no item removal or stock restoration is observed in the unset arm.",
            "SystemResults.NSYRY/NSYA and StockTotalResults.NBO are distinct ledgers: terminal aircraft ready coexists with a pending backorder.",
            "GUI-only behavior and cross-engine parity untested.",
        ],
    }
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": CHECKS,
                      "failures": FAILURES, "verdict_json": str(OUT)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
