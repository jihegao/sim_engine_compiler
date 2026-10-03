"""Independent standard-library, read-only replay of E11.var01 sealed native evidence."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "E11-autonomous-support-gap-v1.0.0"
RUN = CASE / "runs" / "e11-var01-local-v100-ssh-20261003-01"
PRUN = PARENT / "runs" / "e11-base-autom-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")


class Checks:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[str] = []

    def yes(self, condition: bool, label: str) -> None:
        if condition:
            self.passed += 1
        else:
            self.failed.append(label)

    def eq(self, actual: object, expected: object, label: str) -> None:
        self.yes(actual == expected, f"{label}: expected {expected!r}, got {actual!r}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native_report: bool = False) -> dict | list:
    text = path.read_text(encoding="utf-8-sig")
    if native_report:
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def table_map(path: Path, root: str = "model") -> dict[str, dict]:
    return {table["name"]: table for table in read(path, root == "report")[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance.get("rows", [])]


def records(table: dict) -> list[dict]:
    cols = [col["name"] for col in table["columns"]]
    return [dict(zip(cols, row)) for row in rows(table)]


def event(log: str, hour: str, phrase: str, a: Checks) -> None:
    a.yes(any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines()), f"h{hour} {phrase}")


def run() -> dict:
    a = Checks()
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    invoke = read(RUN / "invocation.json")
    closure = read(RUN / "closure.json")
    steps = read(RUN / "steps.json")
    source = table_map(CASE / "native-input.json")
    parent = table_map(PARENT / "native-input.json")
    exported = table_map(RUN / "roundtrip-raw.json")
    child_report = table_map(RUN / "report-raw.json", "report")
    parent_report = table_map(PRUN / "report-raw.json", "report")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (PRUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")

    a.eq(contract["variant_id"], "E11.var01", "contract identity")
    a.eq(sha(CASE / "native-input.json"), contract["native_input_sha256"], "input pin")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "diff pin")
    a.eq(sha(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"], "parent input pin")
    a.eq(sha(PRUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"], "parent closure pin")
    a.eq(sha(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"], "parent index pin")
    installed = {
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    }
    for key, path in installed.items():
        pin = "simlox_exe_sha256" if key == "simlox_exe" else "manual_pdf_sha256" if key == "manual" else "dictionary_sha256"
        a.eq(sha(path), contract["source"][pin], f"installed {key} pin")
    a.eq(diff["changed_tables"], ["ProblemDescription", "StockAllocation"], "declared source delta")
    a.eq(len(diff["changes"]), 2, "two changed cells")
    a.eq(set(source), set(parent), "same parent/child table set")
    a.eq(len(source), 32, "32 source tables")
    changes = []
    for name in sorted(source):
        a.eq(source[name]["columns"], parent[name]["columns"], f"schema {name}")
        if source[name] != parent[name]:
            changes.append(name)
        if name not in {"ProblemDescription", "StockAllocation"}:
            a.eq(source[name], parent[name], f"unchanged parent table {name}")
    a.eq(changes, sorted(diff["changed_tables"]), "actual changed table set")
    for item in diff["changes"]:
        name = item["table"]
        col = next(i for i, c in enumerate(source[name]["columns"]) if c["name"] == item["column"])
        old = rows(parent[name]); new = rows(source[name])
        a.eq(old[item["row"]][col], item["before"], f"parent {name}.{item['column']}")
        a.eq(new[item["row"]][col], item["after"], f"child {name}.{item['column']}")
        a.eq([(i, j) for i, (x, y) in enumerate(zip(old, new)) for j, (v, w) in enumerate(zip(x, y)) if v != w], [(item["row"], col)], f"sole changed cell in {name}")
    stocks = records(source["StockAllocation"])
    a.yes(any(r["STID"] == "BASE-01" and r["IID"] == "TEACH-LRU-01" and r["STSIZ"] == 1 for r in stocks), "one BASE opening spare source")
    a.yes(any(r["STID"] == "DEPOT-01" and r["IID"] == "TEACH-LRU-01" and r["STSIZ"] == 1 for r in stocks), "one unchanged DEPOT opening spare source")

    a.eq(invoke["run_id"], RUN.name, "run identity")
    a.eq(invoke["input_sha256"], sha(CASE / "native-input.json"), "invocation source")
    a.eq(invoke["execution_mode"], "ssh_cli_v1", "SSH CLI mode")
    a.eq(invoke["session_id"], 0, "session zero")
    a.yes(invoke["ssh_connection_present"] is True and "sshd.exe" in invoke["ssh_ancestor_names"], "SSH ancestor")
    a.eq(invoke["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "native queue")
    a.eq(invoke["gui"]["pid"], 13340, "GUI PID")
    a.eq(invoke["gui"]["session_id"], 1, "GUI session")
    a.eq(closure["invocation_sha256"], sha(RUN / "invocation.json"), "invocation seal")
    a.eq(closure["source_hashes_before"], closure["source_hashes_after"], "source stable")
    a.eq(closure["source_hashes_before"], invoke["source_hashes_before"], "source invocation/closure match")
    source_paths = {
        "input": CASE / "native-input.json", "parent": PARENT / "native-input.json",
        "parent_closure": PRUN / "closure.json", "parent_index": PARENT / "evidence-index.json",
        "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
        "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
        "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        **installed,
    }
    for key, path in sorted(source_paths.items()):
        a.eq(closure["source_hashes_before"][key], sha(path), f"source SHA {key}")
    a.eq(len(closure["raw"]), 12, "12 raw seals")
    for name, meta in sorted(closure["raw"].items()):
        path = RUN / name
        a.yes(path.is_file(), f"raw file {name}")
        if path.is_file():
            a.eq(path.stat().st_size, meta["bytes"], f"raw size {name}")
            a.eq(sha(path), meta["sha256"], f"raw SHA {name}")
    a.eq(sha(RUN / "input.json"), sha(CASE / "native-input.json"), "run input copy")
    a.eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
    for step in steps:
        a.eq(step["exit_code"], 0, f"{step['name']} exit")
        a.eq(step["status"], "completed", f"{step['name']} status")
        a.yes(step["gui_preserved"] is True, f"{step['name']} GUI preserved")
        a.eq(step["error"], None, f"{step['name']} error")
    authored = [name for name, table in source.items() if rows(table)]
    a.eq(len(authored), 22, "22 authored row-containing tables")
    a.eq(set(exported), set(source), "native export table set")
    for name in sorted(authored):
        a.eq(exported[name], source[name], f"exact native roundtrip {name}")
    a.yes((RUN / "model.sxo").stat().st_size > 4, "valid SXO")
    a.eq(re.findall(r"\(error #(\d+)\)", converter), [], "no conversion errors")
    a.eq(re.findall(r"\(warning #(\d+)\)", converter), ["108", "2076", "2077"], "warning classification")
    a.yes("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in converter, "converter totals")

    for hour, phrase in [
        ("9.8829", "critical random failure added"), ("9.8829", "mission aborted:"),
        ("10", "item requiring maintenance is <TEACH-LRU-01,0,2>"),
        ("10", "Take replacement item <TEACH-LRU-01,0,1> from stock"),
        ("10", "subitem received <TEACH-LRU-01,0,1>"),
        ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        ("10", "attached to  scheduled transport task 1"),
        ("10.1667", "attached to  scheduled transport task 0"),
        ("10.5", "system SURP task 0 on <TEACH-AIR-01,0> completed"),
        ("10.5", "System ready <TEACH-AIR-01,0>"),
        ("11", "scheduled transport task 0 starts with 1 items/systems, transport time: 0"),
        ("11", "scheduled transport task 1 starts with 1 items/systems, transport time: 0"),
        ("11", "scheduled transport task 0 arrives with 1 items/systems"),
        ("11", "scheduled transport task 1 arrives with 1 items/systems"),
        ("11", "Start repair of item <TEACH-LRU-01,0,2>"),
        ("11", "Put back replacement item <TEACH-LRU-01,0,0> to stock"),
        ("12", "Finished repair of item <TEACH-LRU-01,0,2>"),
        ("12", "Put back replacement item <TEACH-LRU-01,0,2> to stock"),
    ]:
        event(log, hour, phrase, a)
    a.yes("Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log.replace("\r\n", "\n"), "opening depot ID0 stock")
    a.yes("Time: 0 <TEACH-LRU-01,0,BASE-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in log.replace("\r\n", "\n"), "opening BASE ID1 stock")
    a.yes("Time: 11  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started" in log, "depot ID0 replenishes BASE")
    a.yes("Time: 11  transport request <<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log, "failed ID2 sent to DEPOT")
    a.eq(len(re.findall(r"Backorder added|Backorder removed", log)), 0, "no first-demand physical backorder")
    a.eq(len(re.findall(r"^Time: (?:9(?:\.\d+)?|10(?:\.\d+)?) .*transport request .* started", log, re.M)), 0, "no h9-11 physical transport")
    a.yes("Time: 11 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in log, "base receives replenishment ID0")
    a.yes("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in parent_log, "parent has local backorder")
    a.yes("Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready" in parent_log, "parent readiness follows reconnection")
    for mid, ordered, started, finished in [(0, 7, 8, 10), (1, 19, 20, 22), (2, 31, 32, 34)]:
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
        event(log, str(ordered), f"{mission} mission created:", a)
        event(log, str(started), f"{mission} mission starting, duration: 2 : <TEACH-AIR-01,0>", a)
        event(log, str(finished), f"{mission} {'aborted mission completed:' if mid == 0 else 'mission completed:'}", a)
        if mid:
            event(log, str(finished), f"{mission} mission success:", a)
    a.eq(len(re.findall(r"mission aborted:", log)), 1, "one mission abort")
    a.eq(len(re.findall(r"mission success:", log)), 2, "two mission successes")
    a.yes("Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in log, "terminal ready one")
    a.yes("Time: 12 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,2> to stock" in log, "terminal depot ID2 stock")

    a.eq(set(child_report), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table inventory")
    a.eq(rows(child_report["ResultSummary"]), rows(parent_report["ResultSummary"]), "summary equality")
    a.eq(records(child_report["ResultSummary"])[0]["MSUF"], 0.6666666865348816, "two successes of three")
    for name in ("SystemResults", "StockTotalResults"):
        new = records(child_report[name]); old = records(parent_report[name])
        a.eq(len(new), 72, f"{name} 72 bins")
        a.eq(len(old), 72, f"parent {name} 72 bins")
        for i, (x, y) in enumerate(zip(new, old)):
            a.eq((x["STINT"], x["ETINT"]), (i / 2, (i + 1) / 2), f"{name} child bin {i}")
            a.eq((y["STINT"], y["ETINT"]), (i / 2, (i + 1) / 2), f"{name} parent bin {i}")
    system_delta = {
        20: {"NSYRP": [0.3333333432674408, 1], "NSYWI": [0.6666666865348816, 0], "SYDT": [1.3333333730697632, 0.5]},
        21: {"NSYRY": [0, 1], "NSYUA": [1, 0], "NSYA": [0, 1], "NSYWI": [1, 0], "NREPT": [0, 1]},
        22: {"NSYRY": [0.3333333432674408, 1], "NSYUA": [0.6666666865348816, 0], "NSYA": [0.3333333432674408, 1], "NSYRP": [0.6666666865348816, 0], "NREPT": [1, 0]},
    }
    stock_delta = {
        20: {"NBO": [1, 0], "ROS": [1, 0], "ROST": [1, 0], "WT": [1, 0], "WTT": [1, 0], "WTS": [1, None], "PNB": [0, 1]},
        21: {"NBO": [1, 0], "PNB": [0, 1]},
    }
    for name, expected in (("SystemResults", system_delta), ("StockTotalResults", stock_delta)):
        new = records(child_report[name]); old = records(parent_report[name])
        for i, (x, y) in enumerate(zip(new, old)):
            actual = {key: [y[key], x[key]] for key in x if x[key] != y[key]}
            a.eq(actual, expected.get(i, {}), f"complete {name} bin {i} delta")
    system = records(child_report["SystemResults"])
    stock = records(child_report["StockTotalResults"])
    a.eq(sum(row["NSYMO"] * 0.5 for row in system), 6, "six operating aircraft-hours")
    a.eq(sum(row["NFAIL"] for row in system), 1, "one failure marker")
    a.eq(stock[20]["NBO"], 0, "no h10-10.5 backorder")
    a.eq(stock[21]["NBO"], 0, "no h10.5-11 backorder")
    a.eq(stock[-1]["NBO"], 0, "terminal no backorder")
    a.eq(system[-1]["NSYRY"], 1, "terminal report ready one")

    verdict = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "E11.var01",
        "run_id": RUN.name,
        "passed": not a.failed,
        "verdict": "GO: bounded autonomous local-spare satisfaction" if not a.failed else "NO-GO: independent replay mismatch",
        "checks_passed": a.passed,
        "checks_total": a.passed + len(a.failed),
        "failures": a.failed,
        "evidence": {
            "closure_sha256": sha(RUN / "closure.json"),
            "parent_closure_sha256": sha(PRUN / "closure.json"),
            "authored_tables_exact_roundtrip": len(authored),
            "report_bins_each": 72,
            "physical_local_spare_id": 1,
            "physical_depot_replenishment_id": 0,
            "physical_failed_item_id": 2,
            "local_system_ready_hour": 10.5,
            "reconnection_hour": 11,
            "local_backorder_count": 0,
        },
        "limits": [
            "One spare versus none, one first fault, one h9-11 gap, one seed and one support link.",
            "Local replacement resolves the system demand before reconnection; a distinct inventory replenishment remains queued and moves at h11.",
            "StockTotalResults is aggregate; physical item identities, inventories and both transport directions come from the native event log.",
            "No multiple-fault exhaustion, boundary-priority, larger stock, GUI visual or cross-engine claim.",
        ],
    }
    OUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return verdict


if __name__ == "__main__":
    verdict = run()
    print(json.dumps({key: verdict[key] for key in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if verdict["passed"] else 1)
