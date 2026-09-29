"""Read-only replay of the two sealed D13.var02 MAXPM native runs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ONE = HERE.parent / "D13-var02-maxpm-one-v1.0.0"
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas, table_rows  # noqa: E402

INPUT_SHA = {
    "one": "8881ab42a492ce066dd23a51830b039768c316282e241fd45ee73d0ed5ee9748",
    "two": "d65ba7873f89e9b8e391b731a04aaa9622b346b6f8fa7d4547e177b42a285e41",
}
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--one", type=Path, required=True)
    ap.add_argument("--two", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tolerance: float = 3e-5) -> None:
        checks.append({"name": name, "passed": abs(actual - expected) <= tolerance,
                       "actual": actual, "expected": expected, "tolerance": tolerance})

    try:
        source = {"one": ONE, "two": HERE}
        run = {"one": args.one.resolve(), "two": args.two.resolve()}
        parsed_input: dict[str, dict] = {}
        for kind in ("one", "two"):
            folder, evidence = source[kind], run[kind]
            doc = json.loads((folder / "native-input.json").read_text(encoding="utf-8"))
            parsed_input[kind] = doc
            contract = json.loads((folder / "contract.json").read_text(encoding="utf-8"))
            invocation = json.loads((evidence / "invocation.json").read_text(encoding="utf-8-sig"))
            closure = json.loads((evidence / "closure.json").read_text(encoding="utf-8-sig"))
            steps = json.loads((evidence / "steps.json").read_text(encoding="utf-8-sig"))
            roundtrip = json.loads((evidence / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
            report = json.loads(remove_trailing_commas((evidence / "report-raw.json").read_bytes()))
            log = (evidence / "model.log").read_text(encoding="utf-8-sig", errors="replace")
            check(f"{kind} input SHA", sha(folder / "native-input.json"), INPUT_SHA[kind])
            check(f"{kind} copied input SHA", sha(evidence / "input.json"), INPUT_SHA[kind])
            check(f"{kind} contract SHA binding", contract["input_sha256"], INPUT_SHA[kind])
            check(f"{kind} invocation input SHA", invocation["input_sha256"], INPUT_SHA[kind])
            check(f"{kind} case ID", invocation["case_id"], "D13.var02")
            check(f"{kind} session zero", invocation["session_id"], 0)
            check(f"{kind} SSH ancestry", invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], True)
            check(f"{kind} GUI PID/session", [invocation["gui"]["pid"], invocation["gui"]["session_id"]], [13340, 1])
            check(f"{kind} queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
            check(f"{kind} five steps", [x["name"] for x in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
            check(f"{kind} step exits and GUI", all(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"] for x in steps), True)
            check(f"{kind} roundtrip", [roundtrip["passed"], len(roundtrip["populated_tables"])], [True, 18])
            check(f"{kind} closure error", closure["error"], None)
            check(f"{kind} invocation seal", closure["invocation_sha256"], sha(evidence / "invocation.json"))
            check(f"{kind} source seals", closure["source_hashes_before"], closure["source_hashes_after"])
            for field, file in [("input", folder / "native-input.json"), ("contract", folder / "contract.json"),
                                ("builder", folder / "build.py"), ("checker", folder / "check_roundtrip.py"),
                                ("runner_script", folder / "run_native_ssh.ps1")]:
                check(f"{kind} sealed source {field}", closure["source_hashes_after"][field], sha(file))
            for name, sealed in sorted(closure["raw"].items()):
                check(f"{kind} sealed raw {name}", [sha(evidence / name), (evidence / name).stat().st_size],
                      [sealed["sha256"], sealed["bytes"]])

            def times(pattern: str) -> list[float]:
                return [float(x) for x in re.findall(pattern, log, re.MULTILINE)]

            check(f"{kind} PM task starts", times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,[01]> started$"), [24.0, 24.0])
            check(f"{kind} PM identities", len(re.findall(r"^Time: 24  system PM task \d+ on <TEACH-AIR-01,[01]> PMID: CAL24$", log, re.MULTILINE)), 2)
            work = times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,[01]> starts performing, planned to last for 1 hours$")
            done = times(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,[01]> completed$")
            pm_done = times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,[01]> completed$")
            check(f"{kind} subtask work starts", work, [24.0, 25.0] if kind == "one" else [24.0, 24.0])
            check(f"{kind} subtask work ends", done, [25.0, 26.0] if kind == "one" else [25.0, 25.0])
            check(f"{kind} PM completions", pm_done, [25.0, 26.0] if kind == "one" else [25.0, 25.0])
            check(f"{kind} distinct PM aircraft", sorted(set(re.findall(r"^Time: 24  system PM task \d+ on <TEACH-AIR-01,([01])> started$", log, re.MULTILINE))), ["0", "1"])
            check(f"{kind} mission starts", times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission starting, duration: 2 : <TEACH-AIR-01,[01]>$"), [8.0, 20.0, 32.0])
            check(f"{kind} mission completions", times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission completed: <TEACH-AIR-01,[01]>$"), [10.0, 22.0, 34.0])
            check(f"{kind} no mission cancellation", bool(re.search(r"mission (?:aborted|cancelled|canceled)", log, re.I)), False)
            rows = table_rows(report, "SystemResults")
            check(f"{kind} 72 report bins", [(x["STINT"], x["ETINT"]) for x in rows], [(i / 2, (i + 1) / 2) for i in range(72)])
            by_start = {x["STINT"]: x for x in rows}
            check(f"{kind} PM start marker", [(t, x["NPMS"]) for t, x in by_start.items() if x["NPMS"]], [(24, 2)])
            check(f"{kind} PM completion markers", [(t, x["NPMT"]) for t, x in by_start.items() if x["NPMT"]], [(25, 1), (26, 1)] if kind == "one" else [(25, 2)])
            near(f"{kind} PM peak", max(x["NSYPM"] for x in rows), 1.0 if kind == "one" else 2.0)
            near(f"{kind} PM aircraft-hours", sum(x["NSYPM"] * 0.5 for x in rows), 2.0)
            check(f"{kind} terminal ready", rows[-1]["NSYRY"], 2)
            check(f"{kind} no failures/repairs", all(x["NFAIL"] == 0 and x["NREPT"] == 0 for x in rows), True)
            check(f"{kind} report horizon", table_rows(report, "ResultSummary")[0]["RTIUP"], 36)
            runlog = (evidence / "run.log").read_text(encoding="utf-8-sig", errors="replace")
            check(f"{kind} conversion", ["Errors: 0, Warnings: 2" in runlog, "warning #108" in runlog, "warning #126" in runlog], [True, True, True])

        check("accepted D03 parent SHA", sha(HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"), PARENT_SHA)
        check("one parent binding", json.loads((ONE / "contract.json").read_text(encoding="utf-8"))["parent_input_sha256"], PARENT_SHA)
        check("two parent binding", json.loads((HERE / "contract.json").read_text(encoding="utf-8"))["parent_input_sha256"], INPUT_SHA["one"])
        left, right = copy.deepcopy(parsed_input["one"]), copy.deepcopy(parsed_input["two"])
        def get(doc: dict, name: str) -> dict:
            return next(t for t in doc["model"]["tables"] if t["name"] == name)
        get(right, "ProblemDescription")["instances"][0]["rows"] = get(left, "ProblemDescription")["instances"][0]["rows"]
        unit = get(right, "Unit")
        unit["instances"][0]["rows"][0][next(i for i, c in enumerate(unit["columns"]) if c["name"] == "MAXPM")] = 1
        check("only MAXPM plus label differs", right == left, True)
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError, StopIteration) as exc:
        checks.append({"name": "replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d13-var02-maxpm-pair-replay/v1", "case_id": "D13.var02",
              "run_ids": {"one": args.one.name, "two": args.two.name},
              "passed": all(c["passed"] for c in checks), "checks_count": len(checks), "checks": checks,
              "scope": "two noncritical CAL24 PM tasks with MAXPM one versus two, no resource demands",
              "publication_state": "candidate"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output:
        args.output.write_bytes(raw)
    else:
        sys.stdout.buffer.write(raw)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
