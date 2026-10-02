"""Author replay of one fixed-seed intermediate DAMP probe."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from build import HERE, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, validate as validate_roundtrip

RUNS = {
    "control": HERE / "runs/h01-var01-intermediate-control-v100-ssh-20261002-01",
    "intermediate": HERE / "runs/h01-var01-intermediate-child-v100-ssh-20261002-01",
}
SOURCE_HASHES = {
    "control": PARENT_SHA,
    "intermediate": "0c01a03883341e58239bbf5f69b0486e03c6a59f2dc1d8aa18a4941361858d91",
}
CONTRACT_SHA = "68448f0445ef611dfbb63e72ae387915d21e521eacdd27e17ed6368e9011ec7c"
DIFF_SHA = "f0d1d4844c66b0d9a7cfd248bbee91153c020c8f7dba130984f21a6035e73838"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
INSTALL_HASHES = {
    "manual": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
    "dictionary": "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0",
    "simlox_exe": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
}
RAW_NAMES = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
             "run.log", "model.sxo", "model.log", "report-raw.json", "report-export.log",
             "roundtrip-validation.json", "steps.json"}
STARTS = (8.0, 20.0, 32.0)
ENDS = (10.0, 22.0, 34.0)
EVENT = re.compile(r"^Time: ([0-9.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: *$")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_table(report: dict, name: str) -> tuple[list[str], list[list]]:
    matches = [t for t in report["report"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"missing/duplicate report table {name}")
    table = matches[0]
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
    reports, events = {}, {}
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
        check(f"{arm}.raw_names", set(raw) == RAW_NAMES)
        for name, seal in raw.items():
            path = run / name
            check(f"{arm}.raw.{name}", path.is_file() and path.stat().st_size == seal["bytes"] and
                  sha(path) == seal["sha256"])
        check(f"{arm}.closure_error", closure["error"] is None)
        check(f"{arm}.step_names", [s["name"] for s in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"])
        for step in steps:
            check(f"{arm}.step.{step['name']}", step["exit_code"] == 0 and step["gui_preserved"] and
                  step["status"] == ("calc_observed" if step["name"] == "calc" else "completed"))
        roundtrip = validate_roundtrip(run)
        check(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
              len(roundtrip["populated_tables"]) == (13 if arm == "control" else 16) and
              load(run / "roundtrip-validation.json") == roundtrip)
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
                               (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
        check(f"{arm}.converter", conversion is not None and conversion.groups() == ("0", "2", "0") and
              (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        for start, end in zip(STARTS, ENDS, strict=True):
            check(f"{arm}.mission.{start:g}",
                  any(line.startswith(f"Time: {start:g} <BASIC-MISSION,") and " mission starting," in line for line in log.splitlines()) and
                  any(line.startswith(f"Time: {end:g} <BASIC-MISSION,") and " mission success:" in line for line in log.splitlines()) and
                  any(line.startswith(f"Time: {end:g} <BASIC-MISSION,") and " mission completed:" in line for line in log.splitlines()))
        check(f"{arm}.no_attrition_abort", "subject to attrition" not in log and
              "mission aborted" not in log and "mission cancelled" not in log)
        events[arm] = [float(match.group(1)) for line in log.splitlines() if (match := EVENT.match(line))]
        if arm == "control":
            check("control.no_damage", not events[arm] and "Damage " not in log)
        else:
            counts = [sum(start < t < end for t in events[arm]) for start, end in zip(STARTS, ENDS, strict=True)]
            check("intermediate.mixed", 1 <= len(events[arm]) <= 2 and
                  0 in counts and 1 in counts, {"times": events[arm], "counts": counts})
            check("intermediate.inside_missions", all(any(start < t < end for start, end in zip(STARTS, ENDS, strict=True)) for t in events[arm]))
            check("intermediate.at_most_one_per_mission", max(counts) <= 1)
            check("intermediate.no_other_damage", log.count("Damage ") == len(events[arm]))
        reports[arm] = parse_native(run / "report-raw.json")
        sc, sr = report_table(reports[arm], "SystemResults")
        tc, tr = report_table(reports[arm], "StockTotalResults")
        rc, rr = report_table(reports[arm], "ResultSummary")
        check(f"{arm}.bins", len(sr) == len(tr) == 72 and all(
            a[sc.index("STINT")] == b[tc.index("STINT")] and
            a[sc.index("ETINT")] == b[tc.index("ETINT")] for a, b in zip(sr, tr, strict=True)))
        op_hours = sum((r[sc.index("ETINT")] - r[sc.index("STINT")]) * r[sc.index("NSYMO")] for r in sr)
        check(f"{arm}.system_ledger", abs(op_hours - 6) < 1e-8 and
              sr[-1][sc.index("NSYRY")] == 1 and
              all(r[sc.index("NSYLA")] == r[sc.index("NFAIL")] == 0 for r in sr))
        check(f"{arm}.stock_ledger", all(r[tc.index("NBO")] == 0 and r[tc.index("PNB")] == 1 for r in tr))
        check(f"{arm}.summary", len(rr) == 1 and rr[0][rc.index("MSTF")] == 1 and rr[0][rc.index("MSUF")] == 1)
    cs, cr = report_table(reports["control"], "SystemResults")
    rs, rr = report_table(reports["intermediate"], "SystemResults")
    check("aligned_system_columns", cs == rs)
    expected_bins = Counter(int(t * 2) for t in events["intermediate"])
    check("intermediate.ndam_event_bins", all(row[rs.index("NDAM")] == expected_bins.get(i, 0) for i, row in enumerate(rr)))
    check("control.ndam_zero", all(row[cs.index("NDAM")] == 0 for row in cr))
    other_columns = [i for i, field in enumerate(cs) if field != "NDAM"]
    check("system_only_ndam_diff", all(a[i] == b[i] for a, b in zip(cr, rr, strict=True) for i in other_columns))
    for name in ("ResultSummary", "StockTotalResults"):
        control_cols, control_rows = report_table(reports["control"], name)
        child_cols, child_rows = report_table(reports["intermediate"], name)
        check(f"{name}.identical", control_cols == child_cols and control_rows == child_rows)
    result = {"schema": "simlox-h01-var01-intermediate-author-validation/v1", "case_id": "H01", "variant_id": "H01.var01",
              "passed": all(c["passed"] for c in checks),
              "checks_passed": sum(c["passed"] for c in checks), "checks_total": len(checks),
              "failures": [c for c in checks if not c["passed"]], "checks": checks,
              "observed_intermediate_event_times": events["intermediate"],
              "scope": "one fixed-seed DAMP=0.5 mixed-occurrence no-consequence panel", "publication_state": "not_published"}
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
