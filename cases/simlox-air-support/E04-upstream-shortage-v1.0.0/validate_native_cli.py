"""Read-only, source-bound acceptance replay of E04 upstream shortage."""
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

INPUT_SHA = "826ee25fc20e2e690c46b0b61f27c4ce5b1d590891cc9d4cb6ab8f296cf7623f"
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
    ck("invocation identity", invocation.get("case_id") == "E04.var02" and invocation.get("run_id") == run.name)
    ck("E04 shortage evidence schemas", invocation.get("schema") == "simlox-e04-shortage-v100-native-candidate/ssh-cli-v1" and closure.get("schema") == "simlox-e04-shortage-v100-native-closure/v1")
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

    ck("one observed installed LRU failure", len(re.findall(r"^Time: [0-9.]+ <TEACH-AIR-01,0> critical random failure added", log, re.M)) == 1 and sum("subitem failed: <TEACH-LRU-01,0,0> connection path:" in item for item in lines) == 2)
    ck("first mission aborted", event("9.8829", "mission aborted:") and event("10", "aborted mission completed:"))
    ck("later missions succeeded", event("22", "mission success:") and event("34", "mission success:") and len(re.findall(r"mission success:", log)) == 2)
    ck("opening both stations empty", event("0", "<TEACH-LRU-01,0,BASE-01,0> Stock initiated") and event("0", "<TEACH-LRU-01,0,DEPOT-01,0> Stock initiated") and line("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:") and line("Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 0 Items:"))
    ck("base demand and backorder", task("10", "system SURP task 0 on <TEACH-AIR-01,0> started") and event("10", "<TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,0>") and event("10", "<TEACH-LRU-01,0,BASE-01,0> Backorder added") and line("Backorders at: <TEACH-LRU-01,0,BASE-01,0> Nbr: 1 Backorders:<<TEACH-AIR-01,BASE-01,0>,10>,"))
    ck("FAST depot demand and backorder", event("10", "<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,0>") and event("10", "<TEACH-LRU-01,0,DEPOT-01,0> Backorder added") and line("Backorders at: <TEACH-LRU-01,0,DEPOT-01,0> Nbr: 1 Backorders:<<TEACH-LRU-01,0,BASE-01,0>,10>,"))
    ck("no fictitious stock issue", "Take replacement item" not in log and "Put back replacement item" not in log)
    ck("explicit remove before waiting fit", task("10", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> started") and task("10.1667", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed") and event("10", "planned to last for 0.166667 hours") and task("10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> started") and event("10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem"))
    ck("failed item upward two-hour shipment", event("10.1667", "<TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,0>") and event("10.1667", "transport task 0 created from <BASE-01,0> to <DEPOT-01,0>") and event("10.1667", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started") and event("10.1667", "transport task 0 starts with 1 items/systems, transport time: 2") and event("12.1667", "transport task 0 arrives with 1 items/systems"))
    ck("depot receives and repairs same item", event("12.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,0> from position <TEACH-LRU-01,0,BASE-01,0>") and task("12.1667", "item DIRP task 1 on <TEACH-LRU-01,0,0> started") and event("12.1667", "direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,0> starts performing, planned to last for 1 hours") and task("13.1667", "item DIRP task 1 on <TEACH-LRU-01,0,0> completed"))
    ck("repaired item clears depot backorder before stock", event("13.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,0>") and event("13.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Backorder removed, waiting time was 3.16667") and line("Backorders at: <TEACH-LRU-01,0,DEPOT-01,0> Nbr: 0") and "Put back replacement item" not in log)
    ck("same item down two-hour shipment", event("13.1667", "transport task 2 created from <DEPOT-01,0> to <BASE-01,0>") and event("13.1667", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started") and event("13.1667", "transport task 2 starts with 1 items/systems, transport time: 2") and event("15.1667", "transport task 2 arrives with 1 items/systems"))
    ck("base backorder clears with same item", event("15.1667", "<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>") and event("15.1667", "<TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 5.16667") and line("Backorders at: <TEACH-LRU-01,0,BASE-01,0> Nbr: 0") and event("15.1667", "system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,0>"))
    ck("physical fit after receipt", event("15.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours") and task("15.5", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> completed"))
    ck("system restored", task("15.5", "system SURP task 0 on <TEACH-AIR-01,0> completed") and event("15.5", "systems ready: 1 :<TEACH-AIR-01,0>"))
    ck("one full shortage cycle", len(re.findall(r"Backorder added", log)) == 2 and len(re.findall(r"Backorder removed", log)) == 2 and len(re.findall(r"transport task \d+ starts with 1 items/systems", log)) == 2 and len(re.findall(r"transport task \d+ arrives with 1 items/systems", log)) == 2 and len(re.findall(r"^Time: [0-9.]+  system SURP task \d+ .* started$", log, re.M)) == 1 and len(re.findall(r"^Time: [0-9.]+  item DIRP task \d+ .* started$", log, re.M)) == 1)

    result = report(run / "report-raw.json")
    summary = native.table_rows(result, "ResultSummary")
    system = native.table_rows(result, "SystemResults")
    stock = native.table_rows(result, "StockTotalResults")
    ck("mission summary", len(summary) == 1 and summary[0].get("NREP") == 1 and abs(summary[0].get("MSUF", 0) - 2/3) < 1e-6)
    ck("system 72 intervals", len(system) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(system)))
    ck("one system failure and repair", sum(row.get("NFAIL", 0) for row in system) == 1 and sum(row.get("NREPT", 0) for row in system) == 1 and abs(sum(row.get("NSYRP", 0) for row in system)*.5 - .5) < 1e-6)
    ck("repair and five-hour item wait bins", system[19]["NFAIL"] == 1 and system[31]["NREPT"] == 1 and abs(sum(row.get("NSYWI", 0) for row in system)*.5 - 5) < 1e-6 and system[20]["SYDT"] == 5.5)
    ck("terminal aircraft ready", system[-1]["NSYRY"] == 1 and system[-1]["NSYA"] == 1)
    ck("stock 72 intervals", len(stock) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(stock)))
    ck("stock first demand bin", stock[20]["NDF"] == 1 and sum(row["NDF"] for row in stock) == 1)
    ck("single base demand wait", abs(sum(row["NBO"] for row in stock)*.5 - 31/6) < 1e-6 and abs(stock[20]["WT"] - 31/6) < 1e-6 and all(row["NBO"] == 0 for row in stock[31:]))
    parent_path = PARENT_RUN / "report-raw.json"
    ck("parent report SHA", sha(parent_path) == PARENT_REPORT_SHA)
    parent = report(parent_path)
    parent_summary = native.table_rows(parent, "ResultSummary")
    parent_system = native.table_rows(parent, "SystemResults")
    parent_stock = native.table_rows(parent, "StockTotalResults")
    ck("parent control", len(parent_summary) == 1 and abs(parent_summary[0]["MSUF"] - 2/3) < 1e-6 and sum(row["NFAIL"] for row in parent_system) == 1 and sum(row["NREPT"] for row in parent_system) == 1)
    ck("same mission outcome", summary == parent_summary)
    ck("readiness delayed nineteen sixths hour", abs(sum(row["NSYA"] for row in parent_system)*.5 - sum(row["NSYA"] for row in system)*.5 - 19/6) < 1e-6)
    ck("base backorder occupancy extended nineteen sixths hour", abs((sum(row["NBO"] for row in stock)-sum(row["NBO"] for row in parent_stock))*.5 - 19/6) < 1e-6)
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("parent FAST depot issue", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in parent_log)
    ck("parent two-hour down transport", "Time: 10  transport task 0 starts with 1 items/systems, transport time: 2" in parent_log)
    ck("parent ready after transport", "Time: 12.3333 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>" in parent_log)
    return {
        "schema": "simlox-e04-shortage-v100-author-native-validation/v1",
        "case_id": "E04.var02", "run_id": run.name, "passed": not errors,
        "checks": count, "differences": errors,
        "observed_failure_hours": [9.8829],
        "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"),
        "report_sha256": sha(run / "report-raw.json"),
        "scope": "FAST_upstream_zero_stock_depot_repaired_item_fulfills_backorder_cli_candidate",
        "publication_state": "not_published",
    }


if __name__ == "__main__":
    answer = validate(Path(sys.argv[1]))
    print(json.dumps(answer, indent=2))
    sys.exit(0 if answer["passed"] else 1)
