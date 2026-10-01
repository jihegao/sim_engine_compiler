"""Replay sealed G02.var03 native evidence and the predeclared seed analysis."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean, stdev

from check_roundtrip import parse_native

HERE = Path(__file__).resolve().parent
VARIANTS = ("baseline", "qty-two", "env-two")
SEEDS = range(2, 14)
T975_DF11 = 2.200985160082949


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str, root: str) -> dict:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"unexpected {name} table count")
    return matches[0]


def columns_rows(t: dict) -> tuple[list[str], list[list]]:
    if len(t["instances"]) != 1:
        raise ValueError(f"unexpected instance count for {t['name']}")
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def input_delta(a: dict, b: dict, variant: str) -> None:
    baseline = copy.deepcopy(a)
    intervention = copy.deepcopy(b)
    for doc in (baseline, intervention):
        fields, rows = columns_rows(table(doc, "ProblemDescription", "model"))
        rows[0][fields.index("PDESC")] = "controlled provenance field"
    fields, rows = columns_rows(table(intervention, "MaterielStructure", "model"))
    match = [r for r in rows if r[0] == "POS-B" and r[1] == "TEACH-AIR-01"]
    if len(match) != 1:
        raise ValueError("POS-B structure multiplicity differs")
    col = "QTYPM" if variant == "qty-two" else "ENVF"
    expected = 2 if variant == "qty-two" else 2.0
    if match[0][fields.index(col)] != expected:
        raise ValueError(f"{variant} factor absent")
    match[0][fields.index(col)] = 1 if variant == "qty-two" else 1.0
    if baseline != intervention:
        raise ValueError(f"{variant} has other business differences")


def one(seed: int, variant: str) -> dict:
    run_id = f"g02-var03-seed{seed:02d}-{variant}-20261002-01"
    run = HERE / "runs" / run_id
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    assert invocation["seed"] == seed and invocation["variant"] == variant
    assert invocation["run_id"] == run_id and closure["run_id"] == run_id
    assert invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0
    assert "sshd.exe" in invocation["ssh_ancestor_names"]
    assert invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
    assert invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0
    assert closure["error"] is None and sha(run / "invocation.json") == closure["invocation_sha256"]
    assert len(steps) == 5 and all(s["status"] == "completed" and s["exit_code"] == 0
                                   and s["gui_preserved"] for s in steps)
    assert roundtrip["passed"] and len(roundtrip["populated_tables"]) == 18
    assert len(closure["raw"]) == 12
    for name, meta in closure["raw"].items():
        path = run / name
        assert path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], (run_id, name)
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    source_hashes = closure["source_hashes_before"]
    assert source_hashes["input"] == sha(run / "input.json") == invocation["input_sha256"]
    assert source_hashes["contract"] == sha(HERE / "contract.json")
    assert source_hashes["builder"] == sha(HERE / "build.py")
    assert source_hashes["checker"] == sha(HERE / "check_roundtrip.py")
    assert source_hashes["runner_script"] == sha(HERE / "run_native_ssh.ps1")
    assert source_hashes["parent"] == invocation["parent_sha256"]
    model = json.loads((run / "input.json").read_text(encoding="utf-8"))
    cf, cr = columns_rows(table(model, "Control", "model"))
    assert len(cr) == 1 and cr[0][cf.index("NREPS")] == 256
    assert cr[0][cf.index("RSEED")] == str(seed)
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    assert "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in run_log
    assert "Simulation time:" in run_log and "Saving results" in run_log
    report = parse_native(run / "report-raw.json")
    sf, sr = columns_rows(table(report, "SystemResults", "report"))
    assert len(sr) == 72
    assert all(r[sf.index("UNID")] == "Total over all Units" and
               r[sf.index("SID")] == "Total over all Systems" and
               r[sf.index("STINT")] == i * 0.5 and
               r[sf.index("ETINT")] == (i + 1) * 0.5 for i, r in enumerate(sr))
    failures = sum(r[sf.index("NFAIL")] for r in sr)
    repairs = sum(r[sf.index("NREPT")] for r in sr)
    assert failures >= 0 and repairs >= 0
    assert abs(failures * 256 - round(failures * 256)) < 1e-6
    assert abs(repairs * 256 - round(repairs * 256)) < 1e-6
    rf, rr = columns_rows(table(report, "ResultSummary", "report"))
    assert len(rr) == 1 and rr[0][rf.index("NREP")] == 256
    tf, tr = columns_rows(table(report, "StockTotalResults", "report"))
    assert len(tr) == 72 and all(r[tf.index("STINT")] == i * 0.5 and
                                  r[tf.index("ETINT")] == (i + 1) * 0.5 for i, r in enumerate(tr))
    event_log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    fmid_repairs = re.findall(r"system CM task \d+ on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", event_log)
    return {"run_id": run_id, "seed": seed, "variant": variant,
            "input_sha256": sha(run / "input.json"), "closure_sha256": sha(run / "closure.json"),
            "invocation_sha256": sha(run / "invocation.json"), "report_sha256": sha(run / "report-raw.json"),
            "model_log_sha256": sha(run / "model.log"), "failure_count_256": round(failures * 256),
            "repair_count_256": round(repairs * 256), "mtmf": rr[0][rf.index("MTMF")],
            "msuf": rr[0][rf.index("MSUF")], "first_rep_cm_fmids": fmid_repairs,
            "input": model}


def contrast(rows: list[dict], variant: str) -> dict:
    by = {(r["seed"], r["variant"]): r for r in rows}
    differences = [by[(seed, variant)]["failure_count_256"] -
                   by[(seed, "baseline")]["failure_count_256"] for seed in SEEDS]
    n = len(differences)
    m = mean(differences)
    sd = stdev(differences)
    half = T975_DF11 * sd / math.sqrt(n)
    positives = sum(d > 0 for d in differences)
    sign_p = sum(math.comb(n, k) for k in range(positives, n + 1)) / 2 ** n
    return {"arm": variant, "matched_seed_differences_per_256": differences,
            "mean_difference_per_256": m, "sample_sd": sd,
            "student_t_95_interval_per_256": [m - half, m + half],
            "positive_seeds": positives, "exact_one_sided_sign_p": sign_p,
            "predeclared_direction_accepted": m > 0 and sign_p < 0.025}


def main() -> None:
    rows = [one(seed, variant) for seed in SEEDS for variant in VARIANTS]
    by = {(r["seed"], r["variant"]): r for r in rows}
    for seed in SEEDS:
        for variant in VARIANTS[1:]:
            input_delta(by[(seed, "baseline")]["input"], by[(seed, variant)]["input"], variant)
    contrasts = [contrast(rows, variant) for variant in VARIANTS[1:]]
    for row in rows:
        del row["input"]
    result = {"schema": "simlox-g02-var03-seed-panel-author-validation/v1",
              "all_36_native_runs_valid": True, "runs": rows,
              "contrasts": contrasts, "predeclared_direction_accepted": all(
                  c["predeclared_direction_accepted"] for c in contrasts)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
