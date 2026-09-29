"""Replay the sealed D05.var04 positive-worker repair-at-horizon native run."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D05-maintenance-competition-v1.0.0" / "native-input.json"
INPUT_SHA = "c079a64d31f1b4ae2d7d537d1546bc5277bf20bcc55353aa7d1c4f487edd2b74"
PARENT_SHA = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table = next(t for t in doc[root]["tables"] if t["name"] == name)
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row, strict=True)) for instance in table["instances"]
            for row in instance["rows"]]


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
        parent, child = read(PARENT), read(HERE / "native-input.json")
        contract = read(HERE / "contract.json")
        invocation, closure, steps = (read(run / n) for n in
                                       ["invocation.json", "closure.json", "steps.json"])
        roundtrip = read(run / "roundtrip-validation.json")
        copied, exported, report = (native(run / n) for n in
                                    ["input.json", "roundtrip-raw.json", "report-raw.json"])
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")

        check("accepted parent SHA", sha(PARENT), PARENT_SHA)
        check("frozen child SHA", sha(HERE / "native-input.json"), INPUT_SHA)
        check("copied input SHA", sha(run / "input.json"), INPUT_SHA)
        check("contract source binding", (contract["parent_input_sha256"], contract["input_sha256"]),
              (PARENT_SHA, INPUT_SHA))
        check("contract identity", (contract["variant_id"], contract["publication_state"]),
              ("D05.var04", "not_published"))
        p_tables = {t["name"]: t for t in parent["model"]["tables"]}
        c_tables = {t["name"]: t for t in child["model"]["tables"]}
        check("native table names preserved", set(p_tables), set(c_tables))
        check("exact changed table set", {n for n in p_tables if p_tables[n] != c_tables[n]},
              {"ProblemDescription", "Control", "OperationProfile", "ResultCollection"})
        check("stop fields", (rows(child, "model", "Control")[0]["SIMPE"],
                               rows(child, "model", "Control")[0]["RCEND"]), (26, 26))
        check("result end fields", {r["RCEND"] for r in rows(child, "model", "ResultCollection")}, {26})
        check("parent mission starts", [r["STIM"] for r in rows(parent, "model", "OperationProfile")],
              [8, 20, 32])
        check("child mission starts", [r["STIM"] for r in rows(child, "model", "OperationProfile")],
              [8, 20])
        check("worker capacity retained", rows(child, "model", "ResourceAllocation")[0]["RQTY"], 1)
        check("copied model equals source", copied, child)
        source_tables = {t["name"]: (t["columns"],
                         [row for i in t["instances"] for row in i["rows"]])
                         for t in copied["model"]["tables"] if any(i["rows"] for i in t["instances"])}
        export_tables = {t["name"]: (t["columns"],
                         [row for i in t["instances"] for row in i["rows"]])
                         for t in exported["model"]["tables"] if any(i["rows"] for i in t["instances"])}
        check("all 22 source table rows roundtrip", len(source_tables) == 22 and
              all(export_tables.get(n) == value for n, value in source_tables.items()), True)
        check("roundtrip checker", (roundtrip["passed"], roundtrip["differences"]), (True, []))
        check("invocation identity", (invocation["case_id"], invocation["input_sha256"],
              invocation["parent_sha256"], invocation["session_id"],
              invocation["ssh_connection_present"], invocation["gui"]["pid"],
              invocation["queue_mutex"]),
              ("D05.var04", INPUT_SHA, PARENT_SHA, 0, True, 13340,
               "Global\\SimloxIssue18NativeQueue"))
        check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("five guarded native steps", [(s["name"], s["status"], s["exit_code"],
              s["gui_preserved"]) for s in steps],
              [(n, "completed", 0, True) for n in
               ["import", "export", "calc", "jsonreport", "check_import_export"]])
        check("closure no error", closure["error"], None)
        check("closure invocation hash", closure["invocation_sha256"], sha(run / "invocation.json"))
        check("source hashes stable during run", closure["source_hashes_before"],
              closure["source_hashes_after"])
        for name, path in {"input": HERE / "native-input.json", "parent": PARENT,
                           "contract": HERE / "contract.json", "builder": HERE / "build.py",
                           "checker": HERE / "check_roundtrip.py",
                           "runner_script": HERE / "run_native_ssh.ps1"}.items():
            check(f"sealed current {name}", sha(path), closure["source_hashes_before"][name])
        for name, record in sorted(closure["raw"].items()):
            check(f"raw {name}", (sha(run / name), (run / name).stat().st_size),
                  (record["sha256"], record["bytes"]))
        check("conversion errors warnings notes", re.findall(
              r"Errors: (\d+), Warnings: (\d+), Notes: (\d+)", conversion), [("0", "2", "0")])
        check("warning IDs", sorted(re.findall(r"warning #(\d+)", conversion)), ["108", "126"])
        check("native error markers", re.findall(r"error #(\d+)", conversion), [])
        check("log horizon", log.splitlines()[1], "26")

        def times(pattern: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, log, flags=re.MULTILINE)]

        check("mission starts", times(r"^Time: ([\d.]+) <(?:BASIC-MISSION|RISK-MISSION),[^\n]+> mission starting,"), [8, 20])
        check("first mission succeeds", times(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:"), [10])
        check("one critical failure", times(r"^Time: ([\d.]+) <TEACH-AIR-01,1> critical random failure added"), [22.6835])
        check("risk mission abort", times(r"^Time: ([\d.]+) <RISK-MISSION,[^\n]+> mission aborted:"), [22.6835])
        check("repair task starts", times(r"^Time: ([\d.]+)  system DIRP task 0 on <TEACH-AIR-01,1> started$"), [23])
        check("repair work starts", times(r"^Time: ([\d.]+)  direct repair subtask 0 seqno 1 within system DIRP task 0 on <TEACH-AIR-01,1> starts performing,"), [23])
        check("repair work planned five hours", "starts performing, planned to last for 5 hours" in log, True)
        check("one worker booked", times(r"^Time: ([\d.]+)  <P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: 0$"), [23])
        check("no worker deallocation before stop", "deallocated from  maintenance task" in log, False)
        check("PM task objects start", re.findall(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,([01])> started$", log, flags=re.MULTILINE),
              [("24", "0"), ("24", "1")])
        check("one failed PM worker request", len(re.findall(r"^  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 failed ?$", log, flags=re.MULTILINE)), 1)
        check("no maintenance completion", bool(re.search(r"^Time: [\d.]+  (?:system (?:DIRP|PM) task|(?:direct repair )?subtask).* completed$", log, flags=re.MULTILINE)), False)
        check("no PM work", bool(re.search(r"within system PM task .* starts performing", log)), False)
        check("last log event at horizon", log.rstrip().splitlines()[-1].startswith("Time: 26  resource shift 0 ended"), True)

        system = rows(report, "report", "SystemResults")
        resource = rows(report, "report", "ResourceResults")
        summary = rows(report, "report", "ResultSummary")
        check("52 half-hour system bins", len(system), 52)
        check("52 half-hour resource bins", len(resource), 52)
        expected_intervals = [(i / 2, (i + 1) / 2) for i in range(52)]
        check("system intervals", [(r["STINT"], r["ETINT"]) for r in system], expected_intervals)
        check("resource intervals", [(r["STINT"], r["ETINT"]) for r in resource], expected_intervals)
        for key, expected in {"NFAIL": 1, "NREPT": 0, "NPMS": 2, "NPMT": 0}.items():
            check(f"system {key} sum", sum(r[key] or 0 for r in system), expected)
        for key, expected in {"NSYRP": 3, "NSYPM": 0}.items():
            near(f"system {key} aircraft-hours", sum((r[key] or 0) *
                 (r["ETINT"] - r["STINT"]) for r in system), expected)
        for key, expected in {"NRUM": 3, "NRW": 2}.items():
            near(f"resource {key} hours", sum((r[key] or 0) *
                 (r["ETINT"] - r["STINT"]) for r in resource), expected)
        check("one aircraft ready in final bin", system[-1]["NSYRY"], 1)
        check("repair occupying final bin", system[-1]["NSYRP"], 1)
        check("worker used in final bin", resource[-1]["NRUM"], 1)
        check("PM request waiting in final bin", resource[-1]["NRW"], 1)
        near("one of two missions succeeds", summary[0]["MSUF"], 0.5, 1e-6)
    except (OSError, KeyError, ValueError, TypeError, IndexError, AttributeError) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d05-var04-horizon-repair-v100-author-validation/v1",
              "case_id": "D05", "variant_id": "D05.var04", "run_id": run.name,
              "input_sha256": INPUT_SHA, "passed": all(x["passed"] for x in checks),
              "passed_count": sum(x["passed"] for x in checks),
              "failed_count": sum(not x["passed"] for x in checks), "checks": checks,
              "scope": "positive_worker_repair_in_progress_at_hour_26_cli",
              "publication_state": "not_published"}
    encoded = (json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n").encode("utf-8")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    print(json.dumps({k: result[k] for k in ("run_id", "passed", "passed_count", "failed_count")}))
    if not result["passed"]:
        print(json.dumps([x for x in checks if not x["passed"]], default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
