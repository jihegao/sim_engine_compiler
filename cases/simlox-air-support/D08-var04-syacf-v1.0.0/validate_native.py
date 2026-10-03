"""Author replay of the bounded D08.var04 SYACF Y/N contrast."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_IDS = {
    "yes": "d08-var04-syacf-yes-v100-ssh-20261003-01",
    "no": "d08-var04-syacf-no-v100-ssh-20261003-01",
}
CLOSURE_SHA = {
    "yes": "f3cf44140043afbd63df156ab65c8d4211bc093a3ccd05d6bb6a177e1ed6c207",
    "no": "7f2d177baefa1aaf2821b83a1e7dcbb3fd3ce8acac642ccf8cc880bcbe8bef1a",
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
    ck("contract identity and diff seal", contract["case_id"] == "D08" and contract["variant_id"] == "D08.var04" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    parent = ROOT / "D08-var01-mff-contrast-v1.0.0"
    d02 = ROOT / "D02-var01-traditional-op-hours-v1.0.0"
    ck("accepted direct parent", sha(parent / "native-input-default.json") == contract["direct_behavioral_parent"]["input_sha256"] and sha(parent / "runs/d08-var01-default-v100-ssh-20261002-01/closure.json") == contract["direct_behavioral_parent"]["native_closure_sha256"])
    ck("accepted catalog prerequisite", sha(d02 / "native-input.json") == contract["catalog_parent_prerequisite"]["input_sha256"] and sha(d02 / "runs/d02-var01-traditional-op-v100-ssh-20260930-01/closure.json") == contract["catalog_parent_prerequisite"]["native_closure_sha256"])
    ck("source pair", all(sha(HERE / f"native-input-{arm}.json") == contract["arms"][arm]["input_sha256"] == diff["source_sha256"][arm] for arm in RUN_IDS))
    data = {}
    for arm, run_id in RUN_IDS.items():
        run = HERE / "runs" / run_id
        ck(f"{arm} closure seal", sha(run / "closure.json") == CLOSURE_SHA[arm])
        invocation, closure, steps = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} invocation identity", invocation["case_id"] == "D08" and invocation["variant_id"] == "D08.var04" and invocation["run_id"] == run_id and invocation["arm"] == arm and invocation["input_sha256"] == contract["arms"][arm]["input_sha256"])
        ck(f"{arm} SSH queue and GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm} source pins", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
        ck(f"{arm} frozen components", all(invocation["source_hashes_before"][key] == sha(HERE / filename) for key, filename in (("contract", "contract.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
        ck(f"{arm} five native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} raw set", set(closure["raw"]) == RAW_NAMES)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        ck(f"{arm} copied input", sha(run / "input.json") == contract["arms"][arm]["input_sha256"])
        before = populated(parse_native(run / "input.json"))
        after = populated(parse_native(run / "roundtrip-raw.json"))
        roundtrip = read(run / "roundtrip-validation.json")
        ck(f"{arm} 22 authored table roundtrip", len(before) == 22 and roundtrip["passed"] is True and roundtrip["differences"] == [] and all(after.get(k) == v for k, v in before.items()))
        conv = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} converter diagnostics", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in conv and Counter(re.findall(r"\(warning #(\d+)\)", conv)) == Counter({"108": 1, "126": 1}) and "(note #" not in conv.lower())
        ck(f"{arm} warning interpretation", "(warning #108) Enabling simulation log may generate extensive data in log file" in conv and "(warning #126) This system contains no items: TEACH-AIR-01" in conv)
        ck(f"{arm} nonempty native outputs", all((run / n).stat().st_size > 1000 for n in ("model.sxo", "model.log", "report-raw.json")))
        report = {t["name"]: t for t in parse_native(run / "report-raw.json")["report"]["tables"]}
        ck(f"{arm} report table set", {"ResultSummary", "SystemResults", "ResourceResults", "StockTotalResults"}.issubset(report))
        system, resource, stock = (rows(report[n]) for n in ("SystemResults", "ResourceResults", "StockTotalResults"))
        ck(f"{arm} aligned 72 bins", len(system) == len(resource) == len(stock) == 72 and all(system[i]["STINT"] == resource[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == resource[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} one worker", all(r["NR"] == 1 and -1e-4 <= r["NRUM"] <= 1.0001 for r in resource))
        ck(f"{arm} no inventory", all(s["NDF"] == 0 and s["NBO"] == 0 for s in stock))
        ck(f"{arm} terminal readiness", system[-1]["NSYRY"] == 2 and resource[-1]["NRUM"] == 0 and stock[-1]["NBO"] == 0)
        ck(f"{arm} PM ledger", sum(s["NPMS"] for s in system) == 2 and sum(s["NPMT"] for s in system) == 2)
        ck(f"{arm} failure and repair ledger", sum(s["NFAIL"] for s in system) == sum(s["NREPT"] for s in system) == 1)
        ck(f"{arm} worker hours", abs(sum(r["NRUM"] / 2 for r in resource) - 7) < 1e-5)
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        data[arm] = {"log": log, "summary": rows(report["ResultSummary"])[0], "system": system}
    yes, no = data["yes"], data["no"]
    ck("matched failure clock", all(re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,\d+> critical random failure added", d["log"]) == ["22.6835"] for d in (yes, no)))
    ck("matched RISK launch", all("Time: 20 <RISK-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 3 : <TEACH-AIR-01,1>" in d["log"] for d in (yes, no)))
    ck("explicit Y abort", "Time: 22.6835 <RISK-MISSION,TEACH-UNIT,0,0,1> mission aborted:" in yes["log"] and "Time: 23 <RISK-MISSION,TEACH-UNIT,0,0,1> aborted mission completed:" in yes["log"] and "Time: 23 <RISK-MISSION,TEACH-UNIT,0,0,1> mission success:" not in yes["log"])
    ck("explicit N completion", "mission aborted:" not in no["log"] and "Time: 23 <RISK-MISSION,TEACH-UNIT,0,0,1> mission success:" in no["log"] and "Time: 23 <RISK-MISSION,TEACH-UNIT,0,0,1> mission completed: <TEACH-AIR-01,1>" in no["log"])
    ck("both return and repair", all("Time: 23  system DIRP task 0 on <TEACH-AIR-01,1> started" in d["log"] and "Time: 28  system DIRP task 0 on <TEACH-AIR-01,1> completed" in d["log"] for d in (yes, no)))
    ck("both PM sequence", all("Time: 24  system PM task 1 on <TEACH-AIR-01,0> started" in d["log"] and "Time: 24  system PM task 2 on <TEACH-AIR-01,1> started" in d["log"] and "Time: 29  system PM task 1 on <TEACH-AIR-01,0> completed" in d["log"] and "Time: 30  system PM task 2 on <TEACH-AIR-01,1> completed" in d["log"] for d in (yes, no)))
    ck("paired mission fraction", abs(yes["summary"]["MSUF"] - 2 / 3) < 1e-5 and no["summary"]["MSUF"] == 1)
    result = {"schema": "simlox-d08-var04-syacf-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_two_arm_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
