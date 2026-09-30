"""Replay frozen A05 MNOSA=1 source, sealed native events, and report."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, OUT as INPUT, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "a05-var03-mnosa-one-v100-ssh-20260930-01"
RUN = HERE / "runs" / RUN_ID
INPUT_SHA = "586e9b765dd5ab69e578fa3d2ed18262b5b6148fc48862c14e6c95846241d1fa"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
OUT = HERE / "review" / "author-mnosa-validation-2026-09-30.json"


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
    ck("only two changed tables", sorted(k for k in before if before[k] != after[k]),
       ["MissionType", "ProblemDescription"])
    ck("29 unchanged tables", sum(before[k] == after[k] for k in before), 29)
    old_mission = rows(parent, "model", "MissionType")[0]
    new_mission = rows(child, "model", "MissionType")[0]
    ck("MNOS retained at two", (old_mission["MNOS"], new_mission["MNOS"]), (2, 2))
    ck("MNOSA lowered", (old_mission["MNOSA"], new_mission["MNOSA"]), (None, 1))
    ck("remaining mission fields unchanged",
       {k: v for k, v in new_mission.items() if k != "MNOSA"},
       {k: v for k, v in old_mission.items() if k != "MNOSA"})
    ck("three deployed aircraft", [r["QTYPS"] for r in rows(child, "model", "SystemDeployment")], [3])

    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    ck("run identity", (invocation["run_id"], invocation["variant"], invocation["case_version"]),
       (RUN_ID, "mnosa", "var03-1.0.0-candidate"))
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
    mission = r"<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    def times(pattern: str) -> list[float]:
        return [float(m.group(1)) for m in re.finditer(rf"(?m)^Time: ([0-9.]+) {pattern}", event)]

    ck("initial aircraft allocation", (times(rf"{mission} mission allocates system: <TEACH-AIR-01,0>"),
                                      times(rf"{mission} mission allocates system: <TEACH-AIR-01,1>")),
       ([7.0, 11.1325], [7.0]))
    ck("distinct #2 allocation", times(rf"{mission} mission allocates system: <TEACH-AIR-01,2>"),
       [9.8829])
    ck("mission start/end", (times(rf"{mission} mission starting"),
                             times(rf"{mission} mission completed")), ([8.0], [12.0]))
    ck("failures #0/#1", (times(r"<TEACH-AIR-01,0> critical random failure added"),
                          times(r"<TEACH-AIR-01,1> critical random failure added")),
       ([9.8829], [11.1325]))
    ck("no whole-mission suspension", times(rf"{mission} mission suspended"), [])
    ck("no whole-mission resume", times(rf"{mission} mission resumed"), [])
    ck("replacement attachments", (times(rf"{mission} system attached: <TEACH-AIR-01,2>"),
                                     times(rf"{mission} system attached: <TEACH-AIR-01,0>")),
       ([10.3829], [11.6325]))
    for system, start, end in ((2, 9.8829, 10.3829), (0, 11.1325, 11.6325)):
        ck(f"replacement #{system} preparation", (times(rf"<TEACH-AIR-01,{system}> preparation started"),
                                                 times(rf"<TEACH-AIR-01,{system}> preparation ended")),
           ([start] if system == 2 else [7.0, start],
            [end] if system == 2 else [7.5, end]))
    for system, start, end in ((0, 9.8829, 10.3829), (1, 11.1325, 11.6325)):
        ck(f"repair #{system}",
           (times(rf"\s+system DIRP task \d+ on <TEACH-AIR-01,{system}> started$"),
            times(rf"\s+system DIRP task \d+ on <TEACH-AIR-01,{system}> completed$")),
           ([start], [end]))
    ck("mission success", times(rf"{mission} mission success"), [12.0])
    ck("final participants", "Time: 12 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,2>,<TEACH-AIR-01,0>" in event, True)

    report = parse_native(RUN / "report-raw.json")
    ck("report tables", sorted(t["name"] for t in report["report"]["tables"]),
       ["ProblemDescription", "ResultSummary", "StockTotalResults", "SystemResults"])
    summary = rows(report, "report", "ResultSummary")[0]
    ck("mission/system time fractions", (summary["MTMF"], summary["STMF"]), (1, .875))
    ck("fixed-only fractions", (summary["MSTF"], summary["MSUF"]), (0, 0))
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    ck("32 aligned bins", (len(system), len(stock)), (32, 32))
    for i, (sr, st) in enumerate(zip(system, stock, strict=True)):
        ck(f"system bin {i}", (sr["STINT"], sr["ETINT"]), (i * .5, (i + 1) * .5))
        ck(f"stock bin {i}", (st["STINT"], st["ETINT"]), (i * .5, (i + 1) * .5))
        near(f"bin {i} operation/accepted exposure", sr["NSYMO"], sr["STACC"])
        ck(f"stock bin {i} no demand/backorder", tuple(st[k] for k in
            ("NDF", "NDD", "NDR", "NDP", "NBO")), (0, 0, 0, 0, 0))
    for key, expected in (("NSYMO", 7), ("STACC", 7), ("NSYMS", 0),
                          ("NSYRP", 1), ("NSYMP", 2)):
        near(f"integrated {key} aircraft-hours", sum((r[key] or 0) * .5 for r in system), expected)
    ck("two failures and repairs", (sum(r["NFAIL"] or 0 for r in system),
                                    sum(r["NREPT"] or 0 for r in system)), (2, 2))
    ck("four preparation starts/completions", (sum(r["NPSTA"] or 0 for r in system),
                                                sum(r["NPSUC"] or 0 for r in system)), (4, 4))
    ck("three terminal ready", (system[-1]["NSYRY"], system[-1]["NSYMO"],
                                  system[-1]["NSYMS"]), (3, 0, 0))
    for start in (9.5, 10, 11, 11.5):
        active = next(r for r in system if r["STINT"] == start)
        ck(f"survivor operates in bin {start}", active["NSYMO"] > 0, True)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a05-var03-mnosa-one-author-replay/v1",
              "passed": not failed, "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failed": failed, "checks": checks,
              "run_id": RUN_ID,
              "decision": "bounded_active_mission_continues_with_one_aircraft_if_passed",
              "limits": ["One seed; two random failures observed, timing not controlled.",
                         "Does not test start or resumption from suspension below MNOS.",
                         "No generic A05 policy, GUI visual content, or cross-engine claim."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
