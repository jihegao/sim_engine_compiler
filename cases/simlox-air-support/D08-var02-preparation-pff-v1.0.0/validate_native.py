"""Author replay for the bounded D08.var02 PFF preparation contrast."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = HERE / "runs"
RUN_IDS = {
    "zero": "d08-var02-zero-v100-ssh-20261003-01",
    "positive": "d08-var02-positive-v100-ssh-20261003-01",
}
INPUT_SHA = {
    "zero": "66fabb956ef026430722e9cefa64a2154efb5c3661e1cbca727e7cf2add8e08e",
    "positive": "6a4521ee684a28ddf770347942fbbcd32cd58f1fcbeafe736a1ce723a0ccae17",
}
CLOSURE_SHA = {
    "zero": "e2c2e31d2b3aedb68a8088826ce1b2dcc44bf02af7008c2c127b9906c20a82ad",
    "positive": "bb57af9fe2f2125846f99a999765820c0105244ac96cdd95bc371a614c2a4119",
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
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r)) for inst in table["instances"] for r in inst["rows"]]


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
    ck("contract identity and frozen diff", contract["case_id"] == "D08" and contract["variant_id"] == "D08.var02" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    parent = ROOT / "D08-var01-mff-contrast-v1.0.0"
    d02 = ROOT / "D02-var01-traditional-op-hours-v1.0.0"
    ck("accepted direct parent", sha(parent / "native-input-default.json") == contract["direct_behavioral_parent"]["input_sha256"] and sha(parent / "runs/d08-var01-default-v100-ssh-20261002-01/closure.json") == contract["direct_behavioral_parent"]["native_closure_sha256"])
    ck("accepted catalog prerequisite", sha(d02 / "native-input.json") == contract["catalog_parent_prerequisite"]["input_sha256"] and sha(d02 / "runs/d02-var01-traditional-op-v100-ssh-20260930-01/closure.json") == contract["catalog_parent_prerequisite"]["native_closure_sha256"])
    ck("source pair", all(sha(HERE / f"native-input-{arm}.json") == INPUT_SHA[arm] == contract["arms"][arm]["input_sha256"] == diff["input_sha256"][arm] for arm in RUN_IDS))
    ck("pairwise PFF delta", diff["pairwise_business_difference"] == {"table": "MissionReliability", "key": ["RISK-MISSION", "TEACH-AIR-01", "<SYSTEM>"], "field": "PFF", "zero": 0.0, "positive": 10.0})
    data = {}
    for arm, run_id in RUN_IDS.items():
        run = RUNS / run_id
        ck(f"{arm} immutable closure", sha(run / "closure.json") == CLOSURE_SHA[arm])
        invocation, closure, steps = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} invocation identity", invocation["case_id"] == "D08" and invocation["variant_id"] == "D08.var02" and invocation["run_id"] == run_id and invocation["arm"] == arm and invocation["input_sha256"] == INPUT_SHA[arm])
        ck(f"{arm} SSH queue and GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm} source pins unchanged", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
        ck(f"{arm} frozen source components", invocation["source_hashes_before"]["contract"] == sha(HERE / "contract.json") and invocation["source_hashes_before"]["builder"] == sha(HERE / "build.py") and invocation["source_hashes_before"]["diff_builder"] == sha(HERE / "describe_diff.py") and invocation["source_hashes_before"]["checker"] == sha(HERE / "check_roundtrip.py") and invocation["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1"))
        ck(f"{arm} completed native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} raw set", set(closure["raw"]) == RAW_NAMES)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        ck(f"{arm} copied input", sha(run / "input.json") == INPUT_SHA[arm])
        before = populated(parse_native(run / "input.json"))
        after = populated(parse_native(run / "roundtrip-raw.json"))
        roundtrip = read(run / "roundtrip-validation.json")
        ck(f"{arm} 24 authored table roundtrip", len(before) == 24 and roundtrip["passed"] is True and roundtrip["differences"] == [] and all(after.get(k) == v for k, v in before.items()))
        conv = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} converter diagnostics", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in conv and Counter(re.findall(r"\(warning #(\d+)\)", conv)) == Counter({"108": 1, "126": 1}) and "(note #" not in conv.lower())
        ck(f"{arm} warning 108 logging interpretation", "(warning #108) Enabling simulation log may generate extensive data in log file" in conv)
        ck(f"{arm} warning 126 item-free interpretation", "(warning #126) This system contains no items: TEACH-AIR-01" in conv)
        ck(f"{arm} nonempty native outputs", all((run / n).stat().st_size > 1000 for n in ("model.sxo", "model.log", "report-raw.json")))
        report = {t["name"]: t for t in parse_native(run / "report-raw.json")["report"]["tables"]}
        ck(f"{arm} report table set", {"ResultSummary", "SystemResults", "ResourceResults", "StockTotalResults"}.issubset(report))
        system, resource, stock = (rows(report[n]) for n in ("SystemResults", "ResourceResults", "StockTotalResults"))
        ck(f"{arm} aligned 72 bins", len(system) == len(resource) == len(stock) == 72 and all(system[i]["STINT"] == resource[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == resource[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} worker capacity", all(r["NR"] == 1 and -1e-4 <= r["NRUM"] <= 1.0001 for r in resource))
        ck(f"{arm} no inventory demand/backorder", all(s["NDF"] == 0 and s["NBO"] == 0 for s in stock))
        ck(f"{arm} terminal state", system[-1]["NSYRY"] == 2 and resource[-1]["NRUM"] == 0 and stock[-1]["NBO"] == 0)
        ck(f"{arm} PM ledger", sum(s["NPMS"] for s in system) == 2 and sum(s["NPMT"] for s in system) == 2)
        ck(f"{arm} mission success fraction", abs(rows(report["ResultSummary"])[0]["MSUF"] - 2 / 3) < 1e-5)
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        data[arm] = {"log": log, "system": system, "resource": resource, "stock": stock, "summary": rows(report["ResultSummary"])[0]}
    zero, positive = data["zero"], data["positive"]
    ck("zero RISK preparation h19-20", "Time: 19 <TEACH-AIR-01,1> preparation started, mission: <RISK-MISSION" in zero["log"] and "Time: 20 <TEACH-AIR-01,1> preparation ended, mission: <RISK-MISSION" in zero["log"] and re.search(r"planned to last for\s+1 hours", zero["log"]) is not None)
    ck("zero no preparation fault", not any(19 < float(t) < 20 for t in re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,\d+> critical random failure added", zero["log"])))
    ck("zero later mission fault and abort", re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,\d+> critical random failure added", zero["log"]) == ["22.6835"] and "Time: 22.6835 <RISK-MISSION,TEACH-UNIT,0,0,1> mission aborted:" in zero["log"])
    ck("zero result and worker ledger", sum(s["NFAIL"] for s in zero["system"]) == sum(s["NREPT"] for s in zero["system"]) == 1 and abs(sum(r["NRUM"] / 2 for r in zero["resource"]) - 7) < 1e-5)
    ck("positive preparation faults", re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,\d+> critical random failure added", positive["log"]) == ["19.2684", "19.3807"] and "Time: 19 <TEACH-AIR-01,1> preparation started, mission: <RISK-MISSION" in positive["log"] and "Time: 19.2684 <TEACH-AIR-01,0> preparation started, mission: <RISK-MISSION" in positive["log"])
    ck("positive substitution and cancellation", "Time: 19.2684 <RISK-MISSION,TEACH-UNIT,0,0,1> mission allocates system: <TEACH-AIR-01,0>" in positive["log"] and "Time: 19.3807 <RISK-MISSION,TEACH-UNIT,0,0,1> mission cancelled:" in positive["log"] and "mission starting" not in positive["log"].split("Time: 19 <TEACH-UNIT> mission ordered: RISK-MISSION", 1)[1].split("Time: 31", 1)[0])
    ck("positive serial direct repairs", re.findall(r"Time: ([0-9.]+)  direct repair subtask .* (books|frees) resources", positive["log"]) == [("19.2684", "books"), ("24.2684", "frees"), ("24.2684", "books"), ("29.2684", "frees")])
    ck("positive result and worker ledger", sum(s["NFAIL"] for s in positive["system"]) == sum(s["NREPT"] for s in positive["system"]) == 2 and abs(sum(r["NRUM"] / 2 for r in positive["resource"]) - 12) < 1e-5)
    ck("paired outcome change", zero["log"] != positive["log"] and zero["summary"]["MTMF"] > positive["summary"]["MTMF"])
    result = {"schema": "simlox-d08-var02-pff-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_two_arm_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
