"""Replay sealed A08.var02 aggregate and 32 one-replication seed runs."""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from pathlib import Path

from build import HERE, OUT as INPUT, PARENT, PARENT_SHA, build
from build_seed_matrix import MANIFEST, SEEDS, input_bytes, manifest_bytes
from check_roundtrip import parse_native, populated

AGG_ID = "a08-var02-random-count-eq-v100-ssh-20260930-01"
MATRIX_ID = "a08-var02-seed-matrix-v100-ssh-20260930-01"
AGG = HERE / "runs" / AGG_ID
MATRIX = HERE / "runs" / MATRIX_ID
INPUT_SHA = "54e1fab467ede59829b0c8994aa4d72f1e08878cf7a39532c6fe61364ca87c84"
MANIFEST_SHA = "f864321ee5071bf046768e8772732a9c44d00c8451dd27fa39be7486cb8588a4"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
T_CRITICAL_DF31 = 2.039513446
OUT = HERE / "review" / "author-random-count-validation-2026-09-30.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table, = (t for t in doc[root]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in table["instances"][0]["rows"]]


def events(log: str, marker: str) -> list[tuple[float, int]]:
    pattern = rf"(?m)^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> {re.escape(marker)}"
    return [(float(m.group(1)), int(m.group(2))) for m in re.finditer(pattern, log)]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tol: float = 1e-4) -> None:
        checks.append({"name": name, "passed": math.isclose(actual, expected, abs_tol=tol),
                       "actual": actual, "expected": expected, "abs_tol": tol})

    parent = read_json(PARENT)
    child = read_json(INPUT)
    contract = read_json(HERE / "contract.json")
    matrix_contract = read_json(HERE / "contract-seed-matrix-v1.json")
    diff = read_json(HERE / "exact-diff.json")
    manifest = read_json(MANIFEST)
    ck("accepted parent SHA", sha(PARENT), PARENT_SHA)
    ck("child source SHA", sha(INPUT), INPUT_SHA)
    ck("builder identity", child, build())
    ck("contract parent and child", (contract["parent"]["input_sha256"], contract["native_input_sha256"]),
       (PARENT_SHA, INPUT_SHA))
    ck("diff parent and child", (diff["parent_sha256"], diff["child_sha256"]), (PARENT_SHA, INPUT_SHA))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("changed tables", sorted(k for k in before if before[k] != after[k]),
       ["OperationProfile", "ProblemDescription", "Unit"])
    ck("28 unchanged tables", sum(before[k] == after[k] for k in before), 28)
    ck("13 populated source tables", len(populated(child)), 13)
    profile, = rows(child, "model", "OperationProfile")
    ck("random Poisson equidistant profile", tuple(profile[k] for k in
       ("STIM", "ITYPE", "IQTY", "IQTYD", "IPER", "IDISP")),
       (8, "RANDOM", 3, "<POISSON>", 12, "EQUIDIST"))
    ck("manifest deterministic", MANIFEST.read_bytes() == manifest_bytes(), True)
    ck("manifest SHA", sha(MANIFEST), MANIFEST_SHA)
    ck("matrix contract bindings", tuple(matrix_contract[k] for k in
       ("parent_contract_sha256", "aggregate_input_sha256", "seed_manifest_sha256", "seed_generator_sha256")),
       (sha(HERE / "contract.json"), INPUT_SHA, MANIFEST_SHA, sha(HERE / "build_seed_matrix.py")))
    ck("seed list", [s["seed"] for s in manifest["seeds"]], list(SEEDS))

    aggregate_inv = read_json(AGG / "invocation.json")
    aggregate_closure = read_json(AGG / "closure.json")
    aggregate_steps = read_json(AGG / "steps.json")
    ck("aggregate SSH guard", (aggregate_inv["session_id"], aggregate_inv["ssh_connection_present"],
                                "sshd.exe" in [x.lower() for x in aggregate_inv["ssh_ancestor_names"]],
                                aggregate_inv["queue_mutex"], aggregate_inv["gui"]["pid"],
                                aggregate_inv["gui"]["session_id"]),
       (0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1))
    ck("aggregate source unchanged", aggregate_closure["source_hashes_before"], aggregate_closure["source_hashes_after"])
    ck("aggregate source and executable", (aggregate_closure["source_hashes_before"]["input"],
                                            aggregate_closure["source_hashes_before"]["simlox_exe"],
                                            aggregate_closure["source_hashes_before"]["runner_script"]),
       (INPUT_SHA, EXE_SHA, sha(HERE / "run_native_ssh.ps1")))
    ck("aggregate invocation seal", aggregate_closure["invocation_sha256"], sha(AGG / "invocation.json"))
    ck("aggregate closure error", aggregate_closure["error"], None)
    ck("aggregate steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in aggregate_steps],
       [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
    for name, info in aggregate_closure["raw"].items():
        path = AGG / name
        ck(f"aggregate raw seal {name}", (sha(path), path.stat().st_size),
           (info["sha256"], info["bytes"]))
    ck("aggregate copied input", sha(AGG / "input.json"), INPUT_SHA)
    ar = read_json(AGG / "roundtrip-validation.json")
    ck("aggregate source roundtrip", (ar["passed"], ar["source_sha256"], len(ar["populated_tables"])),
       (True, INPUT_SHA, 13))
    aggregate_log = (AGG / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("aggregate conversion", re.search(r"Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
       aggregate_log).groups(), ("0", "2", "0"))
    ck("aggregate warnings", sorted(re.findall(r"warning #(\d+)", aggregate_log)), ["108", "126"])
    aggregate_report = parse_native(AGG / "report-raw.json")
    summary, = rows(aggregate_report, "report", "ResultSummary")
    system = rows(aggregate_report, "report", "SystemResults")
    stock = rows(aggregate_report, "report", "StockTotalResults")
    ck("aggregate report", (summary["NREP"], len(system), len(stock), system[-1]["NSYRY"]), (32, 72, 72, 3))
    ck("aggregate report intervals", [(r["STINT"], r["ETINT"]) for r in system],
       [(i*.5, (i+1)*.5) for i in range(72)])
    ck("aggregate no failures/stock demand", (sum(r["NFAIL"] or 0 for r in system),
       sum(r["NREPT"] or 0 for r in system),
       all(all(r[k] == 0 for k in ("NDF", "NDD", "NDR", "NDP", "NBO")) for r in stock)),
       (0, 0, True))
    aggregate_mean_operation_hours = sum((r["NSYMO"] or 0)*.5 for r in system)
    ck("aggregate mean operation hours plausible", 0 <= aggregate_mean_operation_hours <= 36*3, True)
    aggregate_event = (AGG / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    aggregate_starts = events(aggregate_event, "mission starting")

    invocation = read_json(MATRIX / "invocation.json")
    closure = read_json(MATRIX / "closure.json")
    steps = read_json(MATRIX / "steps.json")
    ck("matrix SSH guard", (invocation["session_id"], invocation["ssh_connection_present"],
                             "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],
                             invocation["queue_mutex"], invocation["gui"]["pid"], invocation["gui"]["session_id"]),
       (0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1))
    ck("matrix source unchanged", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("matrix source and executable", (closure["source_hashes_before"]["aggregate_input"],
                                         closure["source_hashes_before"]["seed_manifest"],
                                         closure["source_hashes_before"]["runner_script"],
                                         closure["source_hashes_before"]["simlox_exe"]),
       (INPUT_SHA, MANIFEST_SHA, sha(HERE / "run_native_seed_matrix_ssh.ps1"), EXE_SHA))
    ck("matrix invocation seal", closure["invocation_sha256"], sha(MATRIX / "invocation.json"))
    ck("matrix closure", (closure["error"], closure["completed_steps"], closure["expected_steps"]),
       (None, 160, 160))
    ck("matrix manifest in invocation", invocation["seeds"], manifest["seeds"])
    ck("matrix completed steps", [(s["seed"], s["name"], s["status"], s["exit_code"], s["gui_preserved"])
       for s in steps], [(seed, name, "completed", 0, True) for seed in SEEDS for name in
       ("import", "export", "calc", "jsonreport", "check_import_export")])
    for name, info in closure["raw"].items():
        path = MATRIX / name
        ck(f"matrix raw seal {name}", (sha(path), path.stat().st_size),
           (info["sha256"], info["bytes"]))

    counts: list[int] = []
    timelines: list[dict] = []
    for item in manifest["seeds"]:
        seed = item["seed"]
        run = MATRIX / f"seed-{seed:02d}"
        ck(f"seed {seed} generated source", (run / "input.json").read_bytes() == input_bytes(seed), True)
        ck(f"seed {seed} source hash", sha(run / "input.json"), item["input_sha256"])
        control, = rows(parse_native(run / "input.json"), "model", "Control")
        ck(f"seed {seed} control", (control["NREPS"], control["RSEED"]), (1, str(seed)))
        roundtrip = read_json(run / "roundtrip-validation.json")
        ck(f"seed {seed} roundtrip", (roundtrip["passed"], roundtrip["input_sha256"]),
           (True, item["input_sha256"]))
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        conversion = re.search(r"Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        ck(f"seed {seed} conversion", conversion.groups() if conversion else None, ("0", "2", "0"))
        ck(f"seed {seed} warnings", sorted(re.findall(r"warning #(\d+)", run_log)), ["108", "126"])
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        start = events(log, "mission starting")
        success = events(log, "mission success")
        complete = events(log, "mission completed")
        n = len(start)
        ck(f"seed {seed} mission identities", sorted(i for _, i in start), list(range(1, n+1)))
        ck(f"seed {seed} success identities", sorted(i for _, i in success), list(range(1, n+1)))
        ck(f"seed {seed} completion identities", sorted(i for _, i in complete), list(range(1, n+1)))
        starts_by_id = {i: t for t, i in start}
        success_by_id = {i: t for t, i in success}
        complete_by_id = {i: t for t, i in complete}
        for k, i in enumerate(range(1, n+1)):
            near(f"seed {seed} mission {i} equidistant", starts_by_id[i], 8+12*k/n)
            near(f"seed {seed} mission {i} success after two hours", success_by_id[i], starts_by_id[i]+2)
            near(f"seed {seed} mission {i} completes at success", complete_by_id[i], success_by_id[i])
        ck(f"seed {seed} no cancellation/failure/repair", bool(re.search(
           r"mission (?:cancelled|aborted|suspended)|critical random failure added|system DIRP task", log)), False)
        report = parse_native(run / "report-raw.json")
        summary, = rows(report, "report", "ResultSummary")
        system = rows(report, "report", "SystemResults")
        stock = rows(report, "report", "StockTotalResults")
        ck(f"seed {seed} report shape", (summary["NREP"], len(system), len(stock), system[-1]["NSYRY"]),
           (1, 72, 72, 3))
        ck(f"seed {seed} system intervals", [(r["STINT"], r["ETINT"]) for r in system],
           [(i*.5, (i+1)*.5) for i in range(72)])
        ck(f"seed {seed} stock intervals", [(r["STINT"], r["ETINT"]) for r in stock],
           [(i*.5, (i+1)*.5) for i in range(72)])
        near(f"seed {seed} mission operation hours", sum((r["NSYMO"] or 0)*.5 for r in system), 2*n, 1e-3)
        ck(f"seed {seed} no failures/repair", (sum(r["NFAIL"] or 0 for r in system),
           sum(r["NREPT"] or 0 for r in system)), (0, 0))
        ck(f"seed {seed} zero stock demand/backorder", all(all(r[k] == 0 for k in
           ("NDF", "NDD", "NDR", "NDP", "NBO")) for r in stock), True)
        counts.append(n)
        timelines.append({"seed": seed, "mission_count": n,
                          "start_hours_by_mission_id": [starts_by_id[i] for i in range(1, n+1)],
                          "model_log_sha256": sha(run / "model.log"),
                          "report_raw_sha256": sha(run / "report-raw.json")})

    ck("aggregate logged timeline equals explicit seed 1", aggregate_starts,
       [(t, i) for i, t in enumerate(timelines[0]["start_hours_by_mission_id"], 1)])
    ck("at least two realized counts", len(set(counts)) >= 2, True)
    mean = statistics.mean(counts)
    variance = statistics.variance(counts)
    half_width = T_CRITICAL_DF31 * math.sqrt(variance/len(counts))
    ck("count mean nonnegative", mean >= 0, True)
    ck("nominal count half-width at most one", half_width <= 1, True)
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a08-var02-random-count-author-replay/v1",
              "passed": not failed, "passed_count": len(checks)-len(failed),
              "failed_count": len(failed), "failed": failed,
              "aggregate_run_id": AGG_ID, "seed_matrix_run_id": MATRIX_ID,
              "aggregate_mean_operation_hours": aggregate_mean_operation_hours,
              "statistics": {"n": len(counts), "count_sum": sum(counts), "mean_count": mean,
                             "sample_variance_count": variance,
                             "t_critical_df31": T_CRITICAL_DF31,
                             "nominal_95_percent_half_width_count": half_width,
                             "minimum_count": min(counts), "maximum_count": max(counts),
                             "distinct_counts": sorted(set(counts))},
              "timelines": timelines,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "limits": ["The explicit seeds are a convenience matrix, not the aggregate's hidden replications.",
                         "The nominal confidence interval cannot prove Poisson behavior or seed independence.",
                         "Random placement, other distributions, GUI visuals and cross-engine equivalence remain unverified."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5],
                      "statistics": result["statistics"]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
