"""Source-bound read-only acceptance replay for D01 direct system repair."""
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

INPUT_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
A02_REPORT_SHA = "a7227687988841c074b28b524792af7d856cd674840169bf15c210f2d2cd4739"
A02_RUN = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A02/a02-bound-final-20260927-03")
AIRCRAFT = "<TEACH-AIR-01,0>"
TAG = "<BASIC-MISSION,TEACH-UNIT,0,0,"
RAW = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "steps.json", "roundtrip-validation.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def validate(run: Path) -> dict:
    errors: list[str] = []
    count = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal count
        count += 1
        if not condition:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("contract input", contract["native_input_sha256"] == INPUT_SHA)
    ck("contract parent", contract["parent"]["input_sha256"] == PARENT_SHA)
    ck("checked input", sha(HERE / "native-input.json") == INPUT_SHA)
    ck("checked A02 parent", sha(HERE.parent / "A02-single-aircraft-repeated-missions/native-input.json") == PARENT_SHA)
    ck("run input", sha(run / "input.json") == INPUT_SHA)
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    ck("invocation identity", invocation.get("case_id") == "D01" and invocation.get("run_id") == run.name)
    ck("invocation source", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == PARENT_SHA)
    ck("contract binding", invocation.get("contract_sha256") == sha(HERE / "contract.json"))
    ck("builder binding", invocation.get("builder_sha256") == sha(HERE / "build.py"))
    ck("runner binding", invocation.get("runner_script_sha256") == sha(HERE / "run_native_ssh.ps1"))
    ck("checker binding", invocation.get("checker_sha256") == sha(HERE / "check_roundtrip.py"))
    ck("pinned native executable", invocation.get("simlox_exe_sha256") == EXE_SHA)
    ck("session-0 SSH", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    ck("GUI identity", invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("closure invocation", closure.get("invocation_sha256") == sha(run / "invocation.json"))
    ck("closure no error", closure.get("error") is None)
    ck("source hashes stable", closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("raw file set", set(closure.get("raw", {})) == RAW)
    for name, item in closure.get("raw", {}).items():
        path = run / name
        ck(f"raw {name}", path.is_file() and path.stat().st_size == item.get("bytes") and sha(path) == item.get("sha256"))
    steps = load(run / "steps.json")
    ck("step sequence", [x.get("name") for x in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
    planned = invocation.get("planned_commands", [])
    ck("command binding", len(planned) == 4 and len(steps) >= 4 and all(planned[i].get("name") == steps[i].get("name") and planned[i].get("arguments") == steps[i].get("arguments") for i in range(4)))
    for step in steps:
        ck(f"step {step.get('name')}", step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
    roundtrip = load(run / "roundtrip-validation.json")
    ck("roundtrip checker", roundtrip.get("passed") is True and roundtrip.get("differences") == [])
    ck("business rows", native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", calc)
    ck("conversion zero errors", conversion is not None and int(conversion[1]) == 0)
    ck("known warnings", conversion is not None and int(conversion[2]) == 2 and Counter(re.findall(r"\(warning #(\d+)\)", calc)) == Counter({"108": 1, "126": 1}))

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = log.splitlines()
    def event(time: str, fragment: str) -> bool:
        return sum(line.startswith(f"Time: {time} ") and fragment in line for line in lines) == 1
    def exact_task(time: str, body: str) -> bool:
        return lines.count(f"Time: {time}  {body}") == 1

    failure_times = [float(m.group(1)) for m in re.finditer(r"^Time: ([0-9.]+) <TEACH-AIR-01,0> critical random failure added", log, re.M)]
    ck("two observed critical failures", failure_times == [9.8829, 33.8602])
    for index, (notice, launch, finish, failure, repair_start) in enumerate(((7, 8, 10, "9.8829", 10), (19, 20, 22, None, None), (31, 32, 34, "33.8602", 34))):
        tag = f"{TAG}{index}>"
        ck(f"mission {index} ordered", event(str(notice), "<TEACH-UNIT> mission ordered: BASIC-MISSION"))
        ck(f"mission {index} created", event(str(notice), f"{tag} mission created:"))
        ck(f"mission {index} allocated", event(str(notice), f"{tag} mission allocates system: {AIRCRAFT}"))
        ck(f"mission {index} launched", event(str(launch), f"{tag} mission starting, duration: 2 : {AIRCRAFT}"))
        if failure:
            ck(f"mission {index} abort", event(failure, f"{tag} mission aborted:"))
            ck(f"mission {index} aborted completion", event(str(finish), f"{tag} aborted mission completed:"))
            ck(f"repair {index} start", exact_task(str(repair_start), f"system DIRP task {0 if index == 0 else 1} on {AIRCRAFT} started"))
            ck(f"repair {index} perform", event(str(repair_start), "starts performing, planned to last for 0.5 hours"))
            ck(f"repair {index} completion", exact_task(str(repair_start + .5), f"system DIRP task {0 if index == 0 else 1} on {AIRCRAFT} completed"))
            ck(f"repair {index} ready", event(str(repair_start + .5), f"<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :{AIRCRAFT}"))
        else:
            ck("middle mission success", event(str(finish), f"{tag} mission success:"))
            ck("middle mission completion", event(str(finish), f"{tag} mission completed: {AIRCRAFT}"))
    ck("no cancelled missions", " mission cancelled:" not in log)
    ck("no extra repair task", len(re.findall(r"^Time: [0-9.]+  system DIRP task \d+ on <TEACH-AIR-01,0> started$", log, re.M)) == 2)

    result = report(run / "report-raw.json")
    summary = native.table_rows(result, "ResultSummary")
    ck("one repetition one of three success", len(summary) == 1 and summary[0].get("NREP") == 1 and abs(summary[0].get("MSUF", 0) - 1 / 3) < 1e-6)
    system = native.table_rows(result, "SystemResults")
    ck("72 intervals", len(system) == 72)
    for i, row in enumerate(system):
        start = i * .5
        allocated = any(a <= start < b for a, b in ((7, 10), (19, 22), (31, 34)))
        flying = any(a <= start < b for a, b in ((8, 10), (20, 22), (32, 34)))
        repairing = start in (10, 34)
        failing = start in (9.5, 33.5)
        ck(f"interval {i} grid", row.get("STINT") == start and row.get("ETINT") == start + .5)
        ck(f"interval {i} states", row.get("NSYA") == int(not repairing) and row.get("NSYMA") == int(allocated) and row.get("NSYMO") == int(flying) and row.get("NSYRP") == int(repairing) and row.get("NSYRY") == int(not allocated and not repairing))
        ck(f"interval {i} fault and mission", row.get("NFAIL") == int(failing) and row.get("FTMO") == int(flying) and row.get("NPSTA") == 0)
    ck("report failure/repair totals", sum(row["NFAIL"] for row in system) == 2 and sum(row["NSYRP"] for row in system) == 2)
    ck("terminal aircraft ready", system[-1]["NSYRY"] == 1)

    control_path = A02_RUN / "report-raw.json"
    ck("A02 control report hash", sha(control_path) == A02_REPORT_SHA)
    control = report(control_path)
    control_summary = native.table_rows(control, "ResultSummary")
    control_system = native.table_rows(control, "SystemResults")
    ck("A02 control normal outcome", len(control_summary) == 1 and control_summary[0].get("MSUF") == 1 and len(control_system) == 72 and sum(row["NFAIL"] for row in control_system) == 0 and sum(row["NSYRP"] for row in control_system) == 0)
    ck("source-vs-control changed mission outcome", summary[0]["MSUF"] < control_summary[0]["MSUF"])
    return {
        "schema": "simlox-d01-v100-author-native-validation/v1",
        "case_id": "D01", "run_id": run.name, "passed": not errors,
        "checks": count, "differences": errors,
        "observed_failure_hours": failure_times,
        "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"),
        "report_sha256": sha(run / "report-raw.json"),
        "scope": "system_level_direct_repair_cli_candidate", "publication_state": "not_published",
    }


if __name__ == "__main__":
    answer = validate(Path(sys.argv[1]))
    print(json.dumps(answer, indent=2))
    sys.exit(0 if answer["passed"] else 1)
