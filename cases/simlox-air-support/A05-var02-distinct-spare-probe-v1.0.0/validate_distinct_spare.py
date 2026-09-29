"""Replay frozen A05.var02 distinct-aircraft replacement evidence and limits."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, OUT as INPUT, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "a05-var02-distinct-spare-v100-ssh-20260930-01"
RUN = HERE / "runs" / RUN_ID
INPUT_SHA = "aab1e4050a107e8490716a9306d9eb461b5c4a0c88430c157a2699afc5a120bb"
DIFF_SHA = "2c62f7b716c9f4441a65e1753da66e2acf2c2597e394a8fcbcced761a987d2e6"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
OUT = HERE / "review" / "author-distinct-spare-validation-2026-09-30.json"


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
    child = json.loads(INPUT.read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    ck("accepted parent SHA", sha(PARENT), PARENT_SHA)
    ck("frozen input SHA", sha(INPUT), INPUT_SHA)
    ck("builder identity", build(), child)
    ck("contract input/parent", (contract["native_input_sha256"], contract["parent"]["input_sha256"]),
       (INPUT_SHA, PARENT_SHA))
    ck("diff SHA", sha(HERE / "exact-diff.json"), DIFF_SHA)
    ck("diff source binding", (diff["parent_sha256"], diff["child_sha256"]), (PARENT_SHA, INPUT_SHA))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("same source table set", sorted(after), sorted(before))
    ck("exact changed tables", sorted(k for k in before if before[k] != after[k]),
       ["ProblemDescription", "SystemDeployment", "Unit"])
    ck("only one extra deployed aircraft", rows(child, "model", "SystemDeployment")[0]["QTYPS"], 3)
    ck("mission quantity remains two", tuple(rows(child, "model", "MissionType")[0][k]
                                             for k in ("NOS", "MNOS", "DURN", "MPAT")),
       (2, 2, 4, "CONTINUOUS"))
    ck("failure and repair tables unchanged", (rows(child, "model", "System"),
                                               rows(child, "model", "SystemRepair")),
       (rows(parent, "model", "System"), rows(parent, "model", "SystemRepair")))

    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    ck("run identity", (invocation["run_id"], invocation["variant"], invocation["case_version"]),
       (RUN_ID, "spare", "distinct-spare-1.0.0-candidate"))
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
    ck("closure input/parent", (closure["source_hashes_before"]["input"],
                                closure["source_hashes_before"]["parent"]), (INPUT_SHA, PARENT_SHA))
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
    def times(pattern: str) -> list[float]:
        return [float(m.group(1)) for m in re.finditer(rf"(?m)^Time: ([0-9.]+) {pattern}", event)]

    ck("initial allocation #0", times(rf"{mission} mission allocates system: <TEACH-AIR-01,0>"), [7.0, 11.7431])
    ck("initial allocation #1", times(rf"{mission} mission allocates system: <TEACH-AIR-01,1>"), [7.0])
    ck("first distinct replacement #2", times(rf"{mission} mission allocates system: <TEACH-AIR-01,2>"), [9.8829])
    ck("mission start/end", (times(rf"{mission} mission starting"),
                             times(rf"{mission} mission completed")), ([8.0], [12.0]))
    ck("failure #0", times(r"<TEACH-AIR-01,0> critical random failure added"), [9.8829])
    ck("failure #1", times(r"<TEACH-AIR-01,1> critical random failure added"), [11.7431])
    ck("two suspension markers", times(rf"{mission} mission suspended"), [9.8829, 11.7431])
    ck("two resumption markers", times(rf"{mission} mission resumed"), [9.8829, 11.7431])
    ck("replacement #2 attached", times(rf"{mission} system attached: <TEACH-AIR-01,2>"), [9.8829])
    ck("repaired #0 attached", times(rf"{mission} system attached: <TEACH-AIR-01,0>"), [11.7431])
    ck("repair completion #0", times(r"\s+system DIRP task 0 on <TEACH-AIR-01,0> completed$"), [10.3829])
    ck("repair completion #1", times(r"\s+system DIRP task 1 on <TEACH-AIR-01,1> completed$"), [12.2431])
    ck("terminal mission participants #2/#0",
       "Time: 12 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,2>,<TEACH-AIR-01,0>" in event,
       True)

    report = parse_native(RUN / "report-raw.json")
    ck("report tables", sorted(t["name"] for t in report["report"]["tables"]),
       ["ProblemDescription", "ResultSummary", "StockTotalResults", "SystemResults"])
    summary = rows(report, "report", "ResultSummary")[0]
    ck("mission/system time fractions", (summary["MTMF"], summary["STMF"]), (1, 1))
    ck("fixed-only summary fractions", (summary["MSTF"], summary["MSUF"]), (0, 0))
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    ck("32 system and stock bins", (len(system), len(stock)), (32, 32))
    for i, (sr, st) in enumerate(zip(system, stock, strict=True)):
        ck(f"system bin {i} interval", (sr["STINT"], sr["ETINT"]), (i * .5, (i + 1) * .5))
        ck(f"stock bin {i} interval", (st["STINT"], st["ETINT"]), (i * .5, (i + 1) * .5))
        near(f"bin {i} operation/accepted exposure", sr["NSYMO"], sr["STACC"])
        ck(f"bin {i} no suspended aircraft", sr["NSYMS"], 0)
        ck(f"stock bin {i} no demand/backorder", (st["NDF"], st["NDD"], st["NDR"], st["NDP"], st["NBO"]),
           (0, 0, 0, 0, 0))
    for key, expected in [("NSYMO", 8), ("STACC", 8), ("NSYMS", 0), ("NSYRP", 1)]:
        near(f"integrated {key} aircraft-hours", sum((r[key] or 0) * .5 for r in system), expected)
    ck("two failures and repairs", (sum(r["NFAIL"] or 0 for r in system),
                                     sum(r["NREPT"] or 0 for r in system)), (2, 2))
    ck("terminal three ready", (system[-1]["NSYRY"], system[-1]["NSYMO"], system[-1]["NSYMS"]),
       (3, 0, 0))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a05-var02-distinct-spare-author-replay/v1", "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed), "failed": failed,
              "checks": checks, "run_id": RUN_ID,
              "decision": "bounded_distinct_spare_immediate_replacement_if_passed",
              "limits": ["One fixed seed; two actual failure times observed rather than controlled.",
                         "Suspension and resumption markers share timestamps; no finite mission suspension observed.",
                         "The third deployed aircraft is a system-level ready spare, not stocked materiel.",
                         "Full A05.var02 and full A05 method remain unaccepted."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:4]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
