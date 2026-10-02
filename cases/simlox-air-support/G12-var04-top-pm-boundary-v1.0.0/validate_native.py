"""Replay the installed-CLI top-composite PM counterexample."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated

RUN_ID = "g12-var04-top-pm-v100-ssh-20261003-01"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = HERE.parent / "G12-var01-two-subsystems-v1.0.0" / "runs" / "g12-var01-two-subsystems-v100-ssh-20261003-02"
OUT = HERE / "author-validation.json"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def report_tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["report"]["tables"]}


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    parent, child = read(PARENT), read(HERE / "native-input.json")
    ck("parent source", sha(PARENT), PARENT_SHA)
    ck("parent native closure", sha(PARENT_RUN / "closure.json"),
       contract["accepted_parent"]["native_closure_sha256"])
    ck("child input", sha(HERE / "native-input.json"), contract["input"]["sha256"])
    ck("builder", make(), child)
    ck("diff SHA", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    before, after = tables(parent), tables(child)
    expected_changed = ["MaterielPM", "PMLocation", "ProblemDescription"]
    ck("changed tables", sorted(n for n in after if after[n] != before[n]), expected_changed)
    ck("diff source pins", (diff["parent_sha256"], diff["input_sha256"]),
       (PARENT_SHA, contract["input"]["sha256"]))
    ck("diff exact before/after", diff["changed"],
       {n: {"before": before[n], "after": after[n]} for n in expected_changed})
    ck("PM moved to top", (rows(child, "MaterielPM")[0][2], rows(child, "PMLocation")[0][1]),
       ("TEACH-AIR-01", "TEACH-AIR-01"))
    ck("parent PM was child A", (rows(parent, "MaterielPM")[0][2], rows(parent, "PMLocation")[0][1]),
       ("TEACH-SUB-A", "TEACH-SUB-A"))
    ck("all structure and mission source tables fixed",
       {n: after[n] for n in after if n not in expected_changed},
       {n: before[n] for n in before if n not in expected_changed})

    inv, closure, steps, rt = (read(RUN / n) for n in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
       (RUN_ID, "top-pm", RUN_ID, "top-pm"))
    ck("session-zero SSH", (inv["session_id"], "sshd.exe" in
       [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
       (0, True, "session0_ssh_cli"))
    ck("GUI and queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]),
       ("NO", "NO"))
    ck("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    source = closure["source_hashes_before"]
    ck("source seals", tuple(source[n] for n in
       ("input", "parent", "parent_closure", "contract", "exact_diff", "builder", "diff_builder",
        "checker", "runner", "exe", "manual", "dictionary")),
       (sha(HERE / "native-input.json"), PARENT_SHA, sha(PARENT_RUN / "closure.json"),
        sha(HERE / "contract.json"), sha(HERE / "exact-diff.json"), sha(HERE / "build.py"),
        sha(HERE / "describe_diff.py"), sha(HERE / "check_roundtrip.py"),
        sha(HERE / "run_native_ssh.ps1"), EXE_SHA,
        contract["source"]["manual_sha256"], contract["source"]["dictionary_sha256"]))
    ck("invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    ck("five guarded steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
       for s in steps], [(n, "completed", 0, True) for n in
                       ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("native outcome", (closure["native_outcome"], closure["error"], closure["report_present"]),
       ("zero_error_reviewed_warnings", None, True))
    ck("converter counts/codes", tuple(closure["conversion"][n] for n in
       ("errors", "warnings", "notes", "error_codes", "warning_codes", "calc_exit_code")),
       (0, 3, 0, [], ["108", "2053", "2053"], 0))
    ck("valid SXO", closure["sxo_bytes"] > 1000, True)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
    ck("13 raw files", len(closure["raw"]), 13)
    ck("copied source", sha(RUN / "input.json"), contract["input"]["sha256"])
    source_rows, exported = populated(child), populated(native_json(RUN / "roundtrip-raw.json"))
    ck("21 populated source tables", len(source_rows), 21)
    for n, v in source_rows.items():
        ck(f"roundtrip {n}", exported.get(n), v)
    ck("roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
       (True, [], contract["input"]["sha256"]))

    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    ck("native converter counts", marker.groups() if marker else None, ("0", "3", "0"))
    ck("exact warning IDs", re.findall(r"\(warning #(\d+)\)", run_log), ["108", "2053", "2053"])
    ck("no converter error IDs", re.findall(r"\(error #(\d+)\)", run_log), [])
    log = (RUN / "model.log").read_bytes()
    ck("event log byte-equal leaf-PM parent", log, (PARENT_RUN / "model.log").read_bytes())
    text = log.decode("utf-8-sig", errors="replace")
    for start, end, task in ((24, 25, 0), (49, 50, 1)):
        ck(f"top PM {task} begins", f"Time: {start}  system PM task {task} on <TEACH-AIR-01,0> started" in text, True)
        ck(f"top PM {task} completes", f"Time: {end}  system PM task {task} on <TEACH-AIR-01,0> completed" in text, True)
    ck("three mission successes", re.findall(r"Time: (\d+) <BASIC-MISSION[^\n]*> mission success:", text),
       ["10", "22", "34"])
    current = report_tables(native_json(RUN / "report-raw.json"))
    previous = report_tables(native_json(PARENT_RUN / "report-raw.json"))
    ck("report table set", set(current), set(previous))
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        ck(f"{name} parent equality", current[name], previous[name])
    ck("SystemResults 120 bins", sum(len(i["rows"]) for i in current["SystemResults"]["instances"]), 120)
    ck("StockTotalResults 120 bins", sum(len(i["rows"]) for i in current["StockTotalResults"]["instances"]), 120)
    names = [c["name"] for c in current["SystemResults"]["columns"]]
    last = current["SystemResults"]["instances"][0]["rows"][-1]
    ck("terminal ready and no PM", (last[names.index("NSYRY")], last[names.index("NSYPM")]), (1, 0))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g12-var04-author-native-replay/v1", "case_id": "G12",
              "variant_id": "G12.var04", "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "failed": failed, "run_id": RUN_ID,
              "decision": "bounded_manual_ignored_top_pm_counterexample_if_passed",
              "limits": ["One composite, two zero-rate children, one CAL24 PM moved to mother.",
                         "Event log names composite for both top and accepted leaf configurations; internal targeting unexposed.",
                         "No general top-PM equivalence, corrective repair, GUI visual or cross-engine claim."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
