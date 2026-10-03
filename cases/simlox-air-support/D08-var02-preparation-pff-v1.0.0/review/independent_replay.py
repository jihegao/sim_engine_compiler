"""Independent, read-only replay of the sealed D08.var02 PFF pair."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent
RUNS = HERE / "runs"
OUT = Path(__file__).with_name("independent-verdict.json")
IDS = {
    "zero": "d08-var02-zero-v100-ssh-20261003-01",
    "positive": "d08-var02-positive-v100-ssh-20261003-01",
}
checks: list[dict[str, object]] = []


def check(label: str, condition: object) -> None:
    checks.append({"name": label, "passed": bool(condition)})


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path: Path, native: bool = False):
    text = path.read_text(encoding="utf-8-sig")
    if native:
        text = re.sub(r",(?=\s*[}\]])", "", text)
    return json.loads(text)


def table_map(doc, root="model"):
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table):
    return [row for inst in table["instances"] for row in inst["rows"]]


def field(table, row, name):
    return row[[c["name"] for c in table["columns"]].index(name)]


def report_table(report, name):
    return next(t for t in report["report"]["tables"] if t["name"] == name)


def near(a, b, tol=0.0002):
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=tol)


def clip(start, end, left, right):
    return max(0.0, min(end, right) - max(start, left))


def exact_roundtrip(label, source, exported):
    n = 0
    for name, authored in source.items():
        if not rows(authored):
            continue
        n += 1
        actual = exported.get(name)
        same = actual is not None
        if same:
            length = len(authored["columns"])
            same = ([c["name"] for c in authored["columns"]]
                    == [c["name"] for c in actual["columns"][:length]])
            same &= ([[r for r in inst["rows"]] for inst in authored["instances"]]
                     == [[r[:length] for r in inst["rows"]] for inst in actual["instances"]])
        check(f"{label}: authored table {name} exact", same)
    check(f"{label}: 24 row-containing authored tables", n == 24)


def event(log: str, time: str, fragment: str):
    return any(line.startswith(f"Time: {time} ") and fragment in line
               for line in log.splitlines())


def bins(label, table, count=72):
    data = rows(table)
    check(f"{label}: {count} half-hour bins", len(data) == count)
    for i, row in enumerate(data):
        check(f"{label}: bin {i} interval", near(field(table, row, "STINT"), i / 2, 1e-6)
              and near(field(table, row, "ETINT"), (i + 1) / 2, 1e-6))
    return data


def main():
    contract = obj(HERE / "contract.json")
    diff = obj(HERE / "exact-diff.json")
    parent_pkg = ROOT / "D08-var01-mff-contrast-v1.0.0"
    parent_input = parent_pkg / "native-input-default.json"
    parent_closure = parent_pkg / "runs" / "d08-var01-default-v100-ssh-20261002-01" / "closure.json"
    catalog = ROOT / "D02-var01-traditional-op-hours-v1.0.0"
    check("accepted D08.var01 parent input pin", digest(parent_input) == contract["direct_behavioral_parent"]["input_sha256"])
    check("accepted D08.var01 parent closure pin", digest(parent_closure) == contract["direct_behavioral_parent"]["native_closure_sha256"])
    check("D02 prerequisite input pin", digest(catalog / "native-input.json") == contract["catalog_parent_prerequisite"]["input_sha256"])
    check("D02 prerequisite closure pin", digest(catalog / "runs" / "d02-var01-traditional-op-v100-ssh-20260930-01" / "closure.json") == contract["catalog_parent_prerequisite"]["native_closure_sha256"])
    check("frozen exact-diff pin", digest(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("diff parent pin", diff["parent_sha256"] == digest(parent_input))

    parent = table_map(obj(parent_input))
    models = {arm: table_map(obj(HERE / f"native-input-{arm}.json")) for arm in IDS}
    for arm, model in models.items():
        check(f"{arm}: contract input pin", digest(HERE / f"native-input-{arm}.json") == contract["arms"][arm]["input_sha256"])
        changed = {name for name in set(parent) | set(model) if parent.get(name) != model.get(name)}
        check(f"{arm}: exact parent table delta", changed == {"ProblemDescription", "MissionPreparation", "MissionReliability"})
        prep = model["MissionPreparation"]
        check(f"{arm}: one-hour RISK preparation row", rows(prep) == [["RISK-MISSION", "TEACH-AIR-01", "BASE-01", 1.0, None, None, None]])
        reliability = model["MissionReliability"]
        rr = rows(reliability)
        check(f"{arm}: targeted <SYSTEM> PFF", len(rr) == 1 and [field(reliability, rr[0], k) for k in ("MTID", "SID", "IID", "PFF")] == ["RISK-MISSION", "TEACH-AIR-01", "<SYSTEM>", contract["arms"][arm]["pff"]])
        check(f"{arm}: ordinary FRT and maintenance unchanged", all(model[k] == parent[k] for k in ("System", "MissionType", "SystemRepair", "Resource", "MaterielPM", "Operations", "Control")))
    changed = {name for name in set(models["zero"]) | set(models["positive"])
               if models["zero"].get(name) != models["positive"].get(name)}
    check("pair changes only PFF and description tables", changed == {"MissionReliability", "ProblemDescription"})
    a = rows(models["zero"]["MissionReliability"])[0]
    b = rows(models["positive"]["MissionReliability"])[0]
    check("pair PFF sole business cell", [(x, y) for x, y in zip(a, b) if x != y] == [(0, 10)])

    observed = {}
    for arm, run_id in IDS.items():
        folder = RUNS / run_id
        inv = obj(folder / "invocation.json")
        closure = obj(folder / "closure.json")
        source = models[arm]
        check(f"{arm}: run identity", inv["run_id"] == closure["run_id"] == run_id)
        check(f"{arm}: invocation input pin", inv["input_sha256"] == digest(HERE / f"native-input-{arm}.json"))
        check(f"{arm}: closure invocation pin", closure["invocation_sha256"] == digest(folder / "invocation.json"))
        check(f"{arm}: source before/after stability", closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
        pins = closure["source_hashes_before"]
        paths = {
            "input": HERE / f"native-input-{arm}.json", "parent": parent_input,
            "parent_closure": parent_closure, "catalog_parent": catalog / "native-input.json",
            "catalog_parent_closure": catalog / "runs" / "d02-var01-traditional-op-v100-ssh-20260930-01" / "closure.json",
            "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
            "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
            "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
        }
        for name, path in paths.items():
            check(f"{arm}: source seal {name}", pins[name] == digest(path))
        check(f"{arm}: executable/manual/dictionary pins", pins["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0" and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
        check(f"{arm}: 12 sealed raw files", len(closure["raw"]) == 12)
        for name, meta in sorted(closure["raw"].items()):
            path = folder / name
            check(f"{arm}: raw seal {name}", path.stat().st_size == meta["bytes"] and digest(path) == meta["sha256"])
        check(f"{arm}: SSH0/mutex/GUI", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        steps = obj(folder / "steps.json")
        check(f"{arm}: five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
        check(f"{arm}: copied input byte identity", digest(folder / "input.json") == pins["input"])
        exact_roundtrip(arm, source, table_map(obj(folder / "roundtrip-raw.json", True)))
        runlog = (folder / "run.log").read_text(encoding="utf-8-sig")
        check(f"{arm}: converter errors0/warnings108+126/notes0", bool(re.search(r"Errors:\s*0, Warnings:\s*2, Notes:\s*0", runlog)) and sorted(re.findall(r"warning #(\d+)", runlog)) == ["108", "126"])
        check(f"{arm}: valid SXO and report", (folder / "model.sxo").stat().st_size > 1000 and (folder / "model.log").stat().st_size > 1000 and (folder / "report-raw.json").stat().st_size > 1000)
        log = (folder / "model.log").read_text(encoding="utf-8-sig")
        report = obj(folder / "report-raw.json", True)
        check(f"{arm}: BASIC mission 8-10 success", event(log, "8", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting") and event(log, "10", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission success"))
        check(f"{arm}: RISK allocation first aircraft1", event(log, "19", "RISK-MISSION,TEACH-UNIT,0,0,1> mission allocates system: <TEACH-AIR-01,1>"))
        check(f"{arm}: RISK preparation starts h19 aircraft1", event(log, "19", "<TEACH-AIR-01,1> preparation started, mission: <RISK-MISSION"))
        check(f"{arm}: BASIC mission 32-34 success", event(log, "32", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting") and event(log, "34", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission success"))
        sys = report_table(report, "SystemResults")
        stock = report_table(report, "StockTotalResults")
        resource = report_table(report, "ResourceResults")
        summary = report_table(report, "ResultSummary")
        sr = bins(f"{arm}: SystemResults", sys)
        st = bins(f"{arm}: StockTotalResults", stock)
        rr = bins(f"{arm}: ResourceResults", resource)
        check(f"{arm}: no stock demand/backorders", all((field(stock, row, "NDF") or 0) == 0 and (field(stock, row, "NBO") or 0) == 0 for row in st))
        check(f"{arm}: terminal two ready", near(field(sys, sr[-1], "NSYRY"), 2))
        check(f"{arm}: report one repetition, 36h", field(summary, rows(summary)[0], "NREP") == 1 and field(summary, rows(summary)[0], "RTIUP") == 36)
        observed[arm] = {"run_id": run_id, "closure_sha256": digest(folder / "closure.json"), "report_sha256": digest(folder / "report-raw.json"), "log": log, "system": (sys, sr), "resource": (resource, rr), "summary": summary}

    zero, pos = observed["zero"], observed["positive"]
    zlog, plog = zero["log"], pos["log"]
    check("zero: full aircraft1 preparation h19-20", event(zlog, "20", "<TEACH-AIR-01,1> preparation ended, mission: <RISK-MISSION") and not any("random failure added" in line and 19 <= float(line.split()[1]) < 20 for line in zlog.splitlines() if line.startswith("Time: ")))
    check("zero: RISK launches h20 and aborts h22.6835", event(zlog, "20", "RISK-MISSION,TEACH-UNIT,0,0,1> mission starting") and event(zlog, "22.6835", "RISK-MISSION,TEACH-UNIT,0,0,1> mission aborted"))
    check("zero: one failure on aircraft1 h22.6835", re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,(\d)> critical random failure added", zlog) == [("22.6835", "1")])
    check("positive: first prep fault aircraft1 h19.2684", event(plog, "19.2684", "<TEACH-AIR-01,1> critical random failure added"))
    check("positive: second prep fault aircraft0 h19.3807", event(plog, "19.3807", "<TEACH-AIR-01,0> critical random failure added"))
    check("positive: RISK reallocates to aircraft0 at first fault", event(plog, "19.2684", "RISK-MISSION,TEACH-UNIT,0,0,1> mission allocates system: <TEACH-AIR-01,0>"))
    check("positive: RISK cancels at second fault before launch", event(plog, "19.3807", "RISK-MISSION,TEACH-UNIT,0,0,1> mission cancelled") and "<RISK-MISSION,TEACH-UNIT,0,0,1> mission starting" not in plog)
    for arm, phases, failures, repairs, pm_bins, worker_hours, work_span, fail_bins, repair_bins in (
        ("zero", [(19, 20)], 1, 1, [29, 30], 7, (23, 30), [22.5], [28]),
        ("positive", [(19, 19.2684), (19.2684, 19.3807)], 2, 2, [30, 31], 12, (19.2684, 31.2684), [19], [24, 29]),
    ):
        sys, sr = observed[arm]["system"]
        res, rr = observed[arm]["resource"]
        for i, row in enumerate(sr):
            left, right = i / 2, (i + 1) / 2
            prep = sum(clip(a, b, left, right) for a, b in phases) / 0.5
            check(f"{arm}: preparation occupancy bin {i}", near(field(sys, row, "NSYMP") or 0, prep, 0.0005))
            check(f"{arm}: stock-free mission flight bin {i}", near(field(sys, row, "NSYMO") or 0, (clip(8, 10, left, right) + clip(32, 34, left, right) + (clip(20, 23, left, right) if arm == "zero" else 0)) / 0.5, 0.0005))
            check(f"{arm}: worker booking bin {i}", near(field(res, rr[i], "NRUM") or 0, clip(*work_span, left, right) / 0.5, 0.0005))
        check(f"{arm}: report failure total", near(sum(field(sys, row, "NFAIL") or 0 for row in sr), failures))
        check(f"{arm}: report repair total", near(sum(field(sys, row, "NREPT") or 0 for row in sr), repairs))
        check(f"{arm}: failure bins", [field(sys, row, "STINT") for row in sr if (field(sys, row, "NFAIL") or 0) > 0] == fail_bins)
        check(f"{arm}: repair completion bins", [field(sys, row, "STINT") for row in sr if (field(sys, row, "NREPT") or 0) > 0] == repair_bins)
        check(f"{arm}: report PM completion bins", [field(sys, row, "STINT") for row in sr if (field(sys, row, "NPMT") or 0) > 0] == [float(t) for t in pm_bins])
        check(f"{arm}: report one maintenance worker work integral", near(sum((field(res, row, "NRUM") or 0) * 0.5 for row in rr), worker_hours, 0.01))
        summary = observed[arm]["summary"]
        summary_row = rows(summary)[0]
        expected = {"zero": {"MTMF": 1, "MSTF": 1, "MSUF": 2/3, "STMF": 1},
                    "positive": {"MTMF": 4/7, "MSTF": 2/3, "MSUF": 2/3, "STMF": 4/7}}[arm]
        for key, value in expected.items():
            check(f"{arm}: summary {key}", near(field(summary, summary_row, key), value, 0.00001))
    check("zero: direct repair and PM worker sequence", all(event(zlog, a, b) for a, b in (("23", "system DIRP task 1 on <TEACH-AIR-01,1> started"), ("28", "system DIRP task 1 on <TEACH-AIR-01,1> completed"), ("29", "system PM task 2 on <TEACH-AIR-01,0> completed"), ("30", "system PM task 3 on <TEACH-AIR-01,1> completed"))))
    check("positive: two serial repairs and two PM completions", all(event(plog, a, b) for a, b in (("19.2684", "system DIRP task 2 on <TEACH-AIR-01,1> started"), ("24.2684", "system DIRP task 2 on <TEACH-AIR-01,1> completed"), ("24.2684", "direct repair subtask 3 seqno 1 within system DIRP task 3 on <TEACH-AIR-01,0> starts performing"), ("29.2684", "system DIRP task 3 on <TEACH-AIR-01,0> completed"), ("30.2684", "system PM task 4 on <TEACH-AIR-01,1> completed"), ("31.2684", "system PM task 5 on <TEACH-AIR-01,0> completed"))))
    failures = [c["name"] for c in checks if not c["passed"]]
    result = {
        "schema": "simlox-d08-var02-independent-readonly/v1", "passed": not failures,
        "verdict": "GO_bounded_fixed_seed_PFF_preparation_contrast" if not failures else "NO_GO",
        "checks_passed": len(checks) - len(failures), "checks_total": len(checks),
        "failures": failures, "checks": checks,
        "hashes": {"zero_input": digest(HERE / "native-input-zero.json"), "positive_input": digest(HERE / "native-input-positive.json"), "contract": digest(HERE / "contract.json"), "exact_diff": digest(HERE / "exact-diff.json")},
        "runs": {arm: {k: v for k, v in data.items() if k in ("run_id", "closure_sha256", "report_sha256")} for arm, data in observed.items()},
        "scope": "One seed, two item-free aircraft, one RISK-MISSION preparation: PFF0 has full h19-20 preparation without a preparation fault; PFF10 has aircraft1 fault h19.2684, reassignment, aircraft0 fault h19.3807 and cancellation before launch.",
        "limits": ["Synthetic PFF10 and one seed do not estimate a failure probability or a general hazard law.", "Zero PFF does not prevent the observed later on-mission fault h22.6835.", "No per-item or failure-mode targeting, calendar rate, GUI visual or cross-engine claim."]
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "failures": failures, "output": str(OUT)}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
