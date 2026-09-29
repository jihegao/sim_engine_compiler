"""Source-bound C01 1.0.2 SSH CLI validation for all capacity variants."""
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
RAW_FILES = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
             "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
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


def same_timeline(actual: list[dict], wanted: list[tuple[float, str]]) -> bool:
    return len(actual) == len(wanted) and all(
        abs(row["hour"] - hour) <= 1e-4 and row["body"] == body
        for row, (hour, body) in zip(actual, wanted)
    )


def check_events(raw: str, variant_id: str) -> tuple[list[str], dict]:
    events = event_rows(raw)
    errors = []
    tag, owner = "<BASIC-MISSION,TEACH-UNIT,0,0,0>", "<TEACH-AIR-01,0>"
    first = f"subtask 0 seqno 1 within system preparation task 0 on {owner}"
    second = f"subtask 1 seqno 2 within system preparation task 0 on {owner}"
    resource = "<P-CREW at <BASE-01,0>>"

    def selected(marker: str) -> list[dict]:
        return [row for row in events if marker in row["body"]]

    def exact(label: str, actual: list[dict], wanted: list[tuple[float, str]]) -> None:
        if not same_timeline(actual, wanted):
            errors.append(f"{label}: expected {wanted!r}; observed {[(r['hour'], r['body']) for r in actual]!r}")

    exact("notice", selected(" mission ordered:"), [(7, "<TEACH-UNIT> mission ordered: BASIC-MISSION")])
    exact("created", selected(" mission created:"), [(7, f"{tag} mission created:")])
    exact("allocation", selected(" mission allocates system:"), [(7, f"{tag} mission allocates system: {owner}")])
    exact("prep start", selected(" preparation started,"), [(7, f"{owner} preparation started, mission: {tag}")])
    exact("task start", [r for r in selected("system preparation task") if r["body"].endswith(" started") and r["body"].startswith("system preparation task")],
          [(7, f"system preparation task 0 on {owner} started")])
    exact("INSPECT start", [r for r in events if r["body"].startswith("subtask ") and r["body"].endswith(" started") and "within system preparation task" in r["body"]],
          [(7, first + " started")] if variant_id != "capacity-2" else
          [(7, first + " started"), (7 + 10 / 60, second + " started")])
    exact("request", selected(first + " requests resources"), [(7, first + " requests resources")])
    exact("availability check", selected(first + " resource availability test"), [(7, first + " resource availability test")])
    if any(a["hour"] > b["hour"] + 1e-9 for a, b in zip(events, events[1:])):
        errors.append("native event times are not monotonic")
    if raw.count(f"Availability test on  {resource} request for: 2 ") != 1 or "Availability test on  <P-OTHER" in raw:
        errors.append("request is not exactly P-CREW x2")
    observed = {"cancellation_hour": None, "lease_person_minutes": 0}
    if variant_id == "capacity-2":
        if raw.count(f"Availability test on  {resource} request for: 2 OK") != 1:
            errors.append("capacity-two request did not succeed")
        exact("booking", selected(first + " books resources"), [(7, first + " books resources")])
        exact("lease", selected("allocated to maintenance task:"),
              [(7, resource + " allocated to maintenance task: 2  available now: 0")])
        exact("release", selected("deallocated from  maintenance task:"),
              [(7 + 10 / 60, resource + " deallocated from  maintenance task: 2  available now: 2")])
        sequence = [
            first + " books resources",
            resource + " allocated to maintenance task: 2  available now: 0",
            first + " starts performing, planned to last for 0.166667 hours",
            first + " completed",
            first + " frees resources",
            resource + " deallocated from  maintenance task: 2  available now: 2",
            second + " starts performing, planned to last for 0.333333 hours",
        ]
        positions = [[row["line"] for row in events if row["body"] == body] for body in sequence]
        if any(len(group) != 1 for group in positions) or any(
                a[0] >= b[0] for a, b in zip(positions, positions[1:])):
            errors.append(f"crew acquisition/work/release order differs: {positions}")
        wanted_steps = [
            (7, first + " started"), (7, first + " requests resources"),
            (7, first + " resource availability test"), (7, first + " books resources"),
            (7, first + " starts performing, planned to last for 0.166667 hours"),
            (7 + 10 / 60, first + " completed"), (7 + 10 / 60, first + " frees resources"),
            (7 + 10 / 60, second + " started"),
            (7 + 10 / 60, second + " requests resources: no resources needed"),
            (7 + 10 / 60, second + " resource availability test"),
            (7 + 10 / 60, second + " starts performing, planned to last for 0.333333 hours"),
            (7.5, second + " completed"),
        ]
        actual_steps = [r for r in events if re.match(r"subtask \d+ seqno \d+ within system preparation task \d+ on <[^>]+> ", r["body"])
                        and not r["body"].endswith("check return remote resources")]
        exact("serial resource steps", actual_steps, wanted_steps)
        exact("task completion", [r for r in selected("system preparation task") if r["body"].startswith("system preparation task") and r["body"].endswith(" completed")],
              [(7.5, f"system preparation task 0 on {owner} completed")])
        exact("prep end", selected(" preparation ended,"), [(7.5, f"{owner} preparation ended, mission: {tag}")])
        exact("launch", selected(" mission starting, duration:"), [(8, f"{tag} mission starting, duration: 2 : {owner}")])
        exact("success", selected(" mission success:"), [(10, f"{tag} mission success:")])
        exact("completion", selected(" mission completed:"), [(10, f"{tag} mission completed: {owner}")])
        exact("cancel", selected(" mission cancelled:"), [])
        if selected("<P-OTHER at <BASE-01,0>> allocated"):
            errors.append("other specialty was consumed")
        observed["lease_person_minutes"] = 20
    else:
        if raw.count(f"Availability test on  {resource} request for: 2 failed") != 1:
            errors.append("blocked request did not fail")
        if any("allocated to maintenance task:" in r["body"] or "deallocated from  maintenance task:" in r["body"] for r in events):
            errors.append("blocked variant booked a partial lease")
        if any((" starts performing," in r["body"] or " books resources" in r["body"]) and "subtask " in r["body"] for r in events):
            errors.append("blocked variant started preparation work")
        if any("subtask 1 seqno 2" in r["body"] for r in events):
            errors.append("SERVICE started despite blocked INSPECT")
        for label, marker in (("launch", " mission starting, duration:"), ("success", " mission success:"),
                              ("completion", " mission completed:")):
            if selected(marker):
                errors.append(f"blocked variant has {label} event")
        cancelled = selected(" mission cancelled:")
        if len(cancelled) != 1 or cancelled[0]["body"] != f"{tag} mission cancelled:" or cancelled[0]["hour"] < 7:
            errors.append("blocked variant lacks one native cancellation after notice")
        else:
            observed["cancellation_hour"] = cancelled[0]["hour"]
            ordered, wait, task, prep = (selected(first + " ordered to stop"), selected(first + " resource waiting stopped"),
                                         [r for r in events if r["body"] == f"system preparation task 0 on {owner} stopped"],
                                         selected(" preparation ended,"))
            if any(len(group) != 1 for group in (ordered, wait, task, prep)):
                errors.append("blocked cancellation-to-stop events missing or duplicated")
            elif not (cancelled[0]["line"] < ordered[0]["line"] < wait[0]["line"] < task[0]["line"] < prep[0]["line"]):
                errors.append("blocked cancellation-to-stop order differs")
            if len(prep) == 1 and prep[0]["body"] != f"{owner} preparation ended, mission: {tag}":
                errors.append("blocked preparation ended on wrong aircraft or mission")
    return errors, observed


def check_report(report: dict, variant_id: str) -> list[str]:
    errors = []
    success = variant_id == "capacity-2"
    summary = native.table_rows(report, "ResultSummary")
    wanted = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": int(success), "MSUF": int(success)}
    if len(summary) != 1 or any(summary[0].get(k) != v for k, v in wanted.items()):
        errors.append(f"ResultSummary differs from {wanted}")
    system = native.table_rows(report, "SystemResults")
    if len(system) != 72:
        errors.append(f"expected 72 SystemResults intervals, found {len(system)}")
    for index, row in enumerate(system):
        start, end = index / 2, (index + 1) / 2
        if row.get("STINT") != start or row.get("ETINT") != end or row.get("UNID") != "Total over all Units" or row.get("SID") != "Total over all Systems" or row.get("NSYA") != 1:
            errors.append(f"SystemResults geometry or aircraft count differs at {index}")
        expected = {"NPSTA": int(start == 7), "NPSUC": int(success and start == 7.5),
                    "FTMO": int(success and 8 <= start < 10), "NSYMO": int(success and 8 <= start < 10)}
        for field, value in expected.items():
            actual = row.get(field)
            if not isinstance(actual, (int, float)) or abs(actual - value) > 1e-8:
                errors.append(f"interval {index} {field}: expected {value}, got {actual}")
        if success and abs(row.get("NSYMP", -1) - int(start == 7)) > 1e-8:
            errors.append(f"interval {index} preparation aircraft-hours differ")
    resources = native.table_rows(report, "ResourceResults")
    if len(resources) != 72:
        errors.append(f"expected 72 ResourceResults intervals, found {len(resources)}")
    capacities = {"capacity-2": 2, "capacity-1": 1, "capacity-0": 0, "wrong-specialty": 2}
    first_wait = {"capacity-2": 0, "capacity-1": 1, "capacity-0": 2, "wrong-specialty": 2}
    for index, row in enumerate(resources):
        start, end = index / 2, (index + 1) / 2
        if (row.get("RID") != "Total over all Resources" or row.get("STID") != "Total over all Stations"
                or row.get("STINT") != start or row.get("ETINT") != end or row.get("NR") != capacities[variant_id]):
            errors.append(f"ResourceResults identity, interval or capacity differs at {index}")
        expected_busy = 2 / 3 if success and start == 7 else 0
        expected_wait = first_wait[variant_id] * (1 if start == 7 else 1 / 6 if start == 7.5 else 0)
        if abs(row.get("NRUM", -1) - expected_busy) > 1e-5 or abs(row.get("NRW", -1) - expected_wait) > 1e-5:
            errors.append(f"ResourceResults busy/wait ledger differs at {index}: {row.get('NRUM')}, {row.get('NRW')}")
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
    variant_id = invocation.get("variant_id")
    if variant_id not in build.VARIANTS:
        return invocation, [f"unknown variant in invocation: {variant_id}"]
    variant = CONTRACT["variants"][variant_id]
    expected = {
        "input_sha256": variant["input_sha256"], "contract_sha256": sha256(HERE / "contract.json"),
        "builder_sha256": sha256(HERE / "build.py"), "parent_input_sha256": CONTRACT["parent_input_sha256"],
        "parent_diff_sha256": sha256(HERE / "parent-diffs" / f"{variant_id}.json"),
        "validator_sha256": sha256(HERE / "validate.py"),
        "runner_sha256": sha256(HERE / "run_native_ssh.ps1"),
        "launcher_sha256": sha256(HERE / "invoke_loopback.ps1"),
    }
    for field, wanted in expected.items():
        if invocation.get(field) != wanted:
            errors.append(f"invocation {field} differs from checked source")
    if invocation.get("schema") != "simlox-c01-invocation/ssh-cli-v1" or invocation.get("case_id") != "C01" or invocation.get("case_version") != "1.0.2":
        errors.append("invocation case identity/version mismatch")
    if invocation.get("execution_mode") != "ssh_cli_v1" or invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
        errors.append("invocation does not prove session-0 SSH ancestry")
    if invocation.get("host_name", "").lower() != "4700-3" or invocation.get("simlox_exe_sha256") != "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0":
        errors.append("host or SIMLOX executable fingerprint mismatch")
    gui = invocation.get("coexisting_gui") or {}
    if not invocation.get("allow_existing_gui") or gui.get("pid") != 13340 or gui.get("session_id") != 1 or gui.get("process_start_utc") != "2026-09-28T10:09:56.8261381Z" or gui.get("responding_at_preflight") is not True or not gui.get("session_query_line"):
        errors.append("invocation does not bind original GUI PID 13340")
    if closure.get("case_id") != "C01" or closure.get("variant_id") != variant_id or closure.get("input_sha256") != variant["input_sha256"] or closure.get("run_id") != invocation.get("run_id"):
        errors.append("closure identity, variant or input hash mismatch")
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
            errors.append(f"native step failed or GUI coexistence lost: {step.get('name')}")
    if sha256(run / "input.json") != variant["input_sha256"] or sha256(HERE / "inputs" / f"{variant_id}.json") != variant["input_sha256"]:
        errors.append("run or checked variant input hash mismatch")
    return invocation, errors


def validate(run: Path) -> dict:
    invocation, errors = check_provenance(run)
    variant_id = invocation.get("variant_id")
    if errors:
        return {"case_id": "C01", "version": "1.0.2", "variant_id": variant_id,
                "passed": False, "differences": errors}
    built = build.build()
    for name, (native_input, exact_diff) in built.items():
        if native_input != (HERE / "inputs" / f"{name}.json").read_bytes() or exact_diff != (HERE / "parent-diffs" / f"{name}.json").read_bytes():
            errors.append(f"builder or exact B02 parent diff differs for {name}")
    source, exported = load_json(run / "input.json"), load_json(run / "roundtrip-raw.json")
    candidate = json.loads(built[variant_id][0])
    for name in build.CHANGED_TABLES:
        wanted = model_rows(candidate, name)
        for label, document in (("source", source), ("roundtrip", exported)):
            if model_rows(document, name) != wanted:
                errors.append(f"{label} {name} rows differ from contract")
    if model_rows(source, "MissionType")[0].get("NOPER") != 1.0:
        errors.append("B02 one-hour notice was not preserved")
    roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append(f"nonempty business rows changed in roundtrip: {roundtrip['changed']}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
    if conversion is None or int(conversion[1]) != 0 or int(conversion[2]) != 2 or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"conversion errors, warning count or warning IDs differ: {dict(warnings)}")
    event_errors, observed = check_events((run / "model.log").read_text(encoding="utf-8-sig", errors="replace"), variant_id)
    errors.extend(event_errors)
    errors.extend(check_report(load_json(run / "report-raw.json"), variant_id))
    return {"case_id": "C01", "version": "1.0.2", "variant_id": variant_id,
            "run_id": invocation.get("run_id"), "passed": not errors, "differences": errors,
            "input_sha256": CONTRACT["variants"][variant_id]["input_sha256"],
            "roundtrip": roundtrip, "observed": observed,
            "acceptance_scope": CONTRACT["acceptance_scope"],
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
