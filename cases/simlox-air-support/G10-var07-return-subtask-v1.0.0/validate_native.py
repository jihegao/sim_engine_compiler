"""Author replay of the paired first-subtask-at-return native evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var06-online-repair-v1.0.0"
DONOR = HERE.parent / "D09-var04-shortage-at-escalation-v1.0.0"
ARMS = ("crew-present", "crew-absent")
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "model_Prelife.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table = next(t for t in doc[root]["tables"] if t["name"] == name)
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def bin_counts(values: list[float]) -> list[int]:
    result = [0] * 72
    for value in values:
        result[int(value * 2)] += 1
    return result


def occupancy(start: float, end: float) -> list[float]:
    return [2 * max(0, min(end, (i + 1) / 2) - max(start, i / 2)) for i in range(72)]


def occupancy_many(intervals: list[tuple[float, float]]) -> list[float]:
    return [sum(occupancy(start, end)[i] for start, end in intervals) for i in range(72)]


def same_bins(actual: list[float], expected: list[float], tolerance: float = .0001) -> bool:
    return len(actual) == len(expected) == 72 and all(abs(a - b) < tolerance for a, b in zip(actual, expected))


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("frozen contract/diff", contract["variant_id"] == "G10.var07" and sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    ck("accepted parent", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"] and sha(PARENT / "cli-scope-signoff-2026-10-03.md") == contract["parent"]["signoff_sha256"] and sha(PARENT / "runs" / contract["parent"]["native_run_id"] / "closure.json") == contract["parent"]["native_closure_sha256"])
    ck("accepted donor", sha(DONOR / "native-input-supplied.json") == contract["resource_donor"]["input_sha256"] and sha(DONOR / "cli-scope-signoff-2026-10-02.md") == contract["resource_donor"]["signoff_sha256"])
    ck("controlled table diff", diff["parent_changed_tables"] == ["MissionType", "OperationProfile", "ProblemDescription", "Resource", "ResourceAllocation", "SubTaskResource", "SystemRepair", "TaskBreakDown"] and diff["pair_changed_tables"] == ["ProblemDescription", "ResourceAllocation"] and diff["pair_changes"]["ResourceAllocation"]["before"][0][3] == 1 and diff["pair_changes"]["ResourceAllocation"]["after"][0][3] == 0)

    logs: dict[str, str] = {}
    reports: dict[str, dict[str, list[dict]]] = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g10-var07-{arm}-v100-ssh-20261003-01"
        source_sha = contract["arms"][arm]["input_sha256"]
        invocation, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} source input", sha(HERE / f"native-input-{arm}.json") == sha(run / "input.json") == source_sha == diff["crew_present_sha256" if arm == "crew-present" else "crew_absent_sha256"])
        ck(f"{arm} invocation/closure", invocation["arm"] == closure["arm"] == arm and invocation["run_id"] == closure["run_id"] == run.name and closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
        bound = {"contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1", "exact_diff": HERE / "exact-diff.json", "parent": PARENT / "native-input.json", "parent_signoff": PARENT / "cli-scope-signoff-2026-10-03.md", "parent_closure": PARENT / "runs" / contract["parent"]["native_run_id"] / "closure.json", "donor": DONOR / "native-input-supplied.json", "donor_signoff": DONOR / "cli-scope-signoff-2026-10-02.md", "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"), "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
        for key, path in bound.items():
            ck(f"{arm} bound {key}", invocation["source_hashes_before"].get(key) == sha(path))
        ck(f"{arm} source binary", invocation["simlox_exe_sha256"] == sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")) and invocation["source_hashes_before"]["python"] == sha(Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")))
        ck(f"{arm} guarded SSH", invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm} raw set", set(closure["raw"]) == RAW)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} sealed {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        ck(f"{arm} five completed steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
        source, exported = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        rt = read(run / "roundtrip-validation.json")
        ck(f"{arm} 25-table roundtrip", rt["passed"] and not rt["differences"] and len(source) == 25 and all(exported.get(name) == table for name, table in source.items()))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} zero-error conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}) and "(error #" not in conversion)
        log = logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        report = parse_native(run / "report-raw.json")
        reports[arm] = {name: rows(report, "report", name) for name in ("ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal")}
        sy, st, re_rows = (reports[arm][name] for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
        ck(f"{arm} 72 contiguous report bins", len(sy) == len(st) == len(re_rows) == 72 and all(sy[i]["STINT"] == st[i]["STINT"] == re_rows[i]["STINT"] == i / 2 and sy[i]["ETINT"] == st[i]["ETINT"] == re_rows[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        fault_times = [float(x) for x in re.findall(r"^Time: ([\d.]+) <TEACH-AIR-01,0> noncritical random failure added", log, re.M)]
        replacement_times = [float(x) for x in re.findall(r"^Time: ([\d.]+)  system SURP task 0 on <TEACH-AIR-01,0> completed", log, re.M)]
        demand_times = [float(x) for x in re.findall(r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives", log, re.M)]
        ck(f"{arm} one matched noncritical physical fault", fault_times == [8.31382] and not re.search(r"^Time: [\d.]+ <TEACH-AIR-01,0> critical random failure added", log, re.M) and "subitem failed: <TEACH-LRU-01,0,3>" in log)
        ck(f"{arm} per-bin physical and replacement counts", [r["NFAIL"] for r in sy] == bin_counts(fault_times) and [r["NREPT"] for r in sy] == bin_counts(replacement_times))
        ck(f"{arm} per-bin stock demands/waits", [r["NDF"] for r in st] == [r["NWT"] for r in st] == bin_counts(demand_times) and all(r["NBO"] == 0 for r in st))
        ck(f"{arm} first mission success", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "mission aborted:" not in log)
        ck(f"{arm} no stock backorder", "Backorder added" not in log and "Backorder removed" not in log and len(re.findall(r"Take replacement item <TEACH-LRU-01", log)) == 1)
        ck(f"{arm} two mission successes", len(re.findall(r"mission success:", log)) == 2 and len(re.findall(r"mission completed:", log)) == 2)
        ck(f"{arm} report summary scope", len(reports[arm]["ResultSummary"]) == 1 and reports[arm]["ResultSummary"][0]["NREP"] == 1 and reports[arm]["ResultSummary"][0]["RTIUP"] == 36 and reports[arm]["ResultSummary"][0]["MSTF"] == reports[arm]["ResultSummary"][0]["MSUF"] == 0)

    present, absent = logs["crew-present"], logs["crew-absent"]
    ps, pt, pr = (reports["crew-present"][name] for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
    a_s, a_t, ar = (reports["crew-absent"][name] for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
    ck("present removal actively performs and repair open at return", "Time: 8.31382  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> starts performing" in present and "Time: 8.48048  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed" in present and "Time: 11.3138  system SURP task 0 on <TEACH-AIR-01,0> completed" in present and "Time: 9 <TEACH-AIR-01,BASE-01,0> System arrives" in present)
    ck("absent removal waits and no repair completion", "Time: 8.31382  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> resource availability test" in absent and "request for: 1 failed" in absent and "starts performing" not in absent and "system SURP task 0 on <TEACH-AIR-01,0> completed" not in absent)
    ck("present return inhibited", "Time: 9 <TEACH-AIR-01,0> nbr ready increased at unit:" in present and "Time: 9 <TEACH-AIR-01,0> nbr ready decreased at unit:" in present and "Time: 10.5 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission suspended:" in present and "Time: 11.3138 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission resumed:" in present)
    ck("absent return NCF ready and reused", "Time: 9 <TEACH-AIR-01,BASE-01,0> System NCF ready" in absent and "Time: 9.5 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission allocates system:" in absent and "Time: 10.5 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 1 : <TEACH-AIR-01,0>" in absent)
    ck("matched stock issue, divergent returns", present.count("Take replacement item <TEACH-LRU-01") == absent.count("Take replacement item <TEACH-LRU-01") == 1 and present.count("Put back replacement item <TEACH-LRU-01") == 1 and absent.count("Put back replacement item <TEACH-LRU-01") == 0 and present.count("Take replacement item <TEACH-SRU-01") == present.count("Put back replacement item <TEACH-SRU-01") == 1 and "Take replacement item <TEACH-SRU-01" not in absent)
    ck("crew allocation/deallocation ledger", present.count("allocated to maintenance task: 1") == present.count("deallocated from  maintenance task: 1") == 1 and "allocated to maintenance task: 1" not in absent)
    ck("present system state 72 bins", same_bins([r["NSYRP"] for r in ps], occupancy(9, 11.3138)) and same_bins([r["NSYA"] for r in ps], [1 - x for x in occupancy(9, 11.3138)]) and same_bins([r["NSYMA"] for r in ps], occupancy_many([(7, 9), (11.3138, 11.5)])) and same_bins([r["NSYMO"] for r in ps], occupancy_many([(8, 9), (11.3138, 11.5)])))
    ck("absent system state 72 bins", same_bins([r["NSYRP"] for r in a_s], [0] * 72) and same_bins([r["NSYA"] for r in a_s], [1] * 72) and same_bins([r["NSYMA"] for r in a_s], occupancy_many([(7, 9), (9.5, 11.5)])) and same_bins([r["NSYMO"] for r in a_s], occupancy_many([(8, 9), (10.5, 11.5)])))
    ck("resource allocated/waiting 72 bins", same_bins([r["NRUM"] for r in pr], occupancy(8.31382, 8.48048)) and same_bins([r["NRW"] for r in pr], [0] * 72) and same_bins([r["NRW"] for r in ar], occupancy(8.31382, 36)) and same_bins([r["NRUM"] for r in ar], [0] * 72))
    ck("resource capacity 72 bins", all(r["NR"] == r["NRA"] == r["NRN"] == 1 for r in pr) and all(r["NR"] == r["NRA"] == r["NRN"] == 0 for r in ar))
    ck("stock terminal and 72 bins", all(r["NBO"] == 0 for r in pt + a_t) and ps[-1]["NSYRY"] == a_s[-1]["NSYRY"] == 1 and ps[-1]["NSYRP"] == a_s[-1]["NSYRP"] == 0)
    result = {"schema": "simlox-g10-var07-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "arms": list(ARMS), "scope": "paired_first_subtask_return_boundary_native_cli", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}, indent=2))
        sys.exit(1)
