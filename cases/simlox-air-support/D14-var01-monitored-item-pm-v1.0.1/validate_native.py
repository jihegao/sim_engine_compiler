"""Author replay of the sealed D14.var01 MONIT contrast; never runs SIMLOX."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import SHA, native_json, populated

HERE = Path(__file__).resolve().parent
RUNS = {"monitored": "d14-var01-monitored-v101-ssh-20261002-01",
        "system-converted": "d14-var01-system-converted-v101-ssh-20261002-01"}
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
CONTRACT_SHA = "16a7534982a805869ee5e4d3e73b9f9156e55fb68244ec91d6716462dcd2668c"
DIFF_SHA = "574db345461b91e43e52d98199f936bcbc54a3db05b2d15c1a34d7d42e2bcb93"


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


def values(t: dict, column: str) -> list:
    names = [c["name"] for c in t["columns"]]
    return [row[names.index(column)] for inst in t["instances"] for row in inst["rows"]]


def intervals(t: dict) -> list[tuple[float, float]]:
    names = [c["name"] for c in t["columns"]]
    return [(float(row[names.index("STINT")]), float(row[names.index("ETINT")]))
            for inst in t["instances"] for row in inst["rows"]]


def audit_arm(arm: str, audit: Audit) -> dict:
    run = HERE / "runs" / RUNS[arm]
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    audit.need(sha(HERE / "contract.json") == CONTRACT_SHA, "contract SHA")
    audit.need(sha(HERE / "exact-diff.json") == DIFF_SHA, "diff SHA")
    audit.need(sha(HERE / f"native-input-{arm}.json") == SHA[arm], f"{arm} source SHA")
    audit.need(contract["arms"][arm]["input_sha256"] == SHA[arm], f"{arm} contract input pin")
    audit.need(contract["accepted_parent"]["input_sha256"] == PARENT_SHA, "parent contract pin")
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    audit.need(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation closure")
    audit.need(closure["error"] is None, f"{arm} closure error")
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
    audit.need(times(r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> started") == [10, 22, 34], f"{arm} system PM starts")
    audit.need(times(r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed") == [10.5, 22.5, 34.5], f"{arm} system PM ends")
    audit.need(times(r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,\d+> started") == [10.25, 22.25, 34.25], f"{arm} item PM starts")
    audit.need(times(r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,\d+> completed") == [11.25, 23.25, 35.25], f"{arm} item PM ends")
    removed = [int(x) for x in re.findall(r"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>", event)]
    taken = [int(x) for x in re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", event)]
    returned = [int(x) for x in re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock", event)]
    expected = {"monitored": {"removed": [0, 1, 0], "taken": [1, 0, 1], "returned": [0, 1, 0]},
                "system-converted": {"removed": [1, 2, 3], "taken": [0, 1, 2], "returned": [1, 2, 3]}}[arm]
    audit.need(removed == expected["removed"], f"{arm} removed physical IDs")
    audit.need(taken == expected["taken"], f"{arm} stock issue physical IDs")
    audit.need(returned == expected["returned"], f"{arm} stock return physical IDs")
    audit.need("mission cancelled" not in event and "backorder" not in event.lower(), f"{arm} no cancellation/backorder")
    report = native_json(run / "report-raw.json")["report"]["tables"]
    by_name = {t["name"]: t for t in report}
    audit.need(set(by_name) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{arm} report tables")
    system, stock = by_name["SystemResults"], by_name["StockTotalResults"]
    for label, table in (("system", system), ("stock", stock)):
        bins = intervals(table)
        audit.need(len(bins) == 72 and bins[0] == (0, .5) and bins[-1] == (35.5, 36), f"{arm} {label} 72 bins")
        audit.need(all(a[1] == b[0] for a, b in zip(bins, bins[1:])), f"{arm} {label} contiguous")
    for field, target in {"NPMT": 3, "NPMS": 3, "NFAIL": 0, "NSYPM": 3, "NSYMO": 12}.items():
        audit.need(sum(v or 0 for v in values(system, field)) == target, f"{arm} {field} total")
    for field, target in {"NBO": 0, "NDP": 3, "NWT": 3}.items():
        audit.need(sum(v or 0 for v in values(stock, field)) == target, f"{arm} {field} total")
    audit.need(values(system, "NSYRY")[-1] == 1 and values(system, "NSYPM")[-1] == 0, f"{arm} terminal system ready")
    audit.need(values(stock, "PNB")[-1] == 1 and values(stock, "NBO")[-1] == 0, f"{arm} terminal stock one/no BO")
    return {"arm": arm, "run_id": RUNS[arm], "closure_sha256": sha(run / "closure.json"),
            "removed_ids": removed, "issued_ids": taken, "returned_ids": returned,
            "report_sha256": sha(run / "report-raw.json"), "event_log_sha256": sha(run / "model.log")}


def main() -> int:
    audit = Audit()
    result = [audit_arm(arm, audit) for arm in RUNS]
    verdict = {"schema": "simlox-d14-var01-author-replay/v1", "case_id": "D14", "variant_id": "D14.var01",
               "version": "1.0.1", "checks": audit.checks, "passed_checks": audit.checks - len(audit.errors),
               "passed": not audit.errors, "differences": audit.errors, "arms": result,
               "scope": "native CLI MONIT physical-identity contrast only", "publication_state": "not_published"}
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
