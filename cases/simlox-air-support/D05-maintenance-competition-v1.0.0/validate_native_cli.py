"""Replay the sealed D05 native run and its bounded shared-worker assertions."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

INPUT_SHA256 = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
PARENT_SHA256 = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"]
            for row in instance["rows"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected, "actual": actual,
                       "expected": expected})

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
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")

        check("frozen input SHA", sha(source), INPUT_SHA256)
        check("accepted parent SHA", sha(parent), PARENT_SHA256)
        check("copied input SHA", sha(run / "input.json"), INPUT_SHA256)
        check("contract input SHA", contract["input_sha256"], INPUT_SHA256)
        check("contract parent SHA", contract["parent_input_sha256"], PARENT_SHA256)
        check("contract publication state", contract["publication_state"], "not_published")
        check("run case ID", invocation["case_id"], "D05")
        check("run input SHA", invocation["input_sha256"], INPUT_SHA256)
        check("run parent SHA", invocation["parent_sha256"], PARENT_SHA256)
        check("SSH session zero", invocation["session_id"], 0)
        check("SSH connection", invocation["ssh_connection_present"], True)
        check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("GUI PID", invocation["gui"]["pid"], 13340)
        check("GUI session", invocation["gui"]["session_id"], 1)
        check("queue identity", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("native commands", [x["name"] for x in invocation["planned_commands"]],
              ["import", "export", "calc", "jsonreport"])
        check("executed steps", [x["name"] for x in steps],
              ["import", "export", "calc", "jsonreport", "check_import_export"])
        check("steps successful and GUI guarded", all(x["status"] == "completed" and
              x["exit_code"] == 0 and x["gui_preserved"] for x in steps), True)
        check("roundtrip", roundtrip["passed"], True)
        check("22 input populated tables", len(roundtrip["populated_tables"]), 22)
        check("closure error", closure["error"], None)
        check("closure invocation SHA", closure["invocation_sha256"], sha(run / "invocation.json"))
        check("sealed sources unchanged", closure["source_hashes_before"],
              closure["source_hashes_after"])
        current_sources = {
            "input": sha(source), "parent": sha(parent), "contract": sha(HERE / "contract.json"),
            "builder": sha(HERE / "build.py"), "checker": sha(HERE / "check_roundtrip.py"),
            "runner_script": sha(HERE / "run_native_ssh.ps1"),
        }
        for key, value in current_sources.items():
            check(f"sealed {key} matches current", value, closure["source_hashes_before"][key])
        for name, sealed in sorted(closure["raw"].items()):
            check(f"raw {name} SHA and bytes", [sha(run / name), (run / name).stat().st_size],
                  [sealed["sha256"], sealed["bytes"]])
        check("conversion result", re.findall(r"Errors: (\d+), Warnings: (\d+), Notes: (\d+)", conversion),
              [("0", "2", "0")])
        check("warning IDs", sorted(re.findall(r"warning #(\d+)", conversion)), ["108", "126"])
        check("no native error marker", bool(re.search(r"\berror #\d+", conversion)), False)
        check("report export populated", len(report["report"]["tables"]) > 3, True)

        def times(pattern: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, log, flags=re.MULTILINE)]

        check("one critical random failure", times(r"^Time: ([\d.]+) <TEACH-AIR-01,1> critical random failure added"), [22.6835])
        check("no other random failures", len(re.findall(r"critical random failure added", log)), 1)
        check("mission launches", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|RISK-MISSION),[^\n]+> mission starting,"),
              [8.0, 20.0, 32.0])
        check("mission successes", times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:"), [10.0, 34.0])
        check("risk mission aborted", times(r"^Time: ([\d.]+) <RISK-MISSION,[^\n]+> mission aborted:"), [22.6835])
        check("no mission cancellation", "mission cancelled" in log or "mission canceled" in log, False)
        check("repair task start", times(r"^Time: ([\d.]+)  system DIRP task 0 on <TEACH-AIR-01,1> started$"), [23.0])
        check("repair work start", times(r"^Time: ([\d.]+)  direct repair subtask 0 seqno 1 within system DIRP task 0 on <TEACH-AIR-01,1> starts performing,"), [23.0])
        check("repair work end", times(r"^Time: ([\d.]+)  direct repair subtask 0 seqno 1 within system DIRP task 0 on <TEACH-AIR-01,1> completed$"), [28.0])
        check("repair task complete", times(r"^Time: ([\d.]+)  system DIRP task 0 on <TEACH-AIR-01,1> completed$"), [28.0])
        check("PM object starts", re.findall(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,(\d)> started$", log, flags=re.MULTILINE),
              [("24", "0"), ("24", "1")])
        check("healthy PM work", times(r"^Time: ([\d.]+)  subtask 1 seqno 1 within system PM task 1 on <TEACH-AIR-01,0> starts performing,"), [28.0])
        check("failed aircraft PM work", times(r"^Time: ([\d.]+)  subtask 2 seqno 1 within system PM task 2 on <TEACH-AIR-01,1> starts performing,"), [29.0])
        check("PM completions", re.findall(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,(\d)> completed$", log, flags=re.MULTILINE),
              [("29", "0"), ("30", "1")])
        check("failed aircraft PM reactivation", times(r"^Time: ([\d.]+)  system PM task 2 on <TEACH-AIR-01,1> reactivated$"), [28.0])
        check("worker allocations", times(r"^Time: ([\d.]+)  <P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: 0$"),
              [23.0, 28.0, 29.0])
        check("worker releases", times(r"^Time: ([\d.]+)  <P-MAINT at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1$"),
              [28.0, 29.0, 30.0])
        check("worker only one busy", "Missions and tasks using resources at: <BASE-01,0> 2" in log, False)
        check("terminal two ready", "Time: 30 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log, True)

        tables = {t["name"]: records(t) for t in report["report"]["tables"]}
        system = tables["SystemResults"]
        resource = tables["ResourceResults"]
        check("72 system half-hour rows", len(system), 72)
        check("72 resource half-hour rows", len(resource), 72)
        check("system intervals", [(r["STINT"], r["ETINT"]) for r in system],
              [(i / 2, (i + 1) / 2) for i in range(72)])
        check("resource intervals", [(r["STINT"], r["ETINT"]) for r in resource],
              [(i / 2, (i + 1) / 2) for i in range(72)])
        for key, expected in {"NFAIL": 1, "NREPT": 1, "NPMS": 2, "NPMT": 2}.items():
            check(f"system event sum {key}", sum(r[key] or 0 for r in system), expected)
        for key, expected in {"NSYRP": 5, "NSYPM": 2}.items():
            near(f"system occupancy hours {key}", sum((r[key] or 0) * (r["ETINT"] - r["STINT"])
                                                   for r in system), expected)
        for key, expected in {"NRUM": 7, "NRW": 5}.items():
            near(f"worker {key} integrated hours", sum((r[key] or 0) * (r["ETINT"] - r["STINT"])
                                                    for r in resource), expected)
        check("resource count at all bins", {r["NR"] for r in resource}, {1})
        check("worker usage never exceeds one", max(r["NRUM"] for r in resource), 1)
        check("last system ready count", system[-1]["NSYRY"], 2)
        check("last worker free count", resource[-1]["NRA"], 1)
        near("mission success fraction", tables["ResultSummary"][0]["MSUF"], 2 / 3, 1e-6)
    except (OSError, KeyError, ValueError, TypeError, IndexError, AttributeError) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d05-maintenance-v100-author-native-validation/v1",
              "case_id": "D05", "run_id": run.name, "input_sha256": INPUT_SHA256,
              "passed": all(c["passed"] for c in checks), "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks), "checks": checks,
              "scope": "bounded_one_failure_shared_worker_cli", "publication_state": "not_published"}
    encoded = json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded.encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("case_id", "run_id", "passed", "passed_count", "failed_count")}, ensure_ascii=False))
    if not result["passed"]:
        print(json.dumps([c for c in checks if not c["passed"]], ensure_ascii=False, default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
