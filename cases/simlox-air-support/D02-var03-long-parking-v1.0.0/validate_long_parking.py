"""Replay D02.var03 130-hour no-flight gap against accepted D02.var01."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D02-var01-traditional-op-hours-v1.0.0" / "native-input.json"
PARENT_RUN = HERE.parent / "D02-var01-traditional-op-hours-v1.0.0" / "runs" / "d02-var01-traditional-op-v100-ssh-20260930-01"
RUN = HERE / "runs" / "d02-var03-long-park-v100-ssh-20260930-01"
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table = next(t for t in doc[root]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True))
            for instance in table["instances"] for row in instance["rows"]]


def main() -> int:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tol: float = 1e-5) -> None:
        checks.append({"name": name, "passed": abs(actual - expected) <= tol,
                       "actual": actual, "expected": expected, "tolerance": tol})

    try:
        source = HERE / "native-input.json"
        parent, child, contract, diff = (read(p) for p in
                                         (PARENT, source, HERE / "contract.json",
                                          HERE / "parent-diff.json"))
        invocation, closure, steps = (read(RUN / n) for n in
                                      ("invocation.json", "closure.json", "steps.json"))
        report = native(RUN / "report-raw.json")
        parent_report = native(PARENT_RUN / "report-raw.json")
        roundtrip = read(RUN / "roundtrip-validation.json")
        conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check("accepted parent SHA", sha(PARENT), contract["parent"]["input_sha256"])
        check("frozen child SHA", sha(source), contract["native_input_sha256"])
        check("copied input SHA", sha(RUN / "input.json"), contract["native_input_sha256"])
        check("copied input identity", native(RUN / "input.json") == child, True)
        check("contract identity", (contract["case_id"], contract["variant_id"],
              contract["case_version"], contract["publication_state"]),
              ("D02", "D02.var03", "1.0.0-candidate", "not_published"))
        check("exact parent diff scope", (sorted(diff["changed_tables_only"]),
              diff["added_tables_only"], diff["unchanged_table_count"]),
              (["Control", "OperationProfile", "ProblemDescription", "ResultCollection"],
               [], 27))
        check("parent launches", [r["STIM"] for r in rows(parent, "model", "OperationProfile")],
              [8, 20, 52])
        check("child launches", [r["STIM"] for r in rows(child, "model", "OperationProfile")],
              [8, 20, 152])
        check("seed unchanged", rows(child, "model", "Control")[0]["RSEED"],
              rows(parent, "model", "Control")[0]["RSEED"])
        check("parent and child horizons", ((rows(parent, "model", "Control")[0]["SIMPE"],
              rows(parent, "model", "Control")[0]["RCEND"]),
              (rows(child, "model", "Control")[0]["SIMPE"],
              rows(child, "model", "Control")[0]["RCEND"])),
              ((60, 60), (160, 160)))
        check("result collection horizon", [r["RCEND"] for r in
              rows(child, "model", "ResultCollection")], [160, 160])
        for name in ("System", "Item"):
            check(f"traditional {name} FRT/clock retained", [(r["FRT"], r["OPID"])
                  for r in rows(child, "model", name)], [(300000, "OPHOURS")])
        check("installed LRU and spare retained", (rows(child, "model", "ItemStructure"),
              rows(child, "model", "StockAllocation")),
              (rows(parent, "model", "ItemStructure"),
               rows(parent, "model", "StockAllocation")))
        check("session-0 guarded invocation", (invocation["case_id"],
              invocation["case_version"], invocation["input_sha256"],
              invocation["parent_sha256"], invocation["session_id"],
              invocation["ssh_connection_present"],
              "sshd.exe" in invocation["ssh_ancestor_names"],
              invocation["gui"]["pid"], invocation["gui"]["session_id"],
              invocation["queue_mutex"]),
              ("D02.var03", "1.0.0-candidate", contract["native_input_sha256"],
               contract["parent"]["input_sha256"], 0, True, True, 13340, 1,
               "Global\\SimloxIssue18NativeQueue"))
        check("five guarded steps", [(s["name"], s["status"], s["exit_code"],
              s["gui_preserved"]) for s in steps],
              [(n, "completed", 0, True) for n in
               ("import", "export", "calc", "jsonreport", "check_import_export")])
        check("closure no error", closure["error"], None)
        check("invocation sealed", sha(RUN / "invocation.json"),
              closure["invocation_sha256"])
        check("source hashes stable", closure["source_hashes_before"],
              closure["source_hashes_after"])
        for key, path in {"input": source, "parent": PARENT, "contract": HERE / "contract.json",
                          "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
                          "runner_script": HERE / "run_native_ssh.ps1"}.items():
            check("sealed current " + key, sha(path),
                  closure["source_hashes_before"][key])
        for name, seal in sorted(closure["raw"].items()):
            path = RUN / name
            check("raw " + name, (sha(path), path.stat().st_size),
                  (seal["sha256"], seal["bytes"]))
        check("roundtrip passed", (roundtrip["passed"], roundtrip["differences"]),
              (True, []))
        check("18 row-containing source tables", len(roundtrip["populated_tables"]), 18)
        check("conversion summary", re.findall(
              r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
              conversion), [("0", "1", "0")])
        check("only logging warning", re.findall(r"warning #(\d+)", conversion), ["108"])
        check("no conversion errors", re.findall(r"error #(\d+)", conversion), [])

        def times(pattern: str, data: str = log) -> list[float]:
            return [float(x) for x in re.findall(pattern, data, flags=re.MULTILINE)]

        failure = r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added"
        mission_start = r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission starting,"
        mission_success = r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:"
        mission_abort = r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:"
        check("parent/child failure times", (times(failure, parent_log), times(failure)),
              ([9.8829], [9.8829]))
        check("installed LRU failure", len(re.findall(
              r"subitem failed: <TEACH-LRU-01,0,1> connection path:", log)), 2)
        check("parent mission starts", times(mission_start, parent_log), [8, 20, 52])
        check("child mission starts", times(mission_start), [8, 20, 152])
        check("child mission success/abort", (times(mission_success), times(mission_abort)),
              ([22, 154], [9.8829]))
        check("same first two mission outcomes", (times(mission_success, parent_log)[:1],
              times(mission_abort, parent_log)[:1]), ([22], [9.8829]))
        check("no failure in 22-152 interval", [t for t in times(failure) if 22 <= t < 152], [])
        check("system replacement 10-10.5", (
              times(r"^Time: ([\d.]+)  system SURP task 0 on <TEACH-AIR-01,0> started$"),
              times(r"^Time: ([\d.]+)  system SURP task 0 on <TEACH-AIR-01,0> completed$")),
              ([10], [10.5]))
        check("item direct repair 10.25-11.25", (
              times(r"^Time: ([\d.]+)  item DIRP task 1 on <TEACH-LRU-01,0,1> started$"),
              times(r"^Time: ([\d.]+)  item DIRP task 1 on <TEACH-LRU-01,0,1> completed$")),
              ([10.25], [11.25]))
        check("spare issued and restocked", (
              "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log,
              "Time: 11.25 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in log),
              (True, True))
        check("third mission ordered/prepared late", (
              "Time: 151 <TEACH-UNIT> mission ordered: BASIC-MISSION" in log,
              "Time: 151 <TEACH-AIR-01,0> preparation started" in log),
              (True, True))
        check("next failure time shifts with mission by 100 hours", (
              "Time: 52 <TEACH-AIR-01,0> Next random failure will occur 55.7461" in parent_log,
              "Time: 152 <TEACH-AIR-01,0> Next random failure will occur 155.746" in log),
              (True, True))
        system = rows(report, "report", "SystemResults")
        parent_system = rows(parent_report, "report", "SystemResults")
        stock = rows(report, "report", "StockTotalResults")
        check("320 aligned system bins", [(r["STINT"], r["ETINT"]) for r in system],
              [(i / 2, (i + 1) / 2) for i in range(320)])
        check("320 aligned stock bins", [(r["STINT"], r["ETINT"]) for r in stock],
              [(i / 2, (i + 1) / 2) for i in range(320)])
        check("parent has 120 bins", len(parent_system), 120)
        check("one failure/repair", (sum(r["NFAIL"] or 0 for r in system),
              sum(r["NREPT"] or 0 for r in system)), (1, 1))
        check("no report gap failures", sum(r["NFAIL"] or 0 for r in system
              if r["STINT"] >= 22 and r["ETINT"] <= 152), 0)
        check("no operation in 22-152 gap", sum(r["NSYMO"] or 0 for r in system
              if r["STINT"] >= 22 and r["ETINT"] <= 152), 0)
        check("ready during 22-151 parking", set(r["NSYRY"] for r in system
              if r["STINT"] >= 22 and r["ETINT"] <= 151), {1})
        check("preparation at 151-152", [(r["STINT"], r["ETINT"], r["NSYMA"])
              for r in system if 151 <= r["STINT"] < 152],
              [(151, 151.5, 1), (151.5, 152, 1)])
        check("stock one demand no backorder", (sum(r["NDF"] or 0 for r in stock),
              sum(r["NBO"] or 0 for r in stock)), (1, 0))
        check("terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"]), (1, 0))
        near("summary mission success fraction", rows(report, "report", "ResultSummary")[0]["MSUF"],
             2 / 3)
        near("parent summary same success fraction", rows(parent_report, "report", "ResultSummary")[0]["MSUF"],
             2 / 3)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d02-var03-long-parking-author-validation/v1",
              "case_id": "D02", "variant_id": "D02.var03", "run_id": RUN.name,
              "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks),
              "checks": checks, "scope": "traditional_item_ophours_130_hour_no_flight_gap",
              "publication_state": "not_published"}
    output = HERE / "review" / "author-long-parking-validation-2026-09-30.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
                       .encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("run_id", "passed", "passed_count", "failed_count")}))
    if not result["passed"]:
        print(json.dumps([c for c in checks if not c["passed"]], default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
