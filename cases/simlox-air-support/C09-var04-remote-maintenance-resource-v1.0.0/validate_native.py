"""Reconcile three C09.var04 native closures and first-replication events."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, sha

HERE = Path(__file__).resolve().parent
INPUT_HASHES = {
    "local": "1f7e87b3c7886f6b05ff2b2d9f04ee1a98e64445f8f5d6b660595eb2c5845730",
    "remote": "c0602d0a6bb3ee4603ac3be636ba81474dfbde33837f6a368ecdc6ded7e29ba1",
    "remote-disabled": "bc2b346e311650a0c5913e8b05662cd440e1ede9049ca20869d3b001f1274552",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def events(log: str, phrase: str) -> list[float]:
    return [float(m.group(1)) for m in re.finditer(r"^Time: ([\d.]+) .*" + re.escape(phrase), log, re.M)]


def check_run(variant: str) -> dict:
    run = HERE / "runs" / f"c09-var04-{variant}-20261002-01"
    errors: list[str] = []
    closure = read_json(run / "closure.json")
    invocation = read_json(run / "invocation.json")
    steps = read_json(run / "steps.json")
    checker = read_json(run / "roundtrip-validation.json")
    if closure["invocation_sha256"] != sha(run / "invocation.json"):
        errors.append("invocation SHA differs from closure")
    for name, item in closure["raw"].items():
        path = run / name
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            errors.append(f"raw seal differs: {name}")
    if closure["source_hashes_before"] != closure["source_hashes_after"]:
        errors.append("source changed during run")
    if closure.get("error") or len(steps) != 5 or any(s["status"] != "completed" or s["exit_code"] != 0 or not s["gui_preserved"] for s in steps):
        errors.append("native steps or GUI continuity failed")
    if invocation["variant"] != variant or invocation["input_sha256"] != INPUT_HASHES[variant] or sha(run / "input.json") != INPUT_HASHES[variant]:
        errors.append("input or variant identity differs")
    if not checker["passed"] or checker["differences"]:
        errors.append("native import/export identity failed")
    report = parse_native(run / "report-raw.json")["report"]["tables"]
    tables = {t["name"]: t for t in report}
    for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        rows = [r for i in tables[name]["instances"] for r in i["rows"]]
        if len(rows) != 72:
            errors.append(f"{name} expected 72 half-hour rows, got {len(rows)}")
        else:
            cols = [c["name"] for c in tables[name]["columns"]]
            start, end = cols.index("STINT"), cols.index("ETINT")
            if any(abs(row[start] - i * 0.5) > 1e-9 or abs(row[end] - (i + 1) * 0.5) > 1e-9 for i, row in enumerate(rows)):
                errors.append(f"{name} collection grid differs")
    system = tables["SystemResults"]
    sc = {c["name"]: i for i, c in enumerate(system["columns"])}
    sr = system["instances"][0]["rows"]
    failures = sum(row[sc["NFAIL"]] or 0 for row in sr)
    repairs = sum(row[sc["NREPT"]] or 0 for row in sr)
    ready = sr[-1][sc["NSYRY"]]
    waiting = sr[-1][sc["NSYWR"]]
    if failures != 2 or (repairs, ready, waiting) != ((0, 0, 2) if variant == "remote-disabled" else (2, 2, 0)):
        errors.append("SystemResults failures, repairs or terminal state differ")
    resource = tables["ResourceResults"]
    rc = {c["name"]: i for i, c in enumerate(resource["columns"])}
    rr = resource["instances"][0]["rows"]
    if any(abs(row[rc["NR"]] + row[rc["NRRT"]] - row[rc["NRN"]]) > 1e-5 for row in rr):
        errors.append("aggregate ResourceResults NR+NRRT conservation differs")
    transit_hours = sum(row[rc["NRRT"]] * (row[rc["ETINT"]] - row[rc["STINT"]]) for row in rr)
    if abs(transit_hours - (0.75 if variant == "remote" else 0)) > 1e-5:
        errors.append("aggregate resource transit hours differ")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if "Input conversion completed. Errors: 0" not in calc:
        errors.append("native conversion errors present")
    repair_started = re.findall(r"^Time: ([\d.]+)  system DIRP task 2 on <TEACH-AIR-01,0> started$", log, re.M)
    repair_completed = [float(m) for m in re.findall(r"^Time: ([\d.]+)  system DIRP task 2 on <TEACH-AIR-01,0> completed$", log, re.M)]
    if not repair_started or (variant != "remote-disabled" and len(repair_completed) != 1) or (variant == "remote-disabled" and repair_completed):
        errors.append("first aircraft primary repair behavior differs")
    loan_created = events(log, "remote resource transport task 3 created")
    loan_arrived = events(log, "remote resource transport task 3 arrives")
    return_created = events(log, "return resource transport task 0 created")
    return_arrived = events(log, "return resource transport task 0 arrives")
    if variant == "remote":
        if not (len(loan_created) == len(loan_arrived) == len(return_created) == len(return_arrived) == 1):
            errors.append("expected one outward and return resource transport")
        else:
            if abs((loan_arrived[0] - loan_created[0]) - 0.25) > 1e-5:
                errors.append("outward transport duration differs")
            if abs((return_arrived[0] - return_created[0]) - 0.5) > 1e-4:
                errors.append("return transport duration differs")
        for phrase in ("Free resources at: <BASE-01,0> P-CREW 2, P-MECH 0",
                       "Free resources at: <BASE-02,0> P-MECH 1",
                       "<P-MECH at <BASE-01,0>> remote transport arrives: 1",
                       "<P-MECH at <BASE-02,0>> return transport arrives: 1"):
            if phrase not in log:
                errors.append(f"resource conservation ledger missing: {phrase}")
    elif loan_created or loan_arrived or return_created or return_arrived:
        errors.append("control unexpectedly transported a remote resource")
    if variant == "remote-disabled" and "Tasks waiting for resources at: <BASE-01,0> 2" not in log:
        errors.append("disabled arm did not retain two waiting repairs")
    return {
        "variant": variant, "passed": not errors, "errors": errors,
        "run_id": run.name, "input_sha256": INPUT_HASHES[variant],
        "closure_sha256": sha(run / "closure.json"),
        "raw_seals": len(closure["raw"]), "native_steps": len(steps),
        "source_hashes_stable": closure["source_hashes_before"] == closure["source_hashes_after"],
        "report_bins_each": 72,
        "report_counts": {"failures": failures, "completed_repairs": repairs,
                          "terminal_ready": ready, "terminal_waiting_resource": waiting,
                          "resource_transit_hours": transit_hours},
        "events_hour": {"loan_created": loan_created, "loan_arrived": loan_arrived,
                        "return_created": return_created, "return_arrived": return_arrived,
                        "first_repair_completed": repair_completed},
    }


def main() -> int:
    result = {"schema": "simlox-c09-var04-author-validation/v1",
              "scope": "first_replication_native_primary_maintenance_remote_resource",
              "runs": [check_run(v) for v in INPUT_HASHES]}
    result["passed"] = all(r["passed"] for r in result["runs"])
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
