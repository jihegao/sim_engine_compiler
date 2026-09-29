"""Read-only author acceptance replay for the frozen A17 four-step CLI run."""
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

EXPECTED = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"
PARENT = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
EXE = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
TAG = "<BASIC-MISSION,TEACH-GROUP,0,0,0>"
AIRCRAFT = ("<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>")
UNITS = (("TEACH-UNIT", "BASE-01"), ("TEACH-UNIT-2", "BASE-02"))
RAW = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json",
    "report-export.log", "steps.json", "probe-validation.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate(run: Path) -> dict:
    errors: list[str] = []
    checks = 0

    def check(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            errors.append(label)

    contract = load(HERE / "contract.json")
    check("contract/input hash", contract["native_input_sha256"] == EXPECTED)
    check("contract/parent hash", contract["parent"]["input_sha256"] == PARENT)
    check("checked input hash", sha(HERE / "native-input.json") == EXPECTED)
    check("checked parent hash", sha(HERE.parent / "A03-two-aircraft-formation-v1.0.1/native-input.json") == PARENT)
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    check("run input hash", sha(run / "input.json") == EXPECTED)
    check("invocation input hash", invocation.get("input_sha256") == EXPECTED)
    check("invocation contract hash", invocation.get("contract_sha256") == sha(HERE / "contract.json"))
    check("invocation builder hash", invocation.get("builder_sha256") == sha(HERE / "build.py"))
    check("invocation runner hash", invocation.get("probe_script_sha256") == sha(HERE / "run_native_ssh.ps1"))
    check("invocation checker hash", invocation.get("checker_sha256") == sha(HERE / "check_probe.py"))
    check("pinned native executable", invocation.get("simlox_exe_sha256") == EXE)
    check("closure invocation hash", closure.get("invocation_sha256") == sha(run / "invocation.json"))
    check("closure no error", closure.get("error") is None)
    check("source fingerprints stable", closure.get("source_hashes_before") == closure.get("source_hashes_after"))
    check("raw file set", set(closure.get("raw", {})) == RAW)
    for name, record in closure.get("raw", {}).items():
        path = run / name
        check(f"raw {name}", path.is_file() and path.stat().st_size == record.get("bytes") and sha(path) == record.get("sha256"))

    check("session-0 SSH", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    check("GUI identity", invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    steps = load(run / "steps.json")
    check("four native steps and checker", [step.get("name") for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
    planned = invocation.get("planned_commands", [])
    check("launched command arguments bound", len(planned) == 4 and len(steps) >= 4 and all(
        planned[index].get("name") == steps[index].get("name") and
        planned[index].get("arguments") == steps[index].get("arguments")
        for index in range(min(len(planned), 4))
    ))
    for step in steps:
        check(f"step {step.get('name')}", step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
    probe = load(run / "probe-validation.json")
    check("import/export business rows", probe.get("passed") is True and probe.get("differences") == [])
    check("source business rows", native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])

    simulation = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", simulation)
    check("zero conversion errors", conversion is not None and int(conversion[1]) == 0)
    check("known conversion warnings", conversion is not None and int(conversion[2]) == 2 and Counter(re.findall(r"\(warning #(\d+)\)", simulation)) == Counter({"108": 1, "126": 1}))

    lines = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    def event(hour: int, body: str) -> bool:
        return sum(line.startswith(f"Time: {hour} ") and body in line for line in lines) == 1

    check("group mission ordered", event(7, "<TEACH-GROUP> mission ordered: BASIC-MISSION"))
    check("one mission created", event(7, f"{TAG} mission created:"))
    check("two systems requested", event(7, f"{TAG} mission activated, systems requested: 2"))
    for aircraft, (unit, base) in zip(AIRCRAFT, UNITS):
        check(f"{unit} initial station", event(0, f"{aircraft} nbr ready increased at unit: <{unit} at <{base},0>>"))
        check(f"{unit} allocation", event(7, f"{TAG} mission allocates system: {aircraft}"))
        check(f"{unit} preparation", event(7, f"{aircraft} preparation ended, mission: {TAG}"))
        check(f"{unit} return station", event(10, f"{aircraft} nbr ready increased at unit: <{unit} at <{base},0>>"))
        check(f"{unit} ready", event(10, f"<{unit} at <{base},0>> systems ready: 1 :{aircraft}"))
    formation = ",".join(AIRCRAFT)
    check("joint launch", event(8, f"{TAG} mission starting, duration: 2 : {formation}"))
    check("one success", event(10, f"{TAG} mission success:"))
    check("joint completion", event(10, f"{TAG} mission completed: {formation}"))
    for forbidden in (" mission cancelled:", " mission aborted:", " failure occurred", " PMTask started"):
        check(f"absence {forbidden}", not any(forbidden in line for line in lines))

    report = json.loads(native.remove_trailing_commas((run / "report-raw.json").read_bytes()))
    summary = native.table_rows(report, "ResultSummary")
    check("one successful repetition", len(summary) == 1 and summary[0].get("NREP") == 1 and summary[0].get("MSUF") == 1)
    rows = native.table_rows(report, "SystemResults")
    check("72 half-hour intervals", len(rows) == 72)
    mission_hours = aircraft_hours = 0.0
    for index, row in enumerate(rows):
        start, end = row.get("STINT"), row.get("ETINT")
        check(f"interval {index} grid", start == index * .5 and end == (index + 1) * .5)
        flying = 2 if 8 <= index * .5 < 10 else 0
        allocated = 2 if 7 <= index * .5 < 10 else 0
        check(f"interval {index} aircraft", row.get("NSYA") == 2 and row.get("NSYMA") == allocated and row.get("NSYMO") == flying and row.get("NSYRY") == 2 - allocated)
        check(f"interval {index} mission", row.get("FTMO") == (1 if flying else 0) and row.get("NPSTA") == 0)
        mission_hours += float(row.get("FTMO", 0)) * .5
        aircraft_hours += float(row.get("NSYMO", 0)) * .5
    check("two mission hours", mission_hours == 2)
    check("four aircraft hours", aircraft_hours == 4)
    check("terminal two ready", bool(rows) and rows[-1].get("NSYRY") == 2)
    return {
        "schema": "simlox-a17-v100-author-native-validation/v1",
        "case_id": "A17", "run_id": run.name, "passed": not errors,
        "differences": errors, "checks": checks,
        "input_sha256": EXPECTED, "model_log_sha256": sha(run / "model.log"),
        "report_sha256": sha(run / "report-raw.json"),
        "scope": "native_behavior_cli_candidate", "publication_state": "not_published",
    }


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
