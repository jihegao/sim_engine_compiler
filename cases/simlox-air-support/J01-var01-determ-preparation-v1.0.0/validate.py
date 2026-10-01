"""Read-only validation of one J01.var01 native SSH probe."""
from __future__ import annotations

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
RAW_FILES = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo",
             "import.log", "export.log", "run.log", "model.log", "report-raw.json",
             "report-export.log", "steps.json"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def table_rows(document: dict, name: str) -> list[dict]:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    names = [item["name"] for item in found[0]["columns"]]
    return [dict(zip(names, row, strict=True)) for row in found[0]["instances"][0]["rows"]]


def validate(run: Path) -> dict:
    errors: list[str] = []
    files = RAW_FILES | {"invocation.json", "closure.json"}
    for name in files:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing raw artifact: {name}")
    if errors:
        return {"passed": False, "differences": errors}
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    expected = {
        "input_sha256": CONTRACT["input_sha256"],
        "contract_sha256": sha256(HERE / "contract.json"),
        "builder_sha256": sha256(HERE / "build.py"),
        "validator_sha256": sha256(HERE / "validate.py"),
        "runner_sha256": sha256(HERE / "run_native_ssh.ps1"),
        "parent_diff_sha256": sha256(HERE / "parent-diff.json"),
    }
    for name, wanted in expected.items():
        if invocation.get(name) != wanted:
            errors.append(f"invocation {name} differs from source")
    if invocation.get("schema") != "simlox-j01-var01-invocation/ssh-cli-v1" or invocation.get("case_id") != "J01" or invocation.get("case_version") != "1.0.0":
        errors.append("invocation case identity mismatch")
    if invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
        errors.append("session-0 SSH ancestry unverified")
    gui = invocation.get("coexisting_gui") or {}
    if gui.get("pid") != 13340 or gui.get("session_id") != 1 or gui.get("process_start_utc") != "2026-09-28T10:09:56.8261381Z":
        errors.append("preserved GUI identity mismatch")
    if closure.get("case_id") != "J01" or closure.get("input_sha256") != CONTRACT["input_sha256"] or closure.get("invocation_sha256") != sha256(run / "invocation.json"):
        errors.append("closure identity mismatch")
    if closure.get("state") != "native_steps_complete":
        errors.append("closure does not seal four completed native steps")
    post_source = closure.get("post_source_sha256") or {}
    for name, wanted in {
        "native-input.json": CONTRACT["input_sha256"],
        "contract.json": sha256(HERE / "contract.json"),
        "build.py": sha256(HERE / "build.py"),
        "validate.py": sha256(HERE / "validate.py"),
        "run_native_ssh.ps1": sha256(HERE / "run_native_ssh.ps1"),
        "parent-diff.json": sha256(HERE / "parent-diff.json"),
        "parent-input.json": CONTRACT["parent_input_sha256"],
        "database-dictionary.txt": CONTRACT["source"]["database_dictionary_sha256"],
        "manual.pdf": CONTRACT["source"]["manual_sha256"],
    }.items():
        if post_source.get(name) != wanted:
            errors.append(f"post-run source seal differs: {name}")
    if set(closure.get("raw", {})) != RAW_FILES:
        errors.append("closure raw file list mismatch")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha256(path) != record.get("sha256"):
            errors.append(f"raw seal differs: {name}")
    steps = load(run / "steps.json")
    if [step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"]:
        errors.append("native step order mismatch")
    if any(step.get("exit_code") != 0 or step.get("coexisting_gui_present_after") is not True for step in steps):
        errors.append("native step failed or GUI was lost")
    candidate, diff = build.build()
    if candidate != (HERE / "native-input.json").read_bytes() or diff != (HERE / "parent-diff.json").read_bytes():
        errors.append("builder output differs")
    if sha256(run / "input.json") != CONTRACT["input_sha256"]:
        errors.append("run input differs")
    source, roundtrip = load(run / "input.json"), load(run / "roundtrip-raw.json")
    for label, document in (("source", source), ("roundtrip", roundtrip)):
        distribution = table_rows(document, "TimeDistributions")
        if distribution != [{"DISTID": "PREP-DET", "PFAC": 1, "BASED": "<DETERM>", "PARAM1": 0.5,
                             "PARAM2": None, "PARAM3": None, "NOTE": None}]:
            errors.append(f"{label} deterministic distribution row differs: {distribution!r}")
        prep = table_rows(document, "MissionPreparation")
        if len(prep) != 1 or prep[0].get("DURN") != 0.5 or prep[0].get("DURND") != "PREP-DET":
            errors.append(f"{label} preparation link differs: {prep!r}")
    comparison = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not comparison["all_equal"]:
        errors.append(f"business roundtrip differs: {comparison['changed']!r}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    if conversion is None or int(conversion[1]) != 0:
        errors.append("input conversion errors or absent summary")
    events = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for hour, marker in ((7, " preparation started,"), (7.5, " preparation ended,"),
                         (8, " mission starting, duration:"), (10, " mission success:")):
        hits = [float(match[1]) for line in events.splitlines()
                if (match := re.match(r"Time:\s*([0-9.eE+\-]+)\s+", line)) and marker in line]
        if len(hits) != 1 or abs(hits[0] - hour) > 1e-6:
            errors.append(f"event {marker} at {hour} differs: {hits!r}")
    report = load(run / "report-raw.json")
    summary = native.table_rows(report, "ResultSummary")
    if len(summary) != 1 or summary[0].get("MSTF") != 1 or summary[0].get("MSUF") != 1:
        errors.append("report does not show one successful mission")
    systems = native.table_rows(report, "SystemResults")
    if len(systems) != 72:
        errors.append(f"expected 72 half-hour system bins, got {len(systems)}")
    else:
        prep_hours = sum(float(row.get("NSYMP") or 0) * 0.5 for row in systems)
        if abs(prep_hours - 0.5) > 1e-8:
            errors.append(f"preparation system-hours {prep_hours} differs from 0.5")
    return {"case_id": "J01", "variant_id": "J01.var01", "version": "1.0.0",
            "run_id": invocation.get("run_id"), "passed": not errors, "differences": errors,
            "roundtrip": comparison, "input_sha256": CONTRACT["input_sha256"],
            "publication_state": "not_published", "acceptance_scope": "one deterministic B01 preparation probe"}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate.py RUN_DIRECTORY")
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
