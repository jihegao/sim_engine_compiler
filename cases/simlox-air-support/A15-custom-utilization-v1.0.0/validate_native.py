"""Author replay of sealed A15 source acceptance and observable mission results."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, validate as roundtrip

HERE = Path(__file__).resolve().parent
RUNS = {
    "per-hour": ("a15-per-hour-20260930-01", "2100f7d1ae7725962483419571433d64c6ef92f8fb69078dd58f6835d90ed084"),
    "per-mission": ("a15-per-mission-20260930-01", "7d75161d524c65bc0ebeed60eb6cdb07cedc624a2fffe4174a3d3d85bd7012ea"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, label: str) -> None:
    if not ok:
        raise ValueError(label)


def report_table(doc: dict, name: str) -> list[dict]:
    obj = next(t for t in doc["report"]["tables"] if t["name"] == name)
    fields = [c["name"] for c in obj["columns"]]
    return [dict(zip(fields, row)) for i in obj["instances"] for row in i["rows"]]


def one(variant: str) -> dict:
    run_id, input_sha = RUNS[variant]
    run = HERE / "runs" / run_id
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "closure")
    require(sha(run / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    require(invocation["case_id"] == "A15" and invocation["variant"] == variant and invocation["input_sha256"] == input_sha, "identity")
    require(invocation["session_id"] == 0 and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI/session")
    require(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "queue")
    sources = {"input": HERE / f"{variant}-input.json", "parent": HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json",
               "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
               "runner_script": HERE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        require(sha(path) == closure["source_hashes_before"][name], f"source {name}")
    for name, record in closure["raw"].items():
        require((run / name).stat().st_size == record["bytes"] and sha(run / name) == record["sha256"], f"raw {name}")
    require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "steps")
    require(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "step result")
    rt = roundtrip(run)
    require(rt["passed"] and len(rt["populated_tables"]) == 14, "14 row-containing table roundtrip")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    require("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and "Total execution time:" in calc, "conversion/calc")
    require(sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126], "expected warnings")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    require("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log, "mission start")
    require("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log, "mission success")
    require("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed" in log, "mission completion")
    report = parse_native(run / "report-raw.json")
    names = [t["name"] for t in report["report"]["tables"]]
    require(names == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"], "default report table set")
    summary, system, stock = (report_table(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    require(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36, "summary")
    require(len(system) == len(stock) == 72 and system[-1]["STINT"] == 35.5, "72 bins")
    require(system[-1]["NSYRY"] == system[-1]["NSYA"] == 1, "terminal ready")
    return {"variant": variant, "run_id": run_id, "input_sha256": input_sha,
            "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "source_roundtrip": True,
            "native_steps": 5, "report_tables": names, "system_bins": len(system), "stock_bins": len(stock)}


def main() -> None:
    result = {variant: one(variant) for variant in RUNS}
    require(result["per-hour"]["model_log_sha256"] == result["per-mission"]["model_log_sha256"], "byte-identical event logs")
    a, b = (parse_native(HERE / "runs" / RUNS[v][0] / "report-raw.json") for v in RUNS)
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        require(report_table(a, name) == report_table(b, name), f"paired {name}")
    output = {"schema": "simlox-a15-v100-author-native-validation/v1", "passed": True,
              "runs": result, "scope": "custom KM per-hour and per-mission inputs convert, roundtrip, and yield identical observable mission output",
              "unverified": ["SOACC/custom-operation exposure total; default JSON report omits MissionOperation"],
              "publication_state": "candidate_pending_independent_review"}
    target = HERE / "review" / "author-native-validation-2026-09-30.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
