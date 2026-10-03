"""Independent standard-library replay of sealed D08.var04 SYACF evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUTPUT = Path(__file__).with_name("independent-verdict.json")
RUN_ID = {a: f"d08-var04-syacf-{a}-v100-ssh-20261003-01" for a in ("yes", "no")}
checks = []


def ck(name, ok):
    checks.append({"name": name, "passed": bool(ok)})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native=False):
    data = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", data) if native else data)


def tables(data, key="model"):
    return {t["name"]: t for t in data[key]["tables"]}


def rows(t):
    return [r for i in t["instances"] for r in i["rows"]]


def val(t, row, col):
    return row[[c["name"] for c in t["columns"]].index(col)]


def close(a, b, tolerance=0.0003):
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=tolerance)


def overlap(a, b, left, right):
    return max(0, min(b, right) - max(a, left))


def has(log, hour, phrase):
    return any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines())


def roundtrip(arm, original, exported):
    count = 0
    for name, source in original.items():
        if not rows(source):
            continue
        count += 1
        target = exported.get(name)
        good = target is not None
        if good:
            width = len(source["columns"])
            good = ([c["name"] for c in source["columns"]] ==
                    [c["name"] for c in target["columns"][:width]])
            good &= ([i["rows"] for i in source["instances"]] ==
                     [[r[:width] for r in i["rows"]] for i in target["instances"]])
        ck(f"{arm}: authored roundtrip {name}", good)
    ck(f"{arm}: 22 row-containing source tables", count == 22)


def bins(arm, t):
    seq = rows(t)
    ck(f"{arm}: {t['name']} 72 bins", len(seq) == 72)
    for i, row in enumerate(seq):
        ck(f"{arm}: {t['name']} interval {i}", close(val(t, row, "STINT"), i / 2, 1e-6)
           and close(val(t, row, "ETINT"), (i + 1) / 2, 1e-6))
    return seq


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    parent_pkg = ROOT / "D08-var01-mff-contrast-v1.0.0"
    parent_input = parent_pkg / "native-input-default.json"
    parent_closure = parent_pkg / "runs" / "d08-var01-default-v100-ssh-20261002-01" / "closure.json"
    d02 = ROOT / "D02-var01-traditional-op-hours-v1.0.0"
    d02_input = d02 / "native-input.json"
    d02_closure = d02 / "runs" / "d02-var01-traditional-op-v100-ssh-20260930-01" / "closure.json"
    ck("accepted D08.var01 parent source", sha(parent_input) == contract["direct_behavioral_parent"]["input_sha256"])
    ck("accepted D08.var01 parent closure", sha(parent_closure) == contract["direct_behavioral_parent"]["native_closure_sha256"])
    ck("D02 prerequisite source", sha(d02_input) == contract["catalog_parent_prerequisite"]["input_sha256"])
    ck("D02 prerequisite closure", sha(d02_closure) == contract["catalog_parent_prerequisite"]["native_closure_sha256"])
    ck("exact diff seal", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    ck("diff parent pin", diff["parent_sha256"] == sha(parent_input))
    parent = tables(read(parent_input))
    source = {arm: tables(read(CASE / f"native-input-{arm}.json")) for arm in RUN_ID}
    for arm, model in source.items():
        ck(f"{arm}: frozen input hash", sha(CASE / f"native-input-{arm}.json") == contract["arms"][arm]["input_sha256"] == diff["source_sha256"][arm])
        changed = {name for name in parent.keys() | model.keys() if parent.get(name) != model.get(name)}
        ck(f"{arm}: exact two-table parent delta", changed == {"ProblemDescription", "MissionType"})
        for name in sorted(parent.keys() - {"ProblemDescription", "MissionType"}):
            ck(f"{arm}: unchanged table {name}", model[name] == parent[name])
        base = rows(parent["MissionType"])
        curr = rows(model["MissionType"])
        col = [c["name"] for c in parent["MissionType"]["columns"]].index("SYACF")
        ck(f"{arm}: only RISK SYACF cell changes", len(base) == len(curr) == 2 and
           [(i, j) for i, (br, cr) in enumerate(zip(base, curr)) for j, (x, y) in enumerate(zip(br, cr)) if x != y] == [(1, col)] and
           base[1][col] is None and curr[1][col] == contract["arms"][arm]["risk_syacf"])
    ck("pairwise only description and SYACF", {k for k in source["yes"].keys() | source["no"].keys()
        if source["yes"].get(k) != source["no"].get(k)} == {"ProblemDescription", "MissionType"})

    actual = {}
    for arm, run_id in RUN_ID.items():
        run = CASE / "runs" / run_id
        inv, closure = read(run / "invocation.json"), read(run / "closure.json")
        ck(f"{arm}: run identity", inv["run_id"] == closure["run_id"] == run_id)
        ck(f"{arm}: invocation/closure binding", closure["invocation_sha256"] == sha(run / "invocation.json"))
        ck(f"{arm}: input binding", inv["input_sha256"] == sha(CASE / f"native-input-{arm}.json") == sha(run / "input.json"))
        ck(f"{arm}: stable source hashes", closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
        pins = closure["source_hashes_before"]
        sealed = {
            "input": CASE / f"native-input-{arm}.json", "parent": parent_input, "parent_closure": parent_closure,
            "catalog_parent": d02_input, "catalog_parent_closure": d02_closure,
            "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
            "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
        }
        for key, path in sealed.items():
            ck(f"{arm}: source seal {key}", pins[key] == sha(path))
        ck(f"{arm}: manual/dictionary/exe pins", pins["manual"] == contract["source"]["manual_pdf_sha256"] and
           pins["dictionary"] == contract["source"]["dictionary_sha256"] and
           pins["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0")
        ck(f"{arm}: SSH0 GUI mutex", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and
           inv["ssh_connection_present"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
           inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        steps = read(run / "steps.json")
        ck(f"{arm}: five guarded successful steps", [s["name"] for s in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
        ck(f"{arm}: twelve raw seals", len(closure["raw"]) == 12)
        for name, meta in sorted(closure["raw"].items()):
            path = run / name
            ck(f"{arm}: raw {name}", path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"])
        roundtrip(arm, source[arm], tables(read(run / "roundtrip-raw.json", True)))
        converter = (run / "run.log").read_text(encoding="utf-8-sig")
        ck(f"{arm}: converter only warnings108/126", bool(re.search(r"Errors:\s*0, Warnings:\s*2, Notes:\s*0", converter)) and
           sorted(re.findall(r"warning #(\d+)", converter)) == ["108", "126"])
        ck(f"{arm}: valid native outputs", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        report = tables(read(run / "report-raw.json", True), "report")
        check_common_events = all(has(log, t, phrase) for t, phrase in (
            ("8", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting"),
            ("10", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission success"),
            ("20", "RISK-MISSION,TEACH-UNIT,0,0,1> mission starting"),
            ("22.6835", "<TEACH-AIR-01,1> critical random failure added"),
            ("23", "system DIRP task 0 on <TEACH-AIR-01,1> started"),
            ("28", "system DIRP task 0 on <TEACH-AIR-01,1> completed"),
            ("29", "system PM task 1 on <TEACH-AIR-01,0> completed"),
            ("30", "system PM task 2 on <TEACH-AIR-01,1> completed"),
            ("32", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting"),
            ("34", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission success")))
        ck(f"{arm}: common fault/mission/repair/PM events", check_common_events)
        ck(f"{arm}: one worker serial repair then PM", all(has(log, t, phrase) for t, phrase in (
            ("23", "<P-MAINT at <BASE-01,0>> allocated to maintenance task: 1"),
            ("28", "<P-MAINT at <BASE-01,0>> deallocated from  maintenance task: 1"),
            ("28", "<P-MAINT at <BASE-01,0>> allocated to maintenance task: 1"),
            ("29", "<P-MAINT at <BASE-01,0>> allocated to maintenance task: 1"),
            ("30", "<P-MAINT at <BASE-01,0>> deallocated from  maintenance task: 1"))))
        sys, stock, res, summary = (report[name] for name in ("SystemResults", "StockTotalResults", "ResourceResults", "ResultSummary"))
        sy, st, rr = bins(arm, sys), bins(arm, stock), bins(arm, res)
        for i, row in enumerate(sy):
            left, right = i / 2, (i + 1) / 2
            expect_flight = (overlap(8, 10, left, right) + overlap(20, 23, left, right) + overlap(32, 34, left, right)) / 0.5
            expect_worker = overlap(23, 30, left, right) / 0.5
            ck(f"{arm}: flight occupancy bin {i}", close(val(sys, row, "NSYMO") or 0, expect_flight, 0.0005))
            ck(f"{arm}: one-worker occupancy bin {i}", close(val(res, rr[i], "NRUM") or 0, expect_worker, 0.0005))
            ck(f"{arm}: zero stock demand/backorder bin {i}", (val(stock, st[i], "NDF") or 0) == 0 and (val(stock, st[i], "NBO") or 0) == 0)
        for key, expected in (("NFAIL", [22.5]), ("NREPT", [28]), ("NPMT", [29, 30]), ("NPMS", [24])):
            ck(f"{arm}: {key} event bins", [val(sys, row, "STINT") for row in sy if (val(sys, row, key) or 0) > 0] == expected)
        ck(f"{arm}: terminal two ready", val(sys, sy[-1], "NSYRY") == 2)
        ck(f"{arm}: summary horizon/mission factors", val(summary, rows(summary)[0], "NREP") == 1 and
           val(summary, rows(summary)[0], "RTIUP") == 36 and
           close(val(summary, rows(summary)[0], "MTMF"), 1) and
           close(val(summary, rows(summary)[0], "MSTF"), 1))
        actual[arm] = {"log": log, "report": report, "summary": summary, "run_id": run_id,
                       "closure_sha256": sha(run / "closure.json"), "report_sha256": sha(run / "report-raw.json")}

    yes, no = actual["yes"], actual["no"]
    ck("Y: immediate critical mission abort", has(yes["log"], "22.6835", "RISK-MISSION,TEACH-UNIT,0,0,1> mission aborted") and
       has(yes["log"], "23", "RISK-MISSION,TEACH-UNIT,0,0,1> aborted mission completed") and
       not has(yes["log"], "23", "RISK-MISSION,TEACH-UNIT,0,0,1> mission success"))
    ck("N: same critical failure, mission succeeds at h23", not "<TEACH-AIR-01,1> aborts its mission" in no["log"] and
       has(no["log"], "23", "RISK-MISSION,TEACH-UNIT,0,0,1> mission success") and
       has(no["log"], "23", "RISK-MISSION,TEACH-UNIT,0,0,1> mission completed"))
    for arm, expected in (("yes", 2/3), ("no", 1)):
        summary = actual[arm]["summary"]
        ck(f"{arm}: summary mission success fraction", close(val(summary, rows(summary)[0], "MSUF"), expected, 0.00001))
    for name in ("SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"):
        ck(f"Y/N: {name} native report equality", yes["report"][name] == no["report"][name])
    failures = [x["name"] for x in checks if not x["passed"]]
    result = {
        "schema": "simlox-d08-var04-syacf-independent-replay/v1", "passed": not failures,
        "verdict": "GO_bounded_fixed_seed_SYACF_Y_N_contrast" if not failures else "NO_GO",
        "checks_passed": len(checks) - len(failures), "checks_total": len(checks), "failures": failures,
        "checks": checks,
        "hashes": {"yes_input": sha(CASE / "native-input-yes.json"), "no_input": sha(CASE / "native-input-no.json"),
                   "contract": sha(CASE / "contract.json"), "exact_diff": sha(CASE / "exact-diff.json")},
        "runs": {arm: {k: value for k, value in data.items() if k in ("run_id", "closure_sha256", "report_sha256")}
                 for arm, data in actual.items()},
        "scope": "The matched fixed-seed critical fault at h22.6835 aborts RISK-MISSION with SYACF Y; with SYACF N the same mission reaches h23 success, followed by the same five-hour direct repair and serial PM work.",
        "limits": ["One fixed seed, one fault timing, two item-free aircraft, one fixed RISK mission.",
                   "The native report differs in mission success summary while System, Stock and Resource tables are equal; aggregate bins do not identify the SYACF internal decision path.",
                   "No inference for noncritical escalation, other fault timing, continuous missions, SYACP, GUI visual behavior or cross-engine parity."],
    }
    OUTPUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                      "checks_total": result["checks_total"], "failures": failures, "output": str(OUTPUT)}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
