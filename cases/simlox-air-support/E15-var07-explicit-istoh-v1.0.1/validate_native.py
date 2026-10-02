"""Replay the bounded E15.var07 paired native evidence from sealed local raw files."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SHA = {
    "default": {
        "input": "602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e",
        "native_closure": "f00b8fc07a4deb1db33b6142f0704e373a5db09197e8f6190fd0b22947e6feff",
        "report_closure": "640e77479b0930137ca7f97e1f346babc9de7132ec33cd6f9ca400fb8295b249",
    },
    "explicit-three": {
        "input": "bb57aecc7285d8eef5c71ba1b7f6b6f7dd9fb4cc46f3e6d88e863eb1da3f206f",
        "native_closure": "79e4729d44a4a3ed524ad9e0f0559c4d98c3aff64278bf553c3768f956c435e5",
        "report_closure": "1bf91edb10034e912a49e1b810f7d5697f351a0eb50d51cefd8fa24bcdc9bbb8",
    },
}
DONOR_SHA = "c409f4b210b9f60e5f36bf6b15f56aaba95f4b08b4f6b6de290b60d65086d7d9"
E02_SHA = "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
RAW_NATIVE = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}
RAW_REPORT = {"item-report-raw.json", "report-export.log"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def tables(path: Path) -> dict[str, dict]:
    data = parse_native(path)["report"]["tables"]
    result = {t["name"]: t for t in data}
    if len(result) != len(data):
        raise ValueError("duplicate result table")
    return result


def main() -> int:
    issues: list[str] = []
    count = 0

    def ck(label: str, yes: bool) -> None:
        nonlocal count
        count += 1
        if not yes:
            issues.append(label)

    contract = read(HERE / "contract.json")
    ck("contract identity", contract["case_id"] == "E15" and contract["variant_id"] == "E15.var07" and contract["case_version"] == "1.0.1-candidate")
    ck("donor/prerequisite pins", contract["direct_behavioral_donor"]["input_sha256"] == DONOR_SHA and contract["catalog_parent_prerequisite"]["input_sha256"] == E02_SHA)
    for arm, pins in SHA.items():
        ck(f"{arm} contract input", contract["arms"][arm]["input_sha256"] == pins["input"])
        ck(f"{arm} source input", sha(HERE / f"native-input-{arm}.json") == pins["input"])
    ck("donor bytes", sha(HERE.parent / "G01-var03-du-discard-reorder-v1.0.0/native-input.json") == DONOR_SHA)
    ck("E02 bytes", sha(HERE.parent / "E02-zero-stock-local-backorder-v1.0.0/native-input.json") == E02_SHA)
    main_reports = {}
    selected_reports = {}
    for arm, pins in SHA.items():
        native_id = f"e15-var07-{arm}-v101-ssh-20261002-01"
        selected_id = f"e15-var07-{arm}-item-v101-ssh-20261002-01"
        native, selected = RUNS / native_id, RUNS / selected_id
        ck(f"{arm} native closure fixed", sha(native / "closure.json") == pins["native_closure"])
        ck(f"{arm} report closure fixed", sha(selected / "closure.json") == pins["report_closure"])
        inv, closure, steps = (read(native / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} invocation identity", inv["case_id"] == "E15" and inv["case_version"] == "1.0.1-candidate" and inv["arm"] == arm and inv["run_id"] == native_id)
        ck(f"{arm} native source pins", inv["input_sha256"] == pins["input"] and inv["parent_sha256"] == DONOR_SHA and inv["catalog_parent_sha256"] == E02_SHA and inv["simlox_exe_sha256"] == EXE_SHA)
        ck(f"{arm} run source bytes", sha(native / "input.json") == pins["input"] and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
        ck(f"{arm} invocation closure", closure["run_id"] == native_id and closure["arm"] == arm and closure["invocation_sha256"] == sha(native / "invocation.json") and closure["error"] is None)
        ck(f"{arm} source source-hashes", inv["source_hashes_before"]["contract"] == sha(HERE / "contract.json") and inv["source_hashes_before"]["exact_diff"] == sha(HERE / "exact-diff.json") and inv["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1"))
        ck(f"{arm} execution guard", inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        ck(f"{arm} five stages", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} native raw file set", set(closure["raw"]) == RAW_NATIVE)
        for name, seal in closure["raw"].items():
            p = native / name
            ck(f"{arm} native raw {name}", p.is_file() and p.stat().st_size == seal["bytes"] and sha(p) == seal["sha256"])
        roundtrip = read(native / "roundtrip-validation.json")
        ck(f"{arm} exact 21-table roundtrip", roundtrip["passed"] is True and roundtrip["differences"] == [] and len(roundtrip["populated_tables"]) == 21 and populated(parse_native(native / "input.json")) == {k: populated(parse_native(native / "roundtrip-raw.json"))[k] for k in populated(parse_native(native / "input.json"))})
        runlog = (native / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}))
        ck(f"{arm} valid SXO", (native / "model.sxo").stat().st_size > 1000)
        report = tables(native / "report-raw.json")
        main_reports[arm] = report
        ck(f"{arm} default business tables", {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(report))
        selected_inv, selected_closure = (read(selected / name) for name in ("invocation.json", "closure.json"))
        ck(f"{arm} selected source", selected_inv["arm"] == arm and selected_inv["source_run_id"] == native_id and selected_inv["source_closure_sha256"] == pins["native_closure"])
        ck(f"{arm} selected guard", selected_inv["session_id"] == 0 and "sshd.exe" in selected_inv["ssh_ancestor_names"] and selected_inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and selected_inv["gui"]["pid"] == 13340)
        ck(f"{arm} selected closure", selected_closure["error"] is None and selected_closure["exit_code"] == 0 and selected_closure["invocation_sha256"] == sha(selected / "invocation.json") and selected_closure["source_hashes_before"] == selected_closure["source_hashes_after"] == selected_inv["source_hashes_before"])
        ck(f"{arm} report raw file set", set(selected_closure["raw"]) == RAW_REPORT)
        for name, seal in selected_closure["raw"].items():
            p = selected / name
            ck(f"{arm} report raw {name}", p.is_file() and p.stat().st_size == seal["bytes"] and sha(p) == seal["sha256"])
        reportlog = (selected / "report-export.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} report export", "Report completed" in reportlog and "Export completed!" in reportlog)
        selected_report = tables(selected / "item-report-raw.json")
        selected_reports[arm] = selected_report
        ck(f"{arm} selected tables", {"ItemResults", "ItemResultsTotal", "SystemResults", "StockTotalResults", "ResultSummary", "FixedMissionResultsTotal"}.issubset(selected_report))
        item = rows(selected_report["ItemResults"])
        ck(f"{arm} 72 depot bins", len(item) == 72 and all(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01" and row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(item)))
        ck(f"{arm} nominal 4 and zero backorder", all(row["STSZ"] == 4 and row["NBO"] == 0 for row in item))
        expected = ([4] * 20 + [3] * 52) if arm == "default" else ([3] * 20 + [2] * 2 + [4] * 50)
        for i, (row, want) in enumerate(zip(item, expected)):
            ck(f"{arm} on-hand bin {i}", row["STOHA"] == want)
        total = rows(selected_report["ItemResultsTotal"])[0]
        ck(f"{arm} item total", total["STSZ"] == 4 and abs(total["STOHA"] - sum(expected) / 72) < 1e-5 and total["NRO"] == (0 if arm == "default" else 1))
        system = rows(selected_report["SystemResults"])
        ck(f"{arm} system bins/terminal", len(system) == 72 and system[-1]["NSYRY"] == 1)
        fixed = rows(selected_report["FixedMissionResultsTotal"])[0]
        ck(f"{arm} missions", fixed["NMSTA"] == 3 and fixed["NMSUC"] == 2)
        log = (native / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} one depot issue", len(re.findall(r"Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item", log)) == 1)
        ck(f"{arm} one base receipt", len(re.findall(r"Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item", log)) == 1)
        starts = re.findall(r"Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task \d+ started, reorder time: 1", log)
        completes = re.findall(r"Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task \d+ completed, total time was 1", log)
        depot_returns = re.findall(r"Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Put back replacement item", log)
        ck(f"{arm} reorder event contrast", (len(starts), len(completes), len(depot_returns)) == ((0, 0, 0) if arm == "default" else (1, 1, 2)) and log.count("reorder task") == (0 if arm == "default" else 2))
    for name in ("ResultSummary", "SystemResults", "StockTotalResults", "MissionResults", "FixedMissionResultsTotal"):
        ck(f"selected {name} paired equality", selected_reports["default"].get(name) == selected_reports["explicit-three"].get(name))
    ck("initial/terminal contrast", rows(selected_reports["default"]["ItemResults"])[0]["STOHA"] == 4 and rows(selected_reports["explicit-three"]["ItemResults"])[0]["STOHA"] == 3 and rows(selected_reports["default"]["ItemResults"])[-1]["STOHA"] == 3 and rows(selected_reports["explicit-three"]["ItemResults"])[-1]["STOHA"] == 4)
    result = {"schema": "simlox-e15-var07-v101-author-validation/v1", "passed": not issues, "checks": count, "differences": issues, "scope": "bounded_two_arm_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}, indent=2))
        sys.exit(1)
