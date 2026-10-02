"""Read-only author replay of the frozen G11.var04 installed-item INHERIT pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import SHA, native_json, populated

HERE = Path(__file__).resolve().parent
RUNS = {arm: f"g11-var04-{arm}-v101-ssh-20261002-01"
        for arm in ("explicit-control", "inherited")}
CONTRACT_SHA = "42b965fb4c6a8576db032e3d56d559bb6fb31d82d65b790bb0f467ec6513e2be"
DIFF_SHA = "9f4ee2e54f78ce4189ac6bf2f5a6dc53bb477303b019846b5586576a33f6f7cb"
PARENT_SHA = "29dd9638ecaf5980b7ecf90ef41644afbbcca3a9b15f88dceb8f2fe3e5c32903"
PARENT_CLOSURE_SHA = "7a0977eefefb06be79860ad0982efa2f8c0d4259c8b0905e2a17a5fca9122ead"
DONOR_SHA = "9ee61443dc0cd0d774d5c1bc6f77343e87fe25ff9bda3772f2b8f37f520c2748"


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


def values(t: dict, field: str) -> list:
    names = [c["name"] for c in t["columns"]]
    return [row[names.index(field)] for inst in t["instances"] for row in inst["rows"]]


def intervals(t: dict) -> list[tuple[float, float]]:
    return list(zip(values(t, "STINT"), values(t, "ETINT")))


def times(log: str, pattern: str) -> list[float]:
    return [float(x) for x in re.findall(pattern, log)]


def audit_arm(arm: str, a: Audit) -> dict:
    run = HERE / "runs" / RUNS[arm]
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    a.need(sha(HERE / "contract.json") == CONTRACT_SHA, f"{arm} contract SHA")
    a.need(sha(HERE / "exact-diff.json") == DIFF_SHA, f"{arm} diff SHA")
    a.need(sha(HERE / f"native-input-{arm}.json") == SHA[arm], f"{arm} input SHA")
    a.need(contract["inputs"][arm]["sha256"] == SHA[arm], f"{arm} contract input")
    a.need(sha(HERE.parent / "D14-var01-monitored-item-pm-v1.0.1/native-input-monitored.json") == PARENT_SHA,
           f"{arm} D14 parent input")
    a.need(sha(HERE.parent / "D14-var01-monitored-item-pm-v1.0.1/runs/d14-var01-monitored-v101-ssh-20261002-01/closure.json") == PARENT_CLOSURE_SHA,
           f"{arm} D14 parent closure")
    a.need(sha(HERE.parent / "G11-var03-random-system-prelife-v1.0.0/native-input-equidist-control.json") == DONOR_SHA,
           f"{arm} G11 schema donor")

    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    a.need(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
    a.need(closure["arm"] == arm and closure["run_id"] == RUNS[arm] and closure["error"] is None,
           f"{arm} closure identity")
    a.need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} session0 SSH")
    a.need(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
           f"{arm} GUI guard")
    a.need(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{arm} mutex")
    a.need(invocation["prelife_log_option_before"] == "NO" and closure["prelife_log_option_after"] == "NO",
           f"{arm} registry restore")
    a.need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"],
           f"{arm} five native steps")
    for step in steps:
        a.need(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"],
               f"{arm} {step['name']} completed")
    for key, digest in closure["source_hashes_before"].items():
        a.need(closure["source_hashes_after"].get(key) == digest, f"{arm} source unchanged {key}")
    for key, digest in {"input": SHA[arm], "parent": PARENT_SHA, "parent_closure": PARENT_CLOSURE_SHA,
                        "prelife_donor": DONOR_SHA, "contract": CONTRACT_SHA, "exact_diff": DIFF_SHA}.items():
        a.need(closure["source_hashes_before"].get(key) == digest, f"{arm} pinned source {key}")
    a.need(len(closure["raw"]) == 13, f"{arm} raw file count")
    for name, seal in closure["raw"].items():
        path = run / name
        a.need(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"],
               f"{arm} raw seal {name}")

    a.need(roundtrip["passed"] and roundtrip["differences"] == [], f"{arm} roundtrip verdict")
    before = populated(native_json(run / "input.json"))
    after = populated(native_json(run / "roundtrip-raw.json"))
    a.need(len(before) == 23, f"{arm} authored populated table count")
    for name, body in before.items():
        a.need(after.get(name) == body, f"{arm} roundtrip {name}")
    a.need(roundtrip["populated_tables"] == sorted(before), f"{arm} roundtrip list")

    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    warning_ids = re.findall(r"\(warning #(\d+)\)", log)
    expected_warnings = ["108"] if arm == "explicit-control" else ["108", "419"]
    a.need(warning_ids == expected_warnings, f"{arm} classified warning IDs")
    a.need(f"Input conversion completed. Errors: 0, Warnings: {len(expected_warnings)}, Notes: 0" in log,
           f"{arm} conversion totals")
    a.need("(error #" not in log and "(notice #" not in log, f"{arm} no error/notice")

    prelife = (run / "model_Prelife.log").read_text(encoding="utf-8-sig", errors="replace")
    expected_age = 20.0 if arm == "explicit-control" else 60.0
    parsed = [(mid, float(age)) for mid, age in re.findall(
        r"\*\*(TEACH-AIR-01|POS-A|TEACH-LRU-01)\*\*[^*]+\*\* Age\[CALHOURS\]:([0-9.]+)", prelife)]
    a.need(parsed == [("TEACH-AIR-01", 60.0), ("POS-A", 60.0), ("TEACH-LRU-01", expected_age)],
           f"{arm} three-level Prelife Log")
    a.need("Prelifed Stock:" in prelife, f"{arm} stock prelife section")

    event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    due = 80.0 if arm == "explicit-control" else 40.0
    a.need(times(event, r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> started") == [due],
           f"{arm} original item PM system phase")
    a.need(times(event, r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed") == [due + .5],
           f"{arm} system phase completion")
    a.need(times(event, r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,0> started") == [due + .25],
           f"{arm} physical item0 PM start")
    a.need(times(event, r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,0> completed") == [due + 1.25],
           f"{arm} physical item0 PM end")
    a.need(len(re.findall(r"PMID: LRU-CAL100", event)) == 1 and "PMID: SYS-CAL1000" not in event,
           f"{arm} PM attribution")
    removed = re.findall(r"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is\s*<TEACH-LRU-01,0,(\d+)>", event)
    issued = re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", event)
    returned = re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock", event)
    a.need(removed == ["0"] and issued == ["1"] and returned == ["0"], f"{arm} physical stock route")
    a.need(not re.search(r"mission (started|success:|cancelled)", event, re.I), f"{arm} no missions")
    a.need("backorder" not in event.lower() and "(error #" not in event, f"{arm} no backorder/error")

    report = {t["name"]: t for t in native_json(run / "report-raw.json")["report"]["tables"]}
    a.need(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
           f"{arm} report tables")
    summary = report["ResultSummary"]
    for field, target in {"NREP": 1, "RTIUP": 96, "MSTF": 0, "MSUF": 0}.items():
        a.need(values(summary, field) == [target], f"{arm} summary {field}")
    for name in ("SystemResults", "StockTotalResults"):
        bins = intervals(report[name])
        a.need(len(bins) == 192 and bins[0] == (0, .5) and bins[-1] == (95.5, 96),
               f"{arm} {name} horizon")
        a.need(all(left[1] == right[0] for left, right in zip(bins, bins[1:])),
               f"{arm} {name} contiguous")
    system, stock = report["SystemResults"], report["StockTotalResults"]
    for field, total in {"NPMT": 1, "NPMS": 1, "NFAIL": 0, "NSYPM": 1}.items():
        a.need(sum(v or 0 for v in values(system, field)) == total, f"{arm} system {field}")
    for field, total in {"NBO": 0, "NDP": 1, "NWT": 1}.items():
        a.need(sum(v or 0 for v in values(stock, field)) == total, f"{arm} stock {field}")
    a.need(values(system, "NSYRY")[-1] == 1 and values(system, "NSYPM")[-1] == 0,
           f"{arm} terminal ready")
    a.need(values(stock, "PNB")[-1] == 1 and values(stock, "NBO")[-1] == 0,
           f"{arm} terminal stock")
    return {"arm": arm, "run_id": RUNS[arm], "closure_sha256": sha(run / "closure.json"),
            "prelife_log_sha256": sha(run / "model_Prelife.log"), "event_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "ages": parsed, "first_original_item_pm_hour": due,
            "removed_item_ids": removed, "issued_item_ids": issued, "returned_item_ids": returned}


def main() -> int:
    a = Audit()
    source_explicit = native_json(HERE / "native-input-explicit-control.json")
    source_inherited = native_json(HERE / "native-input-inherited.json")
    explicit_tables = {t["name"]: t for t in source_explicit["model"]["tables"]}
    inherited_tables = {t["name"]: t for t in source_inherited["model"]["tables"]}
    a.need({n for n in explicit_tables if explicit_tables[n] != inherited_tables[n]} ==
           {"ProblemDescription", "PrelifeData"}, "arm changed-table set")
    erows = explicit_tables["PrelifeData"]["instances"][0]["rows"]
    irows = inherited_tables["PrelifeData"]["instances"][0]["rows"]
    a.need(erows[:2] == irows[:2] and erows[2][:6] == irows[2][:6] and
           erows[2][6:] == ["FIXED", None] and irows[2][6:] == ["INHERIT", None],
           "item TYPE-only business contrast")
    arms = [audit_arm(arm, a) for arm in RUNS]
    result = {"schema": "simlox-g11-var04-inherit-item-prelife-author-replay/v1", "case_id": "G11",
              "variant_id": "G11.var04", "version": "1.0.1", "checks": a.checks,
              "passed_checks": a.checks - len(a.errors), "passed": not a.errors,
              "differences": a.errors, "arms": arms,
              "scope": "one three-level installed monitored-item CALHOURS inheritance contrast, first PM only",
              "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
