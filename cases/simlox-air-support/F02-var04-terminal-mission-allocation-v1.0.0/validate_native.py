"""Replay the fresh F02 report-cutoff mission-allocation native run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated
from build import build

HERE = Path(__file__).resolve().parent
RUN_ID = "f02-var04-allocation-v100-ssh-20261004-01"
RUN = HERE / "runs" / RUN_ID
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def times(log: str, pattern: str) -> list[float]:
    return [float(m.group(1)) for m in re.finditer(r"^Time: ([\d.]+) " + pattern, log, re.M)]


def prior_events(log: str, cutoff: float) -> list[str]:
    out = []
    retain = False
    for line in log.splitlines():
        m = re.match(r"Time: ([\d.]+) ", line)
        if m:
            retain = float(m.group(1)) < cutoff
        if retain:
            out.append(line)
    return out


def main() -> None:
    failures = []
    count = 0

    def ck(ok: bool, label: str) -> None:
        nonlocal count
        count += 1
        if not ok:
            failures.append(label)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    parent = HERE.parent / contract["accepted_parent"]["package"]
    diagnostic = HERE.parent / contract["excluded_diagnostic"]["package"]
    ck(contract["case_id"] == "F02" and contract["variant_id"] == "F02.var04" and
       contract["version"] == "1.0.0-candidate", "contract identity")
    ck(sha(HERE / "allocation-input.json") == contract["allocation_input_sha256"] ==
       diff["child_input_sha256"] == sha(diagnostic / "preassignment-input.json"), "frozen identical input")
    ck(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"] and
       diff["changed_cells"] == [{"table": "Control", "instance": 0, "row": 0,
                                   "column": "SIMPE", "before": 60.0, "after": 65.0}] and
       [x["table"] for x in diff["added_rows"]] ==
       ["MissionType", "OperationProfile", "MissionPreparation", "MissionTurnround"] and
       build() == load(HERE / "allocation-input.json"), "exact parent delta and reproducible builder")
    ck(sha(parent / "repair-input.json") == contract["accepted_parent"]["input_sha256"] and
       sha(parent / "runs" / contract["accepted_parent"]["run_id"] / "closure.json") ==
       contract["accepted_parent"]["closure_sha256"] and
       sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"],
       "accepted parent pins")
    ck(sha(diagnostic / "contract.json") == contract["excluded_diagnostic"]["contract_sha256"] and
       sha(diagnostic / "runs" / contract["excluded_diagnostic"]["run_id"] / "closure.json") ==
       contract["excluded_diagnostic"]["closure_sha256"], "excluded diagnostic pins")

    invocation, closure, steps = (load(RUN / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck(invocation["run_id"] == closure["run_id"] == RUN_ID and
       invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and
       "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "SSH0 and host queue")
    ck(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and
       closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json") and
       closure["source_hashes_before"] == closure["source_hashes_after"] ==
       invocation["source_hashes_before"], "GUI and stable closure")
    ck(set(closure["raw"]) == RAW, "12 raw artifact names")
    for name, meta in closure["raw"].items():
        ck((RUN / name).stat().st_size == meta["bytes"] and sha(RUN / name) == meta["sha256"],
           f"raw seal {name}")
    for name in ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1"):
        ck(closure["source_hashes_before"][name] == sha(HERE / name), f"source seal {name}")
    ck(closure["source_hashes_before"]["input"] == contract["allocation_input_sha256"] and
       closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json") and
       closure["source_hashes_before"]["exact_diff"] == sha(HERE / "exact-diff.json"),
       "source-bound input/contract/diff")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(s["status"] == "completed" and s["exit_code"] == 0 and s.get("gui_preserved", True)
           for s in steps), "five guarded native steps")
    roundtrip = load(RUN / "roundtrip-validation.json")
    authored, exported = populated(parse(RUN / "input.json")), populated(parse(RUN / "roundtrip-raw.json"))
    ck(roundtrip["passed"] and len(authored) == 30 and
       authored == {n: exported[n] for n in authored}, "exact 30-table roundtrip")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       runlog.count("(warning #108)") == 1 and
       not re.search(r"\((?:error|warning|notice) #(?!108\))", runlog), "native converter diagnostics")

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (parent / "runs" / contract["accepted_parent"]["run_id"] / "model.log").read_text(
        encoding="utf-8-sig", errors="replace")
    ck(prior_events(log, 59.5) == prior_events(parent_log, 59.5), "native event prefix matches parent")
    order = times(log, r"<TEACH-UNIT> mission ordered: TERMINAL-HOLD")
    alloc = times(log, r"<TERMINAL-HOLD,TEACH-UNIT,0,0,4> mission allocates system: <TEACH-AIR-01,1>")
    preassign = times(log, r"<TERMINAL-HOLD[^\n]*> mission preassigns a system:")
    prep = times(log, r"<TEACH-AIR-01,1> preparation started, mission: <TERMINAL-HOLD,TEACH-UNIT,0,0,4>")
    prep_end = times(log, r"<TEACH-AIR-01,1> preparation ended, mission: <TERMINAL-HOLD,TEACH-UNIT,0,0,4>")
    wait = times(log, r"<TERMINAL-HOLD,TEACH-UNIT,0,0,4> mission waiting:  timeout at 62")
    cancel = times(log, r"<TERMINAL-HOLD,TEACH-UNIT,0,0,4> mission cancelled:")
    ck(order == alloc == prep == wait == [59.5] and prep_end == [60.0] and
       cancel == [62.0] and not preassign, "direct allocation and final-bin preparation; no preassignment")
    ck(times(log, r"<TEACH-AIR-01,BASE-01,0> system PM task 18 on <TEACH-AIR-01,1> paused\.") == [59.5] and
       times(log, r" subtask 18 seqno 1 within system PM task 18 on <TEACH-AIR-01,1> resource waiting stopped") == [59.5],
       "healthy aircraft PM pauses and worker request stops")
    ck(times(log, r" <P-CREW at <BASE-01,0>> allocated to maintenance task:")[-1] == 59.5 and
       times(log, r" <P-CREW at <BASE-01,0>> deallocated from\s+maintenance task:")[-1] == 60.0 and
       [t for t in times(log, r" <P-MAINT at <BASE-01,0>> allocated to maintenance task:") if t <= 60][-1] == 47.9896 and
       all(t <= 47.9896 or t > 60 for t in times(log, r" <P-MAINT at <BASE-01,0>> deallocated from\s+maintenance task:")),
       "crew final-bin lease and maintainer open at cutoff")
    ck(times(log, r" remove subitem subtask 14 seqno 1 within system SURP task 14 on <TEACH-AIR-01,0> starts performing, planned to last for 15 hours") == [47.9896] and
       times(log, r" remove subitem subtask 14 seqno 1 within system SURP task 14 on <TEACH-AIR-01,0> completed") == [62.9896],
       "aircraft 0 removal active through report cutoff")
    ck(not times(log, r"<TERMINAL-HOLD[^\n]*> mission starting,") and cancel[0] > 60,
       "mission not launched or released before report cutoff")

    report = parse(RUN / "report-raw.json")
    parent_report = parse(parent / "runs" / contract["accepted_parent"]["run_id"] / "report-raw.json")
    summary = rows(report, "ResultSummary")
    ck(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 65,
       "full-simulation summary is 65 hours")
    for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        child, base = rows(report, name), rows(parent_report, name)
        ck(len(child) == len(base) == 120, f"{name} 120 bins")
        for i, (a, b) in enumerate(zip(child, base)):
            ck(abs(a["STINT"] - i / 2) < 1e-9 and abs(a["ETINT"] - (i + 1) / 2) < 1e-9,
               f"{name} interval {i}")
            if name == "SystemResults" and i == 95:
                ck({k: v for k, v in a.items() if k not in ("SYDT", "NSYDT")} ==
                   {k: v for k, v in b.items() if k not in ("SYDT", "NSYDT")} and
                   a["NSYDT"] == 1 and b["NSYDT"] == 0,
                   "system horizon-sensitive forecast marker bin 95")
            elif i == 119 and name == "SystemResults":
                ck({k: v for k, v in a.items() if k not in ("NSYRY", "NSYMA", "NSYMP", "NPSTA")} ==
                   {k: v for k, v in b.items() if k not in ("NSYRY", "NSYMA", "NSYMP", "NPSTA")} and
                   (a["NSYRY"], a["NSYMA"], a["NSYMP"], a["NPSTA"], a["NSYMR"], a["NSYRP"]) ==
                   (0, 1, 1, 1, 0, 1), "last-bin mission prep plus active repair")
            elif i == 119 and name == "ResourceResults":
                ck({k: v for k, v in a.items() if k not in ("NRUM", "NRW")} ==
                   {k: v for k, v in b.items() if k not in ("NRUM", "NRW")} and
                   (a["NRUM"], a["NRW"]) == (2, 0), "last-bin two workers; PM wait stopped")
            else:
                ck(a == b, f"{name} parent-matched bin {i}")
    result = {"schema": "simlox-f02-var04-report-cutoff-allocation-author-replay/v1",
              "run_id": RUN_ID, "passed": not failures, "checks": count, "failures": failures,
              "observed": {"allocation_hour": alloc, "preparation_interval": [prep[0], prep_end[0]],
                           "mission_cancel_hour": cancel, "report_cutoff_hour": 60,
                           "system_final_bin": {k: rows(report, "SystemResults")[-1][k]
                                                for k in ("NSYRY", "NSYMA", "NSYMP", "NSYMR", "NSYRP")},
                           "resource_final_bin": {k: rows(report, "ResourceResults")[-1][k]
                                                  for k in ("NRUM", "NRW")}},
              "scope": "mission_allocated_and_preparing_in_final_report_bin;no_preassignment_or_stock_reservation"}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
