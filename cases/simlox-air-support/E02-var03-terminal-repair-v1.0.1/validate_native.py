"""Read-only author replay for the bounded E02.var03 h11 terminal state."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent.parent / "E02-var03-terminal-repair-v1.0.0"
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_native as shared  # noqa: E402


SOURCE_SHA256 = "6d2b20e4ddc92bd5dc0894537152e12dbb3598c1d725c18eb025d4c19b14f28e"
PARENT_RUN = ROOT / "E02-zero-stock-local-backorder-v1.0.0" / "runs" / "e02-v100-ssh-20260929-01"
PARENT_EVENT_SHA256 = "bdea346172a799f2c4c1630fe5f9f132dda6d5f4f6c439fc024ed329bc09dd0c"
PARENT_REPORT_SHA256 = "b5b83fbdc877eac297ba8a7492bdcdb162c6eeaab64901eacb16a3daa5cacf3e"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    return json.loads(shared.remove_trailing_commas(path.read_bytes()))


def audit(run: Path) -> dict:
    failures: list[str] = []
    checks = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    contract = load(HERE / "contract.json")
    ck("frozen contract", contract["case_id"] == "E02" and contract["variant_id"] == "E02.var03"
       and contract["version"] == "1.0.0" and contract["run_id"] == run.name
       and contract["native_input_sha256"] == SOURCE_SHA256)
    ck("frozen child input", sha(HERE / "native-input.json") == SOURCE_SHA256)
    ck("run copied child input", sha(run / "input.json") == SOURCE_SHA256)
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    ck("invocation identity", invocation["run_id"] == run.name and invocation["session_id"] == 0
       and "sshd.exe" in invocation["ssh_ancestor_names"])
    ck("protected GUI", invocation["gui"] == {"pid": 13340, "session_id": 1,
       "start_utc": "2026-09-28T10:09:56.8261381Z"})
    ck("host mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck("closure invocation", closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck("closure success", closure["error"] is None)
    ck("source stable", closure["source_hashes_before"] == closure["source_hashes_after"]
       == invocation["source_hashes_before"])
    for name, record in closure["raw"].items():
        path = run / name
        ck(f"raw {name}", path.is_file() and path.stat().st_size == record["bytes"]
           and sha(path) == record["sha256"])
    for name in ("input.json", "model.sxi", "roundtrip-raw.json", "run.log", "model.sxo",
                 "model.log", "report-raw.json", "steps.json", "roundtrip-check.json"):
        ck(f"required raw {name}", name in closure["raw"])
    steps = load(run / "steps.json")
    ck("step order", [s["name"] for s in steps] == ["import", "export", "calc", "report"])
    for step in steps:
        ck(f"step {step['name']}", step["status"] == "completed" and step["exit_code"] == 0
           and step["gui_preserved"] is True)
    roundtrip = load(run / "roundtrip-check.json")
    ck("20-table roundtrip", roundtrip["passed"] is True and roundtrip["differences"] == []
       and len(roundtrip["populated_tables"]) == 20
       and shared.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    ck("converter summary", match is not None and tuple(map(int, match.groups())) == (0, 1, 0)
       and Counter(re.findall(r"\(warning #(\d+)\)", log)) == Counter({"108": 1}))
    ck("valid SXO", (run / "model.sxo").stat().st_size > 1000)

    child_log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("parent event pin", sha(PARENT_RUN / "model.log") == PARENT_EVENT_SHA256)
    phrases = [
        "critical random failure added",
        "mission aborted:",
        "Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,0>",
        "Backorder added",
        "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed",
        "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem",
        "Item requiring maintenance arrives <TEACH-LRU-01,0,0> from position <TEACH-AIR-01,BASE-01,0>",
        "  item DIRP task 1 on <TEACH-LRU-01,0,0> started",
        "direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,0> starts performing, planned to last for 1 hours",
    ]
    for phrase in phrases:
        parent_lines = [line for line in parent_log.splitlines() if line.startswith("Time: ") and phrase in line
                        and float(line.split()[1]) < 11]
        child_lines = [line for line in child_log.splitlines() if line.startswith("Time: ") and phrase in line]
        ck(f"prefix {phrase[:40]}", len(parent_lines) == len(child_lines) == 1
           and parent_lines == child_lines)
    ck("no post-horizon event", all(float(m.group(1)) <= 11 for m in re.finditer(r"^Time: ([0-9.]+) ", child_log, re.M)))
    for forbidden in ("Finished repair of item", "Backorder removed", "Replacement item arrives",
                      "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing",
                      ):
        ck(f"no {forbidden[:30]}", forbidden not in child_log)
    ck("no post-failure recovery", not any("systems ready: 1" in line and line.startswith("Time: ") and float(line.split()[1]) >= 9.8829 for line in child_log.splitlines()))
    ck("one open backorder", child_log.count("Backorder added") == 1
       and "Backorders at: <TEACH-LRU-01,0,BASE-01,0> Nbr: 1" in child_log)

    child_report = report(run / "report-raw.json")
    parent_report = report(PARENT_RUN / "report-raw.json")
    ck("parent report pin", sha(PARENT_RUN / "report-raw.json") == PARENT_REPORT_SHA256)
    system = shared.table_rows(child_report, "SystemResults")
    stock = shared.table_rows(child_report, "StockTotalResults")
    parent_system = shared.table_rows(parent_report, "SystemResults")
    parent_stock = shared.table_rows(parent_report, "StockTotalResults")
    for name, rows in (("system", system), ("stock", stock)):
        ck(f"{name} 22 contiguous bins", len(rows) == 22 and all(
            row["STINT"] == i * .5 and row["ETINT"] == (i + 1) * .5
            for i, row in enumerate(rows)))
    for i in range(22):
        for field in ("NSYRY", "NSYUA", "NSYRP", "NSYWI", "NFAIL", "NREPT"):
            ck(f"system prefix bin{i} {field}", system[i][field] == parent_system[i][field])
        for field in ("NBO", "NDF", "PNB"):
            ck(f"stock prefix bin{i} {field}", stock[i][field] == parent_stock[i][field])
    ck("terminal aircraft unavailable", system[-1]["NSYRY"] == 0 and system[-1]["NSYUA"] == 1
       and system[-1]["NREPT"] == 0)
    ck("terminal backorder", stock[-1]["NBO"] == 1 and stock[-1]["PNB"] == 0
       and sum(row["NDF"] for row in stock) == 1)
    ck("terminal repair pending by events", "Time: 10.1667  item DIRP task 1 on <TEACH-LRU-01,0,0> started" in child_log
       and "item DIRP task 1 on <TEACH-LRU-01,0,0> completed" not in child_log)
    return {"schema": "simlox-e02-var03-v101-readonly-replay/v1", "run_id": run.name,
            "passed": not failures, "checks": checks, "failures": failures,
            "scope": "one fixed-seed h11 terminal local repair/backorder CLI boundary"}


if __name__ == "__main__":
    try:
        verdict = audit(Path(sys.argv[1]))
    except (OSError, KeyError, TypeError, ValueError, AssertionError, IndexError) as exc:
        verdict = {"schema": "simlox-e02-var03-v101-readonly-replay/v1", "passed": False,
                   "failures": [f"replay error: {type(exc).__name__}: {exc}"]}
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    raise SystemExit(0 if verdict["passed"] else 1)
