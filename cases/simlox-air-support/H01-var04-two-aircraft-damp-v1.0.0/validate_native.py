"""Author replay of one fixed two-aircraft DAMP occurrence probe."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from build import HERE, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, validate as validate_roundtrip

RUNS = {
    "control": HERE / "runs/h01-var04-control-v100-ssh-20261002-01",
    "damp": HERE / "runs/h01-var04-damp-v100-ssh-20261002-01",
}
SOURCE_HASHES = {
    "control": PARENT_SHA,
    "damp": "ca7ce1a2493631202c7c1ee4e5f7e3a5fe2c765b0d016bf47fbdd2751921f28c",
}
CONTRACT_SHA = "67b0ff49e79f9a16a920fbc5e26b280f9a952f277a9ea35ac2f6b95c2ccd6d7e"
DIFF_SHA = "fedbb7381a16d7938316a765bbad7dd723628866c57c39c2c8c54b886b4c79af"
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
START, END = 8.0, 10.0
EVENT = re.compile(r"^Time: ([0-9.]+) <TEACH-AIR-01,([01])>Damage BATTLE-HIT occured\. Damaged items: *$")


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
        check(f"{arm}.mission", all(
            any(line.startswith(f"Time: {time:g} <BASIC-MISSION,") and phrase in line
                for line in log.splitlines())
            for time, phrase in ((START, " mission starting,"), (END, " mission success:"),
                                 (END, " mission completed:"))))
        check(f"{arm}.formation", "mission activated, systems requested: 2" in log and
              "mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log and
              all(f"System arrives <TEACH-AIR-01,{i}>, mission success" in log for i in (0, 1)))
        check(f"{arm}.no_attrition_abort", "subject to attrition" not in log and
              "mission aborted" not in log and "mission cancelled" not in log)
        events[arm] = [(float(match.group(1)), int(match.group(2)))
                       for line in log.splitlines() if (match := EVENT.match(line))]
        if arm == "control":
            check("control.no_damage", not events[arm] and "Damage " not in log)
        else:
            check("damp.one_per_aircraft", len(events[arm]) == 2 and
                  sorted(i for _, i in events[arm]) == [0, 1], events[arm])
            check("damp.in_flight", all(START < t < END for t, _ in events[arm]))
            check("damp.distinct_times", len({t for t, _ in events[arm]}) == 2)
            check("damp.no_other_damage", log.count("Damage ") == 2)
        reports[arm] = parse_native(run / "report-raw.json")
        sc, sr = report_table(reports[arm], "SystemResults")
        tc, tr = report_table(reports[arm], "StockTotalResults")
        rc, rr = report_table(reports[arm], "ResultSummary")
        check(f"{arm}.bins", len(sr) == len(tr) == 72 and all(
            a[sc.index("STINT")] == b[tc.index("STINT")] and
            a[sc.index("ETINT")] == b[tc.index("ETINT")] for a, b in zip(sr, tr, strict=True)))
        op_hours = sum((r[sc.index("ETINT")] - r[sc.index("STINT")]) * r[sc.index("NSYMO")] for r in sr)
        check(f"{arm}.system_ledger", abs(op_hours - 4) < 1e-8 and
              sr[-1][sc.index("NSYRY")] == 2 and
              all(r[sc.index("NSYLA")] == r[sc.index("NFAIL")] == 0 for r in sr))
        check(f"{arm}.stock_ledger", all(r[tc.index("NBO")] == 0 and r[tc.index("PNB")] == 1 for r in tr))
        check(f"{arm}.summary", len(rr) == 1 and rr[0][rc.index("MSTF")] == 1 and rr[0][rc.index("MSUF")] == 1)
    cs, cr = report_table(reports["control"], "SystemResults")
    rs, rr = report_table(reports["damp"], "SystemResults")
    check("aligned_system_columns", cs == rs)
    expected_bins = Counter(int(t * 2) for t, _ in events["damp"])
    check("damp.ndam_event_bins", all(row[rs.index("NDAM")] == expected_bins.get(i, 0) for i, row in enumerate(rr)))
    check("control.ndam_zero", all(row[cs.index("NDAM")] == 0 for row in cr))
    other_columns = [i for i, field in enumerate(cs) if field != "NDAM"]
    check("system_only_ndam_diff", all(a[i] == b[i] for a, b in zip(cr, rr, strict=True) for i in other_columns))
    for name in ("ResultSummary", "StockTotalResults"):
        control_cols, control_rows = report_table(reports["control"], name)
        damp_cols, damp_rows = report_table(reports["damp"], name)
        check(f"{name}.identical", control_cols == damp_cols and control_rows == damp_rows)
    result = {"schema": "simlox-h01-var04-author-validation/v1", "case_id": "H01", "variant_id": "H01.var04",
              "passed": all(c["passed"] for c in checks),
              "checks_passed": sum(c["passed"] for c in checks), "checks_total": len(checks),
              "failures": [c for c in checks if not c["passed"]], "checks": checks,
              "observed_damp_events": events["damp"],
              "scope": "one fixed-seed two-aircraft DAMP=1 no-consequence occurrence panel", "publication_state": "not_published"}
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
