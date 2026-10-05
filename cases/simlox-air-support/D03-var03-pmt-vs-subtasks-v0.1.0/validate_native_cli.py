"""Replay the sealed D03.var03 child against the full accepted D03 run."""
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

INPUT_SHA256 = "59642b8ef5ac9e48c45110223b147cf776e0be4e0e8983a2e9507b1412074a36"
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

        parent_run = HERE.parent / "D03-calendar-pm-v1.0.0" / "runs" / "d03-calendar-v100-ssh-20261001-02"
        parent_closure = json.loads((parent_run / "closure.json").read_text(encoding="utf-8-sig"))
        parent_report = json.loads(remove_trailing_commas((parent_run / "report-raw.json").read_bytes()))
        parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check("accepted parent closure SHA", sha(parent_run / "closure.json"),
              "9cd845f957105eb8659809ec09cf380ae5df68a63babb264d70631c164f7d2d8")
        check("accepted parent report SHA", sha(parent_run / "report-raw.json"),
              "a9cc414e9b40da06be620e5fb64c52e0db41ec6fe959ac0874497d358232a84e")
        check("accepted parent event SHA", sha(parent_run / "model.log"),
              "edd41c34046fb92e53a3f5eb8569cec3a932aa00aed8e878ecc40ef45826a4a5")
        check("accepted parent closure status", parent_closure["error"], None)
        for name, seal in parent_closure["raw"].items():
            check(f"accepted parent raw {name}", [sha(parent_run / name), (parent_run / name).stat().st_size],
                  [seal["sha256"], seal["bytes"]])
        check("case source SHA", sha(source), INPUT_SHA256)
        check("parent source SHA", sha(parent), PARENT_SHA256)
        check("copied native input SHA", sha(run / "input.json"), INPUT_SHA256)
        check("contract variant ID", contract["variant_id"], "D03.var03")
        check("contract version", contract["version"], "0.1.0-contract-candidate")
        check("reserved run ID", contract["ownership"]["native_run_id_reserved"], run.name)
        check("contract parent SHA", contract["accepted_parent"]["input_sha256"], PARENT_SHA256)
        check("contract proposed PMT change", contract["source_delta"]["only_changed_cell"],
              "PMLocation row CAL24/TEACH-AIR-01/BASE-01 PMT 1 to 4 hours")
        check("run case ID", invocation["case_id"], "D03")
        check("run variant ID", invocation["variant_id"], "D03.var03")
        check("run ID", invocation["run_id"], "d03-var03-pmt4-task1-v010-ssh-20261006-01")
        check("run input SHA", invocation["input_sha256"], INPUT_SHA256)
        check("run parent SHA", invocation["parent_sha256"], PARENT_SHA256)
        check("SSH session zero", invocation["session_id"], 0)
        check("SSH connection", invocation["ssh_connection_present"], True)
        check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("GUI PID", invocation["gui"]["pid"], 13340)
        check("GUI session", invocation["gui"]["session_id"], 1)
        check("GUI start", invocation["gui"]["start_utc"], "2026-09-28T10:09:56.8261381Z")
        check("queue identity", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("planned native commands", [x["name"] for x in invocation["planned_commands"]],
              ["import", "export", "calc", "jsonreport"])
        check("executed steps", [x["name"] for x in steps],
              ["import", "export", "check_import_export", "calc", "jsonreport"])
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

        check("PM start sequence", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"), [24.0, 49.0])
        check("PM identity count", len(re.findall(r"^Time: [\d.]+  system PM task \d+ on <TEACH-AIR-01,0> PMID: CAL24$", log, re.MULTILINE)), 2)
        check("PM completion sequence", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"), [25.0, 50.0])
        check("subtask work sequence", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$"), [24.0, 49.0])
        check("subtask completion sequence", times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed$"), [25.0, 50.0])
        check("no resource demand for bounded case", log.count("requests resources: no resources needed"), 2)
        check("mission starts", times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission starting, duration: 2 : <TEACH-AIR-01,0>$"), [8.0, 20.0, 32.0])
        check("mission successes", times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success: $"), [10.0, 22.0, 34.0])
        check("mission completions", times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission completed: <TEACH-AIR-01,0>$"), [10.0, 22.0, 34.0])
        check("no mission abort or cancellation", bool(re.search(r"mission (?:aborted|cancelled|canceled)", log, re.I)), False)
        check("all child event lines equal accepted parent", log.splitlines()[2:],
              parent_log.splitlines()[2:])

        summary = table_rows(report, "ResultSummary")
        check("one report summary", len(summary), 1)
        check("report horizon", summary[0]["RTIUP"], 60)
        check("ResultSummary equals accepted parent", summary, table_rows(parent_report, "ResultSummary"))
        rows = table_rows(report, "SystemResults")
        check("120 half-hour system rows", len(rows), 120)
        check("system row coverage", [(x["STINT"], x["ETINT"]) for x in rows],
              [(i / 2, (i + 1) / 2) for i in range(120)])
        check("all SystemResults rows equal accepted parent", rows,
              table_rows(parent_report, "SystemResults"))
        stock = table_rows(report, "StockTotalResults")
        check("120 stock rows", len(stock), 120)
        check("all StockTotalResults rows equal accepted parent", stock,
              table_rows(parent_report, "StockTotalResults"))
        by_start = {x["STINT"]: x for x in rows}
        check("PM start report markers", [t for t, x in by_start.items() if x["NPMS"] == 1], [24.0, 49.0])
        check("PM completion report markers", [t for t, x in by_start.items() if x["NPMT"] == 1], [25.0, 50.0])
        for t in [24.5, 49.5]:
            near(f"PM occupies {t}h interval", by_start[t]["NSYPM"], 1.0)
            near(f"aircraft unready during {t}h PM", by_start[t]["NSYRY"], 0.0)
        for t in [23.5, 25.5, 48.5, 50.5, 59.5]:
            near(f"ready at {t}h", by_start[t]["NSYRY"], 1.0)
        check("no reported failures", all(x["NFAIL"] == 0 for x in rows), True)
        check("no reported repairs", all(x["NREPT"] == 0 for x in rows), True)
        check("reported PM starts", sum(x["NPMS"] for x in rows), 2)
        check("reported PM completions", sum(x["NPMT"] for x in rows), 2)
        near("integrated ready aircraft-hours", sum(x["NSYRY"] * .5 for x in rows), 49)
        near("integrated available aircraft-hours", sum(x["NSYA"] * .5 for x in rows), 58)
        near("integrated mission aircraft-hours", sum(x["NSYMO"] * .5 for x in rows), 6)
        near("integrated PM aircraft-hours", sum(x["NSYPM"] * .5 for x in rows), 2)
        check("terminal aircraft ready", rows[-1]["NSYRY"], 1)
        check("terminal PM count", rows[-1]["NSYPM"], 0)
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
        checks.append({"name": "replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d03-var03-v010-behavior-replay/v1", "case_id": "D03",
              "run_id": run.name, "passed": all(c["passed"] for c in checks),
              "checks_count": len(checks), "checks": checks,
              "scope": "one aircraft, three missions and two one-hour calendar-PM cycles before hour 60 despite PMT four",
              "publication_state": "candidate"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output:
        args.output.write_bytes(raw)
    else:
        sys.stdout.buffer.write(raw)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
