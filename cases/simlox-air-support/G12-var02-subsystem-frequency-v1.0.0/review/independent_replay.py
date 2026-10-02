"""Independent read-only replay of the G12.var02 36-run fixed-seed panel."""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "G12-var01-two-subsystems-v1.0.0"
PARENT_INPUT = PARENT / "native-input.json"
PARENT_CLOSURE = PARENT / "runs/g12-var01-two-subsystems-v100-ssh-20261003-02/closure.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
ARMS = ("baseline", "qty-two", "env-two")
SEEDS = tuple(range(2, 14))
COUNT = 0
FAILURES: list[str] = []


def ck(ok: bool, label: str) -> None:
    global COUNT
    COUNT += 1
    if not ok:
        FAILURES.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rd(path: Path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str):
    return {t["name"]: t for t in rd(path)[root]["tables"]}


def rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for i in table["instances"] for row in i["rows"]]


def integer_count(value: float, label: str) -> int:
    count = round(value * 256)
    ck(abs(value * 256 - count) < .0001, label)
    return count


def main() -> int:
    contract, manifest = rd(CASE / "contract.json"), rd(CASE / "input-manifest.json")
    ck(sha(PARENT_INPUT) == contract["accepted_parent"]["input_sha256"] == manifest["parent_input_sha256"],
       "accepted G12.var01 source")
    ck(sha(PARENT_CLOSURE) == contract["accepted_parent"]["native_closure_sha256"],
       "accepted G12.var01 closure")
    ck(sha(CASE / "input-manifest.json") == contract["input_manifest_sha256"], "frozen manifest SHA")
    ck(sha(MANUAL) == contract["source"]["manual_sha256"], "manual SHA")
    ck(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary SHA")
    ck(sha(EXE) == contract["source"]["exe_sha256"], "CLI SHA")
    ck(manifest["seeds"] == list(SEEDS) and manifest["arms"] == list(ARMS),
       "manifest complete predeclared seed/arm grid")
    parent = tables(PARENT_INPUT, "model")
    observed: dict[int, dict[str, dict]] = {}
    models: dict[int, dict[str, dict]] = {}
    missing = [f"g12-var02-seed{seed:02d}-{arm}-20261003-01"
               for seed in SEEDS for arm in ARMS
               if not (CASE / "runs" / f"g12-var02-seed{seed:02d}-{arm}-20261003-01" / "closure.json").exists()]
    ck(not missing, f"all 36 closures present; missing={missing}")
    if missing:
        print(json.dumps({"passed": False, "missing_runs": missing, "checks_total": COUNT}))
        return 2
    for seed in SEEDS:
        observed[seed], models[seed] = {}, {}
        for arm in ARMS:
            label = f"seed{seed:02d}/{arm}"
            run = CASE / "runs" / f"g12-var02-seed{seed:02d}-{arm}-20261003-01"
            source = run / "input.json"
            entry = manifest["entries"][str(seed)][arm]
            ck(sha(source) == entry["sha256"], f"{label}: manifest input SHA")
            model = tables(source, "model")
            models[seed][arm] = model
            delta = {n: model[n] for n in parent if model[n] != parent[n]}
            delta.update({n: model[n] for n in set(model) - set(parent)})
            ck(sorted(delta) == sorted(entry["changed_tables"]), f"{label}: parent changed-table set")
            for name, table in model.items():
                if name not in delta:
                    ck(table == parent[name], f"{label}: unchanged parent {name}")
            for name in entry["source_rows"]:
                raw_rows = [row for i in model[name]["instances"] for row in i["rows"]]
                ck(raw_rows == entry["source_rows"][name], f"{label}: frozen changed rows {name}")
            control = rows(model["Control"])[0]
            ck(control["NREPS"] == 256 and str(control["RSEED"]) == str(seed),
               f"{label}: 256 replications and seed")
            systems = {r["SID"]: r for r in rows(model["System"])}
            ck(systems["TEACH-AIR-01"]["FRT"] is None and systems["TEACH-SUB-A"]["FRT"] == 0 and
               systems["TEACH-SUB-B"]["FRT"] == 50000, f"{label}: common failure-rate geometry")
            repair = rows(model["SystemRepair"])
            ck(len(repair) == 1 and repair[0]["SID"] == "TEACH-SUB-B" and
               repair[0]["SURPT"] == .5, f"{label}: direct half-hour child-B repair")
            closure, invocation, steps = (rd(run / n) for n in ("closure.json", "invocation.json", "steps.json"))
            ck(closure["run_id"] == invocation["run_id"] == run.name and
               closure["arm"] == arm and closure["seed"] == seed, f"{label}: run identity")
            ck(sha(run / "invocation.json") == closure["invocation_sha256"], f"{label}: invocation SHA")
            ck(invocation["source_hashes_before"] == closure["source_hashes_before"] ==
               closure["source_hashes_after"], f"{label}: source before/after stability")
            pins = {"input": source, "manifest": CASE / "input-manifest.json", "parent": PARENT_INPUT,
                    "parent_closure": PARENT_CLOSURE, "contract": CASE / "contract.json",
                    "builder": CASE / "build.py", "manifest_builder": CASE / "make_input_manifest.py",
                    "checker": CASE / "check_roundtrip.py", "runner": CASE / "run_native_ssh.ps1",
                    "python": PYTHON, "exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY}
            for name, path in pins.items():
                ck(sha(path) == closure["source_hashes_before"][name], f"{label}: source pin {name}")
            ck(len(closure["raw"]) == 13 and closure["error"] is None, f"{label}: 13 raw seals")
            for name, seal in closure["raw"].items():
                path = run / name
                ck(path.exists() and path.stat().st_size == seal["bytes"], f"{label}: raw size {name}")
                ck(sha(path) == seal["sha256"], f"{label}: raw SHA {name}")
            ck(invocation["execution_mode"] == "session0_ssh_cli" and invocation["session_id"] == 0 and
               "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]], f"{label}: SSH0")
            ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
               invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
               f"{label}: mutex/GUI")
            ck(invocation["prelife_log_option_before"] == closure["prelife_log_option_after"] == "NO",
               f"{label}: registry option restored")
            ck([s["name"] for s in steps] ==
               ["import", "export", "calc", "jsonreport", "check_import_export"], f"{label}: five steps")
            for step in steps:
                ck(step["status"] == "completed" and step["exit_code"] == 0 and
                   step["gui_preserved"] is True, f"{label}: successful {step['name']}")
            exported = tables(run / "roundtrip-raw.json", "model")
            populated = [n for n, t in model.items() if any(i["rows"] for i in t["instances"])]
            ck(len(populated) == 22, f"{label}: 22 populated authored tables")
            for name in populated:
                ck(name in exported and model[name]["columns"] == exported[name]["columns"] and
                   model[name]["instances"] == exported[name]["instances"], f"{label}: roundtrip {name}")
            log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
            ck("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in log and
               re.findall(r"\(warning #(\d+)\)", log) == ["108", "2053", "2053"] and
               "(error #" not in log, f"{label}: zero errors/notes and reviewed warnings")
            ck((run / "model.sxo").stat().st_size > 4 and
               (run / "model.log").stat().st_size > 0, f"{label}: valid native outputs")
            report = tables(run / "report-raw.json", "report")
            ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
               f"{label}: report table set")
            summary, sy, stock = rows(report["ResultSummary"]), rows(report["SystemResults"]), rows(report["StockTotalResults"])
            ck(len(summary) == 1 and summary[0]["NREP"] == 256 and
               summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 60,
               f"{label}: NREP256 and report horizon")
            ck(len(sy) == len(stock) == 120, f"{label}: 120 report bins")
            for i, (s, k) in enumerate(zip(sy, stock)):
                t = i / 2
                ck(s["STINT"] == k["STINT"] == t and s["ETINT"] == k["ETINT"] == t + .5,
                   f"{label}: aligned bin {i}")
                ck(s["NFAIL"] >= 0 and s["NREPT"] >= 0 and k["PNB"] == 1 and
                   k["NBO"] == 0, f"{label}: nonnegative event rates/no stock BO bin {i}")
            failures = integer_count(sum(s["NFAIL"] for s in sy), f"{label}: 256*NFAIL integral integer")
            repairs = integer_count(sum(s["NREPT"] for s in sy), f"{label}: 256*NREPT integral integer")
            ck(failures == repairs, f"{label}: failure count equals direct repair count")
            ck(sy[-1]["NSYRY"] == 1 and sy[-1]["NSYPM"] == 0 and
               stock[-1]["NBO"] == 0, f"{label}: terminal ready one and no BO")
            observed[seed][arm] = {"nfail_count": failures, "nrept_count": repairs,
                                   "closure_sha256": sha(run / "closure.json"),
                                   "report_sha256": sha(run / "report-raw.json"),
                                   "input_sha256": sha(source), "raw_seals": len(closure["raw"]),
                                   "summary": summary[0]}
        base, qty, env = (models[seed][arm] for arm in ARMS)
        for arm, model, field, expected in (("qty-two", qty, "QTYPM", 2),
                                             ("env-two", env, "ENVF", 2.0)):
            contrast = {n for n in base if base[n] != model[n]}
            ck(contrast == {"ProblemDescription", "SystemStructure"},
               f"seed{seed:02d}/{arm}: isolated pair table contrast")
            br, vr = rows(base["SystemStructure"]), rows(model["SystemStructure"])
            ck(len(br) == len(vr) == 2 and br[0] == vr[0] and
               br[1]["SID"] == vr[1]["SID"] == "TEACH-SUB-B" and
               br[1][field] == 1 and vr[1][field] == expected and
               all(br[1][n] == vr[1][n] for n in br[1] if n != field),
               f"seed{seed:02d}/{arm}: only B {field} changed")
    contrasts = {}
    for arm in ("qty-two", "env-two"):
        diffs = [observed[seed][arm]["nfail_count"] - observed[seed]["baseline"]["nfail_count"]
                 for seed in SEEDS]
        mean = statistics.mean(diffs)
        sd = statistics.stdev(diffs)
        halfwidth = 2.200985160082949 * sd / math.sqrt(len(diffs))
        positive = sum(d > 0 for d in diffs)
        p_one_sided = sum(math.comb(12, k) for k in range(positive, 13)) / 2**12
        ck(mean > 0 and p_one_sided < .025, f"{arm}: predeclared mean/sign-test acceptance")
        contrasts[arm] = {"paired_differences": diffs, "mean": mean,
                          "sample_sd": sd, "student_t_95_interval": [mean - halfwidth, mean + halfwidth],
                          "strict_positive_seeds": positive, "one_sided_exact_sign_p": p_one_sided,
                          "bonferroni_alpha": .025}
    result = {"schema": "simlox-independent-g12-var02/v1", "passed": not FAILURES,
              "decision": "GO: bounded fixed-seed aggregate child-frequency propagation" if not FAILURES else
                          "NO-GO: independent replay mismatch",
              "checks_passed": COUNT - len(FAILURES), "checks_total": COUNT, "failures": FAILURES,
              "run_count": 36, "raw_seal_count": sum(observed[s][a]["raw_seals"] for s in SEEDS for a in ARMS),
              "observed": observed, "paired_contrasts": contrasts,
              "finding": "For the 12 matched seeds and 256 replications per arm, aggregate SystemResults NFAIL counts increase under child-B QTYPM2 and ENVF2 versus baseline. Both predeclared paired sign tests and positive mean gates are evaluated independently from raw report bins.",
              "limits": ["NFAIL and NREPT are aggregate per-replication report means; multiplying their 120-bin sums by 256 gives per-run integer totals. The event log exposes only the first replication and is not used as the aggregate count source.",
                         "This panel does not establish physical multiplicity, an exact twofold rate, or equivalence of QTYPM and ENVF mechanisms.",
                         "The 12 seed panel gives paired descriptive statistics for this model, horizon and installed CLI; it does not prove a population law or cross-engine parity.",
                         "PM and mission outcomes can change as secondary effects; no sibling operation or other repair-policy claim.",
                         "GUI and registry preservation are supported by guarded records, not independent live visual inspection."]}
    out = CASE / "review/independent-validation-2026-10-03.json"
    out.write_bytes((json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": COUNT,
                      "failures": FAILURES[:20], "output": str(out)}))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
