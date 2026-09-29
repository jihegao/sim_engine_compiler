"""Replay the frozen A05.var02 native failure, suspension, repair and resumption evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, OUT as INPUT, PARENT, PARENT_SHA, REPAIR_PARENT, REPAIR_PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "a05-var02-system-loss-v100-ssh-20260930-01"
RUN = HERE / "runs" / RUN_ID
INPUT_SHA = "02e823bd09fd3e6a3c2f0ae59846adcb2d35bcbc6d0ee9b09d0d936ebf36b10c"
DIFF_SHA = "a142842294b40e128eef49c32cad746ccc83019518212e605bd05c0407fcd459"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
REVIEW = HERE / "review" / "author-system-loss-validation-2026-09-30.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(doc: dict, root: str, name: str) -> list[dict]:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {root}.{name}")
    t = matches[0]
    columns = [c["name"] for c in t["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in t["instances"][0]["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tol: float = 1e-5) -> None:
        checks.append({"name": name, "passed": math.isclose(actual, expected, abs_tol=tol),
                       "actual": actual, "expected": expected, "abs_tol": tol})

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    repair_source = json.loads(REPAIR_PARENT.read_text(encoding="utf-8"))
    child = json.loads(INPUT.read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    ck("accepted A05 parent SHA", sha(PARENT), PARENT_SHA)
    ck("accepted D01 repair source SHA", sha(REPAIR_PARENT), REPAIR_PARENT_SHA)
    ck("frozen input SHA", sha(INPUT), INPUT_SHA)
    ck("exact diff SHA", sha(HERE / "exact-diff.json"), DIFF_SHA)
    ck("diff parent/child binding", (diff["parent_sha256"], diff["child_sha256"]),
       (PARENT_SHA, INPUT_SHA))
    ck("builder identity", build(), child)
    ck("contract input/parents", (contract["native_input_sha256"], contract["parent"]["input_sha256"],
                                  contract["repair_source"]["input_sha256"]),
       (INPUT_SHA, PARENT_SHA, REPAIR_PARENT_SHA))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("same table set", sorted(after), sorted(before))
    ck("exact three changed tables", sorted(k for k in before if before[k] != after[k]),
       ["ProblemDescription", "System", "SystemRepair"])
    ck("problem label", rows(child, "model", "ProblemDescription")[0]["PDESC"],
       "A05 continuous four-hour two-aircraft seeded system-loss probe")
    ck("system FRT", rows(child, "model", "System")[0]["FRT"], 300000)
    ck("repair row exactly D01", rows(child, "model", "SystemRepair"),
       rows(repair_source, "model", "SystemRepair"))
    ck("mission unchanged", rows(child, "model", "MissionType"), rows(parent, "model", "MissionType"))
    ck("deployment unchanged", rows(child, "model", "SystemDeployment"),
       rows(parent, "model", "SystemDeployment"))

    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    ck("run identity", (invocation["run_id"], invocation["variant"], invocation["case_version"]),
       (RUN_ID, "loss", "var02-1.0.0-candidate"))
    ck("copied source SHA", sha(RUN / "input.json"), INPUT_SHA)
    ck("session-0 SSH", (invocation["session_id"], invocation["ssh_connection_present"],
                          "sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]]),
       (0, True, True))
    ck("GUI and mutex", (invocation["gui"]["pid"], invocation["gui"]["session_id"],
                          invocation["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("exe SHA", invocation["simlox_exe_sha256"], EXE_SHA)
    ck("invocation seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure error", closure["error"], None)
    ck("source hashes unchanged", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("closure input/parents", tuple(closure["source_hashes_before"][k] for k in
                                       ("input", "parent", "repair_parent")),
       (INPUT_SHA, PARENT_SHA, REPAIR_PARENT_SHA))
    for name, info in closure["raw"].items():
        ck(f"raw seal {name}", (sha(RUN / name), (RUN / name).stat().st_size),
           (info["sha256"], info["bytes"]))
    ck("native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
                        for s in steps],
       [(name, "completed", 0, True) for name in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("roundtrip", (roundtrip["passed"], len(roundtrip["populated_tables"]),
                     roundtrip["source_sha256"]), (True, 14, INPUT_SHA))
    ck("source row tables", len(populated(child)), 14)
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion totals", re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
                                       run_log).groups(), ("0", "2", "0"))
    ck("conversion warnings", sorted(re.findall(r"warning #(\d+)", run_log)), ["108", "126"])
    event = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    mission = r"<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    markers = [
        ("mission starting", rf"{mission} mission starting", 8.0),
        ("critical random failure", r"<TEACH-AIR-01,0> critical random failure added", 9.8829),
        ("mission suspended", rf"{mission} mission suspended", 9.8829),
        ("system repair started", r"\s+system DIRP task 0 on <TEACH-AIR-01,0> started$", 9.8829),
        ("system repair completed", r"\s+system DIRP task 0 on <TEACH-AIR-01,0> completed$", 10.3829),
        ("system attached", rf"{mission} system attached: <TEACH-AIR-01,0>", 10.3829),
        ("mission resumed", rf"{mission} mission resumed", 10.3829),
        ("mission success", rf"{mission} mission success", 12.0),
        ("mission completed", rf"{mission} mission completed", 12.0),
    ]
    for label, pattern, expected in markers:
        times = [float(m.group(1)) for m in re.finditer(
            rf"(?m)^Time: ([0-9.]+) {pattern}", event)]
        ck(f"event {label}", times, [expected])
    ck("repaired aircraft rejoins", "Time: 10.3829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>" in event,
       True)
    ck("retained aircraft resumes", "<TEACH-AIR-01,1> resumed on mission" in event, True)
    ck("repaired aircraft resumes", "<TEACH-AIR-01,0> resumed on mission" in event, True)
    ck("distinct third aircraft absent", "<TEACH-AIR-01,2>" in event, False)

    report = parse_native(RUN / "report-raw.json")
    ck("report table names", sorted(t["name"] for t in report["report"]["tables"]),
       ["ProblemDescription", "ResultSummary", "StockTotalResults", "SystemResults"])
    summary = rows(report, "report", "ResultSummary")
    ck("one summary", len(summary), 1)
    near("mission active-time fraction", summary[0]["MTMF"], 0.875)
    near("system active-time fraction", summary[0]["STMF"], 0.875)
    ck("fixed-only summary fractions", (summary[0]["MSTF"], summary[0]["MSUF"]), (0, 0))
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    ck("32 system and stock bins", (len(system), len(stock)), (32, 32))
    for i, (sr, st) in enumerate(zip(system, stock, strict=True)):
        ck(f"system bin {i} interval", (sr["STINT"], sr["ETINT"]), (i * .5, (i + 1) * .5))
        ck(f"stock bin {i} interval", (st["STINT"], st["ETINT"]), (i * .5, (i + 1) * .5))
        near(f"system bin {i} operation/accepted exposure", sr["NSYMO"], sr["STACC"])
        ck(f"stock bin {i} no demand/backorder", (st["NDF"], st["NDD"], st["NDR"], st["NDP"], st["NBO"]),
           (0, 0, 0, 0, 0))
    for key, expected in [("NSYMO", 7.0), ("STACC", 7.0), ("NSYMS", .5), ("NSYRP", .5)]:
        near(f"integrated {key} aircraft-hours", sum((r[key] or 0) * .5 for r in system), expected)
    ck("failure and repair counts", (sum(r["NFAIL"] or 0 for r in system),
                                      sum(r["NREPT"] or 0 for r in system)), (1, 1))
    ck("terminal ready", (system[-1]["NSYRY"], system[-1]["NSYMO"], system[-1]["NSYMS"]), (2, 0, 0))
    near("suspension duration hours", 10.3829 - 9.8829, .5)
    near("mission calendar duration hours", 12 - 8, 4)
    near("mission operating fraction from event times", ((9.8829 - 8) + (12 - 10.3829)) / 4, .875)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a05-var02-system-loss-author-replay/v1", "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed), "failed": failed,
              "checks": checks, "run_id": RUN_ID,
              "decision": "bounded_same_aircraft_repair_and_sustained_resumption_if_passed",
              "limits": ["One fixed seed; actual failure time is observed, not controlled.",
                         "The same aircraft is repaired and reattached; no distinct spare replacement is shown.",
                         "A05.var02 and full A05 remain unaccepted without a separately verified replacement case."]}
    REVIEW.parent.mkdir(exist_ok=True)
    REVIEW.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
