"""Replay the bounded D07.var02 native evidence without changing raw files."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import parse_native, validate as validate_roundtrip

HERE = Path(__file__).resolve().parent
RUN_ID = "d07-var02-dual-opid-v100-ssh-20261003-01"
RUN = HERE / "runs" / RUN_ID


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    tables = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(tables) == 1, name
    table = tables[0]
    return [c["name"] for c in table["columns"]], [r for i in table["instances"] for r in i["rows"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    issues: list[str] = []
    checks = 0

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            issues.append(message)

    contract = load(HERE / "contract.json")
    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    steps = load(RUN / "steps.json")
    roundtrip = validate_roundtrip(RUN)
    check(contract["variant_id"] == "D07.var02", "contract variant")
    check(sha(HERE / "native-input.json") == contract["input_sha256"], "input hash")
    check(sha(HERE.parent / "D02-var01-traditional-op-hours-v1.0.0" / "native-input.json") == contract["parent_input_sha256"], "parent hash")
    check(invocation["session_id"] == 0 and invocation["ssh_connection_present"], "SSH session zero")
    check("sshd.exe" in invocation["ssh_ancestor_names"], "SSH ancestor")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "host queue")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0, "GUI guard")
    check(invocation["input_sha256"] == contract["input_sha256"], "invocation input")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(closure["error"] is None, "closure error")
    check(closure["source_hashes_before"] == closure["source_hashes_after"], "source stable")
    check(len(steps) == 5 and [s["name"] for s in steps] == ["import", "export", "calc", "report", "check_import_export"], "native steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"step {step['name']}")
    check(roundtrip["passed"] and len(roundtrip["populated_tables"]) == 21, "21-table roundtrip")
    for filename, seal in closure["raw"].items():
        path = RUN / filename
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {filename}")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    check(match is not None and match.groups() == ("0", "1", "0"), "conversion counts")
    check(re.findall(r"warning #(\d+)", run_log) == ["108"], "reviewed warning")
    check("Starting simulation" in run_log, "simulation start")
    report_log = (RUN / "report-export.log").read_text(encoding="utf-8-sig", errors="replace")
    check(not re.search(r"could not be loaded|Reverting to default settings|Failed to open file", report_log), "report settings fallback")
    report = parse_native(RUN / "report-raw.json")
    columns, totals = rows(report, "MissionOperationTotalAccumulated")
    check(columns == ["UNID", "MTID", "OPID", "SOACC"], "SOACC total schema")
    achieved = {r[columns.index("OPID")]: r[columns.index("SOACC")] for r in totals}
    check(len(totals) == 2 and achieved == {"OPHOURS": 6, "KM": 360}, "dual accumulated exposure")
    columns, intervals = rows(report, "MissionOperationAccumulated")
    op = {(r[columns.index("STINT")], r[columns.index("ETINT")]): r[columns.index("SOACC")] for r in intervals if r[columns.index("OPID")] == "OPHOURS"}
    km = {(r[columns.index("STINT")], r[columns.index("ETINT")]): r[columns.index("SOACC")] for r in intervals if r[columns.index("OPID")] == "KM"}
    check(len(op) == 120 and len(km) == 104 and set(km).issubset(op), "custom KM grid begins at first mission")
    check(all(abs(value - 60 * op[key]) < 1e-6 for key, value in km.items()), "KM to OPHOURS accumulated ratio")
    check(op[(8, 8.5)] == 0.5 and km[(8, 8.5)] == 30, "first active half-hour")
    columns, system = rows(report, "SystemResults")
    check(len(system) == 120, "system horizon bins")
    observed = {name: sum((r[columns.index(name)] or 0) for r in system) for name in ("NFAIL", "NREPT")}
    result = {
        "schema": "simlox-d07-var02-author-native-replay/v1",
        "run_id": RUN_ID,
        "passed": not issues,
        "checks": checks,
        "issues": issues,
        "source_sha256": contract["input_sha256"],
        "closure_sha256": sha(RUN / "closure.json"),
        "report_sha256": sha(RUN / "report-raw.json"),
        "accumulated_soacc": achieved,
        "observed_system_events": observed,
        "interpretation": "Native dual OPID input accepted with positive KM exposure; one fixed seed does not statistically establish hazard additivity.",
    }
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw)
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
