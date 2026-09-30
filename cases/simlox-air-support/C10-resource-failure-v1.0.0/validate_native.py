"""Read-only author replay of the sealed C10 operational crew-failure pair."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
SCHEMA_SOURCE = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
RUNS = {
    "oper-no-spare": ("c334c1d6c0efa89f9ff70151a45180cac53b9ae05bf1a783219b566f41dbd62b", "c10-oper-no-spare-20260930-01", 2),
    "oper-one-spare": ("e34ce47cc2d26fa74fb9a90766cfd426caae0ff7b4a7fc75038867762d7b4278", "c10-oper-one-spare-20260930-01", 3),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(doc: dict, section: str) -> dict:
    return {t["name"]: t for t in doc[section]["tables"]}


def rows(table: dict) -> list[list]:
    return [r for instance in table["instances"] for r in instance["rows"]]


def values(table: dict, column: str) -> list:
    i = [c["name"] for c in table["columns"]].index(column)
    return [r[i] for r in rows(table)]


def check() -> dict:
    issues: list[str] = []

    def require(ok: bool, label: str) -> None:
        if not ok:
            issues.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    parent_sha = "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0"
    schema_sha = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"
    require(contract["parent_publication_id"] == "C03.shared_crew.1.0.2" and sha(PARENT) == parent_sha == diff["parent_input_sha256"] == contract["parent_input_sha256"], "accepted C03 parent")
    require(sha(SCHEMA_SOURCE) == schema_sha == diff["schema_source_input_sha256"] == contract["schema_source_input_sha256"], "ResourceStationData schema source")
    base = tables(parse_native(PARENT), "model")
    source_tables = {}
    logs = {}
    reports = {}
    for variant, (input_sha, run_id, qty) in RUNS.items():
        source = HERE / f"{variant}-input.json"
        require(sha(source) == input_sha == contract["input_sha256"][variant] == diff["child_input_sha256"][variant], f"{variant} frozen input")
        child = tables(parse_native(source), "model")
        source_tables[variant] = child
        require(set(child) - set(base) == {"ResourceStationData"} and set(base) - set(child) == set(), f"{variant} added table")
        require(sorted(n for n in base if base[n] != child[n]) == (["ProblemDescription"] if qty == 2 else ["ProblemDescription", "ResourceAllocation"]), f"{variant} parent table delta")
        require(rows(child["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", qty, None]], f"{variant} crew quantity")
        require(rows(child["ResourceStationData"]) == [["P-CREW", "BASE-01", None, None, None, 0.5, "OPERATION", 0.25, None, None, None]], f"{variant} operational failure fields")

        run = HERE / "runs" / run_id
        inv = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        require(inv["run_id"] == closure["run_id"] == run_id and inv["case_id"] == "C10" and inv["variant"] == variant and inv["input_sha256"] == input_sha and inv["parent_sha256"] == parent_sha, f"{variant} run identity")
        require(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} guarded SSH")
        require(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} GUI identity")
        require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], f"{variant} source stability")
        for key, path in {"input": source, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
            require(closure["source_hashes_before"][key] == sha(path), f"{variant} source seal {key}")
        require(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} invocation seal")
        require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant} guarded steps")
        for name, item in closure["raw"].items():
            path = run / name
            require(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"{variant} raw seal {name}")
        require(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], f"{variant} native roundtrip")
        require(len(populated(parse_native(run / "input.json"))) == 21 and populated(parse_native(run / "input.json")) == {k: v for k, v in populated(parse_native(run / "roundtrip-raw.json")).items() if k in populated(parse_native(run / "input.json"))}, f"{variant} 21 row tables")
        calc = (run / "run.log").read_text(encoding="utf-8-sig")
        require("Errors: 0, Warnings: 2, Notes: 0" in calc and set(re.findall(r"warning\s+#(\d+)", calc, re.I)) == {"108", "126"}, f"{variant} conversion status")
        require((run / "model.sxo").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 4, f"{variant} nonempty output")
        logs[variant] = (run / "model.log").read_text(encoding="utf-8-sig")
        reports[variant] = tables(parse_native(run / "report-raw.json"), "report")

    a, b = source_tables["oper-no-spare"], source_tables["oper-one-spare"]
    require(sorted(n for n in a if a[n] != b[n]) == ["ProblemDescription", "ResourceAllocation"], "sole between-child business change")
    no, spare = logs["oper-no-spare"], logs["oper-one-spare"]
    for variant, log in logs.items():
        require("Time: 7.5 <P-CREW at <BASE-01,0>> Next Random Failure 7.78243" in log and "Time: 7.5 <P-CREW at <BASE-01,0>> Next Random Failure 7.73494" in log, f"{variant} active operational exposure")
        require("Time: 7.73494 <P-CREW at <BASE-01,0>> Failed" in log and "Time: 7.98494 <P-CREW at <BASE-01,0>> Repaired" in log, f"{variant} failure and repair")
        require(log.count("<P-CREW at <BASE-01,0>> Failed") == 1 and log.count("<P-CREW at <BASE-01,0>> Repaired") == 1, f"{variant} one observed failure")
        require("Time: 7.5 <TEACH-AIR-01,0> preparation started" in log and "Time: 7.5 <TEACH-AIR-01,1> preparation started" in log, f"{variant} two active tasks")
        require("Time: 36  resource shift 0 ended" in log, f"{variant} terminal shift")
    require("Time: 7.73494  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> is stopped due to a resource failure, time left= 0.265061" in no and "Time: 7.98494  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.265061 hours" in no, "no-spare stop and remaining-work resume")
    require("Time: 8.25 <TEACH-AIR-01,0> preparation ended" in no and "Time: 8.25 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in no and "Time: 9.25 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in no, "no-spare delayed outcome")
    require("is stopped due to a resource failure" not in spare and "Tasks waiting for resources at: <BASE-01,0> 0" in spare, "spare absorbs failure without task stop")
    require(all(f"Time: 8 <TEACH-AIR-01,{i}> preparation ended" in spare for i in (0, 1)) and "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in spare and "Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in spare, "spare baseline-time outcome")

    for variant, (_, _, qty) in RUNS.items():
        report = reports[variant]
        require(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"}, f"{variant} report tables")
        summary = report["ResultSummary"]
        require(len(rows(summary)) == 1 and all(values(summary, n) == [1] for n in ("NREP", "MTMF", "MSTF", "MSUF", "STMF")), f"{variant} successful mission summary")
        resource = report["ResourceResults"]
        require(len(rows(resource)) == 72 and values(resource, "STINT") == [i / 2 for i in range(72)] and values(resource, "ETINT") == [(i + 1) / 2 for i in range(72)] and all(n == qty for n in values(resource, "NR")), f"{variant} 72-bin resource count")
        require(math.isclose(values(resource, "NRF")[15], 0.5, abs_tol=1e-6) and all(v == 0 for i, v in enumerate(values(resource, "NRF")) if i != 15), f"{variant} failure ledger bin")
        require(math.isclose(values(resource, "NRUM")[15], 1.5 if qty == 2 else 2, abs_tol=1e-6) and math.isclose(values(resource, "NRW")[15], 0.5 if qty == 2 else 0, abs_tol=1e-6), f"{variant} work/wait ledger bin")
        total = report["ResourceResultsTotal"]
        require(len(rows(total)) == 1 and values(total, "NR") == [qty] and math.isclose(values(total, "NRF")[0], 0.25 / 36, abs_tol=1e-6) and math.isclose(values(total, "NRUM")[0], (1 if qty == 2 else 1) / 36, abs_tol=1e-6) and math.isclose(values(total, "NRW")[0], (0.25 if qty == 2 else 0) / 36, abs_tol=1e-6), f"{variant} resource totals")
        system = report["SystemResults"]
        require(len(rows(system)) == 72 and values(system, "NSYRY")[-1] == 2 and all(v == 0 for v in values(system, "NFAIL")), f"{variant} two ready systems without aircraft failure")
        stock = report["StockTotalResults"]
        require(len(rows(stock)) == 72 and all(v == 0 for n in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT") for v in values(stock, n)), f"{variant} zero stock movement")

    return {"schema": "simlox-c10-resource-failure-author-validation/v1", "passed": not issues, "issues": issues,
            "runs": [{"variant": variant, "run_id": run_id, "input_sha256": input_sha,
                      "closure_sha256": sha(HERE / "runs" / run_id / "closure.json"),
                      "model_log_sha256": sha(HERE / "runs" / run_id / "model.log"),
                      "report_raw_sha256": sha(HERE / "runs" / run_id / "report-raw.json")}
                     for variant, (input_sha, run_id, _) in RUNS.items()],
            "scope": "one seeded operational crew failure at 7.73494; with two crews a preparation stops until repair and mission succeeds 0.25 hour later; with one idle spare no task stop and baseline timing persists"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
