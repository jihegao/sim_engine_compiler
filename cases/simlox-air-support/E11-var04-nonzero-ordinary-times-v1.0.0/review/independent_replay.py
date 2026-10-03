"""Independent read-only standard-library replay of E11.var04 native evidence."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "E11-autonomous-support-gap-v1.0.0"
RUN = CASE / "runs" / "e11-var04-ordinary-times-v100-ssh-20261003-01"
PRUN = PARENT / "runs" / "e11-base-autom-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")


class Audit:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []

    def yes(self, value: bool, label: str) -> None:
        if value:
            self.passed += 1
        else:
            self.failures.append(label)

    def eq(self, actual: object, expected: object, label: str) -> None:
        self.yes(actual == expected, f"{label}: expected {expected!r}, got {actual!r}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, report: bool = False) -> dict | list:
    data = path.read_text(encoding="utf-8-sig")
    if report:
        data = re.sub(r",\s*([}\]])", r"\1", data)
    return json.loads(data)


def tables(path: Path, root: str = "model") -> dict[str, dict]:
    return {t["name"]: t for t in read(path, root == "report")[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [r for instance in table["instances"] for r in instance.get("rows", [])]


def records(table: dict) -> list[dict]:
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, r)) for r in rows(table)]


def event(a: Audit, log: str, hour: str, phrase: str) -> None:
    a.yes(any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines()), f"event h{hour}: {phrase}")


def main() -> dict:
    a = Audit()
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    invoke = read(RUN / "invocation.json")
    closure = read(RUN / "closure.json")
    steps = read(RUN / "steps.json")
    source = tables(CASE / "native-input.json")
    parent = tables(PARENT / "native-input.json")
    export = tables(RUN / "roundtrip-raw.json")
    result = tables(RUN / "report-raw.json", "report")
    parent_result = tables(PRUN / "report-raw.json", "report")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")

    a.eq(contract["variant_id"], "E11.var04", "contract identity")
    a.eq(sha(CASE / "native-input.json"), contract["native_input_sha256"], "child source pin")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "exact diff pin")
    a.eq(sha(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"], "parent source pin")
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
    a.eq(diff["changed_tables"], ["ProblemDescription", "StationStructure"], "declared changed tables")
    a.eq(set(source), set(parent), "same parent/child table set")
    a.eq(len(source), 32, "32 source tables")
    for name in sorted(source):
        a.eq(source[name]["columns"], parent[name]["columns"], f"schema {name}")
        if name not in {"ProblemDescription", "StationStructure"}:
            a.eq(source[name], parent[name], f"unchanged table {name}")
    a.eq([name for name in sorted(source) if source[name] != parent[name]], ["ProblemDescription", "StationStructure"], "actual changed tables")
    a.eq(len(diff["changes"]), 3, "three changed cells")
    for item in diff["changes"]:
        name = item["table"]
        old = rows(parent[name]); new = rows(source[name])
        col = next(i for i, c in enumerate(source[name]["columns"]) if c["name"] == item["column"])
        a.eq(old[item["row"]][col], item["before"], f"parent {name}.{item['column']}")
        a.eq(new[item["row"]][col], item["after"], f"child {name}.{item['column']}")
        actual = [(i, j) for i, (x, y) in enumerate(zip(old, new)) for j, (v, w) in enumerate(zip(x, y)) if v != w]
        expected = [(x["row"], next(j for j, c in enumerate(source[name]["columns"]) if c["name"] == x["column"])) for x in diff["changes"] if x["table"] == name]
        a.eq(actual, expected, f"only declared cells in {name}")
    link = records(source["StationStructure"])[0]
    a.eq((link["TFRMS"], link["TTOMS"]), (7, 11), "ordinary transport inputs")
    a.eq((link["PFRMS"], link["PTOMS"]), ("DOWN-POLICY", "DOWN-POLICY"), "matched policy unchanged")
    a.eq(source["TransportPolicyProfile"], parent["TransportPolicyProfile"], "ONDEM windows unchanged")

    a.eq(invoke["run_id"], RUN.name, "run identity")
    a.eq(invoke["input_sha256"], sha(CASE / "native-input.json"), "invocation input")
    a.eq(invoke["execution_mode"], "ssh_cli_v1", "SSH mode")
    a.eq(invoke["session_id"], 0, "session zero")
    a.yes(invoke["ssh_connection_present"] is True and "sshd.exe" in invoke["ssh_ancestor_names"], "SSH ancestry")
    a.eq(invoke["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "queue mutex")
    a.eq(invoke["gui"]["pid"], 13340, "GUI PID")
    a.eq(invoke["gui"]["session_id"], 1, "GUI separate session")
    a.eq(closure["invocation_sha256"], sha(RUN / "invocation.json"), "invocation seal")
    a.eq(closure["source_hashes_before"], closure["source_hashes_after"], "source frozen across run")
    a.eq(closure["source_hashes_before"], invoke["source_hashes_before"], "invocation source agreement")
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
        a.yes(path.is_file(), f"raw exists {name}")
        if path.is_file():
            a.eq(path.stat().st_size, meta["bytes"], f"raw size {name}")
            a.eq(sha(path), meta["sha256"], f"raw SHA {name}")
    a.eq(sha(RUN / "input.json"), sha(CASE / "native-input.json"), "run input copied")
    a.eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
    for step in steps:
        a.eq(step["exit_code"], 0, f"{step['name']} exit")
        a.eq(step["status"], "completed", f"{step['name']} completed")
        a.yes(step["gui_preserved"] is True, f"{step['name']} GUI preserved")
        a.eq(step["error"], None, f"{step['name']} error")
    authored = [name for name, table in source.items() if rows(table)]
    a.eq(len(authored), 22, "22 authored row-containing tables")
    a.eq(set(export), set(source), "native export table set")
    for name in sorted(authored):
        a.eq(export[name], source[name], f"exact roundtrip {name}")
    a.yes((RUN / "model.sxo").stat().st_size > 4, "nontrivial valid SXO")
    a.eq(re.findall(r"\(error #(\d+)\)", converter), [], "converter zero errors")
    a.eq(re.findall(r"\(warning #(\d+)\)", converter), ["108", "2076", "2077"], "converter warning codes")
    a.yes("TFRMS ignored for autonomous mission station: BASE-01" in converter, "TFRMS ignored warning text")
    a.yes("TTOMS ignored for autonomous mission station: BASE-01" in converter, "TTOMS ignored warning text")
    a.yes("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in converter, "converter totals")

    a.eq(sha(RUN / "model.log"), sha(PRUN / "model.log"), "complete event log byte parity")
    a.eq(set(result), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table names")
    a.yes(result["ProblemDescription"] != parent_result["ProblemDescription"], "description changed")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        a.eq(result[name], parent_result[name], f"all non-description {name} report rows equal")
    for name in ("SystemResults", "StockTotalResults"):
        got = records(result[name]); ref = records(parent_result[name])
        a.eq(len(got), 72, f"{name} 72 half-hour rows")
        for i, (row, old) in enumerate(zip(got, ref)):
            a.eq((row["STINT"], row["ETINT"]), (i / 2, (i + 1) / 2), f"{name} child interval {i}")
            a.eq(row, old, f"{name} complete interval {i} parity")
    summary = records(result["ResultSummary"])[0]
    a.eq((summary["NREP"], summary["MTMF"], summary["MSTF"], summary["MSUF"]), (1, 1, 1, 0.6666666865348816), "summary mission metrics")
    system = records(result["SystemResults"]); stock = records(result["StockTotalResults"])
    a.eq(sum(r["NSYMO"] * 0.5 for r in system), 6, "six operating aircraft-hours")
    a.eq(sum(r["NFAIL"] for r in system), 1, "one failure marker")
    a.eq(stock[20]["NBO"], 1, "h10 backorder")
    a.eq(stock[22]["NBO"], 0, "h11 backorder cleared")
    a.eq(stock[-1]["NBO"], 0, "terminal no backorder")
    a.eq(system[-1]["NSYRY"], 1, "terminal one ready aircraft")
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
    a.yes("Time: 11  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started" in log, "spare ID0 inward at h11")
    a.yes("Time: 11  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log, "failed ID1 outward at h11")
    a.eq(len(re.findall(r"mission aborted:", log)), 1, "one first-mission abort")
    a.eq(len(re.findall(r"mission success:", log)), 2, "two later successes")
    a.eq(len(re.findall(r"books resources|frees resources", log)), 0, "no resource lease")
    a.yes("Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in log, "terminal ready one")

    verdict = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "E11.var04",
        "run_id": RUN.name,
        "passed": not a.failures,
        "verdict": "GO: bounded ignored ordinary-time contrast" if not a.failures else "NO-GO: independent replay mismatch",
        "checks_passed": a.passed,
        "checks_total": a.passed + len(a.failures),
        "failures": a.failures,
        "evidence": {"closure_sha256": sha(RUN / "closure.json"), "parent_closure_sha256": sha(PRUN / "closure.json"), "event_log_sha256_identical": sha(RUN / "model.log"), "authored_tables_exact_roundtrip": len(authored), "system_stock_bins_each": 72, "ordinary_times_child_hours": [7, 11], "native_bidirectional_transport_hours_at_h11": 0},
        "limits": [
            "One AUTOM link, one ordinary-time contrast, one gap/reconnection/demand and one seed.",
            "Warnings #2076/#2077 explicitly describe ordinary TFRMS/TTOMS as ignored for autonomous BASE-01; byte parity confirms this run's behavior only.",
            "No other AUTOM topology, policy TPTIM override, item-specific route, GUI visual or cross-engine claim.",
        ],
    }
    OUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return verdict


if __name__ == "__main__":
    verdict = main()
    print(json.dumps({key: verdict[key] for key in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if verdict["passed"] else 1)
