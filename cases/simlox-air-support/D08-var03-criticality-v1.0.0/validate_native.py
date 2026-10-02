"""Author replay of D08.var03 traditional and explicit-mode criticality."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
CATALOG = HERE.parent / "D02-var01-traditional-op-hours-v1.0.0"
CATALOG_INPUT_SHA = "9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2"
CATALOG_CLOSURE_SHA = "fdb0c93c2a59313392587378665115baa26cb23de01e48d543b56eaa33abfbb8"
ARMS = {
    "traditional": {"input": "cd549962924b57f4db8ccc9de906f6abd86af5c5057e4c413c2f9824bf46a01e", "closure": "512f30614f3ce25ea4253afa6d708008f5c182a76366464709700f209879ffe0", "parent": HERE.parent / "D01-installed-lru-direct-repair-v1.0.0", "parent_input": "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93", "parent_closure": "3642d558e98abd31f4510e213286182f9ce0d6eda0a86f6185c64f439f7e79f0", "parent_run": "d01-lru-v100-ssh-20260929-01", "field": ("Item", "CRIT"), "faults": ["9.8829"], "repairs": ["10.5"]},
    "failure-mode": {"input": "36d20f6be3bcb877ff925542aa2a3f95324a7e1562ed57f18c1561fba27fe59e", "closure": "47a0f9aa98a0682afa4a997de86e880ea0f9e654cee16587b9f6e309d8196fbe", "parent": HERE.parent / "D06-explicit-position-direct-repair-v1.0.0", "parent_input": "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78", "parent_closure": "afd8689161874d247dee92a6f6265211733375b8933f3fcd30bfb297cfe975c7", "parent_run": "d06-position-cm-v100-ssh-20260930-02", "field": ("FailureMode", "CRITF"), "faults": ["9.8829", "21.8602"], "repairs": ["10.5", "22.5"]},
}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def tables(path: Path) -> dict:
    all_tables = parse_native(path)["report"]["tables"]
    result = {table["name"]: table for table in all_tables}
    assert len(result) == len(all_tables)
    return result


def main() -> int:
    issues: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            issues.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("contract identity", contract["case_id"] == "D08" and contract["variant_id"] == "D08.var03" and contract["case_version"] == "1.0.0-candidate")
    ck("frozen contract/diff", sha(HERE / "contract.json") == "466a76f8d8c2d8966acaa04811deedffa42e2fd009a24e11b832dc8fa750062b" and sha(HERE / "exact-diff.json") == "0a78a78404b2762fdc7d8dfbea8b05c4fb3ad04ec8c6e7526a9fcf516545528f")
    ck("D02 prerequisite", sha(CATALOG / "native-input.json") == CATALOG_INPUT_SHA and sha(CATALOG / "runs/d02-var01-traditional-op-v100-ssh-20260930-01/closure.json") == CATALOG_CLOSURE_SHA and contract["catalog_parent_prerequisite"]["input_sha256"] == CATALOG_INPUT_SHA)
    for arm, pins in ARMS.items():
        run_id = f"d08-var03-{arm}-v100-ssh-20261002-01"
        run = RUNS / run_id
        parent = pins["parent"]
        parent_run = parent / "runs" / pins["parent_run"]
        ck(f"{arm} accepted parent pins", sha(parent / "native-input.json") == pins["parent_input"] and sha(parent_run / "closure.json") == pins["parent_closure"] and contract["accepted_controls"][arm]["input_sha256"] == pins["parent_input"] and contract["accepted_controls"][arm]["native_closure_sha256"] == pins["parent_closure"])
        ck(f"{arm} child source and diff", sha(HERE / f"native-input-{arm}.json") == pins["input"] and contract["arms"][arm]["input_sha256"] == pins["input"] and diff["arms"][arm]["child_sha256"] == pins["input"] and diff["arms"][arm]["parent_sha256"] == pins["parent_input"])
        critical = [x for x in diff["arms"][arm]["changes"] if x["table"] == pins["field"][0] and x["field"] == pins["field"][1]]
        ck(f"{arm} exact criticality delta", len(diff["arms"][arm]["changes"]) == 2 and len(critical) == 1 and critical[0]["before"] == 1 and critical[0]["after"] == 0)
        ck(f"{arm} sealed closure", sha(run / "closure.json") == pins["closure"])
        inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} invocation", inv["case_id"] == "D08" and inv["variant_id"] == "D08.var03" and inv["arm"] == arm and inv["run_id"] == run_id and inv["input_sha256"] == pins["input"] and inv["parent_sha256"] == pins["parent_input"] and inv["parent_closure_sha256"] == pins["parent_closure"])
        ck(f"{arm} SSH/GUI/queue", inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        ck(f"{arm} source closure", closure["error"] is None and closure["arm"] == arm and closure["run_id"] == run_id and closure["invocation_sha256"] == sha(run / "invocation.json") and inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
        ck(f"{arm} source files fixed", inv["source_hashes_before"]["contract"] == sha(HERE / "contract.json") and inv["source_hashes_before"]["exact_diff"] == sha(HERE / "exact-diff.json") and inv["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1"))
        ck(f"{arm} five native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} raw file set", set(closure["raw"]) == RAW)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        ck(f"{arm} copied input", sha(run / "input.json") == pins["input"])
        roundtrip = read(run / "roundtrip-validation.json")
        before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm} 18 table exact roundtrip", roundtrip["passed"] is True and roundtrip["differences"] == [] and len(before) == 18 and all(after.get(name) == value for name, value in before.items()))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} converter", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
        ck(f"{arm} SXO/report nonempty", (run / "model.sxo").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} critical control aborts first mission", "Time: 9.8829" in parent_log and "mission aborted:" in parent_log and "critical" in parent_log)
        kind = "random failure" if arm == "traditional" else "CM failure mode"
        faults = re.findall(rf"Time: ([0-9.]+) <TEACH-AIR-01,0> noncritical {kind} added", log)
        ck(f"{arm} noncritical fault ledger", faults == pins["faults"])
        missions = re.findall(r"Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission (success|aborted):", log)
        ck(f"{arm} three mission successes", missions == [("10", "success"), ("22", "success"), ("34", "success")] and "mission aborted:" not in log)
        ck(f"{arm} first fault precedes mission success", log.index("Time: 9.8829") < log.index("Time: 10 <BASIC-MISSION") < log.index("Time: 10  system"))
        repair_type = "SURP" if arm == "traditional" else "CM"
        repair_done = re.findall(rf"Time: ([0-9.]+)  system {repair_type} task \d+ on <TEACH-AIR-01,0> completed", log)
        ck(f"{arm} repair count and completion", repair_done == pins["repairs"])
        if arm == "traditional":
            ck("traditional physical LRU and stock loop", "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log and "Time: 11.25 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in log)
        else:
            ck("explicit FMID/position route", log.count("noncritical CM failure mode added") == 2 and log.count("FMID: FM-POS-A") == 2 and "on materiel: <POS-A,0>" in log and "Take replacement item" not in log)
        report = tables(run / "report-raw.json")
        ck(f"{arm} report tables", {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(report))
        system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
        ck(f"{arm} 72 half-hour bins", len(system) == len(stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} failure/repair totals", sum(row["NFAIL"] for row in system) == len(pins["faults"]) and sum(row["NREPT"] for row in system) == len(pins["repairs"]))
        ck(f"{arm} report terminal/mission", system[-1]["NSYRY"] == 1 and abs(rows(report["ResultSummary"])[0]["MSUF"] - 1) < 1e-6)
        ck(f"{arm} no stock backorder", all(row["NBO"] == 0 for row in stock))
        ck(f"{arm} stock demand route", sum(row["NDF"] for row in stock) == (1 if arm == "traditional" else 0))
    result = {"schema": "simlox-d08-var03-criticality-v100-author-validation/v1", "passed": not issues, "checks": checks, "differences": issues, "scope": "bounded_two_route_noncritical_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}, indent=2))
        raise SystemExit(1)
