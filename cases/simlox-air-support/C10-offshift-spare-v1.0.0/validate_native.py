"""Read-only author replay of the C10 on-shift versus off-shift spare pair."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C10-resource-failure-v1.0.0" / "oper-one-spare-input.json"
SHIFT_SCHEMA = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
PARENT_SHA = "e34ce47cc2d26fa74fb9a90766cfd426caae0ff7b4a7fc75038867762d7b4278"
SCHEMA_SHA = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"
RUNS = {
    "onshift-three": ("4e8ffe8bad98d5313279c189aeb8947db64f2f04d61789c0a6c5db134d011d92", "c10-onshift-three-20260930-01", 3),
    "onshift-two-offshift-one": ("7d11ed709942d00fdbdab558bfabb82471f38b3f3a3098df33171df96c38922d", "c10-onshift-two-offshift-one-20260930-01", 2),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict, section: str) -> dict:
    return {table["name"]: table for table in doc[section]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def values(table: dict, column: str) -> list:
    i = [c["name"] for c in table["columns"]].index(column)
    return [row[i] for row in rows(table)]


def check() -> dict:
    issues: list[str] = []

    def require(ok: bool, label: str) -> None:
        if not ok:
            issues.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    publications = {e["publication_id"] for e in read(HERE.parent / "publication-index-v1.json")["entries"]}
    parent_id = "C10.var02.operational_crew_failure_spare.1.0.0"
    require(parent_id in publications and contract["parent_publication_id"] == diff["parent_publication_id"] == parent_id, "accepted C10 parent publication")
    require(sha(PARENT) == PARENT_SHA == contract["parent_input_sha256"] == diff["parent_input_sha256"], "parent source fingerprint")
    require(sha(SHIFT_SCHEMA) == SCHEMA_SHA == contract["schema_source_input_sha256"] == diff["schema_source_input_sha256"], "shift schema source fingerprint")
    base = tables(parse_native(PARENT), "model")
    sources: dict[str, dict] = {}
    logs: dict[str, str] = {}
    reports: dict[str, dict] = {}
    for variant, (input_sha, run_id, onshift) in RUNS.items():
        source = HERE / f"{variant}-input.json"
        require(sha(source) == input_sha == contract["input_sha256"][variant] == diff["child_input_sha256"][variant], f"{variant} input fingerprint")
        model = tables(parse_native(source), "model")
        sources[variant] = model
        require(len(base) == 32 and len(model) == 35 and set(model) - set(base) == {"Shift", "ShiftProfile", "ShiftResource"} and set(base) - set(model) == set(), f"{variant} added shift tables")
        require(sorted(n for n in base if base[n] != model[n]) == ["Control", "ProblemDescription", "ResourceStationData"], f"{variant} parent table delta")
        require(rows(model["Control"])[0][17] == "N" and rows(base["Control"])[0][17] is None, f"{variant} DRAOS off shift zero")
        require(rows(model["ResourceStationData"]) == [["P-CREW", "BASE-01", None, None, None, 0.5, "OPERATION", 0.25, None, "CREW-DAY", None]], f"{variant} failure and shift profile")
        require(rows(model["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 3, None]], f"{variant} three allocated crew")
        require(rows(model["Shift"]) == [["DAY-OPEN", "Crew scheduled 7 to 10", None]] and rows(model["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 7, 10, 1, None, None]] and rows(model["ShiftResource"]) == [["DAY-OPEN", "BASE-01", "P-CREW", onshift, None, None]], f"{variant} 7-10 staffing")

        run = HERE / "runs" / run_id
        inv, closure, steps = read(run / "invocation.json"), read(run / "closure.json"), read(run / "steps.json")
        require(inv["case_id"] == "C10" and inv["variant"] == variant and inv["run_id"] == closure["run_id"] == run_id and inv["input_sha256"] == input_sha and inv["parent_sha256"] == PARENT_SHA, f"{variant} run identity")
        require(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} SSH and mutex")
        require(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} GUI identity")
        require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"] and closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} closure")
        for key, path in {"input": source, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
            require(closure["source_hashes_before"][key] == sha(path), f"{variant} source seal {key}")
        require(closure["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", f"{variant} executable hash")
        require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant} five guarded steps")
        for name, item in closure["raw"].items():
            file = run / name
            require(file.is_file() and file.stat().st_size == item["bytes"] and sha(file) == item["sha256"], f"{variant} raw seal {name}")
        require(read(run / "roundtrip-validation.json")["passed"], f"{variant} native roundtrip checker")
        input_rows = populated(parse_native(run / "input.json"))
        export_rows = populated(parse_native(run / "roundtrip-raw.json"))
        require(len(input_rows) == 24 and all(export_rows.get(name) == table for name, table in input_rows.items()), f"{variant} 24-table source roundtrip")
        calc = (run / "run.log").read_text(encoding="utf-8-sig")
        require("Errors: 0, Warnings: 2, Notes: 0" in calc and set(re.findall(r"warning\s+#(\d+)", calc, re.I)) == {"108", "126"}, f"{variant} zero-error conversion")
        require((run / "model.sxo").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 4, f"{variant} nonempty output")
        logs[variant] = (run / "model.log").read_text(encoding="utf-8-sig")
        reports[variant] = tables(parse_native(run / "report-raw.json"), "report")

    one, two = sources["onshift-three"], sources["onshift-two-offshift-one"]
    require(sorted(n for n in one if one[n] != two[n]) == ["ProblemDescription", "ShiftResource"], "sole paired business delta")
    for variant, (_, _, onshift) in RUNS.items():
        log = logs[variant]
        require(f"Time: 7  resource shift 1 starting at <P-CREW at <BASE-01,0>>" in log and f"Time: 7  resource shift 1 created at <P-CREW at <BASE-01,0>>" in log and f"Time: 10  resource shift 1 ended at <P-CREW at <BASE-01,0>>" in log, f"{variant} native shift boundaries")
        require(f"Free resources at: <BASE-01,0> P-CREW {onshift}" in log and "Time: 7.5 <TEACH-AIR-01,0> preparation started" in log and "Time: 7.5 <TEACH-AIR-01,1> preparation started" in log and log.count("Time: 7.5  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1") == 2, f"{variant} scheduled capacity fully booked")
        require(log.count("<P-CREW at <BASE-01,0>> Failed") == 1 and log.count("<P-CREW at <BASE-01,0>> Repaired") == 1 and "Time: 7.73494 <P-CREW at <BASE-01,0>> Failed" in log and "Time: 7.98494 <P-CREW at <BASE-01,0>> Repaired" in log, f"{variant} active crew failure and repair")
        require("is stopped due to a resource failure" not in log and "Time: 8 <TEACH-AIR-01,0> preparation ended" in log and "Time: 8 <TEACH-AIR-01,1> preparation ended" in log and "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log, f"{variant} uninterrupted tasks and mission")

        report = reports[variant]
        require(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"}, f"{variant} report tables")
        summary = report["ResultSummary"]
        require(len(rows(summary)) == 1 and all(values(summary, n) == [1] for n in ("NREP", "MTMF", "MSTF", "MSUF", "STMF")), f"{variant} one successful formation")
        resource = report["ResourceResults"]
        require(len(rows(resource)) == 72 and values(resource, "STINT") == [i / 2 for i in range(72)] and values(resource, "ETINT") == [(i + 1) / 2 for i in range(72)] and all(v == 3 for v in values(resource, "NR")), f"{variant} 72-bin three-crew ledger")
        expected_available = {i: onshift for i in range(14, 20)}
        require(all(math.isclose(v, expected_available.get(i, 0) - (0.5 if i == 15 and onshift == 3 else 0), abs_tol=1e-6) for i, v in enumerate(values(resource, "NRA"))), f"{variant} on-shift effective available capacity")
        require(values(resource, "NRUM")[15] == 2 and all(v == 0 for i, v in enumerate(values(resource, "NRUM")) if i != 15) and values(resource, "NRF")[15] == 0.5 and all(v == 0 for i, v in enumerate(values(resource, "NRF")) if i != 15) and all(v == 0 for v in values(resource, "NRW")), f"{variant} work/failure/zero-wait bins")
        total = report["ResourceResultsTotal"]
        require(len(rows(total)) == 1 and values(total, "NR") == [3] and math.isclose(values(total, "NRUM")[0] * 36, 1, abs_tol=1e-6) and math.isclose(values(total, "NRF")[0] * 36, 0.25, abs_tol=1e-6) and values(total, "NRW") == [0], f"{variant} resource totals")
        system = report["SystemResults"]
        require(len(rows(system)) == 72 and values(system, "NSYRY")[-1] == 2 and all(v == 0 for v in values(system, "NFAIL")), f"{variant} terminal two ready aircraft")
        stock = report["StockTotalResults"]
        require(len(rows(stock)) == 72 and all(v == 0 for n in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT") for v in values(stock, n)), f"{variant} zero stock movement")

    return {"schema": "simlox-c10-offshift-spare-author-validation/v1", "passed": not issues, "issues": issues,
            "runs": [{"variant": variant, "run_id": run_id, "input_sha256": input_sha, "closure_sha256": sha(HERE / "runs" / run_id / "closure.json"), "model_log_sha256": sha(HERE / "runs" / run_id / "model.log"), "report_raw_sha256": sha(HERE / "runs" / run_id / "report-raw.json")} for variant, (input_sha, run_id, _) in RUNS.items()],
            "scope": "one fixed-seed 7-10 shift: three allocated crew, two versus three scheduled; a 7.73494 failure leaves both preparation tasks uninterrupted and mission 8-9 successful, with the two-on-shift effective capacity remaining two at pool level"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["passed"] else 1)
