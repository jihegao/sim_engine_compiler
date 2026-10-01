"""Replay one J04.var02 native confidence-stop run."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_native as native  # noqa: E402
import build_256 as build  # noqa: E402

RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log",
       "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def validate(run: Path) -> dict:
    errors: list[str] = []
    contract = load(HERE / "contract.json")
    expected = contract["expected_observation"]
    if run.name not in expected["run_ids"]:
        errors.append("run identity")
    for name in RAW | {"invocation.json", "closure.json"}:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing or empty artifact: {name}")
    if errors:
        return {"passed": False, "differences": errors}
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    if (invocation.get("schema"), invocation.get("run_id")) != ("simlox-j04-var02-confidence-stop-invocation/ssh-cli-v1", run.name):
        errors.append("invocation schema/identity")
    if (closure.get("schema"), closure.get("run_id"), closure.get("state")) != ("simlox-j04-var02-confidence-stop-closure/v1", run.name, "native_steps_complete"):
        errors.append("closure schema/identity/state")
    if invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
        errors.append("session-0 SSH ancestry")
    if invocation.get("gui_pid") != 13340 or invocation.get("gui_start_utc") != "2026-09-28T10:09:56.8261381Z" or invocation.get("queue_mutex") != "Global\\SimloxIssue18NativeQueue":
        errors.append("preserved GUI/mutex identity")
    if sha(run / "input.json") != contract["input_sha256"] or invocation.get("input_sha256") != contract["input_sha256"]:
        errors.append("input fingerprint")
    if closure.get("invocation_sha256") != sha(run / "invocation.json") or set(closure.get("raw", {})) != RAW:
        errors.append("invocation/raw file set")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw seal: {name}")
    source_paths = {
        "contract.json": HERE / "contract.json", "build_256.py": HERE / "build_256.py",
        "probe256-diff.json": HERE / "probe256-diff.json", "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
        "validate.py": HERE / "validate.py", "validate_pair.py": HERE / "validate_pair.py",
        "probe256-input.json": HERE / "probe256-input.json", "parent-input.json": build.PARENT,
        "database-dictionary.txt": Path(contract["source"]["database_dictionary"]),
        "manual.pdf": Path(contract["source"]["manual"]),
    }
    if set(closure.get("post_source_sha256", {})) != set(source_paths):
        errors.append("source file set")
    for name, path in source_paths.items():
        if closure.get("post_source_sha256", {}).get(name) != sha(path):
            errors.append(f"source seal: {name}")
    for field, source in (("contract_sha256", "contract.json"), ("builder_sha256", "build_256.py"),
                          ("validator_sha256", "validate.py"), ("pair_validator_sha256", "validate_pair.py"),
                          ("runner_sha256", "run_native_ssh.ps1")):
        if invocation.get(field) != sha(source_paths[source]):
            errors.append(f"invocation source: {field}")
    source, diff = build.build()
    if (HERE / "probe256-input.json").read_bytes() != source or (HERE / "probe256-diff.json").read_bytes() != diff:
        errors.append("builder output")
    if sha(HERE / "probe256-diff.json") != contract["exact_diff_sha256"]:
        errors.append("exact diff fingerprint")
    original, exported = load(run / "input.json"), load(run / "roundtrip-raw.json")
    for label, document in (("source", original), ("export", exported)):
        control = build.rows(build.table(document, "Control"))
        if len(control) != 1 or control[0].get("NREPS") != 256 or control[0].get("TCLEV") != 0.09 or control[0].get("RSEED") != "1" or control[0].get("ENLOG") != "Y":
            errors.append(f"{label} control")
    roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append("business roundtrip")
    steps = load(run / "steps.json")
    if [step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"] or any(
        step.get("exit_code") != 0 or step.get("coexisting_gui_present_after") is not True for step in steps
    ):
        errors.append("native steps/GUI")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", log))
    if conversion is None or int(conversion[1]) != 0 or warnings != Counter({"108": 1, "211": 1, "126": 1}):
        errors.append("converter summary/warnings")
    parent_log = ROOT / "J04-var01-fixed-replications-v1.0.0/runs/j04-var01-fixed-reps-accepted-20261001-03/model.log"
    if (run / "model.log").read_bytes() != parent_log.read_bytes():
        errors.append("first-replication ENLOG differs from accepted parent")
    report = load(run / "report-raw.json")
    summary = native.table_rows(report, "ResultSummary")
    if len(summary) != 1 or any(summary[0].get(key) != value for key, value in {
        "NREP": expected["actual_nrep"], "RTILW": 0, "RTIUP": 36,
        **{key: expected["mtmf"] for key in ("MTMF", "MSTF", "MSUF", "STMF")},
        **{key: expected["rsmtmf"] for key in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")}
    }.items()):
        errors.append("ResultSummary")
    system = native.table_rows(report, "SystemResults")
    stock = native.table_rows(report, "StockTotalResults")
    if len(system) != 72 or len(stock) != 72:
        errors.append("72-bin System/Stock report")
    flight_hours = 0.0
    for index, row in enumerate(system):
        operating = expected["mean_operating_aircraft_at_hour_8"] if 16 <= index < 20 else 0
        assigned = expected["mean_operating_aircraft_at_hour_8"] if 14 <= index < 20 else 0
        if row.get("STINT") != index * 0.5 or row.get("ETINT") != (index + 1) * 0.5 or row.get("NSYA") != 12:
            errors.append(f"system bin bounds/capacity {index}")
        if row.get("NSYMO") != operating or row.get("NSYMA") != assigned or abs(float(row.get("NSYRY") or 0) - (12 - assigned)) > 1e-5:
            errors.append(f"system bin occupancy {index}")
        if any(row.get(key) != 0 for key in ("NFAIL", "NPMT", "NSYMC", "NSYMT", "NSYMS")):
            errors.append(f"unrelated mechanism in system bin {index}")
        flight_hours += float(row.get("NSYMO") or 0) * 0.5
    for index, row in enumerate(stock):
        if row.get("STINT") != index * 0.5 or row.get("ETINT") != (index + 1) * 0.5:
            errors.append(f"stock bin bounds {index}")
        if any(row.get(key) != 0 for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
            errors.append(f"stock demand {index}")
    if abs(flight_hours - expected["mean_aircraft_flight_hours"]) > 1e-6 or system[-1].get("NSYRY") != 12 or system[-1].get("NSYMA") != 0:
        errors.append("average flight integral/terminal state")
    return {
        "schema": "simlox-j04-var02-confidence-stop-run-validation/v1",
        "case_id": "J04", "variant_id": "J04.var02", "version": "1.0.0",
        "run_id": run.name, "passed": not errors, "differences": errors,
        "nrep": summary[0].get("NREP") if summary else None,
        "rsmtmf": summary[0].get("RSMTMF") if summary else None,
        "average_aircraft_flight_hours": flight_hours,
        "roundtrip": roundtrip, "publication_state": "not_published",
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate.py RUN_DIRECTORY")
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
