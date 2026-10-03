"""Author replay of both physical DFRAC-selected depot paths."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "e12-var07-two-depot-dfrac-v100-ssh-20261004-01"
RAW_NAMES = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
             "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
             "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    contract, diff = (read(HERE / n) for n in ("contract.json", "exact-diff.json"))
    parent = HERE.parent / contract["accepted_parent"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    run = HERE / "runs" / RUN_ID
    inv, closure, steps = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck("frozen source", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"] == sha(run / "input.json"))
    ck("frozen diff", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"] and diff["changed_tables"] == ["ItemStationStructure", "ProblemDescription", "Station", "StationStructure", "StockAllocation"] and diff["unchanged_parent_tables"] == 27 and len(diff["modified_cells"]) == 5 and len(diff["added_rows"]) == 6)
    ck("accepted parent", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("builder replay", __import__("build").build() == (HERE / "native-input.json").read_bytes())
    ck("diff replay", __import__("describe_diff").describe() == diff)
    ck("native identity", inv["case_id"] == "E12" and inv["variant_id"] == "E12.var07" and inv["case_version"] == "1.0.0-candidate" and closure["run_id"] == inv["run_id"] == RUN_ID)
    ck("guarded queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck("source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    pins = inv["source_hashes_before"]
    for key, name in (("input", "native-input.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"),
                      ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
        ck(f"source pin {key}", pins[key] == sha(HERE / name))
    ck("parent pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"])
    ck("installed source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
    ck("five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
    ck("raw artifact set", set(closure["raw"]) == RAW_NAMES)
    for name, meta in closure["raw"].items():
        path = run / name
        ck(f"raw {name}", path.stat().st_size == meta["bytes"] > 4 and sha(path) == meta["sha256"])
    source, roundtrip = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
    ck("22 table exact roundtrip", read(run / "roundtrip-validation.json")["passed"] is True and len(source) == 22 and all(roundtrip.get(name) == table for name, table in source.items()))

    def source_rows(name: str) -> list[dict]:
        table = source[name]
        return [dict(zip([c["name"] for c in table["columns"]], row)) for row in table["rows"]]

    stations = {r["STID"]: r for r in source_rows("Station")}
    ck("four physical stations", set(stations) == {"BASE-01", "BASE-02", "DEPOT-01", "DEPOT-02"} and all(stations[n]["QTY"] == 1 and stations[n]["GSTID"] == "DEPOT-GRP" for n in ("DEPOT-01", "DEPOT-02")))
    for name in ("StationStructure", "ItemStationStructure"):
        links = source_rows(name)
        for base in ("BASE-01", "BASE-02"):
            chosen = [r for r in links if r["STID"] == base]
            ck(f"{name} {base} equal fractions", len(chosen) == 2 and {r["MSTID"]: r["DFRAC"] for r in chosen} == {"DEPOT-01": 0.5, "DEPOT-02": 0.5} and sum(r["DFRAC"] for r in chosen) == 1)
    stock = {r["STID"]: r["STSIZ"] for r in source_rows("StockAllocation")}
    ck("independent opening stock", stock == {"BASE-01": 1, "BASE-02": 0, "DEPOT-01": 1, "DEPOT-02": 1})
    ck("depot group repair", any(r["IID"] == "LRU-GRP" and r["STID"] == "DEPOT-GRP" and r["DIRPT"] == 1 for r in source_rows("ItemRepair")))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("zero-error valid output", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and "Starting simulation..." in conversion and "Saving results ..." in conversion and all((run / n).stat().st_size > 1000 for n in ("model.sxo", "model.log", "report-raw.json")))
    ck("warning identity", Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    demand_pattern = re.compile(r"Time: ([\d.]+) <TEACH-LRU-01,0,(DEPOT-0[12]),0> Item demand arrives from pos <TEACH-LRU-01,0,(BASE-0[12]),0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>")
    demands = [(float(t), depot, base, int(item)) for t, depot, base, item in demand_pattern.findall(log)]
    ck("four propagated demands", demands == [(10.7579, "DEPOT-01", "BASE-01", 3), (11.5, "DEPOT-02", "BASE-02", 4), (23.4473, "DEPOT-02", "BASE-01", 5), (35.5, "DEPOT-02", "BASE-01", 6)])
    ck("both actual depots selected", {depot for _, depot, _, _ in demands} == {"DEPOT-01", "DEPOT-02"})
    upward_pattern = re.compile(r"transport request <<TEACH-LRU-01,0,(\d+)>,<TEACH-LRU-01,0,(BASE-0[12]),0>,<TEACH-LRU-01,0,(DEPOT-0[12]),0>> started")
    upward = [(int(item), base, depot) for item, base, depot in upward_pattern.findall(log)]
    ck("failed-item upward routes equal demand depot", sorted(upward) == sorted((item, base, depot) for _, depot, base, item in demands))
    for depot, spare, base, failed in (("DEPOT-01", 0, "BASE-01", 3), ("DEPOT-02", 1, "BASE-02", 4)):
        ck(f"{depot} opening spare", f"Time: 0 <TEACH-LRU-01,0,{depot},0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,{depot},0> Level: 1 Items:<TEACH-LRU-01,0,{spare}>," in log)
        ck(f"{depot} first demand and supply", f"<TEACH-LRU-01,0,{depot},0> Take replacement item <TEACH-LRU-01,0,{spare}> from stock" in log and f"transport request <<TEACH-LRU-01,0,{spare}>,<TEACH-LRU-01,0,{depot},0>,<TEACH-LRU-01,0,{base},0>> started" in log)
        ck(f"{depot} failed item repair", f"<TEACH-LRU-01,0,{depot},0> Start repair of item <TEACH-LRU-01,0,{failed}>" in log and f"<TEACH-LRU-01,0,{depot},0> Put back replacement item <TEACH-LRU-01,0,{failed}> to stock" in log)
    ck("later depot-02 repair", "Time: 26.614 <TEACH-LRU-01,0,DEPOT-02,0> Start repair of item <TEACH-LRU-01,0,5>" in log and "Time: 27.614 <TEACH-LRU-01,0,DEPOT-02,0> Put back replacement item <TEACH-LRU-01,0,5> to stock" in log)
    ck("BASE-02 local-only backorder", "Time: 11.5 <TEACH-LRU-01,0,BASE-02,0> Backorder added" in log and "Time: 12.5 <TEACH-LRU-01,0,BASE-02,0> Backorder removed, waiting time was 1" in log and "<TEACH-LRU-01,0,DEPOT-01,0> Backorder added" not in log and "<TEACH-LRU-01,0,DEPOT-02,0> Backorder added" not in log)
    ck("aircraft readiness", all(f"Time: {t} <TEACH-AIR-01,{base},0> System ready <TEACH-AIR-01,{idx}>" in log for t, base, idx in (("11.2579", "BASE-01", 0), ("13.1667", "BASE-02", 1), ("23.9473", "BASE-01", 0), ("36", "BASE-01", 0))))
    ck("six missions four abort two success", log.count("mission ordered: BASIC-MISSION") == 6 and log.count("mission aborted:") == 4 and log.count("mission success:") == 2)
    ck("terminal ID6 upward in transit", "Time: 35.6667  transport request <<TEACH-LRU-01,0,6>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-02,0>> started" in log and "Start repair of item <TEACH-LRU-01,0,6>" not in log)
    report = {t["name"]: t for t in parse_native(run / "report-raw.json")["report"]["tables"]}
    ck("four report tables", set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary = rows(report["ResultSummary"])[0]
    ck("36h and mission success", summary["NREP"] == 1 and summary["RTILW"] == 0 and summary["RTIUP"] == 36 and abs(summary["MSUF"] - 2 / 6) < 1e-6)
    system, stock_result = (rows(report[name]) for name in ("SystemResults", "StockTotalResults"))
    ck("72 system bins", len(system) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(system)))
    ck("72 stock bins", len(stock_result) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(stock_result)))
    ck("reported one-hour local backorder", [i for i, r in enumerate(stock_result) if r["NBO"] > 0] == [23, 24] and all(stock_result[i]["NBO"] == 1 for i in (23, 24)))
    ck("second base ready after replenishment", system[24]["NSYRY"] == 1 and system[27]["NSYRY"] == 2)
    ck("terminal interval and event", system[-1]["NSYRY"] == system[-1]["NSYA"] == 1 and stock_result[-1]["NBO"] == 0 and "Time: 36 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log)
    result = {"schema": "simlox-e12-var07-two-depot-dfrac-v100-author-validation/v1", "passed": not failures,
              "checks_total": checks, "checks_passed": checks - len(failures), "failures": failures,
              "run_id": RUN_ID, "closure_sha256": sha(run / "closure.json"), "event_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"),
              "selected_depots": sorted({depot for _, depot, _, _ in demands}), "demand_routes": demands}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
