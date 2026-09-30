"""Replay A06.var01 source, guarded native output, and A05 control equality."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, OUT as INPUT, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "a06-var01-no-interruption-v100-ssh-20260930-02"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = HERE.parent / "A05-continuous-baseline-v1.0.1" / "runs" / "a05-continuous-four-hour-v101-ssh-20260930-01"
INPUT_SHA = "6d508cb4af5f997785be802c0527cd6f50918cde78714406ae2106e7b421ca6c"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
OUT = HERE / "review" / "author-no-interruption-validation-2026-09-30.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(doc: dict, name: str) -> list[dict]:
    table, = (t for t in doc["report"]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in table["instances"][0]["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float) -> None:
        checks.append({"name": name, "passed": math.isclose(actual, expected, abs_tol=1e-7),
                       "actual": actual, "expected": expected})

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    child = json.loads(INPUT.read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    ck("accepted parent fingerprint", sha(PARENT), PARENT_SHA)
    ck("child fingerprint", sha(INPUT), INPUT_SHA)
    ck("builder identity", build(), child)
    ck("contract source identity", (contract["parent"]["input_sha256"], contract["native_input_sha256"]),
       (PARENT_SHA, INPUT_SHA))
    ck("diff source identity", (diff["parent_sha256"], diff["child_sha256"]), (PARENT_SHA, INPUT_SHA))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("same table set", sorted(after), sorted(before))
    ck("changed tables only", sorted(k for k in before if before[k] != after[k]),
       ["MissionType", "ProblemDescription"])
    ck("unchanged tables", sum(before[k] == after[k] for k in before), 29)
    ck("13 populated source tables", len(populated(child)), 13)
    mission_before = before["MissionType"]
    mission_after = after["MissionType"]
    col = [c["name"] for c in mission_after["columns"]]
    old = dict(zip(col, mission_before["instances"][0]["rows"][0], strict=True))
    new = dict(zip(col, mission_after["instances"][0]["rows"][0], strict=True))
    ck("mission pattern", (old["MPAT"], new["MPAT"]), ("CONTINUOUS", "EXTENDABLE"))
    ck("all other mission fields", {k: v for k, v in new.items() if k != "MPAT"},
       {k: v for k, v in old.items() if k != "MPAT"})
    ck("formation", (new["NOS"], new["MNOS"]), (2, 2))
    ck("four active hours", new["DURN"], 4)

    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    ck("run identity", (invocation["run_id"], invocation["variant"], invocation["case_version"]),
       (RUN_ID, "no-interruption", "1.0.0-candidate"))
    ck("session-0 SSH", (invocation["session_id"], invocation["ssh_connection_present"],
                           "sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]]),
       (0, True, True))
    ck("GUI and mutex", (invocation["gui"]["pid"], invocation["gui"]["session_id"],
                          invocation["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("native executable", invocation["simlox_exe_sha256"], EXE_SHA)
    ck("copied input", sha(RUN / "input.json"), INPUT_SHA)
    ck("invocation seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure clean", closure["error"], None)
    ck("unchanged source during run", closure["source_hashes_before"], closure["source_hashes_after"])
    for name, info in closure["raw"].items():
        ck(f"raw seal {name}", (sha(RUN / name), (RUN / name).stat().st_size),
           (info["sha256"], info["bytes"]))
    ck("native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
                         for s in steps],
       [(name, "completed", 0, True) for name in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("roundtrip", (roundtrip["passed"], len(roundtrip["populated_tables"]),
                     roundtrip["source_sha256"]), (True, 13, INPUT_SHA))
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    ck("conversion counts", match.groups() if match else None, ("0", "2", "0"))
    ck("warning codes", sorted(re.findall(r"warning #(\d+)", run_log)), ["108", "126"])

    event = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("parent event log byte identity", sha(RUN / "model.log"), sha(PARENT_RUN / "model.log"))
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    for label, pattern, expected in (
        ("mission start", rf"(?m)^Time: ([0-9.]+) {mission} mission starting", [8.0]),
        ("mission success", rf"(?m)^Time: ([0-9.]+) {mission} mission success", [12.0]),
        ("mission completion", rf"(?m)^Time: ([0-9.]+) {mission} mission completed", [12.0]),
        ("mission suspension", rf"(?m)^Time: ([0-9.]+) {mission} mission suspended", []),
        ("failure", r"(?m)^Time: ([0-9.]+) .*critical random failure added", []),
    ):
        ck(label, [float(m.group(1)) for m in re.finditer(pattern, event)], expected)
    for aircraft in (0, 1):
        ck(f"aircraft {aircraft} allocation", len(re.findall(
            rf"(?m)^Time: 7 {mission} mission allocates system: <TEACH-AIR-01,{aircraft}>$", event)), 1)
        ck(f"aircraft {aircraft} ready at end", len(re.findall(
            rf"(?m)^Time: 12 <TEACH-AIR-01,{aircraft}> nbr ready increased at unit", event)), 1)

    report = parse_native(RUN / "report-raw.json")
    control = parse_native(PARENT_RUN / "report-raw.json")
    ck("report table names", sorted(t["name"] for t in report["report"]["tables"]),
       ["ProblemDescription", "ResultSummary", "StockTotalResults", "SystemResults"])
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        ck(f"{name} parent identity", rows(report, name), rows(control, name))
    ck("report label", rows(report, "ProblemDescription")[0]["PDESC"],
       "A06 extendable four-hour two-aircraft no-interruption control")
    summary = rows(report, "ResultSummary")[0]
    ck("summary time and fractions", tuple(summary[k] for k in
       ("RTILW", "RTIUP", "MTMF", "STMF", "MSTF", "MSUF")), (0, 16, 1, 1, 0, 0))
    system = rows(report, "SystemResults")
    stock = rows(report, "StockTotalResults")
    ck("32 aligned bins", (len(system), len(stock)), (32, 32))
    for i, (sr, st) in enumerate(zip(system, stock, strict=True)):
        ck(f"system bin {i} boundary", (sr["STINT"], sr["ETINT"]), (i * .5, (i + 1) * .5))
        ck(f"stock bin {i} boundary", (st["STINT"], st["ETINT"]), (i * .5, (i + 1) * .5))
        ck(f"stock bin {i} zero demand", tuple(st[k] for k in ("NDF", "NDD", "NDR", "NDP", "NBO")),
           (0, 0, 0, 0, 0))
    for key, expected in (("NSYMO", 8), ("STACC", 8), ("NSYMS", 0), ("NSYRP", 0), ("NSYMP", 0)):
        near(f"integrated {key}", sum((r[key] or 0) * .5 for r in system), expected)
    ck("failure/repair/preparation counts", tuple(sum(r[k] or 0 for r in system)
       for k in ("NFAIL", "NREPT", "NPSTA", "NPSUC")), (0, 0, 0, 0))
    ck("terminal two ready", (system[-1]["NSYRY"], system[-1]["NSYMO"], system[-1]["NSYMS"]),
       (2, 0, 0))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a06-var01-no-interruption-author-replay/v1",
              "passed": not failed, "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failed": failed, "checks": checks,
              "run_id": RUN_ID,
              "decision": "bounded_no_interruption_equality_if_passed",
              "limits": ["One fixed-seed no-failure formation; no generic mission-pattern equivalence.",
                         "GUI visual content and cross-engine behavior unverified."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
