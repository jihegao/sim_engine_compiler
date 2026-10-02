"""Author replay of the frozen D14 age/reinstallation CLI evidence; never launches SIMLOX."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import SHA, native_json, populated

HERE = Path(__file__).resolve().parent
RUNS = {
    "monitored": "d14-var02-03-monitored-v100-ssh-20261002-01",
    "system-converted": "d14-var02-03-system-converted-v100-ssh-20261002-01",
}
CONTRACT_SHA = "e1a66466575088ce6aa4e96855ed972843b59e9fac25dfc87d5967bc015feb4d"
DIFF_SHA = "fad291803b7131004573178e1ca281bd7ea5fa404b8a5231ccfe9afdc39f6cf3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.errors: list[str] = []

    def need(self, truth: bool, message: str) -> None:
        self.checks += 1
        if not truth:
            self.errors.append(message)


def values(table: dict, column: str) -> list:
    names = [c["name"] for c in table["columns"]]
    return [row[names.index(column)] for inst in table["instances"] for row in inst["rows"]]


def intervals(table: dict) -> list[tuple[float, float]]:
    names = [c["name"] for c in table["columns"]]
    return [(float(row[names.index("STINT")]), float(row[names.index("ETINT")]))
            for inst in table["instances"] for row in inst["rows"]]


def audit_arm(arm: str, audit: Audit) -> dict:
    run = HERE / "runs" / RUNS[arm]
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    audit.need(sha(HERE / "contract.json") == CONTRACT_SHA, "contract SHA")
    audit.need(sha(HERE / "exact-diff.json") == DIFF_SHA, "diff SHA")
    audit.need(sha(HERE / f"native-input-{arm}.json") == SHA[arm], f"{arm} source SHA")
    audit.need(contract["inputs"][arm]["sha256"] == SHA[arm], f"{arm} contract input pin")
    parent = contract["accepted_parent"]["inputs"][arm]
    parent_dir = HERE / contract["accepted_parent"]["package"]
    parent_run = {
        "monitored": "d14-var01-monitored-v101-ssh-20261002-01",
        "system-converted": "d14-var01-system-converted-v101-ssh-20261002-01",
    }[arm]
    audit.need(sha(parent_dir / f"native-input-{arm}.json") == parent["sha256"], f"{arm} parent input")
    audit.need(sha(parent_dir / "runs" / parent_run / "closure.json") == parent["native_closure_sha256"], f"{arm} parent closure")
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    audit.need(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation closure")
    audit.need(closure["error"] is None and closure["arm"] == arm and closure["run_id"] == RUNS[arm], f"{arm} closure identity")
    audit.need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} SSH guard")
    audit.need(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0, f"{arm} GUI identity")
    audit.need(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{arm} mutex")
    audit.need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm} steps")
    for step in steps:
        audit.need(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"{arm} {step['name']} result")
    for key, value in closure["source_hashes_before"].items():
        audit.need(closure["source_hashes_after"][key] == value, f"{arm} source unchanged {key}")
    audit.need(closure["source_hashes_before"]["input"] == SHA[arm], f"{arm} runner source")
    audit.need(closure["source_hashes_before"]["contract"] == CONTRACT_SHA, f"{arm} runner contract")
    audit.need(closure["source_hashes_before"]["exact_diff"] == DIFF_SHA, f"{arm} runner diff")
    audit.need(len(closure["raw"]) == 12, f"{arm} 12 raw files")
    for name, entry in closure["raw"].items():
        path = run / name
        audit.need(path.is_file() and path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], f"{arm} sealed {name}")
    audit.need(roundtrip["passed"] is True and roundtrip["differences"] == [], f"{arm} roundtrip passed")
    audit.need(len(roundtrip["populated_tables"]) == 20, f"{arm} 20 authored tables")
    before = populated(native_json(run / "input.json"))
    after = populated(native_json(run / "roundtrip-raw.json"))
    for name, body in before.items():
        audit.need(after.get(name) == body, f"{arm} roundtrip {name}")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    audit.need("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in log, f"{arm} zero conversion errors")
    audit.need(re.findall(r"\(warning #(\d+)\)", log) == ["108"], f"{arm} warning 108 only")
    audit.need("(error #" not in log, f"{arm} no runtime error")
    event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    def times(pattern: str) -> list[float]:
        return [float(x) for x in re.findall(pattern, event)]
    audit.need(times(r"Time: ([0-9.]+) .*mission success:") == [10, 22, 34], f"{arm} mission success points")
    expected_times = {"monitored": [10, 34], "system-converted": [10, 22]}[arm]
    audit.need(times(r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> started") == expected_times, f"{arm} system PM starts")
    audit.need(times(r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed") == [x + .5 for x in expected_times], f"{arm} system PM ends")
    audit.need(re.findall(r"system PM task \d+ on <TEACH-AIR-01,0> PMID: ([A-Z0-9-]+)", event) == ["SYS-SWAP", "LRU-OP3"], f"{arm} PMID order")
    audit.need(times(r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,\d+> started") == [x + .25 for x in expected_times], f"{arm} item PM starts")
    audit.need(times(r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,\d+> completed") == [x + 1.25 for x in expected_times], f"{arm} item PM ends")
    removed = [int(x) for x in re.findall(r"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>", event)]
    taken = [int(x) for x in re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", event)]
    returned = [int(x) for x in re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock", event)]
    expected_ids = {"monitored": ([0, 1], [1, 0], [0, 1]), "system-converted": ([1, 2], [0, 1], [1, 2])}[arm]
    audit.need((removed, taken, returned) == expected_ids, f"{arm} physical ID route")
    audit.need("mission cancelled" not in event and "backorder" not in event.lower(), f"{arm} no cancellation/backorder")
    report = native_json(run / "report-raw.json")["report"]["tables"]
    by_name = {t["name"]: t for t in report}
    audit.need(set(by_name) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{arm} report tables")
    system, stock = by_name["SystemResults"], by_name["StockTotalResults"]
    for label, table in (("system", system), ("stock", stock)):
        bins = intervals(table)
        audit.need(len(bins) == 72 and bins[0] == (0, .5) and bins[-1] == (35.5, 36), f"{arm} {label} 72 bins")
        audit.need(all(a[1] == b[0] for a, b in zip(bins, bins[1:])), f"{arm} {label} contiguous")
    for field, target in {"NPMT": 2, "NPMS": 2, "NFAIL": 0, "NSYPM": 2, "NSYMO": 12}.items():
        audit.need(sum(v or 0 for v in values(system, field)) == target, f"{arm} {field} total")
    for field, target in {"NBO": 0, "NDP": 2, "NWT": 2}.items():
        audit.need(sum(v or 0 for v in values(stock, field)) == target, f"{arm} {field} total")
    audit.need(values(system, "NSYRY")[-1] == 1 and values(system, "NSYPM")[-1] == 0, f"{arm} terminal system ready")
    audit.need(values(stock, "PNB")[-1] == 1 and values(stock, "NBO")[-1] == 0, f"{arm} terminal stock one/no BO")
    return {"arm": arm, "run_id": RUNS[arm], "closure_sha256": sha(run / "closure.json"),
            "system_pm_starts": expected_times, "removed_ids": removed, "issued_ids": taken,
            "returned_ids": returned, "report_sha256": sha(run / "report-raw.json"),
            "event_log_sha256": sha(run / "model.log")}


def main() -> int:
    audit = Audit()
    result = [audit_arm(arm, audit) for arm in RUNS]
    verdict = {"schema": "simlox-d14-var02-03-author-replay/v1", "case_id": "D14",
               "variant_ids": ["D14.var02", "D14.var03"], "version": "1.0.0",
               "checks": audit.checks, "passed_checks": audit.checks - len(audit.errors),
               "passed": not audit.errors, "differences": audit.errors, "arms": result,
               "scope": "bounded native CLI differential timing and item identity; counter age inferred, not directly reported",
               "publication_state": "not_published"}
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
