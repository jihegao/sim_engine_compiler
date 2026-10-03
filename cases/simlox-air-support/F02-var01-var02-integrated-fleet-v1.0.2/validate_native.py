"""Author replay of frozen F02 paired native evidence and cross-mechanism ledgers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated
from build import SOURCES

HERE = Path(__file__).resolve().parent
RUNS = {
    "deterministic": "f02-pair-v102-det-ssh-20261004-01",
    "risk": "f02-pair-v102-risk-ssh-20261004-01",
}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo",
       "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table_rows(report: dict, name: str) -> list[dict]:
    tab = next(t for t in report["report"]["tables"] if t["name"] == name)
    names = [col["name"] for col in tab["columns"]]
    return [dict(zip(names, row)) for inst in tab["instances"] for row in inst["rows"]]


def events(log: str, pattern: str) -> list[re.Match]:
    return list(re.finditer(r"^Time: ([\d.]+) " + pattern, log, re.M))


def main() -> None:
    failures: list[str] = []
    checks = 0
    observed: dict = {}

    def ck(condition: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    ck(contract["case_id"] == "F02" and contract["version"] == "1.0.2-candidate", "contract identity")
    ck(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen exact diff")
    ck(diff["paired_differences"] == [{"table": "MissionType", "row": 1, "column": "MFF", "deterministic": 0.0, "risk": 1.0}], "single paired switch")
    for name, digest in contract["accepted_inputs"].items():
        relative, expected = SOURCES[name]
        ck(sha(HERE.parent / relative) == digest == expected, f"accepted {name} input")
    deterministic, risk = (load(HERE / f"{arm}-input.json") for arm in RUNS)
    for arm, document in (("deterministic", deterministic), ("risk", risk)):
        key = "F02.var01_deterministic" if arm == "deterministic" else "F02.var02_risk"
        ck(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][key] == diff["arms"][arm]["input_sha256"], f"{arm} input freeze")
        authored = populated(document)
        ck(len(authored) == 30, f"{arm} 30 populated tables")

    for arm, run_id in RUNS.items():
        run = HERE / "runs" / run_id
        invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(invocation["run_id"] == closure["run_id"] == run_id and invocation["arm"] == arm and invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} SSH0 identity")
        ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{arm} GUI/queue guard")
        ck(closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], f"{arm} source stability")
        ck(set(closure["raw"]) == RAW, f"{arm} 12 sealed raw files")
        for name, meta in closure["raw"].items():
            path = run / name
            ck(path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"{arm} raw {name}")
        for name in ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1"):
            ck(closure["source_hashes_before"][name] == sha(HERE / name), f"{arm} sealed {name}")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s.get("gui_preserved", True) for s in steps), f"{arm} five completed steps")
        before, after = populated(parse(run / "input.json")), populated(parse(run / "roundtrip-raw.json"))
        ck(load(run / "roundtrip-validation.json")["passed"] and all(after.get(name) == tab for name, tab in before.items()), f"{arm} exact authored populated roundtrip")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and runlog.count("(warning #108)") == 1 and not re.search(r"\((?:warning|notice) #(?!108\))", runlog), f"{arm} exact converter diagnostics")

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        report = parse(run / "report-raw.json")
        ordered = events(log, r"<TEACH-UNIT> mission ordered: (RISK-MISSION|BASIC-MISSION)")
        started = events(log, r"<(RISK-MISSION|BASIC-MISSION),[^\n]+> mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        success = events(log, r"<(RISK-MISSION|BASIC-MISSION),[^\n]+> mission success:")
        aborted = events(log, r"<RISK-MISSION,[^\n]+> mission aborted:")
        cancelled = events(log, r"<BASIC-MISSION,[^\n]+> mission cancelled:")
        ck([m.group(2) for m in ordered] == ["RISK-MISSION", "BASIC-MISSION", "RISK-MISSION", "BASIC-MISSION"], f"{arm} four two-day waves")
        ck([round(float(m.group(1)), 4) for m in ordered] == [20.5, 23.75, 44.5, 47.75], f"{arm} preparation-adjusted orders")
        ck(len(started) == (4 if arm == "deterministic" else 3), f"{arm} formation starts")
        ck(len(success) == (4 if arm == "deterministic" else 2) and len(aborted) == (0 if arm == "deterministic" else 1) and len(cancelled) == (0 if arm == "deterministic" else 1), f"{arm} outcome ledger")
        turns = events(log, r"<TEACH-AIR-01,([01])> turnround started, mission:")
        turn_ends = events(log, r"<TEACH-AIR-01,([01])> turnround ended, mission:")
        ck(len(turns) == len(turn_ends) and len(turns) >= 6 and all(abs(float(b.group(1)) - float(a.group(1)) - 1) < 1e-4 for a, b in zip(turns, turn_ends)), f"{arm} one-hour turnround ledger")
        ck(any(float(a.group(1)) < 24 < float(b.group(1)) for a, b in zip(turns, turn_ends)), f"{arm} midnight turnround")
        pm = events(log, r" system PM task \d+ on <TEACH-AIR-01,[01]> PMID: CAL24")
        pm_done = events(log, r" system PM task \d+ on <TEACH-AIR-01,[01]> completed")
        ck(len(pm) == len(pm_done) == 4 and max(float(m.group(1)) for m in pm_done) < 60, f"{arm} four completed PMs")
        ck("<P-CREW at <BASE-01,0>> request for: 1 failed" in log and "<P-CREW at <BASE-01,0>> request for: 1 OK" in log, f"{arm} crew queue")
        ck("<P-MAINT at <BASE-01,0>> request for: 1 failed" in log and "<P-MAINT at <BASE-01,0>> request for: 1 OK" in log, f"{arm} maintenance queue")
        resource_spans = []
        for rid in ("P-CREW", "P-MAINT"):
            starts = events(log, rf" <{rid} at <BASE-01,0>> allocated to maintenance task: 1  available now: 0")
            ends = events(log, rf" <{rid} at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1")
            ck(len(starts) == len(ends) and all(float(a.group(1)) < float(b.group(1)) for a, b in zip(starts, ends)), f"{arm} {rid} balanced grants")
            resource_spans.extend((float(a.group(1)), float(b.group(1))) for a, b in zip(starts, ends))
        faults = events(log, r"<TEACH-AIR-01,[01]> critical random failure added")
        ck(len(faults) == (0 if arm == "deterministic" else 1), f"{arm} stochastic fault switch")
        for name, total in (("SystemResults", 2), ("StockTotalResults", None), ("ResourceResults", 2)):
            rr = table_rows(report, name)
            ck(len(rr) == 120 and all(abs(float(row["STINT"]) - i * 0.5) < 1e-7 and abs(float(row["ETINT"]) - (i+1) * 0.5) < 1e-7 for i, row in enumerate(rr)), f"{arm} {name} 120-bin grid")
            if name == "SystemResults":
                ck(all(abs(row["NSYRY"] + row["NSYMA"] + row["NSYUA"] - total) < 1e-4 for row in rr), f"{arm} {name} conserved aircraft")
            elif name == "ResourceResults":
                ck(all(row["NR"] == total for row in rr), f"{arm} {name} conserved count")
        system_last = table_rows(report, "SystemResults")[-1]
        stock_last = table_rows(report, "StockTotalResults")[-1]
        resource_last = table_rows(report, "ResourceResults")[-1]
        for i, row in enumerate(table_rows(report, "ResourceResults")):
            start, end = i * 0.5, (i + 1) * 0.5
            used = sum(max(0.0, min(b, end) - max(a, start)) for a, b in resource_spans) / 0.5
            ck(abs(used - row["NRUM"]) < 1e-3, f"{arm} resource utilization bin {i}")
        ck(system_last["NSYRY"] == 2 and all(system_last[f] == 0 for f in ("NSYMP", "NSYMT", "NSYMR", "NSYRP", "NSYPM")) and stock_last["NBO"] == 0 and resource_last["NRA"] == 2 and resource_last["NRW"] == 0, f"{arm} terminal closure")
        observed[arm] = {"run_id": run_id, "closure_sha256": sha(run / "closure.json"), "faults": len(faults), "missions_ordered": len(ordered), "missions_started": len(started), "mission_successes": len(success), "mission_aborts": len(aborted), "mission_cancellations": len(cancelled), "pm_completed": len(pm_done), "report_bins": 120, "terminal_ready": system_last["NSYRY"]}

        if arm == "risk":
            back = events(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder added")
            demand = events(log, r"<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>")
            spare = events(log, r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
            arrival = events(log, r"<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,(\d+)>")
            failed_at_depot = events(log, r"<TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)> from position <TEACH-LRU-01,0,BASE-01,0> subitem failed: <TEACH-SRU-01,0,(\d+)>")
            sru_spare = events(log, r"<TEACH-SRU-01,0,DEPOT-01,0> Take replacement item <TEACH-SRU-01,0,(\d+)> from stock")
            lru_return = events(log, r"<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
            sru_return = events(log, r"<TEACH-SRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-SRU-01,0,(\d+)> to stock")
            ck(all(len(seq) == 1 for seq in (back, demand, spare, arrival, failed_at_depot, sru_spare, lru_return, sru_return)), "risk single physical nested supply/repair cycle")
            if all(len(seq) == 1 for seq in (back, demand, spare, arrival, failed_at_depot, sru_spare, lru_return, sru_return)):
                ck(demand[0].group(2) == failed_at_depot[0].group(2) == lru_return[0].group(2), "failed LRU identity through upstream repair")
                ck(spare[0].group(2) == arrival[0].group(2) and spare[0].group(2) != lru_return[0].group(2), "distinct depot spare issued at base")
                ck(failed_at_depot[0].group(3) == sru_return[0].group(2) and sru_spare[0].group(2) != sru_return[0].group(2), "failed SRU identity repaired and spare distinct")
                ck(abs(float(arrival[0].group(1)) - float(spare[0].group(1)) - 2) < 1e-4 and abs(float(failed_at_depot[0].group(1)) - 48.1563 - 2) < 1e-4, "two-hour outward and return transport")
                ck(float(back[0].group(1)) <= float(spare[0].group(1)) < float(arrival[0].group(1)) < float(lru_return[0].group(1)) < float(sru_return[0].group(1)), "physical event order")
                observed[arm]["physical"] = {"failed_lru": failed_at_depot[0].group(2), "issued_lru": spare[0].group(2), "failed_sru": failed_at_depot[0].group(3), "issued_sru": sru_spare[0].group(2), "base_backorder_hours": round(float(arrival[0].group(1)) - float(back[0].group(1)), 6)}
                for i, row in enumerate(table_rows(report, "StockTotalResults")):
                    start, end = i * 0.5, (i + 1) * 0.5
                    expected = max(0.0, min(float(arrival[0].group(1)), end) - max(float(back[0].group(1)), start)) / 0.5
                    ck(abs(expected - row["NBO"]) < 1e-3, f"risk backorder bin {i}")
            for item in ("LRU", "SRU"):
                states = re.findall(rf"^  Stock at: <TEACH-{item}-01,0,DEPOT-01,0> Level: (\d+) Items:([^\n]*)", log, re.M)
                ck(bool(states) and int(states[0][0]) == int(states[-1][0]) == 2 and len(re.findall(rf"<TEACH-{item}-01,0,\d+>", states[-1][1])) == 2, f"risk depot {item} stock restored")

    result = {"schema": "simlox-f02-paired-author-native-replay/v1", "passed": not failures, "checks": checks, "failures": failures, "observed": observed, "publication_state": "not_published"}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
