"""Author replay for the bounded two-base risk-demand location pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F03-var02-two-base-stock-v1.0.0"
RUNS = {"risk_base1": HERE / "runs/f03-demand-base1-v100-ssh-20261004-01",
        "risk_base2": HERE / "runs/f03-demand-base2-v100-ssh-20261004-01"}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo",
       "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table_rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def events(log: str, pattern: str) -> list[re.Match]:
    return list(re.finditer(r"^Time: ([\d.]+) " + pattern, log, re.M))


def overlap(a: float, b: float, lo: float, hi: float) -> float:
    return max(0.0, min(b, hi) - max(a, lo)) / (hi - lo)


def resource_usage(log: str) -> list[tuple[float, float]]:
    spans = []
    for station in ("BASE-01", "BASE-02"):
        for rid in ("P-CREW", "P-MAINT"):
            starts = events(log, rf" <{rid} at <{station},0>> allocated to maintenance task: 1  available now: 0")
            ends = events(log, rf" <{rid} at <{station},0>> deallocated from  maintenance task: 1  available now: 1")
            assert len(starts) == len(ends) and all(float(a.group(1)) <= float(b.group(1)) for a, b in zip(starts, ends))
            spans.extend((float(a.group(1)), float(b.group(1))) for a, b in zip(starts, ends))
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
    ck(contract["case_id"] == "F03" and contract["variant_id"] == "F03.var03" and
       sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen contract/diff")
    ck(sha(PARENT / "depot_only-input.json") == contract["accepted_parent"]["input_sha256"] and
       sha(PARENT / "runs/f03-stock-depot-v100-ssh-20261004-01/closure.json") == contract["accepted_parent"]["closure_sha256"] and
       sha(PARENT / "cli-scope-signoff-2026-10-04.md") == contract["accepted_parent"]["signoff_sha256"], "accepted F03 parent")
    ck(diff["parent_changed_tables"] == ["ProblemDescription"] and
       diff["pair_changed_tables"] == ["ProblemDescription", "Unit", "MissionPreparation", "MissionTurnround"] and
       len(diff["pair_changed_cells"]) == 9 and sum(c["column"] == "STID" for c in diff["pair_changed_cells"]) == 8,
       "exact paired station switch")
    reports = {}
    for arm, run in RUNS.items():
        station = "BASE-01" if arm == "risk_base1" else "BASE-02"
        other = "BASE-02" if arm == "risk_base1" else "BASE-01"
        risk_ids = (0, 1) if arm == "risk_base1" else (1, 2)
        small_id = 2 if arm == "risk_base1" else 0
        ck(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm], f"{arm} input hash")
        invocation, closure, steps = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        ck(closure["error"] is None and closure["run_id"] == run.name and closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"] and
           invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
           f"{arm} native guards")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(s["status"] == "completed" and s["exit_code"] == 0 for s in steps), f"{arm} five native steps")
        ck(set(closure["raw"]) == RAW, f"{arm} 12 raw")
        for name, meta in closure["raw"].items():
            path = run / name
            ck(path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"{arm} raw {name}")
        original, returned = populated(parse(run / "input.json")), populated(parse(run / "roundtrip-raw.json"))
        ck(len(original) == 30 and all(returned.get(name) == value for name, value in original.items()) and
           read(run / "roundtrip-validation.json")["passed"], f"{arm} exact roundtrip")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
           runlog.count("(warning #108)") == 1 and not re.search(r"\((?:warning|notice) #(?!108\))", runlog), f"{arm} diagnostics")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        report = parse(run / "report-raw.json")
        reports[arm] = report
        small = events(log, rf"<BASE2-MISSION,TEACH-UNIT-2,[^>]+> mission starting[^\n]+<TEACH-AIR-01,{small_id}>")
        ck([float(m.group(1)) for m in small] == [8] and
           [float(m.group(1)) for m in events(log, r"<BASE2-MISSION,TEACH-UNIT-2,[^>]+> mission success:")] == [10] and
           f"Time: 11 <TEACH-AIR-01,{other},0> System arrives <TEACH-AIR-01,{small_id}>, mission success" in log,
           f"{arm} small unit at opposite base")
        risk_start = events(log, rf"<RISK-MISSION,TEACH-UNIT,[^>]+> mission starting[^\n]+<TEACH-AIR-01,{risk_ids[0]}>,<TEACH-AIR-01,{risk_ids[1]}>")
        ck([float(m.group(1)) for m in risk_start] == [21.5, 45.5], f"{arm} risk aircraft identity")
        faults = [(float(m.group(1)), int(m.group(2))) for m in events(log, r"<TEACH-AIR-01,([012])> critical random failure added")]
        ck(faults == [(22.24, risk_ids[1]), (46.7231, risk_ids[0]), (46.8394, risk_ids[1])], f"{arm} matched risk faults")
        demand = events(log, rf"<TEACH-LRU-01,0,{station},0> Item demand arrives from pos <TEACH-AIR-01,{station},0>")
        ck([float(m.group(1)) for m in demand] == [23.74, 48.2231, 48.2231] and
           not events(log, rf"<TEACH-LRU-01,0,{other},0> Item demand arrives from pos <TEACH-AIR-01,{other},0>"),
           f"{arm} demand follows risk unit station")
        starts = [float(m.group(1)) for m in events(log, rf"<TEACH-LRU-01,0,{station},0> Backorder added")]
        ends = [float(m.group(1)) for m in events(log, rf"<TEACH-LRU-01,0,{station},0> Backorder removed, waiting time was 2")]
        ck(starts == [23.74, 48.2231, 48.2231] and ends == [25.74, 50.2231, 50.2231] and
           not events(log, rf"<TEACH-LRU-01,0,{other},0> Backorder added"), f"{arm} station backorders")
        outgoing = [float(m.group(1)) for m in events(log, rf" transport task \d+ created from <DEPOT-01,0> to <{station},0>, scheduled to start at (?:23\.74|48\.2231)")]
        incoming = [float(m.group(1)) for m in events(log, rf" transport task \d+ created from <{station},0> to <DEPOT-01,0>, scheduled to start at (?:23\.9066|48\.3898|48\.5565)")]
        ck(outgoing == [23.74, 48.2231, 48.2231] and incoming == [23.9066, 48.3898, 48.5565], f"{arm} transport endpoints")
        system, stock, resource = (table_rows(report, n) for n in ("SystemResults", "StockTotalResults", "ResourceResults"))
        ck(all(len(rows) == 120 and all(abs(r["STINT"]-i*.5) < 1e-7 and abs(r["ETINT"]-(i+1)*.5) < 1e-7
           for i, r in enumerate(rows)) for rows in (system, stock, resource)), f"{arm} 120 aligned bins")
        ck(all(abs(r["NSYRY"] + r["NSYMA"] + r["NSYUA"] - 3) < 1e-4 for r in system), f"{arm} three-aircraft conservation")
        backorders, used, queued = list(zip(starts, ends)), resource_usage(log), resource_queues(log)
        for i in range(120):
            lo, hi = i*.5, (i+1)*.5
            nbo = sum(overlap(a, b, lo, hi) for a, b in backorders)
            booked = sum(overlap(a, b, lo, hi) for a, b in used)
            waiting = sum(overlap(a, b, lo, hi) for a, b in queued)
            ck(abs(stock[i]["NBO"]-nbo) < 2e-4, f"{arm} stock bin {i}")
            ck(resource[i]["NR"] == 4 and abs(resource[i]["NRUM"]-booked) < 2e-3 and
               abs(resource[i]["NRW"]-waiting) < 2e-3, f"{arm} resource bin {i}")
        ck(abs(sum(r["NBO"]*.5 for r in stock)-6) < 1e-4, f"{arm} six backorder item-hours")
        ck(system[-1]["NSYRY"] == 3 and stock[-1]["NBO"] == 0 and resource[-1]["NRUM"] == resource[-1]["NRW"] == 0,
           f"{arm} terminal ready3/no queue/backorder")
    a, b = reports.values()
    at = {t["name"]: t for t in a["report"]["tables"]}
    bt = {t["name"]: t for t in b["report"]["tables"]}
    ck(at.keys() == bt.keys() and all(at[n] == bt[n] for n in at if n != "ProblemDescription"), "all aggregate results equal under symmetric station swap")
    result = {"schema": "simlox-f03-demand-location-author-replay/v1", "case_id": "F03", "variant_id": "F03.var03",
              "passed": not failures, "checks": checks, "failures": failures,
              "runs": {arm: {"id": run.name, "closure_sha256": sha(run / "closure.json")} for arm, run in RUNS.items()},
              "publication_state": "not_published"}
    target = HERE / "author-validation-2026-10-04.json"
    target.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{checks-len(failures)}/{checks} checks: {target}")
    if failures:
        print(failures[:25])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
