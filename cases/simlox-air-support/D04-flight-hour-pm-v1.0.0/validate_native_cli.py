"""Replay D04's sealed native run against its bounded PM contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas, table_rows  # noqa: E402

INPUT_SHA256 = "d0b0ee5b74f3afe5f05b418771774adcf8ef987b0f553f1bfd535874955c790a"
PARENT_SHA256 = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tolerance: float = 3e-5) -> None:
        checks.append({"name": name, "passed": abs(actual - expected) <= tolerance,
                       "actual": actual, "expected": expected, "tolerance": tolerance})

    try:
        source = HERE / "native-input.json"
        parent = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
        contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
        report = json.loads(remove_trailing_commas((run / "report-raw.json").read_bytes()))
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")

        check("case source SHA", sha(source), INPUT_SHA256)
        check("parent source SHA", sha(parent), PARENT_SHA256)
        check("copied native input SHA", sha(run / "input.json"), INPUT_SHA256)
        check("contract input SHA", contract["input_sha256"], INPUT_SHA256)
        check("contract parent SHA", contract["parent_input_sha256"], PARENT_SHA256)
        check("run case ID", invocation["case_id"], "D04")
        check("run input SHA", invocation["input_sha256"], INPUT_SHA256)
        check("run parent SHA", invocation["parent_sha256"], PARENT_SHA256)
        check("SSH session zero", invocation["session_id"], 0)
        check("SSH connection", invocation["ssh_connection_present"], True)
        check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("GUI PID", invocation["gui"]["pid"], 13340)
        check("GUI session", invocation["gui"]["session_id"], 1)
        check("queue identity", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("planned native commands", [x["name"] for x in invocation["planned_commands"]],
              ["import", "export", "calc", "jsonreport"])
        check("executed steps", [x["name"] for x in steps],
              ["import", "export", "calc", "jsonreport", "check_import_export"])
        check("all steps completed", all(x["status"] == "completed" and x["exit_code"] == 0
                                         and x["gui_preserved"] for x in steps), True)
        check("roundtrip identity", roundtrip["passed"], True)
        check("closure error", closure["error"], None)
        check("closure invocation hash", closure["invocation_sha256"], sha(run / "invocation.json"))
        check("sealed source hashes", closure["source_hashes_before"], closure["source_hashes_after"])
        for name, sealed in sorted(closure["raw"].items()):
            check(f"sealed raw {name}", [sha(run / name), (run / name).stat().st_size],
                  [sealed["sha256"], sealed["bytes"]])

        def times(pattern: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, log, flags=re.MULTILINE)]

        check("PM start sequence", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"), [41.0])
        check("PM identity count", len(re.findall(r"^Time: [\d.]+  system PM task \d+ on <TEACH-AIR-01,0> PMID: OP3$", log, re.MULTILINE)), 1)
        check("PM completion sequence", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"), [42.0])
        check("subtask work sequence", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$"), [41.0])
        check("subtask completion sequence", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed$"), [42.0])
        check("no resource demand for bounded case", log.count("requests resources: no resources needed"), 1)
        check("mission starts", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission starting, duration: [12] : <TEACH-AIR-01,0>$"), [8.0, 40.0])
        check("mission type and duration at launch",
              re.findall(r"^Time: [\d.]+ <(BASIC-MISSION|SHORT-MISSION),[^\n]+> mission starting, duration: ([12]) : <TEACH-AIR-01,0>$", log, re.MULTILINE),
              [("BASIC-MISSION", "2"), ("SHORT-MISSION", "1")])
        check("mission successes", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission success: $"), [10.0, 41.0])
        check("mission completions", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),[^\n]+> mission completed: <TEACH-AIR-01,0>$"), [10.0, 41.0])
        check("no mission abort or cancellation", bool(re.search(r"mission (?:aborted|cancelled|canceled)", log, re.I)), False)

        summary = table_rows(report, "ResultSummary")
        check("one report summary", len(summary), 1)
        check("report horizon", summary[0]["RTIUP"], 60)
        rows = table_rows(report, "SystemResults")
        check("120 half-hour system rows", len(rows), 120)
        check("system row coverage", [(x["STINT"], x["ETINT"]) for x in rows],
              [(i / 2, (i + 1) / 2) for i in range(120)])
        by_start = {x["STINT"]: x for x in rows}
        check("PM start report markers", [t for t, x in by_start.items() if x["NPMS"] == 1], [41.0])
        check("PM completion report markers", [t for t, x in by_start.items() if x["NPMT"] == 1], [42.0])
        check("no PM occupancy before second return", all(x["NSYPM"] == 0 for x in rows if x["ETINT"] <= 41), True)
        check("no flight through long gap", all(x["NSYMO"] == 0 for x in rows if 10 <= x["STINT"] and x["ETINT"] <= 40), True)
        for t in [41.5]:
            near(f"PM occupies {t}h interval", by_start[t]["NSYPM"], 1.0)
            near(f"aircraft unready during {t}h PM", by_start[t]["NSYRY"], 0.0)
        for t in [10.5, 24.5, 38.5, 42.5, 59.5]:
            near(f"ready at {t}h", by_start[t]["NSYRY"], 1.0)
        check("no reported failures", all(x["NFAIL"] == 0 for x in rows), True)
        check("no reported repairs", all(x["NREPT"] == 0 for x in rows), True)
        check("reported PM starts", sum(x["NPMS"] for x in rows), 1)
        check("reported PM completions", sum(x["NPMT"] for x in rows), 1)
        near("PM occupancy integral in aircraft-hours", sum(x["NSYPM"] * 0.5 for x in rows), 1.0)
        near("flight integral in aircraft-hours", sum(x["NSYMO"] * 0.5 for x in rows), 3.0)
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
        checks.append({"name": "replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d04-flight-v100-behavior-replay/v1", "case_id": "D04",
              "run_id": run.name, "passed": all(c["passed"] for c in checks),
              "checks_count": len(checks), "checks": checks,
              "scope": "one aircraft, two missions totaling three OPHOURS and one one-hour PM",
              "publication_state": "candidate"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output:
        args.output.write_bytes(raw)
    else:
        sys.stdout.buffer.write(raw)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
