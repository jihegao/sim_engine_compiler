"""Read-only author replay of the bounded C10.var05 in-flight crew failure pair."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C05-mission-resource-v1.0.0" / "capacity-2-input.json"
SCHEMA = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
RUNS = {
    "five-hour-control": HERE / "runs" / "c10-mission-five-hour-control-20260930-01",
    "five-hour-failure": HERE / "runs" / "c10-mission-five-hour-failure-20260930-01",
}
HASHES = {
    "five-hour-control": "cd3a757cda6464584a8edd4542533019068551fc8bab47e6fe0058cb3785a00c",
    "five-hour-failure": "876abeefe8bea39458bc93f3f809c88e9c97e03adf47cbbeff607f994f543396",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict, section: str) -> dict:
    return {t["name"]: t for t in doc[section]["tables"]}


def rows(t: dict) -> list[list]:
    return [r for i in t["instances"] for r in i["rows"]]


def col(t: dict, name: str) -> list:
    i = [c["name"] for c in t["columns"]].index(name)
    return [r[i] for r in rows(t)]


def bin_average(segments: list[tuple[float, float, float]]) -> list[float]:
    return [sum(max(0, min((i+1)/2, end)-max(i/2, start))*value for start,end,value in segments)/.5 for i in range(72)]


def check() -> dict:
    issues: list[str] = []
    checks = 0

    def require(ok: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            issues.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    published = {e["publication_id"] for e in read(HERE.parent / "publication-index-v1.json")["entries"]}
    parent_id = "C05.mission_resource_capacity.1.0.0"
    require(parent_id in published and contract["parent_publication_id"] == diff["parent_publication_id"] == parent_id, "accepted parent")
    require(sha(PARENT) == contract["parent_input_sha256"] == diff["parent_input_sha256"] == "d2ea6e874eff82f1e50f271051010985c28adfba7aab94d2a0a0b343b989e865", "parent hash")
    require(sha(SCHEMA) == contract["schema_source_input_sha256"] == "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e", "schema hash")
    source = {v: tables(parse_native(HERE / f"{v}-input.json"), "model") for v in RUNS}
    parent = tables(parse_native(PARENT), "model")
    control, failure = source.values()
    require(len(parent) == len(control) == 32 and len(failure) == 33 and sorted(n for n in parent if parent[n] != control[n]) == ["MissionType", "ProblemDescription"] and sorted(n for n in control if n in failure and control[n] != failure[n]) == ["ProblemDescription"] and set(failure)-set(control) == {"ResourceStationData"}, "exact table delta")
    old_mission, new_mission = rows(parent["MissionType"])[0], rows(control["MissionType"])[0]
    require(old_mission[5] == 2.0 and new_mission[5] == rows(failure["MissionType"])[0][5] == 5.0 and all(a == b for i,(a,b) in enumerate(zip(old_mission,new_mission)) if i not in (1,5)), "matched five-hour duration")
    require(rows(control["MissionResource"]) == rows(failure["MissionResource"]) == [["BASIC-MISSION", "TEACH-AIR-01", "MISSION-CREW", 1, None]] and rows(control["ResourceAllocation"]) == rows(failure["ResourceAllocation"]) == [["AIR_BASIC", "MISSION-CREW", "BASE-01", 2, None]], "same mission crew allocation")
    require(rows(failure["ResourceStationData"]) == [["MISSION-CREW", "BASE-01", None, None, None, 3.0, "OPERATION", .25, None, None, None]], "failure row")
    for variant, run in RUNS.items():
        source_file = HERE / f"{variant}-input.json"
        require(sha(source_file) == HASHES[variant] == contract["input_sha256"][variant], f"{variant} input hash")
        inv, close, steps = read(run / "invocation.json"), read(run / "closure.json"), read(run / "steps.json")
        require(inv["variant"] == variant and inv["run_id"] == close["run_id"] == run.name and inv["input_sha256"] == HASHES[variant] and inv["parent_sha256"] == contract["parent_input_sha256"], f"{variant} invocation")
        require(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} SSH/mutex/GUI")
        require(close["error"] is None and close["source_hashes_before"] == close["source_hashes_after"] and close["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} closure")
        for key, file in {"input": source_file, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
            require(close["source_hashes_before"][key] == sha(file), f"{variant} frozen {key}")
        require(close["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", f"{variant} executable")
        require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant} native steps")
        for name, item in close["raw"].items():
            file = run / name
            require(file.is_file() and file.stat().st_size == item["bytes"] and sha(file) == item["sha256"], f"{variant} raw {name}")
        require(read(run / "roundtrip-validation.json")["passed"], f"{variant} native roundtrip checker")
        before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        require(len(before) == (16 if variant == "five-hour-control" else 17) and all(after.get(n) == t for n,t in before.items()), f"{variant} exact row-containing roundtrip")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig")
        require("Errors: 0, Warnings: 2, Notes: 0" in runlog and set(re.findall(r"warning\s+#(\d+)", runlog, re.I)) == {"108", "126"}, f"{variant} zero-error conversion")
        require((run / "model.sxo").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 4, f"{variant} nonempty output")

    logs = {v: (r / "model.log").read_text(encoding="utf-8-sig") for v,r in RUNS.items()}
    ctl, fail = logs.values()
    require("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 5" in ctl and "Time: 13 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in ctl and " Failed " not in ctl, "five-hour control success")
    require("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 5" in fail and "Time: 11.655 <MISSION-CREW at <BASE-01,0>> Failed" in fail and "Time: 11.655 <TEACH-AIR-01,0> resource failure on MISSION-CREW when on mission" in fail, "assigned in-flight failure")
    require("<TEACH-AIR-01,0> aborts its mission" in fail and "Time: 11.655 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted: <TEACH-AIR-01,1>" in fail and "mission success" not in fail, "aircraft and whole formation abort")
    require("Time: 12.905 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed" in fail and fail.count("System arrives <TEACH-AIR-01,") == 2 and "Time: 13.155 <MISSION-CREW at <BASE-01,0>> Repaired" in fail, "return and repair chronology")
    require(fail.index("Time: 12.905 <TEACH-AIR-01,0> releases faulty resources") < fail.index("Time: 13.155 <MISSION-CREW at <BASE-01,0>> Repaired"), "faulty crew released at return before repair")

    metrics = {}
    for variant, run in RUNS.items():
        report = tables(parse_native(run / "report-raw.json"), "report")
        require(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"}, f"{variant} report tables")
        summary = report["ResultSummary"]
        require(col(summary, "NREP") == [1] and col(summary, "MSTF") == [1] and col(summary, "MSUF") == ([1] if variant == "five-hour-control" else [0]), f"{variant} mission result summary")
        resource = report["ResourceResults"]
        require(len(rows(resource)) == 72 and col(resource, "STINT") == [i/2 for i in range(72)] and col(resource, "ETINT") == [(i+1)/2 for i in range(72)] and all(n == 2 for n in col(resource, "NR")), f"{variant} resource horizon")
        if variant == "five-hour-control":
            expected_failed = [0.0]*72
            expected_mission = bin_average([(8,13,2)])
        else:
            expected_failed = bin_average([(11.655,13.155,1)])
            expected_mission = bin_average([(8,11.655,2),(11.655,12.905,1)])
        require(all(abs(a-b) < 2e-4 for a,b in zip(expected_failed,col(resource,"NRF"))), f"{variant} every failed-resource bin")
        require(all(abs(a-b) < 2e-4 for a,b in zip(expected_mission,col(resource,"NRMO"))), f"{variant} every mission-resource bin")
        areas = {name:sum(col(resource,name))/2 for name in ("NRMO","NRMA","NRF")}
        total = report["ResourceResultsTotal"]
        require(all(math.isclose(col(total,name)[0]*36,value,abs_tol=4e-4) for name,value in areas.items()), f"{variant} interval/total resource ledger")
        require(math.isclose(areas["NRMA"],2,abs_tol=1e-5) and math.isclose(areas["NRF"],0 if variant=="five-hour-control" else 1.5,abs_tol=2e-4), f"{variant} mission assignment and failed exposure")
        system, stock = report["SystemResults"], report["StockTotalResults"]
        require(len(rows(system)) == 72 and col(system,"NSYRY")[-1] == 2 and all(v==0 for v in col(system,"NFAIL")), f"{variant} terminal two ready and no aircraft failure")
        require(len(rows(stock)) == 72 and all(v==0 for name in ("NDF","NDD","NDR","NDP","NLD","NWT") for v in col(stock,name)), f"{variant} no stock movement")
        metrics[variant] = areas
    require(math.isclose(metrics["five-hour-control"]["NRMO"],10,abs_tol=1e-5) and math.isclose(metrics["five-hour-failure"]["NRMO"],8.56,abs_tol=2e-4), "mission resource-hour contrast")
    return {"schema":"simlox-c10-mission-resource-failure-author-replay/v1","passed":not issues,"checks":checks,"issues":issues,"metrics":metrics,"scope":"one_seed_inflight_crew_failure_and_abort","publication_state":"not_published"}


if __name__ == "__main__":
    try:
        result = check()
    except Exception as exc:
        result = {"schema":"simlox-c10-mission-resource-failure-author-replay/v1","passed":False,"issues":[f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if result["passed"] else 1)
