"""Replay the frozen G12.var03 source, guarded run, event log and report."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, make
from check_roundtrip import native_json, populated

RUN_ID = "g12-var03-leaf-cm-pm-v100-ssh-20261003-01"
RUN = HERE / "runs" / RUN_ID
OUT = HERE / "author-validation.json"
PARENT_RUN = HERE.parent / "G12-var01-two-subsystems-v1.0.0" / "runs" / "g12-var01-two-subsystems-v100-ssh-20261003-02"
SUPPORT_RUN = HERE.parent / "G12-var02-subsystem-frequency-v1.0.0" / "runs" / "g12-var02-seed02-baseline-20261003-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def model_tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def model_rows(doc: dict, name: str) -> list[list]:
    return model_tables(doc)[name]["instances"][0]["rows"]


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    parent, child = read(PARENT), read(HERE / "native-input.json")
    ck("contract identity", (contract["case_id"], contract["variant_id"]), ("G12", "G12.var03"))
    ck("parent input pin", sha(PARENT), PARENT_SHA)
    ck("parent native closure pin", sha(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"])
    ck("support native closure pin", sha(SUPPORT_RUN / "closure.json"), contract["supporting_frequency_control"]["native_closure_sha256"])
    ck("child input pin", sha(HERE / "native-input.json"), contract["input"]["sha256"])
    ck("builder replay", make(), child)
    ck("diff pin", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    before, after = model_tables(parent), model_tables(child)
    changed = sorted(n for n in after if before[n] != after[n])
    ck("four changed tables", changed, ["Control", "ProblemDescription", "System", "SystemRepair"])
    ck("exact before/after diff", diff["changed"], {n: {"before": before[n], "after": after[n]} for n in changed})
    ck("diff source pins", (diff["parent_sha256"], diff["input_sha256"]), (PARENT_SHA, contract["input"]["sha256"]))
    ck("linked structure unchanged", model_rows(child, "SystemStructure"), model_rows(parent, "SystemStructure"))
    ck("PM tables unchanged", (model_rows(child, "MaterielPM"), model_rows(child, "PMLocation")),
       (model_rows(parent, "MaterielPM"), model_rows(parent, "PMLocation")))
    ck("direct child-B repair row", model_rows(child, "SystemRepair"),
       [["TEACH-SUB-B", "BASE-01", 0.5, 0.5, 1.0, 1.0] + [None] * 9])
    ck("system rates", [(r[0], r[3]) for r in model_rows(child, "System")],
       [("TEACH-AIR-01", None), ("TEACH-SUB-A", 0), ("TEACH-SUB-B", 500000)])

    inv, closure, steps, rt = (read(RUN / n) for n in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
       (RUN_ID, "leaf-cm-pm", RUN_ID, "leaf-cm-pm"))
    ck("SSH session 0", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
       (0, True, "session0_ssh_cli"))
    ck("GUI and queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
    ck("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    source = closure["source_hashes_before"]
    paths = {"input": HERE / "native-input.json", "parent": PARENT,
             "parent_closure": PARENT_RUN / "closure.json", "support_closure": SUPPORT_RUN / "closure.json",
             "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
             "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
             "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
    for key, path in paths.items():
        ck(f"source seal {key}", source[key], sha(path))
    ck("installed source pins", (source["exe"], source["manual"], source["dictionary"]),
       (contract["source"]["exe_sha256"], contract["source"]["manual_sha256"], contract["source"]["dictionary_sha256"]))
    ck("invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    ck("closure error and outcome", (closure["error"], closure["native_outcome"]), (None, "zero_error_reviewed_warnings"))
    ck("five completed guarded steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("raw file count", len(closure["raw"]), 13)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
    ck("roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
       (True, [], contract["input"]["sha256"]))
    authored, exported = populated(child), populated(native_json(RUN / "roundtrip-raw.json"))
    ck("22 authored populated tables", len(authored), 22)
    for name, value in authored.items():
        ck(f"native exact rows {name}", exported.get(name), value)

    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    ck("conversion counts", marker.groups() if marker else None, ("0", "3", "0"))
    ck("reviewed warnings", re.findall(r"\(warning #(\d+)\)", run_log), ["108", "2053", "2053"])
    ck("no native error codes", re.findall(r"\(error #(\d+)\)", run_log), [])
    ck("native SXO present", (RUN / "model.sxo").stat().st_size > 1000, True)
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    failures = re.findall(r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added, now", log, re.M)
    paths_in_log = re.findall(r"^  direct repair failure  connection path: (.+)$", log, re.M)
    ck("three child-B failures", failures, ["8.49322", "8.58686", "20.5929"])
    ck("all printed failure paths end child B", all(p.startswith("TEACH-AIR-01 - TEACH-AIR-01 - TEACH-SUB-B") for p in paths_in_log), True)
    ck("first two missions aborted", re.findall(r"^Time: ([\d.]+) <BASIC-MISSION[^\n]+> mission aborted:", log, re.M),
       ["8.49322", "20.5929"])
    ck("third mission succeeds", re.findall(r"^Time: ([\d.]+) <BASIC-MISSION[^\n]+> mission success:", log, re.M), ["34"])
    cm_starts = re.findall(r"^Time: ([\d.]+)  system DIRP task (\d+) on <TEACH-AIR-01,0> started$", log, re.M)
    cm_ends = re.findall(r"^Time: ([\d.]+)  system DIRP task (\d+) on <TEACH-AIR-01,0> completed$", log, re.M)
    ck("CM starts at base arrival", cm_starts, [("8.98644", "0"), ("8.98644", "1"), ("21.0929", "2")])
    ck("CM completes after 0.5 hour", cm_ends, [("9.48644", "0"), ("9.48644", "1"), ("21.5929", "2")])
    ck("three half-hour direct repair plans", len(re.findall(r"starts performing, planned to last for 0\.5 hours", log)), 3)
    ck("PM starts", re.findall(r"^Time: ([\d.]+)  system PM task (\d+) on <TEACH-AIR-01,0> started$", log, re.M),
       [("24", "3"), ("49", "4")])
    ck("PM ends", re.findall(r"^Time: ([\d.]+)  system PM task (\d+) on <TEACH-AIR-01,0> completed$", log, re.M),
       [("25", "3"), ("50", "4")])
    ck("PM identifier twice", len(re.findall(r"PMID: CAL24", log)), 2)
    ck("terminal ready log", "Time: 50 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>" in log, True)

    report = native_json(RUN / "report-raw.json")
    ck("report tables", {t["name"] for t in report["report"]["tables"]},
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary, system, stock = (report_rows(report, name) for name in
                              ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("one replication and horizon", (summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"]), (1, 0, 60))
    ck("mission success fraction", math.isclose(summary[0]["MSUF"], 1 / 3, abs_tol=1e-6), True)
    ck("120 aligned System bins", [(r["STINT"], r["ETINT"]) for r in system],
       [(i / 2, (i + 1) / 2) for i in range(120)])
    ck("120 aligned Stock bins", [(r["STINT"], r["ETINT"]) for r in stock],
       [(i / 2, (i + 1) / 2) for i in range(120)])
    ck("report event totals", tuple(sum(r[k] or 0 for r in system) for k in
       ("NFAIL", "NREPT", "NPMS", "NPMT")), (3, 3, 2, 2))
    ck("terminal report ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYPM"]), (1, 0, 0))
    for hour in (24.5, 49.5):
        row = next(r for r in system if r["STINT"] == hour)
        ck(f"PM unavailable bin {hour}", (row["NSYRY"], row["NSYPM"]), (0, 1))
    ck("zero stock backorders and movements", tuple(sum(r[k] or 0 for r in stock) for k in
       ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), (0,) * 7)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g12-var03-author-native-replay/v1", "case_id": "G12", "variant_id": "G12.var03",
              "run_id": RUN_ID, "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"child_b_failure_times_hours": [8.49322, 8.58686, 20.5929],
                              "composite_missions": "abort, abort, success", "direct_repair_tasks": 3,
                              "calendar_pm_intervals_hours": [[24, 25], [49, 50]], "terminal_top_ready": 1},
              "limits": ["One seed/replication and one configuration; no general frequency inference.",
                         "Failure connection path identifies child B, but task lines name the deployed composite.",
                         "No direct sibling state identifier is logged; sibling outage is not asserted."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
