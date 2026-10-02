"""Source-bound replay for the guarded two-subsystem native observation."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, make
from check_roundtrip import native_json, populated

RUN_ID = "g12-var01-two-subsystems-v100-ssh-20261003-02"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = HERE.parent / "D03-calendar-pm-v1.0.0" / "runs" / "d03-calendar-v100-ssh-20261001-02"
OUT = HERE / "author-validation.json"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
EXCLUDED_SHA = "1672b3c579481a442a003e01af136305994c9a43d867cfe51139aa91530f95cf"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(doc: dict, name: str) -> list[list]:
    return tables(doc)[name]["instances"][0]["rows"]


def report_tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["report"]["tables"]}


def report_rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    parent, child = read(PARENT), read(HERE / "native-input.json")
    ck("parent input pin", sha(PARENT), PARENT_SHA)
    ck("parent closure pin", sha(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"])
    ck("child input pin", sha(HERE / "native-input.json"), contract["input"]["sha256"])
    ck("builder output", make(), child)
    ck("contract identity", (contract["case_id"], contract["variant_id"]), ("G12", "G12.var01"))
    ck("diff SHA", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    before, after = tables(parent), tables(child)
    changed = sorted(n for n in after if before.get(n) != after[n])
    expected_changed = sorted(("Item", "ItemStructure", "MaterielPM", "PMLocation",
                               "ProblemDescription", "System", "SystemStructure"))
    ck("exact seven changed tables", changed, expected_changed)
    ck("diff source binding", (diff["parent_sha256"], diff["input_sha256"]),
       (PARENT_SHA, contract["input"]["sha256"]))
    ck("diff exact before/after", diff["changed"],
       {n: {"before": before.get(n), "after": after[n]} for n in expected_changed})
    ck("SystemStructure keyed columns", [(c["name"], c.get("key", False)) for c in
       after["SystemStructure"]["columns"]],
       [("SID", True), ("MSID", True), ("QTYPM", False), ("ENVF", False), ("NOTE", False)])
    ck("two linked child systems", rows(child, "SystemStructure"),
       [["TEACH-SUB-A", "TEACH-AIR-01", 1, 1.0, None],
        ["TEACH-SUB-B", "TEACH-AIR-01", 1, 1.0, None]])
    ck("child LRUs", [(r[0], r[1], r[2], r[3]) for r in rows(child, "ItemStructure")],
       [("TEACH-LRU-A", "TEACH-SUB-A", 1, 1.0),
        ("TEACH-LRU-B", "TEACH-SUB-B", 1, 1.0)])
    ck("top system only deployed", rows(child, "SystemDeployment"), rows(parent, "SystemDeployment"))
    ck("PM assigned to leaf A", (rows(child, "MaterielPM")[0][2], rows(child, "PMLocation")[0][1]),
       ("TEACH-SUB-A", "TEACH-SUB-A"))
    ck("no direct failures", [(r[0], r[3]) for r in rows(child, "System")],
       [("TEACH-AIR-01", 0), ("TEACH-SUB-A", 0), ("TEACH-SUB-B", 0)])

    inv, closure, steps, rt = (read(RUN / n) for n in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
       (RUN_ID, "two-subsystems", RUN_ID, "two-subsystems"))
    ck("session-zero SSH", (inv["session_id"], "sshd.exe" in
       [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
       (0, True, "session0_ssh_cli"))
    ck("GUI and queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]),
       ("NO", "NO"))
    ck("stable source hashes", closure["source_hashes_before"], closure["source_hashes_after"])
    source = closure["source_hashes_before"]
    ck("source seal", tuple(source[n] for n in
       ("input", "parent", "parent_closure", "contract", "exact_diff", "builder", "diff_builder",
        "checker", "runner", "exe", "manual", "dictionary")),
       (sha(HERE / "native-input.json"), PARENT_SHA, sha(PARENT_RUN / "closure.json"),
        sha(HERE / "contract.json"), sha(HERE / "exact-diff.json"), sha(HERE / "build.py"),
        sha(HERE / "describe_diff.py"), sha(HERE / "check_roundtrip.py"),
        sha(HERE / "run_native_ssh.ps1"), EXE_SHA,
        contract["source"]["manual_sha256"], contract["source"]["dictionary_sha256"]))
    ck("invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    ck("closure error", closure["error"], None)
    ck("five guarded steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
       for s in steps], [(n, "completed", 0, True) for n in
                       ("import", "export", "calc", "jsonreport", "check_import_export")])
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
    ck("13 raw files", len(closure["raw"]), 13)
    ck("copied source", sha(RUN / "input.json"), contract["input"]["sha256"])
    source_rows, export_rows = populated(child), populated(native_json(RUN / "roundtrip-raw.json"))
    ck("21 populated source tables", len(source_rows), 21)
    for name, value in source_rows.items():
        ck(f"native row roundtrip {name}", export_rows.get(name), value)
    ck("roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
       (True, [], contract["input"]["sha256"]))
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    ck("conversion counts", marker.groups() if marker else None, ("0", "3", "0"))
    ck("warning IDs", re.findall(r"\(warning #(\d+)\)", run_log), ["108", "2053", "2053"])
    ck("zero-rate warning rows", re.findall(r"rec [12]: \(warning #2053\).*", run_log),
       ["rec 1: (warning #2053) FRT is zero for: TEACH-LRU-A",
        "rec 2: (warning #2053) FRT is zero for: TEACH-LRU-B"])
    ck("no converter/runtime errors", re.findall(r"\(error #(\d+)\)", run_log), [])
    ck("valid SXO", (RUN / "model.sxo").stat().st_size > 1000, True)
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("event log equals accepted D03 control", log, parent_log)
    for start, end, task in ((24, 25, 0), (49, 50, 1)):
        ck(f"PM task {task} start", f"Time: {start}  system PM task {task} on <TEACH-AIR-01,0> started" in log, True)
        ck(f"PM task {task} completion", f"Time: {end}  system PM task {task} on <TEACH-AIR-01,0> completed" in log, True)
    ck("mission successes", re.findall(r"Time: (\d+) <BASIC-MISSION[^\n]*> mission success:", log),
       ["10", "22", "34"])
    report, parent_report = (native_json(path) for path in
                             (RUN / "report-raw.json", PARENT_RUN / "report-raw.json"))
    current, previous = report_tables(report), report_tables(parent_report)
    ck("report table set", set(current), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        ck(f"{name} equals D03", current[name], previous[name])
    summary = report_rows(current["ResultSummary"])
    ck("summary success factors", (summary[0]["MSUF"], summary[0]["MSTF"]), (1, 1))
    systems = report_rows(current["SystemResults"])
    stocks = report_rows(current["StockTotalResults"])
    ck("120 aligned half-hour system bins", [(r["STINT"], r["ETINT"]) for r in systems],
       [(i / 2, (i + 1) / 2) for i in range(120)])
    ck("120 aligned half-hour stock bins", [(r["STINT"], r["ETINT"]) for r in stocks],
       [(i / 2, (i + 1) / 2) for i in range(120)])
    for hour in (24.5, 49.5):
        bin_row = next(r for r in systems if r["STINT"] == hour)
        ck(f"mother unavailable during PM {hour}",
           (bin_row["NSYRY"], bin_row["NSYPM"]), (0, 1))
    ck("terminal top system ready", (systems[-1]["NSYRY"], systems[-1]["NSYPM"]), (1, 0))
    ck("no stock backorder bins", [r["NBO"] for r in stocks], [0] * 120)
    ck("excluded diagnostic closure", sha(HERE / "runs" /
       "g12-var01-two-subsystems-v100-ssh-20261003-01" / "closure.json"), EXCLUDED_SHA)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g12-var01-author-native-replay/v1", "case_id": "G12",
              "variant_id": "G12.var01", "passed": not failed, "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failed": failed,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "run_id": RUN_ID, "decision": "bounded_two_subsystem_cli_acceptance_if_passed",
              "limits": ["Two zero-failure subsystems and one leaf-A PM only; no failure propagation or scaling claim.",
                         "Native event log reports the composite TEACH-AIR-01 for the leaf-configured PM.",
                         "GUI visuals and cross-engine parity unverified."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
