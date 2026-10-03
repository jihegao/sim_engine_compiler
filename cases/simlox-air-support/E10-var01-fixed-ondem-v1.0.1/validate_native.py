"""Author replay for bounded E10.var01 transport policy evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_IDS = {a: f"e10-var01-{a}-v101-ssh-20261003-01" for a in ("fixed", "ondem")}
CLOSURE_SHA = {
    "fixed": "97465eeda1b3a9254db3ac023988218021880253ecacc7d3be9b4854d6b0544a",
    "ondem": "867fe911aa502e4fb55ae15a5488e2f6e132932f77b26ce725e552fe859e5d07",
}
RAW_NAMES = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "steps.json", "roundtrip-validation.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, passed: bool) -> None:
        nonlocal checks
        checks += 1
        if not passed:
            failures.append(label)

    contract = read(HERE / "contract.json")
    diff = read(HERE / "exact-diff.json")
    ck("contract identity and diff", contract["case_id"] == "E10" and contract["variant_id"] == "E10.var01" and contract["case_version"] == "1.0.1-candidate" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    parent = ROOT / "E04-upstream-transport-fast-v1.0.0"
    e02 = ROOT / "E02-zero-stock-local-backorder-v1.0.0"
    diagnostic = ROOT / contract["prior_diagnostic"]["package"]
    ck("accepted E04 parent", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] and sha(parent / "runs/e04-fast-v100-ssh-20260929-01/closure.json") == contract["accepted_parent"]["native_closure_sha256"])
    ck("accepted E02 prerequisite", sha(e02 / "native-input.json") == contract["supporting_prerequisite"]["input_sha256"] and sha(e02 / "runs/e02-v100-ssh-20260929-01/closure.json") == contract["supporting_prerequisite"]["native_closure_sha256"])
    ck("prior diagnostic closures", all(sha(diagnostic / "runs" / contract["prior_diagnostic"][f"{arm}_run_id"] / "closure.json") == contract["prior_diagnostic"][f"{arm}_closure_sha256"] for arm in RUN_IDS))
    ck("paired source and diff", all(sha(HERE / f"native-input-{arm}.json") == contract["arms"][arm]["input_sha256"] == diff["source_sha256"][arm] == sha(diagnostic / f"native-input-{arm}.json") for arm in RUN_IDS))
    data = {}
    for arm, run_id in RUN_IDS.items():
        run = HERE / "runs" / run_id
        ck(f"{arm} closure SHA", sha(run / "closure.json") == CLOSURE_SHA[arm])
        inv, closure, steps = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} run identity", inv["case_id"] == "E10" and inv["variant_id"] == "E10.var01" and inv["case_version"] == "1.0.1-candidate" and inv["arm"] == arm and inv["run_id"] == closure["run_id"] == run_id)
        ck(f"{arm} guarded SSH and GUI", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        ck(f"{arm} source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
        pins = inv["source_hashes_before"]
        ck(f"{arm} frozen source pins", all(pins[k] == sha(HERE / n) for k, n in (("input", f"native-input-{arm}.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
        ck(f"{arm} prior diagnostic pins", all(pins[f"prior_{other}_closure"] == contract["prior_diagnostic"][f"{other}_closure_sha256"] for other in RUN_IDS))
        ck(f"{arm} five steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} raw set", set(closure["raw"]) == RAW_NAMES)
        for name, meta in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw {name}", path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"])
        ck(f"{arm} copied input", sha(run / "input.json") == contract["arms"][arm]["input_sha256"])
        before = populated(parse_native(run / "input.json"))
        after = populated(parse_native(run / "roundtrip-raw.json"))
        rt = read(run / "roundtrip-validation.json")
        ck(f"{arm} 22 source tables roundtrip", len(before) == 22 and rt["passed"] is True and rt["differences"] == [] and all(after.get(k) == v for k, v in before.items()))
        ck(f"{arm} resource-free authored source", all(name not in before for name in ("Resource", "ResourceAllocation", "TaskResource")))
        conv = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} converter", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conv and Counter(re.findall(r"\(warning #(\d+)\)", conv)) == Counter({"108": 1}) and "(note #" not in conv.lower())
        ck(f"{arm} warning meaning", "(warning #108) Enabling simulation log may generate extensive data in log file" in conv)
        ck(f"{arm} native output", all((run / n).stat().st_size > 1000 for n in ("model.sxo", "model.log", "report-raw.json")))
        report = {t["name"]: t for t in parse_native(run / "report-raw.json")["report"]["tables"]}
        ck(f"{arm} selected report tables", {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(report) and "ResourceResults" not in report)
        system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
        ck(f"{arm} aligned 72 bins", len(system) == len(stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} failure and system repair", sum(r["NFAIL"] or 0 for r in system) == sum(r["NREPT"] or 0 for r in system) == 1)
        ck(f"{arm} one demand", sum(r["NDF"] or 0 for r in stock) == 1)
        ck(f"{arm} terminal readiness/backorder", system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0)
        ck(f"{arm} aggregate mission success", abs(rows(report["ResultSummary"])[0]["MSUF"] - 2/3) < 1e-5)
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} no resource demand", "requests resources: no resources needed" in log and "allocated to maintenance task" not in log)
        ck(f"{arm} one item cycle", log.count("critical random failure added") == 1 and log.count("Item demand arrives from pos <TEACH-AIR-01") == 1 and log.count("Backorder added") == 1 and log.count("Backorder removed") == 1 and log.count("Take replacement item") == 1 and log.count("Put back replacement item") == 1)
        ck(f"{arm} later missions only", "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success:" in log and "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success:" in log)
        data[arm] = {"log": log, "system": system, "stock": stock}
    fixed, ondem = data["fixed"], data["ondem"]
    for arm, d in data.items():
        ck(f"{arm} matched fault/demand", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in d["log"] and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives" in d["log"] and "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" in d["log"])
        ck(f"{arm} unchanged upward transport", "Time: 10.1667  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in d["log"] and "Time: 12.1667 <TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>" in d["log"])
        ck(f"{arm} depot repair/stock", "Time: 13.1667  item DIRP task 1 on <TEACH-LRU-01,0,1> completed" in d["log"] and "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in d["log"])
    ck("ONDEM immediate two-hour delivery", "Time: 10  transport task 1 starts with 1 items/systems, transport time: 2" in ondem["log"] and "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in ondem["log"] and "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 2" in ondem["log"] and "Time: 12.3333 <TEACH-AIR-01,BASE-01,0> System ready" in ondem["log"])
    ck("FIXED queued h10 and h11 dispatch", "Time: 10  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 0" in fixed["log"] and "Time: 11  scheduled transport task 0 starts with 1 items/systems, transport time: 2" in fixed["log"])
    ck("FIXED h13 delivery", "Time: 13 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in fixed["log"] and "Time: 13 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 3" in fixed["log"] and "Time: 13.3333 <TEACH-AIR-01,BASE-01,0> System ready" in fixed["log"])
    ck("paired backorder bins", abs(sum(r["NBO"] or 0 for r in fixed["stock"]) / 2 - 3) < 1e-5 and abs(sum(r["NBO"] or 0 for r in ondem["stock"]) / 2 - 2) < 1e-5)
    ck("paired readiness bins", abs((sum(r["NSYA"] or 0 for r in ondem["system"]) - sum(r["NSYA"] or 0 for r in fixed["system"])) / 2 - 1) < 1e-5)
    result = {"schema": "simlox-e10-var01-fixed-ondem-v101-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_two_arm_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
