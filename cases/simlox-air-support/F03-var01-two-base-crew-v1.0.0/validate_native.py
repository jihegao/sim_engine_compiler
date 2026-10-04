"""Author replay of the bounded F03 two-base crew-capacity pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F02-var01-var02-integrated-fleet-v1.0.2"
RUNS = {arm: HERE / "runs" / f"f03-v101-{arm}-ssh-20261004-01" for arm in ("staffed", "unstaffed")}
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


def resource_usage(log: str) -> dict[tuple[str, str], list[tuple[float, float]]]:
    spans = {}
    for station in ("BASE-01", "BASE-02"):
        for rid in ("P-CREW", "P-MAINT"):
            starts = events(log, rf" <{rid} at <{station},0>> allocated to maintenance task: 1  available now: 0")
            ends = events(log, rf" <{rid} at <{station},0>> deallocated from  maintenance task: 1  available now: 1")
            assert len(starts) == len(ends) and all(float(a.group(1)) < float(b.group(1)) for a, b in zip(starts, ends))
            spans[(station, rid)] = [(float(a.group(1)), float(b.group(1))) for a, b in zip(starts, ends)]
    return spans


def resource_queues(log: str, arm: str) -> dict[tuple[str, str], list[tuple[float, float]]]:
    spans: dict[tuple[str, str], list[tuple[float, float]]] = {}
    pending: dict[tuple[str, str], float] = {}
    now = None
    for line in log.splitlines():
        tick = re.match(r"^Time: ([\d.]+)", line)
        if tick:
            now = float(tick.group(1))
        test = re.search(r"<(?P<rid>P-CREW|P-MAINT) at <(?P<station>BASE-0[12]),0>> request for: 1 (?P<state>failed|OK)", line)
        if not test:
            continue
        assert now is not None
        key = (test.group("station"), test.group("rid"))
        if test.group("state") == "failed":
            assert key not in pending
            pending[key] = now
        elif key in pending:
            spans.setdefault(key, []).append((pending.pop(key), now))
    if arm == "unstaffed":
        key = ("BASE-02", "P-CREW")
        assert pending.pop(key) == 7.0
        assert "Time: 8.5  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,2> resource waiting stopped" in log
        spans.setdefault(key, []).append((7.0, 8.5))
    assert not pending
    return spans


def main() -> None:
    failures: list[str] = []
    checks = 0

    def ck(condition: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck(contract["case_id"] == "F03" and contract["variant_id"] == "F03.var01" and sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen contract/diff")
    ck(sha(PARENT / "deterministic-input.json") == contract["accepted_parent"]["input_sha256"] and
       sha(PARENT / "runs/f02-pair-v102-det-ssh-20261004-01/closure.json") == contract["accepted_parent"]["closure_sha256"], "accepted parent")
    ck(diff["sole_business_pair_change"] == {"table": "ResourceAllocation", "row": 4, "station": "BASE-02", "resource": "P-CREW", "field": "RQTY", "staffed": 1, "unstaffed": 0}, "one business pair change")
    for arm, run in RUNS.items():
        ck(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm], f"{arm} frozen input")
        invocation, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(closure["error"] is None and closure["run_id"] == run.name and closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"] and
           invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{arm} native guards and seal")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(s["status"] == "completed" and s["exit_code"] == 0 for s in steps), f"{arm} five native steps")
        ck(set(closure["raw"]) == RAW, f"{arm} 12 raw files")
        for name, meta in closure["raw"].items():
            path = run / name
            ck(path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"{arm} raw {name}")
        original, returned = populated(parse(run / "input.json")), populated(parse(run / "roundtrip-raw.json"))
        ck(len(original) == 30 and all(returned.get(name) == value for name, value in original.items()) and read(run / "roundtrip-validation.json")["passed"], f"{arm} exact 30-table roundtrip")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and runlog.count("(warning #108)") == 1 and
           not re.search(r"\((?:warning|notice) #(?!108\))", runlog), f"{arm} converter diagnostics")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        report = parse(run / "report-raw.json")
        mission = {name: [(float(m.group(1)), m.group(2)) for m in events(log, rf"<([^>]+)> mission {name}:")]
                   for name in ("ordered", "success", "cancelled")}
        base1_orders = [(round(t, 4), n) for t, n in mission["ordered"] if n == "TEACH-UNIT"]
        ck(base1_orders == [(20.5, "TEACH-UNIT"), (23.75, "TEACH-UNIT"), (44.5, "TEACH-UNIT"), (47.75, "TEACH-UNIT")], f"{arm} four base1 orders")
        base1_starts = [float(m.group(1)) for m in events(log, r"<(?:RISK-MISSION|BASIC-MISSION),TEACH-UNIT,[^>]+> mission starting[^\n]+<TEACH-AIR-01,0>,<TEACH-AIR-01,1>")]
        base1_success = [float(m.group(1)) for m in events(log, r"<(?:RISK-MISSION|BASIC-MISSION),TEACH-UNIT,[^>]+> mission success:")]
        ck(base1_starts == [21.5, 25.5, 45.5, 49.5] and base1_success == [23.5, 27.5, 47.5, 51.5], f"{arm} unchanged base1 missions/identities")
        ck(len(events(log, r"<TEACH-AIR-01,[012]> critical random failure added")) == 0 and
           not events(log, r"<TEACH-LRU-01,0,BASE-0[12],0> Backorder added"), f"{arm} no failure or stock backorder")
        pm = [(float(m.group(1)), int(m.group(2))) for m in events(log, r" system PM task \d+ on <TEACH-AIR-01,([012])> completed")]
        ck(pm == [(25.0, 2), (29.5, 0), (30.5, 1), (50.0, 2), (54.5, 0), (55.5, 1)], f"{arm} six per-aircraft PM completions")
        base2_order = events(log, r"<TEACH-UNIT-2> mission ordered: BASE2-MISSION")
        base2_start = events(log, r"<BASE2-MISSION,TEACH-UNIT-2,[^>]+> mission starting[^\n]+<TEACH-AIR-01,2>")
        base2_success = events(log, r"<BASE2-MISSION,TEACH-UNIT-2,[^>]+> mission success:")
        base2_cancel = events(log, r"<BASE2-MISSION,TEACH-UNIT-2,[^>]+> mission cancelled:")
        ck(len(base2_order) == 1 and float(base2_order[0].group(1)) == 7 and
           [float(m.group(1)) for m in base2_start] == ([8.0] if arm == "staffed" else []) and
           [float(m.group(1)) for m in base2_success] == ([10.0] if arm == "staffed" else []) and
           [float(m.group(1)) for m in base2_cancel] == ([] if arm == "staffed" else [8.5]), f"{arm} base2 crew-gated mission")
        ck(("<P-CREW at <BASE-02,0>> request for: 1 OK" in log) == (arm == "staffed") and
           ("<P-CREW at <BASE-02,0>> request for: 1 failed" in log) == (arm == "unstaffed"), f"{arm} local crew availability")
        system, stock, resource = (table_rows(report, name) for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
        ck(all(len(rows) == 120 and all(abs(row["STINT"] - i*.5) < 1e-7 and abs(row["ETINT"] - (i+1)*.5) < 1e-7 for i, row in enumerate(rows)) for rows in (system, stock, resource)), f"{arm} aligned 120 bins")
        ck(all(abs(row["NSYRY"] + row["NSYMA"] + row["NSYUA"] - 3) < 1e-4 for row in system), f"{arm} three-aircraft conservation")
        ck(all(row["NBO"] == 0 and row["NDF"] == 0 for row in stock), f"{arm} stock ledger zero")
        ck(all(row["NR"] == (4 if arm == "staffed" else 3) for row in resource), f"{arm} resource count")
        ck(abs(sum(row["NSYMO"]*.5 for row in system) - (18 if arm == "staffed" else 16)) < 1e-4 and
           abs(sum(row["NSYPM"]*.5 for row in system) - 6) < 1e-4, f"{arm} mission and PM aircraft-hours")
        used, queued = resource_usage(log), resource_queues(log, arm)
        ck(abs(sum(b-a for v in used.values() for a, b in v) - (10.5 if arm == "staffed" else 10)) < 1e-4 and
           abs(sum(b-a for v in queued.values() for a, b in v) - (3 if arm == "staffed" else 4.5)) < 1e-4, f"{arm} per-base resource ledgers")
        for i, row in enumerate(resource):
            lo, hi = i*.5, (i+1)*.5
            expect_used = sum(overlap(a, b, lo, hi) for v in used.values() for a, b in v)
            expect_wait = sum(overlap(a, b, lo, hi) for v in queued.values() for a, b in v)
            ck(abs(row["NRUM"] - expect_used) < 1e-3 and abs(row["NRW"] - expect_wait) < 1e-3, f"{arm} resource bin {i}")
        summary = table_rows(report, "ResultSummary")[0]
        ck(abs(summary["MTMF"] - (1 if arm == "staffed" else .8)) < 1e-6 and
           abs(summary["STMF"] - (1 if arm == "staffed" else 8/9)) < 1e-6, f"{arm} mission/aircraft denominators")
        ck(system[-1]["NSYRY"] == 3 and all(system[-1][f] == 0 for f in ("NSYMA", "NSYUA", "NSYMP", "NSYRP")) and
           resource[-1]["NRW"] == resource[-1]["NRUM"] == 0 and stock[-1]["NBO"] == 0, f"{arm} terminal all ready/no queue")

    result = {"schema": "simlox-f03-two-base-author-replay/v1", "case_id": "F03", "variant_id": "F03.var01",
              "passed": not failures, "checks": checks, "failures": failures,
              "runs": {a: {"id": p.name, "closure_sha256": sha(p / "closure.json")} for a, p in RUNS.items()},
              "publication_state": "not_published"}
    target = HERE / "author-validation-2026-10-04.json"
    target.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{checks-len(failures)}/{checks} checks: {target}")
    if failures:
        print(failures[:25])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
