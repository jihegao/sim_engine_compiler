"""Independent standard-library replay of E11.var03; does not execute SIMLOX."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "E11-autonomous-support-gap-v1.0.0"
RUN = CASE / "runs" / "e11-var03-no-reconnect-v100-ssh-20261003-01"
PRUN = PARENT / "runs" / "e11-base-autom-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")


class Audit:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []

    def check(self, condition: bool, description: str) -> None:
        if condition:
            self.passed += 1
        else:
            self.failures.append(description)

    def eq(self, actual: object, expected: object, description: str) -> None:
        self.check(actual == expected, f"{description}: expected {expected!r}, got {actual!r}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native_report: bool = False) -> dict | list:
    value = path.read_text(encoding="utf-8-sig")
    if native_report:
        value = re.sub(r",\s*([}\]])", r"\1", value)
    return json.loads(value)


def tables(path: Path, root: str = "model") -> dict[str, dict]:
    return {t["name"]: t for t in read(path, root == "report")[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance.get("rows", [])]


def records(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def event(a: Audit, log: str, hour: str, phrase: str) -> None:
    a.check(any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines()), f"event h{hour}: {phrase}")


def main() -> dict:
    a = Audit()
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    inv = read(RUN / "invocation.json")
    closure = read(RUN / "closure.json")
    steps = read(RUN / "steps.json")
    source = tables(CASE / "native-input.json")
    parent = tables(PARENT / "native-input.json")
    exported = tables(RUN / "roundtrip-raw.json")
    result = tables(RUN / "report-raw.json", "report")
    control = tables(PRUN / "report-raw.json", "report")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (PRUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")

    a.eq(contract["variant_id"], "E11.var03", "contract identity")
    a.eq(sha(CASE / "native-input.json"), contract["native_input_sha256"], "child source pin")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "exact diff pin")
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
    a.eq(diff["parent_sha256"], sha(PARENT / "native-input.json"), "diff parent pin")
    a.eq(diff["source_sha256"], sha(CASE / "native-input.json"), "diff child pin")
    a.eq(diff["changed_tables"], ["ProblemDescription", "TransportPolicyProfile"], "declared changed tables")
    a.eq(set(source), set(parent), "same source table names")
    a.eq(len(source), 32, "32 source tables")
    for name in sorted(source):
        a.eq(source[name]["columns"], parent[name]["columns"], f"schema {name}")
        if name not in {"ProblemDescription", "TransportPolicyProfile"}:
            a.eq(source[name], parent[name], f"unchanged parent table {name}")
    a.eq([name for name in sorted(source) if source[name] != parent[name]], ["ProblemDescription", "TransportPolicyProfile"], "actual changed tables")
    a.eq(rows(parent["ProblemDescription"])[0][0], diff["description_before"], "parent description")
    a.eq(rows(source["ProblemDescription"])[0][0], diff["description_after"], "child description")
    a.eq(rows(parent["TransportPolicyProfile"]), [diff["retained_policy_row"], diff["deleted_policy_row"]], "parent policy pair")
    a.eq(rows(source["TransportPolicyProfile"]), [diff["retained_policy_row"]], "child policy first row only")
    a.eq(diff["retained_policy_row"][2] + diff["retained_policy_row"][5], 9, "isolation begins h9")
    a.eq(diff["deleted_policy_row"][2], 11, "deleted reconnection h11")
    a.eq(records(source["Station"])[0]["TYPE"], "AUTOM", "AUTOM station unchanged")
    a.eq(records(source["StockAllocation"])[0]["STSIZ"], 0, "empty local opening stock")

    a.eq(inv["run_id"], RUN.name, "run identity")
    a.eq(inv["input_sha256"], sha(CASE / "native-input.json"), "invocation input")
    a.eq(inv["execution_mode"], "ssh_cli_v1", "SSH mode")
    a.eq(inv["session_id"], 0, "session zero")
    a.check(inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"], "SSH ancestor")
    a.eq(inv["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "queue mutex")
    a.eq(inv["gui"]["pid"], 13340, "GUI PID")
    a.eq(inv["gui"]["session_id"], 1, "GUI separate session")
    a.eq(closure["invocation_sha256"], sha(RUN / "invocation.json"), "invocation seal")
    a.eq(closure["source_hashes_before"], closure["source_hashes_after"], "source frozen before/after")
    a.eq(closure["source_hashes_before"], inv["source_hashes_before"], "invocation source agreement")
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
        a.eq(closure["source_hashes_before"][key], sha(path), f"source seal {key}")
    a.eq(len(closure["raw"]), 12, "12 raw seals")
    for name, meta in sorted(closure["raw"].items()):
        path = RUN / name
        a.check(path.is_file(), f"raw exists {name}")
        if path.is_file():
            a.eq(path.stat().st_size, meta["bytes"], f"raw size {name}")
            a.eq(sha(path), meta["sha256"], f"raw SHA {name}")
    a.eq(sha(RUN / "input.json"), sha(CASE / "native-input.json"), "run input copied")
    a.eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five guarded steps")
    for step in steps:
        a.eq(step["exit_code"], 0, f"{step['name']} exit")
        a.eq(step["status"], "completed", f"{step['name']} status")
        a.check(step["gui_preserved"] is True, f"{step['name']} GUI preserved")
        a.eq(step["error"], None, f"{step['name']} error")
    authored = [name for name, table in source.items() if rows(table)]
    a.eq(len(authored), 22, "22 authored row-containing tables")
    a.eq(set(exported), set(source), "native export table names")
    for name in sorted(authored):
        a.eq(exported[name], source[name], f"exact native roundtrip {name}")
    a.check((RUN / "model.sxo").stat().st_size > 4, "valid SXO")
    a.eq(re.findall(r"\(error #(\d+)\)", converter), [], "zero converter errors")
    a.eq(re.findall(r"\(warning #(\d+)\)", converter), ["108", "2076", "2077"], "warning list")
    a.check("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in converter, "conversion totals")

    for hour, phrase in [
        ("0", "scheduled transport task 0 created from <BASE-01,0> to <DEPOT-01,0>, scheduled to start at 1.79769e+308"),
        ("0", "scheduled transport task 1 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 1.79769e+308"),
        ("9.8829", "critical random failure added"), ("9.8829", "mission aborted:"),
        ("10", "aborted mission completed:"),
        ("10", "system SURP task 0 on <TEACH-AIR-01,0> started"),
        ("10", "item requiring maintenance is <TEACH-LRU-01,0,1>"),
        ("10", "Backorder added"),
        ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        ("10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 1"),
        ("10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem"),
        ("10.1667", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached to  scheduled transport task 0"),
        ("20.3333", "mission cancelled:"), ("32.3333", "mission cancelled:"),
    ]:
        event(a, log, hour, phrase)
    a.eq(len(re.findall(r"^Time: .*transport request .* started", log, re.M)), 0, "no physical transport request starts through h36")
    a.eq(len(re.findall(r"^Time: .*transport task \d+ arrives", log, re.M)), 0, "no physical transport arrivals through h36")
    a.eq(len(re.findall(r"Backorder removed", log)), 0, "backorder never cleared")
    a.check("Time: 0 <TEACH-LRU-01,0,BASE-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in log.replace("\r\n", "\n"), "BASE stock starts empty")
    a.check("Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 0 Items:" in log.replace("\r\n", "\n"), "DEPOT stock reaches zero on reservation")
    a.eq(len(re.findall(r"Replacement item arrives", log)), 0, "no later spare arrival at either station")
    a.eq(len(re.findall(r"subitem received", log)), 0, "SURP never receives spare")
    a.eq(len(re.findall(r"^Time: [^\n]+  system SURP task 0 on <TEACH-AIR-01,0> completed$", log, re.M)), 0, "SURP remains unfinished")
    a.eq(len(re.findall(r"Start repair of item", log)), 0, "failed ID1 never reaches depot repair")
    a.eq(len(re.findall(r"Put back replacement item", log)), 0, "no stock return")
    a.eq(len(re.findall(r"mission success:", log)), 0, "no successful missions")
    a.eq(len(re.findall(r"mission aborted:", log)), 1, "first mission abort")
    a.eq(len(re.findall(r"mission cancelled:", log)), 2, "two later cancellations")
    a.eq(len(re.findall(r"books resources|frees resources", log)), 0, "no resource bookings")
    for mid, ordered, cancel in [(1, 19, "20.3333"), (2, 31, "32.3333")]:
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
        event(a, log, str(ordered), f"{mission} mission created:")
        event(a, log, str(ordered), f"{mission} mission waiting:  timeout at {cancel}")
        event(a, log, cancel, f"{mission} mission cancelled:")
    a.check("Time: 11  transport request <<TEACH-LRU-01,0,0>" in parent_log, "accepted parent moves spare at reconnect h11")
    a.check("Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready" in parent_log, "accepted parent becomes ready h11.3333")
    a.check("Time: 12 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in parent_log, "accepted parent repairs ID1")

    a.eq(set(result), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    summary = records(result["ResultSummary"])[0]
    parent_summary = records(control["ResultSummary"])[0]
    summary_delta = {key: [parent_summary[key], summary[key]] for key in summary if summary[key] != parent_summary[key]}
    a.eq(summary_delta, {"MTMF": [1, 0.3333333432674408], "MSTF": [1, 0.3333333432674408], "MSUF": [0.6666666865348816, 0], "STMF": [1, 0.3333333432674408]}, "complete summary delta")
    expected_system = {
        20: {"SYDT": [1.3333333730697632, None], "NSYDT": [1, 0]},
        22: {"NSYRY": [0.3333333432674408, 0], "NSYUA": [0.6666666865348816, 1], "NSYA": [0.3333333432674408, 0], "NSYRP": [0.6666666865348816, 0], "NSYWI": [0, 1], "NREPT": [1, 0]},
    }
    expected_stock = {20: {"WT": [1, None], "WTT": [1, None], "WTS": [1, None], "NWT": [1, 0]}}
    ordinary_ready = set(range(23, 38)) | set(range(44, 62)) | set(range(68, 72))
    reserved = {38, 39, 62, 63}
    operating = set(range(40, 44)) | set(range(64, 68))
    for i in ordinary_ready:
        expected_system[i] = {"NSYRY": [1, 0], "NSYUA": [0, 1], "NSYA": [1, 0], "NSYWI": [0, 1]}
    for i in reserved:
        expected_system[i] = {"NSYMA": [1, 0], "NSYMR": [1, 0], "NSYUA": [0, 1], "NSYA": [1, 0], "NSYWI": [0, 1]}
    for i in operating:
        expected_system[i] = {"NSYMA": [1, 0], "NSYMO": [1, 0], "NSYUA": [0, 1], "NSYA": [1, 0], "FTMO": [1, 0], "NSYWI": [0, 1], "STACC": [1, 0]}
    for i in range(22, 72):
        expected_stock[i] = {"NBO": [0, 1], "PNB": [1, 0]}
    for name, expected in (("SystemResults", expected_system), ("StockTotalResults", expected_stock)):
        child_rows = records(result[name]); parent_rows = records(control[name])
        a.eq(len(child_rows), 72, f"{name} 72 bins")
        a.eq(len(parent_rows), 72, f"parent {name} 72 bins")
        for i, (new, old) in enumerate(zip(child_rows, parent_rows)):
            a.eq((new["STINT"], new["ETINT"]), (i / 2, (i + 1) / 2), f"{name} child bin {i} time")
            a.eq((old["STINT"], old["ETINT"]), (i / 2, (i + 1) / 2), f"{name} parent bin {i} time")
            actual = {key: [old[key], new[key]] for key in new if new[key] != old[key]}
            a.eq(actual, expected.get(i, {}), f"complete {name} bin {i} delta")
    system = records(result["SystemResults"]); stock = records(result["StockTotalResults"])
    a.eq(sum(row["NSYMO"] * 0.5 for row in system), 2, "only first mission two operating aircraft-hours")
    a.eq(sum(row["NFAIL"] for row in system), 1, "one failure")
    a.eq(stock[20]["NBO"], 1, "BO begins h10")
    a.eq(stock[-1]["NBO"], 1, "BO persists to horizon")
    a.eq(system[-1]["NSYRY"], 0, "terminal no ready aircraft")
    a.eq(system[-1]["NSYWI"], 1, "terminal aircraft waiting item")

    verdict = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "E11.var03",
        "run_id": RUN.name,
        "passed": not a.failures,
        "verdict": "GO: bounded no-reconnection observation through h36" if not a.failures else "NO-GO: independent replay mismatch",
        "checks_passed": a.passed,
        "checks_total": a.passed + len(a.failures),
        "failures": a.failures,
        "evidence": {"closure_sha256": sha(RUN / "closure.json"), "parent_closure_sha256": sha(PRUN / "closure.json"), "authored_tables_exact_roundtrip": len(authored), "system_stock_report_bins_each": 72, "last_connected_hour": 9, "physical_transport_starts": 0, "depot_on_hand_after_reservation": 0, "base_on_hand_through_horizon": 0, "unresolved_backorder_at_horizon": 1, "terminal_ready_aircraft": 0, "mission_outcomes": ["abort", "cancel", "cancel"]},
        "limits": [
            "One h9-h36 disconnection, one initial h10 demand, one seed and one support link.",
            "Depot ID0 was removed from stock and attached to a scheduled request, but no physical transport started or arrived through h36; do not call it in transit.",
            "Failed ID1 likewise remained attached to an upward request; no depot repair/restock is observed.",
            "No finite later reconnection, local opening stock, repeated demand, GUI visual or cross-engine claim.",
        ],
    }
    OUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return verdict


if __name__ == "__main__":
    verdict = main()
    print(json.dumps({key: verdict[key] for key in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if verdict["passed"] else 1)
