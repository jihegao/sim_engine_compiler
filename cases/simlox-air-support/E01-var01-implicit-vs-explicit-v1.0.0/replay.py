"""Read-only comparison of accepted D01 implicit and E01 explicit LRU replacement."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_native as native  # noqa: E402

CONTRACT_SHA = "ff683ebaa65214a1ed90f58ec9cfcea3e1820363e72318707e8fa48f777676e0"
SIMLOX_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
PINS = {
    "implicit": {
        "package": "D01-installed-lru-direct-repair-v1.0.0",
        "run": "d01-lru-v100-ssh-20260929-01",
        "input": "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93",
        "signoff": "e2c567a5db6b1af672fa279b448b36ff43ed68a90c2c529bdf5506ed2cd39832",
        "closure": "3642d558e98abd31f4510e213286182f9ce0d6eda0a86f6185c64f439f7e79f0",
        "row_tables": 18,
    },
    "explicit": {
        "package": "E01-local-spare-explicit-replacement-v1.0.0",
        "run": "e01-v100-ssh-20260929-01",
        "input": "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931",
        "signoff": "c52dd13ba1f6fab05032ebf80597940099241bb652f2c3a73a26edbf059c1110",
        "closure": "1713af4ca149f3fe3bd80bb8a033372475762eec787e36e38aeaddf8c385f5c6",
        "row_tables": 20,
    },
}
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
        raise ValueError(f"expected one {name} table")
    return found[0]


def row(source: dict, name: str) -> dict:
    t = table(source, name)
    if len(t["instances"]) != 1 or len(t["instances"][0]["rows"]) != 1:
        raise ValueError(f"expected one {name} row")
    return dict(zip([c["name"] for c in t["columns"]], t["instances"][0]["rows"][0]))


def rows(source: dict, name: str) -> list[dict]:
    t = table(source, name)
    return [dict(zip([c["name"] for c in t["columns"]], raw)) for inst in t["instances"] for raw in inst["rows"] if any(v is not None for v in raw)]


def main() -> dict:
    failures: list[str] = []
    checks = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    ck("reviewed contract byte pin", sha(HERE / "contract.json") == CONTRACT_SHA)
    contract = load(HERE / "contract.json")
    ck("contract identity and mode", contract.get("variant_id") == "E01.var01" and contract.get("evidence_mode", "").startswith("read-only"))
    arms = {}
    for label, pin in PINS.items():
        package = ROOT / pin["package"]
        run = package / "runs" / pin["run"]
        ck(f"{label} input pin", sha(package / "native-input.json") == pin["input"])
        ck(f"{label} signoff pin", sha(package / "cli-scope-signoff-2026-09-29.md") == pin["signoff"])
        ck(f"{label} closure pin", sha(run / "closure.json") == pin["closure"])
        source, invocation, closure = load(package / "native-input.json"), load(run / "invocation.json"), load(run / "closure.json")
        independent = load(package / "review" / "independent-native-review-2026-09-29.json")
        ck(f"{label} prior independent acceptance", independent.get("passed") is True and independent.get("differences") == [])
        ck(f"{label} invocation identity", invocation.get("run_id") == pin["run"] and closure.get("run_id") == pin["run"] and closure.get("invocation_sha256") == sha(run / "invocation.json"))
        ck(f"{label} source and executable stable", closure.get("source_hashes_before") == closure.get("source_hashes_after") and closure["source_hashes_before"]["input"] == pin["input"] and closure["source_hashes_before"]["simlox_exe"] == SIMLOX_SHA)
        ck(f"{label} SSH0 mutex and GUI", invocation.get("session_id") == 0 and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue" and invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
        ck(f"{label} complete raw set", set(closure.get("raw", {})) == RAW_NAMES)
        for name, seal in closure.get("raw", {}).items():
            path = run / name
            ck(f"{label} raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        ck(f"{label} native input copy", sha(run / "input.json") == pin["input"])
        steps = load(run / "steps.json")
        ck(f"{label} step names", [s.get("name") for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
        for step in steps:
            ck(f"{label} {step.get('name')} completed", step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
        roundtrip = load(run / "roundtrip-validation.json")
        ck(f"{label} exact source roundtrip", roundtrip.get("passed") is True and roundtrip.get("differences") == [] and len(roundtrip.get("populated_tables", [])) == pin["row_tables"] and native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        ck(f"{label} zero conversion errors", conversion is not None and tuple(map(int, conversion.groups())) == (0, 1, 0) and Counter(re.findall(r"\(warning #(\d+)\)", run_log)) == Counter({"108": 1}))
        ck(f"{label} valid output", (run / "model.sxo").stat().st_size > 4 and (run / "model.log").stat().st_size > 0 and (run / "report-raw.json").stat().st_size > 0)
        report = json.loads(native.remove_trailing_commas((run / "report-raw.json").read_bytes()))
        summary, system, stock = (native.table_rows(report, name) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{label} 72 aligned system bins", len(system) == 72 and all(r["STINT"] == n * .5 and r["ETINT"] == (n + 1) * .5 for n, r in enumerate(system)))
        ck(f"{label} 72 aligned stock bins", len(stock) == 72 and all(r["STINT"] == n * .5 and r["ETINT"] == (n + 1) * .5 for n, r in enumerate(stock)))
        ck(f"{label} outcome and terminal", len(summary) == 1 and abs(summary[0]["MSUF"] - 2 / 3) < 1e-6 and sum(r["NFAIL"] for r in system) == 1 and sum(r["NREPT"] for r in system) == 1 and sum(r["NDF"] for r in stock) == 1 and all(r["NBO"] == 0 for r in stock) and system[-1]["NSYRY"] == 1)
        arms[label] = {"source": source, "log": (run / "model.log").read_text(encoding="utf-8-sig", errors="replace"), "summary": summary, "system": system, "stock": stock}

    implicit, explicit = arms["implicit"], arms["explicit"]
    source_a, source_b = implicit["source"], explicit["source"]
    ta = {t["name"]: t for t in source_a["model"]["tables"]}
    tb = {t["name"]: t for t in source_b["model"]["tables"]}
    ck("same source schema and table order", list(ta) == list(tb) and all(ta[n]["columns"] == tb[n]["columns"] for n in ta))
    ck("exact four changed tables", {n for n in ta if ta[n] != tb[n]} == {"ProblemDescription", "SystemRepair", "Tasks", "TaskBreakDown"})
    ck("same half-hour SURPT, binding differs", row(source_a, "SystemRepair")["SURPT"] == row(source_b, "SystemRepair")["SURPT"] == .5 and row(source_a, "SystemRepair")["SURPTID"] is None and row(source_b, "SystemRepair")["SURPTID"] == "E01-SURP")
    ck("only system repair SURPTID cell differs", {k for k, v in row(source_a, "SystemRepair").items() if v != row(source_b, "SystemRepair")[k]} == {"SURPTID"})
    ck("implicit no explicit tasks", rows(source_a, "Tasks") == [] and rows(source_a, "TaskBreakDown") == [])
    ck("explicit task and sequence", len(rows(source_b, "Tasks")) == 1 and rows(source_b, "Tasks")[0]["TID"] == "E01-SURP" and [(r["SEQ"], r["SUTID"], r["DURN"]) for r in rows(source_b, "TaskBreakDown")] == [(1, "<REMOVE>", 1 / 6), (2, "<REPLACE>", 1 / 3)])
    ck("description only in description table", row(source_a, "ProblemDescription") != row(source_b, "ProblemDescription"))

    def event(log: str, time: str, fragment: str) -> bool:
        return sum(line.startswith(f"Time: {time} ") and fragment in line for line in log.splitlines()) == 1

    for label, arm, sequence, remove_end, return_time, remove_duration, fit_duration in (
        ("implicit", implicit, (0, 1), "10.25", "11.25", "0.25", "0.25"),
        ("explicit", explicit, (1, 2), "10.1667", "11.1667", "0.166667", "0.333333"),
    ):
        log = arm["log"]
        ck(f"{label} same first physical failure", event(log, "9.8829", "critical random failure added") and "subitem failed: <TEACH-LRU-01,0,1>" in log)
        ck(f"{label} opening spare and issue", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log and event(log, "10", "Take replacement item <TEACH-LRU-01,0,0> from stock"))
        ck(f"{label} remove starts and completes", event(log, "10", f"remove subitem subtask 0 seqno {sequence[0]} within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for {remove_duration} hours") and event(log, remove_end, f"remove subitem subtask 0 seqno {sequence[0]} within system SURP task 0 on <TEACH-AIR-01,0> completed"))
        ck(f"{label} physical fit schedule", event(log, remove_end, f"fit subitem subtask 1 seqno {sequence[1]} within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for {fit_duration} hours") and event(log, "10.5", f"fit subitem subtask 1 seqno {sequence[1]} within system SURP task 0 on <TEACH-AIR-01,0> completed"))
        ck(f"{label} removed ID1 repair and stock return", event(log, remove_end, "Item requiring maintenance arrives <TEACH-LRU-01,0,1>") and event(log, return_time, "Put back replacement item <TEACH-LRU-01,0,1> to stock"))
        ck(f"{label} ready and no backorder", event(log, "10.5", "System ready <TEACH-AIR-01,0>") and "Backorder added" not in log)

    ck("all parent summary rows equal", implicit["summary"] == explicit["summary"])
    ck("all 72 parent system rows equal", implicit["system"] == explicit["system"])
    ck("all 72 parent stock rows equal", implicit["stock"] == explicit["stock"])
    return {
        "schema": "simlox-e01-var01-derived-author-replay/v1",
        "case_id": "E01", "variant_id": "E01.var01", "version": "1.0.0",
        "evidence_mode": "read-only comparison of accepted D01 and E01 native runs",
        "passed": not failures, "checks": checks, "differences": failures,
        "parent_raw_seals": {"implicit": 12, "explicit": 12},
        "observed": {"failed_lru_id": 1, "issued_spare_id": 0, "first_failure_hour": 9.8829, "implicit_remove_fit_hours": [10, 10.25, 10.5], "explicit_remove_fit_hours": [10, 10.1667, 10.5], "item_restock_hours": {"implicit": 11.25, "explicit": 11.1667}, "system_report_rows_equal": implicit["system"] == explicit["system"], "stock_report_rows_equal": implicit["stock"] == explicit["stock"]},
        "limit": "explicitness and step durations vary together; no isolated mechanism causality",
        "publication_state": "not_published",
    }


if __name__ == "__main__":
    answer = main()
    print(json.dumps(answer, indent=2, ensure_ascii=False))
    sys.exit(0 if answer["passed"] else 1)
