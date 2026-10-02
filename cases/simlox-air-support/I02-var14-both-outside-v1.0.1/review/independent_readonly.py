"""Independent, read-only replay of the I02.var14 v1.0.1 native evidence.

Uses only Python's standard library.  Never imports the case builder or validator.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
CASES = CASE.parent
PARENT = CASES / "I02-var01-in-transfer-v1.0.2"
PROBE = CASES / "I02-var14-both-outside-v1.0.0"
NATIVE = CASE / "runs/i02-var14-both-outside-v101-ssh-20261002-01"
SELECTED = CASE / "runs/i02-var14-depot-item-v101-ssh-20261002-01"
PARENT_NATIVE = PARENT / "runs/i02-var01-in-v102-ssh-20261002-01"
PARENT_SELECTED = PARENT / "runs/i02-var01-item-results-v102-ssh-20261002-01"
REPORT = HERE / "independent-readonly-2026-10-02.json"
FAILURES: list[str] = []
CHECKS = 0


def check(ok: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    # SIMLOX's native JSON export may contain trailing commas.
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def tables(doc):
    return {t["name"]: t for t in doc["model"]["tables"]}


def report_tables(path: Path):
    return {t["name"]: t for t in read(path)["report"]["tables"]}


def rows(table):
    return [dict(zip([c["name"] for c in table["columns"]], r))
            for instance in table["instances"] for r in instance["rows"]]


def close(a, b, tol=1e-5):
    return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)


def closure(run: Path, count: int):
    c = read(run / "closure.json")
    i = read(run / "invocation.json")
    check(c["run_id"] == run.name == i["run_id"], f"run identity {run.name}")
    check(sha(run / "invocation.json") == c["invocation_sha256"], f"invocation seal {run.name}")
    check(c["source_hashes_before"] == c["source_hashes_after"], f"stable source {run.name}")
    check(i["source_hashes_before"] == c["source_hashes_before"], f"invocation source {run.name}")
    check(len(c["raw"]) == count, f"raw count {run.name}")
    for name, evidence in c["raw"].items():
        f = run / name
        check(f.exists() and f.stat().st_size == evidence["bytes"], f"raw bytes {run.name}/{name}")
        check(sha(f) == evidence["sha256"], f"raw SHA {run.name}/{name}")
    check(i["execution_mode"] == "ssh_cli_v1" and i["session_id"] == 0,
          f"SSH session 0 {run.name}")
    check("sshd.exe" in [x.lower() for x in i["ssh_ancestor_names"]], f"SSH ancestor {run.name}")
    check(i["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"mutex {run.name}")
    check(i["gui"]["pid"] == 13340 and i["gui"]["session_id"] == 1,
          f"preserved GUI identity {run.name}")
    return c, i


def main():
    contract = read(CASE / "contract.json")
    source = read(CASE / "native-input.json")
    parent = read(PARENT / "native-input.json")
    diff = read(CASE / "exact-diff.json")
    check(sha(PARENT / "native-input.json") == contract["direct_parent"]["source_sha256"], "parent SHA")
    check(sha(CASE / "native-input.json") == contract["input_sha256"], "child SHA")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "diff SHA")
    check(diff["parent_sha256"] == contract["direct_parent"]["source_sha256"], "diff parent")
    check(diff["input_sha256"] == contract["input_sha256"], "diff input")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    exe = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
    for path, key in [(manual, "manual_pdf"), (dictionary, "table_dictionary"), (exe, "simlox_exe")]:
        check(sha(path) == contract["installed_source_sha256"][key], f"installed {key} SHA")
    pt, ct = tables(parent), tables(source)
    check(set(pt) == set(ct) and len(pt) == 32, "32 source tables")
    check({n for n in pt if pt[n] != ct[n]} == {"ItemTransfer", "ProblemDescription"},
          "exact two-table delta")
    for n in pt.keys() - {"ItemTransfer", "ProblemDescription"}:
        check(pt[n] == ct[n], f"unchanged source table {n}")
    transfer_before, transfer_after = rows(pt["ItemTransfer"]), rows(ct["ItemTransfer"])
    check(len(transfer_before) == len(transfer_after) == 1, "single transfer row")
    check(transfer_before[0]["STTID"] == "DEPOT-01" and transfer_after[0]["STTID"] == "<OUTSIDE>",
          "STTID changed from depot to outside")
    check(transfer_before[0]["STFID"] == transfer_after[0]["STFID"] == "<OUTSIDE>",
          "both child endpoints outside")
    check(transfer_before[0] | {"STTID": "<OUTSIDE>"} == transfer_after[0],
          "only business cell changed")
    pdesc_before, pdesc_after = rows(pt["ProblemDescription"]), rows(ct["ProblemDescription"])
    check(len(pdesc_before) == len(pdesc_after) == 1 and
          {k for k in pdesc_before[0] if pdesc_before[0][k] != pdesc_after[0][k]} == {"PDESC"},
          "description-only provenance delta")
    check(sha(PROBE / "native-input.json") == sha(CASE / "native-input.json"),
          "excluded v1.0.0 probe uses same business source")

    native, inv = closure(NATIVE, 12)
    selected, sinv = closure(SELECTED, 2)
    parent_native, pinv = closure(PARENT_NATIVE, 12)
    parent_selected, psinv = closure(PARENT_SELECTED, 2)
    for key, path in {
        "input": CASE / "native-input.json", "parent": PARENT / "native-input.json",
        "contract": CASE / "contract.json", "manual": manual, "dictionary": dictionary,
        "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
        "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
        "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": exe,
    }.items():
        check(native["source_hashes_before"][key] == sha(path), f"native source pin {key}")
    check(native["source_hashes_before"]["python"] == inv["python_sha256"], "Python runtime pin")
    for key, path in {"sxo": NATIVE / "model.sxo",
                      "settings": CASE / "runs/report-settings/item-position-results.sxs",
                      "exe": exe, "runner": CASE / "report_native_ssh.ps1"}.items():
        check(selected["source_hashes_before"][key] == sha(path), f"selected report source {key}")
    check(sinv["source_run_id"] == NATIVE.name and
          sinv["source_closure_sha256"] == sha(NATIVE / "closure.json"),
          "selected report bound to native closure")
    check(parent_selected["source_hashes_before"]["sxo"] == sha(PARENT_NATIVE / "model.sxo") and
          psinv["source_closure_sha256"] == sha(PARENT_NATIVE / "closure.json"),
          "accepted parent selected report bound to native closure")
    check(sha(NATIVE / "input.json") == contract["input_sha256"], "raw child input")
    check(sha(PARENT_NATIVE / "input.json") == contract["direct_parent"]["source_sha256"],
          "raw parent input")
    steps = read(NATIVE / "steps.json")
    check([s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"], "five native steps")
    for s in steps:
        check(s["exit_code"] == 0 and s["status"] in {"completed", "calc_observed"},
              f"native step {s['name']}")
    check(selected["exit_code"] == 0 and selected["error"] is None, "selected report success")

    exported = tables(read(NATIVE / "roundtrip-raw.json"))
    check(set(exported) >= set(ct), "native export contains source tables")
    populated = [n for n, t in ct.items() if any(i["rows"] for i in t["instances"])]
    check(len(populated) == 22, "22 populated source tables")
    for n in populated:
        check(ct[n]["columns"] == exported[n]["columns"] and
              ct[n]["instances"] == exported[n]["instances"], f"exact native roundtrip {n}")
    log = (NATIVE / "run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in log,
          "zero converter errors; warning count one")
    check("warning #108" in log and "Saving results" in log, "warning and result saved")
    check((NATIVE / "model.sxo").stat().st_size > 4, "valid nontrivial SXO")
    event = (NATIVE / "model.log").read_text(encoding="utf-8-sig")
    check(not any("Item transfer" in line or "ItemTransfer" in line
                  for line in event.splitlines() if line.startswith("Time: 4 ")),
          "no h4 scheduled transfer event")
    check(not any(line.startswith("Time: 4 ") for line in event.splitlines()),
          "no h4 event at all")
    for fragment in [
        "Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated",
        "Level: 1 Items:<TEACH-LRU-01,0,0>",
        "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting",
        "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted",
        "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed",
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives",
        "item requiring maintenance is <TEACH-LRU-01,0,1>",
        "Time: 12.1667 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,1>",
        "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,1>",
        "Level: 1 Items:<TEACH-LRU-01,0,1>",
        "Time: 12.3333 <TEACH-AIR-01,BASE-01,0> System ready",
        "Time: 20 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting",
        "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success",
        "Time: 32 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting",
        "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success",
        "Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1",
    ]:
        check(fragment in event, f"native event {fragment[:64]}")

    cr = report_tables(NATIVE / "report-raw.json")
    pr = report_tables(PARENT_NATIVE / "report-raw.json")
    check(set(cr) == set(pr), "matched default report tables")
    for n in set(cr) - {"ProblemDescription"}:
        check(cr[n] == pr[n], f"parent-child default report equality {n}")
    check(len(rows(cr["SystemResults"])) == len(rows(cr["StockTotalResults"])) == 72,
          "72 default System and Stock bins")
    summary = rows(cr["ResultSummary"])[0]
    check(summary["NREP"] == 1 and close(summary["MSUF"], 2 / 3), "summary replication and mission success factor")
    check(close(sum(float(r["FTMO"] or 0) * .5 for r in rows(cr["SystemResults"])), 6),
          "six aircraft flight hours")
    check(rows(cr["SystemResults"])[-1]["NSYRY"] == 1 and
          rows(cr["StockTotalResults"])[-1]["NBO"] == 0,
          "terminal ready aircraft and no aggregate backorder")

    ci = report_tables(SELECTED / "item-report-raw.json")
    pi = report_tables(PARENT_SELECTED / "item-report-raw.json")
    child_items, parent_items = rows(ci["ItemResults"]), rows(pi["ItemResults"])
    check(len(child_items) == len(parent_items) == 72, "72 depot item bins each")
    for idx, (a, b) in enumerate(zip(child_items, parent_items)):
        start = idx / 2
        check(a["IID"] == b["IID"] == "TEACH-LRU-01" and
              a["STID"] == b["STID"] == "DEPOT-01" and
              close(a["STINT"], start) and close(a["ETINT"], start + .5) and
              close(b["STINT"], start) and close(b["ETINT"], start + .5),
              f"depot item bin identity/time {idx}")
        difference = 0 if start < 4 else 1
        check(close(float(b["STSZ"]) - float(a["STSZ"]), difference),
              f"depot nominal parent minus child {idx}")
        check(close(float(b["STOHA"]) - float(a["STOHA"]), difference),
              f"depot on-hand parent minus child {idx}")
        check(a["NBO"] == b["NBO"] == 0, f"depot aggregate NBO {idx}")
    check(close(child_items[0]["STSZ"], 1) and close(child_items[8]["STSZ"], 1) and
          close(parent_items[8]["STSZ"], 2), "h4 absent IN changes nominal depot level")
    check(close(child_items[20]["STOHA"], 0) and close(parent_items[20]["STOHA"], 1),
          "h10 ordinary issue reduces child depot on-hand to zero")
    check(close(child_items[-1]["STSZ"], 1) and close(child_items[-1]["STOHA"], 1),
          "child terminal depot stock one")
    check("both ItemTransfer endpoints cannot be <OUTSIDE>" in contract["manual_basis"],
          "manual prohibition explicitly pinned")

    result = {
        "schema": "simlox-independent-readonly-i02-var14-v101/v1",
        "passed": not FAILURES,
        "verdict": ("GO: bounded installed-CLI counterexample to manual double-OUTSIDE prohibition"
                    if not FAILURES else "NO-GO: independent evidence replay failed"),
        "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS,
        "failures": FAILURES,
        "accepted_runs": [NATIVE.name, SELECTED.name],
        "parent_runs": [PARENT_NATIVE.name, PARENT_SELECTED.name],
        "evidence": {
            "child_source_sha256": sha(CASE / "native-input.json"),
            "native_closure_sha256": sha(NATIVE / "closure.json"),
            "selected_closure_sha256": sha(SELECTED / "closure.json"),
            "native_report_sha256": sha(NATIVE / "report-raw.json"),
            "depot_item_report_sha256": sha(SELECTED / "item-report-raw.json"),
            "parent_native_report_sha256": sha(PARENT_NATIVE / "report-raw.json"),
            "parent_depot_item_report_sha256": sha(PARENT_SELECTED / "item-report-raw.json"),
        },
        "observed": "Authored and roundtripped h4 double-<OUTSIDE> row converts with zero errors; no h4 event or depot increase. Parent IN increases depot STSZ and STOHA by one in all h4-36 bins. The child has the same default system, stock and summary tables as the parent, while using a different physical initial item identity.",
        "limits": [
            "One installed SIMLOX CLI build, model, seed and one-unit scheduled row; the manual still prohibits this source form.",
            "No general silent-handling guarantee, modeling recommendation, GUI behavior or cross-engine conclusion.",
            "The local v1.0.0 rejection probe is excluded: its conversion unexpectedly succeeded but its old runner stopped before report and roundtrip checks.",
        ],
    }
    REPORT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": CHECKS, "failures": FAILURES,
                      "report": str(REPORT)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
