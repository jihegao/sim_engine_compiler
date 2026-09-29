"""Read-only, source-bound B02 1.0.2 native behavior validation."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402
import build  # noqa: E402

CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
INPUT_HASH = CONTRACT["input_sha256"]
RAW_FILES = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo",
             "import.log", "export.log", "run.log", "model.log", "report-raw.json",
             "report-export.log", "steps.json"}
TIME = re.compile(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def model_rows(document: dict, name: str) -> list[dict]:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"missing or duplicate {name} model table")
    names = [column["name"] for column in found[0]["columns"]]
    return [dict(zip(names, row, strict=True)) for row in found[0]["instances"][0]["rows"]]


def event_rows(raw: str) -> list[dict]:
    result = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        found = TIME.match(line)
        if found:
            result.append({"line": line_number, "hour": float(found[1]), "body": found[2].strip()})
    return result


def check_events(raw: str) -> list[str]:
    events = event_rows(raw)
    expected = CONTRACT["expected_native"]
    tag = expected["mission_tag"]
    owner = expected["aircraft_instance"]
    checks = {
        "notice": (" mission ordered:", [(7, "<TEACH-UNIT> mission ordered: BASIC-MISSION")]),
        "created": (" mission created:", [(7, f"{tag} mission created:")]),
        "allocated": (" mission allocates system:", [(7, f"{tag} mission allocates system: {owner}")]),
        "prep_start": (" preparation started,", [(7, f"{owner} preparation started, mission: {tag}")]),
        "prep_end": (" preparation ended,", [(7.5, f"{owner} preparation ended, mission: {tag}")]),
        "task_start": ("system preparation task 0 on", [(7, f"system preparation task 0 on {owner} started"),
                                                              (7.5, f"system preparation task 0 on {owner} completed")]),
        "launch": (" mission starting, duration:", [(8, f"{tag} mission starting, duration: 2 : {owner}")]),
        "success": (" mission success:", [(10, f"{tag} mission success:")]),
        "completion": (" mission completed:", [(10, f"{tag} mission completed: {owner}")]),
        "cancel": (" mission cancelled:", []),
        "abort": (" mission aborted:", []),
    }
    errors = []
    for label, (marker, wanted) in checks.items():
        if label == "task_start":
            actual = [(row["hour"], row["body"]) for row in events if re.fullmatch(
                r"system preparation task \d+ on <[^>]+> (?:started|completed)", row["body"])]
        else:
            actual = [(row["hour"], row["body"]) for row in events if marker in row["body"]]
        if len(actual) != len(wanted) or any(abs(a[0] - w[0]) > 1e-4 or a[1] != w[1]
                                             for a, w in zip(actual, wanted)):
            errors.append(f"{label}: expected {wanted!r}; observed {actual!r}")
    if any(events[i]["hour"] > events[i + 1]["hour"] + 1e-9 for i in range(len(events) - 1)):
        errors.append("event timestamps are not monotonic")
    prep_end = [row["line"] for row in events if " preparation ended," in row["body"]]
    launch = [row["line"] for row in events if " mission starting, duration:" in row["body"]]
    if len(prep_end) != 1 or len(launch) != 1 or prep_end[0] >= launch[0]:
        errors.append("preparation completion does not precede mission launch in log order")
    # Names are bound to SEQ by checked source/roundtrip rows; the native log prints SEQ and ordinal.
    prefix = "within system preparation task 0 on " + owner
    first = "subtask 0 seqno 1 " + prefix
    second = "subtask 1 seqno 2 " + prefix
    wanted_steps = [
        (7, first + " started"),
        (7, first + " requests resources: no resources needed"),
        (7, first + " resource availability test"),
        (7, first + " starts performing, planned to last for 0.166667 hours"),
        (7 + 10 / 60, first + " completed"),
        (7 + 10 / 60, second + " started"),
        (7 + 10 / 60, second + " requests resources: no resources needed"),
        (7 + 10 / 60, second + " resource availability test"),
        (7 + 10 / 60, second + " starts performing, planned to last for 0.333333 hours"),
        (7.5, second + " completed"),
    ]
    observed_steps = [row for row in events if re.match(r"subtask \d+ seqno \d+ within system preparation task \d+ on <[^>]+> ", row["body"])]
    if len(observed_steps) != len(wanted_steps) or any(
        abs(actual["hour"] - wanted[0]) > 1e-4 or actual["body"] != wanted[1]
        for actual, wanted in zip(observed_steps, wanted_steps)
    ):
        errors.append(f"serial subtask lifecycle differs: {[(row['hour'], row['body']) for row in observed_steps]!r}")
    if len(observed_steps) == len(wanted_steps) and any(
        observed_steps[i]["line"] >= observed_steps[i + 1]["line"] for i in range(len(observed_steps) - 1)
    ):
        errors.append("serial subtask event order differs")
    return errors


def check_report(report: dict) -> list[str]:
    errors = []
    summary = native.table_rows(report, "ResultSummary")
    if len(summary) != 1 or any(summary[0].get(field) != value for field, value in
                                {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}.items()):
        errors.append("ResultSummary must cover one successful mission in one 0-36 h repetition")
    system = native.table_rows(report, "SystemResults")
    if len(system) != 72:
        errors.append(f"expected 72 SystemResults intervals, found {len(system)}")
    totals = {field: 0.0 for field in ("NPSTA", "NPSUC", "NSYMP", "FTMO", "NSYMO")}
    for index, row in enumerate(system):
        start, end = index * 0.5, (index + 1) * 0.5
        if row.get("STINT") != start or row.get("ETINT") != end:
            errors.append(f"interval {index} is not the {start}-{end} half-hour window")
        if row.get("UNID") != "Total over all Units" or row.get("SID") != "Total over all Systems":
            errors.append(f"interval {index} is not the aggregate system row")
        if row.get("NSYA") != 1:
            errors.append(f"interval {index} must retain one available aircraft type")
        wanted = {"NPSTA": int(start == 7), "NPSUC": int(start == 7.5),
                  "NSYMP": int(start == 7), "FTMO": int(8 <= start < 10),
                  "NSYMO": int(8 <= start < 10)}
        for field, value in wanted.items():
            actual = row.get(field)
            if not isinstance(actual, (int, float)) or abs(actual - value) > 1e-8:
                errors.append(f"interval {index} {field}: expected {value}, got {actual}")
            else:
                totals[field] += actual if field in ("NPSTA", "NPSUC") else actual * 0.5
    for field, value in {"NPSTA": 1, "NPSUC": 1, "NSYMP": 0.5, "FTMO": 2, "NSYMO": 2}.items():
        if abs(totals[field] - value) > 1e-8:
            errors.append(f"{field} total: expected {value}, got {totals[field]}")
    return errors


def check_provenance(run: Path) -> tuple[dict, list[str]]:
    errors = []
    for name in RAW_FILES | {"invocation.json", "closure.json"}:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing or empty artifact: {name}")
    if errors:
        return {}, errors
    invocation, closure = load_json(run / "invocation.json"), load_json(run / "closure.json")
    expected_hashes = {"input_sha256": INPUT_HASH,
                       "contract_sha256": sha256(HERE / "contract.json"),
                       "builder_sha256": sha256(HERE / "build.py"),
                       "parent_diff_sha256": sha256(HERE / "parent-diff.json"),
                       "validator_sha256": sha256(HERE / "validate.py"),
                       "runner_sha256": sha256(HERE / "run_native_ssh.ps1"),
                       "launcher_sha256": sha256(HERE / "invoke_loopback.ps1")}
    for field, expected in expected_hashes.items():
        if invocation.get(field) != expected:
            errors.append(f"invocation {field} differs from frozen source")
    if invocation.get("schema") != "simlox-b02-invocation/ssh-cli-v1" or invocation.get("case_version") != "1.0.2":
        errors.append("invocation case identity/version mismatch")
    if invocation.get("execution_mode") != "ssh_cli_v1" or invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
        errors.append("invocation does not prove session-0 SSH ancestry")
    if invocation.get("host_name", "").lower() != "4700-3" or invocation.get("simlox_exe_sha256") != "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0":
        errors.append("host or SIMLOX executable fingerprint mismatch")
    gui = invocation.get("coexisting_gui") or {}
    if not invocation.get("allow_existing_gui") or gui.get("pid") != 13340 or gui.get("session_id") != 1 or gui.get("process_start_utc") != "2026-09-28T10:09:56.8261381Z" or gui.get("responding_at_preflight") is not True or not gui.get("session_query_line"):
        errors.append("invocation does not bind existing GUI PID 13340")
    if closure.get("input_sha256") != INPUT_HASH or closure.get("case_id") != "B02" or closure.get("run_id") != invocation.get("run_id"):
        errors.append("closure identity or input hash mismatch")
    if closure.get("invocation_sha256") != sha256(run / "invocation.json"):
        errors.append("closure invocation hash mismatch")
    if set(closure.get("raw", {})) != RAW_FILES:
        errors.append("closure raw file set mismatch")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha256(path) != record.get("sha256"):
            errors.append(f"closure mismatch: {name}")
    steps = load_json(run / "steps.json")
    if [step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"]:
        errors.append("native step sequence mismatch")
    for step in steps:
        if step.get("exit_code") != 0 or not step.get("coexisting_gui_present_after") or not step.get("started_utc") or not step.get("completed_utc"):
            errors.append(f"native step failed or GUI coexistence was lost: {step.get('name')}")
    if sha256(run / "input.json") != INPUT_HASH or sha256(HERE / "native-input.json") != INPUT_HASH:
        errors.append("run or checked native input hash mismatch")
    return invocation, errors


def validate(run: Path) -> dict:
    invocation, errors = check_provenance(run)
    if errors:
        return {"case_id": "B02", "version": "1.0.2", "passed": False, "differences": errors}
    expected_input, expected_diff = build.build()
    if expected_input != (HERE / "native-input.json").read_bytes() or expected_diff != (HERE / "parent-diff.json").read_bytes():
        errors.append("builder or exact B01 parent diff differs from frozen source")
    source, exported = load_json(run / "input.json"), load_json(run / "roundtrip-raw.json")
    candidate = json.loads(expected_input)
    for name in build.CHANGED_TABLES:
        wanted = model_rows(candidate, name)
        for label, document in (("source", source), ("roundtrip", exported)):
            if model_rows(document, name) != wanted:
                errors.append(f"{label} {name} rows differ from contract")
    if model_rows(source, "MissionType")[0].get("NOPER") != 1.0:
        errors.append("B01 MissionType.NOPER=1 hour was not preserved")
    roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append(f"nonempty business rows changed in roundtrip: {roundtrip['changed']}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
    if conversion is None or int(conversion[1]) != 0 or int(conversion[2]) != 2 or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"conversion errors, warning count, or warning IDs differ: {dict(warnings)}")
    events = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    errors.extend(check_events(events))
    report = load_json(run / "report-raw.json")
    errors.extend(check_report(report))
    return {"case_id": "B02", "version": "1.0.2", "run_id": invocation.get("run_id"),
            "passed": not errors, "differences": errors, "input_sha256": INPUT_HASH,
            "roundtrip": roundtrip, "acceptance_scope": CONTRACT["acceptance_scope"],
            "gui_status": "not_run", "publication_state": "not_published"}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate.py RUN_DIRECTORY")
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
