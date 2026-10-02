"""Author replay of the frozen, matched D09.var03 MAXNC native pair."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {arm: HERE / "runs" / f"d09-var03-{arm}-v100-ssh-20261002-01" for arm in ("limit-2", "limit-3")}
INPUTS = {arm: HERE / f"native-input-{arm}.json" for arm in RUNS}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("contract identity", contract["case_id"] == "D09" and contract["variant_id"] == "D09.var03")
    ck("frozen exact diff", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    parent = HERE.parent / "D09-var02-unset-vs-finite-v1.0.0"
    d08 = HERE.parent / "D08-var03-criticality-v1.0.0"
    ck("accepted parent source and closure", sha(parent / "native-input-unset.json") == contract["accepted_parent"]["input_sha256"] and sha(parent / "runs/d09-var02-unset-v100-ssh-20261002-01/closure.json") == contract["accepted_parent"]["native_closure_sha256"])
    ck("earlier noncritical source and closure", sha(d08 / "native-input-traditional.json") == contract["earlier_noncritical_prerequisite"]["input_sha256"] and sha(d08 / "runs/d08-var03-traditional-v100-ssh-20261002-01/closure.json") == contract["earlier_noncritical_prerequisite"]["native_closure_sha256"])
    logs: dict[str, str] = {}
    summaries: dict[str, list[dict]] = {}
    systems: dict[str, list[dict]] = {}
    stocks: dict[str, list[dict]] = {}
    first_faults: dict[str, list[tuple[str, str]]] = {}
    for arm, run in RUNS.items():
        source_sha = contract["arms"][arm]["input_sha256"]
        ck(f"{arm} source/diff", sha(INPUTS[arm]) == source_sha == diff["children"][arm]["input_sha256"])
        invocation, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} sealed invocation", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"] and closure["source_hashes_before"]["input"] == source_sha and closure["source_hashes_before"]["exact_diff"] == contract["exact_diff_sha256"] and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"))
        ck(f"{arm} SSH/GUI/mutex", invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm} five completed native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} exact raw set", set(closure["raw"]) == RAW)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        original = populated(parse_native(run / "input.json"))
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        roundtrip = read(run / "roundtrip-validation.json")
        ck(f"{arm} 18-table roundtrip", sha(run / "input.json") == source_sha and roundtrip["passed"] is True and not roundtrip["differences"] and len(original) == 18 and all(exported.get(name) == value for name, value in original.items()))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} native conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
        ck(f"{arm} nonempty SXO/report/log", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "report-raw.json", "model.log")))
        log = logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        first = log.split("Time: 10 ", 1)[0] if arm == "limit-3" else log.split("Time: 19 ", 1)[0]
        first_faults[arm] = re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,0> noncritical random failure added, now\s+(\d+) failures", first)
        ck(f"{arm} three first-mission counts", first_faults[arm] == [("8.06276", "1"), ("8.16075", "2"), ("8.22615", "3")])
        for index in (0, 1, 2):
            ck(f"{arm} distinct installed LRU {index}", f"subitem failed: <TEACH-LRU-01,0,{index}>" in first)
        report = {table["name"]: table for table in parse_native(run / "report-raw.json")["report"]["tables"]}
        ck(f"{arm} report tables", {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(report))
        summaries[arm], systems[arm], stocks[arm] = (rows(report[name]) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
        system, stock = systems[arm], stocks[arm]
        ck(f"{arm} 72 aligned half-hour bins", len(summaries[arm]) == 1 and len(system) == len(stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} terminal ready", system[-1]["NSYRY"] == 1)
    ck("matched first fault sequence", first_faults["limit-2"] == first_faults["limit-3"])
    low, high = logs["limit-2"], logs["limit-3"]
    ck("limit 2 third fault aborts", "Time: 8.22615 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in low and "<TEACH-AIR-01,0> aborts its mission" in low)
    ck("limit 3 third fault allowed", "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in high and "mission aborted:" not in high)
    ck("critical versus noncritical priority", re.search(r"Repair task priority list:\s+< system SURP task 0.* C, 0\.5>,< system SURP task 1.* C, 0\.5>,< system SURP task 2.* C, 0\.5>", low) is not None and re.search(r"Repair task priority list:\s+< system SURP task 0.* NC, 0\.5>,< system SURP task 1.* NC, 0\.5>,< system SURP task 2.* NC, 0\.5>", high) is not None)
    ck("critical physical repair", "Time: 8.45229 <TEACH-AIR-01,BASE-01,0> System to repair" in low and all(f"Item requiring maintenance arrives <TEACH-LRU-01,0,{i}>" in low for i in (0, 1, 2)) and "remove subitem subtask" not in high)
    ck("stock ledger", low.count("Backorder added") == low.count("Backorder removed") == 9 and high.count("Backorder added") == 3 and "Backorder removed" not in high)
    ck("mission contrast", re.findall(r"mission (success|aborted):", low) == ["aborted"] * 3 and re.findall(r"mission (success|aborted):", high) == ["success"] * 3)
    ck("result summary contrast", summaries["limit-2"][0]["MSUF"] == 0 and summaries["limit-3"][0]["MSUF"] == 1)
    ck("failure and repair bins", sum(r["NFAIL"] for r in systems["limit-2"]) == 9 and sum(r["NREPT"] for r in systems["limit-2"]) == 9 and sum(r["NFAIL"] for r in systems["limit-3"]) == 3 and sum(r["NREPT"] for r in systems["limit-3"]) == 0)
    ck("stock demand and terminal backorders", sum(r["NDF"] for r in stocks["limit-2"]) == 9 and sum(r["NDF"] for r in stocks["limit-3"]) == 3 and stocks["limit-2"][-1]["NBO"] == 0 and stocks["limit-3"][-1]["NBO"] == 3)
    result = {"schema": "simlox-d09-var03-maxnc-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_maxnc_2_vs_3_three_installed_lru_native_cli", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}, indent=2))
        raise SystemExit(1)
