"""Replay A07 regenerative source, guarded native events, and report ledgers."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, OUT as INPUT, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "a07-regenerative-relief-v100-ssh-20260930-01"
RUN = HERE / "runs" / RUN_ID
INPUT_SHA = "fed4f8343d203fc250d8b3508f3f5f9fe76ecbd1a86646d5965531d246b89240"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
OUT = HERE / "review" / "author-regenerative-validation-2026-09-30.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table, = (t for t in doc[root]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in table["instances"][0]["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tol: float = 1e-6) -> None:
        checks.append({"name": name, "passed": math.isclose(actual, expected, abs_tol=tol),
                       "actual": actual, "expected": expected, "abs_tol": tol})

    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    child = json.loads(INPUT.read_text(encoding="utf-8"))
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
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
    ck("changed tables", sorted(k for k in before if before[k] != after[k]),
       ["MissionType", "OperationProfile", "ProblemDescription", "SystemDeployment", "Unit"])
    ck("unchanged table count", sum(before[k] == after[k] for k in before), 26)
    ck("13 populated source tables", len(populated(child)), 13)
    mission = rows(child, "model", "MissionType")[0]
    ck("fixed mission with phase fractions", tuple(mission[k] for k in
       ("MPAT", "DURN", "TFOUT", "TFRET", "NOS", "MNOS", "NOPER")),
       (None, 4, .25, .25, 1, 1, 1))
    profile, = rows(child, "model", "OperationProfile")
    ck("regenerative profile", tuple(profile[k] for k in
       ("STIM", "ITYPE", "IQTY", "IQTYD", "IPER", "DTIM")),
       (8, "REGENERATIVE", None, None, 8, None))
    ck("two deployed aircraft", rows(child, "model", "SystemDeployment")[0]["QTYPS"], 2)

    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    ck("run identity", (invocation["run_id"], invocation["variant"], invocation["case_id"]),
       (RUN_ID, "regenerative", "A07"))
    ck("session-0 SSH", (invocation["session_id"], invocation["ssh_connection_present"],
                          "sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]]),
       (0, True, True))
    ck("GUI and mutex", (invocation["gui"]["pid"], invocation["gui"]["session_id"],
                         invocation["queue_mutex"]), (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("native executable", invocation["simlox_exe_sha256"], EXE_SHA)
    ck("source copy", sha(RUN / "input.json"), INPUT_SHA)
    ck("invocation seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure no error", closure["error"], None)
    ck("source unchanged during run", closure["source_hashes_before"], closure["source_hashes_after"])
    for name, info in closure["raw"].items():
        ck(f"raw seal {name}", (sha(RUN / name), (RUN / name).stat().st_size),
           (info["sha256"], info["bytes"]))
    ck("native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
                        for s in steps],
       [(name, "completed", 0, True) for name in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("exact source roundtrip", (roundtrip["passed"], len(roundtrip["populated_tables"]),
                                   roundtrip["source_sha256"]), (True, 13, INPUT_SHA))
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    ck("conversion counts", match.groups() if match else None, ("0", "2", "0"))
    ck("warning codes", sorted(re.findall(r"warning #(\d+)", run_log)), ["108", "126"])

    event = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")

    def times(index: int, label: str) -> list[float]:
        identity = rf"<BASIC-MISSION,TEACH-UNIT,0,{index},{index}>"
        return [float(m.group(1)) for m in re.finditer(
            rf"(?m)^Time: ([0-9.]+) {identity} {re.escape(label)}", event)]

    expected = [(8, 9, 11, 12), (10, 11, 13, 14), (12, 13, 15, 16), (14, 15, 15, 16)]
    ck("four created sub-missions", event.count("regenerative mission created"), 4)
    ck("four activated sub-missions", event.count("mission activated, systems requested"), 4)
    for i, (start, on, back, end) in enumerate(expected):
        ck(f"sub-mission {i} created", times(i, "regenerative mission created"),
           [float((7, 7, 9, 12)[i])])
        ck(f"sub-mission {i} activated/notified", times(i, "mission activated"),
           [float((7, 9, 11, 13)[i])])
        ck(f"sub-mission {i} start", times(i, "mission starting"), [float(start)])
        ck(f"sub-mission {i} on-station begin", times(i, "task starting"), [float(on)])
        ck(f"sub-mission {i} on-station end", times(i, "task completed"), [float(back)])
        ck(f"sub-mission {i} success", times(i, "mission success"), [float(end)])
        ck(f"sub-mission {i} completion", times(i, "mission completed"), [float(end)])
        ck(f"sub-mission {i} assigned aircraft", bool(re.search(
            rf"(?m)^Time: [0-9.]+ <BASIC-MISSION,TEACH-UNIT,0,{i},{i}> mission allocates system: <TEACH-AIR-01,{i % 2}>$",
            event)), True)
    ck("one-hour outbound phases", [on-start for start, on, _, _ in expected], [1, 1, 1, 1])
    ck("on-station intervals meet", [expected[i][2] == expected[i+1][1] for i in range(3)],
       [True, True, True])
    ck("last child truncated at period end", (expected[-1][2]-expected[-1][1], expected[-1][3]), (0, 16))
    ck("no aborted or suspended mission", bool(re.search(r"mission (?:aborted|suspended|cancelled)", event)), False)
    ck("no random failure", "critical random failure added" in event, False)
    ck("four starts/four successes", (event.count("mission starting, duration"),
                                      event.count("mission success:")), (4, 4))
    ck("two aircraft ready after final return", "Time: 16 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in event, True)

    report = parse_native(RUN / "report-raw.json")
    ck("report table names", sorted(t["name"] for t in report["report"]["tables"]),
       ["ProblemDescription", "ResultSummary", "StockTotalResults", "SystemResults"])
    summary, = rows(report, "report", "ResultSummary")
    ck("summary period", tuple(summary[k] for k in ("NREP", "RTILW", "RTIUP")), (1, 0, 36))
    near("MTMF", summary["MTMF"], 1)
    near("STMF exceeds one from regenerative overlap", summary["STMF"], 7/6)
    ck("regenerative excluded from fixed start/success fractions",
       (summary["MSTF"], summary["MSUF"]), (0, 0))
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    ck("72 aligned bins", (len(system), len(stock)), (72, 72))
    for i, (sr, st) in enumerate(zip(system, stock, strict=True)):
        ck(f"system bin {i} boundary", (sr["STINT"], sr["ETINT"]), (i*.5, (i+1)*.5))
        ck(f"stock bin {i} boundary", (st["STINT"], st["ETINT"]), (i*.5, (i+1)*.5))
        ck(f"stock bin {i} no demand/backorder", tuple(st[k] for k in
           ("NDF", "NDD", "NDR", "NDP", "NBO")), (0, 0, 0, 0, 0))
        near(f"bin {i} operation/accepted exposure", sr["NSYMO"], sr["STACC"])
    for key, expected_total in (("NSYMO", 14), ("STACC", 14), ("NSYMA", 16),
                                ("NSYMS", 0), ("NSYRP", 0), ("NSYMP", 0)):
        near(f"integrated {key} aircraft-hours", sum((r[key] or 0)*.5 for r in system), expected_total)
    ck("zero failure/repair/preparation", tuple(sum(r[k] or 0 for r in system)
       for k in ("NFAIL", "NREPT", "NPSTA", "NPSUC")), (0, 0, 0, 0))
    ck("terminal two ready", (system[-1]["NSYRY"], system[-1]["NSYMO"]), (2, 0))
    ck("finite mission count", len(expected), 4)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a07-regenerative-relief-author-replay/v1",
              "passed": not failed, "passed_count": len(checks)-len(failed),
              "failed_count": len(failed), "failed": failed, "checks": checks,
              "run_id": RUN_ID,
              "decision": "bounded_four_child_regenerative_relief_if_passed",
              "limits": ["One fixed-seed, no-failure regenerative sequence.",
                         "The fourth child has zero on-station time and returns at the period end.",
                         "GUI visual content and cross-engine equivalence remain unverified."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
