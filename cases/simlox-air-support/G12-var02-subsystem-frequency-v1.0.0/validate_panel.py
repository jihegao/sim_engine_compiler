"""Replay sealed G12.var02 native runs and the predeclared matched-seed analysis."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path
from statistics import mean, stdev

from build import HERE, PARENT, PARENT_SHA, SEEDS, VARIANTS, build
from check_roundtrip import parse_native, populated

OUT = HERE / "author-validation.json"
T975_DF11 = 2.200985160082949
RUN_SUFFIX = "20261003-01"
PARENT_CLOSURE = (HERE.parent / "G12-var01-two-subsystems-v1.0.0" / "runs" /
                  "g12-var01-two-subsystems-v100-ssh-20261003-02" / "closure.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(doc: dict, root: str, name: str) -> dict:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def fields_rows(doc: dict, root: str, name: str) -> tuple[list[str], list[list]]:
    t = table(doc, root, name)
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def exact_contrast(baseline: dict, arm: dict, variant: str) -> bool:
    a, b = copy.deepcopy(baseline), copy.deepcopy(arm)
    for doc in (a, b):
        fields, rows = fields_rows(doc, "model", "ProblemDescription")
        rows[0][fields.index("PDESC")] = "provenance excluded"
    fields, rows = fields_rows(b, "model", "SystemStructure")
    match = [r for r in rows if r[0] == "TEACH-SUB-B" and r[1] == "TEACH-AIR-01"]
    if len(match) != 1:
        return False
    factor = "QTYPM" if variant == "qty-two" else "ENVF"
    expected = 2 if variant == "qty-two" else 2.0
    if match[0][fields.index(factor)] != expected:
        return False
    match[0][fields.index(factor)] = 1 if variant == "qty-two" else 1.0
    return a == b


def contrast(rows: list[dict], variant: str) -> dict:
    by = {(r["seed"], r["arm"]): r for r in rows}
    differences = [by[seed, variant]["failure_count_256"] - by[seed, "baseline"]["failure_count_256"]
                   for seed in SEEDS]
    n = len(differences)
    avg, sd = mean(differences), stdev(differences)
    half = T975_DF11 * sd / math.sqrt(n)
    positive = sum(x > 0 for x in differences)
    p = sum(math.comb(n, k) for k in range(positive, n + 1)) / 2 ** n
    return {"arm": variant, "matched_seed_differences_per_256": differences,
            "mean_difference_per_256": avg, "sample_sd": sd,
            "student_t_95_interval_per_256": [avg - half, avg + half],
            "positive_seeds": positive, "exact_one_sided_sign_p": p,
            "predeclared_direction_accepted": avg > 0 and p < 0.025}


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, manifest = read(HERE / "contract.json"), read(HERE / "input-manifest.json")
    ck("accepted parent input", sha(PARENT), PARENT_SHA)
    ck("accepted parent closure", sha(PARENT_CLOSURE), contract["accepted_parent"]["native_closure_sha256"])
    ck("frozen input manifest", sha(HERE / "input-manifest.json"), contract["input_manifest_sha256"])
    ck("manifest parent", manifest["parent_input_sha256"], PARENT_SHA)
    ck("manifest seeds/arms", (manifest["seeds"], manifest["arms"]), (list(SEEDS), list(VARIANTS)))
    rows: list[dict] = []
    inputs: dict[tuple[int, str], dict] = {}
    reports: dict[tuple[int, str], dict] = {}
    for seed in SEEDS:
        for arm in VARIANTS:
            run_id = f"g12-var02-seed{seed:02d}-{arm}-{RUN_SUFFIX}"
            run = HERE / "runs" / run_id
            prefix = f"{seed}/{arm}"
            inv, closure, steps, rt = (read(run / n) for n in
                                       ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
            ck(f"{prefix} run identity", (inv["run_id"], closure["run_id"], inv["seed"], closure["seed"],
                                         inv["arm"], closure["arm"]),
               (run_id, run_id, seed, seed, arm, arm))
            ck(f"{prefix} SSH0 and GUI", (inv["execution_mode"], inv["session_id"],
               "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
               inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"]),
               ("session0_ssh_cli", 0, True, "Global\\SimloxIssue18NativeQueue", 13340, 1))
            ck(f"{prefix} GUI start", inv["gui"]["start_utc"], "2026-09-28T10:09:56.8261381Z")
            ck(f"{prefix} registry restored", (inv["prelife_log_option_before"],
               closure["prelife_log_option_after"]), ("NO", "NO"))
            ck(f"{prefix} invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
            ck(f"{prefix} source stable", closure["source_hashes_before"], closure["source_hashes_after"])
            source = closure["source_hashes_before"]
            paths = {"input": run / "input.json", "manifest": HERE / "input-manifest.json",
                     "parent": PARENT, "parent_closure": PARENT_CLOSURE, "contract": HERE / "contract.json",
                     "builder": HERE / "build.py", "manifest_builder": HERE / "make_input_manifest.py",
                     "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
            for key, path in paths.items():
                ck(f"{prefix} source {key}", source[key], sha(path))
            for key in ("exe", "manual", "dictionary"):
                ck(f"{prefix} source {key}", source[key], contract["source"][f"{key}_sha256"])
            ck(f"{prefix} input manifest seal", source["input"], manifest["entries"][str(seed)][arm]["sha256"])
            ck(f"{prefix} native outcome", (closure["native_outcome"], closure["error"],
               closure["report_present"], closure["conversion"]["errors"],
               closure["conversion"]["warnings"], closure["conversion"]["notes"],
               closure["conversion"]["warning_codes"]),
               ("zero_error_reviewed_warnings", None, True, 0, 3, 0, ["108", "2053", "2053"]))
            ck(f"{prefix} valid SXO", closure["sxo_bytes"] > 1000, True)
            ck(f"{prefix} five guarded steps",
               [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
               [(n, "completed", 0, True) for n in
                ("import", "export", "calc", "jsonreport", "check_import_export")])
            ck(f"{prefix} raw count", len(closure["raw"]), 13)
            for name, seal in closure["raw"].items():
                path = run / name
                ck(f"{prefix} raw {name}", (path.stat().st_size, sha(path)),
                   (seal["bytes"], seal["sha256"]))
            source_doc = read(run / "input.json")
            inputs[seed, arm] = source_doc
            ck(f"{prefix} builder", source_doc, build(arm, seed))
            ck(f"{prefix} 22 populated tables", len(populated(source_doc)), 22)
            authored, exported = populated(source_doc), populated(parse_native(run / "roundtrip-raw.json"))
            ck(f"{prefix} exact roundtrip", {n: exported.get(n) for n in authored}, authored)
            ck(f"{prefix} roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
               (True, [], source["input"]))
            run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
            ck(f"{prefix} converter text", bool(re.search(
               r"Input conversion completed\. Errors: 0, Warnings: 3, Notes: 0", run_log)), True)
            ck(f"{prefix} calc saved", ("Simulation time:" in run_log, "Saving results" in run_log),
               (True, True))
            report = parse_native(run / "report-raw.json")
            reports[seed, arm] = report
            rf, rr = fields_rows(report, "report", "ResultSummary")
            ck(f"{prefix} replications", (len(rr), rr[0][rf.index("NREP")]), (1, 256))
            sf, sr = fields_rows(report, "report", "SystemResults")
            ck(f"{prefix} System bins", len(sr), 120)
            ck(f"{prefix} System interval labels",
               [(r[sf.index("STINT")], r[sf.index("ETINT")]) for r in sr],
               [(i / 2, (i + 1) / 2) for i in range(120)])
            ck(f"{prefix} one aggregate system label",
               {(r[sf.index("UNID")], r[sf.index("SID")]) for r in sr},
               {("Total over all Units", "Total over all Systems")})
            failures = sum(r[sf.index("NFAIL")] or 0 for r in sr)
            repairs = sum(r[sf.index("NREPT")] or 0 for r in sr)
            ck(f"{prefix} integral failure count", abs(failures * 256 - round(failures * 256)) < 1e-6, True)
            ck(f"{prefix} integral repair count", abs(repairs * 256 - round(repairs * 256)) < 1e-6, True)
            ck(f"{prefix} failure/repair count", round(failures * 256), round(repairs * 256))
            tf, tr = fields_rows(report, "report", "StockTotalResults")
            ck(f"{prefix} Stock bins", len(tr), 120)
            ck(f"{prefix} Stock interval labels",
               [(r[tf.index("STINT")], r[tf.index("ETINT")]) for r in tr],
               [(i / 2, (i + 1) / 2) for i in range(120)])
            event_log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
            ck(f"{prefix} event log header", event_log.startswith("SIMLOX LOG FILE"), True)
            rows.append({"seed": seed, "arm": arm, "run_id": run_id,
                         "input_sha256": source["input"], "closure_sha256": sha(run / "closure.json"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "event_log_sha256": sha(run / "model.log"),
                         "failure_count_256": round(failures * 256),
                         "repair_count_256": round(repairs * 256),
                         "mtmf": rr[0][rf.index("MTMF")], "msuf": rr[0][rf.index("MSUF")],
                         "first_rep_pm_events": len(re.findall(r"^Time: [^\n]*  system PM task \d+ on .* started$", event_log, re.M)),
                         "first_rep_cm_events": len(re.findall(r"^Time: [^\n]*  system CM task \d+ on .* started$", event_log, re.M))})
    for seed in SEEDS:
        for arm in VARIANTS[1:]:
            ck(f"seed {seed} exact {arm} one-factor contrast",
               exact_contrast(inputs[seed, "baseline"], inputs[seed, arm], arm), True)
        qty = {t["name"]: t for t in reports[seed, "qty-two"]["report"]["tables"]}
        env = {t["name"]: t for t in reports[seed, "env-two"]["report"]["tables"]}
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            ck(f"seed {seed} factor-arm {name} equality", qty[name], env[name])
    contrasts = [contrast(rows, arm) for arm in VARIANTS[1:]]
    for c in contrasts:
        ck(f"{c['arm']} predeclared direction", c["predeclared_direction_accepted"], True)
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g12-var02-panel-author-replay/v1", "case_id": "G12",
              "variant_id": "G12.var02", "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "failed": failed, "runs": rows, "contrasts": contrasts,
              "limits": contract["limits"]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "contrasts": contrasts,
                      "first_failures": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
