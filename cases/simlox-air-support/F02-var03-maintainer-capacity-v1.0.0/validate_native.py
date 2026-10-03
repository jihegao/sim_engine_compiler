"""Read-only author replay for F02.var03 P-MAINT one-versus-two capacity."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F02-var01-var02-integrated-fleet-v1.0.2"
PARENT_RUN = PARENT / "runs/f02-pair-v102-risk-ssh-20261004-01"
RUN = HERE / "runs/f02-var03-pmaint2-v100-ssh-20261004-01"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo",
       "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(report: dict, name: str) -> list[dict]:
    tab = next(t for t in report["report"]["tables"] if t["name"] == name)
    fields = [c["name"] for c in tab["columns"]]
    return [dict(zip(fields, row)) for inst in tab["instances"] for row in inst["rows"]]


def events(log: str, pattern: str) -> list[re.Match]:
    return list(re.finditer(r"^Time: ([\d.]+) " + pattern, log, re.M))


def main() -> None:
    failures: list[str] = []
    count = 0

    def ck(ok: bool, label: str) -> None:
        nonlocal count
        count += 1
        if not ok:
            failures.append(label)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    parent = contract["accepted_parent"]
    ck(contract["case_id"] == "F02" and contract["variant_id"] == "F02.var03" and contract["version"] == "1.0.0-candidate", "contract identity")
    ck(sha(PARENT / "risk-input.json") == parent["input_sha256"] == diff["parent_input_sha256"], "accepted parent input")
    ck(sha(PARENT_RUN / "closure.json") == parent["closure_sha256"], "accepted parent closure")
    ck(sha(PARENT / "evidence-index.json") == parent["evidence_index_sha256"], "accepted parent evidence")
    ck(sha(HERE / "no-conflict-input.json") == contract["no_conflict_input_sha256"] == diff["no_conflict_input_sha256"], "new input freeze")
    ck(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff freeze")
    ck(diff["changed_cells"] == [{"table": "ResourceAllocation", "row": 0, "column": "RQTY", "before": 1, "after": 2}], "one allocation cell")
    invocation, closure, steps = (load(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck(invocation["run_id"] == closure["run_id"] == RUN.name and invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0 provenance")
    ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI and queue guard")
    ck(closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "stable closure")
    ck(set(closure["raw"]) == RAW, "12 sealed raw files")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw {name}")
    for key, path in (("input", HERE / "no-conflict-input.json"), ("parent", PARENT / "risk-input.json"),
                      ("parent_closure", PARENT_RUN / "closure.json"), ("parent_evidence_index", PARENT / "evidence-index.json"),
                      ("contract", HERE / "contract.json"), ("exact_diff", HERE / "exact-diff.json")):
        ck(closure["source_hashes_before"][key] == sha(path), f"sealed {key}")
    for name in ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1"):
        ck(closure["source_hashes_before"][name] == sha(HERE / name), f"sealed {name}")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s.get("gui_preserved", True) for s in steps), "five completed guarded steps")
    before, after = populated(parse(RUN / "input.json")), populated(parse(RUN / "roundtrip-raw.json"))
    ck(load(RUN / "roundtrip-validation.json")["passed"] and len(before) == 30 and all(after.get(name) == tab for name, tab in before.items()), "30-table exact authored roundtrip")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and runlog.count("(warning #108)") == 1 and not re.search(r"\((?:warning|notice) #(?!108\))", runlog), "exact converter diagnostic set")

    old_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    old_pm = events(old_log, r" system PM task \d+ on <TEACH-AIR-01,[01]> completed")
    new_pm = events(log, r" system PM task \d+ on <TEACH-AIR-01,[01]> completed")
    ck([float(m.group(1)) for m in old_pm] == [29.5, 30.5, 54.5, 55.5], "one-worker PM completion ledger")
    ck([float(m.group(1)) for m in new_pm] == [29.5, 29.5, 54.5, 54.5], "two-worker overlapping PM completion ledger")
    ck(len(events(old_log, r" subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,1> resource received")) >= 1, "parent first-day PM waited")
    ck(not events(log, r" subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,[01]> resource received"), "new PM has no worker wait")
    ck(log.count("<P-CREW at <BASE-01,0>> request for: 1 failed") > 0, "crew contention remains")
    ck(len(events(log, r"<TEACH-AIR-01,[01]> critical random failure added")) == 1, "same bounded risk fault")
    for marker, total in (("mission ordered:", 4), ("mission success:", 2), ("mission aborted:", 1), ("mission cancelled:", 1)):
        ck(log.count(marker) == old_log.count(marker) == total, f"matched {marker} count")
    for marker in ("<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,2>",
                   "<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,2>",
                   "<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,4>",
                   "<TEACH-SRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-SRU-01,0,5>"):
        ck(marker in old_log and marker in log, f"matched physical {marker}")

    old_report, report = parse(PARENT_RUN / "report-raw.json"), parse(RUN / "report-raw.json")
    ck(rows(old_report, "ResultSummary") == rows(report, "ResultSummary"), "same mission summary")
    ck(rows(old_report, "StockTotalResults") == rows(report, "StockTotalResults"), "same 120-bin stock ledger")
    system_before, system_after = rows(old_report, "SystemResults"), rows(report, "SystemResults")
    resource_before, resource_after = rows(old_report, "ResourceResults"), rows(report, "ResourceResults")
    ck(len(system_before) == len(system_after) == len(resource_before) == len(resource_after) == 120, "120-bin aligned reports")
    allowed_system = {"NSYRY", "NSYUA", "NSYA", "NSYPM", "NSYDT", "NPMT", "SYDT", "NPMS"}
    allowed_resource = {"NR", "NRA", "NRN", "NRUM", "NRW"}
    changed_system, changed_resource = set(), set()
    for i, (old, new) in enumerate(zip(system_before, system_after)):
        ck(abs(new["STINT"] - i * 0.5) < 1e-6 and abs(new["ETINT"] - (i+1) * 0.5) < 1e-6, f"system bin {i} grid")
        ck(abs(new["NSYRY"] + new["NSYMA"] + new["NSYUA"] - 2) < 1e-4, f"system bin {i} conservation")
        for field in new:
            if old[field] != new[field]:
                changed_system.add(field)
                ck(field in allowed_system, f"system bin {i} allowed {field}")
    for i, (old, new) in enumerate(zip(resource_before, resource_after)):
        ck(new["NR"] == 3 and old["NR"] == 2 and new["NRA"] == 3, f"resource bin {i} capacity")
        for field in new:
            if old[field] != new[field]:
                changed_resource.add(field)
                ck(field in allowed_resource, f"resource bin {i} allowed {field}")
    ck("NSYPM" in changed_system and "NRUM" in changed_resource and "NRW" in changed_resource, "PM/worker report delta present")
    terminal = system_after[-1], rows(report, "StockTotalResults")[-1], resource_after[-1]
    ck(terminal[0]["NSYRY"] == 2 and terminal[0]["NSYPM"] == 0 and terminal[1]["NBO"] == 0 and terminal[2]["NRW"] == 0, "terminal ready/no wait/backorder")
    result = {"schema": "simlox-f02-var03-author-native-replay/v1", "passed": not failures,
              "checks": count, "failures": failures, "parent_closure_sha256": sha(PARENT_RUN / "closure.json"),
              "new_closure_sha256": sha(RUN / "closure.json"), "changed_system_fields": sorted(changed_system),
              "changed_resource_fields": sorted(changed_resource), "publication_state": "not_published"}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
