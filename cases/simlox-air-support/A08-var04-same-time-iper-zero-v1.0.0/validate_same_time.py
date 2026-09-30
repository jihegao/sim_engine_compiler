"""Replay A08.var04 aggregate and 32 sealed one-replication seed runs."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, OUT as INPUT, PARENT, PARENT_SHA, build
from build_seed_matrix import MANIFEST, SEEDS, input_bytes, manifest_bytes
from check_roundtrip import parse_native, populated

AGGREGATE_ID = "a08-var04-same-time-v100-ssh-20260930-01"
MATRIX_ID = "a08-var04-seed-matrix-v100-ssh-20260930-02"
AGGREGATE = HERE / "runs" / AGGREGATE_ID
MATRIX = HERE / "runs" / MATRIX_ID
INPUT_SHA = "bae76ba5a88871129fb2669a8d04744745b8831f11d0dec96c7594d621793485"
MANIFEST_SHA = "ce971c2ff06054752e272feffd4e78a09102052e0903c6cb64b8cdd155af1348"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
OUT = HERE / "review" / "author-same-time-validation-2026-09-30.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table, = (t for t in doc[root]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in table["instances"][0]["rows"]]


def event_times(event: str, mission_id: int, marker: str) -> list[float]:
    pattern = rf"(?m)^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,{mission_id}> {re.escape(marker)}"
    return [float(m.group(1)) for m in re.finditer(pattern, event)]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tol: float = 1e-4) -> None:
        checks.append({"name": name, "passed": math.isclose(actual, expected, abs_tol=tol),
                       "actual": actual, "expected": expected, "abs_tol": tol})

    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    child = json.loads(INPUT.read_text(encoding="utf-8"))
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    matrix_contract = json.loads((HERE / "contract-seed-matrix-v1.json").read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ck("accepted A08.var01 parent SHA", sha(PARENT), PARENT_SHA)
    ck("frozen A08 input SHA", sha(INPUT), INPUT_SHA)
    ck("A08 builder identity", build(), child)
    ck("source contract", (contract["parent"]["input_sha256"], contract["native_input_sha256"]),
       (PARENT_SHA, INPUT_SHA))
    ck("source diff", (diff["parent_sha256"], diff["child_sha256"]), (PARENT_SHA, INPUT_SHA))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("changed tables only", sorted(k for k in before if before[k] != after[k]),
       ["OperationProfile", "ProblemDescription"])
    ck("29 unchanged tables", sum(before[k] == after[k] for k in before), 29)
    ck("13 populated source tables", len(populated(child)), 13)
    profile, = rows(child, "model", "OperationProfile")
    ck("zero-period fixed-count profile", tuple(profile[k] for k in
       ("STIM", "ITYPE", "IQTY", "IQTYD", "IPER", "IDISP")),
       (8, "RANDOM", 3, None, 0, "RANDOM"))
    ck("32 replications and three aircraft", (rows(child, "model", "Control")[0]["NREPS"],
                                            rows(child, "model", "SystemDeployment")[0]["QTYPS"]), (32, 3))
    ck("manifest deterministic", MANIFEST.read_bytes() == manifest_bytes(), True)
    ck("manifest SHA", sha(MANIFEST), MANIFEST_SHA)
    ck("matrix contract binding", (matrix_contract["parent_contract_sha256"],
                                    matrix_contract["aggregate_input_sha256"],
                                    matrix_contract["seed_manifest_sha256"],
                                    matrix_contract["seed_generator_sha256"]),
       (sha(HERE / "contract.json"), INPUT_SHA, MANIFEST_SHA, sha(HERE / "build_seed_matrix.py")))
    ck("seed list", [x["seed"] for x in manifest["seeds"]], list(SEEDS))

    aggregate_inv = json.loads((AGGREGATE / "invocation.json").read_text(encoding="utf-8-sig"))
    aggregate_closure = json.loads((AGGREGATE / "closure.json").read_text(encoding="utf-8-sig"))
    aggregate_steps = json.loads((AGGREGATE / "steps.json").read_text(encoding="utf-8-sig"))
    ck("aggregate session-0 SSH", (aggregate_inv["session_id"], aggregate_inv["ssh_connection_present"],
                                      "sshd.exe" in [s.lower() for s in aggregate_inv["ssh_ancestor_names"]]),
       (0, True, True))
    ck("aggregate GUI and mutex", (aggregate_inv["gui"]["pid"], aggregate_inv["gui"]["session_id"],
                                    aggregate_inv["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("aggregate invocation seal", aggregate_closure["invocation_sha256"], sha(AGGREGATE / "invocation.json"))
    ck("aggregate closure", (aggregate_closure["error"],
                              aggregate_closure["source_hashes_before"] == aggregate_closure["source_hashes_after"]),
       (None, True))
    ck("aggregate runner source", aggregate_closure["source_hashes_before"]["runner_script"],
       sha(HERE / "run_native_ssh.ps1"))
    ck("aggregate steps", [(s["name"], s["status"], s["exit_code"]) for s in aggregate_steps],
       [(n, "completed", 0) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
    for name, info in aggregate_closure["raw"].items():
        path = AGGREGATE / name
        ck(f"aggregate raw seal {name}", (sha(path), path.stat().st_size),
           (info["sha256"], info["bytes"]))
    ck("aggregate report source copy", sha(AGGREGATE / "input.json"), INPUT_SHA)
    aggregate_roundtrip = json.loads((AGGREGATE / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    ck("aggregate source roundtrip", (aggregate_roundtrip["passed"],
                                      aggregate_roundtrip["source_sha256"],
                                      len(aggregate_roundtrip["populated_tables"])),
       (True, INPUT_SHA, 13))
    aggregate_run_log = (AGGREGATE / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", aggregate_run_log)
    ck("aggregate conversion", conversion.groups() if conversion else None, ("0", "2", "0"))
    ck("aggregate warning codes", sorted(re.findall(r"warning #(\d+)", aggregate_run_log)), ["108", "126"])
    aggregate_report = parse_native(AGGREGATE / "report-raw.json")
    aggregate_summary, = rows(aggregate_report, "report", "ResultSummary")
    ck("aggregate replications", aggregate_summary["NREP"], 32)
    aggregate_system = rows(aggregate_report, "report", "SystemResults")
    aggregate_stock = rows(aggregate_report, "report", "StockTotalResults")
    ck("aggregate bins", (len(aggregate_system), len(aggregate_stock)), (72, 72))
    ck("aggregate system intervals", [(r["STINT"], r["ETINT"]) for r in aggregate_system],
       [(i*.5, (i+1)*.5) for i in range(72)])
    ck("aggregate stock intervals", [(r["STINT"], r["ETINT"]) for r in aggregate_stock],
       [(i*.5, (i+1)*.5) for i in range(72)])
    near("aggregate average operation hours", sum((r["NSYMO"] or 0)*.5 for r in aggregate_system), 6)
    ck("aggregate no system failure or repair", tuple(sum(r[k] or 0 for r in aggregate_system)
       for k in ("NFAIL", "NREPT", "NPSTA", "NPSUC")), (0, 0, 0, 0))
    ck("aggregate zero stock demand/backorder", all(all(r[k] == 0 for k in
       ("NDF", "NDD", "NDR", "NDP", "NBO")) for r in aggregate_stock), True)
    ck("aggregate terminal readiness", aggregate_system[-1]["NSYRY"], 3)
    aggregate_event = (AGGREGATE / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    aggregate_logged_starts = [event_times(aggregate_event, i, "mission starting")[0] for i in (1, 2, 3)]
    ck("aggregate log has only three starts", aggregate_event.count("mission starting, duration"), 3)
    ck("aggregate three simultaneous starts", aggregate_logged_starts, [8, 8, 8])
    ck("aggregate three simultaneous successes", [event_times(aggregate_event, i, "mission success") for i in (1, 2, 3)], [[10], [10], [10]])
    ck("aggregate three simultaneous completions", [event_times(aggregate_event, i, "mission completed") for i in (1, 2, 3)], [[10], [10], [10]])

    invocation = json.loads((MATRIX / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((MATRIX / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((MATRIX / "steps.json").read_text(encoding="utf-8-sig"))
    ck("matrix identity", invocation["run_id"], MATRIX_ID)
    ck("matrix session-0 SSH", (invocation["session_id"], invocation["ssh_connection_present"],
                                   "sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]]),
       (0, True, True))
    ck("matrix GUI and mutex", (invocation["gui"]["pid"], invocation["gui"]["session_id"],
                                 invocation["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("matrix native executable", invocation["source_hashes_before"]["simlox_exe"], EXE_SHA)
    ck("matrix invocation seal", closure["invocation_sha256"], sha(MATRIX / "invocation.json"))
    ck("matrix closure", (closure["error"], closure["completed_steps"], closure["expected_steps"]),
       (None, 160, 160))
    ck("matrix unchanged source", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("matrix current runner hash", closure["source_hashes_before"]["runner_script"],
       sha(HERE / "run_native_seed_matrix_ssh.ps1"))
    ck("matrix seed input manifest", invocation["seeds"], manifest["seeds"])
    ck("matrix 160 completed guarded steps", [(s["seed"], s["name"], s["status"], s["exit_code"],
                                                s["gui_preserved"]) for s in steps],
       [(seed, name, "completed", 0, True) for seed in SEEDS for name in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    for name, info in closure["raw"].items():
        path = MATRIX / name
        ck(f"matrix raw seal {name}", (sha(path), path.stat().st_size),
           (info["sha256"], info["bytes"]))

    all_starts: list[float] = []
    timelines: list[dict] = []
    for item in manifest["seeds"]:
        seed = item["seed"]
        run = MATRIX / f"seed-{seed:02d}"
        ck(f"seed {seed} generated input", (run / "input.json").read_bytes() == input_bytes(seed), True)
        ck(f"seed {seed} frozen input SHA", sha(run / "input.json"), item["input_sha256"])
        source_doc = parse_native(run / "input.json")
        control, = rows(source_doc, "model", "Control")
        ck(f"seed {seed} control", (control["NREPS"], control["RSEED"]), (1, str(seed)))
        roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
        ck(f"seed {seed} roundtrip", (roundtrip["passed"], roundtrip["input_sha256"]),
           (True, item["input_sha256"]))
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        ck(f"seed {seed} conversion", match.groups() if match else None, ("0", "2", "0"))
        ck(f"seed {seed} warning codes", sorted(re.findall(r"warning #(\d+)", run_log)), ["108", "126"])
        event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        starts: list[float] = []
        for mission_id in (1, 2, 3):
            start = event_times(event, mission_id, "mission starting")
            success = event_times(event, mission_id, "mission success")
            completed = event_times(event, mission_id, "mission completed")
            on = event_times(event, mission_id, "task starting")
            back = event_times(event, mission_id, "task completed")
            ck(f"seed {seed} child {mission_id} single phase events",
               tuple(len(x) for x in (start, on, back, success, completed)), (1, 1, 1, 1, 1))
            if all(len(x) == 1 for x in (start, on, back, success, completed)):
                ck(f"seed {seed} child {mission_id} starts at hour 8", start[0], 8)
                near(f"seed {seed} child {mission_id} on-station begins", on[0]-start[0], .5)
                near(f"seed {seed} child {mission_id} on-station lasts one hour", back[0]-on[0], 1)
                near(f"seed {seed} child {mission_id} completes two hours later", completed[0]-start[0], 2)
                near(f"seed {seed} child {mission_id} success at completion", success[0], completed[0])
                starts.append(start[0])
        ck(f"seed {seed} exactly three starts", event.count("mission starting, duration"), 3)
        ck(f"seed {seed} three simultaneous starts", starts, [8, 8, 8])
        ck(f"seed {seed} no cancellation/failure/repair", bool(re.search(
            r"mission (?:cancelled|aborted|suspended)|critical random failure added|system DIRP task", event)), False)
        report = parse_native(run / "report-raw.json")
        summary, = rows(report, "report", "ResultSummary")
        ck(f"seed {seed} summary", tuple(summary[k] for k in
           ("NREP", "RTILW", "RTIUP", "MTMF", "MSTF", "MSUF", "STMF")),
           (1, 0, 36, 1, 1, 1, 1))
        system = rows(report, "report", "SystemResults")
        stock = rows(report, "report", "StockTotalResults")
        ck(f"seed {seed} bins", (len(system), len(stock)), (72, 72))
        ck(f"seed {seed} system intervals", [(r["STINT"], r["ETINT"]) for r in system],
           [(i*.5, (i+1)*.5) for i in range(72)])
        ck(f"seed {seed} stock intervals", [(r["STINT"], r["ETINT"]) for r in stock],
           [(i*.5, (i+1)*.5) for i in range(72)])
        near(f"seed {seed} aircraft operation hours", sum((r["NSYMO"] or 0)*.5 for r in system), 6)
        near(f"seed {seed} accepted system hours", sum((r["STACC"] or 0)*.5 for r in system), 6)
        ck(f"seed {seed} no system failure/repair", tuple(sum(r[k] or 0 for r in system)
           for k in ("NFAIL", "NREPT", "NPSTA", "NPSUC")), (0, 0, 0, 0))
        ck(f"seed {seed} zero stock demand/backorder", all(all(r[k] == 0 for k in
           ("NDF", "NDD", "NDR", "NDP", "NBO")) for r in stock), True)
        ck(f"seed {seed} terminal three ready", (system[-1]["NSYRY"], system[-1]["NSYMO"]), (3, 0))
        all_starts.extend(starts)
        timelines.append({"seed": seed, "start_hours": starts,
                          "model_log_sha256": sha(run / "model.log"),
                          "report_raw_sha256": sha(run / "report-raw.json")})

    ck("seed 1 matches aggregate logged replication", timelines[0]["start_hours"], aggregate_logged_starts)
    ck("96 observed mission starts", len(all_starts), 96)
    ck("all observed mission starts at hour 8", all_starts, [8] * 96)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a08-var04-same-time-author-replay/v1",
              "passed": not failed, "passed_count": len(checks)-len(failed),
              "failed_count": len(failed), "failed": failed,
              "aggregate_run_id": AGGREGATE_ID, "seed_matrix_run_id": MATRIX_ID,
              "observed_starts": {"mission_count": len(all_starts), "start_hour": 8,
                                  "seed_count": len(timelines)},
              "timelines": timelines,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "decision": "bounded_fixed_count_zero_period_if_passed",
              "limits": ["The 32 explicit seeds are a convenience matrix, not a random seed sample.",
                         "The aggregate run logs one replication only; per-seed timelines come from one-replication runs.",
                         "Other zero-period combinations, GUI visuals and cross-engine equivalence remain unverified."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5],
                      "observed_starts": result["observed_starts"]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
