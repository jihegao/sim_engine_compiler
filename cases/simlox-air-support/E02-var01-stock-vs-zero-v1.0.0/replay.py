"""Read-only, byte-pinned comparison of accepted E01 and E02 native evidence."""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_native as native  # noqa: E402

PINS = {
    "one": {
        "package": "E01-local-spare-explicit-replacement-v1.0.0",
        "run": "e01-v100-ssh-20260929-01",
        "input": "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931",
        "signoff": "c52dd13ba1f6fab05032ebf80597940099241bb652f2c3a73a26edbf059c1110",
        "closure": "1713af4ca149f3fe3bd80bb8a033372475762eec787e36e38aeaddf8c385f5c6",
        "independent": "independent-native-review-2026-09-29.json",
    },
    "zero": {
        "package": "E02-zero-stock-local-backorder-v1.0.0",
        "run": "e02-v100-ssh-20260929-01",
        "input": "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd",
        "signoff": "c28abcac8c3b8a55d0f58adf87ec3038555102d6b7bc2b35dc84ab9793e42ad6",
        "closure": "a8ec55f67c710be700cb4dc3663c7f79041d69c2021edb9924c1d0daddda04ef",
        "independent": "independent-native-review-2026-09-29.json",
    },
}
CONTRACT_SHA = "e7ddeeab754851d3fe5f18edb1f52d7ee98e875c0e1e57a9a681d2e3201d9f3d"
E05_SIGNOFF_SHA = "e7f4e82be24e09d258345e5f8084ac99e822e8384cb5c8698fbd1ea687105f2f"
SIMLOX_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
RAW_NAMES = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "steps.json", "roundtrip-validation.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(source: dict, name: str) -> dict:
    found = [t for t in source["model"]["tables"] if t["name"] == name]
    if len(found) != 1:
        raise ValueError(f"expected one {name} table, got {len(found)}")
    return found[0]


def field(source: dict, name: str, column: str) -> object:
    entry = table(source, name)
    cols = [c["name"] for c in entry["columns"]]
    if len(entry["instances"]) != 1 or len(entry["instances"][0]["rows"]) != 1:
        raise ValueError(f"expected one {name} row")
    return entry["instances"][0]["rows"][0][cols.index(column)]


def set_field(source: dict, name: str, column: str, value: object) -> None:
    entry = table(source, name)
    cols = [c["name"] for c in entry["columns"]]
    entry["instances"][0]["rows"][0][cols.index(column)] = value


def main() -> dict:
    failures: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    ck("reviewed contract byte pin", sha(HERE / "contract.json") == CONTRACT_SHA)
    contract = load(HERE / "contract.json")
    ck("contract identity", contract.get("variant_id") == "E02.var01" and contract.get("evidence_mode", "").startswith("read-only"))
    ck("E05 accepted prerequisite byte pin", sha(ROOT / "E05-local-repair-reissue-v1.0.0" / "cli-scope-signoff-2026-09-29.md") == E05_SIGNOFF_SHA)

    arms: dict[str, dict] = {}
    for label, pin in PINS.items():
        package = ROOT / pin["package"]
        run = package / "runs" / pin["run"]
        ck(f"{label} input pin", sha(package / "native-input.json") == pin["input"])
        ck(f"{label} signoff pin", sha(package / "cli-scope-signoff-2026-09-29.md") == pin["signoff"])
        ck(f"{label} closure pin", sha(run / "closure.json") == pin["closure"])
        source = load(package / "native-input.json")
        closure = load(run / "closure.json")
        invocation = load(run / "invocation.json")
        independent = load(package / "review" / pin["independent"])
        ck(f"{label} independent parent accepted", independent.get("passed") is True and independent.get("differences") == [])
        ck(f"{label} invocation and run identity", closure.get("run_id") == pin["run"] and invocation.get("run_id") == pin["run"] and closure.get("invocation_sha256") == sha(run / "invocation.json"))
        ck(f"{label} source and executable bound", closure.get("source_hashes_before") == closure.get("source_hashes_after") and closure["source_hashes_before"]["input"] == pin["input"] and closure["source_hashes_before"]["simlox_exe"] == SIMLOX_SHA)
        ck(f"{label} SSH0 and serial GUI guard", invocation.get("session_id") == 0 and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue" and invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
        ck(f"{label} 12 raw names", set(closure.get("raw", {})) == RAW_NAMES)
        for name, seal in closure.get("raw", {}).items():
            item = run / name
            ck(f"{label} raw {name}", item.is_file() and item.stat().st_size == seal["bytes"] and sha(item) == seal["sha256"])
        ck(f"{label} input/run match", sha(run / "input.json") == pin["input"])
        steps = load(run / "steps.json")
        ck(f"{label} five recorded steps", [s.get("name") for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
        for step in steps:
            ck(f"{label} step {step.get('name')}", step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
        roundtrip = load(run / "roundtrip-validation.json")
        ck(f"{label} 20-table roundtrip", roundtrip.get("passed") is True and roundtrip.get("differences") == [] and len(roundtrip.get("populated_tables", [])) == 20 and native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        ck(f"{label} clean conversion", conversion is not None and tuple(map(int, conversion.groups())) == (0, 1, 0) and Counter(re.findall(r"\(warning #(\d+)\)", run_log)) == Counter({"108": 1}))
        ck(f"{label} valid native result", (run / "model.sxo").stat().st_size > 4 and (run / "model.log").stat().st_size > 0 and (run / "report-raw.json").stat().st_size > 0)
        report = json.loads(native.remove_trailing_commas((run / "report-raw.json").read_bytes()))
        summary, system, stock = (native.table_rows(report, name) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{label} 72 aligned system rows", len(system) == 72 and all(r["STINT"] == n * 0.5 and r["ETINT"] == (n + 1) * 0.5 for n, r in enumerate(system)))
        ck(f"{label} 72 aligned stock rows", len(stock) == 72 and all(r["STINT"] == n * 0.5 and r["ETINT"] == (n + 1) * 0.5 for n, r in enumerate(stock)))
        ck(f"{label} one failure/repair/demand", sum(r["NFAIL"] for r in system) == 1 and sum(r["NREPT"] for r in system) == 1 and sum(r["NDF"] for r in stock) == 1)
        ck(f"{label} mission and terminal state", len(summary) == 1 and abs(summary[0]["MSUF"] - 2 / 3) < 1e-6 and system[-1]["NSYRY"] == 1 and system[-1]["NSYA"] == 1 and stock[-1]["NBO"] == 0)
        arms[label] = {"source": source, "run": run, "log": (run / "model.log").read_text(encoding="utf-8-sig", errors="replace"), "summary": summary, "system": system, "stock": stock}

    one, zero = arms["one"], arms["zero"]
    source_one = copy.deepcopy(one["source"])
    ck("same table schemas/order", [t["name"] for t in source_one["model"]["tables"]] == [t["name"] for t in zero["source"]["model"]["tables"]])
    ck("stock row target and value", field(source_one, "StockAllocation", "POINT") == "AIR_BASIC" and field(source_one, "StockAllocation", "IID") == "TEACH-LRU-01" and field(source_one, "StockAllocation", "STID") == "BASE-01" and field(source_one, "StockAllocation", "STSIZ") == 1 and field(zero["source"], "StockAllocation", "STSIZ") == 0)
    set_field(source_one, "StockAllocation", "STSIZ", 0)
    set_field(source_one, "ProblemDescription", "PDESC", field(zero["source"], "ProblemDescription", "PDESC"))
    ck("only source delta: description and STSIZ", source_one == zero["source"])

    def event(log: str, time: str, fragment: str) -> bool:
        return sum(line.startswith(f"Time: {time} ") and fragment in line for line in log.splitlines()) == 1

    a, b = one["log"], zero["log"]
    for label, log, failed_id in (("one", a, 1), ("zero", b, 0)):
        ck(f"{label} sole first aircraft failure", len(re.findall(r"^Time: [0-9.]+ <TEACH-AIR-01,0> critical random failure added", log, re.M)) == 1 and event(log, "9.8829", "critical random failure added") and f"subitem failed: <TEACH-LRU-01,0,{failed_id}>" in log)
        ck(f"{label} demand and removal", event(log, "10", f"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,{failed_id}>") and event(log, "10", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> starts performing") and event(log, "10.1667", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed"))
        ck(f"{label} failed item repair", event(log, "10.1667", f"Item requiring maintenance arrives <TEACH-LRU-01,0,{failed_id}>") and event(log, "11.1667", f"item DIRP task 1 on <TEACH-LRU-01,0,{failed_id}> completed"))

    ck("one-spare issue and physical fit", event(a, "0", "Stock initiated") and "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in a and event(a, "10", "Take replacement item <TEACH-LRU-01,0,0> from stock") and event(a, "10", "subitem received <TEACH-LRU-01,0,0>") and event(a, "10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing") and event(a, "10.5", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> completed") and event(a, "10.5", "System ready <TEACH-AIR-01,0>"))
    ck("one-spare return to stock", event(a, "11.1667", "Put back replacement item <TEACH-LRU-01,0,1> to stock") and "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in a and "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in a and "Backorder added" not in a)
    ck("zero-stock backorder and physical wait", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in b and event(b, "10", "Backorder added") and event(b, "10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem") and not event(b, "10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing"))
    ck("zero-stock same-item backorder clearance and fit", event(b, "11.1667", "Replacement item arrives <TEACH-LRU-01,0,0>") and event(b, "11.1667", "Backorder removed, waiting time was 1.16667") and event(b, "11.1667", "subitem received <TEACH-LRU-01,0,0>") and event(b, "11.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing") and event(b, "11.5", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> completed") and event(b, "11.5", "System ready <TEACH-AIR-01,0>") and "Put back replacement item" not in b)
    ck("same summary, no cross-run identity inference", one["summary"] == zero["summary"])
    ck("stock occupancy integrals", abs(sum(r["NBO"] for r in one["stock"]) * 0.5) < 1e-9 and abs(sum(r["NBO"] for r in zero["stock"]) * 0.5 - 7 / 6) < 1e-5)
    ck("system availability integrals", abs(sum(r["NSYA"] for r in one["system"]) * 0.5 - 26.5) < 1e-6 and abs(sum(r["NSYA"] for r in zero["system"]) * 0.5 - 25.5) < 1e-6)
    ck("bounded changed 72-bin rows", [r["STINT"] for r, s in zip(zero["system"], one["system"]) if r != s] == [10, 10.5, 11, 11.5] and [r["STINT"] for r, s in zip(zero["stock"], one["stock"]) if r != s] == [10, 10.5, 11])

    return {
        "schema": "simlox-e02-var01-read-only-author-replay/v1",
        "case_id": "E02", "variant_id": "E02.var01", "package_version": "1.0.0",
        "evidence_mode": "existing accepted E01/E02 native runs; no new native execution",
        "passed": not failures, "checks": checks, "differences": failures,
        "parent_raw_seals": {"one": len(load(one["run"] / "closure.json")["raw"]), "zero": len(load(zero["run"] / "closure.json")["raw"])},
        "observed": {
            "first_failure_hour_both": 9.8829,
            "failed_physical_lru_ids": {"stock_one": 1, "stock_zero": 0},
            "issued_spare_id_stock_one": 0,
            "opening_stock": {"one": 1, "zero": 0},
            "physical_fit_start_hours": {"one": 10.1667, "zero": 11.1667},
            "aircraft_ready_hours": {"one": 10.5, "zero": 11.5},
            "ready_integral_hours": {"one": sum(r["NSYA"] for r in one["system"]) * 0.5, "zero": sum(r["NSYA"] for r in zero["system"]) * 0.5},
            "backorder_integral_hours": {"one": sum(r["NBO"] for r in one["stock"]) * 0.5, "zero": sum(r["NBO"] for r in zero["stock"]) * 0.5},
        },
        "scope": "one fixed-seed accepted-stock-one versus accepted-stock-zero local LRU contrast only",
        "publication_state": "not_published",
    }


if __name__ == "__main__":
    answer = main()
    print(json.dumps(answer, indent=2, ensure_ascii=False))
    sys.exit(0 if answer["passed"] else 1)
