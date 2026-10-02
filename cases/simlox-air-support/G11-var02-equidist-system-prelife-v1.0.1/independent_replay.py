"""Read-only independent replay of G11.var02 equidistant system prelife evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "G11-var01-fixed-system-prelife-v1.0.0"
PARENT_INPUT = PARENT / "native-input-fixed-ages.json"
PARENT_CLOSURE = PARENT / "runs/g11-var01-fixed-ages-v100-ssh-20261002-01/closure.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
ARMS = {"fixed-explicit": "g11-var02-fixed-explicit-v101-ssh-20261002-01",
        "equidist": "g11-var02-equidist-v101-ssh-20261002-01"}
COUNT = 0
FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    global COUNT
    COUNT += 1
    if not condition:
        FAILURES.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict:
    return {table["name"]: table for table in read(path)[root]["tables"]}


def rows(table: dict) -> list[dict]:
    columns = [col["name"] for col in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def near(actual, expected, tolerance=0.0001) -> bool:
    return isinstance(actual, (int, float)) and abs(actual - expected) <= tolerance


def occupied(time: float, periods: list[tuple[float, float]]) -> int:
    return int(any(start <= time < end for start, end in periods))


def report_checks(arm: str, run: Path, pm: list[tuple[int, int]]) -> dict:
    report = tables(run / "report-raw.json", "report")
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{arm}: report table set")
    sy = rows(report["SystemResults"])
    st = rows(report["StockTotalResults"])
    summary = rows(report["ResultSummary"])
    check(len(sy) == len(st) == 208, f"{arm}: 208 report bins")
    check(summary == [{"NREP": 1, "RTILW": 0, "RTIUP": 104, "MTMF": 1, "RSMTMF": 0,
                       "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}],
          f"{arm}: summary factors")
    activity = [(7, 10), (11, 14), (31, 34)]
    flight = [(8, 10), (12, 14), (32, 34)]
    prep = [(7, 8), (11, 12), (31, 32)]
    pm_periods = [(hour, hour + 1) for hour, _ in pm]
    starts = [hour for hour, _ in pm]
    ends = [hour + 1 for hour, _ in pm]
    zero_system = ("NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYAL", "NSYRP", "NSYTP", "NSYWR", "NSYWI",
                   "NSYLA", "NSYUH", "NREPT", "NFAIL", "NDAM", "NROBT", "NRCFG", "STREQ", "STF", "STLOW",
                   "SYDTU", "NSYSW", "NPSTA", "NPSUC")
    zero_stock = ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")
    null_stock = ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS")
    for index, (s, k) in enumerate(zip(sy, st)):
        t = index / 2
        check(s["STINT"] == k["STINT"] == t and s["ETINT"] == k["ETINT"] == t + .5,
              f"{arm}: aligned bin {index}")
        pm_value = sum(start <= t < end for start, end in pm_periods)
        mission_value = occupied(t, activity)
        flight_value = occupied(t, flight)
        expected = {"NSYRY": 3 - mission_value - pm_value, "NSYMA": mission_value,
                    "NSYMO": flight_value, "NSYMR": occupied(t, prep), "NSYUA": pm_value,
                    "NSYA": 3 - pm_value, "FTMO": flight_value / 3, "NSYPM": pm_value,
                    "NPMT": ends.count(t), "NPMS": starts.count(t), "STACC": flight_value,
                    "NSYDT": starts.count(t)}
        for key, value in expected.items():
            check(near(s[key], value), f"{arm}: SystemResults {key} bin {index}")
        check(s["SYDT"] == (1 if t in starts else None), f"{arm}: PM duration marker bin {index}")
        for key in zero_system:
            check(s[key] == 0, f"{arm}: zero SystemResults {key} bin {index}")
        check(k["PNB"] == 1, f"{arm}: stock PNB bin {index}")
        for key in zero_stock:
            check(k[key] == 0, f"{arm}: zero StockTotalResults {key} bin {index}")
        for key in null_stock:
            check(k[key] is None, f"{arm}: null StockTotalResults {key} bin {index}")
    check(near(sum(s["NSYPM"] * .5 for s in sy), 3) and
          near(sum(s["NSYMO"] * .5 for s in sy), 6), f"{arm}: three PM and six flight aircraft-hours")
    check(near(sy[-1]["NSYRY"], 3) and sy[-1]["NSYPM"] == 0 and st[-1]["NBO"] == 0,
          f"{arm}: terminal three ready and no backorder")
    return {"report_sha256": sha(run / "report-raw.json"), "system_bins": len(sy),
            "stock_bins": len(st)}


def main() -> int:
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(PARENT_INPUT) == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"],
          "accepted G11.var01 parent source")
    check(sha(PARENT_CLOSURE) == contract["accepted_parent"]["native_closure_sha256"],
          "accepted G11.var01 parent closure")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff seal")
    check(sha(MANUAL) == contract["source"]["manual_sha256"], "manual seal")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary seal")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "CLI seal")
    parent = tables(PARENT_INPUT, "model")
    sources = {}
    evidence = {}
    for arm, run_id in ARMS.items():
        source = CASE / f"native-input-{arm}.json"
        model = tables(source, "model")
        sources[arm] = model
        run = CASE / "runs" / run_id
        check(sha(source) == contract["inputs"][arm]["sha256"] == diff["arms"][arm]["input_sha256"],
              f"{arm}: input seal")
        actual = {name: {"before": parent[name], "after": model[name]}
                  for name in parent if parent[name] != model[name]}
        actual.update({name: {"before": None, "after": model[name]} for name in set(model) - set(parent)})
        check(actual == diff["arms"][arm]["changed"], f"{arm}: exact parent delta")
        check(set(parent).issubset(model), f"{arm}: parent table topology")
        pm_source = rows(model["MaterielPM"])
        check(pm_source == [{"PMID": "CAL100", "DESCR": "100-hour calendar service", "MID": "TEACH-AIR-01",
                             "PMINT": 100, "OPID": "CALHOURS", "CRITF": None, "ATIM": 0, "DTIM": 0,
                             "MONIT": None, "PMRID": None, "ENFNC": None, "ENREG": None,
                             "MNOCC": None, "NOTE": None}], f"{arm}: one CAL100 PM")
        closure, invocation, steps = (read(run / n) for n in ("closure.json", "invocation.json", "steps.json"))
        check(closure["run_id"] == invocation["run_id"] == run_id and closure["arm"] == arm,
              f"{arm}: run identity")
        check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm}: invocation seal")
        check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"],
              f"{arm}: source before/after stability")
        pins = {"input": source, "parent": PARENT_INPUT, "parent_closure": PARENT_CLOSURE,
                "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
                "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
                "checker": CASE / "check_roundtrip.py", "runner": CASE / "run_native_ssh.ps1",
                "python": PYTHON, "exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY}
        for key, path in pins.items():
            check(sha(path) == closure["source_hashes_before"][key], f"{arm}: source seal {key}")
        check(len(closure["raw"]) == 13 and closure["error"] is None, f"{arm}: thirteen raw seals")
        for name, seal in closure["raw"].items():
            path = run / name
            check(path.exists() and path.stat().st_size == seal["bytes"], f"{arm}: raw size {name}")
            check(sha(path) == seal["sha256"], f"{arm}: raw SHA {name}")
        check(sha(run / "input.json") == sha(source), f"{arm}: raw input matches source")
        check(invocation["execution_mode"] == "session0_ssh_cli" and invocation["session_id"] == 0 and
              "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]], f"{arm}: SSH session zero")
        check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
              invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
              f"{arm}: queue and GUI")
        check(invocation["prelife_log_option_before"] == closure["prelife_log_option_after"] == "NO",
              f"{arm}: prior Prelife Log registry option restored")
        check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"],
              f"{arm}: five native/check steps")
        for step in steps:
            check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] is True,
                  f"{arm}: successful step {step['name']}")
        exported = tables(run / "roundtrip-raw.json", "model")
        populated = [name for name, table in model.items() if any(i["rows"] for i in table["instances"])]
        check(len(populated) == 20, f"{arm}: populated authored table count")
        for name in populated:
            check(name in exported and exported[name]["columns"] == model[name]["columns"] and
                  exported[name]["instances"] == model[name]["instances"], f"{arm}: roundtrip {name}")
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("Input conversion completed. Errors: 0" in run_log and "(error #" not in run_log,
              f"{arm}: zero converter errors")
        check((run / "model.sxo").stat().st_size > 4, f"{arm}: valid SXO")
        prelife_log = (run / "model_Prelife.log").read_text(encoding="utf-8-sig", errors="replace")
        entities = re.findall(r"\*\*TEACH-AIR-01\*\*(AGE\d+|EQ-0-120)\*\* Age\[CALHOURS\]:([0-9.]+)", prelife_log)
        expected_ids = ('AGE40', 'AGE80', 'AGE120') if arm == "fixed-explicit" else ('EQ-0-120',) * 3
        check(entities == list(zip(expected_ids, ('40.00', '80.00', '120.00'))),
              f"{arm}: Prelife Log PLIND and age sequence")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        mission_ids = [(8, 10, 0, 0), (12, 14, 1, 1), (32, 34, 2, 2)]
        for start, end, mid, aircraft in mission_ids:
            ident = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
            check(f"Time: {start} {ident} mission starting, duration: 2 : <TEACH-AIR-01,{aircraft}>" in log,
                  f"{arm}: mission {mid} starts on aircraft {aircraft}")
            check(f"Time: {end} {ident} mission success:" in log and
                  f"Time: {end} {ident} mission completed:" in log, f"{arm}: mission {mid} success/completion")
        pm = [(20, 1), (60, 0), (80, 2)]
        starts = [(int(h), int(a)) for h, a in re.findall(
            r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,(\d+)> PMID: CAL100", log)]
        check(starts == pm, f"{arm}: CAL100 first-PM per-aircraft starts")
        for hour, aircraft in pm:
            check(re.search(rf"Time: {hour+1}  system PM task \d+ on <TEACH-AIR-01,{aircraft}> completed", log) is not None,
                  f"{arm}: aircraft {aircraft} PM completes at {hour+1}")
        check("mission aborted" not in log and "failure occurs" not in log, f"{arm}: no failed mission")
        report_evidence = report_checks(arm, run, pm)
        evidence[arm] = {"input_sha256": sha(source), "closure_sha256": sha(run / "closure.json"),
                         "prelife_log_sha256": sha(run / "model_Prelife.log"),
                         "model_log_sha256": sha(run / "model.log"), **report_evidence}
    fixed, equidist = sources["fixed-explicit"], sources["equidist"]
    observed = {name: {"before": fixed.get(name), "after": equidist.get(name)}
                for name in set(fixed) | set(equidist) if fixed.get(name) != equidist.get(name)}
    check(observed == diff["arm_contrast"], "isolated zero/fixed arm contrast")
    check({name for name in observed} == {"PrelifeData", "ProblemDescription"},
          "pair isolates PrelifeData and description")
    check([(r["PLIND"], r["QTY"], r["AGE"], r["AGEMIN"], r["OPID"], r["TYPE"])
           for r in rows(fixed["PrelifeData"])] ==
          [("AGE40", 1, 40, 0, "CALHOURS", "FIXED"),
           ("AGE80", 1, 80, 0, "CALHOURS", "FIXED"),
           ("AGE120", 1, 120, 0, "CALHOURS", "FIXED")], "explicit fixed PLIND rows")
    check([(r["PLIND"], r["QTY"], r["AGE"], r["AGEMIN"], r["OPID"], r["TYPE"])
           for r in rows(equidist["PrelifeData"])] ==
          [("EQ-0-120", 3, 120, 0, "CALHOURS", "EQUIDIST")], "single EQUIDIST source row")
    check(rows(fixed["SystemDeployment"])[0]["PLID"] ==
          rows(equidist["SystemDeployment"])[0]["PLID"] == "PL-SYS", "same deployment PLID")
    check(evidence["fixed-explicit"]["model_log_sha256"] == evidence["equidist"]["model_log_sha256"],
          "native event logs byte-identical")
    diagnostic = CASE.parent / "G11-var02-equidist-system-prelife-v1.0.0" / "runs"
    check(sha(diagnostic / "g11-var02-fixed-explicit-v100-ssh-20261002-01/closure.json") ==
          contract["excluded_diagnostic"]["fixed_explicit_closure_sha256"] and
          sha(diagnostic / "g11-var02-equidist-v100-ssh-20261002-01/closure.json") ==
          contract["excluded_diagnostic"]["equidist_closure_sha256"],
          "excluded v1.0.0 diagnostic closure identities")
    result = {"schema": "simlox-independent-readonly-g11-var02/v1", "passed": not FAILURES,
              "verdict": "GO: bounded EQUIDIST system calendar prelife observation" if not FAILURES else "NO-GO: independent replay failed",
              "checks_passed": COUNT - len(FAILURES), "checks_total": COUNT, "failures": FAILURES,
              "evidence": evidence,
              "finding": "The explicit FIXED and one-row EQUIDIST CALHOURS sources both yield Prelife Log ages 40/80/120. Both native logs show CAL100 PM first starts on aircraft ID1 at h20, ID0 at h60, and ID2 at h80; the logs are byte-identical. Three missions succeed at h8/12/32, and 208 half-hour System/Stock bins per arm reconcile with PM work and terminal readiness.",
              "limits": ["The Prelife Log lists PLINDs and ages in sequence but not native aircraft indices; mapping to indices uses source order and item-specific PM event times.",
                         "Earlier v1.0.0 runs are excluded diagnostics: a mission collision deferred the h20 PM until h22. The fresh v1.0.1 schedule moves the second mission to h12 in both arms.",
                         "Three same-type top-level aircraft, one EQUIDIST interval 0–120, one seed and first CAL100 PM only; no RANDOM pattern, item/stock ages, other operation parameter, later cycle, GUI visual, or cross-engine claim.",
                         "Registry restoration is supported by guarded invocation/closure records, not an independent live registry observation."]}
    out = CASE / "independent-verdict.json"
    out.write_bytes((json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": COUNT, "failures": FAILURES,
                      "verdict": result["verdict"], "output": str(out)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
