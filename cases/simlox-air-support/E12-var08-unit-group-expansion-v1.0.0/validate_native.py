"""Author replay of group mission assignment and independent base ledgers."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "e12-var08-unit-group-expansion-v100-ssh-20261004-01"
RAW_NAMES = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
             "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
             "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    contract, diff = (read(HERE / name) for name in ("contract.json", "exact-diff.json"))
    parent = HERE.parent / contract["accepted_parent"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    run = HERE / "runs" / RUN_ID
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("frozen source", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"] == sha(run / "input.json"))
    ck("frozen diff", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"] and diff["changed_existing_tables"] == ["OperationProfile", "Operations", "ProblemDescription"] and diff["unchanged_parent_tables"] == 29 and set(diff["added_tables"]) == {"UnitGroup", "UnitGroupMember"} and len(diff["modified_cells"]) == 5 and len(diff["removed_rows"]) == 1)
    ck("accepted parent", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("A17 schema reference", sha(HERE.parent / "A17-multi-unit-group-v1.0.0/native-input.json") == contract["a17_schema_reference_sha256"])
    ck("builder replay", __import__("build").build() == (HERE / "native-input.json").read_bytes())
    ck("diff replay", __import__("describe_diff").describe() == diff)
    ck("native identity", inv["case_id"] == "E12" and inv["variant_id"] == "E12.var08" and inv["case_version"] == "1.0.0-candidate" and closure["run_id"] == inv["run_id"] == RUN_ID)
    ck("guarded queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck("source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    pins = inv["source_hashes_before"]
    for key, name in (("input", "native-input.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"),
                      ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
        ck(f"source pin {key}", pins[key] == sha(HERE / name))
    ck("parent pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"])
    ck("A17 pin", pins["a17_schema"] == contract["a17_schema_reference_sha256"])
    ck("installed source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
    ck("five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
    ck("raw artifact set", set(closure["raw"]) == RAW_NAMES)
    for name, meta in closure["raw"].items():
        path = run / name
        ck(f"raw {name}", path.stat().st_size == meta["bytes"] > 4 and sha(path) == meta["sha256"])
    source, exported = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
    ck("24 table roundtrip", read(run / "roundtrip-validation.json")["passed"] is True and len(source) == 24 and all(exported.get(name) == table for name, table in source.items()))
    def src(name: str) -> list[dict]:
        return [dict(zip([c["name"] for c in source[name]["columns"]], row)) for row in source[name]["rows"]]
    ck("group row", src("UnitGroup") == [{"UGID": "TEACH-GROUP", "DESCR": "Two-unit teaching group", "UNPR1": "N", "NOTE": None}])
    ck("equal explicit members", {(r["USTID"], r["PRI"], r["XTIME"]) for r in src("UnitGroupMember")} == {("TEACH-UNIT", 1, 0), ("TEACH-UNIT-2", 1, 0)})
    ck("physical unit bases", {r["UNID"]: r["STID"] for r in src("Unit")} == {"TEACH-UNIT": "BASE-01", "TEACH-UNIT-2": "BASE-02"})
    ck("one aircraft per unit", {r["USTID"]: r["QTYPS"] for r in src("SystemDeployment")} == {"TEACH-UNIT": 1, "TEACH-UNIT-2": 1})
    ck("group-owned schedule", src("Operations") == [{"USTID": "TEACH-GROUP", "PRID": "BASIC-SCHEDULE", "NOTE": None}])
    ck("three paired waves", [(r["STIM"], r["IQTY"], r["IPER"]) for r in src("OperationProfile")] == [(8, 2, 0), (20, 2, 0), (32, 2, 0)])
    ck("separate opening stock", {r["STID"]: r["STSIZ"] for r in src("StockAllocation")} == {"DEPOT-01": 1, "BASE-01": 1, "BASE-02": 0})
    ck("unchanged depot repair rule", any(r["IID"] == "LRU-GRP" and r["STID"] == "DEPOT-GRP" and r["DIRPT"] == 1 for r in src("ItemRepair")))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("zero-error valid output", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and "Starting simulation..." in conversion and "Saving results ..." in conversion and all((run / n).stat().st_size > 1000 for n in ("model.sxo", "model.log", "report-raw.json")))
    ck("warning identity", Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    orders = [(float(t), owner) for t, owner in re.findall(r"Time: ([\d.]+) <([^>]+)> mission ordered: BASIC-MISSION", log)]
    ck("six group orders", orders == [(7, "TEACH-GROUP")] * 2 + [(19, "TEACH-GROUP")] * 2 + [(31, "TEACH-GROUP")] * 2)
    allocations = [(float(t), int(m), int(a)) for t, m, a in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-GROUP,0,0,(\d+)> mission allocates system: <TEACH-AIR-01,(\d+)>", log)]
    ck("alternating member aircraft", allocations == [(7, 0, 0), (7, 1, 1), (19, 2, 0), (19, 3, 1), (31, 4, 0), (31, 5, 1)])
    for wave, time in enumerate((7, 19, 31)):
        for member, base, aircraft in (("TEACH-UNIT", "BASE-01", 0), ("TEACH-UNIT-2", "BASE-02", 1)):
            ck(f"wave {wave} {member} own aircraft", f"Time: {time} <TEACH-AIR-01,{aircraft}> nbr ready decreased at unit: <{member} at <{base},0>>" in log and f"Time: {time} <BASIC-MISSION,TEACH-GROUP,0,0,{wave*2+aircraft}> mission allocates system: <TEACH-AIR-01,{aircraft}>" in log)
    starts = [(float(t), int(m), int(a)) for t, m, a in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-GROUP,0,0,(\d+)> mission starting, duration: 3.5 : <TEACH-AIR-01,(\d+)>", log)]
    ck("six physical starts", starts == [(8, 0, 0), (8, 1, 1), (20, 2, 0), (20, 3, 1), (32, 4, 0), (32, 5, 1)])
    aborted = [(float(t), int(m)) for t, m in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-GROUP,0,0,(\d+)> mission aborted:", log)]
    succeeded = [(float(t), int(m)) for t, m in re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-GROUP,0,0,(\d+)> mission success:", log)]
    ck("four aborts", aborted == [(9.8829, 0), (11.1325, 1), (22.5723, 2), (34.7893, 4)])
    ck("two successes", succeeded == [(23.5, 3), (35.5, 5)])
    demand = [(float(t), base, int(item)) for t, base, item in re.findall(r"Time: ([\d.]+) <TEACH-LRU-01,0,(BASE-0[12]),0> Item demand arrives from pos <TEACH-AIR-01,BASE-0[12],0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>", log)]
    ck("base-specific failed items", demand == [(10.7579, "BASE-01", 2), (11.5, "BASE-02", 3), (23.4473, "BASE-01", 4), (35.5, "BASE-01", 5)])
    upward = [(int(item), base) for item, base in re.findall(r"transport request <<TEACH-LRU-01,0,(\d+)>,<TEACH-LRU-01,0,(BASE-0[12]),0>,<TEACH-LRU-01,0,DEPOT-01,0>> started", log)]
    ck("failed-item upward transport", upward == [(2, "BASE-01"), (3, "BASE-02"), (4, "BASE-01"), (5, "BASE-01")])
    downward = [(int(item), base) for item, base in re.findall(r"transport request <<TEACH-LRU-01,0,(\d+)>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,(BASE-0[12]),0>> started", log)]
    ck("replacement downward transport", downward == [(0, "BASE-01"), (2, "BASE-02"), (3, "BASE-01"), (4, "BASE-01")])
    ck("opening spares are distinct", all(f"Time: 0 <TEACH-LRU-01,0,{place},0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,{place},0> Level: 1 Items:<TEACH-LRU-01,0,{item}>," in log for place, item in (("DEPOT-01", 0), ("BASE-01", 1))))
    ck("depot repair completion", all(f"<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,{item}>" in log and f"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,{item}>" in log for item in (2, 3, 4)))
    ck("repaired ID2 resolves depot shortage", "Time: 14.9246 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>" in log and "Time: 14.9246 <TEACH-LRU-01,0,DEPOT-01,0> Backorder removed" in log and "Time: 14.9246  transport request <<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-02,0>> started" in log)
    ck("later repairs replenish depot stock", all(f"<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,{item}> to stock" in log for item in (3, 4)))
    ck("last failed item in transit at horizon", "Time: 35.6667  transport request <<TEACH-LRU-01,0,5>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log and "Start repair of item <TEACH-LRU-01,0,5>" not in log)
    ck("base02 and depot backorders", all(f"Time: {t} <TEACH-LRU-01,0,{place},0> Backorder {event}" in log for t, place, event in (("11.5", "BASE-02", "added"), ("11.5", "DEPOT-01", "added"), ("14.9246", "DEPOT-01", "removed"), ("15.9246", "BASE-02", "removed"))) and "<TEACH-LRU-01,0,BASE-01,0> Backorder added" not in log)
    ck("base02 repair and readiness", "Time: 15.9246 <TEACH-LRU-01,0,BASE-02,0> Backorder removed, waiting time was 4.42457" in log and "Time: 16.5912 <TEACH-AIR-01,BASE-02,0> System ready <TEACH-AIR-01,1>" in log)
    ck("per-base terminal aircraft", all(f"Time: {t} <TEACH-AIR-01,{base},0> System ready <TEACH-AIR-01,{aircraft}>" in log for t, base, aircraft in (("35.5", "BASE-02", 1), ("36", "BASE-01", 0))))
    report = {t["name"]: t for t in parse_native(run / "report-raw.json")["report"]["tables"]}
    parent_report = {t["name"]: t for t in parse_native(parent_run / "report-raw.json")["report"]["tables"]}
    ck("four report tables", set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary = rows(report["ResultSummary"])[0]
    ck("36h and mission success", summary["NREP"] == 1 and summary["RTILW"] == 0 and summary["RTIUP"] == 36 and abs(summary["MSUF"] - 2 / 6) < 1e-6)
    system, stock = (rows(report[name]) for name in ("SystemResults", "StockTotalResults"))
    ck("72 system bins", len(system) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(system)))
    ck("72 stock bins", len(stock) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(stock)))
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        ck(f"report {name} schema", report[name]["columns"] == parent_report[name]["columns"])
        child_rows, parent_rows = rows(report[name]), rows(parent_report[name])
        ck(f"report {name} row count", len(child_rows) == len(parent_rows))
        for i, (child, previous) in enumerate(zip(child_rows, parent_rows)):
            ck(f"report {name} row {i} accepted comparator", child == previous)
    ck("backorder bins", [i for i, row in enumerate(stock) if row["NBO"] > 0] == list(range(23, 32)))
    ck("terminal interval and event", system[-1]["NSYRY"] == system[-1]["NSYA"] == 1 and stock[-1]["NBO"] == 0 and "Time: 36 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log)
    result = {"schema": "simlox-e12-var08-unit-group-expansion-v100-author-validation/v1", "passed": not failures,
              "checks_total": checks, "checks_passed": checks - len(failures), "failures": failures,
              "run_id": RUN_ID, "closure_sha256": sha(run / "closure.json"), "event_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"),
              "allocations": allocations, "mission_aborts": aborted, "mission_successes": succeeded}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
