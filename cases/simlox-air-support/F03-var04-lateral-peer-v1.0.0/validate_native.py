"""Author replay of the bounded F03 lateral peer experiment."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F03-var03-demand-location-v1.0.0"
DONOR = HERE.parent / "E08-var01-immediate-lateral-v1.0.2"
RUNS = {arm: HERE / "runs" / f"f03-lateral-{arm}-v100-ssh-20261004-01"
        for arm in ("on", "off")}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log",
       "export.log", "model.sxo", "run.log", "model.log", "report-raw.json",
       "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def times(log: str, pattern: str) -> list[float]:
    return [float(m.group(1)) for m in re.finditer(
        r"^Time: ([\d.]+) " + pattern, log, re.M)]


def table_rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for inst in table["instances"] for row in inst["rows"]]


def overlap(a: float, b: float, lo: float, hi: float) -> float:
    return max(0.0, min(b, hi) - max(a, lo)) / (hi - lo)


def resource_spans(log: str) -> list[tuple[float, float]]:
    spans = []
    for station in ("BASE-01", "BASE-02"):
        for rid in ("P-CREW", "P-MAINT"):
            starts = times(log, rf" <{rid} at <{station},0>> allocated to maintenance task: 1  available now: 0")
            ends = times(log, rf" <{rid} at <{station},0>> deallocated from  maintenance task: 1  available now: 1")
            assert len(starts) == len(ends)
            spans.extend(zip(starts, ends))
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
    ck(contract["case_id"] == "F03" and contract["variant_id"] == "F03.var04"
       and sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"],
       "contract and diff")
    ck(sha(PARENT / "risk_base1-input.json") == contract["accepted_parent"]["input_sha256"]
       and sha(PARENT / "runs/f03-demand-base1-v100-ssh-20261004-01/closure.json") == contract["accepted_parent"]["closure_sha256"]
       and sha(PARENT / "cli-scope-signoff-2026-10-04.md") == contract["accepted_parent"]["signoff_sha256"],
       "accepted F03 parent")
    ck(sha(DONOR / "on-input.json") == contract["accepted_lateral_donor"]["input_sha256"]
       and sha(DONOR / "cli-scope-signoff-2026-10-02.md") == contract["accepted_lateral_donor"]["signoff_sha256"],
       "accepted E08 donor")
    ck(diff["parent_changed_tables"] == ["ProblemDescription", "Control", "Station", "StockAllocation"]
       and diff["parent_appended_tables"] == ["LateralSupport"]
       and diff["pair_changed_tables"] == ["ProblemDescription", "Control"]
       and diff["sole_business_pair_change"]["column"] == "ENLAT", "bounded pair")
    logs = {}
    summaries = {}
    for arm, run in RUNS.items():
        name = f"lateral_{arm}"
        ck(sha(HERE / f"{name}-input.json") == contract["inputs_sha256"][name],
           f"{arm} input hash")
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
        for file, meta in closure["raw"].items():
            ck((run / file).stat().st_size == meta["bytes"]
               and sha(run / file) == meta["sha256"], f"{arm} raw {file}")
        authored = populated(parse(run / "input.json"))
        returned = populated(parse(run / "roundtrip-raw.json"))
        ck(len(authored) == 31 and all(returned.get(t) == v for t, v in authored.items())
           and read(run / "roundtrip-validation.json")["passed"], f"{arm} 31-table roundtrip")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog
           and runlog.count("(warning #108)") == 1
           and not re.search(r"\((?:warning|notice) #(?!108\))", runlog),
           f"{arm} diagnostics")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        logs[arm] = log
        ck(times(log, r"<BASE2-MISSION,TEACH-UNIT-2,[^>]+> mission starting") == [8.]
           and times(log, r"<BASE2-MISSION,TEACH-UNIT-2,[^>]+> mission success:") == [10.]
           and times(log, r"<RISK-MISSION,TEACH-UNIT,[^>]+> mission starting") == [21.5, 45.5],
           f"{arm} two active bases")
        starts = times(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder added")
        ends = times(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder removed")
        expected = ([23.74, 48.3394], [24.24, 48.8394]) if arm == "on" else (
            [23.74, 48.2231, 48.2231], [25.74, 50.2231, 50.2231])
        ck((starts, ends) == expected and not times(log, r"<TEACH-LRU-01,0,BASE-02,0> Backorder added"),
           f"{arm} bounded backorders")
        ck(times(log, r"<TEACH-AIR-01,1> critical random failure added")[:1] == [22.24]
           and times(log, r"<TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0>")[:1] == [23.74],
           f"{arm} matched first failure/demand")
        report = parse(run / "report-raw.json")
        system, stock, resource = (table_rows(report, t) for t in
                                   ("SystemResults", "StockTotalResults", "ResourceResults"))
        ck(all(len(t) == 120 and all(abs(row["STINT"] - i*.5) < 1e-7
           and abs(row["ETINT"] - (i+1)*.5) < 1e-7 for i, row in enumerate(t))
           for t in (system, stock, resource)), f"{arm} aligned half-hour bins")
        ck(all(abs(row["NSYRY"] + row["NSYMA"] + row["NSYUA"] - 3) < 1e-4
           for row in system), f"{arm} three-aircraft conservation")
        used, queued = resource_spans(log), resource_queues(log)
        for i in range(120):
            lo, hi = i*.5, (i+1)*.5
            nbo = sum(overlap(a, b, lo, hi) for a, b in zip(starts, ends))
            booked = sum(overlap(a, b, lo, hi) for a, b in used)
            waiting = sum(overlap(a, b, lo, hi) for a, b in queued)
            ck(abs(stock[i]["NBO"] - nbo) < 2e-4, f"{arm} stock bin {i}")
            ck(resource[i]["NR"] == 4 and abs(resource[i]["NRUM"] - booked) < 2e-3
               and abs(resource[i]["NRW"] - waiting) < 2e-3, f"{arm} resource bin {i}")
        ck(abs(sum(row["NBO"]*.5 for row in stock) - (1 if arm == "on" else 6)) < 1e-4,
           f"{arm} whole-run backorder item-hours (descriptive)")
        ck(system[-1]["NSYRY"] == 3 and stock[-1]["NBO"] == 0
           and resource[-1]["NRUM"] == resource[-1]["NRW"] == 0,
           f"{arm} terminal ready and no queue")
        summaries[arm] = {"backorders": list(zip(starts, ends)),
                          "backorder_item_hours": sum(row["NBO"]*.5 for row in stock)}
    on, off = logs["on"], logs["off"]
    ck("Time: 23.74 <TEACH-LRU-01,0,BASE-02,0> Take replacement item <TEACH-LRU-01,0,4> from stock" in on
       and "Time: 23.74  transport request <<TEACH-LRU-01,0,4>,<TEACH-LRU-01,0,BASE-02,0>,<TEACH-LRU-01,0,BASE-01,0>> attached" in on
       and "Time: 24.24 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,4>" in on
       and "Time: 23.74 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,2> from stock" in on
       and "Time: 25.74 <TEACH-LRU-01,0,BASE-02,0> Replacement item arrives <TEACH-LRU-01,0,2>" in on,
       "physical peer issue and depot replenishment")
    ck("Lateral support from:" not in off
       and "Time: 23.74  transport request <<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached" in off
       and "Time: 25.74 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,2>" in off,
       "disabled lateral uses depot")
    ck(times(on, r" system SURP task 6 on <TEACH-AIR-01,1> completed") == [24.5733]
       and times(off, r" system SURP task 6 on <TEACH-AIR-01,1> completed") == [26.0733]
       and times(on, r"<BASIC-MISSION,TEACH-UNIT,[^>]+> mission starting")[0] == 25.0733
       and times(off, r"<BASIC-MISSION,TEACH-UNIT,[^>]+> mission starting")[0] == 26.5733,
       "matched first repair and mission shift")
    ck(times(on, r"<TEACH-AIR-01,0> critical random failure added") !=
       times(off, r"<TEACH-AIR-01,0> critical random failure added"),
       "later random trajectory diverges")
    result = {"schema": "simlox-f03-lateral-peer-author-replay/v1",
              "case_id": "F03", "variant_id": "F03.var04",
              "passed": not failures, "checks": checks, "failures": failures,
              "paired_claim": "first matched BASE-01 demand only",
              "later_path": "divergent, whole-run totals descriptive only",
              "summaries": summaries,
              "runs": {arm: {"id": run.name, "closure_sha256": sha(run / "closure.json")}
                       for arm, run in RUNS.items()},
              "publication_state": "not_published"}
    target = HERE / "author-validation-2026-10-04.json"
    target.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{checks-len(failures)}/{checks} checks: {target}")
    if failures:
        print(failures[:25])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
