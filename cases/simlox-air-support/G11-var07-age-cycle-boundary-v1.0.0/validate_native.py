"""Read-only author replay of frozen G11.var07 PM age boundary evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from check_roundtrip import SHA, native_json, populated

HERE = Path(__file__).resolve().parent
RUNS = {arm: f"g11-var07-{arm}-v100-ssh-20261003-01" for arm in ("above-control", "equal-boundary")}
CONTRACT_SHA = "e8589d0c1ad70357d23425398ec782f7a71b080981e1987531d631945631812b"
DIFF_SHA = "8a08562cdf48656d48d821f7735da7c88fd412c67c8928ff223c8d1febfcb1bb"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.errors: list[str] = []

    def need(self, truth: bool, message: str) -> None:
        self.checks += 1
        if not truth:
            self.errors.append(message)


def column_values(table: dict, name: str) -> list:
    names = [c["name"] for c in table["columns"]]
    return [r[names.index(name)] for i in table["instances"] for r in i["rows"]]


def audit_arm(arm: str, a: Audit) -> dict:
    run = HERE / "runs" / RUNS[arm]
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    a.need(sha(HERE / "contract.json") == CONTRACT_SHA, f"{arm} contract SHA")
    a.need(sha(HERE / "exact-diff.json") == DIFF_SHA, f"{arm} exact diff SHA")
    a.need(sha(HERE / f"native-input-{arm}.json") == SHA[arm], f"{arm} input SHA")
    a.need(contract["inputs"][arm]["sha256"] == SHA[arm], f"{arm} contract pin")
    parent = HERE / "../G11-var01-fixed-system-prelife-v1.0.0"
    a.need(sha(parent / "native-input-fixed-ages.json") == contract["accepted_parent"]["input_sha256"], f"{arm} G11.var01 input")
    a.need(sha(parent / "runs/g11-var01-fixed-ages-v100-ssh-20261002-01/closure.json") == contract["accepted_parent"]["native_closure_sha256"], f"{arm} G11.var01 closure")
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    a.need(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
    a.need(closure["arm"] == arm and closure["run_id"] == RUNS[arm] and closure["error"] is None, f"{arm} closure identity")
    a.need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} session-0 SSH")
    a.need(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0, f"{arm} GUI guard")
    a.need(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{arm} mutex")
    a.need(invocation["prelife_log_option_before"] == "NO" and closure["prelife_log_option_after"] == "NO", f"{arm} option restored")
    a.need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm} steps")
    for s in steps:
        a.need(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"], f"{arm} step {s['name']}")
    for key, value in closure["source_hashes_before"].items():
        a.need(closure["source_hashes_after"].get(key) == value, f"{arm} unchanged source {key}")
    for key, value in {"input": SHA[arm], "contract": CONTRACT_SHA, "exact_diff": DIFF_SHA}.items():
        a.need(closure["source_hashes_before"].get(key) == value, f"{arm} source pin {key}")
    a.need(len(closure["raw"]) == 13, f"{arm} raw count")
    for name, entry in closure["raw"].items():
        path = run / name
        a.need(path.is_file() and path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], f"{arm} raw seal {name}")
    a.need(roundtrip["passed"] and roundtrip["differences"] == [], f"{arm} roundtrip result")
    authored = populated(native_json(run / "input.json"))
    exported = populated(native_json(run / "roundtrip-raw.json"))
    a.need(len(authored) == 20, f"{arm} populated table count")
    for name, body in authored.items():
        a.need(exported.get(name) == body, f"{arm} roundtrip {name}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.need("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log, f"{arm} conversion")
    a.need(re.findall(r"\(warning #(\d+)\)", run_log) == ["108", "126"], f"{arm} known warnings")
    a.need("(error #" not in run_log, f"{arm} no conversion/runtime error")
    prelife = (run / "model_Prelife.log").read_text(encoding="utf-8-sig", errors="replace")
    age_rows = [(p, float(v)) for p, v in re.findall(r"\*\*TEACH-AIR-01\*\*([^*]+)\*\* Age\[CALHOURS\]:([0-9.]+)", prelife)]
    expected_age_rows = ([("BELOW", 60.0), ("MIDDLE", 120.0), ("ABOVE", 120.0)]
                         if arm == "above-control" else
                         [("BELOW", 60.0), ("MIDDLE", 100.0), ("ABOVE", 120.0)])
    a.need(age_rows == expected_age_rows, f"{arm} Prelife Log ages/PLINDs")
    a.need(all(0 <= age <= 120 for _, age in age_rows), f"{arm} ages in range")
    event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    starts = [(int(i), float(t)) for t, i in re.findall(r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,(\d+)> started", event)]
    expected = ([(0, 40.0), (1, 80.0), (2, 80.0)] if arm == "above-control" else
                [(0, 40.0), (2, 80.0), (1, 100.0)])
    a.need(starts == expected, f"{arm} first PM starts per entity")
    a.need(all(t > 0 for _, t in starts), f"{arm} no hour-zero PM")
    by_id = {i: t for i, t in starts}
    a.need(all(abs(by_id[i] - ((math.floor(age / 100.0) + 1) * 100.0 - age)) <= .02
               for i, (_, age) in enumerate(age_rows)), f"{arm} first PM versus logged age")
    completions = [(int(i), float(t)) for t, i in re.findall(r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,(\d+)> completed", event)]
    a.need(completions == [(i, t + 1.0) for i, t in expected], f"{arm} PM completion")
    a.need(len(re.findall(r"PMID: CAL100", event)) == 3, f"{arm} CAL100 attribution")
    a.need(len({i for i, t in starts if t == 80.0}) == (2 if arm == "above-control" else 1),
           f"{arm} distinct hour-80 PM entities")
    a.need(len(re.findall(r"mission success:|mission started|mission cancelled", event, re.I)) == 0, f"{arm} no missions instantiated")
    report = {t["name"]: t for t in native_json(run / "report-raw.json")["report"]["tables"]}
    a.need(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{arm} report tables")
    for name in ("SystemResults", "StockTotalResults"):
        t = report[name]
        bins = list(zip(column_values(t, "STINT"), column_values(t, "ETINT")))
        a.need(len(bins) == 208 and bins[0] == (0, .5) and bins[-1] == (103.5, 104), f"{arm} {name} horizon")
        a.need(all(x[1] == y[0] for x, y in zip(bins, bins[1:])), f"{arm} {name} contiguous")
    systems = report["SystemResults"]
    for field, target in {"NPMT": 3, "NPMS": 3, "NFAIL": 0, "NSYPM": 6}.items():
        a.need(sum(v or 0 for v in column_values(systems, field)) == target, f"{arm} {field} total")
    a.need(column_values(systems, "NSYRY")[-1] == 3, f"{arm} terminal ready three")
    a.need(sum(v or 0 for v in column_values(report["StockTotalResults"], "NBO")) == 0,
           f"{arm} no backorders")
    return {"arm": arm, "run_id": RUNS[arm], "closure_sha256": sha(run / "closure.json"),
            "prelife_log_sha256": sha(run / "model_Prelife.log"), "event_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "prelife_ages": age_rows, "first_pm_starts": starts}


def main() -> int:
    a = Audit()
    control = native_json(HERE / "native-input-above-control.json")
    equal = native_json(HERE / "native-input-equal-boundary.json")
    control_tables = {t["name"]: t for t in control["model"]["tables"]}
    equal_tables = {t["name"]: t for t in equal["model"]["tables"]}
    a.need({name for name in control_tables if control_tables[name] != equal_tables[name]} ==
           {"PrelifeData", "ProblemDescription"}, "arm changed-table set")
    crows = control_tables["PrelifeData"]["instances"][0]["rows"]
    erows = equal_tables["PrelifeData"]["instances"][0]["rows"]
    a.need(len(crows) == len(erows) == 3 and crows[0] == erows[0] and crows[2] == erows[2] and
           crows[1][:3] == erows[1][:3] == ["PL-SYS", "MIDDLE", 1] and
           crows[1][3] == 120.0 and erows[1][3] == 100.0 and crows[1][4:] == erows[1][4:],
           "middle AGE-only business contrast")
    arms = [audit_arm(arm, a) for arm in RUNS]
    a.need(arms[0]["event_log_sha256"] != arms[1]["event_log_sha256"],
           "paired event logs differ at middle PM timing")
    a.need(arms[0]["prelife_log_sha256"] != arms[1]["prelife_log_sha256"],
           "paired Prelife Logs differ at middle age")
    result = {"schema": "simlox-g11-var07-age-cycle-boundary-author-replay/v1", "case_id": "G11",
              "variant_id": "G11.var07", "version": "1.0.0", "checks": a.checks,
              "passed_checks": a.checks - len(a.errors), "passed": not a.errors,
              "differences": a.errors, "arms": arms,
              "scope": "three-system fixed CALHOURS ages below/equal/above PMINT100, first CAL100 PM only",
              "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
