"""Replay the sealed D13.var01 local PM activation profile and D03 control."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d03-calendar-v100-ssh-20261001-02"
INPUT_SHA = "f4fce5c8f362be817264544f22f271c1ee47b6e635e871619525fa1c8545ca70"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
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
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for i in table["instances"] for row in i["rows"]]


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
        parent_path, child_path = PARENT / "native-input.json", HERE / "native-input.json"
        parent, child = read(parent_path), read(child_path)
        contract = read(HERE / "contract.json")
        invocation, closure, steps = (read(run / n) for n in
                                       ["invocation.json", "closure.json", "steps.json"])
        roundtrip = read(run / "roundtrip-validation.json")
        copied, exported, report = (native(run / n) for n in
                                    ["input.json", "roundtrip-raw.json", "report-raw.json"])
        parent_report = native(PARENT_RUN / "report-raw.json")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")

        check("accepted D03 parent SHA", sha(parent_path), PARENT_SHA)
        check("frozen child SHA", sha(child_path), INPUT_SHA)
        check("copied input SHA", sha(run / "input.json"), INPUT_SHA)
        check("contract source binding", (contract["parent_input_sha256"], contract["input_sha256"]),
              (PARENT_SHA, INPUT_SHA))
        check("contract variant and state", (contract["variant_id"], contract["publication_state"]),
              ("D13.var01", "not_published"))
        p_tables = {t["name"]: t for t in parent["model"]["tables"]}
        c_tables = {t["name"]: t for t in child["model"]["tables"]}
        check("parent table set retained", set(p_tables).issubset(c_tables), True)
        check("exact added tables", set(c_tables) - set(p_tables),
              {"PMActivation", "PMActivationProfile"})
        check("only parent description changes", {n for n in p_tables if p_tables[n] != c_tables[n]},
              {"ProblemDescription"})
        check("global PM remains on", rows(child, "model", "Control")[0]["ENPM"], "Y")
        check("local activation row", rows(child, "model", "PMActivation"),
              [{"USTID": "TEACH-UNIT", "PMID": "CAL24", "ENPM": "Y", "CRIT": "Y",
                "PRID": "PM-SWITCH", "NOTE": None}])
        check("off/on profile", [(r["PRID"], r["SPRID"], r["STIM"], r["ETIM"],
              r["ENPM"], r["CRIT"]) for r in rows(child, "model", "PMActivationProfile")],
              [("PM-SWITCH", "<LIMIT>", 0, 30, "N", "Y"),
               ("PM-SWITCH", "<LIMIT>", 30, 60, "Y", "Y")])
        check("copied model equals source", copied, child)
        def populated(doc: dict) -> dict:
            return {t["name"]: (t["columns"],
                    [row for i in t["instances"] for row in i["rows"]])
                    for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])}
        source_tables, export_tables = populated(copied), populated(exported)
        check("20 source row-containing tables roundtrip", len(source_tables) == 20 and
              all(export_tables.get(n) == v for n, v in source_tables.items()), True)
        check("roundtrip checker", (roundtrip["passed"], roundtrip["differences"]), (True, []))
        check("invocation identity", (invocation["case_id"], invocation["input_sha256"],
              invocation["parent_sha256"], invocation["session_id"],
              invocation["ssh_connection_present"], invocation["gui"]["pid"],
              invocation["queue_mutex"]),
              ("D13.var01", INPUT_SHA, PARENT_SHA, 0, True, 13340,
               "Global\\SimloxIssue18NativeQueue"))
        check("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("five guarded native steps", [(s["name"], s["status"], s["exit_code"],
              s["gui_preserved"]) for s in steps],
              [(n, "completed", 0, True) for n in
               ["import", "export", "calc", "jsonreport", "check_import_export"]])
        check("closure no error", closure["error"], None)
        check("closure invocation SHA", closure["invocation_sha256"], sha(run / "invocation.json"))
        check("sealed sources stable", closure["source_hashes_before"], closure["source_hashes_after"])
        for name, path in {"input": child_path, "parent": parent_path,
                           "contract": HERE / "contract.json", "builder": HERE / "build.py",
                           "checker": HERE / "check_roundtrip.py",
                           "runner_script": HERE / "run_native_ssh.ps1"}.items():
            check(f"sealed current {name}", sha(path), closure["source_hashes_before"][name])
        for name, sealed in sorted(closure["raw"].items()):
            check(f"raw {name}", (sha(run / name), (run / name).stat().st_size),
                  (sealed["sha256"], sealed["bytes"]))
        check("conversion result", re.findall(r"Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
              conversion), [("0", "2", "0")])
        check("warning IDs", sorted(re.findall(r"warning #(\d+)", conversion)), ["108", "126"])
        check("native error IDs", re.findall(r"error #(\d+)", conversion), [])

        def times(pattern: str, source: str) -> list[float]:
            return [float(x) for x in re.findall(pattern, source, flags=re.MULTILINE)]

        pm_start = r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"
        pm_finish = r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"
        pm_work = r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing,"
        mission_start = r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission starting,"
        mission_success = r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:"
        check("D03 parent PM starts", times(pm_start, parent_log), [24, 49])
        check("child PM starts", times(pm_start, log), [30, 55])
        check("child PM work starts", times(pm_work, log), [30, 55])
        check("child PM completes", times(pm_finish, log), [31, 56])
        check("no PM before enable", all(t >= 30 for t in times(pm_start, log)), True)
        check("parent mission starts", times(mission_start, parent_log), [8, 20, 32])
        check("child mission starts", times(mission_start, log), [8, 20, 32])
        check("child mission successes", times(mission_success, log), [10, 22, 34])
        check("child no mission abort/cancel", bool(re.search(r"mission (?:aborted|cancelled|canceled)", log)), False)
        check("child no failure", "critical random failure added" in log, False)
        system = rows(report, "report", "SystemResults")
        parent_system = rows(parent_report, "report", "SystemResults")
        check("120 parent half-hour bins", len(parent_system), 120)
        check("120 child half-hour bins", len(system), 120)
        check("child intervals", [(r["STINT"], r["ETINT"]) for r in system],
              [(i / 2, (i + 1) / 2) for i in range(120)])
        for field, expected in {"NFAIL": 0, "NREPT": 0, "NPMS": 2, "NPMT": 2}.items():
            check(f"child {field} sum", sum(r[field] or 0 for r in system), expected)
        for field, expected in {"NSYPM": 2, "NSYMO": 6}.items():
            near(f"child {field} aircraft-hours", sum((r[field] or 0) *
                 (r["ETINT"] - r["STINT"]) for r in system), expected)
        check("no PM occupancy before hour30", all((r["NSYPM"] or 0) == 0
              for r in system if r["ETINT"] <= 30), True)
        check("terminal aircraft ready", (system[-1]["NSYRY"], system[-1]["NSYPM"]), (1, 0))
        check("summary all missions succeed", rows(report, "report", "ResultSummary")[0]["MSUF"], 1)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d13-var01-activation-v100-author-validation/v1",
              "case_id": "D13", "variant_id": "D13.var01", "run_id": run.name,
              "input_sha256": INPUT_SHA, "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks), "checks": checks,
              "scope": "fixed_local_pm_activation_off_0_30_on_30_60_cli",
              "publication_state": "not_published"}
    encoded = (json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n").encode("utf-8")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    print(json.dumps({k: result[k] for k in ("run_id", "passed", "passed_count", "failed_count")}))
    if not result["passed"]:
        print(json.dumps([c for c in checks if not c["passed"]], default=str), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
