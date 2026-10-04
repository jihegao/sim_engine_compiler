"""Author replay of the bounded eight-aircraft, 43-day deterministic native pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {arm: HERE / "runs" / f"f04-var01-repeat-{arm}-v101-ssh-20261004-01"
        for arm in ("a", "b")}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log",
       "export.log", "model.sxo", "run.log", "model.log", "report-raw.json",
       "report-export.log", "steps.json", "roundtrip-validation.json"}
PREREQS = {
    "J04.var01": "J04-var01-fixed-replications-v1.0.0/cli-scope-signoff-2026-10-01.md",
    "J05.var05": "J05-horizon-v1.0.0/cli-scope-signoff-2026-10-01.md",
    "J06.var02": "J06-system-replication-v1.0.1/cli-scope-signoff-2026-10-04.md",
    "J07.var01": "J07-formation-denial-v1.0.0/cli-scope-signoff-2026-10-01.md",
    "J08.var01": "J08-item-stock-resource-ledger-v1.0.0/cli-scope-signoff-2026-10-04.md",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        out: list[str] = []
        quoted = escaped = False
        n = len(raw)
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == ",":
                j = i + 1
                while j < n and raw[j].isspace():
                    j += 1
                if j >= n or raw[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out))


def rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def events(log: str, pattern: str) -> list[re.Match]:
    return list(re.finditer(r"^Time: ([\d.]+) " + pattern, log, re.M))


def times_equal(matches: list[re.Match], expected: list[float]) -> bool:
    return [float(match.group(1)) for match in matches] == expected


def overlap(a: float, b: float, lo: float, hi: float) -> float:
    return max(0.0, min(b, hi) - max(a, lo)) / (hi - lo)


def resource_spans(log: str) -> list[tuple[float, float]]:
    spans = []
    for station in ("BASE-01", "BASE-02"):
        for rid in ("P-CREW", "P-MAINT"):
            starts = events(log, rf" <{rid} at <{station},0>> allocated to maintenance task: 1  available now: 0")
            ends = events(log, rf" <{rid} at <{station},0>> deallocated from  maintenance task: 1  available now: 1")
            if (station, rid) == ("BASE-02", "P-MAINT"):
                assert len(starts) == len(ends) + 1 and starts[-1].group(1) == "1031"
                ends = ends + [None]
            else:
                assert len(starts) == len(ends)
            spans.extend((float(a.group(1)), float(b.group(1)) if b else 1032.0)
                         for a, b in zip(starts, ends))
    return spans


def resource_queues(log: str) -> list[tuple[float, float]]:
    spans = []
    pending: dict[tuple[str, str, str], float] = {}
    now = None
    task = None
    for line in log.splitlines():
        tick = re.match(r"^Time: ([\d.]+)", line)
        if tick:
            now = float(tick.group(1))
        test_task = re.match(r"^Time: [\d.]+  (.+?) resource availability test", line)
        if test_task:
            task = test_task.group(1)
        test = re.search(r"<(?P<rid>P-CREW|P-MAINT) at <(?P<station>BASE-0[12]),0>> request for: 1 (?P<state>failed|OK)", line)
        if not test:
            continue
        assert now is not None and task is not None
        key = (test.group("station"), test.group("rid"), task)
        if test.group("state") == "failed":
            pending.setdefault(key, now)
        elif key in pending:
            spans.append((pending.pop(key), now))
    assert not pending
    return spans


def main() -> None:
    failures: list[str] = []
    checks = 0

    def ck(ok: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck(contract["case_id"] == "F04" and contract["variant_id"] == "F04.var01"
       and contract["version"] == "1.0.1-candidate"
       and sha(HERE / "native-input.json") == contract["input_sha256"]
       and sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
       and len(diff["changes"]) == 14, "frozen F04 source")
    parent = ROOT / "F03-var01-two-base-crew-v1.0.0"
    ck(sha(parent / "staffed-input.json") == contract["accepted_parent"]["input_sha256"]
       and sha(parent / "runs/f03-v101-staffed-ssh-20261004-01/closure.json") == contract["accepted_parent"]["closure_sha256"]
       and sha(parent / "cli-scope-signoff-2026-10-04.md") == contract["accepted_parent"]["signoff_sha256"],
       "accepted F03 parent")
    for key, path in PREREQS.items():
        ck(sha(ROOT / path) == contract["accepted_reporting_prerequisites_sha256"][key],
           f"accepted {key} signoff")
    source = native_json(HERE / "native-input.json")
    ck(len(populated(source)) == 30, "thirty populated authored tables")
    ck({c["table"] for c in diff["changes"]} ==
       {"ProblemDescription", "Control", "System", "Item", "SystemDeployment",
        "OperationProfile", "ResultCollection"}, "bounded seven-table change")
    report_sha = {}
    log_sha = {}
    summaries = {}
    for arm, run in RUNS.items():
        invocation, closure, steps = (read(run / n) for n in
                                      ("invocation.json", "closure.json", "steps.json"))
        ck(closure["error"] is None and closure["run_id"] == run.name
           and closure["invocation_sha256"] == sha(run / "invocation.json")
           and closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"]
           and invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0
           and "sshd.exe" in invocation["ssh_ancestor_names"]
           and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
           and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
           f"{arm} native guards")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
           and all(s["status"] == "completed" and s["exit_code"] == 0 for s in steps),
           f"{arm} five steps")
        ck(set(closure["raw"]) == RAW, f"{arm} twelve raw")
        for name, meta in closure["raw"].items():
            ck((run / name).stat().st_size == meta["bytes"]
               and sha(run / name) == meta["sha256"], f"{arm} raw {name}")
        ck(sha(run / "input.json") == contract["input_sha256"], f"{arm} input")
        rt = read(run / "roundtrip-validation.json")
        returned = populated(native_json(run / "roundtrip-raw.json"))
        authored = populated(source)
        ck(rt["passed"] and len(rt["populated_tables"]) == 30
           and all(returned.get(name) == value for name, value in authored.items()),
           f"{arm} exact thirty-table roundtrip")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog
           and re.findall(r"\(warning #(\d+)\)", runlog) == ["108", "2053", "2053"]
           and "rec 1: (warning #2053) FRT is zero for: TEACH-LRU-01" in runlog
           and "rec 2: (warning #2053) FRT is zero for: TEACH-SRU-01" in runlog
           and not re.search(r"\((?:error|notice) #", runlog), f"{arm} reviewed converter")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        log_sha[arm] = sha(run / "model.log")
        report_sha[arm] = sha(run / "report-raw.json")
        mission = {}
        for mtype, first in (("BASE2-MISSION", 8.0), ("RISK-MISSION", 21.5),
                             ("BASIC-MISSION", 24.75)):
            actual = [float(m.group(1)) for m in events(log, rf"<{mtype},[^>]+> mission starting")]
            success = [float(m.group(1)) for m in events(log, rf"<{mtype},[^>]+> mission success:")]
            expected = [first + 48*i for i in range(21)]
            ck(actual == expected and success == [t+2 for t in expected],
               f"{arm} {mtype} 21 starts and successes")
            mission[mtype] = len(actual)
        ck(not re.search(r"critical random failure added|Item demand arrives|Backorder added|mission cancelled|mission abort", log, re.I),
           f"{arm} no random loss or stock demand")
        starts = events(log, r" system PM task \d+ on <TEACH-AIR-01,\d+> started")
        ends = events(log, r" system PM task \d+ on <TEACH-AIR-01,\d+> completed")
        ck(len(starts) == 324 and len(ends) == 323
           and times_equal(events(log, r" system PM task 533 on <TEACH-AIR-01,6> started"), [1031.0])
           and not events(log, r" system PM task 533 on <TEACH-AIR-01,6> completed"),
           f"{arm} CAL24 PM and one unfinished boundary task")
        report = native_json(run / "report-raw.json")
        system, stock, resource = (rows(report, t) for t in
                                   ("SystemResults", "StockTotalResults", "ResourceResults"))
        summary = rows(report, "ResultSummary")
        ck(len(summary) == 1 and summary[0]["NREP"] == 1
           and summary[0]["RTIUP"] == 1032
           and all(summary[0][name] == 1 for name in ("MTMF", "MSTF", "MSUF", "STMF")),
           f"{arm} one-replication mission metrics")
        ck(all(len(t) == 2064 and all(abs(row["STINT"]-i*.5) < 1e-7
           and abs(row["ETINT"]-(i+1)*.5) < 1e-7 for i, row in enumerate(t))
           for t in (system, stock, resource)), f"{arm} aligned 2064 bins")
        ck(abs(sum(row["NSYMO"]*.5 for row in system) - 210) < .01
           and abs(sum(row["NSYPM"]*.5 for row in system) - 324) < .01,
           f"{arm} 105 sorties/210 operating aircraft-hours and PM occupancy")
        used, queued = resource_spans(log), resource_queues(log)
        for i in range(2064):
            lo, hi = i*.5, (i+1)*.5
            booked = sum(overlap(a, b, lo, hi) for a, b in used)
            waiting = sum(overlap(a, b, lo, hi) for a, b in queued)
            ck(abs(system[i]["NSYRY"] + system[i]["NSYMA"] + system[i]["NSYUA"] - 8) < 1e-4,
               f"{arm} system conservation bin {i}")
            ck(stock[i]["NBO"] == 0, f"{arm} zero stock backorder bin {i}")
            ck(resource[i]["NR"] == 4 and abs(resource[i]["NRUM"] - booked) < 5e-3
               and abs(resource[i]["NRW"] - waiting) < 5e-3,
               f"{arm} resource bin {i}")
        ck(abs(sum(row["NRUM"]*.5 for row in resource) - sum(b-a for a, b in used)) < .01
           and abs(sum(row["NRW"]*.5 for row in resource) - sum(b-a for a, b in queued)) < .01,
           f"{arm} integrated worker booked/queue hours")
        ck(system[-1]["NSYRY"] == 7 and system[-1]["NSYPM"] == 1
           and stock[-1]["NBO"] == 0
           and resource[-1]["NRUM"] == 1 and resource[-1]["NRW"] == 0,
           f"{arm} terminal ready7/PM1/worker1/no queue")
        summaries[arm] = {"missions": mission, "pm_started": len(starts),
                          "pm_completed": len(ends), "terminal_ready": system[-1]["NSYRY"]}
    ck(log_sha["a"] == log_sha["b"] and report_sha["a"] == report_sha["b"],
       "independent native event/report byte repeatability")
    result = {"schema": "simlox-f04-deterministic-43day-author-replay/v1",
              "case_id": "F04", "variant_id": "F04.var01", "version": "1.0.1",
              "passed": not failures, "checks": checks, "failures": failures,
              "summaries": summaries, "model_log_sha256": log_sha,
              "report_sha256": report_sha,
              "excluded_v1_0_0": {
                  "reason": "IQTY21/IPER48 compressed requests to 2.2857-hour spacing",
                  "closure_sha256": [
                      "243d95f08119e7be250ac0c57c0c5468acb4b6934a3d08af53aaa80e30650002",
                      "2faaa3116c5320334873d3056b17587856c4c09b4babf885568123f4c070087e"]},
              "runs": {arm: {"id": run.name, "closure_sha256": sha(run / "closure.json")}
                       for arm, run in RUNS.items()},
              "publication_state": "not_published"}
    target = HERE / "author-validation-2026-10-04.json"
    target.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{checks-len(failures)}/{checks} checks: {target}")
    if failures:
        print(failures[:30])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
