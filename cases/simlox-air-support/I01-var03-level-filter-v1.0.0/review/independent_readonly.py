"""Independent, read-only replay of the I01.var03 level/APID matrix.

Uses only the standard library and raw/source files. It never calls SIMLOX or
imports the package's builder, checker, or validator.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
AIR = CASE.parent
RUNS = CASE / "runs"
PARENT = AIR / "I01-var03-maintenance-station-v1.0.0"
DATE = "2026-10-02"
OUT = HERE / f"independent-readonly-{DATE}.json"
VARIANTS = ("basic-base", "depot-base", "basic-alternate", "depot-alternate")
RUN_ID = {v: f"i01-var03-level-{v}-v100-ssh-20261002-01" for v in VARIANTS}
ROUTE = {"basic-base": "BASE", "depot-base": "DEPOT",
         "basic-alternate": "DEPOT", "depot-alternate": "BASE"}
PARENT_RUN = {"BASE": PARENT / "runs/i01-var03-station-base-v100-ssh-20261002-01",
              "DEPOT": PARENT / "runs/i01-var03-station-depot-v100-ssh-20261002-01"}
checks = 0
failures: list[str] = []


def check(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def table(doc: dict, name: str, section: str = "model") -> dict:
    found = [t for t in doc[section]["tables"] if t["name"] == name]
    check(len(found) == 1, f"one {section}.{name} table")
    return found[0]


def rows(doc: dict, name: str, section: str = "model") -> list[list]:
    t = table(doc, name, section)
    check(len(t["instances"]) == 1, f"one {section}.{name} instance")
    return t["instances"][0]["rows"]


def event(text: str, hour: str, fragment: str, label: str) -> None:
    check(any(line.startswith(f"Time: {hour} ") and fragment in line
              for line in text.splitlines()), label)


def source_checks(contract: dict) -> dict[str, dict]:
    parent_path = PARENT / "base-input.json"
    check(digest(parent_path) == contract["direct_parent"]["sha256"], "accepted parent bytes")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    repository = AIR.parent.parent
    merged = subprocess.run(
        ["git", "show", "origin/simlox/main:cases/simlox-air-support/"
         "I01-var03-maintenance-station-v1.0.0/base-input.json"],
        cwd=repository, capture_output=True, check=False)
    check(merged.returncode == 0 and
          hashlib.sha256(merged.stdout).hexdigest() == digest(parent_path),
          "accepted parent bytes in merged origin/simlox/main")
    exact_diff = CASE / "exact-diff.json"
    check(digest(exact_diff) == contract["sources_sha256"]["exact_diff"], "exact-diff seal")
    diff = json.loads(exact_diff.read_text(encoding="utf-8"))
    check(diff["source_sha256"]["parent"] == digest(parent_path), "diff parent pin")
    check("I01-var03-maintenance-station-v1.0.0" in
          (AIR / "publication-index-v1.json").read_text(encoding="utf-8"),
          "parent in publication index")

    # Reconstruct every business table from the accepted station source.
    baseline = copy.deepcopy(parent)
    rows(baseline, "Tasks")[1][1] = "Level task"
    rows(baseline, "Tasks").append(
        ["I01-LEVEL-B", "Level task", "LRU-CM", "ALT", None])
    rows(baseline, "TaskLevel").append(["ALT", 2, None])
    rows(baseline, "MaintenanceAllocation").extend([
        ["AIR_BASIC", "LRU-CM", "ALT", "DEPOT-01", None],
        ["AIR_DEPOT", "LRU-CM", "ALT", "BASE-01", None],
    ])
    source_docs: dict[str, dict] = {}
    for variant in VARIANTS:
        path = CASE / f"{variant}-input.json"
        check(digest(path) == contract["sources_sha256"][variant], f"{variant} input seal")
        check(diff["source_sha256"][variant] == digest(path), f"{variant} diff pin")
        doc = json.loads(path.read_text(encoding="utf-8"))
        expected = copy.deepcopy(baseline)
        level = "base" if variant.endswith("base") else "alternate"
        point = "AIR_BASIC" if variant.startswith("basic") else "AIR_DEPOT"
        if level == "alternate":
            rows(expected, "Tasks")[1][3] = "ALT"
            rows(expected, "Tasks")[2][3] = "BASE"
        rows(expected, "Control")[0][3] = point
        rows(expected, "ProblemDescription")[0][0] = (
            f"I01.var03 level matrix {level} task at {point}")
        check(doc == expected, f"{variant} exact reconstructed source")
        check(len([t for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])]) == 24,
              f"{variant} 24 row-containing source tables")
        source_docs[variant] = doc
    # The referenced action has the same TID and station rows in all sources.
    for variant, doc in source_docs.items():
        repairs = rows(doc, "ItemRepair")
        check(len(repairs) == 2 and {r[1] for r in repairs} == {"BASE-01", "DEPOT-01"}
              and {r[11] for r in repairs} == {"I01-LRU-DIRP"},
              f"{variant} fixed dual-station referenced action")
        tasks = rows(doc, "Tasks")
        check(tasks[1][1] == tasks[2][1] == "Level task"
              and tasks[1][2] == tasks[2][2] == "LRU-CM"
              and {tasks[1][3], tasks[2][3]} == {"BASE", "ALT"},
              f"{variant} isolated level labels")
        check(rows(doc, "TaskLevel") == [["BASE", 1, None], ["ALT", 2, None]],
              f"{variant} level label/number mapping")
        ma = rows(doc, "MaintenanceAllocation")
        check({tuple(r[:4]) for r in ma} == {
            ("AIR_BASIC", "LRU-CM", "BASE", "BASE-01"),
            ("AIR_BASIC", "LRU-CM", "ALT", "DEPOT-01"),
            ("AIR_DEPOT", "LRU-CM", "BASE", "DEPOT-01"),
            ("AIR_DEPOT", "LRU-CM", "ALT", "BASE-01"),
        }, f"{variant} crossed complete allocations")
        stock = rows(doc, "StockAllocation")
        check(len(stock) == 4 and
              {(r[0], r[2], r[3]) for r in stock} == {
                  (p, s, q) for p in ("AIR_BASIC", "AIR_DEPOT")
                  for s, q in (("BASE-01", 1), ("DEPOT-01", 0))},
              f"{variant} equal stock POINTs")
    expected_pairs = {
        "parent_to_basic_base": (parent, source_docs["basic-base"],
                                 {"ProblemDescription", "Tasks", "TaskLevel", "MaintenanceAllocation"}),
        "basic_base_to_depot_base": (source_docs["basic-base"], source_docs["depot-base"],
                                     {"ProblemDescription", "Control"}),
        "basic_base_to_basic_alternate": (source_docs["basic-base"], source_docs["basic-alternate"],
                                           {"ProblemDescription", "Tasks"}),
        "depot_base_to_depot_alternate": (source_docs["depot-base"], source_docs["depot-alternate"],
                                           {"ProblemDescription", "Tasks"}),
        "basic_alternate_to_depot_alternate": (source_docs["basic-alternate"],
                                               source_docs["depot-alternate"],
                                               {"ProblemDescription", "Control"}),
    }
    check(set(diff["deltas"]) == set(expected_pairs), "exact-diff five declared contrasts")
    for name, (before, after, expected_changed) in expected_pairs.items():
        bt = {t["name"]: t for t in before["model"]["tables"]}
        at = {t["name"]: t for t in after["model"]["tables"]}
        changed = {n for n in bt.keys() & at.keys() if bt[n] != at[n]}
        declared = diff["deltas"][name]
        check(changed == expected_changed == set(declared["changed_tables"]),
              f"{name} exact changed-table set")
        check(not declared["added_tables"] and not declared["removed_tables"] and bt.keys() == at.keys(),
              f"{name} no changed table inventory")
        check(declared["unchanged_table_count"] == len(bt) - len(changed),
              f"{name} unchanged table count")
        for n in changed:
            check(declared["changed_tables"][n] == {"before": bt[n], "after": at[n]},
                  f"{name} exact {n} before/after")
    return source_docs


def report_checks(variant: str, report: dict, parent_report: dict) -> None:
    actual = {t["name"]: t for t in report["report"]["tables"]}
    reference = {t["name"]: t for t in parent_report["report"]["tables"]}
    check(set(actual) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
          f"{variant} report tables")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        check(actual[name]["columns"] == reference[name]["columns"], f"{variant} {name} columns")
        ar = rows(report, name, "report")
        rr = rows(parent_report, name, "report")
        check(len(ar) == len(rr) == (1 if name == "ResultSummary" else 72),
              f"{variant} {name} row count")
        for index, (a, b) in enumerate(zip(ar, rr)):
            check(a == b, f"{variant} {name} row {index} versus accepted parent")
    system = actual["SystemResults"]
    c = {x["name"]: i for i, x in enumerate(system["columns"])}
    sr = system["instances"][0]["rows"]
    for i, r in enumerate(sr):
        check(r[c["STINT"]] == i / 2 and r[c["ETINT"]] == (i + 1) / 2,
              f"{variant} SystemResults half-hour interval {i}")
    stock = actual["StockTotalResults"]
    sc = {x["name"]: i for i, x in enumerate(stock["columns"])}
    for i, r in enumerate(stock["instances"][0]["rows"]):
        check(r[sc["STINT"]] == i / 2 and r[sc["ETINT"]] == (i + 1) / 2,
              f"{variant} StockTotalResults half-hour interval {i}")
    summary = rows(report, "ResultSummary", "report")[0]
    sm = {x["name"]: summary[i] for i, x in enumerate(actual["ResultSummary"]["columns"])}
    check(sm["NREP"] == 1 and sm["MTMF"] == 1 and sm["MSTF"] == 1 and
          abs(sm["MSUF"] - 2 / 3) < 1e-6, f"{variant} summary factors")
    check(abs(sum(r[c["NSYMO"]] * .5 for r in sr) - 6) < 1e-9,
          f"{variant} six operating aircraft hours")
    check(abs(sum(r[c["NSYRP"]] * .5 for r in sr) - .5) < 1e-9,
          f"{variant} half-hour system replacement")
    check(sr[-1][c["NSYRY"]] == 1 and sr[-1][c["NSYMO"]] == 0,
          f"{variant} terminal ready")
    check(all(r[sc["NBO"]] == 0 for r in stock["instances"][0]["rows"]),
          f"{variant} no persistent aggregate stock backorder bins")


def main() -> int:
    contract = json.loads((CASE / "contract.json").read_text(encoding="utf-8"))
    installed = contract["installed_source_sha256"]
    for label, path in (
        ("simlox_exe", Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")),
        ("manual_pdf", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")),
        ("table_dictionary", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")),
    ):
        check(path.is_file() and digest(path) == installed[label], f"installed {label} byte fingerprint")
    docs = source_checks(contract)
    captured: dict[str, dict] = {}
    for variant in VARIANTS:
        d = RUNS / RUN_ID[variant]
        check(d.is_dir(), f"{variant} run directory")
        invocation = json.loads((d / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((d / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((d / "steps.json").read_text(encoding="utf-8-sig"))
        check(closure["run_id"] == invocation["run_id"] == d.name, f"{variant} run identity")
        check(closure["invocation_sha256"] == digest(d / "invocation.json"), f"{variant} invocation seal")
        check(invocation["input_sha256"] == digest(CASE / f"{variant}-input.json"),
              f"{variant} invoked source")
        check((d / "input.json").read_bytes() == (CASE / f"{variant}-input.json").read_bytes(),
              f"{variant} copied source exact")
        check(closure["source_hashes_before"] == closure["source_hashes_after"] ==
              invocation["source_hashes_before"], f"{variant} frozen before/after source")
        pins = closure["source_hashes_before"]
        for key, expected in (("input", digest(CASE / f"{variant}-input.json")),
                              ("parent", contract["direct_parent"]["sha256"]),
                              ("structural_donor", contract["direct_parent"].get("structural_donor_sha256",
                                   digest(AIR / "E04-upstream-transport-fast-v1.0.0/native-input.json"))),
                              ("contract", digest(CASE / "contract.json")),
                              ("exact_diff", digest(CASE / "exact-diff.json")),
                              ("builder", digest(CASE / "build.py")),
                              ("diff_checker", digest(CASE / "describe_diff.py")),
                              ("checker", digest(CASE / "check_roundtrip.py")),
                              ("runner_script", digest(CASE / "run_native_ssh.ps1")),
                              ("manual", contract["installed_source_sha256"]["manual_pdf"]),
                              ("dictionary", contract["installed_source_sha256"]["table_dictionary"]),
                              ("simlox_exe", contract["installed_source_sha256"]["simlox_exe"])):
            check(pins.get(key) == expected, f"{variant} {key} source pin")
        check(invocation["execution_mode"] == "ssh_cli_v1" and
              invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
              "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant} SSH session-0")
        check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue",
              f"{variant} queue mutex")
        check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
              f"{variant} separate preserved GUI")
        check([s["name"] for s in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"],
              f"{variant} five step sequence")
        check("-threads 1 -calc" in steps[2]["arguments"] and
              "-jsonreport" in steps[3]["arguments"] and
              str(d) in steps[2]["arguments"] and str(d) in steps[3]["arguments"],
              f"{variant} bound single-thread calc and native report commands")
        for s in steps:
            check(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None and
                  s["status"] in ("completed", "calc_observed"),
                  f"{variant} step {s['name']}")
        check(len(closure["raw"]) == 12, f"{variant} twelve raw seals")
        for name, data in closure["raw"].items():
            p = d / name
            check(p.is_file() and p.stat().st_size == data["bytes"] and digest(p) == data["sha256"],
                  f"{variant} raw {name} byte seal")
        check(closure["error"] is None and (d / "model.sxo").stat().st_size > 4,
              f"{variant} valid native output")
        runlog = (d / "run.log").read_bytes().decode("cp1252")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 1" in runlog
              and "warning #108" in runlog and "notice #2034" in runlog
              and "error #" not in runlog and "warning #241" not in runlog,
              f"{variant} conversion diagnostics")
        exported = native_json(d / "roundtrip-raw.json")
        check(exported["model"]["database_version"] == docs[variant]["model"]["database_version"],
              f"{variant} native model version")
        source_tables = {t["name"]: t for t in docs[variant]["model"]["tables"]
                         if any(i["rows"] for i in t["instances"])}
        export_tables = {t["name"]: t for t in exported["model"]["tables"]}
        check(len(source_tables) == 24, f"{variant} populated table cardinality")
        for name, authored in source_tables.items():
            check(authored == export_tables.get(name), f"{variant} exact native roundtrip {name}")
        model = (d / "model.log").read_bytes().decode("cp1252")
        item = "<TEACH-LRU-01,0,1>"
        event(model, "9.8829", "critical random failure added", f"{variant} physical failure time")
        check("subitem failed: <TEACH-LRU-01,0,1>" in model,
              f"{variant} physical failed item ID1")
        event(model, "10", "Take replacement item <TEACH-LRU-01,0,0> from stock",
              f"{variant} spare ID0 issued")
        event(model, "10.5", "System ready <TEACH-AIR-01,0>",
              f"{variant} restored aircraft at 10.5")
        event(model, "20", "mission starting, duration: 2", f"{variant} second sortie")
        event(model, "22", "mission success:", f"{variant} second mission success")
        event(model, "32", "mission starting, duration: 2", f"{variant} third sortie")
        event(model, "34", "mission success:", f"{variant} third mission success")
        event(model, "34", "systems ready: 1 :<TEACH-AIR-01,0>",
              f"{variant} terminal aircraft ID0 ready")
        if ROUTE[variant] == "BASE":
            event(model, "10.1667", f"<TEACH-LRU-01,0,BASE-01,0> Start repair of item {item}",
                  f"{variant} BASE repair start")
            event(model, "11.1667", f"<TEACH-LRU-01,0,BASE-01,0> Finished repair of item {item}",
                  f"{variant} BASE repair end")
            event(model, "11.1667", f"<TEACH-LRU-01,0,BASE-01,0> Put back replacement item {item} to stock",
                  f"{variant} BASE stock restoration")
            check("transport request <<TEACH-LRU-01,0,1>" not in model,
                  f"{variant} no depot transport")
        else:
            event(model, "10.1667", f"transport request <{item},<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started",
                  f"{variant} outward transport start")
            event(model, "12.1667", f"<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item {item}",
                  f"{variant} DEPOT repair start")
            event(model, "13.1667", f"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item {item}",
                  f"{variant} DEPOT repair end")
            event(model, "15.1667", f"<TEACH-LRU-01,0,BASE-01,0> Put back replacement item {item} to stock",
                  f"{variant} returned BASE stock")
            check("<TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,1>" not in model,
                  f"{variant} no BASE item repair")
        report = native_json(d / "report-raw.json")
        parent_report = native_json(PARENT_RUN[ROUTE[variant]] / "report-raw.json")
        parent_closure = json.loads((PARENT_RUN[ROUTE[variant]] / "closure.json").read_text(encoding="utf-8-sig"))
        for name in ("report-raw.json", "model.log"):
            check(parent_closure["raw"][name]["sha256"] == digest(PARENT_RUN[ROUTE[variant]] / name),
                  f"{variant} accepted-parent {name} raw seal")
        check(model.encode("cp1252") == (PARENT_RUN[ROUTE[variant]] / "model.log").read_bytes(),
              f"{variant} event log byte equality to accepted route")
        report_checks(variant, report, parent_report)
        captured[variant] = {"model": model, "report": report,
                             "model_sha256": digest(d / "model.log"),
                             "report_sha256": digest(d / "report-raw.json"),
                             "closure_sha256": digest(d / "closure.json")}
    for a, b in (("basic-base", "depot-alternate"),
                 ("depot-base", "basic-alternate")):
        check(captured[a]["model"] == captured[b]["model"], f"{a}/{b} byte-identical native event log")
        at = {t["name"]: t for t in captured[a]["report"]["report"]["tables"]}
        bt = {t["name"]: t for t in captured[b]["report"]["report"]["tables"]}
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            check(at[name] == bt[name], f"{a}/{b} equal {name}")
    result = {
        "schema": "simlox-i01-var03-level-independent-readonly/v1",
        "case": CASE.name,
        "passed": not failures,
        "verdict": "GO — bounded level-aware task binding and APID crossover" if not failures else "NO-GO",
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "source_sha256": {v: digest(CASE / f"{v}-input.json") for v in VARIANTS},
        "runs": {v: {"run_id": RUN_ID[v], "route": ROUTE[v],
                     "closure_sha256": captured[v]["closure_sha256"],
                     "model_log_sha256": captured[v]["model_sha256"],
                     "report_raw_sha256": captured[v]["report_sha256"]} for v in VARIANTS},
        "scope": "One LRU, one task category, two TLID/LEVL mappings, two APIDs, two stations, one seed; source-bound level-aware matching with physical BASE/DEPOT crossover.",
        "limits": ["The second Task is inert; no competing live repair demand is tested.",
                   "TLID label and its linked numeric LEVL mapping are not isolated from one another; other seeds, <NONE> reorder, GUI visual behavior, and cross-engine parity are unverified.",
                   "Default aggregate StockTotalResults does not show station-level inventory; individual stock identity and return timing come from native model.log."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"{result['verdict']}: {result['checks_passed']}/{result['checks_total']}")
    for failure in failures:
        print("FAIL", failure)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
