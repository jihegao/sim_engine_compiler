"""Read-only, source-bound acceptance replay of E03 shared spare."""
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

INPUT_SHA = "657c0d52116c09ef2dbd009209f461f6fb4ed3570327c4305e0e4608f208cbf0"
PARENT_SHA = "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
PARENT_REPORT_SHA = "b5b83fbdc877eac297ba8a7492bdcdb162c6eeaab64901eacb16a3daa5cacf3e"
PARENT_RUN = HERE.parent / "E02-zero-stock-local-backorder-v1.0.0" / "runs" / "e02-v100-ssh-20260929-01"
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
    ck("contract input and parent", contract["native_input_sha256"] == INPUT_SHA and contract["parent"]["input_sha256"] == PARENT_SHA)
    ck("frozen input", sha(HERE / "native-input.json") == INPUT_SHA)
    ck("accepted parent", sha(HERE.parent / "E02-zero-stock-local-backorder-v1.0.0/native-input.json") == PARENT_SHA)
    ck("run input", sha(run / "input.json") == INPUT_SHA)
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    ck("invocation identity", invocation.get("case_id") == "E03" and invocation.get("run_id") == run.name)
    ck("E03 evidence schemas", invocation.get("schema") == "simlox-e03-v100-native-candidate/ssh-cli-v1" and closure.get("schema") == "simlox-e03-v100-native-closure/v1")
    ck("invocation source", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == PARENT_SHA)
    for key, filename in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"), ("runner_script_sha256", "run_native_ssh.ps1"), ("checker_sha256", "check_roundtrip.py")):
        ck(f"bound {filename}", invocation.get(key) == sha(HERE / filename))
    ck("pinned executable", invocation.get("simlox_exe_sha256") == EXE_SHA)
    ck("session-0 SSH", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    ck("sole GUI identity", invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("host queue", invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
    ck("closure invocation", closure.get("invocation_sha256") == sha(run / "invocation.json"))
    ck("closure successful", closure.get("error") is None)
    ck("source stable", closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("raw set", set(closure.get("raw", {})) == RAW)
    for name, item in closure.get("raw", {}).items():
        path = run / name
        ck(f"raw {name}", path.is_file() and path.stat().st_size == item.get("bytes") and sha(path) == item.get("sha256"))
    steps = load(run / "steps.json")
    ck("step order", [step.get("name") for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
    planned = invocation.get("planned_commands", [])
    ck("planned commands", len(planned) == 4 and all(planned[i].get("name") == steps[i].get("name") and planned[i].get("arguments") == steps[i].get("arguments") for i in range(4)))
    for step in steps:
        ck(f"step {step.get('name')}", step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
    roundtrip = load(run / "roundtrip-validation.json")
    ck("roundtrip checker", roundtrip.get("passed") is True and roundtrip.get("differences") == [] and len(roundtrip.get("populated_tables", [])) == 20)
    ck("business rows preserved", native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", calc)
    ck("conversion clean", conversion is not None and int(conversion[1]) == 0 and int(conversion[2]) == 1 and Counter(re.findall(r"\(warning #(\d+)\)", calc)) == Counter({"108": 1}))

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = log.splitlines()

    def event(time: str, fragment: str) -> bool:
        return sum(line.startswith(f"Time: {time} ") and fragment in line for line in lines) == 1

    def line(fragment: str) -> bool:
        return sum(fragment in item for item in lines) == 1

    def task(time: str, body: str) -> bool:
        return lines.count(f"Time: {time}  {body}") == 1

    ck("two aircraft ready initially", event("0", "systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>"))
    ck("two distinct mission allocations", event("7", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>") and event("7", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission allocates system: <TEACH-AIR-01,1>"))
    ck("two one-aircraft launches", event("8", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>") and event("8", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2 : <TEACH-AIR-01,1>"))
    ck("two installed-LRU failures", event("8.18829", "<TEACH-AIR-01,0> critical random failure added") and event("8.31325", "<TEACH-AIR-01,1> critical random failure added") and sum("subitem failed: <TEACH-LRU-01,0,1> connection path:" in item for item in lines) == 2 and sum("subitem failed: <TEACH-LRU-01,0,2> connection path:" in item for item in lines) == 2)
    ck("both missions abort and return", event("8.18829", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:") and event("8.31325", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission aborted:") and event("8.37658", "<BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:") and event("8.6265", "<BASIC-MISSION,TEACH-UNIT,0,0,1> aborted mission completed:") and "mission success:" not in log)
    ck("sole opening stock item", event("0", "Stock initiated") and line("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>,"))
    ck("first demand issues sole spare", task("8.37658", "system SURP task 0 on <TEACH-AIR-01,0> started") and event("8.37658", "item requiring maintenance is <TEACH-LRU-01,0,1>") and event("8.37658", "Take replacement item <TEACH-LRU-01,0,0> from stock") and line("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:"))
    ck("first explicit remove", task("8.37658", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> started") and task("8.54325", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed"))
    ck("first removed item to repair", event("8.54325", "Item requiring maintenance arrives <TEACH-LRU-01,0,1>") and task("8.54325", "item DIRP task 1 on <TEACH-LRU-01,0,1> started"))
    ck("first physical fit and ready", event("8.54325", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours") and task("8.87658", "system SURP task 0 on <TEACH-AIR-01,0> completed") and event("8.87658", "systems ready: 1 :<TEACH-AIR-01,0>"))
    ck("second demand becomes backorder", task("8.6265", "system SURP task 2 on <TEACH-AIR-01,1> started") and event("8.6265", "item requiring maintenance is <TEACH-LRU-01,0,2>") and event("8.6265", "Backorder added") and line("Backorders at: <TEACH-LRU-01,0,BASE-01,0> Nbr: 1 Backorders:<<TEACH-AIR-01,BASE-01,0>,8.6265>,"))
    ck("second remove and wait", task("8.6265", "remove subitem subtask 3 seqno 1 within system SURP task 2 on <TEACH-AIR-01,1> started") and task("8.79317", "remove subitem subtask 3 seqno 1 within system SURP task 2 on <TEACH-AIR-01,1> completed") and task("8.79317", "fit subitem subtask 4 seqno 2 within system SURP task 2 on <TEACH-AIR-01,1> wait for subitem"))
    ck("second removed item to repair", event("8.79317", "Item requiring maintenance arrives <TEACH-LRU-01,0,2>") and task("8.79317", "item DIRP task 3 on <TEACH-LRU-01,0,2> started"))
    ck("first item repairs four hours", event("8.54325", "direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,1> starts performing, planned to last for 4 hours") and task("12.5432", "item DIRP task 1 on <TEACH-LRU-01,0,1> completed"))
    ck("first repaired item clears second backorder", event("12.5432", "Replacement item arrives <TEACH-LRU-01,0,1>") and event("12.5432", "Backorder removed, waiting time was 3.91674") and line("Backorders at: <TEACH-LRU-01,0,BASE-01,0> Nbr: 0") and event("12.5432", "system SURP task 2 on <TEACH-AIR-01,1> subitem received <TEACH-LRU-01,0,1>"))
    ck("second physical fit and ready", event("12.5432", "fit subitem subtask 4 seqno 2 within system SURP task 2 on <TEACH-AIR-01,1> starts performing, planned to last for 0.333333 hours") and task("12.8766", "system SURP task 2 on <TEACH-AIR-01,1> completed") and event("12.8766", "systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>"))
    ck("second item repairs and restocks", event("8.79317", "direct repair subtask 5 seqno 0 within item DIRP task 3 on <TEACH-LRU-01,0,2> starts performing, planned to last for 4 hours") and task("12.7932", "item DIRP task 3 on <TEACH-LRU-01,0,2> completed") and event("12.7932", "Put back replacement item <TEACH-LRU-01,0,2> to stock") and line("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,2>,"))
    ck("unique issue and no other logistics", len(re.findall(r"Take replacement item", log)) == 1 and len(re.findall(r"Backorder added", log)) == 1 and len(re.findall(r"Backorder removed", log)) == 1 and len(re.findall(r"Put back replacement item", log)) == 1 and "Transport" not in log and len(re.findall(r"^Time: [0-9.]+  system SURP task \d+ .* started$", log, re.M)) == 2 and len(re.findall(r"^Time: [0-9.]+  item DIRP task \d+ .* started$", log, re.M)) == 2)

    result = report(run / "report-raw.json")
    summary = native.table_rows(result, "ResultSummary")
    system = native.table_rows(result, "SystemResults")
    stock = native.table_rows(result, "StockTotalResults")
    ck("mission summary", len(summary) == 1 and summary[0].get("NREP") == 1 and summary[0].get("MSUF") == 0)
    ck("system 72 intervals", len(system) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(system)))
    ck("two system failures and repairs", sum(row.get("NFAIL", 0) for row in system) == 2 and sum(row.get("NREPT", 0) for row in system) == 2 and abs(sum(row.get("NSYRP", 0) for row in system)*.5 - 1) < 1e-5)
    ck("system repair and wait bins", system[16]["NFAIL"] == 2 and system[17]["NREPT"] == 1 and system[25]["NREPT"] == 1 and abs(sum(row.get("NSYWI", 0) for row in system)*.5 - 3.750075) < 1e-4)
    ck("terminal two aircraft ready", system[-1]["NSYRY"] == 2 and system[-1]["NSYA"] == 2)
    ck("stock 72 intervals", len(stock) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(stock)))
    ck("two stock demand bins", stock[16]["NDF"] == 1 and stock[17]["NDF"] == 1 and sum(row["NDF"] for row in stock) == 2)
    ck("one backorder occupancy and wait", abs(sum(row["NBO"] for row in stock)*.5 - 3.916742) < 1e-4 and abs(stock[17]["WT"] - 3.916742) < 1e-4 and all(row["NBO"] == 0 for row in stock[26:]))
    parent_path = PARENT_RUN / "report-raw.json"
    ck("parent report SHA", sha(parent_path) == PARENT_REPORT_SHA)
    parent = report(parent_path)
    parent_summary = native.table_rows(parent, "ResultSummary")
    parent_system = native.table_rows(parent, "SystemResults")
    parent_stock = native.table_rows(parent, "StockTotalResults")
    ck("accepted parent control", len(parent_summary) == 1 and abs(parent_summary[0]["MSUF"] - 2/3) < 1e-6 and sum(row["NFAIL"] for row in parent_system) == 1 and sum(row["NREPT"] for row in parent_system) == 1 and sum(row["NDF"] for row in parent_stock) == 1)
    ck("two-aircraft outcome differs from parent", summary[0]["MSUF"] == 0 and sum(row["NFAIL"] for row in system) == 2)
    return {
        "schema": "simlox-e03-v100-author-native-validation/v1",
        "case_id": "E03", "run_id": run.name, "passed": not errors,
        "checks": count, "differences": errors,
        "observed_failure_hours": [8.18829, 8.31325],
        "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"),
        "report_sha256": sha(run / "report-raw.json"),
        "scope": "two_aircraft_one_shared_local_spare_and_one_backorder_cli_candidate",
        "publication_state": "not_published",
    }


if __name__ == "__main__":
    answer = validate(Path(sys.argv[1]))
    print(json.dumps(answer, indent=2))
    sys.exit(0 if answer["passed"] else 1)
