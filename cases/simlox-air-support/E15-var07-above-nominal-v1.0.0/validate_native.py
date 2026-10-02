"""Replay the frozen E15.var07 above-nominal child against the accepted default."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1"
CHILD_NATIVE_ID = "e15-var07-above-nominal-v100-ssh-20261002-01"
CHILD_REPORT_ID = "e15-var07-above-nominal-item-v100-ssh-20261002-01"
PARENT_NATIVE_ID = "e15-var07-default-v101-ssh-20261002-01"
PARENT_REPORT_ID = "e15-var07-default-item-v101-ssh-20261002-01"
INPUT_SHA = "d65eec8aef4a75253370530bf308af3ca18c0fa97a0090da3f0fc34d98e54c5b"
PARENT_INPUT_SHA = "602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e"
NATIVE_CLOSURE_SHA = "0c4cbdad0dfa7a1e35fb14220b36d1061d3e0c2976db3d18cca50bdb49d4b1fb"
REPORT_CLOSURE_SHA = "582f11d0ae5ac2a7750d3c7160e558630ef51eec6019d5252a951483a147599a"
PARENT_NATIVE_CLOSURE_SHA = "f00b8fc07a4deb1db33b6142f0704e373a5db09197e8f6190fd0b22947e6feff"
PARENT_REPORT_CLOSURE_SHA = "640e77479b0930137ca7f97e1f346babc9de7132ec33cd6f9ca400fb8295b249"
NATIVE_RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}
REPORT_RAW = {"item-report-raw.json", "report-export.log"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path) -> dict:
    report = parse_native(path)["report"]["tables"]
    result = {table["name"]: table for table in report}
    assert len(result) == len(report)
    return result


def rows(table: dict) -> list[dict]:
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def main() -> int:
    problems: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            problems.append(label)

    contract = read(HERE / "contract.json")
    cn = HERE / "runs" / CHILD_NATIVE_ID
    cr = HERE / "runs" / CHILD_REPORT_ID
    pn = PARENT / "runs" / PARENT_NATIVE_ID
    pr = PARENT / "runs" / PARENT_REPORT_ID
    ck("contract identity", contract["case_id"] == "E15" and contract["variant_id"] == "E15.var07" and contract["case_version"] == "1.0.0-candidate")
    ck("contract source pins", contract["native_input_sha256"] == INPUT_SHA and contract["parent"]["input_sha256"] == PARENT_INPUT_SHA and contract["parent"]["native_closure_sha256"] == PARENT_NATIVE_CLOSURE_SHA and contract["parent"]["selected_item_report_closure_sha256"] == PARENT_REPORT_CLOSURE_SHA)
    ck("child and parent input bytes", digest(HERE / "native-input.json") == INPUT_SHA and digest(PARENT / "native-input-default.json") == PARENT_INPUT_SHA)
    ck("closure fixed", digest(cn / "closure.json") == NATIVE_CLOSURE_SHA and digest(cr / "closure.json") == REPORT_CLOSURE_SHA and digest(pn / "closure.json") == PARENT_NATIVE_CLOSURE_SHA and digest(pr / "closure.json") == PARENT_REPORT_CLOSURE_SHA)
    ck("exact diff fixed", digest(HERE / "exact-diff.json") == "4c1111aca21ea6131645675aec8979b0c780b50c3c03007e3122f0d983e137ea")
    diff = read(HERE / "exact-diff.json")
    ck("exact source change", [(x["table"], x["field"], x["before"], x["after"]) for x in diff["changes"]] == [("ProblemDescription", "PDESC", "E15.var07 tracked stock reorder initial depot on-hand default", "E15.var07 explicit depot ISTOH6 above nominal STSIZ4"), ("StockAllocation", "ISTOH", None, 6)] and diff["unchanged_tables"] == 29)

    inv, closure, steps = (read(cn / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("native invocation identity", inv["case_id"] == "E15" and inv["variant_id"] == "E15.var07" and inv["arm"] == "explicit-six" and inv["run_id"] == CHILD_NATIVE_ID and inv["input_sha256"] == INPUT_SHA and inv["parent_sha256"] == PARENT_INPUT_SHA)
    ck("native closure identity", closure["error"] is None and closure["run_id"] == CHILD_NATIVE_ID and closure["invocation_sha256"] == digest(cn / "invocation.json"))
    ck("native execution guard", inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck("native frozen sources", inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"] and inv["source_hashes_before"]["contract"] == digest(HERE / "contract.json") and inv["source_hashes_before"]["runner_script"] == digest(HERE / "run_native_ssh.ps1"))
    ck("five native steps", [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True for step in steps))
    ck("native raw set", set(closure["raw"]) == NATIVE_RAW)
    for name, seal in closure["raw"].items():
        path = cn / name
        ck(f"native raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and digest(path) == seal["sha256"])
    ck("native input copied", digest(cn / "input.json") == INPUT_SHA)
    roundtrip = read(cn / "roundtrip-validation.json")
    before = populated(parse_native(cn / "input.json"))
    after = populated(parse_native(cn / "roundtrip-raw.json"))
    ck("exact 21 authored tables", roundtrip["passed"] is True and roundtrip["differences"] == [] and len(before) == 21 and all(after.get(k) == value for k, value in before.items()))
    runlog = (cn / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter zero errors", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}))
    ck("native output nonempty", (cn / "model.sxo").stat().st_size > 1000 and {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(tables(cn / "report-raw.json")))

    rinv, rclosure = read(cr / "invocation.json"), read(cr / "closure.json")
    ck("selected report source", rinv["source_run_id"] == CHILD_NATIVE_ID and rinv["source_closure_sha256"] == NATIVE_CLOSURE_SHA and rinv["arm"] == "explicit-six")
    ck("selected report execution guard", rinv["session_id"] == 0 and "sshd.exe" in rinv["ssh_ancestor_names"] and rinv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and rinv["gui"]["pid"] == 13340)
    ck("selected report closure", rclosure["error"] is None and rclosure["exit_code"] == 0 and rclosure["invocation_sha256"] == digest(cr / "invocation.json") and rinv["source_hashes_before"] == rclosure["source_hashes_before"] == rclosure["source_hashes_after"])
    ck("selected raw set", set(rclosure["raw"]) == REPORT_RAW)
    for name, seal in rclosure["raw"].items():
        path = cr / name
        ck(f"selected raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and digest(path) == seal["sha256"])
    reportlog = (cr / "report-export.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("selected export markers", "Report completed" in reportlog and "Export completed!" in reportlog)
    child, parent = tables(cr / "item-report-raw.json"), tables(pr / "item-report-raw.json")
    ck("selected tables", {"ItemResults", "ItemResultsTotal", "SystemResults", "StockTotalResults", "ResultSummary", "FixedMissionResultsTotal"}.issubset(child))
    child_item, parent_item = rows(child["ItemResults"]), rows(parent["ItemResults"])
    ck("72 half-hour depot bins", len(child_item) == len(parent_item) == 72 and all(c["IID"] == p["IID"] == "TEACH-DU-01" and c["STID"] == p["STID"] == "DEPOT-01" and c["STINT"] == p["STINT"] == i / 2 and c["ETINT"] == p["ETINT"] == (i + 1) / 2 for i, (c, p) in enumerate(zip(child_item, parent_item))))
    for i, (c, p) in enumerate(zip(child_item, parent_item)):
        ck(f"depot bin {i}", c["STSZ"] == p["STSZ"] == 4 and c["STOHA"] == (6 if i < 20 else 5) and p["STOHA"] == (4 if i < 20 else 3) and c["STOHA"] - p["STOHA"] == 2 and c["NBO"] == p["NBO"] == 0)
    child_total, parent_total = rows(child["ItemResultsTotal"])[0], rows(parent["ItemResultsTotal"])[0]
    ck("item average and no reorder", child_total["STSZ"] == parent_total["STSZ"] == 4 and abs(child_total["STOHA"] - (20 * 6 + 52 * 5) / 72) < 1e-5 and abs(parent_total["STOHA"] - (20 * 4 + 52 * 3) / 72) < 1e-5 and child_total["NRO"] == parent_total["NRO"] == 0)
    for name in ("ResultSummary", "SystemResults", "StockTotalResults", "MissionResults", "FixedMissionResultsTotal"):
        ck(f"selected {name} parent equality", child.get(name) == parent.get(name))
    ck("terminal readiness", len(rows(child["SystemResults"])) == 72 and rows(child["SystemResults"])[-1]["NSYRY"] == 1)
    fixed = rows(child["FixedMissionResultsTotal"])[0]
    ck("mission outcomes", fixed["NMSTA"] == 3 and fixed["NMSUC"] == 2)
    child_log = (cn / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (pn / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for label, log in (("child", child_log), ("parent", parent_log)):
        ck(f"{label} one depot issue", len(re.findall(r"Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item", log)) == 1)
        ck(f"{label} one base replenishment", len(re.findall(r"Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item", log)) == 1)
        ck(f"{label} no reorder events", "reorder task" not in log)
    result = {"schema": "simlox-e15-var07-above-nominal-v100-author-validation/v1", "passed": not problems, "checks": checks, "differences": problems, "scope": "bounded_child_vs_accepted_default_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}, indent=2))
        raise SystemExit(1)
