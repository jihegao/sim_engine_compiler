"""Replay D05.var01 two-worker control against accepted one-worker D05."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D05-maintenance-competition-v1.0.0"
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

ONE_SHA = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
TWO_SHA = "a29857331ed02bf4150c04be71d34a5f84ce66e6e76f1db27bdd94a14320686a"
ONE_RUN = PARENT / "runs" / "d05-pilot-v100-ssh-20260930-03"
TWO_RUN = HERE / "runs" / "d05-var01-two-v100-ssh-20260930-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def values(doc: dict, name: str) -> list[dict]:
    t = table(doc, name)
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols, row, strict=True)) for inst in t["instances"] for row in inst["rows"]]


def report_rows(doc: dict, name: str) -> list[dict]:
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols, row, strict=True)) for inst in t["instances"] for row in inst["rows"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tolerance: float = 3e-5) -> None:
        checks.append({"name": name, "passed": abs(actual - expected) <= tolerance,
                       "actual": actual, "expected": expected, "tolerance": tolerance})

    try:
        parent_source = PARENT / "native-input.json"
        child_source = HERE / "native-input.json"
        contract = read(HERE / "contract.json")
        parent_doc, child_doc = read(parent_source), read(child_source)
        check("accepted parent input SHA", sha(parent_source), ONE_SHA)
        check("child input SHA", sha(child_source), TWO_SHA)
        check("contract source binding", (contract["parent_input_sha256"], contract["input_sha256"]),
              (ONE_SHA, TWO_SHA))
        before = {t["name"]: t for t in parent_doc["model"]["tables"]}
        after = {t["name"]: t for t in child_doc["model"]["tables"]}
        check("same native table names", set(before), set(after))
        check("exact changed table set", {name for name in before if before[name] != after[name]},
              {"ProblemDescription", "Resource", "ResourceAllocation"})
        for name, changed_field in [("ProblemDescription", "PDESC"), ("Resource", "DESCR"),
                                    ("ResourceAllocation", "RQTY")]:
            a, b = values(parent_doc, name), values(child_doc, name)
            check(f"{name} row count", (len(a), len(b)), (1, 1))
            check(f"{name} only field", {key for key in a[0] if a[0][key] != b[0][key]},
                  {changed_field})
        check("sole behavioral change RQTY", (values(parent_doc, "ResourceAllocation")[0]["RQTY"],
              values(child_doc, "ResourceAllocation")[0]["RQTY"]), (1, 2))

        data = {}
        for key, case, run, source_sha, expected_id in [
            ("one", PARENT, ONE_RUN, ONE_SHA, "D05"),
            ("two", HERE, TWO_RUN, TWO_SHA, "D05.var01"),
        ]:
            inv, closure, steps = read(run / "invocation.json"), read(run / "closure.json"), read(run / "steps.json")
            roundtrip = read(run / "roundtrip-validation.json")
            log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
            conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
            report = native(run / "report-raw.json")
            copied, exported = native(run / "input.json"), native(run / "roundtrip-raw.json")
            check(f"{key} copied input SHA", sha(run / "input.json"), source_sha)
            check(f"{key} invocation identity", (inv["case_id"], inv["input_sha256"],
                  inv["session_id"], inv["ssh_connection_present"], inv["gui"]["pid"],
                  inv["queue_mutex"]), (expected_id, source_sha, 0, True, 13340,
                                           "Global\\SimloxIssue18NativeQueue"))
            check(f"{key} sshd ancestor", "sshd.exe" in inv["ssh_ancestor_names"], True)
            check(f"{key} five guarded steps", [(s["name"], s["status"], s["exit_code"],
                  s["gui_preserved"]) for s in steps],
                  [(n, "completed", 0, True) for n in
                   ["import", "export", "calc", "jsonreport", "check_import_export"]])
            check(f"{key} closure no error", closure["error"], None)
            check(f"{key} closure invocation SHA", closure["invocation_sha256"],
                  sha(run / "invocation.json"))
            check(f"{key} sealed sources unchanged", closure["source_hashes_before"],
                  closure["source_hashes_after"])
            for source_name, source_path in {"input": case / "native-input.json",
                                             "parent": PARENT.parent / "D03-calendar-pm-v1.0.0" / "native-input.json" if key == "one" else parent_source,
                                             "contract": case / "contract.json",
                                             "builder": case / "build.py",
                                             "checker": case / "check_roundtrip.py",
                                             "runner_script": case / "run_native_ssh.ps1"}.items():
                check(f"{key} current sealed {source_name}", sha(source_path),
                      closure["source_hashes_before"][source_name])
            for name, record in sorted(closure["raw"].items()):
                check(f"{key} raw {name}", (sha(run / name), (run / name).stat().st_size),
                      (record["sha256"], record["bytes"]))
            check(f"{key} roundtrip passed", roundtrip["passed"], True)
            check(f"{key} roundtrip source rows", (len(roundtrip["populated_tables"]),
                  copied == read(case / "native-input.json")), (22, True))
            populated = lambda doc: {t["name"]: (t["columns"],
                         [row for i in t["instances"] for row in i["rows"]])
                         for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])}
            check(f"{key} exported source rows", all(populated(exported).get(n) == v
                  for n, v in populated(copied).items()), True)
            check(f"{key} conversion", re.findall(r"Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
                  conversion), [("0", "2", "0")])
            check(f"{key} warning IDs", sorted(re.findall(r"warning #(\d+)", conversion)),
                  ["108", "126"])
            data[key] = {"log": log, "system": report_rows(report, "SystemResults"),
                         "resource": report_rows(report, "ResourceResults"),
                         "summary": report_rows(report, "ResultSummary")}

        for key, expected_pm, expected_alloc, expected_release, capacity, wait in [
            ("one", [(28.0, 0), (29.0, 1)], [(23.0, 0), (28.0, 0), (29.0, 0)],
             [(28.0, 1), (29.0, 1), (30.0, 1)], 1, 5),
            ("two", [(24.0, 0), (28.0, 1)], [(23.0, 1), (24.0, 0), (28.0, 1)],
             [(25.0, 1), (28.0, 2), (29.0, 2)], 2, 0),
        ]:
            log, system, resource = data[key]["log"], data[key]["system"], data[key]["resource"]
            matches = lambda pattern: re.findall(pattern, log, flags=re.MULTILINE)
            check(f"{key} one failure", matches(r"^Time: ([\d.]+) <TEACH-AIR-01,1> critical random failure added"), ["22.6835"])
            check(f"{key} aborted risk mission", matches(r"^Time: ([\d.]+) <RISK-MISSION,[^\n]+> mission aborted:"), ["22.6835"])
            check(f"{key} repair work starts", matches(r"^Time: ([\d.]+)  direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,1> starts performing,"), ["23"])
            check(f"{key} repair task ends", matches(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> completed$"), ["28"])
            check(f"{key} PM object starts", [(float(t), int(a)) for t, a in matches(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,([01])> started$")], [(24.0, 0), (24.0, 1)])
            check(f"{key} actual PM work", [(float(t), int(a)) for t, a in matches(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,([01])> starts performing,")], expected_pm)
            check(f"{key} worker bookings", [(float(t), int(q)) for t, q in matches(r"^Time: ([\d.]+)  <P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: ([0-2])$")], expected_alloc)
            check(f"{key} worker releases", [(float(t), int(q)) for t, q in matches(r"^Time: ([\d.]+)  <P-MAINT at <BASE-01,0>> deallocated from  maintenance task: 1  available now: ([0-2])$")], expected_release)
            check(f"{key} mission starts", matches(r"^Time: ([\d.]+) <(?:BASIC-MISSION|RISK-MISSION),[^\n]+> mission starting,"), ["8", "20", "32"])
            check(f"{key} mission successes", matches(r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:"), ["10", "34"])
            check(f"{key} 72 report bins", (len(system), len(resource)), (72, 72))
            check(f"{key} half-hour intervals", all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(resource)), True)
            check(f"{key} event counts", tuple(sum(r[n] or 0 for r in system) for n in
                  ["NFAIL", "NREPT", "NPMS", "NPMT"]), (1, 1, 2, 2))
            for field, expected in [("NSYRP", 5), ("NSYPM", 2)]:
                near(f"{key} {field} aircraft-hours", sum((r[field] or 0) * .5 for r in system), expected)
            near(f"{key} worker used hours", sum((r["NRUM"] or 0) * .5 for r in resource), 7)
            near(f"{key} worker wait hours", sum((r["NRW"] or 0) * .5 for r in resource), wait)
            check(f"{key} peak worker use", max(r["NRUM"] for r in resource), capacity)
            check(f"{key} terminal availability", (system[-1]["NSYRY"], resource[-1]["NRA"]), (2, capacity))
            near(f"{key} mission success fraction", data[key]["summary"][0]["MSUF"], 2 / 3, 1e-6)
        check("two-worker PM overlaps repair", all(abs(actual - expected) < 3e-5 for actual, expected in [
              (data["two"]["system"][48]["NSYRP"], 1),
              (data["two"]["system"][48]["NSYPM"], 1),
              (data["two"]["resource"][48]["NRUM"], 2)]), True)
    except (OSError, KeyError, ValueError, TypeError, IndexError, StopIteration) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d05-var01-pair-author-validation/v1",
              "case_id": "D05", "variant_id": "D05.var01", "parent_run_id": ONE_RUN.name,
              "child_run_id": TWO_RUN.name, "parent_input_sha256": ONE_SHA, "child_input_sha256": TWO_SHA,
              "passed": all(c["passed"] for c in checks), "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks), "checks": checks,
              "publication_state": "not_published"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n").encode("utf-8")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    print(json.dumps({k: result[k] for k in ("case_id", "variant_id", "passed", "passed_count", "failed_count")}))
    if not result["passed"]:
        print(json.dumps([x for x in checks if not x["passed"]], default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
