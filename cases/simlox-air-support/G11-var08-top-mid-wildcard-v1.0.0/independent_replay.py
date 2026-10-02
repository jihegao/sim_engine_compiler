"""Read-only independent replay of G11.var08 top-level Prelife.MID wildcard."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "G11-var07-age-cycle-boundary-v1.0.0"
PARENT_INPUT = PARENT / "native-input-equal-boundary.json"
PARENT_CLOSURE = PARENT / "runs/g11-var07-equal-boundary-v100-ssh-20261003-01/closure.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
ARMS = {"explicit-mid": "g11-var08-explicit-mid-v100-ssh-20261003-01",
        "wildcard-mid": "g11-var08-wildcard-mid-v100-ssh-20261003-01"}
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
        expected = {"NSYRY": 3 - pm_value, "NSYMA": 0,
                    "NSYMO": 0, "NSYMR": 0, "NSYUA": pm_value,
                    "NSYA": 3 - pm_value, "FTMO": 0, "NSYPM": pm_value,
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
    check(near(sum(s["NSYPM"] * .5 for s in sy), 3) and
          near(sum(s["NSYMO"] * .5 for s in sy), 0), f"{arm}: three PM and zero flight aircraft-hours")
    check(near(sy[-1]["NSYRY"], 3) and sy[-1]["NSYPM"] == 0 and st[-1]["NBO"] == 0,
          f"{arm}: terminal three ready and no backorder")
    return {"report_sha256": sha(run / "report-raw.json"), "system_bins": len(sy),
            "stock_bins": len(st)}


def main() -> int:
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(PARENT_INPUT) == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"],
          "accepted G11.var07 parent source")
    check(sha(PARENT_CLOSURE) == contract["accepted_parent"]["native_closure_sha256"],
          "accepted G11.var07 parent closure")
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
              "(error #" not in run_log, f"{arm}: zero converter errors and notes")
        check(re.findall(r"\(warning #(\d+)\)", run_log) == ["108", "126"],
              f"{arm}: only inherited warnings 108/126")
        check((run / "model.sxo").stat().st_size > 4, f"{arm}: valid SXO")
        prelife_log = (run / "model_Prelife.log").read_text(encoding="utf-8-sig", errors="replace")
        entities = re.findall(r"\*\*TEACH-AIR-01\*\*(BELOW|MIDDLE|ABOVE)\*\* Age\[CALHOURS\]:([0-9.]+)", prelife_log)
        check([ident for ident, _ in entities] == ["BELOW", "MIDDLE", "ABOVE"], f"{arm}: Prelife Log PLIND sequence")
        ages = [float(age) for _, age in entities]
        check(len(ages) == 3 and all(0 <= age <= 120 for age in ages), f"{arm}: three in-range ages")
        check(ages == [60, 100, 120], f"{arm}: fixed source ages")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(not re.search(r"mission (?:ordered|created|starting|success|completed|cancelled|aborted)", log),
              f"{arm}: no instantiated mission")
        pm = [(40., 0), (80., 2), (100., 1)]
        starts = [(float(h), int(a)) for h, a in re.findall(
            r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,(\d+)> PMID: CAL100", log)]
        check(starts == pm, f"{arm}: CAL100 first-PM per-aircraft starts")
        completed = [(float(h), int(a)) for h, a in re.findall(
            r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,(\d+)> completed", log)]
        check(completed == [(h + 1, a) for h, a in pm], f"{arm}: exactly three one-hour PM completions")
        for hour, aircraft in pm:
            check(re.search(rf"Time: {hour+1:g}  system PM task \d+ on <TEACH-AIR-01,{aircraft}> completed", log) is not None,
                  f"{arm}: aircraft {aircraft} PM completes at {hour+1:g}")
        for aircraft, age in enumerate(ages):
            start = next(hour for hour, index in pm if index == aircraft)
            remaining = 100 - (age % 100)
            check(abs(start - remaining) <= .0001, f"{arm}: aircraft {aircraft} PM next strictly greater multiple")
        check(all(hour > 0 for hour, _ in starts) and "Time: 0  system PM task" not in log,
              f"{arm}: no h0 PM")
        check("mission aborted" not in log and "failure occurs" not in log, f"{arm}: no failed mission")
        report_evidence = report_checks(arm, run, pm)
        evidence[arm] = {"input_sha256": sha(source), "closure_sha256": sha(run / "closure.json"),
                         "prelife_log_sha256": sha(run / "model_Prelife.log"),
                         "model_log_sha256": sha(run / "model.log"), **report_evidence}
    explicit, wildcard = sources["explicit-mid"], sources["wildcard-mid"]
    observed = {name: {"before": explicit.get(name), "after": wildcard.get(name)}
                for name in set(explicit) | set(wildcard) if explicit.get(name) != wildcard.get(name)}
    check(observed == diff["arm_contrast"], "isolated Prelife.MID arm contrast")
    check({name for name in observed} == {"Prelife", "ProblemDescription"},
          "pair isolates Prelife and description")
    for arm, model in sources.items():
        entries = rows(model["PrelifeData"])
        check([(r["PLID"], r["PLIND"], r["QTY"], r["AGE"], r["AGEMIN"], r["OPID"], r["TYPE"])
               for r in entries] == [("PL-SYS", label, 1, age, 0, "CALHOURS", "FIXED")
                                    for label, age in zip(("BELOW", "MIDDLE", "ABOVE"), (60, 100, 120))],
              f"{arm}: three fixed prelife rows")
    explicit_pre, wildcard_pre = rows(explicit["Prelife"]), rows(wildcard["Prelife"])
    check(len(explicit_pre) == len(wildcard_pre) == 1 and
          explicit_pre[0]["MID"] == "TEACH-AIR-01" and wildcard_pre[0]["MID"] == "*" and
          {k: v for k, v in explicit_pre[0].items() if k != "MID"} ==
          {k: v for k, v in wildcard_pre[0].items() if k != "MID"},
          "only Prelife.MID changes from concrete to literal star")
    for arm, model in sources.items():
        check([r["IQTY"] for r in rows(model["OperationProfile"])] == [0, 0, 0],
              f"{arm}: all three profile quantities zero")
    check(rows(explicit["SystemDeployment"])[0]["PLID"] ==
          rows(wildcard["SystemDeployment"])[0]["PLID"] == "PL-SYS", "same deployment PLID")
    first = CASE / "runs" / ARMS["explicit-mid"]
    second = CASE / "runs" / ARMS["wildcard-mid"]
    check((first / "model_Prelife.log").read_bytes() == (second / "model_Prelife.log").read_bytes(),
          "Prelife logs byte identical")
    check((first / "model.log").read_bytes() == (second / "model.log").read_bytes(),
          "event logs byte identical")
    first_report, second_report = tables(first / "report-raw.json", "report"), tables(second / "report-raw.json", "report")
    check({k: v for k, v in first_report.items() if k != "ProblemDescription"} ==
          {k: v for k, v in second_report.items() if k != "ProblemDescription"},
          "native report tables equal except description")
    result = {"schema": "simlox-independent-readonly-g11-var08/v1", "passed": not FAILURES,
              "verdict": "GO: bounded single-type top-level Prelife.MID wildcard equivalence" if not FAILURES else "NO-GO: independent replay failed",
              "checks_passed": COUNT - len(FAILURES), "checks_total": COUNT, "failures": FAILURES,
              "evidence": evidence,
              "finding": "For the one deployed top-level system type, changing only Prelife.MID from TEACH-AIR-01 to literal * preserves ages 60/100/120, first CAL100 PM IDs 0@40, 2@80, 1@100, byte-identical Prelife/event logs, and all non-description report tables. Every PM runs one hour; no missions run. The 208 half-hour System/Stock bins per arm end with three ready systems.",
              "limits": ["One top-level system MID, one deployment PLID, CALHOURS PMINT100, first PM and 104-hour horizon only; wildcard matching across multiple MIDs is untested.",
                         "The Prelife Log lists PLINDs and ages in sequence but not numeric aircraft indices; index mapping uses source order and first PM event timing.",
                         "No StockAllocation wildcard, sub-prelife validity, missions, installed/stocked item prelife, GUI visual, or cross-engine claim.",
                         "Registry restoration is supported by guarded invocation/closure records, not an independent live registry observation."]}
    out = CASE / "independent-verdict.json"
    out.write_bytes((json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": COUNT, "failures": FAILURES,
                      "verdict": result["verdict"], "output": str(out)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
