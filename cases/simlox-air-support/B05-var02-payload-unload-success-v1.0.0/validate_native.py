"""Author replay of the sealed B05.var02 successful-mission native pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, validate as roundtrip

HERE = Path(__file__).resolve().parent
RUNS = {
    "ordinary-control": ("b05-var02-ordinary-control-20260930-01", "21bd66e3ba54e22fb5d7c7c9b612892faf2999cb873f7dd34483e5880a607c9a"),
    "unloading": ("b05-var02-unloading-20260930-01", "29243344997dc519af9893625819d4c8eb7ca7ee1875f216af8859859ce75dd2"),
}
AIR = "<TEACH-AIR-01,0>"
MISSION = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, label: str) -> None:
    if not ok:
        raise ValueError(label)


def event(log: str, hour: str, body: str) -> None:
    pattern = rf"^Time: {re.escape(hour)} {re.escape(body)}(?:$|[,: ])"
    require(len(re.findall(pattern, log, re.M)) == 1, f"event {hour} {body}")


def report_table(doc: dict, name: str) -> list[dict]:
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    fields = [col["name"] for col in t["columns"]]
    return [dict(zip(fields, row)) for instance in t["instances"] for row in instance["rows"]]


def one(variant: str) -> dict:
    run_id, source_sha = RUNS[variant]
    run = HERE / "runs" / run_id
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "source closure")
    require(sha(run / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    require(invocation["variant"] == variant and invocation["input_sha256"] == source_sha, "input binding")
    require(invocation["case_id"] == "B05.var02" and invocation["case_version"] == "1.0.0-candidate", "case version")
    require(invocation["session_id"] == 0 and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "native/GUI session")
    require(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "native mutex")
    sources = {"input": HERE / f"{variant}-input.json", "parent": HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json",
               "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
               "runner_script": HERE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        require(sha(path) == closure["source_hashes_before"][name], f"source {name}")
    for name, record in closure["raw"].items():
        require((run / name).stat().st_size == record["bytes"] and sha(run / name) == record["sha256"], f"raw {name}")
    require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "native step names")
    require(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "native steps")
    rt = roundtrip(run)
    require(rt["passed"] and len(rt["populated_tables"]) == 18, "exact source roundtrip")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    require("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and "Total execution time:" in calc, "native conversion/calc")
    require(sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126], "conversion warnings")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for hour, body in [
        ("7", "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
        ("7", f"{AIR} preparation started, mission: {MISSION}"),
        ("7", f" payloading subtask 0 seqno 1 within system preparation task 0 on {AIR} starts performing, planned to last for 0.166667 hours"),
        ("7.16667", f" payloading subtask 0 seqno 1 within system preparation task 0 on {AIR} completed"),
        ("7.5", f"{AIR} preparation ended, mission: {MISSION}"),
        ("8", f"{MISSION} mission starting"), ("10", f"{MISSION} mission success"),
        ("10", f"{MISSION} mission completed"),
        ("10", f"{AIR} turnround started, mission: {MISSION}"),
    ]:
        event(log, hour, body)
    if variant == "unloading":
        event(log, "10", f" unloading subtask 2 seqno 1 within system turnround task 1 on {AIR} skipped")
        require(len(re.findall(r"unloading subtask 2 seqno 1 within system turnround task 1", log)) == 1, "no unloading work")
        end = "10"
    else:
        event(log, "10", f" subtask 2 seqno 1 within system turnround task 1 on {AIR} starts performing, planned to last for 0.166667 hours")
        event(log, "10.1667", f" subtask 2 seqno 1 within system turnround task 1 on {AIR} completed")
        end = "10.1667"
    event(log, end, f"{AIR} turnround ended, mission: {MISSION}")
    event(log, end, f"{AIR} nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>")
    report = parse_native(run / "report-raw.json")
    summary = report_table(report, "ResultSummary")
    system = report_table(report, "SystemResults")
    stock = report_table(report, "StockTotalResults")
    require(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36, "report summary")
    require(len(system) == len(stock) == 72, "report bin count")
    require(all(abs(r["ETINT"]-r["STINT"]-.5) < 1e-6 for r in system), "half-hour bins")
    bin10 = next(r for r in system if r["STINT"] == 10)
    expect_ready = 1 if variant == "unloading" else 2/3
    require(abs(bin10["NSYRY"]-expect_ready) < 2e-5 and abs(bin10["NSYMT"]-(1-expect_ready)) < 2e-5, "return-bin ready/turnround")
    require(system[-1]["STINT"] == 35.5 and system[-1]["NSYRY"] == system[-1]["NSYA"] == 1, "terminal ready")
    return {"variant": variant, "run_id": run_id, "input_sha256": source_sha,
            "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "native_steps": 5,
            "populated_source_tables": len(rt["populated_tables"]), "system_bins": len(system), "stock_bins": len(stock),
            "ready_fraction_10_to_10_5": bin10["NSYRY"], "turnround_fraction_10_to_10_5": bin10["NSYMT"]}


def main() -> None:
    results = {variant: one(variant) for variant in RUNS}
    a, b = (parse_native(HERE / "runs" / RUNS[v][0] / "report-raw.json") for v in RUNS)
    require(report_table(a, "ResultSummary") == report_table(b, "ResultSummary"), "paired summary")
    require(report_table(a, "StockTotalResults") == report_table(b, "StockTotalResults"), "paired stock")
    for x, y in zip(report_table(a, "SystemResults"), report_table(b, "SystemResults")):
        changed = {k for k in x if x[k] != y[k]}
        require(changed == ({"NSYRY", "NSYMA", "NSYMT"} if x["STINT"] == 10 else set()), "paired system bin delta")
    output = {"schema": "simlox-b05-var02-success-v100-author-native-validation/v1", "passed": True,
              "runs": results, "scope": "successful payloaded mission: built-in UNLOADING skipped versus equal-duration ordinary turnround performed",
              "publication_state": "candidate_pending_independent_review"}
    target = HERE / "review" / "author-native-validation-2026-09-30.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
