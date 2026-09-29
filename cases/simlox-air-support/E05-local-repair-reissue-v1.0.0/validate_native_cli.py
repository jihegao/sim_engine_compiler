"""Read-only acceptance replay for local LRU repair, restock, and reissue."""
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

INPUT_SHA = "ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca"
PARENT_SHA = "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
PARENT_REPORT_SHA = "e23caaf4092fec476cbb83c4d7ac85b97301efc89db19937c9d6b756d7c27c77"
PARENT_RUN = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0" / "runs" / "e01-v100-ssh-20260929-01"
RAW = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "steps.json", "roundtrip-validation.json",
}
AIR = "<TEACH-AIR-01,0>"
ITEM = "<TEACH-LRU-01,0,"
STOCK = "<TEACH-LRU-01,0,BASE-01,0>"
# Times and task IDs below are observed native evidence, not predeclared seed promises.
CYCLES = (
    {"wave": 0, "failure": "9.25527", "return": "9.75527", "remove_end": "9.92193", "ready": "10.2553", "restock": "10.9219", "system_task": 0, "item_task": 1, "remove_task": 0, "fit_task": 1, "direct_task": 2, "failed_item": 1, "spare": 0},
    {"wave": 1, "failure": "21.9597", "return": "22", "remove_end": "22.1667", "ready": "22.5", "restock": "23.1667", "system_task": 2, "item_task": 3, "remove_task": 3, "fit_task": 4, "direct_task": 5, "failed_item": 2, "spare": 1},
    {"wave": 2, "failure": "33.3079", "return": "33.8079", "remove_end": "33.9746", "ready": "34.3079", "restock": "34.9746", "system_task": 4, "item_task": 5, "remove_task": 6, "fit_task": 7, "direct_task": 8, "failed_item": 3, "spare": 2},
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def validate(run: Path) -> dict:
    errors: list[str] = []
    count = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal count
        count += 1
        if not ok:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("contract input/parent", contract["native_input_sha256"] == INPUT_SHA and contract["parent"]["input_sha256"] == PARENT_SHA)
    ck("frozen input", sha(HERE / "native-input.json") == INPUT_SHA)
    ck("accepted parent", sha(HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json") == PARENT_SHA)
    ck("run input", sha(run / "input.json") == INPUT_SHA)
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    ck("invocation identity", invocation.get("case_id") == "E05" and invocation.get("run_id") == run.name)
    ck("invocation source", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == PARENT_SHA)
    for key, filename in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"), ("runner_script_sha256", "run_native_ssh.ps1"), ("checker_sha256", "check_roundtrip.py")):
        ck(f"bound {filename}", invocation.get(key) == sha(HERE / filename))
    ck("pinned executable", invocation.get("simlox_exe_sha256") == EXE_SHA)
    ck("session-0 SSH", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    ck("GUI identity", invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("host queue", invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
    ck("closure invocation", closure.get("invocation_sha256") == sha(run / "invocation.json"))
    ck("closure successful", closure.get("error") is None)
    ck("source hashes stable", closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("raw file set", set(closure.get("raw", {})) == RAW)
    for name, item in closure.get("raw", {}).items():
        path = run / name
        ck(f"raw {name}", path.is_file() and path.stat().st_size == item.get("bytes") and sha(path) == item.get("sha256"))
    steps = load(run / "steps.json")
    ck("step order", [x.get("name") for x in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
    planned = invocation.get("planned_commands", [])
    ck("command binding", len(planned) == 4 and all(planned[i].get("name") == steps[i].get("name") and planned[i].get("arguments") == steps[i].get("arguments") for i in range(4)))
    for step in steps:
        ck(f"step {step.get('name')}", step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
    roundtrip = load(run / "roundtrip-validation.json")
    ck("roundtrip checker", roundtrip.get("passed") is True and roundtrip.get("differences") == [] and len(roundtrip.get("populated_tables", [])) == 20)
    ck("all source rows preserved", native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", calc)
    ck("conversion clean", conversion is not None and int(conversion[1]) == 0 and int(conversion[2]) == 1 and Counter(re.findall(r"\(warning #(\d+)\)", calc)) == Counter({"108": 1}))

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = log.splitlines()

    def event(time: str, fragment: str) -> bool:
        return sum(line.startswith(f"Time: {time} ") and fragment in line for line in lines) == 1

    def task(time: str, body: str) -> bool:
        return lines.count(f"Time: {time}  {body}") == 1

    def followed_by_stock(time: str, fragment: str, expected: str) -> bool:
        matches = [i for i, line in enumerate(lines) if line.startswith(f"Time: {time} ") and fragment in line]
        return len(matches) == 1 and matches[0] + 1 < len(lines) and lines[matches[0] + 1] == expected

    def item(n: int) -> str:
        return f"{ITEM}{n}>"

    ck("opening stock", followed_by_stock("0", f"{STOCK} Stock initiated", f"  Stock at: {STOCK} Level: 1 Items:{item(0)},"))
    ck("three observed failures", len(re.findall(r"^Time: [0-9.]+ <TEACH-AIR-01,0> critical random failure added", log, re.M)) == len(CYCLES))
    ck("three system and item tasks", len(re.findall(r"^Time: [0-9.]+  system SURP task \d+ on <TEACH-AIR-01,0> started$", log, re.M)) == len(CYCLES) and len(re.findall(r"^Time: [0-9.]+  item DIRP task \d+ on <TEACH-LRU-01,0,\d+> started$", log, re.M)) == len(CYCLES))
    for x in CYCLES:
        wave, failure, arrival, remove_end, ready, restock = (x[k] for k in ("wave", "failure", "return", "remove_end", "ready", "restock"))
        sid, iid, rid, fid, did = (x[k] for k in ("system_task", "item_task", "remove_task", "fit_task", "direct_task"))
        failed, spare = item(x["failed_item"]), item(x["spare"])
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{wave}>"
        ck(f"wave {wave} failure/abort", event(failure, f"{AIR} critical random failure added") and event(failure, f"{mission} mission aborted:") and event(arrival, f"{mission} aborted mission completed:") and sum(f"subitem failed: {failed} connection path:" in line for line in lines) == 2)
        ck(f"wave {wave} demand and specific spare", task(arrival, f"system SURP task {sid} on {AIR} started") and event(arrival, f"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is {failed}") and event(arrival, f"Take replacement item {spare} from stock") and event(arrival, f"system SURP task {sid} on {AIR} subitem received {spare}"))
        ck(f"wave {wave} stock issue", followed_by_stock(arrival, f"Take replacement item {spare} from stock", f"  Stock at: {STOCK} Level: 0 Items:"))
        ck(f"wave {wave} explicit removal", task(arrival, f"remove subitem subtask {rid} seqno 1 within system SURP task {sid} on {AIR} started") and event(arrival, f"remove subitem subtask {rid} seqno 1 within system SURP task {sid} on {AIR} starts performing, planned to last for 0.166667 hours") and task(remove_end, f"remove subitem subtask {rid} seqno 1 within system SURP task {sid} on {AIR} completed"))
        ck(f"wave {wave} fit and recovery", task(remove_end, f"fit subitem subtask {fid} seqno 2 within system SURP task {sid} on {AIR} started") and event(remove_end, f"fit subitem subtask {fid} seqno 2 within system SURP task {sid} on {AIR} starts performing, planned to last for 0.333333 hours") and task(ready, f"fit subitem subtask {fid} seqno 2 within system SURP task {sid} on {AIR} completed") and task(ready, f"system SURP task {sid} on {AIR} completed") and event(ready, f"systems ready: 1 :{AIR}"))
        ck(f"wave {wave} direct item repair", event(remove_end, f"Item requiring maintenance arrives {failed} from position <TEACH-AIR-01,BASE-01,0>") and task(remove_end, f"item DIRP task {iid} on {failed} started") and event(remove_end, f"direct repair subtask {did} seqno 0 within item DIRP task {iid} on {failed} starts performing, planned to last for 1 hours") and task(restock, f"item DIRP task {iid} on {failed} completed"))
        ck(f"wave {wave} restock", followed_by_stock(restock, f"Put back replacement item {failed} to stock", f"  Stock at: {STOCK} Level: 1 Items:{failed},"))
        ck(f"wave {wave} order", float(failure) < float(arrival) < float(remove_end) < float(ready) < float(restock))
    ck("repaired item 1 issued on second demand", float(CYCLES[0]["restock"]) < float(CYCLES[1]["return"]) and CYCLES[1]["spare"] == CYCLES[0]["failed_item"])
    ck("repaired item 2 issued on third demand", float(CYCLES[1]["restock"]) < float(CYCLES[2]["return"]) and CYCLES[2]["spare"] == CYCLES[1]["failed_item"])
    ck("no backorder or transport", "backorder" not in log.lower() and "Transport" not in log)

    result = report(run / "report-raw.json")
    summary = native.table_rows(result, "ResultSummary")
    system = native.table_rows(result, "SystemResults")
    stock = native.table_rows(result, "StockTotalResults")
    ck("all three missions aborted", len(summary) == 1 and summary[0].get("NREP") == 1 and summary[0].get("MSUF") == 0 and len(re.findall(r"mission aborted:", log)) == len(CYCLES) and "mission success:" not in log)
    ck("system 72 intervals", len(system) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(system)))
    ck("three faults, repairs and 1.5 repair hours", sum(row["NFAIL"] for row in system) == 3 and sum(row["NREPT"] for row in system) == 3 and abs(sum(row["NSYRP"] for row in system)*.5 - 1.5) < 1e-5)
    ck("terminal aircraft ready", system[-1]["NSYRY"] == 1 and system[-1]["NSYA"] == 1)
    ck("stock 72 intervals", len(stock) == 72 and all(row["STINT"] == i*.5 and row["ETINT"] == (i+1)*.5 for i,row in enumerate(stock)))
    ck("three demands no backorders", sum(row["NDF"] for row in stock) == 3 and all(row["NBO"] == 0 for row in stock) and [stock[i]["NDF"] for i in (19,44,67)] == [1,1,1])
    parent_path = PARENT_RUN / "report-raw.json"
    ck("parent report hash", sha(parent_path) == PARENT_REPORT_SHA)
    parent = report(parent_path)
    parent_summary = native.table_rows(parent, "ResultSummary")
    parent_system = native.table_rows(parent, "SystemResults")
    parent_stock = native.table_rows(parent, "StockTotalResults")
    ck("accepted E01 control", len(parent_summary) == 1 and abs(parent_summary[0]["MSUF"] - 2/3) < 1e-6 and sum(row["NFAIL"] for row in parent_system) == 1 and sum(row["NREPT"] for row in parent_system) == 1 and sum(row["NDF"] for row in parent_stock) == 1)
    ck("extra fault/repair/demand vs E01", sum(row["NFAIL"] for row in system) == sum(row["NFAIL"] for row in parent_system)+2 and sum(row["NREPT"] for row in system) == sum(row["NREPT"] for row in parent_system)+2 and sum(row["NDF"] for row in stock) == sum(row["NDF"] for row in parent_stock)+2)
    return {
        "schema": "simlox-e05-v100-author-native-validation/v1",
        "case_id": "E05", "run_id": run.name, "passed": not errors,
        "checks": count, "differences": errors,
        "observed_failure_hours": [float(x["failure"]) for x in CYCLES],
        "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"),
        "report_sha256": sha(run / "report-raw.json"),
        "scope": "local_lru_repair_restock_reissue_cli_candidate",
        "publication_state": "not_published",
    }


if __name__ == "__main__":
    answer = validate(Path(sys.argv[1]))
    print(json.dumps(answer, indent=2))
    sys.exit(0 if answer["passed"] else 1)
