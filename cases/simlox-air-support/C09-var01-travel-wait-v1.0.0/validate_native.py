"""Validate three C09.var01 native run closures and travel/wait boundary."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, sha

HERE = Path(__file__).resolve().parent
HASHES = {
    "short": "739d7a9ad8e6759a20401a3bf65c63b13c39c42e035a7d9acc28af6f5fc83fe7",
    "equal": "4595a90dafb24ebc4b36662dd2f5738d7f03f1001f4acb8347099f181c15a177",
    "long": "0bf327220330d00b79de37e920ff62529cee0d40265e9d9a1f57f0b3cb165ae7",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def event_time(log: str, phrase: str) -> list[float]:
    return [float(m) for m in re.findall(r"^Time: ([\d.]+) .*" + re.escape(phrase), log, re.M)]


def check(variant: str) -> dict:
    run = HERE / "runs" / f"c09-var01-{variant}-20261002-01"
    inv, closure, steps = (load(run / x) for x in ("invocation.json", "closure.json", "steps.json"))
    errors: list[str] = []
    if inv["variant"] != variant or inv["input_sha256"] != HASHES[variant] or sha(run / "input.json") != HASHES[variant]:
        errors.append("input identity differs")
    if sha(run / "invocation.json") != closure["invocation_sha256"]:
        errors.append("invocation seal differs")
    if closure["source_hashes_before"] != closure["source_hashes_after"]:
        errors.append("source changed during run")
    for name, seal in closure["raw"].items():
        file = run / name
        if not file.is_file() or file.stat().st_size != seal["bytes"] or sha(file) != seal["sha256"]:
            errors.append(f"raw seal differs: {name}")
    if len(closure["raw"]) != 12 or closure["error"] or [s["name"] for s in steps] != ["import", "export", "calc", "jsonreport", "check_import_export"]:
        errors.append("native closure or steps differ")
    if any(s["status"] != "completed" or s["exit_code"] != 0 or not s["gui_preserved"] for s in steps):
        errors.append("native step or GUI continuity failed")
    if not load(run / "roundtrip-validation.json")["passed"]:
        errors.append("authored table roundtrip failed")
    if "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" not in (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"):
        errors.append("native converter diagnostics differ")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    outward = event_time(log, "remote resource transport task 3 created")
    outward_arrival = event_time(log, "remote resource transport task 3 arrives")
    returning = event_time(log, "return resource transport task 0 created")
    returned = event_time(log, "return resource transport task 0 arrives")
    r0 = [float(x) for x in re.findall(r"^Time: ([\d.]+)  system DIRP task 2 on <TEACH-AIR-01,0> completed$", log, re.M)]
    r1 = [float(x) for x in re.findall(r"^Time: ([\d.]+)  system DIRP task 3 on <TEACH-AIR-01,1> completed$", log, re.M)]
    if len(r0) != 1 or abs(r0[0] - 9.03243) > 1e-5 or len(r1) != 1 or abs(r1[0] - (9.28243 if variant == "short" else 9.53243)) > 1e-5:
        errors.append("repair completion boundary differs")
    if variant == "short":
        if [outward, outward_arrival, returning, returned] != [[8.53243], [8.78243], [9.03243], [9.53243]]:
            errors.append("short travel loan or return times differ")
        for phrase in ("<P-MECH at <BASE-01,0>> remote transport arrives: 1",
                       "<P-MECH at <BASE-02,0>> return transport arrives: 1"):
            if phrase not in log:
                errors.append(f"station pool movement missing: {phrase}")
    elif outward or outward_arrival or returning or returned:
        errors.append("equal/long arm unexpectedly transports remote resource")
    report = parse_native(run / "report-raw.json")["report"]["tables"]
    tables = {t["name"]: t for t in report}
    for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        t = tables[name]
        rows = t["instances"][0]["rows"]
        cols = {c["name"]: i for i, c in enumerate(t["columns"])}
        if len(rows) != 72 or any(abs(row[cols["STINT"]] - i * 0.5) > 1e-9 or abs(row[cols["ETINT"]] - (i + 1) * 0.5) > 1e-9 for i, row in enumerate(rows)):
            errors.append(f"{name} grid differs")
    system = tables["SystemResults"]
    sc = {c["name"]: i for i, c in enumerate(system["columns"])}
    sr = system["instances"][0]["rows"]
    failures = sum(r[sc["NFAIL"]] or 0 for r in sr)
    repairs = sum(r[sc["NREPT"]] or 0 for r in sr)
    ready = sr[-1][sc["NSYRY"]]
    if (failures, repairs, ready) != (2, 2, 2):
        errors.append("SystemResults totals differ")
    resource = tables["ResourceResults"]
    rc = {c["name"]: i for i, c in enumerate(resource["columns"])}
    rr = resource["instances"][0]["rows"]
    max_error = max(abs(r[rc["NR"]] + r[rc["NRRT"]] - r[rc["NRN"]]) for r in rr)
    transit = sum(r[rc["NRRT"]] * (r[rc["ETINT"]] - r[rc["STINT"]]) for r in rr)
    if max_error > 1e-5 or abs(transit - (0.75 if variant == "short" else 0)) > 1e-5:
        errors.append("resource conservation or transit-hours differs")
    return {"variant": variant, "run_id": run.name, "passed": not errors, "errors": errors,
            "closure_sha256": sha(run / "closure.json"), "raw_seals": len(closure["raw"]),
            "populated_tables": len(load(run / "roundtrip-validation.json")["populated_tables"]),
            "events_hour": {"outward": outward, "outward_arrival": outward_arrival,
                            "return": returning, "return_arrival": returned,
                            "first_repair_complete": r0, "second_repair_complete": r1},
            "report": {"bins_each": 72, "failures": failures, "repairs": repairs,
                       "terminal_ready": ready, "resource_transit_hours": transit,
                       "max_resource_conservation_error": max_error}}


def main() -> int:
    result = {"schema": "simlox-c09-var01-author-validation/v1",
              "scope": "fixed_seed_primary_repair_travel_vs_local_wait",
              "runs": [check(v) for v in HASHES]}
    result["passed"] = all(r["passed"] for r in result["runs"])
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
