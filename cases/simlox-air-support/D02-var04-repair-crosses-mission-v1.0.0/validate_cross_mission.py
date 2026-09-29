"""Replay sealed D02.var04 repair-across-mission run against accepted D06."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
PARENT_RUN = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "runs" / "d06-position-cm-v100-ssh-20260930-02"
RUN = HERE / "runs" / "d02-var04-cross-cm-v100-ssh-20260930-01"
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
        roundtrip = read(RUN / "roundtrip-validation.json")
        conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_report = native(PARENT_RUN / "report-raw.json")
        check("accepted D06 parent SHA", sha(PARENT), contract["parent"]["input_sha256"])
        check("frozen child SHA", sha(source), contract["native_input_sha256"])
        check("copied child SHA", sha(RUN / "input.json"), contract["native_input_sha256"])
        check("copied child identity", native(RUN / "input.json") == child, True)
        check("contract identity", (contract["case_id"], contract["variant_id"],
              contract["case_version"], contract["publication_state"]),
              ("D02", "D02.var04", "1.0.0-candidate", "not_published"))
        check("exact parent diff scope", (sorted(diff["changed_tables_only"]),
              diff["added_tables_only"], diff["unchanged_table_count"]),
              (["CMLocation", "ProblemDescription"], [], 33))
        check("parent direct CM CMT", [r["CMT"] for r in rows(parent, "model", "CMLocation")],
              [0.5])
        check("child direct CM CMT", [(r["FMID"], r["ID"], r["STID"], r["CMT"])
              for r in rows(child, "model", "CMLocation")],
              [("FM-POS-A", "TEACH-AIR-01", "BASE-01", 15.5)])
        check("same failure mode", rows(child, "model", "FailureMode"),
              rows(parent, "model", "FailureMode"))
        check("OPHOURS failure mode", [(r["FMID"], r["MID"], r["FRQ"], r["OPID"])
              for r in rows(child, "model", "FailureMode")],
              [("FM-POS-A", "POS-A", 300000, "OPHOURS")])
        check("same scheduled launches", [r["STIM"] for r in
              rows(child, "model", "OperationProfile")], [8, 20, 32])
        check("seed and horizon unchanged", rows(child, "model", "Control"),
              rows(parent, "model", "Control"))
        check("session-0 guarded invocation", (invocation["case_id"],
              invocation["case_version"], invocation["input_sha256"],
              invocation["parent_sha256"], invocation["session_id"],
              invocation["ssh_connection_present"],
              "sshd.exe" in invocation["ssh_ancestor_names"],
              invocation["gui"]["pid"], invocation["gui"]["session_id"],
              invocation["queue_mutex"]),
              ("D02.var04", "1.0.0-candidate", contract["native_input_sha256"],
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
        failure_pat = r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical CM failure mode added"
        cm_start_pat = r"^Time: ([\d.]+)  system CM task 0 on <TEACH-AIR-01,0> started$"
        cm_done_pat = r"^Time: ([\d.]+)  system CM task 0 on <TEACH-AIR-01,0> completed$"
        mission_start_pat = r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission starting,"
        mission_success_pat = r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:"
        mission_abort_pat = r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:"
        mission_cancel_pat = r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission cancelled:"

        def times(pattern: str, source_text: str = log) -> list[float]:
            return [float(x) for x in re.findall(pattern, source_text, flags=re.MULTILINE)]

        check("same first seeded failure", (times(failure_pat, parent_log),
              times(failure_pat)), ([9.8829, 33.8602], [9.8829]))
        check("failure is FM-POS-A", len(re.findall(
              r"FMID: FM-POS-A", log)), 1)
        check("direct CM starts and completes", (times(cm_start_pat), times(cm_done_pat)),
              ([10], [25.5]))
        check("one 15.5-hour no-resource subtask", len(re.findall(
              r"starts performing, planned to last for 15\.5 hours", log)), 1)
        check("repair spans scheduled hour 20", 10 < 20 < 25.5, True)
        check("parent mission starts", times(mission_start_pat, parent_log), [8, 20, 32])
        check("child mission starts", times(mission_start_pat), [8, 32])
        check("child mission abort/cancel/success", (times(mission_abort_pat),
              times(mission_cancel_pat), times(mission_success_pat)),
              ([9.8829], [20.3333], [34]))
        check("hour-20 mission ordered and waits", (
              "Time: 19 <TEACH-UNIT> mission ordered: BASIC-MISSION" in log,
              "Time: 19 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission waiting:  timeout at 20.3333" in log),
              (True, True))
        check("aircraft ready only after CM at 25.5", "Time: 25.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log,
              True)
        check("parent second mission succeeds, third aborts", (
              times(mission_success_pat, parent_log), times(mission_abort_pat, parent_log)),
              ([22], [9.8829, 33.8602]))
        system = rows(report, "report", "SystemResults")
        stock = rows(report, "report", "StockTotalResults")
        check("72 aligned system bins", [(r["STINT"], r["ETINT"]) for r in system],
              [(i / 2, (i + 1) / 2) for i in range(72)])
        check("72 aligned stock bins", [(r["STINT"], r["ETINT"]) for r in stock],
              [(i / 2, (i + 1) / 2) for i in range(72)])
        check("failure and repair totals", (sum(r["NFAIL"] or 0 for r in system),
              sum(r["NREPT"] or 0 for r in system)), (1, 1))
        check("failure/report bin", [(r["STINT"], r["ETINT"]) for r in system
              if r["NFAIL"]], [(9.5, 10)])
        check("repair completion/report bin", [(r["STINT"], r["ETINT"]) for r in system
              if r["NREPT"]], [(25.5, 26)])
        check("repair spans exactly 31 half-hour bins", [(r["STINT"], r["ETINT"])
              for r in system if r["NSYRP"]],
              [(i / 2, (i + 1) / 2) for i in range(20, 51)])
        near("repair aircraft-hours", sum((r["NSYRP"] or 0) *
             (r["ETINT"] - r["STINT"]) for r in system), 15.5)
        check("no stock demand or backorder", (sum(r["NDF"] or 0 for r in stock),
              sum(r["NBO"] or 0 for r in stock)), (0, 0))
        check("terminal aircraft ready", (system[-1]["NSYRY"], system[-1]["NSYRP"]),
              (1, 0))
        check("parent two failures and repairs", (sum(r["NFAIL"] or 0 for r in
              rows(parent_report, "report", "SystemResults")),
              sum(r["NREPT"] or 0 for r in
                  rows(parent_report, "report", "SystemResults"))), (2, 2))
        near("child mission success fraction", rows(report, "report", "ResultSummary")[0]["MSUF"],
             1 / 3)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d02-var04-cross-mission-author-validation/v1",
              "case_id": "D02", "variant_id": "D02.var04", "run_id": RUN.name,
              "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks),
              "checks": checks, "scope": "fixed_seed_explicit_fmid_long_cm_crosses_scheduled_mission",
              "publication_state": "not_published"}
    output = HERE / "review" / "author-cross-validation-2026-09-30.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
                       .encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("run_id", "passed", "passed_count", "failed_count")}))
    if not result["passed"]:
        print(json.dumps([c for c in checks if not c["passed"]], default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
