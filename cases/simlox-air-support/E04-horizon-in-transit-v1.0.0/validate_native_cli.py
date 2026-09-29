"""Read-only, source-bound acceptance replay of E04 horizon transit."""
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

INPUT_SHA = "d2d95d45eccf05509ea1f9e35e90a47ef143750c353b1f3bb8791dd81a99b9ae"
PARENT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
PARENT_REPORT_SHA = "3284c19ccce1237ca651cd50c6c0fb3320e9ed914a77f61c75cb4830e624c376"
PARENT_RUN = HERE.parent / "E04-upstream-transport-fast-v1.0.0" / "runs" / "e04-fast-v100-ssh-20260929-01"
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
    ck("accepted parent", sha(HERE.parent / "E04-upstream-transport-fast-v1.0.0/native-input.json") == PARENT_SHA)
    ck("run input", sha(run / "input.json") == INPUT_SHA)
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    ck("invocation identity", invocation.get("case_id") == "E04.var04" and invocation.get("run_id") == run.name)
    ck("E04 transit evidence schemas", invocation.get("schema") == "simlox-e04-transit-v100-native-candidate/ssh-cli-v1" and closure.get("schema") == "simlox-e04-transit-v100-native-closure/v1")
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
    ck("roundtrip checker", roundtrip.get("passed") is True and roundtrip.get("differences") == [] and len(roundtrip.get("populated_tables", [])) == 21)
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

    ck("one observed LRU failure", len(re.findall(r"^Time: [0-9.]+ <TEACH-AIR-01,0> critical random failure added", log, re.M)) == 1 and sum("subitem failed: <TEACH-LRU-01,0,1> connection path:" in item for item in lines) == 2)
    ck("first mission aborted", event("9.8829", "mission aborted:") and event("10", "aborted mission completed:"))
    ck("later missions wait and cancel", event("19", "mission waiting:  timeout at 20.3333") and event("20.3333", "mission cancelled:") and event("31", "mission waiting:  timeout at 32.3333") and event("32.3333", "mission cancelled:") and "mission success:" not in log)
    ck("opening base zero and depot one", event("0", "<TEACH-LRU-01,0,BASE-01,0> Stock initiated") and event("0", "<TEACH-LRU-01,0,DEPOT-01,0> Stock initiated") and line("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:") and line("Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>,"))
    ck("base demand and backorder", task("10", "system SURP task 0 on <TEACH-AIR-01,0> started") and event("10", "<TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,1>") and event("10", "<TEACH-LRU-01,0,BASE-01,0> Backorder added") and line("Backorders at: <TEACH-LRU-01,0,BASE-01,0> Nbr: 1 Backorders:<<TEACH-AIR-01,BASE-01,0>,10>,"))
    ck("FAST demand reaches depot at same time", event("10", "<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,1>"))
    ck("depot issues sole spare", event("10", "<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock") and line("Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 0 Items:"))
    ck("spare downward thirty-hour task", event("10", "transport task 0 created from <DEPOT-01,0> to <BASE-01,0>") and event("10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started") and event("10", "transport task 0 starts with 1 items/systems, transport time: 30"))
    ck("spare remains unarrived through stop", "transport task 0 arrives with 1 items/systems" not in log and "<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" not in log and "Backorder removed" not in log)
    ck("explicit remove and unfinished fit", task("10", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> started") and task("10.1667", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed") and event("10", "planned to last for 0.166667 hours") and task("10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> started") and task("10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem") and "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing" not in log)
    ck("failed item upward two-hour task", event("10.1667", "<TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>") and event("10.1667", "transport task 2 created from <BASE-01,0> to <DEPOT-01,0>") and event("10.1667", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started") and event("10.1667", "transport task 2 starts with 1 items/systems, transport time: 2") and event("12.1667", "transport task 2 arrives with 1 items/systems"))
    ck("depot received failed same item", event("12.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1> from position <TEACH-LRU-01,0,BASE-01,0>") and task("12.1667", "item DIRP task 1 on <TEACH-LRU-01,0,1> started"))
    ck("depot repairs and restocks failed item", event("12.1667", "direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,1> starts performing, planned to last for 1 hours") and task("13.1667", "item DIRP task 1 on <TEACH-LRU-01,0,1> completed") and event("13.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>") and event("13.1667", "Put back replacement item <TEACH-LRU-01,0,1> to stock") and line("Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>,"))
    ck("aircraft repair never completed", re.search(r"^Time: [0-9.]+  system SURP task 0 on <TEACH-AIR-01,0> completed$", log, re.M) is None and "system SURP task 0 on <TEACH-AIR-01,0> subitem received" not in log and not event("36", "systems ready: 1"))
    ck("one unfinished logistics cycle", len(re.findall(r"Take replacement item", log)) == 1 and len(re.findall(r"Backorder added", log)) == 1 and len(re.findall(r"Backorder removed", log)) == 0 and len(re.findall(r"Put back replacement item", log)) == 1 and len(re.findall(r"transport task \d+ starts with 1 items/systems", log)) == 2 and len(re.findall(r"transport task \d+ arrives with 1 items/systems", log)) == 1 and len(re.findall(r"^Time: [0-9.]+  system SURP task \d+ .* started$", log, re.M)) == 1 and len(re.findall(r"^Time: [0-9.]+  item DIRP task \d+ .* started$", log, re.M)) == 1)

    result = report(run / "report-raw.json")
    summary = native.table_rows(result, "ResultSummary")
    system = native.table_rows(result, "SystemResults")
    stock = native.table_rows(result, "StockTotalResults")
    ck("mission summary one abort two cancellations", len(summary) == 1 and summary[0].get("NREP") == 1 and summary[0].get("MSUF") == 0 and abs(summary[0].get("MTMF", 0) - 1/3) < 1e-6)
    ck("system 72 intervals", len(system) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(system)))
    ck("one failure and unfinished system repair", system[19]["NFAIL"] == 1 and sum(row.get("NFAIL", 0) for row in system) == 1 and sum(row.get("NREPT", 0) for row in system) == 0 and abs(sum(row.get("NSYRP", 0) for row in system)*.5 - 1/6) < 1e-6)
    ck("waiting for item through stop", abs(sum(row.get("NSYWI", 0) for row in system)*.5 - 155/6) < 1e-6 and all(row["NSYWI"] == 1 for row in system[21:]))
    ck("terminal aircraft unready", system[-1]["NSYRY"] == 0 and system[-1]["NSYA"] == 0)
    ck("stock 72 intervals", len(stock) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(stock)))
    ck("stock first demand bin", stock[20]["NDF"] == 1 and sum(row["NDF"] for row in stock) == 1)
    ck("base backorder persists through stop", abs(sum(row["NBO"] for row in stock)*.5 - 26) < 1e-6 and all(row["NBO"] == 1 for row in stock[20:]) and stock[-1]["NBO"] == 1)
    ck("completion-based wait and downtime absent", all(not row.get("WT") for row in stock) and all(not row.get("SYDT") for row in system))
    parent_path = PARENT_RUN / "report-raw.json"
    ck("parent report SHA", sha(parent_path) == PARENT_REPORT_SHA)
    parent = report(parent_path)
    parent_summary = native.table_rows(parent, "ResultSummary")
    parent_system = native.table_rows(parent, "SystemResults")
    parent_stock = native.table_rows(parent, "StockTotalResults")
    ck("parent control", len(parent_summary) == 1 and abs(parent_summary[0]["MSUF"] - 2/3) < 1e-6 and sum(row["NFAIL"] for row in parent_system) == 1 and sum(row["NREPT"] for row in parent_system) == 1)
    ck("mission outcomes differ due to unfinished supply", summary[0]["MSUF"] == 0 and abs(parent_summary[0]["MSUF"] - 2/3) < 1e-6)
    ck("parent repair completed and terminal ready", sum(row["NREPT"] for row in parent_system) == 1 and parent_system[-1]["NSYRY"] == 1 and sum(row["NREPT"] for row in system) == 0 and system[-1]["NSYRY"] == 0)
    ck("backorder occupancy extends to stop", abs(sum(row["NBO"] for row in parent_stock)*.5 - 2) < 1e-6 and abs((sum(row["NBO"] for row in stock)-sum(row["NBO"] for row in parent_stock))*.5 - 24) < 1e-6)
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("parent FAST depot issue", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in parent_log)
    ck("parent two-hour down arrival", "Time: 10  transport task 0 starts with 1 items/systems, transport time: 2" in parent_log and "Time: 12  transport task 0 arrives with 1 items/systems" in parent_log)
    ck("parent ready after transport", "Time: 12.3333 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>" in parent_log)
    return {
        "schema": "simlox-e04-transit-v100-author-native-validation/v1",
        "case_id": "E04.var04", "run_id": run.name, "passed": not errors,
        "checks": count, "differences": errors,
        "observed_failure_hours": [9.8829],
        "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"),
        "report_sha256": sha(run / "report-raw.json"),
        "scope": "FAST_one_downward_spare_pending_at_36h_stop_cli_candidate",
        "publication_state": "not_published",
    }


if __name__ == "__main__":
    answer = validate(Path(sys.argv[1]))
    print(json.dumps(answer, indent=2))
    sys.exit(0 if answer["passed"] else 1)
