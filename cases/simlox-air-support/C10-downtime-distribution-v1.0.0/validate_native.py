"""Read-only author replay of C10.var04 fixed versus exponential repair time."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT_PACKAGE = HERE.parent / "C10-resource-failure-v1.0.0"
PARENT = PARENT_PACKAGE / "oper-no-spare-input.json"
CHILD = HERE / "exponential-two-crew-input.json"
PARENT_RUN = PARENT_PACKAGE / "runs" / "c10-oper-no-spare-20260930-01"
CHILD_RUN = HERE / "runs" / "c10-exponential-two-crew-20260930-01"
PARENT_SHA = "c334c1d6c0efa89f9ff70151a45180cac53b9ae05bf1a783219b566f41dbd62b"
CHILD_SHA = "24c8d3c6c16b9f5354063673c24b3dbccdc84329627ab870aba695ce0c485865"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict, section: str) -> dict:
    return {t["name"]: t for t in doc[section]["tables"]}


def rows(t: dict) -> list[list]:
    return [row for inst in t["instances"] for row in inst["rows"]]


def col(t: dict, name: str) -> list:
    i = [c["name"] for c in t["columns"]].index(name)
    return [row[i] for row in rows(t)]


def failures(log: str) -> list[tuple[float, str]]:
    return [(float(t), action) for t, action in re.findall(
        r"Time: ([0-9.]+) <P-CREW at <BASE-01,0>> (Failed|Repaired)\s*", log)]


def expected_nrf(events: list[tuple[float, str]]) -> list[float]:
    values = []
    active = 0
    at = 0
    for i in range(72):
        start, end = i / 2, (i + 1) / 2
        cursor, area = start, 0.0
        while at < len(events) and events[at][0] < end:
            when, action = events[at]
            assert when >= cursor
            area += (when - cursor) * active
            active += 1 if action == "Failed" else -1
            assert 0 <= active <= 2
            cursor = when
            at += 1
        values.append((area + (end - cursor) * active) / 0.5)
    assert at == len(events) and active == 0
    return values


def check() -> dict:
    checks = 0
    issues: list[str] = []

    def require(ok: bool, name: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            issues.append(name)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    published = {e["publication_id"] for e in read(HERE.parent / "publication-index-v1.json")["entries"]}
    parent_id = "C10.var02.operational_crew_failure_spare.1.0.0"
    require(parent_id in published and contract["parent_publication_id"] == diff["parent_publication_id"] == parent_id, "accepted parent")
    require(sha(PARENT) == contract["parent_input_sha256"] == diff["parent_input_sha256"] == PARENT_SHA, "parent hash")
    require(sha(CHILD) == contract["child_input_sha256"] == diff["child_input_sha256"] == CHILD_SHA, "child hash")
    before, after = tables(parse_native(PARENT), "model"), tables(parse_native(CHILD), "model")
    require(len(before) == len(after) == 32 and before.keys() == after.keys() and
            sorted(n for n in before if before[n] != after[n]) == ["ProblemDescription", "ResourceStationData"], "32-table exact delta")
    require(rows(before["ResourceStationData"]) == [["P-CREW", "BASE-01", None, None, None, 0.5, "OPERATION", 0.25, None, None, None]] and
            rows(after["ResourceStationData"]) == [["P-CREW", "BASE-01", None, None, None, 0.5, "OPERATION", 0.25, "<EXP>", None, None]], "one RMDTD field")

    pclose, cclose, inv = read(PARENT_RUN / "closure.json"), read(CHILD_RUN / "closure.json"), read(CHILD_RUN / "invocation.json")
    pentry = next(e for e in read(PARENT_PACKAGE / "evidence-index.json")["runs"] if e["run_id"] == PARENT_RUN.name)
    require(pentry["closure_sha256"] == sha(PARENT_RUN / "closure.json") and pclose["source_hashes_before"] == pclose["source_hashes_after"], "accepted parent run seal")
    for tag, run, close in (("parent", PARENT_RUN, pclose), ("child", CHILD_RUN, cclose)):
        for name, item in close["raw"].items():
            path = run / name
            require(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"{tag} raw {name}")
    require(inv["run_id"] == cclose["run_id"] == CHILD_RUN.name and inv["variant"] == "exponential-two-crew" and inv["input_sha256"] == CHILD_SHA and inv["parent_sha256"] == PARENT_SHA, "child invocation identity")
    require(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "guarded SSH and mutex")
    require(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and cclose["error"] is None and cclose["source_hashes_before"] == cclose["source_hashes_after"] and cclose["invocation_sha256"] == sha(CHILD_RUN / "invocation.json"), "GUI and child closure")
    for key, path in {"input": CHILD, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
        require(cclose["source_hashes_before"][key] == sha(path), f"frozen source {key}")
    require(cclose["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "native executable")
    steps = read(CHILD_RUN / "steps.json")
    require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "five native steps")
    require(read(CHILD_RUN / "roundtrip-validation.json")["passed"], "native checker")
    source, exported = populated(parse_native(CHILD_RUN / "input.json")), populated(parse_native(CHILD_RUN / "roundtrip-raw.json"))
    require(len(source) == 21 and all(exported.get(n) == t for n, t in source.items()), "21 source tables exact roundtrip")
    runlog = (CHILD_RUN / "run.log").read_text(encoding="utf-8-sig")
    require("Errors: 0, Warnings: 2, Notes: 0" in runlog and set(re.findall(r"warning\s+#(\d+)", runlog, re.I)) == {"108", "126"}, "zero-error conversion")
    require((CHILD_RUN / "model.sxo").stat().st_size > 4 and (CHILD_RUN / "report-raw.json").stat().st_size > 4, "nonempty output")

    logs = [(PARENT_RUN / "model.log").read_text(encoding="utf-8-sig"), (CHILD_RUN / "model.log").read_text(encoding="utf-8-sig")]
    pairs = [failures(log) for log in logs]
    require(pairs == [[(7.73494, "Failed"), (7.98494, "Repaired")], [(7.73494, "Failed"), (8.3441, "Repaired")]], "observed failure and repair times")
    require(math.isclose(pairs[0][1][0]-pairs[0][0][0], .25, abs_tol=1e-5) and math.isclose(pairs[1][1][0]-pairs[1][0][0], .60916, abs_tol=1e-5), "fixed versus sampled repair duration")
    for tag, log, start, success in (("parent", logs[0], 8.25, 9.25), ("child", logs[1], 8.26506, 9.26506)):
        require(log.count("is stopped due to a resource failure") == 1 and
                "Time: 7.73494  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> is stopped due to a resource failure, time left= 0.265061" in log, f"{tag} task stop")
        require(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and
                f"Time: {success} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log, f"{tag} mission")
    require("Time: 8  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1" in logs[1] and
            "Time: 8.26506  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1" in logs[1] and
            pairs[1][1][0] > 8.26506, "child resumes with freed pool capacity before repair")

    metrics = {}
    for tag, run, events in (("fixed", PARENT_RUN, pairs[0]), ("exponential", CHILD_RUN, pairs[1])):
        report = tables(parse_native(run / "report-raw.json"), "report")
        require(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"}, f"{tag} report tables")
        require(all(col(report["ResultSummary"], name) == [1] for name in ("NREP", "MTMF", "MSTF", "MSUF", "STMF")), f"{tag} mission summary")
        resource = report["ResourceResults"]
        require(len(rows(resource)) == 72 and col(resource, "STINT") == [i/2 for i in range(72)] and col(resource, "ETINT") == [(i+1)/2 for i in range(72)] and all(n == 2 for n in col(resource, "NR")), f"{tag} resource bins")
        require(all(abs(a-b) < 2e-4 for a,b in zip(expected_nrf(events), col(resource, "NRF"))), f"{tag} failed-resource bins")
        areas = {name: sum(col(resource, name))/2 for name in ("NRUM", "NRW", "NRF")}
        total = report["ResourceResultsTotal"]
        require(len(rows(total)) == 1 and all(math.isclose(col(total, name)[0]*36, value, abs_tol=3e-4) for name,value in areas.items()), f"{tag} interval/total resource reconciliation")
        require(math.isclose(areas["NRUM"], 1, abs_tol=1e-5) and math.isclose(areas["NRF"], events[1][0]-events[0][0], abs_tol=2e-4), f"{tag} productive and failed hours")
        system, stock = report["SystemResults"], report["StockTotalResults"]
        require(len(rows(system)) == 72 and col(system, "NSYRY")[-1] == 2 and all(v == 0 for v in col(system, "NFAIL")), f"{tag} ready aircraft and zero failures")
        require(len(rows(stock)) == 72 and all(v == 0 for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT") for v in col(stock, name)), f"{tag} zero stock movement")
        metrics[tag] = areas
    require(metrics["exponential"]["NRF"] > metrics["fixed"]["NRF"] and metrics["exponential"]["NRW"] > metrics["fixed"]["NRW"], "repair exposure and waiting contrast")
    return {"schema": "simlox-c10-downtime-distribution-author-replay/v1", "passed": not issues, "checks": checks, "issues": issues, "metrics": metrics,
            "scope": "one_seed_exponential_downtime_sample_and_fixed_parent", "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = check()
    except Exception as exc:
        result = {"schema": "simlox-c10-downtime-distribution-author-replay/v1", "passed": False, "issues": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
