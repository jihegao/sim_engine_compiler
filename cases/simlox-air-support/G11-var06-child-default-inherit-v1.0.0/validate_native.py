"""Read-only author replay of frozen G11.var06 omitted-leaf evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import SHA, native_json, populated

HERE = Path(__file__).resolve().parent
RUNS = {arm: f"g11-var06-{arm}-v100-ssh-20261003-01"
        for arm in ("explicit-inherit", "omitted-leaf")}
CONTRACT_SHA = "72d003e61f68bac9b612539043a9a2f5dcf04bc9892304791b1e3af1b621241c"
DIFF_SHA = "964df59703e4ad45c9a9fdea47c60020476ef29620d8d642c69d241f833236e0"
PARENT_SHA = "473efed447d08808d565d08956b659574596be8e2a8457f451b4816bf50251ae"
PARENT_CLOSURE_SHA = "945ee70ce912810bb1bec897030815184648cdbb84326f0ccab038475660c8b9"


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


def values(t: dict, field: str) -> list:
    names = [c["name"] for c in t["columns"]]
    return [row[names.index(field)] for inst in t["instances"] for row in inst["rows"]]


def intervals(t: dict) -> list[tuple[float, float]]:
    return list(zip(values(t, "STINT"), values(t, "ETINT")))


def times(log: str, pattern: str) -> list[float]:
    return [float(x) for x in re.findall(pattern, log)]


def audit_arm(arm: str, a: Audit) -> dict:
    run = HERE / "runs" / RUNS[arm]
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    a.need(sha(HERE / "contract.json") == CONTRACT_SHA, f"{arm} contract SHA")
    a.need(sha(HERE / "exact-diff.json") == DIFF_SHA, f"{arm} diff SHA")
    a.need(sha(HERE / f"native-input-{arm}.json") == SHA[arm], f"{arm} input SHA")
    a.need(contract["inputs"][arm]["sha256"] == SHA[arm], f"{arm} contract input")
    a.need(sha(HERE.parent / "G11-var04-inherit-item-prelife-v1.0.1/native-input-inherited.json") == PARENT_SHA,
           f"{arm} G11.var04 parent input")
    a.need(sha(HERE.parent / "G11-var04-inherit-item-prelife-v1.0.1/runs/g11-var04-inherited-v101-ssh-20261002-01/closure.json") == PARENT_CLOSURE_SHA,
           f"{arm} G11.var04 parent closure")

    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    a.need(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
    a.need(closure["arm"] == arm and closure["run_id"] == RUNS[arm] and closure["error"] is None,
           f"{arm} closure identity")
    a.need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} session0 SSH")
    a.need(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
           f"{arm} GUI guard")
    a.need(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{arm} mutex")
    a.need(invocation["prelife_log_option_before"] == "NO" and closure["prelife_log_option_after"] == "NO",
           f"{arm} registry restore")
    a.need([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"],
           f"{arm} five native steps")
    for step in steps:
        a.need(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"],
               f"{arm} {step['name']} completed")
    for key, digest in closure["source_hashes_before"].items():
        a.need(closure["source_hashes_after"].get(key) == digest, f"{arm} source unchanged {key}")
    for key, digest in {"input": SHA[arm], "parent": PARENT_SHA, "parent_closure": PARENT_CLOSURE_SHA,
                        "contract": CONTRACT_SHA, "exact_diff": DIFF_SHA}.items():
        a.need(closure["source_hashes_before"].get(key) == digest, f"{arm} pinned source {key}")
    a.need(len(closure["raw"]) == 13, f"{arm} raw file count")
    for name, seal in closure["raw"].items():
        path = run / name
        a.need(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"],
               f"{arm} raw seal {name}")

    a.need(roundtrip["passed"] and roundtrip["differences"] == [], f"{arm} roundtrip verdict")
    before = populated(native_json(run / "input.json"))
    after = populated(native_json(run / "roundtrip-raw.json"))
    a.need(len(before) == 23, f"{arm} authored populated table count")
    for name, body in before.items():
        a.need(after.get(name) == body, f"{arm} roundtrip {name}")
    a.need(roundtrip["populated_tables"] == sorted(before), f"{arm} roundtrip list")

    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    warning_ids = re.findall(r"\(warning #(\d+)\)", log)
    expected_warnings = ["108", "419"] if arm == "explicit-inherit" else ["108"]
    a.need(warning_ids == expected_warnings, f"{arm} classified warning IDs")
    a.need(f"Input conversion completed. Errors: 0, Warnings: {len(expected_warnings)}, Notes: 0" in log,
           f"{arm} conversion totals")
    a.need("(error #" not in log and "(notice #" not in log, f"{arm} no error/notice")

    prelife = (run / "model_Prelife.log").read_text(encoding="utf-8-sig", errors="replace")
    parsed = [(mid, float(age)) for mid, age in re.findall(
        r"\*\*(TEACH-AIR-01|POS-A|TEACH-LRU-01)\*\*(?:[^*]*\*\*)? Age\[CALHOURS\]:([0-9.]+)", prelife)]
    a.need(parsed == [("TEACH-AIR-01", 60.0), ("POS-A", 60.0), ("TEACH-LRU-01", 60.0)],
           f"{arm} three-level Prelife Log")
    a.need(("**TEACH-LRU-01**LRU-20**" in prelife) == (arm == "explicit-inherit"),
           f"{arm} item PLIND presence")
    a.need("Prelifed Stock:" in prelife, f"{arm} stock prelife section")

    event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    due = 40.0
    a.need(times(event, r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> started") == [due],
           f"{arm} original item PM system phase")
    a.need(times(event, r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed") == [due + .5],
           f"{arm} system phase completion")
    a.need(times(event, r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,0> started") == [due + .25],
           f"{arm} physical item0 PM start")
    a.need(times(event, r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,0> completed") == [due + 1.25],
           f"{arm} physical item0 PM end")
    a.need(len(re.findall(r"PMID: LRU-CAL100", event)) == 1 and "PMID: SYS-CAL1000" not in event,
           f"{arm} PM attribution")
    removed = re.findall(r"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is\s*<TEACH-LRU-01,0,(\d+)>", event)
    issued = re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", event)
    returned = re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock", event)
    a.need(removed == ["0"] and issued == ["1"] and returned == ["0"], f"{arm} physical stock route")
    a.need(not re.search(r"mission (started|success:|cancelled)", event, re.I), f"{arm} no missions")
    a.need("backorder" not in event.lower() and "(error #" not in event, f"{arm} no backorder/error")

    report = {t["name"]: t for t in native_json(run / "report-raw.json")["report"]["tables"]}
    a.need(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
           f"{arm} report tables")
    summary = report["ResultSummary"]
    for field, target in {"NREP": 1, "RTIUP": 96, "MSTF": 0, "MSUF": 0}.items():
        a.need(values(summary, field) == [target], f"{arm} summary {field}")
    for name in ("SystemResults", "StockTotalResults"):
        bins = intervals(report[name])
        a.need(len(bins) == 192 and bins[0] == (0, .5) and bins[-1] == (95.5, 96),
               f"{arm} {name} horizon")
        a.need(all(left[1] == right[0] for left, right in zip(bins, bins[1:])),
               f"{arm} {name} contiguous")
    system, stock = report["SystemResults"], report["StockTotalResults"]
    for field, total in {"NPMT": 1, "NPMS": 1, "NFAIL": 0, "NSYPM": 1}.items():
        a.need(sum(v or 0 for v in values(system, field)) == total, f"{arm} system {field}")
    for field, total in {"NBO": 0, "NDP": 1, "NWT": 1}.items():
        a.need(sum(v or 0 for v in values(stock, field)) == total, f"{arm} stock {field}")
    a.need(values(system, "NSYRY")[-1] == 1 and values(system, "NSYPM")[-1] == 0,
           f"{arm} terminal ready")
    a.need(values(stock, "PNB")[-1] == 1 and values(stock, "NBO")[-1] == 0,
           f"{arm} terminal stock")
    return {"arm": arm, "run_id": RUNS[arm], "closure_sha256": sha(run / "closure.json"),
            "prelife_log_sha256": sha(run / "model_Prelife.log"), "event_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "ages": parsed, "first_original_item_pm_hour": due,
            "removed_item_ids": removed, "issued_item_ids": issued, "returned_item_ids": returned}


def main() -> int:
    a = Audit()
    source_explicit = native_json(HERE / "native-input-explicit-inherit.json")
    source_omitted = native_json(HERE / "native-input-omitted-leaf.json")
    explicit_tables = {t["name"]: t for t in source_explicit["model"]["tables"]}
    omitted_tables = {t["name"]: t for t in source_omitted["model"]["tables"]}
    a.need({n for n in explicit_tables if explicit_tables[n] != omitted_tables[n]} ==
           {"ProblemDescription", "Prelife", "PrelifeData", "PrelifeStructure"},
           "arm changed-table set")
    for name, leaf in {
        "Prelife": ["PL-LRU", "Installed monitored item age", "TEACH-LRU-01", None],
        "PrelifeData": ["PL-LRU", "LRU-20", 1, 20.0, None, "CALHOURS", "INHERIT", None],
        "PrelifeStructure": ["PL-LRU", "PL-POS", "POS-INH", None],
    }.items():
        erows = explicit_tables[name]["instances"][0]["rows"]
        orows = omitted_tables[name]["instances"][0]["rows"]
        a.need(erows == orows + [leaf], f"only {name} PL-LRU row removed")
    arms = [audit_arm(arm, a) for arm in RUNS]
    a.need(arms[0]["event_log_sha256"] == arms[1]["event_log_sha256"],
           "paired native event logs byte-identical")
    reports = [{t["name"]: t for t in native_json(HERE / "runs" / RUNS[arm] / "report-raw.json")["report"]["tables"]}
               for arm in RUNS]
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        a.need(reports[0][name] == reports[1][name], f"paired {name} tables identical")
    result = {"schema": "simlox-g11-var06-child-default-inherit-author-replay/v1", "case_id": "G11",
              "variant_id": "G11.var06", "version": "1.0.0", "checks": a.checks,
              "passed_checks": a.checks - len(a.errors), "passed": not a.errors,
              "differences": a.errors, "arms": arms,
              "scope": "one omitted leaf LRU versus explicit INHERIT under position, first monitored CALHOURS PM only",
              "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
