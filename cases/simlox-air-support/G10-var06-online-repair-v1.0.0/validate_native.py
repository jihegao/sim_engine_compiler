"""Author replay of the fixed-seed continuous redundancy-repair native run."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var03-nrlrq-crossing-v1.0.0"
PARENT_RUN = PARENT / "runs/g10-var03-nrlrq-crossing-v100-ssh-20261003-01"
DONOR = HERE.parent / "G05-unavailable-standby-v1.0.3"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "model_Prelife.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table = next(t for t in doc[root]["tables"] if t["name"] == name)
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for instance in table["instances"] for row in instance["rows"]]


def events(log: str, pattern: str) -> list[tuple]:
    return re.findall(pattern, log, re.M)


def times(log: str, pattern: str) -> list[float]:
    return [float(x) for x in events(log, r"^Time: ([\d.]+) " + pattern)]


def bin_counts(values: list[float], bins: int = 72) -> list[int]:
    result = [0] * bins
    for value in values:
        result[int(value * 2)] += 1
    return result


def backlog_means(log: str, iid: str, bins: int = 72) -> tuple[list[float], int, int, bool]:
    prefix = re.escape(f"<{iid},0,BASE-01,0>")
    adds = times(log, prefix + r" Backorder added")
    removes = times(log, prefix + r" Backorder removed")
    edges = sorted([(t, 1) for t in adds] + [(t, -1) for t in removes])
    level = 0
    safe = True
    for _, delta in edges:
        level += delta
        safe &= level >= 0
    safe &= level == 0
    means = []
    for index in range(bins):
        start, end = index / 2, (index + 1) / 2
        level = sum(delta for time, delta in edges if time < start)
        previous = start
        area = 0.0
        for time, delta in edges:
            if start <= time < end:
                area += level * (time - previous)
                previous = time
                level += delta
        area += level * (end - previous)
        means.append(area / (end - start))
    return means, len(adds), len(removes), safe


def validate(run: Path) -> dict:
    errors: list[str] = []
    checks = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            errors.append(label)

    contract = load(HERE / "contract.json")
    input_sha = contract["native_input_sha256"]
    ck("frozen input", sha(HERE / "native-input.json") == sha(run / "input.json") == input_sha)
    ck("accepted parent", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"] and sha(PARENT_RUN / "closure.json") == contract["parent"]["native_closure_sha256"] and sha(PARENT / "cli-scope-signoff-2026-10-03.md") == contract["parent"]["signoff_sha256"])
    ck("accepted mission donor", sha(DONOR / "unavailable-input.json") == contract["mission_recipe_donor"]["input_sha256"] and sha(DONOR / "cli-scope-signoff-2026-10-02.md") == contract["mission_recipe_donor"]["signoff_sha256"])
    ck("exact parent delta", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"] and load(HERE / "exact-diff.json")["changed_tables"] == ["MissionType", "OperationProfile", "ProblemDescription"])
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", invocation.get("case_id") == "G10" and invocation.get("case_version") == "1.0.0-candidate" and invocation.get("run_id") == run.name)
    ck("source parent bound", invocation.get("input_sha256") == input_sha and invocation.get("parent_sha256") == contract["parent"]["input_sha256"])
    bound = (("contract", HERE / "contract.json"), ("builder", HERE / "build.py"), ("checker", HERE / "check_roundtrip.py"), ("runner_script", HERE / "run_native_ssh.ps1"), ("parent_signoff", PARENT / "cli-scope-signoff-2026-10-03.md"), ("parent_closure", PARENT_RUN / "closure.json"), ("donor", DONOR / "unavailable-input.json"), ("donor_signoff", DONOR / "cli-scope-signoff-2026-10-02.md"), ("manual", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), ("dictionary", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")))
    for key, path in bound:
        ck(f"bound source {key}", invocation["source_hashes_before"].get(key) == sha(path))
    ck("SSH0/queue/GUI", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True and "sshd.exe" in invocation.get("ssh_ancestor_names", []) and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue" and invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("clean closure", closure.get("error") is None and closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("complete raw set", set(closure["raw"]) == RAW)
    for name, seal in closure["raw"].items():
        path = run / name
        ck(f"sealed {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    ck("five native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    rt = load(run / "roundtrip-validation.json")
    ck("22-table roundtrip", rt["passed"] and rt["differences"] == [] and len(rt["populated_tables"]) == 22)
    source, exported = (parse_native(path) for path in (HERE / "native-input.json", run / "roundtrip-raw.json"))
    ck("all populated business rows", all(populated(exported).get(name) == table for name, table in populated(source).items()))
    mission, profile, repair = (rows(exported, "model", name) for name in ("MissionType", "OperationProfile", "SystemRepair"))
    ck("continuous mission and local replacement", len(mission) == len(profile) == len(repair) == 1 and mission[0]["DURN"] == 26 and mission[0]["MPAT"] == "CONTINUOUS" and mission[0]["TFOUT"] is None and mission[0]["TFRET"] is None and profile[0]["STIM"] == 8 and repair[0]["STID"] == "BASE-01" and repair[0]["SURPT"] == .5)
    ck("spares and no authored resource demand", any(r["IID"] == "TEACH-LRU-01" and r["STID"] == "BASE-01" and r["STSIZ"] == 2 for r in rows(exported, "model", "StockAllocation")) and not rows(source, "model", "ResourceAllocation") and not rows(source, "model", "TaskResource") and not rows(source, "model", "SubTaskResource"))
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("clean conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and len(re.findall(r"\(warning #108\)", runlog)) == 1 and len(re.findall(r"\(warning #\d+\)", runlog)) == 1 and "(error #" not in runlog)

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    faults = re.findall(r"^Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) random failure added, now\s*\n(.*?)(?=^Time:|\Z)", log, re.M | re.S)
    fault_times = [float(t) for t, _, _ in faults]
    fault_ids = [int(re.findall(r"subitem failed: <TEACH-LRU-01,0,(\d+)>", block)[-1]) for _, _, block in faults]
    ck("26 physical failures and severities", len(faults) == 26 and len(set(fault_ids)) == 26 and fault_ids == list(range(3, 54, 2)) and [severity for _, severity, _ in faults].count("noncritical") == 20 and [severity for _, severity, _ in faults].count("critical") == 6)
    mission_start = times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting")
    mission_success = times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:")
    sys_start = [(float(t), int(task)) for t, task in events(log, r"^Time: ([\d.]+)  system SURP task (\d+) on <TEACH-AIR-01,0> started")]
    sys_end = [(float(t), int(task)) for t, task in events(log, r"^Time: ([\d.]+)  system SURP task (\d+) on <TEACH-AIR-01,0> completed")]
    ck("one continuous mission eventually succeeds", mission_start == [8] and mission_success == [34] and "mission aborted:" not in log and len(times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:")) == 1)
    suspended = times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,0> mission suspended:")
    resumed = times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,0> mission resumed:")
    critical = [float(t) for t, severity, _ in faults if severity == "critical"]
    ck("six critical suspension and resume cycles", len(critical) == len(suspended) == len(resumed) == log.count("aborts its mission") == 6 and suspended == critical and all(start <= end <= mission_success[0] for start, end in zip(suspended, resumed)))
    ck("first uninterrupted on-mission repair", len(sys_start) == len(sys_end) == 26 and sys_start[0] == (8.31382, 0) and sys_end[0] == (8.81382, 0) and mission_start[0] < sys_start[0][0] < sys_end[0][0] < suspended[0])
    ck("each failure starts one ordered system repair", len(sys_start) == 26 and all(abs(fault_times[i] - sys_start[i][0]) < .0001 for i in range(26)) and {task for _, task in sys_start} == {task for _, task in sys_end} and all(next(end for end, task2 in sys_end if task2 == task) > start for start, task in sys_start))
    lru_repairs = [(float(t), int(item)) for t, _, item in events(log, r"^Time: ([\d.]+)  item SURP task (\d+) on <TEACH-LRU-01,0,(\d+)> completed")]
    sru_repairs = [(float(t), int(item)) for t, _, item in events(log, r"^Time: ([\d.]+)  item DIRP task (\d+) on <TEACH-SRU-01,0,(\d+)> completed")]
    ck("all nested LRU and SRU repairs", len(lru_repairs) == len(sru_repairs) == 26 and {iid for _, iid in lru_repairs} == set(fault_ids) and {iid for _, iid in sru_repairs} == {iid + 1 for iid in fault_ids})
    for iid, issues, backorders in (("TEACH-LRU-01", 19, 7), ("TEACH-SRU-01", 8, 18)):
        prefix = re.escape(f"<{iid},0,BASE-01,0>")
        issue_times = times(log, prefix + r" Take replacement item")
        return_times = times(log, prefix + r" Put back replacement item")
        means, adds, removes, safe = backlog_means(log, iid)
        ck(f"{iid} issues, returns, backorders", len(issue_times) == len(return_times) == issues and adds == removes == backorders and safe and issues + backorders == 26)
        added_times = times(log, prefix + r" Backorder added")
        cleared = [(float(t), float(wait)) for t, wait in events(log, r"^Time: ([\d.]+) " + prefix + r" Backorder removed, waiting time was ([\d.]+)")]
        ck(f"{iid} backorder waiting ledger", len(added_times) == len(cleared) and all(abs((end - start) - wait) < .002 for start, (end, wait) in zip(added_times, cleared)))
        levels = events(log, r"^  Stock at: " + prefix + r" Level: (\d+) Items:([^\n]*)")
        ck(f"terminal {iid} stock", bool(levels) and int(levels[-1][0]) == (2 if iid == "TEACH-LRU-01" else 1))
    ck("terminal log readiness", "Time: 34.4659 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log and "Time: 34.4659 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in log)

    report = parse_native(run / "report-raw.json")
    summary, systems, stocks = (rows(report, "report", name) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("continuous summary distinction", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36 and 0 < summary[0]["MTMF"] < 1 and summary[0]["MSTF"] == summary[0]["MSUF"] == 0)
    ck("72 contiguous System bins", len(systems) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(systems)))
    ck("72 contiguous Stock bins", len(stocks) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stocks)))
    ck("per-bin physical faults", [r["NFAIL"] for r in systems] == bin_counts(fault_times))
    ck("per-bin system replacements", [r["NREPT"] for r in systems] == bin_counts([t for t, _ in sys_end]))
    ck("per-bin system stock demands", [r["NDF"] for r in stocks] == bin_counts([t for t, _ in sys_start]) and [r["NWT"] for r in stocks] == bin_counts([t for t, _ in sys_start]))
    lru_nbo, _, _, _ = backlog_means(log, "TEACH-LRU-01")
    for index, (observed, expected) in enumerate(zip((r["NBO"] for r in stocks), lru_nbo)):
        ck(f"StockTotal LRU backlog bin {index}", abs(observed - expected) < .002)
    ck("six System downtime bins", [i for i,r in enumerate(systems) if r["NSYDT"]] == [28,31,50,52,64,67] and sum(r["NSYDT"] for r in systems) == 6)
    ck("terminal aircraft ready", systems[-1]["NSYRY"] == systems[-1]["NSYA"] == 1 and systems[-1]["NSYRP"] == 0)
    return {"schema": "simlox-g10-var06-v100-author-validation/v1", "case_id": "G10", "variant_id": "G10.var06", "run_id": run.name, "passed": not errors, "checks": checks, "differences": errors, "input_sha256": input_sha, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
