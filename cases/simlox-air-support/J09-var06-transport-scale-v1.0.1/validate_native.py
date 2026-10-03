"""Read-only source-bound replay of J09.var06 SCTRT=2 native behavior."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated, scale_roundtrip_lossless

HERE = Path(__file__).resolve().parent
RUN_ID = "j09-var06-sctrt2-v101-ssh-20261004-01"
RUN = HERE / "runs" / RUN_ID
PARENT = HERE.parent / "E04-upstream-transport-slow-v1.0.0"
PARENT_RUN = PARENT / "runs/e04-slow-v100-ssh-20260929-01"
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


def occupancy(start: float, end: float, bin_start: float) -> float:
    return max(0.0, min(end, bin_start + .5) - max(start, bin_start)) / .5


def validate() -> dict:
    differences: list[str] = []
    checks = 0

    def ck(label: str, good: bool) -> None:
        nonlocal checks
        checks += 1
        if not good:
            differences.append(label)

    contract = load(HERE / "contract.json")
    invocation, closure = load(RUN / "invocation.json"), load(RUN / "closure.json")
    ck("contract source", contract["scaled_input_sha256"] == sha(HERE / "scaled-input.json") == sha(RUN / "input.json"))
    ck("parent source", contract["accepted_parent"]["input_sha256"] == sha(PARENT / "native-input.json"))
    ck("parent closure", contract["accepted_parent"]["closure_sha256"] == sha(PARENT_RUN / "closure.json"))
    ck("parent signoff", contract["accepted_parent"]["signoff_sha256"] == sha(PARENT / "cli-scope-signoff-2026-09-29.md"))
    ck("excluded diagnostic closure", contract["excluded_diagnostic"]["closure_sha256"] == sha(HERE.parent / "J09-var06-transport-scale-v1.0.0/runs/j09-var06-sctrt2-v100-ssh-20261004-01/closure.json"))
    ck("exact diff", contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("run identity", invocation["run_id"] == closure["run_id"] == RUN_ID and closure["error"] is None)
    ck("session-0 SSH", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
    ck("GUI and queue", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck("invocation seal", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    ck("sources stable", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    for key, path in {"input": HERE / "scaled-input.json", "contract": HERE / "contract.json",
                      "exact_diff": HERE / "exact-diff.json", "parent": PARENT / "native-input.json",
                      "parent_closure": PARENT_RUN / "closure.json",
                      "parent_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
                      "build.py": HERE / "build.py", "describe_diff.py": HERE / "describe_diff.py",
                      "check_roundtrip.py": HERE / "check_roundtrip.py",
                      "run_native_ssh.ps1": HERE / "run_native_ssh.ps1"}.items():
        ck(f"source hash {key}", closure["source_hashes_before"].get(key) == sha(path))
    ck("raw set", set(closure["raw"]) == RAW)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    steps = load(RUN / "steps.json")
    ck("step order", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(f"step completed {step['name']}", step["status"] == "completed" and step["exit_code"] == 0)
    for step in steps[:4]:
        ck(f"GUI preserved {step['name']}", step["gui_preserved"] is True)
    rt = load(RUN / "roundtrip-validation.json")
    ck("roundtrip checker", rt["passed"] is True and rt["differences"] == [] and len(rt["populated_tables"]) == 22)
    authored, exported = populated(parse(RUN / "input.json")), populated(parse(RUN / "roundtrip-raw.json"))
    for name, table in authored.items():
        ck(f"roundtrip {name}", exported.get(name) == table if name != "ScaleFactors" else scale_roundtrip_lossless(table, exported[name]))
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter diagnostics", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}) and
       not re.search(r"\((?:warning|notice) #(?!(?:108)\))", runlog))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    def event(time: str, fragment: str) -> bool:
        return sum(line.startswith(f"Time: {time} ") and fragment in line for line in log.splitlines()) == 1
    ck("same first failure", event("9.8829", "critical random failure added") and "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in parent_log)
    ck("same base demand and removal", event("10", "<TEACH-LRU-01,0,BASE-01,0> Backorder added") and event("10.1667", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed"))
    ck("failed item four-hour upstream transport", event("10.1667", "transport task 0 starts with 1 items/systems, transport time: 4") and event("14.1667", "transport task 0 arrives with 1 items/systems") and event("14.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>"))
    ck("depot delayed issue", event("14.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives") and event("14.1667", "Take replacement item <TEACH-LRU-01,0,0> from stock") and not event("12.1667", "Take replacement item"))
    ck("spare four-hour downstream transport", event("14.1667", "transport task 2 starts with 1 items/systems, transport time: 4") and event("18.1667", "transport task 2 arrives with 1 items/systems") and event("18.1667", "<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>"))
    ck("backorder and fit", event("18.1667", "Backorder removed, waiting time was 8.16667") and event("18.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours") and event("18.5", "System ready <TEACH-AIR-01,0>"))
    ck("depot repair unchanged duration", event("14.1667", "starts performing, planned to last for 1 hours") and event("15.1667", "Put back replacement item <TEACH-LRU-01,0,1> to stock"))
    ck("single logistics cycle", len(re.findall("Backorder added", log)) == len(re.findall("Backorder removed", log)) == len(re.findall("Take replacement item", log)) == len(re.findall("Put back replacement item", log)) == 1 and len(re.findall(r"transport task \d+ starts with 1 items/systems", log)) == 2)
    ck("same mission outcomes", len(re.findall("mission success:", log)) == 2 and event("9.8829", "mission aborted:") and event("22", "mission success:") and event("34", "mission success:"))

    report, parent_report = parse(RUN / "report-raw.json"), parse(PARENT_RUN / "report-raw.json")
    summary, ps = rows(report, "ResultSummary"), rows(parent_report, "ResultSummary")
    ck("same mission summary", summary == ps and len(summary) == 1 and summary[0]["RTIUP"] == 36)
    system, parent_system = rows(report, "SystemResults"), rows(parent_report, "SystemResults")
    stock, parent_stock = rows(report, "StockTotalResults"), rows(parent_report, "StockTotalResults")
    ck("72 aligned system and stock intervals", all(len(t) == 72 and all(r["STINT"] == i*.5 and r["ETINT"] == (i+1)*.5 for i,r in enumerate(t)) for t in (system, stock, parent_system, parent_stock)))
    ck("one failure and repair", sum(r["NFAIL"] for r in system) == sum(r["NREPT"] for r in system) == 1)
    ck("terminal ready and no backorder", system[-1]["NSYRY"] == system[-1]["NSYA"] == 1 and stock[-1]["NBO"] == 0)
    ck("demand and backorder wait", sum(r["NDF"] for r in stock) == 1 and abs(stock[20]["WT"] - 49/6) < 1e-5 and abs(sum(r["NBO"] for r in stock)*.5 - 49/6) < 1e-5)
    for i, (s, p, t, q) in enumerate(zip(system, parent_system, stock, parent_stock)):
        start = i*.5
        ck(f"system availability bin {i}", abs(s["NSYA"] - p["NSYA"] + occupancy(14.5,18.5,start)) < 1e-5)
        ck(f"system ready bin {i}", abs(s["NSYRY"] - p["NSYRY"] + occupancy(14.5,18.5,start)) < 1e-5)
        ck(f"waiting item bin {i}", abs(s["NSYWI"] - p["NSYWI"] - occupancy(14+1/6,18+1/6,start)) < 1e-5)
        ck(f"repair bin {i}", abs(s["NSYRP"] - p["NSYRP"] + occupancy(14+1/6,14.5,start) - occupancy(18+1/6,18.5,start)) < 1e-5)
        ck(f"backorder bin {i}", abs(t["NBO"] - q["NBO"] - occupancy(14+1/6,18+1/6,start)) < 1e-5)
        ck(f"same failure/demand bin {i}", s["NFAIL"] == p["NFAIL"] and t["NDF"] == q["NDF"])
    return {"schema": "simlox-j09-var06-v101-author-native-validation/v1", "case_id": "J09", "variant_id": "J09.var06",
            "run_id": RUN_ID, "passed": not differences, "checks": checks, "differences": differences,
            "input_sha256": sha(RUN / "input.json"), "model_log_sha256": sha(RUN / "model.log"),
            "report_sha256": sha(RUN / "report-raw.json"), "closure_sha256": sha(RUN / "closure.json"),
            "scope": "one SCTRT=2 route and seed compared with accepted E04 SLOW", "publication_state": "not_published"}


if __name__ == "__main__":
    answer = validate()
    print(json.dumps(answer, indent=2))
    raise SystemExit(0 if answer["passed"] else 1)
