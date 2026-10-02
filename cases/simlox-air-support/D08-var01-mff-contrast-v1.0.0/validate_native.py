"""Author replay of the bounded D08.var01 mission multiplier contrast."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PARENT = HERE.parent / "D05-maintenance-competition-v1.0.0"
SHA = {
    "default": {"input": "5be5592989ac38349141d22c9b9bd5f9db11029182f66bbb456207bb908ae030", "closure": "9b715b36af0625ef6b59283b0f865b188670d93db5aedf60ee82e61714843593"},
    "low": {"input": "f4e82b497668a016f79fd2e8f54f7c6df59e1b8a5a9a1f0c084eb8cfcb6b2d66", "closure": "db8b0cbd24d99b7ede89fe8c5d3842937de5f90e3c4e845a31cbd5d78901acf7"},
}
PARENT_SHA = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
PARENT_CLOSURE_SHA = "4ade4062f3ef3a25d8adc96b9f57f5ca34eea850de2fd2a304a4e0163fb55736"
D02_SHA = "9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2"
D02_CLOSURE_SHA = "fdb0c93c2a59313392587378665115baa26cb23de01e48d543b56eaa33abfbb8"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path) -> dict:
    items = parse_native(path)["report"]["tables"]
    result = {item["name"]: item for item in items}
    assert len(result) == len(items)
    return result


def rows(table: dict) -> list[dict]:
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> int:
    issues: list[str] = []
    count = 0

    def ck(label: str, yes: bool) -> None:
        nonlocal count
        count += 1
        if not yes:
            issues.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("frozen contract identity", contract["case_id"] == "D08" and contract["variant_id"] == "D08.var01" and contract["case_version"] == "1.0.0-candidate")
    ck("parent and prerequisite fingerprints", sha(PARENT / "native-input.json") == PARENT_SHA and sha(PARENT / "runs/d05-pilot-v100-ssh-20260930-03/closure.json") == PARENT_CLOSURE_SHA and sha(HERE.parent / "D02-var01-traditional-op-hours-v1.0.0/native-input.json") == D02_SHA and sha(HERE.parent / "D02-var01-traditional-op-hours-v1.0.0/runs/d02-var01-traditional-op-v100-ssh-20260930-01/closure.json") == D02_CLOSURE_SHA)
    ck("contract parent pins", contract["direct_behavioral_donor"]["input_sha256"] == PARENT_SHA and contract["direct_behavioral_donor"]["native_closure_sha256"] == PARENT_CLOSURE_SHA and contract["catalog_parent_prerequisite"]["input_sha256"] == D02_SHA and contract["catalog_parent_prerequisite"]["native_closure_sha256"] == D02_CLOSURE_SHA)
    ck("exact diff fingerprint", sha(HERE / "exact-diff.json") == "4dad45d1518e1411b26c0b9f9581b77e44e5dd70b1a5e4368e99ea5ee8e65f5b")
    ck("pairwise business delta", diff["pairwise_business_difference"] == {"table": "MissionType", "row": 1, "field": "MFF", "default": None, "low": 0.000001} and diff["unchanged_tables"] == 29)
    reports = {}
    logs = {}
    for arm, pins in SHA.items():
        run_id = f"d08-var01-{arm}-v100-ssh-20261002-01"
        run = RUNS / run_id
        ck(f"{arm} frozen input", contract["arms"][arm]["input_sha256"] == pins["input"] and sha(HERE / f"native-input-{arm}.json") == pins["input"] and diff["source_sha256"][arm] == pins["input"])
        ck(f"{arm} closure fixed", sha(run / "closure.json") == pins["closure"])
        inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} invocation identity", inv["case_id"] == "D08" and inv["variant_id"] == "D08.var01" and inv["arm"] == arm and inv["run_id"] == run_id and inv["input_sha256"] == pins["input"] and inv["parent_sha256"] == PARENT_SHA and inv["catalog_parent_sha256"] == D02_SHA)
        ck(f"{arm} session and GUI guard", inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        ck(f"{arm} closure/source identity", closure["error"] is None and closure["run_id"] == run_id and closure["arm"] == arm and closure["invocation_sha256"] == sha(run / "invocation.json") and inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
        ck(f"{arm} frozen contract/diff/runner", inv["source_hashes_before"]["contract"] == sha(HERE / "contract.json") and inv["source_hashes_before"]["exact_diff"] == sha(HERE / "exact-diff.json") and inv["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1"))
        ck(f"{arm} native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} raw set", set(closure["raw"]) == RAW)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        ck(f"{arm} copied input", sha(run / "input.json") == pins["input"])
        checked = read(run / "roundtrip-validation.json")
        before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm} 22 authored table roundtrip", checked["passed"] is True and checked["differences"] == [] and len(before) == 22 and all(after.get(k) == v for k, v in before.items()))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} converter gate", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1, "126": 1}))
        ck(f"{arm} output exists", (run / "model.sxo").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)
        report = tables(run / "report-raw.json")
        reports[arm] = report
        ck(f"{arm} result tables", {"ResultSummary", "SystemResults", "ResourceResults", "ResourceResultsTotal", "StockTotalResults"}.issubset(report))
        system, resource, stock = (rows(report[name]) for name in ("SystemResults", "ResourceResults", "StockTotalResults"))
        ck(f"{arm} 72 half-hour bins", len(system) == len(resource) == len(stock) == 72 and all(system[i]["STINT"] == resource[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == resource[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} worker capacity", all(r["NR"] == 1 and -1e-4 <= r["NRUM"] <= 1.0001 for r in resource))
        ck(f"{arm} no inventory demand/backorder", all(s["NBO"] == 0 and s["NDF"] == 0 for s in stock))
        ck(f"{arm} terminal readiness", system[-1]["NSYRY"] == 2 and resource[-1]["NRUM"] == 0 and resource[-1]["NR"] == 1)
        logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        mission = re.findall(r"Time: ([0-9.]+) <(BASIC-MISSION|RISK-MISSION),TEACH-UNIT,0,0,\d+> mission (success|aborted):", logs[arm])
        expected = [("10", "BASIC-MISSION", "success"), ("22.6835", "RISK-MISSION", "aborted"), ("34", "BASIC-MISSION", "success")] if arm == "default" else [("10", "BASIC-MISSION", "success"), ("23", "RISK-MISSION", "success"), ("34", "BASIC-MISSION", "success")]
        ck(f"{arm} three mission outcomes", mission == expected)
        fault = re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,\d+> critical random failure added", logs[arm])
        ck(f"{arm} failure events", fault == (["22.6835"] if arm == "default" else []))
        ck(f"{arm} PM completion", len(re.findall(r"Time: \d+  system PM task \d+ on <TEACH-AIR-01,\d+> completed", logs[arm])) == 2)
        booking = re.findall(r"Time: ([0-9.]+)  .* (books|frees) resources", logs[arm])
        expected_booking = [("23", "books"), ("28", "frees"), ("28", "books"), ("29", "frees"), ("29", "books"), ("30", "frees")] if arm == "default" else [("24", "books"), ("25", "frees"), ("25", "books"), ("26", "frees")]
        ck(f"{arm} serialized worker ledger", booking == expected_booking)
        ck(f"{arm} direct CM count", len(re.findall(r"direct repair subtask .* books resources", logs[arm])) == (1 if arm == "default" else 0))
        expected_use = 7 if arm == "default" else 2
        expected_wait = 5 if arm == "default" else 1
        ck(f"{arm} worker use/wait integral", abs(sum(r["NRUM"] / 2 for r in resource) - expected_use) < 1e-4 and abs(sum(r["NRW"] / 2 for r in resource) - expected_wait) < 1e-4)
        ck(f"{arm} system event totals", sum(s["NFAIL"] for s in system) == (1 if arm == "default" else 0) and sum(s["NREPT"] for s in system) == (1 if arm == "default" else 0) and sum(s["NPMS"] for s in system) == 2 and sum(s["NPMT"] for s in system) == 2)
        summary = rows(report["ResultSummary"])[0]
        ck(f"{arm} summary mission success fraction", abs(summary["MSUF"] - (2 / 3 if arm == "default" else 1)) < 1e-5)
    ck("default event log matches accepted D05 donor", sha(RUNS / "d08-var01-default-v100-ssh-20261002-01/model.log") == sha(PARENT / "runs/d05-pilot-v100-ssh-20260930-03/model.log"))
    ck("paired output changes", reports["default"]["SystemResults"] != reports["low"]["SystemResults"] and reports["default"]["ResourceResults"] != reports["low"]["ResourceResults"] and logs["default"] != logs["low"])
    result = {"schema": "simlox-d08-var01-mff-v100-author-validation/v1", "passed": not issues, "checks": count, "differences": issues, "scope": "bounded_two_arm_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}, indent=2))
        raise SystemExit(1)
