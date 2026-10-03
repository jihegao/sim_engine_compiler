"""Read-only author replay for positive TSWOV ignored on ACTIVE redundancy."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "G10-var01-active-single-link-v1.0.0"
PARENT_RUN = PARENT / "runs/g10-var01-active-v100-ssh-20261003-01"
DIAGNOSTIC = ROOT / "G10-var05-active-tswov-ignored-v1.0.0/runs/g10-var05-active-tswov-v100-ssh-20261003-01"
INPUT_SHA = "0d45dfb8a553685e0cf8f7ba1d1ce685075f46567b09ab899ae080e8578c7230"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "model_Prelife.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for instance in table["instances"] for row in instance["rows"]]


def validate(run: Path) -> dict:
    errors: list[str] = []
    count = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal count
        count += 1
        if not ok:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("frozen input", sha(HERE / "native-input.json") == sha(run / "input.json") == contract["native_input_sha256"] == INPUT_SHA)
    ck("accepted parent", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"])
    ck("accepted parent closure", sha(PARENT_RUN / "closure.json") == contract["parent"]["native_closure_sha256"])
    ck("accepted parent signoff", sha(PARENT / "cli-scope-signoff-2026-10-03.md") == contract["parent"]["signoff_sha256"])
    ck("sealed diagnostic", sha(DIAGNOSTIC / "closure.json") == contract["prior_diagnostic"]["closure_sha256"])
    inv, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", inv.get("case_id") == "G10" and inv.get("case_version") == "1.0.1-candidate" and inv.get("run_id") == run.name)
    ck("input/parent bound", inv.get("input_sha256") == INPUT_SHA and inv.get("parent_sha256") == contract["parent"]["input_sha256"])
    for key, path in (("contract", HERE / "contract.json"), ("builder", HERE / "build.py"), ("checker", HERE / "check_roundtrip.py"), ("runner_script", HERE / "run_native_ssh.ps1"), ("parent_signoff", PARENT / "cli-scope-signoff-2026-10-03.md"), ("parent_closure", PARENT_RUN / "closure.json"), ("parent_model_log", PARENT_RUN / "model.log"), ("parent_report", PARENT_RUN / "report-raw.json"), ("diagnostic_closure", DIAGNOSTIC / "closure.json"), ("manual", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), ("dictionary", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"))):
        ck(f"bound source {key}", inv["source_hashes_before"].get(key) == sha(path))
    ck("guarded session and GUI", inv.get("session_id") == 0 and inv.get("ssh_connection_present") is True and "sshd.exe" in inv.get("ssh_ancestor_names", []) and inv.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue" and inv.get("gui", {}).get("pid") == 13340 and inv.get("gui", {}).get("session_id") == 1)
    ck("closure stable", closure.get("error") is None and closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("source_hashes_before") == closure.get("source_hashes_after") == inv.get("source_hashes_before"))
    ck("raw set", set(closure["raw"]) == RAW)
    for name, record in closure["raw"].items():
        path = run / name
        ck(f"sealed raw {name}", path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"])
    ck("five native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    rt = load(run / "roundtrip-validation.json")
    ck("22-table roundtrip", rt["passed"] and rt["differences"] == [] and len(rt["populated_tables"]) == 22)
    source, exported = (parse_native(path) for path in (HERE / "native-input.json", run / "roundtrip-raw.json"))
    ck("all populated source rows", all(populated(exported).get(name) == table for name, table in populated(source).items()))
    redundancy = next(t for t in exported["model"]["tables"] if t["name"] == "Redundancy")
    cols = [c["name"] for c in redundancy["columns"]]
    link = dict(zip(cols, redundancy["instances"][0]["rows"][0]))
    ck("ACTIVE TSWOV1", link["ACPA"] == "ACTIVE" and link["TSWOV"] == 1 and link["NRL"] == 2 and link["NRLRQ"] == 1)
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter zero errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog and "(error #" not in runlog)
    ck("reviewed warning 108", len(re.findall(r"\(warning #108\)", runlog)) == 1 and re.search(r"Form: Control\s+rec 1: \(warning #108\) Enabling simulation log may generate extensive data in log file", runlog) is not None)
    ck("reviewed warning 282", len(re.findall(r"\(warning #282\)", runlog)) == 1 and re.search(r"Form: Redundancy\s+rec 1: \(warning #282\) Switch over time \(TSWOV\) ignored", runlog) is not None)
    ck("no extra converter warning", len(re.findall(r"\(warning #\d+\)", runlog)) == 2)
    ck("event log byte identical", sha(run / "model.log") == sha(PARENT_RUN / "model.log") == contract["parent"]["model_log_sha256"])
    current_report = parse_native(run / "report-raw.json")
    parent_report = parse_native(PARENT_RUN / "report-raw.json")
    current_tables = {t["name"]: t for t in current_report["report"]["tables"]}
    parent_tables = {t["name"]: t for t in parent_report["report"]["tables"]}
    ck("report table names exact", set(current_tables) == set(parent_tables))
    ck("all non-description report tables exact", all(value == parent_tables[name] for name, value in current_tables.items() if name != "ProblemDescription"))
    ck("description differs", current_tables["ProblemDescription"] != parent_tables["ProblemDescription"])
    summary = rows(current_report, "ResultSummary")
    systems = rows(current_report, "SystemResults")
    stocks = rows(current_report, "StockTotalResults")
    ck("three successful missions", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["MSUF"] == 1)
    ck("72 system bins", len(systems) == 72 and all(row["STINT"] == i/2 and row["ETINT"] == (i+1)/2 for i,row in enumerate(systems)))
    ck("two failures and repairs", sum(row["NFAIL"] for row in systems) == 2 and sum(row["NREPT"] for row in systems) == 2)
    ck("no switch state and terminal ready", all(row["NSYSW"] == 0 for row in systems) and systems[-1]["NSYRY"] == systems[-1]["NSYA"] == 1)
    ck("72 stock bins no backorder", len(stocks) == 72 and all(row["STINT"] == i/2 and row["ETINT"] == (i+1)/2 and row["NBO"] == 0 for i,row in enumerate(stocks)))
    return {"schema": "simlox-g10-var05-v101-author-validation/v1", "case_id": "G10", "variant_id": "G10.var05", "run_id": run.name, "passed": not errors, "checks": count, "differences": errors, "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
