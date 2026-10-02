"""Author replay for a bounded continuous-mission DAMP converter rejection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from build import HERE, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, validate as validate_roundtrip

RUNS = {
    "control": HERE / "runs/h01-var03-control-v100-ssh-20261002-01",
    "damp": HERE / "runs/h01-var03-damp-v100-ssh-20261002-01",
}
SOURCE_HASHES = {
    "control": PARENT_SHA,
    "damp": "c61974ba269c15afe3e39e76f396d503b08e522b3b97bbad8125e44c3a02071a",
}
CONTRACT_SHA = "2c5842685f35b96be402d93490f4fdc3b0e3e90e92bca0ae7bc0f24c556f75b9"
DIFF_SHA = "50c9b248de8874f911967288aedfd0e46e4d17dd5e6cf59e41f6b906ac5654f2"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
INSTALL_HASHES = {
    "manual": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
    "dictionary": "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0",
    "simlox_exe": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
}
RAW_NAMES = {
    "control": {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
                "run.log", "model.sxo", "model.log", "report-raw.json", "report-export.log",
                "roundtrip-validation.json", "steps.json"},
    "damp": {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
             "run.log", "model.sxo", "roundtrip-validation.json", "steps.json"},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_table(report: dict, name: str) -> tuple[list[str], list[list]]:
    tables = [t for t in report["report"]["tables"] if t["name"] == name]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1:
        raise ValueError(f"missing/duplicate report table {name}")
    table = tables[0]
    return [c["name"] for c in table["columns"]], table["instances"][0]["rows"]


def main() -> None:
    checks: list[dict] = []

    def check(name: str, truth: bool, detail: object = None) -> None:
        checks.append({"name": name, "passed": bool(truth), "detail": None if truth else detail})

    check("accepted_parent_sha", sha(PARENT) == PARENT_SHA)
    check("contract_sha", sha(HERE / "contract.json") == CONTRACT_SHA)
    check("exact_diff_sha", sha(HERE / "exact-diff.json") == DIFF_SHA)
    for name, path in (("manual", MANUAL), ("dictionary", DICTIONARY), ("simlox_exe", EXE)):
        check(f"installed_{name}_sha", sha(path) == INSTALL_HASHES[name])
    for arm, run in RUNS.items():
        source = HERE / f"{arm}-input.json"
        check(f"{arm}.source_sha", sha(source) == SOURCE_HASHES[arm])
        check(f"{arm}.builder", source.read_bytes() == build(arm))
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        check(f"{arm}.identity", invocation["run_id"] == closure["run_id"] == run.name and
              invocation["variant"] == arm and invocation["case_id"] == "H01")
        check(f"{arm}.session_ssh", invocation["session_id"] == 0 and
              invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"])
        gui = invocation["gui"]
        check(f"{arm}.gui_queue", gui["pid"] == 13340 and gui["session_id"] == 1 and
              gui["start_utc"] == "2026-09-28T10:09:56.8261381Z" and
              invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        before, after = closure["source_hashes_before"], closure["source_hashes_after"]
        check(f"{arm}.source_seal", before == after and before["input"] == SOURCE_HASHES[arm] and
              before["parent"] == PARENT_SHA and before["contract"] == CONTRACT_SHA and
              before["exact_diff"] == DIFF_SHA and
              all(before[key] == value for key, value in INSTALL_HASHES.items()) and
              before["runner_script"] == sha(HERE / "run_native_ssh.ps1") and
              before["builder"] == sha(HERE / "build.py") and
              before["checker"] == sha(HERE / "check_roundtrip.py") and
              before["diff_checker"] == sha(HERE / "describe_diff.py"))
        check(f"{arm}.invocation_seal", closure["invocation_sha256"] == sha(run / "invocation.json") and
              invocation["source_hashes_before"] == before and invocation["input_sha256"] == SOURCE_HASHES[arm])
        raw = closure["raw"]
        check(f"{arm}.raw_names", set(raw) == RAW_NAMES[arm])
        for name, seal in raw.items():
            path = run / name
            check(f"{arm}.raw.{name}", path.is_file() and path.stat().st_size == seal["bytes"] and
                  sha(path) == seal["sha256"])
        check(f"{arm}.closure_error", closure["error"] is None)
        expected_steps = ["import", "export", "calc"] + (["jsonreport"] if arm == "control" else []) + ["check_import_export"]
        check(f"{arm}.step_names", [step["name"] for step in steps] == expected_steps)
        for step in steps:
            check(f"{arm}.step.{step['name']}", step["exit_code"] == 0 and step["gui_preserved"] and
                  step["status"] == ("calc_observed" if step["name"] == "calc" else "completed"))
        roundtrip = validate_roundtrip(run)
        check(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
              len(roundtrip["populated_tables"]) == (13 if arm == "control" else 16) and
              load(run / "roundtrip-validation.json") == roundtrip)
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
                               (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
        check(f"{arm}.converter_summary", conversion is not None)
        if arm == "control":
            check("control.zero_errors", conversion is not None and conversion.groups() == ("0", "2", "0"))
            check("control.valid_sxo_report", (run / "model.sxo").stat().st_size > 4 and
                  (run / "report-raw.json").stat().st_size > 4)
            log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
            check("control.mission_events", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and
                  "Time: 12 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and
                  "Time: 12 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and
                  "BATTLE-LOSS" not in log)
            report = parse_native(run / "report-raw.json")
            sc, sr = report_table(report, "SystemResults")
            tc, tr = report_table(report, "StockTotalResults")
            check("control.bins", len(sr) == len(tr) == 32 and
                  all(a[sc.index("STINT")] == b[tc.index("STINT")] and
                      a[sc.index("ETINT")] == b[tc.index("ETINT")] for a, b in zip(sr, tr, strict=True)))
            operating = sum((row[sc.index("ETINT")] - row[sc.index("STINT")]) * row[sc.index("NSYMO")] for row in sr)
            check("control.system_ledger", abs(operating - 8) < 1e-8 and
                  sr[-1][sc.index("NSYRY")] == 2 and
                  all(row[sc.index("NFAIL")] == row[sc.index("NDAM")] == row[sc.index("NSYLA")] == 0 for row in sr))
            check("control.stock_ledger", all(row[tc.index("NBO")] == 0 and row[tc.index("PNB")] == 1 for row in tr))
        else:
            child_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
            check("damp.relevant_error", conversion is not None and conversion.groups() == ("1", "2", "0") and
                  "(error #252) DAMP is not allowed for continuous or extendable type of missions" in child_log)
            check("damp.no_simulation_output", (run / "model.sxo").stat().st_size == 4 and
                  not (run / "report-raw.json").exists() and not (run / "model.log").exists())
    result = {"schema": "simlox-h01-var03-author-validation/v1", "case_id": "H01",
              "variant_id": "H01.var03", "passed": all(item["passed"] for item in checks),
              "checks_passed": sum(item["passed"] for item in checks), "checks_total": len(checks),
              "failures": [item for item in checks if not item["passed"]], "checks": checks,
              "scope": "bounded converter rejection only", "publication_state": "not_published"}
    path = HERE / "author-validation.json"
    raw = (json.dumps(result, indent=2) + "\n").encode()
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("frozen author validation differs")
    if not path.exists():
        path.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "checks": f"{result['checks_passed']}/{result['checks_total']}",
                      "failures": result["failures"], "sha256": sha(path)}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
