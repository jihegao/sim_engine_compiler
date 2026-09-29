"""Source-bound B03 native CLI validator; independent replay is separate."""
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
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
TIMED = re.compile(r"^Time:\s*([\d.eE+\-]+)\s+(.*)$", re.M)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def model_rows(document: dict, name: str) -> list[dict]:
    table = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(table) != 1 or len(table[0]["instances"]) != 1:
        raise ValueError(f"missing or duplicate table: {name}")
    names = [column["name"] for column in table[0]["columns"]]
    return [dict(zip(names, row, strict=True)) for row in table[0]["instances"][0]["rows"]]


def timeline(events: list[tuple[float, str]], marker: str,
             wanted: list[tuple[float, str]], errors: list[str]) -> None:
    actual = [(hour, body) for hour, body in events if marker in body]
    if len(actual) != len(wanted) or any(abs(h - w) > 1e-4 or b != text
                                         for (h, b), (w, text) in zip(actual, wanted)):
        errors.append(f"{marker} lifecycle differs: {actual!r}")


def check_events(raw: str) -> list[str]:
    errors: list[str] = []
    events = [(float(hour), body.strip()) for hour, body in TIMED.findall(raw)]
    if not events or any(a[0] > b[0] + 1e-9 for a, b in zip(events, events[1:])):
        errors.append("native event times missing or unordered")
    missions = CONTRACT["missions"]
    owner = CONTRACT["aircraft_instance"]
    created = [(hour, body) for hour, body in events if " mission created:" in body]
    if len(created) != 3:
        return errors + [f"expected three created missions, got {created!r}"]
    tags = []
    for index, ((hour, body), mission) in enumerate(zip(created, missions, strict=True)):
        tag = body.removesuffix(" mission created:")
        if not re.fullmatch(rf"<{re.escape(mission['mtid'])},TEACH-UNIT,0,0,\d+>", tag):
            errors.append(f"mission {index} tag/MTID mismatch: {tag}")
        if abs(hour - mission["notice_hour"]) > 1e-4 or tag in tags:
            errors.append(f"mission {index} notice time or identity mismatch")
        tags.append(tag)
    expected: dict[str, list[tuple[float, str]]] = {key: [] for key in
        ("ordered", "allocated", "prep_start", "prep_end", "task", "launch", "success", "completion")}
    wanted_subtasks: list[tuple[float, str]] = []
    subtask_index = 0
    for mission_index, (tag, mission) in enumerate(zip(tags, missions, strict=True)):
        notice, launch = mission["notice_hour"], mission["launch_hour"]
        elapsed = 0.0
        finish = notice + sum(step["minutes"] for step in mission["steps"]) / 60
        expected["ordered"].append((notice, f"<TEACH-UNIT> mission ordered: {mission['mtid']}"))
        expected["allocated"].append((notice, f"{tag} mission allocates system: {owner}"))
        expected["prep_start"].append((notice, f"{owner} preparation started, mission: {tag}"))
        expected["prep_end"].append((finish, f"{owner} preparation ended, mission: {tag}"))
        expected["task"].extend([(notice, f"system preparation task {mission_index} on {owner} started"),
                                 (finish, f"system preparation task {mission_index} on {owner} completed")])
        expected["launch"].append((launch, f"{tag} mission starting, duration: 2 : {owner}"))
        expected["success"].append((launch + 2, f"{tag} mission success:"))
        expected["completion"].append((launch + 2, f"{tag} mission completed: {owner}"))
        for ordinal, step in enumerate(mission["steps"]):
            start = notice + elapsed / 60
            end = start + step["minutes"] / 60
            prefix = f"subtask {subtask_index} seqno {step['seq']} within system preparation task {mission_index} on {owner}"
            wanted_subtasks.extend([
                (start, prefix + " started"),
                (start, prefix + " requests resources: no resources needed"),
                (start, prefix + " resource availability test"),
                (start, prefix + f" starts performing, planned to last for {step['minutes']/60:.6f} hours"),
                (end, prefix + " completed"),
            ])
            elapsed += step["minutes"]
            subtask_index += 1
        if finish > launch + 1e-9:
            errors.append(f"preparation finishes after launch: {tag}")
    markers = {"ordered": " mission ordered:", "allocated": " mission allocates system:",
               "prep_start": " preparation started,", "prep_end": " preparation ended,",
               "launch": " mission starting, duration:", "success": " mission success:",
               "completion": " mission completed:"}
    for label, marker in markers.items():
        timeline(events, marker, expected[label], errors)
    actual_tasks = [(hour, body) for hour, body in events if body.startswith("system preparation task ")]
    if len(actual_tasks) != len(expected["task"]) or any(
            abs(h - w) > 1e-4 or b != text for (h, b), (w, text) in zip(actual_tasks, expected["task"])):
        errors.append(f"preparation task lifecycle differs: {actual_tasks!r}")
    actual_steps = [(hour, body) for hour, body in events if body.startswith("subtask ")]
    if len(actual_steps) != len(wanted_subtasks) or any(
            abs(h - w) > 1e-4 or b != text for (h, b), (w, text) in zip(actual_steps, wanted_subtasks)):
        errors.append(f"recipe step lifecycle differs: {actual_steps!r}")
    for marker in (" mission cancelled:", " mission aborted:"):
        if any(marker in body for _, body in events):
            errors.append(f"unexpected {marker.strip()} event")
    # Full global lists above prohibit missing or extra work and cross-recipe steps.
    return errors


def check_report(report: dict) -> list[str]:
    errors: list[str] = []
    summary = native.table_rows(report, "ResultSummary")
    if len(summary) != 1 or any(summary[0].get(key) != value for key, value in
                                {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}.items()):
        errors.append("ResultSummary does not show unit success fractions over 0-36 h")
    system = native.table_rows(report, "SystemResults")
    stock = native.table_rows(report, "StockTotalResults")
    if len(system) != 72 or len(stock) != 72:
        errors.append(f"expected 72 system and stock intervals, got {len(system)} and {len(stock)}")
    totals = Counter()
    starts, finishes = (7, 11, 15), (7.5, 11 + 1/6, 15 + 1/6)
    flights = ((8, 10), (12, 14), (16, 18))
    preps = ((7, 7.5), (11, 11 + 1/6), (15, 15 + 1/6))
    for index, row in enumerate(system):
        a, b = index / 2, (index + 1) / 2
        if row.get("STINT") != a or row.get("ETINT") != b or row.get("NSYA") != 1:
            errors.append(f"SystemResults geometry or aircraft count differs at {index}")
        wanted = {"NPSTA": sum(a <= t < b for t in starts),
                  "NPSUC": sum(a <= t < b for t in finishes),
                  "NSYMP": sum(max(0, min(b, e) - max(a, s)) for s, e in preps) / (b - a),
                  "FTMO": sum(max(0, min(b, e) - max(a, s)) for s, e in flights) / (b - a),
                  "NSYMO": sum(max(0, min(b, e) - max(a, s)) for s, e in flights) / (b - a)}
        for field, value in wanted.items():
            observed = row.get(field)
            if not isinstance(observed, (int, float)) or abs(observed - value) > 1e-4:
                errors.append(f"SystemResults interval {index} {field}: {observed} vs {value}")
            totals[field] += observed or 0
    for field, expected in {"NPSTA": 3, "NPSUC": 3, "NSYMP": 5/3, "FTMO": 12, "NSYMO": 12}.items():
        # Sum of half-hour fractions: 5/6 preparation hours becomes 5/3 interval units.
        if abs(totals[field] - expected) > 1e-4:
            errors.append(f"SystemResults {field} total differs: {totals[field]}")
    for index, row in enumerate(stock):
        if row.get("STINT") != index / 2 or row.get("ETINT") != (index + 1) / 2:
            errors.append(f"StockTotalResults interval {index} differs")
        if any(row.get(field) != 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
            errors.append(f"unexpected inventory/shortage ledger at interval {index}")
    return errors


def validate(run: Path) -> dict:
    errors: list[str] = []
    for name in RAW | {"invocation.json", "closure.json"}:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing or empty artifact: {name}")
    if errors:
        return {"case_id": "B03", "version": "1.0.2", "passed": False, "differences": errors}
    expected_input, expected_diff = build.build()
    if (HERE / "native-input.json").read_bytes() != expected_input or (HERE / "parent-diff.json").read_bytes() != expected_diff:
        errors.append("source differs from exact B02-derived builder")
    invocation, closure = read_json(run / "invocation.json"), read_json(run / "closure.json")
    for field, path in {"contract_sha256": HERE / "contract.json", "builder_sha256": HERE / "build.py",
                        "parent_diff_sha256": HERE / "parent-diff.json", "validator_sha256": HERE / "validate.py",
                        "runner_sha256": HERE / "run_native_ssh.ps1",
                        "launcher_sha256": HERE / "invoke_loopback.ps1"}.items():
        if invocation.get(field) != digest(path):
            errors.append(f"invocation {field} differs from source")
    if (invocation.get("input_sha256") != CONTRACT["input_sha256"] or
            invocation.get("parent_input_sha256") != CONTRACT["parent_input_sha256"] or
            invocation.get("a02_scope_sha256") != digest(HERE.parent / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md") or
            invocation.get("case_id") != "B03" or invocation.get("case_version") != "1.0.2" or
            invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []) or
            invocation.get("host_name", "").lower() != "4700-3" or
            invocation.get("simlox_exe_sha256") != "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"):
        errors.append("native invocation source, host or SSH identity mismatch")
    gui = invocation.get("coexisting_gui") or {}
    if gui.get("pid") != 13340 or gui.get("session_id") != 1 or not gui.get("responding_at_preflight"):
        errors.append("preserved GUI identity mismatch")
    if (closure.get("input_sha256") != CONTRACT["input_sha256"] or closure.get("case_id") != "B03"
            or closure.get("run_id") != invocation.get("run_id") or
            closure.get("invocation_sha256") != digest(run / "invocation.json") or
            set(closure.get("raw", {})) != RAW):
        errors.append("raw closure identity or file set mismatch")
    for name, item in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != item.get("bytes") or digest(path) != item.get("sha256"):
            errors.append(f"raw closure mismatch: {name}")
    steps = read_json(run / "steps.json")
    if [step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"] or any(
            step.get("exit_code") != 0 or not step.get("coexisting_gui_present_after") for step in steps):
        errors.append("native steps or GUI coexistence mismatch")
    if digest(run / "input.json") != CONTRACT["input_sha256"]:
        errors.append("run input hash mismatch")
    source, roundtrip = read_json(run / "input.json"), read_json(run / "roundtrip-raw.json")
    for name in build.CHANGED_TABLES:
        if model_rows(source, name) != model_rows(json.loads(expected_input), name) or model_rows(roundtrip, name) != model_rows(source, name):
            errors.append(f"source or roundtrip {name} rows differ")
    roundtrip_result = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip_result["all_equal"]:
        errors.append(f"native roundtrip business rows differ: {roundtrip_result['changed']}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    found = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
    if not found or (int(found[1]), int(found[2])) != (0, 2) or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"conversion errors or warning allowlist mismatch: {dict(warnings)}")
    errors.extend(check_events((run / "model.log").read_text(encoding="utf-8-sig", errors="replace")))
    errors.extend(check_report(read_json(run / "report-raw.json")))
    return {"case_id": "B03", "version": "1.0.2", "run_id": invocation.get("run_id"),
            "passed": not errors, "differences": errors, "input_sha256": CONTRACT["input_sha256"],
            "roundtrip": roundtrip_result, "acceptance_scope": CONTRACT["acceptance_scope"],
            "gui_status": "not_run", "publication_state": "not_published"}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate.py RUN_DIRECTORY")
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)
