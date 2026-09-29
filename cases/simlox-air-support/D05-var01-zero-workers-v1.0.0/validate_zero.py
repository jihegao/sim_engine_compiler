"""Replay the zero-worker D05.var01 horizon case and accepted one-worker control."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D05-maintenance-competition-v1.0.0"
RUN = HERE / "runs" / "d05-var01-zero-v100-ssh-20260930-01"
BASE_RUN = PARENT / "runs" / "d05-pilot-v100-ssh-20260930-03"
PARENT_SHA = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
INPUT_SHA = "e8ef846a1f5c87e2fce982baaa3c5057b2f9554f3a620b09c49d6ecb8bd4e158"
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
    return [dict(zip(cols, row, strict=True)) for i in table["instances"] for row in i["rows"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected, "actual": actual,
                       "expected": expected})

    def near(name: str, actual: float, expected: float, tolerance: float = 3e-5) -> None:
        checks.append({"name": name, "passed": abs(actual - expected) <= tolerance,
                       "actual": actual, "expected": expected, "tolerance": tolerance})

    try:
        parent_path, child_path = PARENT / "native-input.json", HERE / "native-input.json"
        parent, child = read(parent_path), read(child_path)
        contract = read(HERE / "contract.json")
        invocation, closure, steps = (read(RUN / n) for n in ["invocation.json", "closure.json", "steps.json"])
        roundtrip = read(RUN / "roundtrip-validation.json")
        copied, exported, report = (native(RUN / n) for n in
                                    ["input.json", "roundtrip-raw.json", "report-raw.json"])
        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        base_report = native(BASE_RUN / "report-raw.json")
        check("accepted parent input SHA", sha(parent_path), PARENT_SHA)
        check("zero-worker input SHA", sha(child_path), INPUT_SHA)
        check("contract source binding", (contract["parent_input_sha256"], contract["input_sha256"]),
              (PARENT_SHA, INPUT_SHA))
        p_tables = {t["name"]: t for t in parent["model"]["tables"]}
        c_tables = {t["name"]: t for t in child["model"]["tables"]}
        check("same native tables", set(p_tables), set(c_tables))
        check("exact changed table set", {n for n in p_tables if p_tables[n] != c_tables[n]},
              {"ProblemDescription", "Resource", "ResourceAllocation"})
        for table, field in [("ProblemDescription", "PDESC"), ("Resource", "DESCR"),
                             ("ResourceAllocation", "RQTY")]:
            a, b = rows(parent, "model", table), rows(child, "model", table)
            check(f"{table} only {field} differs", (len(a), len(b),
                  {k for k in a[0] if a[0][k] != b[0][k]}), (1, 1, {field}))
        check("worker capacity one to zero", (rows(parent, "model", "ResourceAllocation")[0]["RQTY"],
              rows(child, "model", "ResourceAllocation")[0]["RQTY"]), (1, 0))
        check("copied input SHA", sha(RUN / "input.json"), INPUT_SHA)
        check("invocation identity", (invocation["case_id"], invocation["input_sha256"],
              invocation["parent_sha256"], invocation["session_id"],
              invocation["ssh_connection_present"], invocation["gui"]["pid"],
              invocation["queue_mutex"]),
              ("D05.var01", INPUT_SHA, PARENT_SHA, 0, True, 13340,
               "Global\\SimloxIssue18NativeQueue"))
        check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("five guarded steps", [(s["name"], s["status"], s["exit_code"],
              s["gui_preserved"]) for s in steps],
              [(n, "completed", 0, True) for n in
               ["import", "export", "calc", "jsonreport", "check_import_export"]])
        check("closure no error", closure["error"], None)
        check("closure invocation hash", closure["invocation_sha256"], sha(RUN / "invocation.json"))
        check("sealed sources unchanged", closure["source_hashes_before"],
              closure["source_hashes_after"])
        for name, path in {"input": child_path, "parent": parent_path,
                           "contract": HERE / "contract.json", "builder": HERE / "build.py",
                           "checker": HERE / "check_roundtrip.py",
                           "runner_script": HERE / "run_native_ssh.ps1"}.items():
            check(f"current sealed {name}", sha(path), closure["source_hashes_before"][name])
        for name, record in sorted(closure["raw"].items()):
            check(f"raw {name}", (sha(RUN / name), (RUN / name).stat().st_size),
                  (record["sha256"], record["bytes"]))
        check("roundtrip passed", roundtrip["passed"], True)
        check("source row-containing table count", len(roundtrip["populated_tables"]), 22)
        check("copied source equals child", copied, child)
        populated = lambda doc: {t["name"]: (t["columns"],
                    [row for i in t["instances"] for row in i["rows"]])
                    for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])}
        check("exported source rows", all(populated(exported).get(n) == v
              for n, v in populated(copied).items()), True)
        check("zero conversion errors", re.findall(r"Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
              conversion), [("0", "2", "0")])
        check("warning IDs", sorted(re.findall(r"warning #(\d+)", conversion)), ["108", "126"])

        matches = lambda pattern: re.findall(pattern, log, flags=re.MULTILINE)
        check("one critical failure", matches(r"^Time: ([\d.]+) <TEACH-AIR-01,1> critical random failure added"), ["22.6835"])
        check("risk mission abort", matches(r"^Time: ([\d.]+) <RISK-MISSION,[^\n]+> mission aborted:"), ["22.6835"])
        check("mission launches", matches(r"^Time: ([\d.]+) <(?:BASIC-MISSION|RISK-MISSION),[^\n]+> mission starting,"), ["8", "20", "32"])
        check("mission success times", matches(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:"), ["10", "34"])
        check("no cancellation", bool(re.search(r"mission cancelle?d", log, flags=re.IGNORECASE)), False)
        check("repair task starts", matches(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> started$"), ["23"])
        check("repair task never completes", matches(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> completed$"), [])
        check("PM objects start", [(float(t), int(a)) for t, a in matches(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,([01])> started$")], [(24.0, 0), (24.0, 1)])
        check("no repair or PM subtask performs", len(matches(r"^Time: [\d.]+  (?:direct repair )?subtask \d+ seqno 1 within system (?:DIRP|PM) task \d+ on <TEACH-AIR-01,[01]> starts performing,")), 0)
        check("zero worker bookings", matches(r"^Time: [\d.]+  <P-MAINT at <BASE-01,0>> allocated to maintenance task:"), [])
        check("healthy PM paused for third mission", matches(r"^Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> system PM task 1 on <TEACH-AIR-01,0> paused\.$"), ["31"])
        check("healthy PM continued after third mission", matches(r"^Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> system PM task 1 on <TEACH-AIR-01,0> continued"), ["34"])
        check("worker availability tests fail", len(matches(r"^  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 failed ?$")), 4)
        system = rows(report, "report", "SystemResults")
        resource = rows(report, "report", "ResourceResults")
        summary = rows(report, "report", "ResultSummary")
        base_system = rows(base_report, "report", "SystemResults")
        base_resource = rows(base_report, "report", "ResourceResults")
        check("72 system/resource bins", (len(system), len(resource)), (72, 72))
        check("aligned half-hour bins", all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2
              for i, r in enumerate(system)), True)
        check("event sums", tuple(sum(r[k] or 0 for r in system) for k in
              ["NFAIL", "NREPT", "NPMS", "NPMT"]), (1, 0, 2, 0))
        check("parent event sums", tuple(sum(r[k] or 0 for r in base_system) for k in
              ["NFAIL", "NREPT", "NPMS", "NPMT"]), (1, 1, 2, 2))
        for field in ["NSYRP", "NSYPM", "NRUM"]:
            rows_here = resource if field == "NRUM" else system
            near(f"zero {field} work hours", sum((r[field] or 0) * .5 for r in rows_here), 0)
        near("zero-worker resource wait hours", sum((r["NRW"] or 0) * .5 for r in resource), 22)
        near("one-worker resource wait hours", sum((r["NRW"] or 0) * .5 for r in base_resource), 5)
        near("failed system resource-wait hours", sum((r["NSYWR"] or 0) * .5 for r in system), 13)
        check("all resource bin quantities zero", {r["NR"] for r in resource}, {0})
        check("terminal one ready and one system waiting", (system[-1]["NSYRY"],
              system[-1]["NSYWR"], system[-1]["NREPT"], system[-1]["NPMT"]), (1, 1, 0, 0))
        check("terminal two resource requests waiting", resource[-1]["NRW"], 2)
        near("mission success fraction remains two thirds", summary[0]["MSUF"], 2 / 3, 1e-6)
    except (OSError, KeyError, ValueError, TypeError, IndexError, StopIteration) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d05-var01-zero-author-validation/v1", "case_id": "D05",
              "variant_id": "D05.var01", "run_id": RUN.name, "parent_run_id": BASE_RUN.name,
              "input_sha256": INPUT_SHA, "parent_input_sha256": PARENT_SHA,
              "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks),
              "checks": checks, "publication_state": "not_published"}
    encoded = (json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n").encode("utf-8")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count")}))
    if not result["passed"]:
        print(json.dumps([c for c in checks if not c["passed"]], default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
