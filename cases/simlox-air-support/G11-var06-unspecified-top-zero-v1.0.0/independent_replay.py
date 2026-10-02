"""Read-only independent replay of G11.var06 unspecified top-level zero prelife."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "G11-var05-remaining-qty-system-prelife-v1.0.0"
PARENT_INPUT = PARENT / "native-input-explicit-two.json"
PARENT_CLOSURE = PARENT / "runs/g11-var05-explicit-two-v100-ssh-20261003-01/closure.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
ARMS = {"explicit-zero": "g11-var06-explicit-zero-v100-ssh-20261003-01",
        "implicit-zero": "g11-var06-implicit-zero-v100-ssh-20261003-01"}
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


def report_checks(arm: str, run: Path, pm: list[tuple[float, int]]) -> dict:
    report = tables(run / "report-raw.json", "report")
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{arm}: report table set")
    sy = rows(report["SystemResults"])
    st = rows(report["StockTotalResults"])
    summary = rows(report["ResultSummary"])
    check(len(sy) == len(st) == 208, f"{arm}: 208 report bins")
    check(summary == [{"NREP": 1, "RTILW": 0, "RTIUP": 104, "MTMF": 0, "RSMTMF": 0,
                       "MSTF": 0, "RSMSTF": 0, "MSUF": 0, "RSMSUF": 0, "STMF": 0, "RSSTMF": 0}],
          f"{arm}: summary factors")
    pm_periods = [(hour, hour + 1) for hour, _ in pm]
    starts = [int(hour * 2) / 2 for hour, _ in pm]
    ends = [int((hour + 1) * 2) / 2 for hour, _ in pm]
    zero_system = ("NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYAL", "NSYRP", "NSYTP", "NSYWR", "NSYWI",
                   "NSYLA", "NSYUH", "NREPT", "NFAIL", "NDAM", "NROBT", "NRCFG", "STREQ", "STF", "STLOW",
                   "SYDTU", "NSYSW", "NPSTA", "NPSUC")
    zero_stock = ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")
    null_stock = ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS")
    for index, (s, k) in enumerate(zip(sy, st)):
        t = index / 2
        check(s["STINT"] == k["STINT"] == t and s["ETINT"] == k["ETINT"] == t + .5,
              f"{arm}: aligned bin {index}")
        pm_value = sum(max(0, min(t + .5, end) - max(t, start)) / .5 for start, end in pm_periods)
        expected = {"NSYRY": 4 - pm_value, "NSYMA": 0,
                    "NSYMO": 0, "NSYMR": 0, "NSYUA": pm_value,
                    "NSYA": 4 - pm_value, "FTMO": 0, "NSYPM": pm_value,
                    "NPMT": ends.count(t), "NPMS": starts.count(t), "STACC": 0,
                    "NSYDT": starts.count(t)}
        for key, value in expected.items():
            check(near(s[key], value, .0003), f"{arm}: SystemResults {key} bin {index}")
        check(s["SYDT"] == (1 if t in starts else None), f"{arm}: PM duration marker bin {index}")
        for key in zero_system:
            check(s[key] == 0, f"{arm}: zero SystemResults {key} bin {index}")
        check(k["PNB"] == 1, f"{arm}: stock PNB bin {index}")
        for key in zero_stock:
            check(k[key] == 0, f"{arm}: zero StockTotalResults {key} bin {index}")
        for key in null_stock:
            check(k[key] is None, f"{arm}: null StockTotalResults {key} bin {index}")
    check(near(sum(s["NSYPM"] * .5 for s in sy), 4) and
          near(sum(s["NSYMO"] * .5 for s in sy), 0), f"{arm}: four PM and zero flight aircraft-hours")
    check(near(sy[-1]["NSYRY"], 4) and sy[-1]["NSYPM"] == 0 and st[-1]["NBO"] == 0,
          f"{arm}: terminal four ready and no backorder")
    return {"report_sha256": sha(run / "report-raw.json"), "system_bins": len(sy),
            "stock_bins": len(st)}


def main() -> int:
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(PARENT_INPUT) == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"],
          "accepted G11.var05 parent source")
    check(sha(PARENT_CLOSURE) == contract["accepted_parent"]["native_closure_sha256"],
          "accepted G11.var05 parent closure")
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
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log and
              "warning #108" in run_log and "warning #126" in run_log and
              run_log.count("(warning #") == 2 and "(error #" not in run_log,
              f"{arm}: zero errors and warnings #108/#126 only")
        check((run / "model.sxo").stat().st_size > 4, f"{arm}: valid SXO")
        prelife_log = (run / "model_Prelife.log").read_text(encoding="utf-8-sig", errors="replace")
        entities = re.findall(r"\*\*TEACH-AIR-01\*\*(AGE\d+)\*\* Age\[CALHOURS\]:([0-9.]+)", prelife_log)
        expected_log = ([("AGE60", "60.00"), ("AGE0", "0.00"),
                         ("AGE0", "0.00"), ("AGE0", "0.00")]
                        if arm == "explicit-zero" else [("AGE60", "60.00")])
        check(entities == expected_log, f"{arm}: source-ordered Prelife Log; defaulted entities omitted")
        ages = [60., 0., 0., 0.]
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(not re.search(r"mission (?:ordered|created|starting|success|completed|cancelled|aborted)", log),
              f"{arm}: no instantiated mission")
        pm = [(40., 0), (100., 1), (100., 2), (100., 3)]
        starts = [(float(h), int(a)) for h, a in re.findall(
            r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,(\d+)> PMID: CAL100", log)]
        check(starts == pm, f"{arm}: CAL100 first-PM per-aircraft starts")
        for hour, aircraft in pm:
            check(re.search(rf"Time: {hour+1:g}  system PM task \d+ on <TEACH-AIR-01,{aircraft}> completed", log) is not None,
                  f"{arm}: aircraft {aircraft} PM completes at {hour+1:g}")
        for aircraft, age in enumerate(ages):
            start = next(hour for hour, index in pm if index == aircraft)
            remaining = 100 - (age % 100)
            check(start == remaining, f"{arm}: aircraft {aircraft} PM next-multiple age arithmetic")
        check("mission aborted" not in log and "failure occurs" not in log, f"{arm}: no failed mission")
        check("books resources" not in log and "Take replacement item" not in log and
              "Item demand arrives" not in log, f"{arm}: no resource/stock demand")
        report_evidence = report_checks(arm, run, pm)
        evidence[arm] = {"input_sha256": sha(source), "closure_sha256": sha(run / "closure.json"),
                         "prelife_log_sha256": sha(run / "model_Prelife.log"),
                         "model_log_sha256": sha(run / "model.log"), **report_evidence}
    explicit, implicit = sources["explicit-zero"], sources["implicit-zero"]
    observed = {name: {"before": explicit.get(name), "after": implicit.get(name)}
                for name in set(explicit) | set(implicit) if explicit.get(name) != implicit.get(name)}
    check(observed == diff["arm_contrast"], "isolated explicit/implicit zero arm contrast")
    check({name for name in observed} == {"PrelifeData", "ProblemDescription"},
          "pair isolates PrelifeData and description")
    erows, irows = rows(explicit["PrelifeData"]), rows(implicit["PrelifeData"])
    check(len(erows) == 2 and len(irows) == 1 and irows == erows[:1],
          "implicit source removes only explicit AGE0/QTY3 row")
    check([(r["PLIND"], r["QTY"], r["AGE"], r["OPID"], r["TYPE"])
           for r in erows] ==
          [("AGE60", 1, 60, "CALHOURS", "FIXED"),
           ("AGE0", 3, 0, "CALHOURS", "FIXED")], "explicit zero source rows")
    for arm, model in sources.items():
        check([r["IQTY"] for r in rows(model["OperationProfile"])] == [0, 0, 0],
              f"{arm}: all three profile quantities zero")
        check(rows(model["SystemDeployment"])[0]["QTYPS"] == 4 and
              rows(model["SystemDeployment"])[0]["PLID"] == "PL-SYS", f"{arm}: QTYPS4 deployment")
    check(evidence["explicit-zero"]["model_log_sha256"] == evidence["implicit-zero"]["model_log_sha256"],
          "model logs byte-identical")
    result = {"schema": "simlox-independent-readonly-g11-var06/v1", "passed": not FAILURES,
              "verdict": "GO: bounded unspecified top-level zero-age observation" if not FAILURES else "NO-GO: independent replay failed",
              "checks_passed": COUNT - len(FAILURES), "checks_total": COUNT, "failures": FAILURES,
              "evidence": evidence,
              "finding": "Removing the explicit AGE0/QTY3 PrelifeData row leaves only AGE60/QTY1 and QTYPS4. The implicit Prelife Log prints AGE60 only, while the explicit log prints AGE60/AGE0/AGE0/AGE0. Native model logs are byte-identical: first CAL100 PM ID0@40 and IDs1,2,3@100, each one hour. No missions or resource/stock demand occur; 208 System/Stock bins per arm reconcile and terminal ready4.",
              "limits": ["One seed, four same-type top-level systems, explicit QTY sum one versus four and first CAL100 PM only. No blank-QTY coexistence, row reorder, overallocated QTY, or nonzero unspecified parameter claim.",
                         "The implicit Prelife Log omits the three default-zero aircraft; their zero-age behavior is inferred from isolated source contrast plus PM events and report. Neither Prelife Log prints numeric aircraft IDs.",
                         "No missions, item/stock prelife, other parameter or topology, later PM cycle, GUI visual, or cross-engine claim.",
                         "Registry restoration is supported by guarded invocation/closure records, not an independent live registry observation."]}
    out = CASE / "independent-verdict.json"
    out.write_bytes((json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": COUNT, "failures": FAILURES,
                      "verdict": result["verdict"], "output": str(out)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
