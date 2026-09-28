"""Read-only acceptance checks for a sealed A03 native run directory."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402

CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
EXPECTED_INPUT_SHA256 = CONTRACT["input_sha256"]
TIME = re.compile(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$")
KINDS = {
    "ordered": " mission ordered:",
    "created": " mission created:",
    "activated": " mission activated, systems requested:",
    "allocation": " mission allocates system:",
    "launch": " mission starting, duration:",
    "success": " mission success:",
    "completion": " mission completed:",
    "cancel": " mission cancelled:",
    "abort": " mission aborted:",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log_events(raw: str) -> dict[str, list[tuple[float, str]]]:
    result: dict[str, list[tuple[float, str]]] = {kind: [] for kind in KINDS}
    for line in raw.splitlines():
        match = TIME.match(line)
        if match:
            for kind, marker in KINDS.items():
                if marker in match[2]:
                    result[kind].append((float(match[1]), match[2].strip()))
    return result


def check_events(raw: str) -> list[str]:
    expected = CONTRACT["expected_native"]
    events = log_events(raw)
    errors: list[str] = []
    tag = expected["mission_tag"]
    aircraft = expected["aircraft"]
    checks = {
        "ordered": [(7, "<TEACH-UNIT> mission ordered: BASIC-MISSION")],
        "created": [(7, f"{tag} mission created:")],
        "activated": [(7, f"{tag} mission activated, systems requested: 2")],
        "allocation": [(7, f"{tag} mission allocates system: {aircraft[0]}"),
                       (7, f"{tag} mission allocates system: {aircraft[1]}")],
        "launch": [(8, f"{tag} mission starting, duration: 2 : {','.join(aircraft)}")],
        "success": [(10, f"{tag} mission success:")],
        "completion": [(10, f"{tag} mission completed: {','.join(aircraft)}")],
        "cancel": [],
        "abort": [],
    }
    for kind, wanted in checks.items():
        actual = events[kind]
        if Counter(actual) != Counter(wanted):
            errors.append(f"{kind}: expected {wanted!r}; observed {actual!r}")
    if len({body for _, body in events["allocation"]}) != 2:
        errors.append("allocations must bind two distinct aircraft")
    return errors


def check_report(report: dict) -> list[str]:
    errors: list[str] = []
    try:
        summary = native.table_rows(report, "ResultSummary")
        system = native.table_rows(report, "SystemResults")
    except (KeyError, ValueError) as exc:
        return [str(exc)]
    if len(summary) != 1 or summary[0].get("NREP") != 1:
        errors.append("one repetition and one ResultSummary row required")
    if len(system) != 72:
        errors.append(f"expected 72 SystemResults half-hour intervals, got {len(system)}")
    mission_hours = 0.0
    flight_aircraft_hours = 0.0
    for index, row in enumerate(system):
        start, end = row.get("STINT"), row.get("ETINT")
        if start is None or end is None or abs(float(start) - index * .5) > 1e-8 or abs(float(end) - (index + 1) * .5) > 1e-8:
            errors.append(f"SystemResults interval {index} differs from half-hour grid")
            continue
        expected_count = 2
        if row.get("NSYA") != expected_count:
            errors.append(f"SystemResults interval {index}: NSYA must be 2")
        expected_flying = 2 if 8 <= float(start) < 10 else 0
        expected_mission_fraction = 1 if expected_flying else 0
        if row.get("FTMO") is None or abs(float(row["FTMO"]) - expected_mission_fraction) > 1e-8:
            errors.append(f"SystemResults interval {index}: FTMO must be {expected_mission_fraction}")
        else:
            mission_hours += float(row["FTMO"]) * (float(end) - float(start))
        if row.get("NSYMO") is None or abs(float(row["NSYMO"]) - expected_flying) > 1e-8:
            errors.append(f"SystemResults interval {index}: NSYMO must be {expected_flying}")
        else:
            flight_aircraft_hours += float(row["NSYMO"]) * (float(end) - float(start))
        if row.get("NPSTA") != 0:
            errors.append(f"SystemResults interval {index}: unexpected preparation count")
    if abs(mission_hours - 2) > 1e-8:
        errors.append(f"expected 2 mission-hours, got {mission_hours}")
    if abs(flight_aircraft_hours - 4) > 1e-8:
        errors.append(f"expected 4 aircraft-hours, got {flight_aircraft_hours}")
    return errors


def validate(run_dir: Path) -> dict:
    required = ("input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "run.log", "model.log", "report-raw.json", "invocation.json", "closure.json")
    for name in required:
        path = run_dir / name
        if not path.is_file() or path.stat().st_size <= 4:
            raise ValueError(f"missing or empty raw artifact: {name}")
    if sha256(run_dir / "input.json") != EXPECTED_INPUT_SHA256:
        raise ValueError("run input differs from frozen A03 input")
    if sha256(HERE / "native-input.json") != EXPECTED_INPUT_SHA256:
        raise ValueError("checked A03 input changed")
    invocation = json.loads((run_dir / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run_dir / "closure.json").read_text(encoding="utf-8-sig"))
    if invocation.get("input_sha256") != EXPECTED_INPUT_SHA256 or closure.get("input_sha256") != EXPECTED_INPUT_SHA256:
        raise ValueError("invocation or closure is not bound to checked input")
    if invocation.get("contract_sha256") != sha256(HERE / "contract.json") or invocation.get("validator_sha256") != sha256(HERE / "validate.py"):
        raise ValueError("invocation source hashes differ from acceptance source")
    for name, record in closure.get("raw", {}).items():
        path = run_dir / name
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha256(path) != record.get("sha256"):
            raise ValueError(f"raw closure mismatch: {name}")
    if set(closure.get("raw", {})) != {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}:
        raise ValueError("raw closure file set differs from contract")
    roundtrip = native.compare_roundtrip(run_dir / "input.json", run_dir / "roundtrip-raw.json")
    errors = [] if roundtrip["all_equal"] else ["native import/export changed nonempty business rows"]
    log = (run_dir / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    if conversion is None or int(conversion[1]) != 0:
        errors.append("conversion errors or missing conversion summary")
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", log))
    if conversion is None or int(conversion[2]) != 2 or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"unexpected native warnings: {dict(warnings)}")
    events = (run_dir / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    errors.extend(check_events(events))
    report = json.loads(native.remove_trailing_commas((run_dir / "report-raw.json").read_bytes()))
    errors.extend(check_report(report))
    return {"case_id": "A03", "scope": "native_behavior_cli_candidate", "passed": not errors,
            "differences": errors, "input_sha256": EXPECTED_INPUT_SHA256,
            "raw_sha256": {name: sha256(run_dir / name) for name in required},
            "roundtrip": roundtrip,
            "publication_state": "not_published", "gui_status": "separate_gate"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = validate(args.run_dir)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
