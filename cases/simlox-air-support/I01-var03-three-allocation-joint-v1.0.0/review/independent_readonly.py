"""Independent, read-only replay of three simultaneous I01 allocation tables.

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
PARENT = AIR / "I01-var03-stock-maintenance-joint-v1.0.0"
DATE = "2026-10-02"
OUT = HERE / f"independent-readonly-{DATE}.json"
VARIANTS = ("one-base", "one-depot", "two-base", "two-depot")
RUN_ID = {v: f"i01-var03-three-{v}-v100-ssh-20261002-01" for v in VARIANTS}
ROUTE = {"one-base": "BASE", "one-depot": "DEPOT",
         "two-base": "BASE", "two-depot": "DEPOT"}
POINT = {"one-base": "AIR_BASIC", "one-depot": "AIR_DEPOT",
         "two-base": "AIR_TWO_BASE", "two-depot": "AIR_TWO_DEPOT"}
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
    parent_path = PARENT / "one-base-input.json"
    check(digest(parent_path) == contract["direct_parent"]["sha256"], "accepted parent bytes")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    repository = AIR.parent.parent
    merged = subprocess.run(
        ["git", "show", "origin/simlox/main:cases/simlox-air-support/"
         "I01-var03-stock-maintenance-joint-v1.0.0/one-base-input.json"],
        cwd=repository, capture_output=True, check=False)
    check(merged.returncode == 0 and
          hashlib.sha256(merged.stdout).hexdigest() == digest(parent_path),
          "accepted parent bytes in merged origin/simlox/main")
    exact_diff = CASE / "exact-diff.json"
    check(digest(exact_diff) == contract["sources_sha256"]["exact_diff"], "exact-diff seal")
    diff = json.loads(exact_diff.read_text(encoding="utf-8"))
    check(diff["source_sha256"]["parent"] == digest(parent_path), "diff parent pin")
    check("I01-var03-stock-maintenance-joint-v1.0.0" in
          (AIR / "publication-index-v1.json").read_text(encoding="utf-8"),
          "parent in publication index")

    donor = AIR / "I01-var01-resource-points-v1.0.0/selected-input.json"
    check(digest(donor) == contract["preparation_resource_donor"]["sha256"],
          "accepted preparation-resource donor bytes")
    # Reconstruct every business table from the accepted joint parent.
    baseline = copy.deepcopy(parent)
    rows(baseline, "MissionPreparation").append(
        ["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", .75, "PREP-FIXED", None, None])
    rows(baseline, "Tasks").append(
        ["PREP-FIXED", "Serial 10+20-minute BASIC-MISSION preparation", None, None, None])
    rows(baseline, "Resource").extend([
        ["P-CREW", "Crew A personnel", None, None, None, "SPECIAL", None, None],
        ["P-OTHER", "Other specialty personnel", None, None, None, "SPECIAL", None, None],
    ])
    rows(baseline, "ResourceAllocation").extend([
        [point, rid, "BASE-01", qty, None]
        for point, crew in (("AIR_BASIC", 2), ("AIR_DEPOT", 2),
                            ("AIR_TWO_BASE", 3), ("AIR_TWO_DEPOT", 3))
        for rid, qty in (("P-CREW", crew), ("P-OTHER", 0))
    ])
    rows(baseline, "SubTaskType").extend([
        ["INSPECT", "INSPECT", None], ["SERVICE", "SERVICE", None]])
    rows(baseline, "TaskBreakDown").extend([
        ["PREP-FIXED", 1, "INSPECT", 1 / 6, None, None],
        ["PREP-FIXED", 2, "SERVICE", 1 / 3, None, None],
    ])
    rows(baseline, "SubTaskResource").append(
        ["PREP-FIXED", 1, "P-CREW", 2, 1, None, None, None, None])
    source_docs: dict[str, dict] = {}
    for variant in VARIANTS:
        path = CASE / f"{variant}-input.json"
        check(digest(path) == contract["sources_sha256"][variant], f"{variant} input seal")
        check(diff["source_sha256"][variant] == digest(path), f"{variant} diff pin")
        doc = json.loads(path.read_text(encoding="utf-8"))
        expected = copy.deepcopy(baseline)
        rows(expected, "Control")[0][3] = POINT[variant]
        rows(expected, "ProblemDescription")[0][0] = (
            f"I01.var03 three allocation POINT diagnostic {variant}")
        check(doc == expected, f"{variant} exact reconstructed source")
        check(len([t for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])]) == 29,
              f"{variant} 29 row-containing source tables")
        source_docs[variant] = doc
    # The referenced action has the same TID and station rows in all sources.
    for variant, doc in source_docs.items():
        repairs = rows(doc, "ItemRepair")
        check(len(repairs) == 2 and {r[1] for r in repairs} == {"BASE-01", "DEPOT-01"}
              and {r[11] for r in repairs} == {"I01-LRU-DIRP"},
              f"{variant} fixed dual-station referenced action")
        check(rows(doc, "Tasks")[:2] == rows(parent, "Tasks") and
              rows(doc, "Tasks")[2] ==
              ["PREP-FIXED", "Serial 10+20-minute BASIC-MISSION preparation", None, None, None],
              f"{variant} fixed maintenance task plus donor preparation")
        ma = rows(doc, "MaintenanceAllocation")
        check({tuple(r[:4]) for r in ma} == {
            ("AIR_BASIC", "LRU-CM", "BASE", "BASE-01"),
            ("AIR_DEPOT", "LRU-CM", "BASE", "DEPOT-01"),
            ("AIR_TWO_BASE", "LRU-CM", "BASE", "BASE-01"),
            ("AIR_TWO_DEPOT", "LRU-CM", "BASE", "DEPOT-01"),
        }, f"{variant} four complete maintenance POINTs")
        stock = rows(doc, "StockAllocation")
        check(len(stock) == 8 and
              {(r[0], r[2], r[3]) for r in stock} == {
                  (p, s, q) for p, q in (("AIR_BASIC", 1), ("AIR_DEPOT", 1),
                                        ("AIR_TWO_BASE", 2), ("AIR_TWO_DEPOT", 2))
                  for s, q in (("BASE-01", q), ("DEPOT-01", 0))},
              f"{variant} four complete stock POINTs")
        resources = rows(doc, "ResourceAllocation")
        check(len(resources) == 8 and
              {(r[0], r[1], r[2], r[3]) for r in resources} == {
                  (p, rid, "BASE-01", qty)
                  for p, capacity in (("AIR_BASIC", 2), ("AIR_DEPOT", 2),
                                      ("AIR_TWO_BASE", 3), ("AIR_TWO_DEPOT", 3))
                  for rid, qty in (("P-CREW", capacity), ("P-OTHER", 0))},
              f"{variant} four complete resource POINTs")
        check(not rows(doc, "ItemReorder"), f"{variant} no ItemReorder rows")
    expected_pairs = {
        "parent_to_one_base": (parent, source_docs["one-base"],
                               {"ProblemDescription", "MissionPreparation", "Tasks", "Resource",
                                "ResourceAllocation", "SubTaskType", "TaskBreakDown", "SubTaskResource"}),
        "one_base_to_one_depot": (source_docs["one-base"], source_docs["one-depot"],
                                  {"ProblemDescription", "Control"}),
        "one_base_to_two_base": (source_docs["one-base"], source_docs["two-base"],
                                 {"ProblemDescription", "Control"}),
        "one_depot_to_two_depot": (source_docs["one-depot"], source_docs["two-depot"],
                                   {"ProblemDescription", "Control"}),
        "two_base_to_two_depot": (source_docs["two-base"], source_docs["two-depot"],
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


def report_checks(variant: str, report: dict) -> None:
    actual = {t["name"]: t for t in report["report"]["tables"]}
    check(set(actual) == {"ProblemDescription", "ResultSummary", "SystemResults",
                          "StockTotalResults", "ResourceResults", "ResourceResultsTotal"},
          f"{variant} report tables")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults",
                 "ResourceResults", "ResourceResultsTotal"):
        ar = rows(report, name, "report")
        check(len(ar) == (1 if name in ("ResultSummary", "ResourceResultsTotal") else 72),
              f"{variant} {name} row count")
    for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        t = actual[name]
        c = {x["name"]: i for i, x in enumerate(t["columns"])}
        for i, r in enumerate(t["instances"][0]["rows"]):
            check(r[c["STINT"]] == i / 2 and r[c["ETINT"]] == (i + 1) / 2,
                  f"{variant} {name} half-hour interval {i}")
    system = actual["SystemResults"]
    c = {x["name"]: i for i, x in enumerate(system["columns"])}
    sr = system["instances"][0]["rows"]
    stock = actual["StockTotalResults"]
    sc = {x["name"]: i for i, x in enumerate(stock["columns"])}
    rr = actual["ResourceResults"]
    rc = {x["name"]: i for i, x in enumerate(rr["columns"])}
    resource_rows = rr["instances"][0]["rows"]
    capacity = 1 if variant.startswith("one") else 2
    crew = capacity + 1
    check(all(r[rc["NR"]] == crew and r[rc["NRA"]] == crew and
              r[rc["NRN"]] == crew and r[rc["NRW"]] == 0 for r in resource_rows),
          f"{variant} 72 resource capacity/availability/wait bins")
    check(all(abs(r[rc["NRUM"]] - (2 / 3 if i in (14, 38, 62) else 0)) < 1e-6
              for i, r in enumerate(resource_rows)),
          f"{variant} three 10-minute two-crew prep work intervals")
    total = rows(report, "ResourceResultsTotal", "report")[0]
    rtc = {x["name"]: i for i, x in enumerate(actual["ResourceResultsTotal"]["columns"])}
    check(total[rtc["NR"]] == crew and total[rtc["NRA"]] == crew and
          abs(total[rtc["NRUM"]] - 1 / 36) < 1e-6,
          f"{variant} resource total and one crew-hour")
    summary = rows(report, "ResultSummary", "report")[0]
    sm = {x["name"]: summary[i] for i, x in enumerate(actual["ResultSummary"]["columns"])}
    check(sm["NREP"] == 1 and sm["MTMF"] == 1 and sm["MSTF"] == 1 and
          abs(sm["MSUF"] - (2 / 3 if variant.endswith("base") else 1 / 3)) < 1e-6,
          f"{variant} summary factors")
    check(abs(sum(r[c["NSYMO"]] * .5 for r in sr) - 6) < 1e-9,
          f"{variant} six operating aircraft hours")
    check(abs(sum(r[c["NSYMP"]] * .5 for r in sr) - 1.5) < 1e-9,
          f"{variant} 1.5 aircraft preparation hours")
    check(abs(sum(r[c["NSYRP"]] * .5 for r in sr) -
              (.5 if variant.endswith("base") else 1.0)) < 1e-9,
          f"{variant} one/two half-hour system replacements")
    check(sr[-1][c["NSYRY"]] == 1 and sr[-1][c["NSYMO"]] == 0,
          f"{variant} terminal ready")
    check(all(r[sc["NBO"]] == 0 for r in stock["instances"][0]["rows"]),
          f"{variant} aggregate NBO zero despite native depot backorder")


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
                              ("preparation_donor", contract["preparation_resource_donor"]["sha256"]),
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
        check(len(source_tables) == 29, f"{variant} populated table cardinality")
        for name, authored in source_tables.items():
            check(authored == export_tables.get(name), f"{variant} exact native roundtrip {name}")
        model = (d / "model.log").read_bytes().decode("cp1252")
        stock_size = 1 if variant.startswith("one") else 2
        item = f"<TEACH-LRU-01,0,{stock_size}>"
        crew = stock_size + 1
        for start in (7, 19, 31):
            event(model, str(start), "preparation started, mission:",
                  f"{variant} preparation begins {start}")
            event(model, str(start), f"<P-CREW at <BASE-01,0>> allocated to maintenance task: 2  available now: {crew - 2}",
                  f"{variant} two crew leased {start}")
            release = "7.16667" if start == 7 else f"{start}.1667"
            event(model, release, f"<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 2  available now: {crew}",
                  f"{variant} crew released after ten minutes {start}")
            event(model, f"{start}.5", "preparation ended, mission:",
                  f"{variant} 30-minute preparation completed {start}")
        event(model, "9.8829", "critical random failure added", f"{variant} physical failure time")
        check(f"subitem failed: {item}" in model,
              f"{variant} physical failed mounted item ID{stock_size}")
        event(model, "10", "Take replacement item <TEACH-LRU-01,0,0> from stock",
              f"{variant} spare ID0 issued")
        base_stock = [(level, items.rstrip()) for level, items in
                      re.findall(r"^  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: (\d+) Items:(.*)$",
                                 model, flags=re.M)]
        expected_stock = ([('1', '<TEACH-LRU-01,0,0>,'), ('0', ''),
                           ('1', '<TEACH-LRU-01,0,1>,')]
                          if stock_size == 1 else
                          [('2', '<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,1>,'),
                           ('1', '<TEACH-LRU-01,0,1>,'),
                           ('2', '<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,2>,')])
        if ROUTE[variant] == "DEPOT":
            expected_stock.append((str(stock_size - 1),
                                   '' if stock_size == 1 else '<TEACH-LRU-01,0,2>,'))
        check(base_stock == expected_stock,
              f"{variant} physical BASE stock initial/issued/returned identity")
        depot_stock = [(level, items.rstrip()) for level, items in
                       re.findall(r"^  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: (\d+) Items:(.*)$",
                                  model, flags=re.M)]
        check(depot_stock == [("0", "")], f"{variant} initial DEPOT stock zero")
        event(model, "10.5", "System ready <TEACH-AIR-01,0>",
              f"{variant} restored aircraft at 10.5")
        event(model, "8", "mission starting, duration: 2", f"{variant} first sortie")
        event(model, "9.8829", "mission aborted:", f"{variant} first mission abort")
        event(model, "20", "mission starting, duration: 2", f"{variant} second sortie")
        event(model, "22", "mission success:", f"{variant} second mission success")
        event(model, "32", "mission starting, duration: 2", f"{variant} third sortie")
        if ROUTE[variant] == "BASE":
            event(model, "34", "mission success:", f"{variant} third mission success")
            event(model, "34", "systems ready: 1 :<TEACH-AIR-01,0>",
                  f"{variant} terminal aircraft ready")
            check("Time: 33.9619 <TEACH-AIR-01,0> critical random failure added" not in model,
                  f"{variant} no second failure")
        else:
            second = f"<TEACH-LRU-01,0,{stock_size + 1}>"
            event(model, "33.9619", "critical random failure added",
                  f"{variant} second failure time")
            check(f"subitem failed: {second}" in model,
                  f"{variant} second failed physical ID")
            event(model, "33.9619", "mission aborted:", f"{variant} third mission abort")
            event(model, "34", "Take replacement item <TEACH-LRU-01,0,1> from stock",
                  f"{variant} second spare ID1 issued")
            event(model, "34.1667", f"transport request <{second},<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started",
                  f"{variant} second failed item outward transit")
            check(f"Finished repair of item {second}" not in model and
                  f"Put back replacement item {second} to stock" not in model,
                  f"{variant} second item unfinished at horizon")
            event(model, "34.5", "systems ready: 1 :<TEACH-AIR-01,0>",
                  f"{variant} terminal aircraft ready despite transit")
            check(sum("Backorder added" in line for line in model.splitlines()) == 2,
                  f"{variant} two physical depot backorders")
        if ROUTE[variant] == "BASE":
            event(model, "10.1667", f"<TEACH-LRU-01,0,BASE-01,0> Start repair of item {item}",
                  f"{variant} BASE repair start")
            event(model, "11.1667", f"<TEACH-LRU-01,0,BASE-01,0> Finished repair of item {item}",
                  f"{variant} BASE repair end")
            event(model, "11.1667", f"<TEACH-LRU-01,0,BASE-01,0> Put back replacement item {item} to stock",
                  f"{variant} BASE stock restoration")
            check(f"transport request <{item}" not in model,
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
            check(f"<TEACH-LRU-01,0,BASE-01,0> Start repair of item {item}" not in model,
                  f"{variant} no BASE item repair")
        report = native_json(d / "report-raw.json")
        report_checks(variant, report)
        captured[variant] = {"model": model, "report": report,
                             "model_sha256": digest(d / "model.log"),
                             "report_sha256": digest(d / "report-raw.json"),
                             "closure_sha256": digest(d / "closure.json")}
    def mission_lines(text: str) -> list[str]:
        return [line for line in text.splitlines() if line.startswith("Time: ")
                and any(term in line for term in ("mission ordered", "mission created",
                                                   "mission starting", "mission aborted",
                                                   "aborted mission completed", "mission success",
                                                   "mission completed"))]
    reports = {v: {t["name"]: t for t in captured[v]["report"]["report"]["tables"]}
               for v in VARIANTS}
    for a, b in (("one-base", "two-base"), ("one-depot", "two-depot")):
        check(mission_lines(captured[a]["model"]) == mission_lines(captured[b]["model"]),
              f"{a}/{b} same route mission outcomes across stock/resource levels")
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            ar = reports[a][name]["instances"][0]["rows"]
            br = reports[b][name]["instances"][0]["rows"]
            for i, (x, y) in enumerate(zip(ar, br)):
                check(x == y, f"{a}/{b} equal {name} row {i}")
    for a, b in (("one-base", "one-depot"), ("two-base", "two-depot")):
        for name in ("ResourceResults", "ResourceResultsTotal"):
            ar = reports[a][name]["instances"][0]["rows"]
            br = reports[b][name]["instances"][0]["rows"]
            for i, (x, y) in enumerate(zip(ar, br)):
                check(x == y, f"{a}/{b} equal resource {name} row {i}")
        sysa, sysb = reports[a]["SystemResults"], reports[b]["SystemResults"]
        sa, sb = sysa["instances"][0]["rows"], sysb["instances"][0]["rows"]
        check([i for i, (x, y) in enumerate(zip(sa, sb)) if x != y] == [67, 68, 69],
              f"{a}/{b} second-failure SystemResults bins only")
        sta, stb = reports[a]["StockTotalResults"], reports[b]["StockTotalResults"]
        check([i for i, (x, y) in enumerate(zip(sta["instances"][0]["rows"],
                                                stb["instances"][0]["rows"])) if x != y] == [68],
              f"{a}/{b} second-demand StockTotalResults bin only")
    result = {
        "schema": "simlox-i01-var03-three-allocation-independent-readonly/v1",
        "case": CASE.name,
        "passed": not failures,
        "verdict": "GO — bounded simultaneous three-allocation APID selection" if not failures else "NO-GO",
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "source_sha256": {v: digest(CASE / f"{v}-input.json") for v in VARIANTS},
        "runs": {v: {"run_id": RUN_ID[v], "point": POINT[v], "base_spares": 1 if v.startswith("one") else 2,
                     "route": ROUTE[v],
                     "closure_sha256": captured[v]["closure_sha256"],
                     "model_log_sha256": captured[v]["model_sha256"],
                     "report_raw_sha256": captured[v]["report_sha256"]} for v in VARIANTS},
        "observations": {
            "resource": "P-CREW capacity 2 at one-spare POINTs and 3 at two-spare POINTs; all three preparations lease two crew for 10 minutes, then release them, and finish at 7.5/19.5/31.5. ResourceResults.NR is 2/3 in all 72 bins; NRUM is 2/3 only in bins 14/38/62; NRW is zero.",
            "inventory": "Native BASE stock item identities show 1->0->1 and 2->1->2 after first issue/repair; DEPOT arms issue a second spare at 34 and end at BASE stock 0/1. Aggregate StockTotalResults does not expose on-hand counts.",
            "maintenance": "First failed item repairs at BASE 10.1667-11.1667 or DEPOT 12.1667-13.1667 after 2-hour outward transport, then returns BASE at 15.1667. In DEPOT arms, a distinct second item fails at 33.9619 and begins outward transit 34.1667; no second repair completion or stock return is logged by 36.",
            "missions": "All first missions abort and all second missions succeed; third mission succeeds only in BASE arms and aborts at 33.9619 in DEPOT arms. Aircraft is ready at horizon in all arms.",
            "backorder": "Native DEPOT log adds an internal backorder after each failed-item dispatch; the second remains unresolved at hour 36 although every aggregate StockTotalResults.NBO bin is zero.",
        },
        "scope": "One LRU, four APID POINTs jointly selecting P-CREW capacity 2/3, BASE spare size 1/2, and BASE/DEPOT repair; one seed.",
        "limits": ["P-CREW 2/3 is correlated with stock 1/2; separate resource-versus-stock causation is not identified.",
                   "DEPOT arms have a second failure at 33.9619 and its failed item remains in transit at horizon; no terminal depot replenishment or matched mission outcomes across routes is claimed.",
                   "Aggregate StockTotalResults.NBO is zero despite physical depot backorder events; it cannot prove absence of internal backorders or on-hand stock quantity.",
                   "No shortage, procurement/reorder, other seeds, category/level changes, GUI visual behavior, or cross-engine parity is tested."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"{result['verdict']}: {result['checks_passed']}/{result['checks_total']}")
    for failure in failures:
        print("FAIL", failure)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
