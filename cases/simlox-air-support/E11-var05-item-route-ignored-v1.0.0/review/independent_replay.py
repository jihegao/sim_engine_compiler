"""Independent read-only standard-library replay of E11.var05 native artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
PARENT = ROOT / "E11-autonomous-support-gap-v1.0.0"
TEMPLATE = ROOT / "E07-item-specific-transport-v1.0.1"
RUN = CASE / "runs" / "e11-var05-item-route-v100-ssh-20261003-01"
PRUN = PARENT / "runs" / "e11-base-autom-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")


class Audit:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        if condition:
            self.passed += 1
        else:
            self.failures.append(label)

    def eq(self, actual: object, expected: object, label: str) -> None:
        self.check(actual == expected, f"{label}: expected {expected!r}, got {actual!r}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native_report: bool = False) -> dict | list:
    data = path.read_text(encoding="utf-8-sig")
    if native_report:
        data = re.sub(r",\s*([}\]])", r"\1", data)
    return json.loads(data)


def tables(path: Path, root: str = "model") -> dict[str, dict]:
    return {t["name"]: t for t in load(path, root == "report")[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance.get("rows", [])]


def records(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def event(a: Audit, log: str, hour: str, phrase: str) -> None:
    a.check(any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines()), f"h{hour} {phrase}")


def main() -> dict:
    a = Audit()
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    invoke = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    steps = load(RUN / "steps.json")
    source = tables(CASE / "native-input.json")
    parent = tables(PARENT / "native-input.json")
    template = tables(TEMPLATE / "native-input.json")
    exported = tables(RUN / "roundtrip-raw.json")
    result = tables(RUN / "report-raw.json", "report")
    parent_result = tables(PRUN / "report-raw.json", "report")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")

    a.eq(contract["variant_id"], "E11.var05", "contract identity")
    a.eq(sha(CASE / "native-input.json"), contract["native_input_sha256"], "child input pin")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "diff pin")
    a.eq(sha(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"], "accepted parent input pin")
    a.eq(sha(PRUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"], "accepted parent closure pin")
    a.eq(sha(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"], "accepted parent index pin")
    a.eq(sha(TEMPLATE / "native-input.json"), contract["template"]["input_sha256"], "E07 schema template input pin")
    installed = {
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    }
    for key, path in installed.items():
        pin = "simlox_exe_sha256" if key == "simlox_exe" else "manual_pdf_sha256" if key == "manual" else "dictionary_sha256"
        a.eq(sha(path), contract["source"][pin], f"installed {key} pin")
    a.eq(diff["parent_sha256"], sha(PARENT / "native-input.json"), "diff parent pin")
    a.eq(diff["template_sha256"], sha(TEMPLATE / "native-input.json"), "diff E07 template pin")
    a.eq(diff["source_sha256"], sha(CASE / "native-input.json"), "diff child pin")
    a.eq(diff["changed_tables"], ["ProblemDescription"], "one changed parent table")
    a.eq(diff["added_tables"], ["ItemStationStructure"], "one added table")
    a.eq(set(source) - set(parent), {"ItemStationStructure"}, "only ItemStationStructure added")
    a.eq(set(parent) - set(source), set(), "no parent table removed")
    a.eq(len(source), 33, "33 child tables")
    for name in sorted(parent):
        a.eq(source[name]["columns"], parent[name]["columns"], f"schema {name}")
        if name != "ProblemDescription":
            a.eq(source[name], parent[name], f"unchanged parent table {name}")
    a.eq([name for name in sorted(parent) if source[name] != parent[name]], ["ProblemDescription"], "actual changed parent table")
    a.eq(rows(parent["ProblemDescription"])[0][0], diff["description_before"], "parent description")
    a.eq(rows(source["ProblemDescription"])[0][0], diff["description_after"], "child description")
    added = source["ItemStationStructure"]
    a.eq([c["name"] for c in added["columns"]], diff["added_columns"], "added schema")
    a.eq(added["columns"], template["ItemStationStructure"]["columns"], "E07 native column definitions")
    a.eq(rows(added), [diff["added_row"]], "sole authored item route")
    a.eq(diff["added_row"], ["TEACH-LRU-01", "BASE-01", "DEPOT-01", 5.0, 7.0, None, None, 1.0, "SLOW", None, None, None], "one LRU SLOW 5/7 row")
    a.eq(source["StationStructure"], parent["StationStructure"], "general bidirectional link unchanged")
    a.eq(source["TransportPolicyProfile"], parent["TransportPolicyProfile"], "ONDEM windows unchanged")

    a.eq(invoke["run_id"], RUN.name, "run identity")
    a.eq(invoke["input_sha256"], sha(CASE / "native-input.json"), "invocation input")
    a.eq(invoke["execution_mode"], "ssh_cli_v1", "SSH mode")
    a.eq(invoke["session_id"], 0, "session zero")
    a.check(invoke["ssh_connection_present"] is True and "sshd.exe" in invoke["ssh_ancestor_names"], "SSH ancestry")
    a.eq(invoke["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "queue mutex")
    a.eq(invoke["gui"]["pid"], 13340, "GUI PID")
    a.eq(invoke["gui"]["session_id"], 1, "GUI separate session")
    a.eq(closure["invocation_sha256"], sha(RUN / "invocation.json"), "invocation seal")
    a.eq(closure["source_hashes_before"], closure["source_hashes_after"], "sources frozen")
    a.eq(closure["source_hashes_before"], invoke["source_hashes_before"], "invocation source match")
    source_paths = {
        "input": CASE / "native-input.json", "parent": PARENT / "native-input.json",
        "parent_closure": PRUN / "closure.json", "parent_index": PARENT / "evidence-index.json",
        "template": TEMPLATE / "native-input.json", "contract": CASE / "contract.json",
        "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
        "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
        "runner_script": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        **installed,
    }
    for key, path in sorted(source_paths.items()):
        a.eq(closure["source_hashes_before"][key], sha(path), f"source SHA {key}")
    a.eq(len(closure["raw"]), 12, "12 raw artifact seals")
    for name, meta in sorted(closure["raw"].items()):
        path = RUN / name
        a.check(path.is_file(), f"raw exists {name}")
        if path.is_file():
            a.eq(path.stat().st_size, meta["bytes"], f"raw size {name}")
            a.eq(sha(path), meta["sha256"], f"raw SHA {name}")
    a.eq(sha(RUN / "input.json"), sha(CASE / "native-input.json"), "run input copied")
    a.eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
    for step in steps:
        a.eq(step["exit_code"], 0, f"{step['name']} exit")
        a.eq(step["status"], "completed", f"{step['name']} status")
        a.check(step["gui_preserved"] is True, f"{step['name']} GUI preserved")
        a.eq(step["error"], None, f"{step['name']} error")
    authored = [name for name, table in source.items() if rows(table)]
    a.eq(len(authored), 23, "23 authored row-containing tables")
    a.eq(set(exported), set(source), "native export table set")
    for name in sorted(authored):
        a.eq(exported[name], source[name], f"exact native roundtrip {name}")
    a.check((RUN / "model.sxo").stat().st_size > 4, "valid SXO")
    a.eq(re.findall(r"\(error #(\d+)\)", converter), [], "zero converter errors")
    a.eq(re.findall(r"\(warning #(\d+)\)", converter), ["108", "2076", "2077", "445"], "all warning codes")
    a.check("(warning #445) Data is ignored for autonomous mission station: BASE-01" in converter, "item-specific row ignored warning")
    a.check("Input conversion completed. Errors: 0, Warnings: 4, Notes: 0" in converter, "converter totals")

    a.eq(sha(RUN / "model.log"), sha(PRUN / "model.log"), "complete event log byte parity")
    a.eq(set(result), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table inventory")
    a.check(result["ProblemDescription"] != parent_result["ProblemDescription"], "report description changed")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        a.eq(result[name], parent_result[name], f"full non-description {name} parity")
    for name in ("SystemResults", "StockTotalResults"):
        child_rows = records(result[name]); parent_rows = records(parent_result[name])
        a.eq(len(child_rows), 72, f"{name} 72 bins")
        for i, (new, old) in enumerate(zip(child_rows, parent_rows)):
            a.eq((new["STINT"], new["ETINT"]), (i / 2, (i + 1) / 2), f"{name} interval {i}")
            a.eq(new, old, f"{name} all columns bin {i}")
    summary = records(result["ResultSummary"])[0]
    a.eq((summary["NREP"], summary["MTMF"], summary["MSTF"], summary["MSUF"]), (1, 1, 1, 0.6666666865348816), "summary mission metrics")
    system = records(result["SystemResults"]); stock = records(result["StockTotalResults"])
    a.eq(sum(r["NSYMO"] * 0.5 for r in system), 6, "six aircraft operating hours")
    a.eq(sum(r["NFAIL"] for r in system), 1, "one failure marker")
    a.eq(stock[20]["NBO"], 1, "h10 physical BO")
    a.eq(stock[22]["NBO"], 0, "BO cleared h11")
    a.eq(stock[-1]["NBO"], 0, "terminal BO zero")
    a.eq(system[-1]["NSYRY"], 1, "terminal ready one")
    for hour, phrase in [
        ("9.8829", "critical random failure added"), ("9.8829", "mission aborted:"),
        ("10", "Backorder added"), ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        ("10.1667", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached"),
        ("11", "scheduled transport task 0 starts with 1 items/systems, transport time: 0"),
        ("11", "scheduled transport task 1 starts with 1 items/systems, transport time: 0"),
        ("11", "scheduled transport task 0 arrives with 1 items/systems"),
        ("11", "scheduled transport task 1 arrives with 1 items/systems"),
        ("11", "Backorder removed, waiting time was 1"),
        ("11.3333", "System ready <TEACH-AIR-01,0>"),
        ("12", "Put back replacement item <TEACH-LRU-01,0,1> to stock"),
        ("22", "mission success:"), ("34", "mission success:"),
    ]:
        event(a, log, hour, phrase)
    a.check("Time: 11  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started" in log, "physical spare ID0 inward")
    a.check("Time: 11  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log, "physical failed ID1 outward")
    a.eq(len(re.findall(r"mission aborted:", log)), 1, "first mission abort")
    a.eq(len(re.findall(r"mission success:", log)), 2, "two later successes")
    a.eq(len(re.findall(r"books resources|frees resources", log)), 0, "no resource leases")
    a.check("Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in log, "terminal one ready")

    verdict = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "E11.var05",
        "run_id": RUN.name,
        "passed": not a.failures,
        "verdict": "GO: bounded ignored item-route observation" if not a.failures else "NO-GO: independent replay mismatch",
        "checks_passed": a.passed,
        "checks_total": a.passed + len(a.failures),
        "failures": a.failures,
        "evidence": {"closure_sha256": sha(RUN / "closure.json"), "parent_closure_sha256": sha(PRUN / "closure.json"), "identical_event_log_sha256": sha(RUN / "model.log"), "authored_tables_exact_roundtrip": len(authored), "system_stock_bins_each": 72, "added_item_route": "TEACH-LRU-01 SLOW 5h from BASE / 7h to BASE", "native_bidirectional_transport_hours_h11": 0},
        "limits": [
            "One item-specific TEACH-LRU-01 row, one autonomous link/demand/reconnection and one seed.",
            "Warning #445 explicitly says the item-specific data is ignored for autonomous BASE-01; event/report parity is observed for this source only.",
            "No precedence claim for other items, table types, policies, network structures, GUI visual behavior or cross-engine parity.",
        ],
    }
    OUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return verdict


if __name__ == "__main__":
    verdict = main()
    print(json.dumps({key: verdict[key] for key in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if verdict["passed"] else 1)
