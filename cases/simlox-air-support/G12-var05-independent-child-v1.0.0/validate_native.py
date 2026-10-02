"""Replay the bounded independent-child deployment against sealed native output."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated

RUN_ID = "g12-var05-independent-child-v100-ssh-20261003-01"
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
    ck("parent native closure", sha(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"])
    ck("child input", sha(HERE / "native-input.json"), contract["input"]["sha256"])
    ck("builder", make(), child)
    ck("diff SHA", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    before, after = tables(parent), tables(child)
    changed = ["Operations", "ProblemDescription", "SystemDeployment", "Unit"]
    ck("changed tables", sorted(n for n in after if after[n] != before[n]), changed)
    ck("diff source pins", (diff["parent_sha256"], diff["input_sha256"]), (PARENT_SHA, contract["input"]["sha256"]))
    ck("diff exact before/after", diff["changed"], {n: {"before": before[n], "after": after[n]} for n in changed})
    ck("parent one unit", rows(parent, "Unit"), [["TEACH-UNIT", "One-aircraft teaching unit", "BASE-01", None, None, None]])
    ck("two distinct units", [r[0] for r in rows(child, "Unit")], ["TEACH-UNIT", "SUB-B-UNIT"])
    ck("two deployments", [(r[0], r[1], r[2]) for r in rows(child, "SystemDeployment")],
       [("TEACH-AIR-01", "TEACH-UNIT", 1), ("TEACH-SUB-B", "SUB-B-UNIT", 1)])
    ck("two operations", [(r[0], r[1]) for r in rows(child, "Operations")],
       [("TEACH-UNIT", "BASIC-SCHEDULE"), ("SUB-B-UNIT", "BASIC-SCHEDULE")])
    ck("embedded structure unchanged", after["SystemStructure"], before["SystemStructure"])
    ck("all other source tables fixed", {n: after[n] for n in after if n not in changed},
       {n: before[n] for n in before if n not in changed})

    inv, closure, steps, rt = (read(RUN / n) for n in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
       (RUN_ID, "independent-child", RUN_ID, "independent-child"))
    ck("session-zero SSH", (inv["session_id"], "sshd.exe" in
       [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
       (0, True, "session0_ssh_cli"))
    ck("GUI and queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
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
    ck("five guarded steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
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
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for unit, sid, oid in (("TEACH-UNIT", "TEACH-AIR-01", 0), ("SUB-B-UNIT", "TEACH-SUB-B", 1)):
        ck(f"{unit} initial ready identity", f"Time: 0 <{sid},{oid}> nbr ready increased at unit: <{unit} at <BASE-01,0>>" in log, True)
        for ordered, start, success in ((7, 8, 10), (19, 20, 22), (31, 32, 34)):
            ck(f"{unit} mission ordered h{ordered}", f"Time: {ordered} <{unit}> mission ordered: BASIC-MISSION" in log, True)
            ck(f"{unit} allocates {sid} h{ordered}",
               f"Time: {ordered} <BASIC-MISSION,{unit}," in log and
               f"mission allocates system: <{sid},{oid}>" in log, True)
            ck(f"{unit} mission start h{start}", bool(re.search(
               rf"Time: {start} <BASIC-MISSION,{unit},[^\n]*> mission starting, duration: 2 : <{sid},{oid}>", log)), True)
            ck(f"{unit} mission success h{success}", bool(re.search(
               rf"Time: {success} <BASIC-MISSION,{unit},[^\n]*> mission success:", log)), True)
    ck("six successes exactly", re.findall(r"Time: (\d+) <BASIC-MISSION,([^,]+),[^\n]*> mission success:", log),
       [(str(t), u) for t in (10, 22, 34) for u in ("TEACH-UNIT", "SUB-B-UNIT")])
    for start, end, task in ((24, 25, 0), (49, 50, 1)):
        ck(f"top PM {task} begins", f"Time: {start}  system PM task {task} on <TEACH-AIR-01,0> started" in log, True)
        ck(f"top PM {task} completes", f"Time: {end}  system PM task {task} on <TEACH-AIR-01,0> completed" in log, True)
    ck("no independent child PM", bool(re.search(r"system PM task [^\n]*<TEACH-SUB-B,1>", log)), False)

    current = report_tables(native_json(RUN / "report-raw.json"))
    previous = report_tables(native_json(PARENT_RUN / "report-raw.json"))
    ck("report table set", set(current), set(previous))
    ck("one aggregate SystemResults instance", len(current["SystemResults"]["instances"]), 1)
    ck("one aggregate StockTotalResults instance", len(current["StockTotalResults"]["instances"]), 1)
    for name in ("ResultSummary", "StockTotalResults"):
        ck(f"{name} parent equality", current[name], previous[name])
    a, b = current["SystemResults"], previous["SystemResults"]
    ck("SystemResults columns/instances", (a["columns"], len(a["instances"])), (b["columns"], len(b["instances"])))
    cur, old = a["instances"][0]["rows"], b["instances"][0]["rows"]
    ck("120 paired SystemResults bins", (len(cur), len(old)), (120, 120))
    names = [c["name"] for c in a["columns"]]
    for i, (row, prior) in enumerate(zip(cur, old)):
        h = i / 2
        reserved = any(start <= h < start + 1 for start in (7, 19, 31))
        operating = any(start <= h < start + 2 for start in (8, 20, 32))
        delta = {"NSYA": 1, "NSYRY": 0 if reserved or operating else 1,
                 "NSYMA": 1 if reserved or operating else 0, "NSYMR": 1 if reserved else 0,
                 "NSYMO": 1 if operating else 0, "STACC": 1 if operating else 0}
        expected = [v + delta.get(n, 0) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
                    for n, v in zip(names, prior)]
        ck(f"SystemResults bin {i} additive child", row, expected)
    ck("terminal two ready", (cur[-1][names.index("NSYRY")], cur[-1][names.index("NSYA")]), (2, 2))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g12-var05-author-native-replay/v1", "case_id": "G12",
              "variant_id": "G12.var05", "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "failed": failed, "run_id": RUN_ID,
              "decision": "bounded_independent_child_deployment_accepted_if_passed",
              "limits": ["One top aircraft and one independently deployed child-B copy, zero failures, shared mission profile.",
                         "Report SystemResults is aggregated; per-unit identities are evidenced by native event log only.",
                         "No GUI visual, alternate subsystem, station separation or cross-engine claim."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
