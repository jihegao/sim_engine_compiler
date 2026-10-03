"""Author replay of paired E10.var06 same-item MINBS evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_IDS = {
    "minbs1": "e10-var06-minbs1-v100-ssh-20261003-01",
    "minbs2": "e10-var06-minbs2-v100-ssh-20261003-01",
}
CLOSURE_SHA = {
    "minbs1": "76b5e93a5c827c988106ef5f3020f110b2686ec6372e3acc2e7c1cfcc6c81de1",
    "minbs2": "7f46c364aa4556b2bce8fe008df8fe7b38aeecd7736d72fa31ff8a6bdbcc7c00",
}
RAW_NAMES = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "steps.json", "roundtrip-validation.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def report(path: Path) -> dict:
    return {t["name"]: t for t in parse_native(path)["report"]["tables"]}


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, passed: bool) -> None:
        nonlocal checks
        checks += 1
        if not passed:
            failures.append(label)

    contract, diff = (read(HERE / name) for name in ("contract.json", "exact-diff.json"))
    parent = ROOT / contract["accepted_parent"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    support = ROOT / contract["accepted_support"]["package"]
    support_run = support / "runs" / contract["accepted_support"]["run_id"]
    ck("frozen contract/diff", contract["variant_id"] == "E10.var06" and contract["case_version"] == "1.0.0-candidate" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("accepted E10 ONDEM parent", sha(parent / "native-input-ondem.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("accepted E03 support", sha(support / "native-input.json") == contract["accepted_support"]["input_sha256"] == diff["support_e03_sha256"] and sha(support_run / "closure.json") == contract["accepted_support"]["native_closure_sha256"] and sha(support / "cli-scope-signoff-2026-09-29.md") == contract["accepted_support"]["signoff_sha256"])
    ck("frozen model delta", diff["changed_tables_parent_to_arm1"] == ["Item", "OperationProfile", "ProblemDescription", "StockAllocation", "System", "SystemDeployment"] and diff["changed_tables_arm1_to_arm2"] == ["ProblemDescription", "TransportPolicyProfile"] and diff["arm1_policy_row"][6] == 1 and diff["arm2_policy_row"][6] == 2)

    reports: dict[str, dict] = {}
    logs: dict[str, str] = {}
    for arm, run_id in RUN_IDS.items():
        run = HERE / "runs" / run_id
        ck(f"{arm} child input", sha(HERE / f"native-input-{arm}.json") == contract["native_inputs_sha256"][arm] == diff[f"arm{arm[-1]}_sha256"])
        ck(f"{arm} closure seal", sha(run / "closure.json") == CLOSURE_SHA[arm])
        inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} native identity", inv["variant_id"] == "E10.var06" and inv["arm"] == closure["arm"] == arm and inv["run_id"] == closure["run_id"] == run_id)
        ck(f"{arm} SSH GUI queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        ck(f"{arm} source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
        pins = inv["source_hashes_before"]
        ck(f"{arm} local source pins", all(pins[key] == sha(HERE / name) for key, name in (("input", f"native-input-{arm}.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
        ck(f"{arm} parent/support pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"] and pins["support"] == contract["accepted_support"]["input_sha256"] and pins["support_closure"] == contract["accepted_support"]["native_closure_sha256"] and pins["support_signoff"] == contract["accepted_support"]["signoff_sha256"])
        ck(f"{arm} installed source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
        ck(f"{arm} five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} raw set", set(closure["raw"]) == RAW_NAMES)
        for name, meta in closure["raw"].items():
            ck(f"{arm} raw {name}", (run / name).stat().st_size == meta["bytes"] > 4 and sha(run / name) == meta["sha256"])
        before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm} exact 22-table roundtrip", sha(run / "input.json") == contract["native_inputs_sha256"][arm] and read(run / "roundtrip-validation.json")["passed"] is True and len(before) == 22 and all(after.get(name) == table for name, table in before.items()))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} converter status", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
        ck(f"{arm} nonempty native output", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))
        reports[arm] = report(run / "report-raw.json")
        logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")

    a, b = logs["minbs1"], logs["minbs2"]
    for arm, log in logs.items():
        ck(f"{arm} two distinct failed items", log.count("critical random failure added") == 2 and all(f"<TEACH-LRU-01,0,{id}>" in log for id in (2, 3)))
        ck(f"{arm} two local/depot demands", log.count("Item demand arrives from pos <TEACH-AIR-01") == 2 and log.count("Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0>") == 2)
        ck(f"{arm} two depot issues", all(f"Take replacement item <TEACH-LRU-01,0,{id}> from stock" in log for id in (0, 1)) and log.count("Take replacement item") == 2)
        ck(f"{arm} two backorders clear", log.count("Backorder added") == log.count("Backorder removed") == 2)
        ck(f"{arm} two upward failed-item cycles", all(f"Put back replacement item <TEACH-LRU-01,0,{id}> to stock" in log for id in (2, 3)) and log.count("Put back replacement item") == 2)
        ck(f"{arm} two mission aborts", log.count("mission aborted:") == 2 and "mission success:" not in log)
        ck(f"{arm} no resource demand", "requests resources: no resources needed" in log and "allocated to maintenance task" not in log)
    ck("same fault and demand instants", all(f"Time: {time} <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" in a and f"Time: {time} <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" in b for time in ("8.37658", "8.6265")))
    ck("MINBS1 immediate separate downward departures", "Time: 8.37658  transport task 1 starts with 1 items/systems, transport time: 2" in a and "Time: 8.6265  transport task 4 starts with 1 items/systems, transport time: 2" in a and "Time: 10.3766  transport task 1 arrives with 1 items/systems" in a and "Time: 10.6265  transport task 4 arrives with 1 items/systems" in a)
    ck("MINBS2 first request held", "Time: 8.37658  transport task 1 cancelled with 1 items/systems" in b and "Time: 8.37658  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 0" in b and "Time: 8.37658  transport task 1 starts" not in b)
    ck("MINBS2 single two-spare departure", "Time: 8.6265  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  transport task 4" in b and "Time: 8.6265  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  transport task 4" in b and "Time: 8.6265  transport task 4 starts with 2 items/systems, transport time: 2" in b and "Time: 10.6265  transport task 4 arrives with 2 items/systems" in b)
    ck("different downward arrival times", "Time: 10.3766 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in a and "Time: 10.6265 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in b and b.count("Time: 10.6265 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives") == 2)
    ck("backorder delay difference", "Time: 10.3766 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 2" in a and "Time: 10.6265 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 2.24992" in b)
    ck("terminal ready and closed shipments", all(log.count("starts with 1 items/systems, transport time: 2") + log.count("starts with 2 items/systems, transport time: 2") == log.count("arrives with 1 items/systems") + log.count("arrives with 2 items/systems") for log in (a, b)) and a.count("System ready <TEACH-AIR-01") >= 2 and b.count("System ready <TEACH-AIR-01") >= 2)

    ra, rb = reports["minbs1"], reports["minbs2"]
    ck("same report table set", set(ra) == set(rb) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("same mission summary", ra["ResultSummary"] == rb["ResultSummary"] and rows(ra["ResultSummary"])[0]["MSUF"] == 0)
    for arm, report_tables in reports.items():
        sysrows, stockrows = rows(report_tables["SystemResults"]), rows(report_tables["StockTotalResults"])
        ck(f"{arm} 72 aligned bins", len(sysrows) == len(stockrows) == 72 and all(sysrows[i]["STINT"] == stockrows[i]["STINT"] == i / 2 and sysrows[i]["ETINT"] == stockrows[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} two failures repairs demands", sum(r["NFAIL"] or 0 for r in sysrows) == sum(r["NREPT"] or 0 for r in sysrows) == sum(r["NDF"] or 0 for r in stockrows) == 2)
        ck(f"{arm} terminal two ready no backorder", sysrows[-1]["NSYRY"] == 2 and stockrows[-1]["NBO"] == 0)
    system_a, system_b = rows(ra["SystemResults"]), rows(rb["SystemResults"])
    stock_a, stock_b = rows(ra["StockTotalResults"]), rows(rb["StockTotalResults"])
    ck("backorder occupancy changes by quarter hour", abs(sum(r["NBO"] for r in stock_a) / 2 - 4) < 1e-5 and abs(sum(r["NBO"] for r in stock_b) / 2 - 4.249925) < 1e-4)
    ck("only bins 16 20 21 system differ", [i for i in range(72) if system_a[i] != system_b[i]] == [16, 20, 21])
    ck("only bins 16 20 21 stock differ", [i for i in range(72) if stock_a[i] != stock_b[i]] == [16, 20, 21])
    result = {"schema": "simlox-e10-var06-minbs-same-item-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "paired_bounded_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
