"""Replay A06.var03 source and report-window/full-run distinction."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, OUT as INPUT, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "a06-var03-report-window-v100-ssh-20260930-01"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = HERE.parent / "A06-extendable-prepared-gap-v1.0.0" / "runs" / "a06-extendable-prepared-gap-v100-ssh-20260930-01"
STOP_RUN = HERE.parent / "A06-var04-horizon-suspension-v1.0.0" / "runs" / "a06-var04-horizon-suspension-v100-ssh-20260930-01"
INPUT_SHA = "0fcd389734758af9b0c5c1b5ae4adfbca27135153954384b2cf7333ac4c9b3ff"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
OUT = HERE / "review" / "author-window-validation-2026-09-30.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(doc: dict, root: str, name: str) -> list[dict]:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {root}.{name}")
    table = matches[0]
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in table["instances"][0]["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tol: float = 1e-5) -> None:
        checks.append({"name": name, "passed": math.isclose(actual, expected, abs_tol=tol),
                       "actual": actual, "expected": expected, "abs_tol": tol})

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    child = json.loads(INPUT.read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    ck("accepted parent SHA", sha(PARENT), PARENT_SHA)
    ck("frozen child SHA", sha(INPUT), INPUT_SHA)
    ck("builder identity", build(), child)
    ck("contract source binding", (contract["parent"]["input_sha256"], contract["native_input_sha256"]),
       (PARENT_SHA, INPUT_SHA))
    ck("diff source binding", (diff["parent_sha256"], diff["child_sha256"]),
       (PARENT_SHA, INPUT_SHA))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("same table set", sorted(after), sorted(before))
    ck("only report-window and description tables changed",
       sorted(k for k in before if before[k] != after[k]),
       ["Control", "ProblemDescription", "ResultCollection"])
    ck("28 unchanged tables", sum(before[k] == after[k] for k in before), 28)
    ck("simulation/report horizon", tuple(rows(child, "model", "Control")[0][k] for k in
                                          ("SIMPE", "RCEND")), (16.0, 12.5))
    ck("both result collection ends", [r["RCEND"] for r in rows(child, "model", "ResultCollection")],
       [12.5, 12.5])
    ck("parent horizon", tuple(rows(parent, "model", "Control")[0][k] for k in
                                ("SIMPE", "RCEND")), (16.0, 16.0))
    ck("mission and aircraft unchanged", (rows(child, "model", "MissionType"),
                                          rows(child, "model", "SystemDeployment")),
       (rows(parent, "model", "MissionType"),
        rows(parent, "model", "SystemDeployment")))

    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    ck("run identity", (invocation["run_id"], invocation["variant"], invocation["case_version"]),
       (RUN_ID, "window", "var03-1.0.0-candidate"))
    ck("source copy", sha(RUN / "input.json"), INPUT_SHA)
    ck("session-0 SSH", (invocation["session_id"], invocation["ssh_connection_present"],
                          "sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]]),
       (0, True, True))
    ck("GUI identity and mutex", (invocation["gui"]["pid"], invocation["gui"]["session_id"],
                                  invocation["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("installed executable", invocation["simlox_exe_sha256"], EXE_SHA)
    ck("invocation seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure no error", closure["error"], None)
    ck("source unchanged", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("source hashes", (closure["source_hashes_before"]["input"],
                         closure["source_hashes_before"]["parent"]), (INPUT_SHA, PARENT_SHA))
    for name, info in closure["raw"].items():
        ck(f"raw seal {name}", (sha(RUN / name), (RUN / name).stat().st_size),
           (info["sha256"], info["bytes"]))
    ck("native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
                        for s in steps],
       [(name, "completed", 0, True) for name in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("roundtrip", (roundtrip["passed"], len(roundtrip["populated_tables"]),
                     roundtrip["source_sha256"]), (True, 16, INPUT_SHA))
    ck("source row tables", len(populated(child)), 16)
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion totals", re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
                                       run_log).groups(), ("0", "2", "0"))
    ck("conversion warnings", sorted(re.findall(r"warning #(\d+)", run_log)), ["108", "126"])

    event = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_event = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("complete native event log equals accepted parent", sha(RUN / "model.log"),
       sha(PARENT_RUN / "model.log"))
    mission = r"<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    def times(pattern: str) -> list[float]:
        return [float(m.group(1)) for m in re.finditer(rf"(?m)^Time: ([0-9.]+) {pattern}", event)]

    ck("mission started", times(rf"{mission} mission starting"), [8.0])
    ck("two critical failures", (times(r"<TEACH-AIR-01,0> critical random failure added"),
                                 times(r"<TEACH-AIR-01,1> critical random failure added")),
       ([9.8829], [12.2431]))
    ck("two suspensions", times(rf"{mission} mission suspended"), [9.8829, 12.2431])
    ck("resumes across result-window end", times(rf"{mission} mission resumed"),
       [10.3829, 12.7431])
    ck("completion after result-window end", times(rf"{mission} mission completed"), [13.0])
    ck("success after result-window end", times(rf"{mission} mission success"), [13.0])
    ck("first spare attached", times(rf"{mission} system attached: <TEACH-AIR-01,2>"), [10.3829])
    ck("second replacement attaches after report end", times(rf"{mission} system attached: <TEACH-AIR-01,0>"),
       [12.7431])
    ck("first repair completed", times(r"\s+system DIRP task \d+ on <TEACH-AIR-01,0> completed$"), [10.3829])
    ck("second repair completes after report end",
       (times(r"\s+system DIRP task \d+ on <TEACH-AIR-01,1> started$"),
        times(r"\s+system DIRP task \d+ on <TEACH-AIR-01,1> completed$")),
       ([12.2431], [12.7431]))
    ck("second preparation completes after report end",
       (times(r"<TEACH-AIR-01,0> preparation started"),
        times(r"<TEACH-AIR-01,0> preparation ended")),
       ([7.0, 12.2431], [7.5, 12.7431]))
    ck("retained #2 during second suspension", "Time: 12.2431 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission suspended: <TEACH-AIR-01,2>" in event, True)

    report = parse_native(RUN / "report-raw.json")
    ck("report tables", sorted(t["name"] for t in report["report"]["tables"]),
       ["ProblemDescription", "ResultSummary", "StockTotalResults", "SystemResults"])
    summary = rows(report, "report", "ResultSummary")[0]
    ck("full-simulation summary fractions", (summary["MTMF"], summary["STMF"]), (1, 1))
    ck("summary simulation upper bound", summary["RTIUP"], 16)
    ck("fixed-only summary fractions", (summary["MSTF"], summary["MSUF"]), (0, 0))
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    ck("25 aligned bins", (len(system), len(stock)), (25, 25))
    parent_report = parse_native(PARENT_RUN / "report-raw.json")
    ck("system bins equal full parent first 25", system,
       rows(parent_report, "report", "SystemResults")[:25])
    ck("stock bins equal full parent first 25", stock,
       rows(parent_report, "report", "StockTotalResults")[:25])
    stop_report = parse_native(STOP_RUN / "report-raw.json")
    stop_system = rows(stop_report, "report", "SystemResults")
    stop_stock = rows(stop_report, "report", "StockTotalResults")
    ck("stock bins equal simulation-stop control", stock, stop_stock)
    changed_bin_fields = [(i, k, sr[k], cr[k]) for i, (sr, cr) in
                          enumerate(zip(system, stop_system, strict=True)) for k in sr if sr[k] != cr[k]]
    ck("only completed-downtime fields differ from simulation-stop control",
       changed_bin_fields, [(24, "SYDT", .5, None), (24, "NSYDT", 1, 0)])
    for i, (sr, st) in enumerate(zip(system, stock, strict=True)):
        ck(f"system bin {i}", (sr["STINT"], sr["ETINT"]), (i * .5, (i + 1) * .5))
        ck(f"stock bin {i}", (st["STINT"], st["ETINT"]), (i * .5, (i + 1) * .5))
        near(f"bin {i} operation/accepted exposure", sr["NSYMO"], sr["STACC"])
        ck(f"stock bin {i} no demand/backorder", tuple(st[k] for k in
            ("NDF", "NDD", "NDR", "NDP", "NBO")), (0, 0, 0, 0, 0))
    integrated = {key: sum((r[key] or 0) * .5 for r in system) for key in
                  ("NSYMO", "STACC", "NSYMS", "NSYRP", "NSYMP")}
    for key, expected in (("NSYMO", 7.486288249492645), ("STACC", 7.486288249492645),
                          ("NSYMS", .7568558603525162), ("NSYRP", .7568558603525162),
                          ("NSYMP", 1.7568558603525162)):
        near(f"integrated {key} aircraft-hours", integrated[key], expected)
    near("operation from printed event timing", integrated["NSYMO"],
         2 * ((12.5 - 8) - .5 - (12.5 - 12.2431)), 5e-4)
    near("suspension from printed event timing", integrated["NSYMS"],
         .5 + (12.5 - 12.2431), 5e-4)
    near("remaining active hours inferred", 4 - integrated["NSYMO"] / 2,
         13 - 12.7431, 5e-4)
    ck("report-window events omit later completions", (sum(r["NFAIL"] or 0 for r in system),
                                                         sum(r["NREPT"] or 0 for r in system),
                                                         sum(r["NPSTA"] or 0 for r in system),
                                                         sum(r["NPSUC"] or 0 for r in system)), (2, 1, 4, 3))
    ck("last bin is interval not terminal point", (system[-1]["STINT"], system[-1]["ETINT"]),
       (12.0, 12.5))
    ck("last bin partial suspension and work", all(system[-1][k] > 0 for k in
       ("NSYMS", "NSYMP", "NSYRP")), True)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a06-var03-report-window-suspension-author-replay/v1",
              "passed": not failed, "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failed": failed, "checks": checks,
              "run_id": RUN_ID,
              "decision": "bounded_report_window_ends_during_suspension_full_run_completes_if_passed",
              "limits": ["ResultSummary reflects the full simulation while SystemResults and StockTotalResults bins end at 12.5.",
                         "SYDT/NSYDT can register completed downtime in its earlier start interval after the report window ends.",
                         "Remaining active hours at 12.5 are inferred from DURN and operating exposure; later completion is event-observed.",
                         "One stochastic seed and observed failure onset; no generic result-window rule."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
