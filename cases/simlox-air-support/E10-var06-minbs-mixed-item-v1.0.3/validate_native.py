"""Author replay of bounded, fixed-seed E10.var06 mixed-IID MINBS evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_IDS = {a: f"e10-var06-mixed-{a}-v103-ssh-20261003-01" for a in ("minbs1", "minbs2")}
CLOSURE_SHA = {
    "minbs1": "124bfff95458b07d1b3efff1b7e0c1b20da1dbcd75d6ecf02101cc2fca8ba815",
    "minbs2": "047c31bea78a1ffe0dbd110d80f513df09524dbaad1eb77ae1f17152f0444ee1",
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
    ck("frozen contract", contract["variant_id"] == "E10.var06" and contract["case_version"] == "1.0.3-candidate" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    for arm in RUN_IDS:
        p = contract["accepted_parent"]
        ck(f"{arm} accepted parent", sha(parent / f"native-input-{arm}.json") == p["input_sha256"][arm] == diff["parent_inputs_sha256"][arm] and sha(parent / "runs" / p["run_ids"][arm] / "closure.json") == p["native_closure_sha256"][arm] and sha(parent / "evidence-index.json") == p["evidence_index_sha256"])
    for field in ("prior_diagnostic_no_go", "second_diagnostic_no_go", "third_diagnostic_no_go"):
        diagnostic = contract[field]
        pkg = ROOT / diagnostic["package"]
        for arm in RUN_IDS:
            matches = list((pkg / "runs").glob(f"*{arm}*/*closure.json"))
            ck(f"{field} {arm} sealed", len(matches) == 1 and sha(matches[0]) == diagnostic["native_closure_sha256"][arm] and sha(pkg / f"native-input-{arm}.json") == diagnostic["input_sha256"][arm])
    ck("frozen delta", diff["changed_tables_each_parent_to_child"] == ["Control", "Item", "ItemRepair", "ItemStructure", "ProblemDescription", "StockAllocation", "System"] and diff["changed_tables_between_child_arms"] == ["ProblemDescription", "TransportPolicyProfile"] and diff["arm1_policy_row"][6] == 1 and diff["arm2_policy_row"][6] == 2)

    logs: dict[str, str] = {}
    reports: dict[str, dict] = {}
    for arm, run_id in RUN_IDS.items():
        run = HERE / "runs" / run_id
        inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} child input and closure", sha(HERE / f"native-input-{arm}.json") == contract["native_inputs_sha256"][arm] == diff[f"arm{arm[-1]}_sha256"] and sha(run / "closure.json") == CLOSURE_SHA[arm])
        ck(f"{arm} invocation identity", inv["run_id"] == closure["run_id"] == run_id and inv["arm"] == closure["arm"] == arm and inv["case_version"] == "1.0.3-candidate")
        ck(f"{arm} guarded session", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        ck(f"{arm} source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
        pins = inv["source_hashes_before"]
        ck(f"{arm} package pins", all(pins[key] == sha(HERE / name) for key, name in (("input", f"native-input-{arm}.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
        ck(f"{arm} accepted and diagnostic pins", all(pins[key] == contract["accepted_parent"][field][source_arm] for key, field, source_arm in (("parent_minbs1", "input_sha256", "minbs1"), ("parent_minbs2", "input_sha256", "minbs2"), ("parent_closure_minbs1", "native_closure_sha256", "minbs1"), ("parent_closure_minbs2", "native_closure_sha256", "minbs2"))) and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"] and all(pins[f"{prefix}_closure_{a}"] == contract[field]["native_closure_sha256"][a] for prefix, field in (("prior_diagnostic", "prior_diagnostic_no_go"), ("second_diagnostic", "second_diagnostic_no_go"), ("third_diagnostic", "third_diagnostic_no_go")) for a in RUN_IDS))
        ck(f"{arm} installed source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
        ck(f"{arm} guarded five steps", [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True for step in steps))
        ck(f"{arm} raw set", set(closure["raw"]) == RAW_NAMES)
        for name, meta in closure["raw"].items():
            ck(f"{arm} sealed {name}", (run / name).stat().st_size == meta["bytes"] > 4 and sha(run / name) == meta["sha256"])
        before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm} all 22 business tables roundtrip", sha(run / "input.json") == contract["native_inputs_sha256"][arm] and read(run / "roundtrip-validation.json")["passed"] is True and len(before) == 22 and all(after.get(name) == table for name, table in before.items()))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} zero conversion errors", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
        ck(f"{arm} nonempty SXO/log/report", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))
        logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        reports[arm] = report(run / "report-raw.json")

    expected_demands = Counter({("8.0822", "TEACH-LRU-01", "4"): 1, ("8.0822", "TEACH-LRU-02", "5"): 1, ("8.66291", "TEACH-LRU-02", "6"): 1, ("8.66291", "TEACH-LRU-01", "7"): 1})
    expected_issues = Counter({("TEACH-LRU-01", "0"): 1, ("TEACH-LRU-02", "2"): 1, ("TEACH-LRU-02", "3"): 1, ("TEACH-LRU-01", "1"): 1})
    for arm, log in logs.items():
        demands = Counter(re.findall(r"Time: ([\d.]+) <(TEACH-LRU-0[12]),0,DEPOT-01,0> Item demand arrives from pos .*item requiring maintenance is <TEACH-LRU-0[12],0,(\d+)>", log))
        issues = Counter(re.findall(r"Take replacement item <(TEACH-LRU-0[12]),0,(\d+)> from stock", log))
        ck(f"{arm} four exact mixed demands", demands == expected_demands and log.count("Item demand arrives from pos <TEACH-AIR-01") == 4)
        ck(f"{arm} four exact physical depot issues", issues == expected_issues and log.count("Take replacement item") == 4)
        ck(f"{arm} four failure/repair cycles", log.count("critical random failure added") == 4 and log.count("Start repair of item") == log.count("Finished repair of item") == log.count("Put back replacement item") == 4)
        ck(f"{arm} four cleared backorders", log.count("Backorder added") == log.count("Backorder removed") == 4 and all(log.count(f"<TEACH-LRU-0{i},0,BASE-01,0> Backorder removed, waiting time was 2") == 2 for i in (1, 2)))
        ck(f"{arm} two aborted missions and ready aircraft", log.count("mission aborted:") == 2 and log.count("mission success:") == 0 and log.count("System ready <TEACH-AIR-01") == 2)
        ck(f"{arm} no maintenance resource contention", "requests resources: no resources needed" in log and "allocated to maintenance task" not in log)
        ck(f"{arm} all transport tasks close", len(re.findall(r"transport task \d+ starts with [12] items/systems", log)) == len(re.findall(r"transport task \d+ arrives with [12] items/systems", log)))
    a, b = logs["minbs1"], logs["minbs2"]
    ck("MINBS1 four separate downward tasks", all(f"Time: {t}  transport task {task} starts with 1 items/systems, transport time: 2" in a for t, task in (("8.0822", 1), ("8.0822", 2), ("8.66291", 6), ("8.66291", 7))) and a.count("starts with 2 items/systems") == 0)
    ck("MINBS2 two held provisional tasks", all(f"Time: {t}  transport task {task} cancelled with 1 items/systems" in b and f"Time: {t}  transport task {task} starts" not in b for t, task in (("8.0822", 1), ("8.66291", 6))))
    ck("MINBS2 two mixed two-item tasks", all(f"Time: {t}  transport task {task} starts with 2 items/systems, transport time: 2" in b and f"Time: {arrive}  transport task {task} arrives with 2 items/systems" in b for t, task, arrive in (("8.0822", 2, "10.0822"), ("8.66291", 7, "10.6629"))) and b.count("starts with 2 items/systems") == 2)
    for task, iid1, iid2 in ((2, ("TEACH-LRU-01", 0), ("TEACH-LRU-02", 2)), (7, ("TEACH-LRU-01", 1), ("TEACH-LRU-02", 3))):
        ck(f"MINBS2 task {task} physical mixed payload", all(f"transport request <<{iid},0,{serial}>,<{iid},0,DEPOT-01,0>,<{iid},0,BASE-01,0>> attached to  transport task {task}" in b and f"transport request <<{iid},0,{serial}>,<{iid},0,DEPOT-01,0>,<{iid},0,BASE-01,0>> started" in b for iid, serial in (iid1, iid2)))
    ck("same two-hour spare arrival times", all(f"Time: {t} <{iid},0,BASE-01,0> Replacement item arrives <{iid},0,{serial}>" in log for log in (a, b) for t, iid, serial in (("10.0822", "TEACH-LRU-01", 0), ("10.0822", "TEACH-LRU-02", 2), ("10.6629", "TEACH-LRU-01", 1), ("10.6629", "TEACH-LRU-02", 3))))

    ra, rb = reports["minbs1"], reports["minbs2"]
    ck("same report tables and summary", set(ra) == set(rb) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"} and ra["ResultSummary"] == rb["ResultSummary"] and rows(ra["ResultSummary"])[0]["MSUF"] == 0)
    for arm, tables in reports.items():
        sysrows, stockrows = rows(tables["SystemResults"]), rows(tables["StockTotalResults"])
        ck(f"{arm} all 72 aligned half-hour bins", len(sysrows) == len(stockrows) == 72 and all(sysrows[i]["STINT"] == stockrows[i]["STINT"] == i / 2 and sysrows[i]["ETINT"] == stockrows[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} four report failures/repairs/demands", sum(r["NFAIL"] or 0 for r in sysrows) == sum(r["NREPT"] or 0 for r in sysrows) == sum(r["NDF"] or 0 for r in stockrows) == 4)
        ck(f"{arm} four two-hour backorders", abs(sum(r["NBO"] or 0 for r in stockrows) / 2 - 8) < 1e-5 and sum(r["NWT"] or 0 for r in stockrows) == 4)
        ck(f"{arm} terminal ready/clear", sysrows[-1]["NSYRY"] == 2 and stockrows[-1]["NBO"] == 0 and sysrows[-1]["NSYRP"] == 0)
    ck("identical metrics and bins", ra["SystemResults"] == rb["SystemResults"] and ra["StockTotalResults"] == rb["StockTotalResults"])
    result = {"schema": "simlox-e10-var06-minbs-mixed-item-v103-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "observations": {"downward_tasks_minbs1": 4, "downward_tasks_minbs2": 2, "spares_per_task_minbs2": 2, "distinct_item_types_per_batch": 2, "depot_spare_demands": 4, "report_difference_bins": [], "wait_benefit_claimed": False}, "scope": "fixed_seed_structural_mixed_iid_replication", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
