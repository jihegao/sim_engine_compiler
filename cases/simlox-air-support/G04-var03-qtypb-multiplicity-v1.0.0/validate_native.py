"""Replay G04.var03 QTYPB source, guarded native run and parent contrast."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated

RUN_ID = "g04-var03-qtypb2-v100-ssh-20261003-01"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = HERE.parent / "G04-three-branch-threshold-v1.0.0" / "runs" / "g04-kn-two-v100-ssh-20261002-01"
OUT = HERE / "author-validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table_map(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def close(value: object, expected: float, tol: float = 1e-4) -> bool:
    return isinstance(value, (float, int)) and math.isclose(float(value), expected, rel_tol=0, abs_tol=tol)


def failure_events(log: str) -> list[tuple]:
    result = []
    for match in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                             r"(.*?)\n(?=Time:|$)", log, re.S):
        modes = re.findall(r"Failure Mode: (FM-POS-[A-Z]) on materiel: <(POS-[A-Z]),0>", match.group(3))
        result.append((float(match.group(1)), match.group(2), modes))
    return result


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, diff, parent, child = (read(p) for p in (HERE / "contract.json", HERE / "exact-diff.json", PARENT, HERE / "native-input.json"))
    ck("contract identity", (contract["case_id"], contract["variant_id"]), ("G04", "G04.var03"))
    ck("parent input seal", sha(PARENT), PARENT_SHA)
    ck("parent native closure seal", sha(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"])
    ck("child input seal", sha(HERE / "native-input.json"), contract["input_sha256"])
    ck("builder replay", make(), child)
    ck("exact diff seal", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    old, new = table_map(parent), table_map(child)
    changed = {name: {"before": old[name], "after": new[name]} for name in old if old[name] != new[name]}
    ck("four exact table changes", sorted(changed), ["MaterielStructure", "ProblemDescription", "RBDParallel", "RBDParallelStructure"])
    ck("exact diff replay", diff["changed"], changed)
    ck("diff source pins", (diff["parent_sha256"], diff["input_sha256"]), (PARENT_SHA, contract["input_sha256"]))
    ck("two installed C copies", rows(child, "MaterielStructure")[2], ["POS-C", "TEACH-AIR-01", 2, 1.0, None, None])
    ck("two C output links", rows(child, "RBDParallelStructure")[2], ["G04-PARALLEL", "POS-C", "G04-OPS", 2, 1, None])
    ck("active two-of-four", rows(child, "RBDParallel")[0][2:6], [2, 4, 0.0, "N"])
    ck("fixed failure modes", rows(child, "FailureMode"), rows(parent, "FailureMode"))
    ck("fixed mission and controls", (rows(child, "MissionType"), rows(child, "OperationProfile"), rows(child, "Control")),
       (rows(parent, "MissionType"), rows(parent, "OperationProfile"), rows(parent, "Control")))

    inv, closure, steps, rt = (read(RUN / n) for n in ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]), (RUN_ID, "qty2", RUN_ID, "qty2"))
    ck("SSH session-zero", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
       (0, True, "session0_ssh_cli"))
    ck("GUI and serial queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
    ck("stable sources", closure["source_hashes_before"], closure["source_hashes_after"])
    sources = closure["source_hashes_before"]
    paths = {"input": HERE / "native-input.json", "parent": PARENT, "parent_closure": PARENT_RUN / "closure.json",
             "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
             "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
    for key, path in paths.items():
        ck(f"source seal {key}", sources[key], sha(path))
    ck("installed source pins", (sources["exe"], sources["manual"], sources["dictionary"]),
       (contract["source"]["exe_sha256"], contract["source"]["manual_sha256"], contract["source"]["dictionary_sha256"]))
    ck("invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    ck("accepted native outcome", (closure["error"], closure["native_outcome"]), (None, "zero_error_reviewed_warnings"))
    ck("five native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("13 raw files", len(closure["raw"]), 13)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
    ck("roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
       (True, [], contract["input_sha256"]))
    authored, exported = populated(child), populated(native_json(RUN / "roundtrip-raw.json"))
    ck("23 populated tables", len(authored), 23)
    for name, value in authored.items():
        ck(f"native table {name}", exported.get(name), value)
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion counts", re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log).groups(), ("0", "1", "0"))
    ck("reviewed warning", re.findall(r"\(warning #(\d+)\)", run_log), ["108"])
    ck("no native converter errors", re.findall(r"\(error #(\d+)\)", run_log), [])

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    events, parent_events = failure_events(log), failure_events(parent_log)
    expected = [(8.62763, "noncritical", [("FM-POS-B", "POS-B")]),
                (16.7498, "noncritical", [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")])]
    ck("two noncritical failure events", events, expected)
    ck("identical A/B samples versus parent", [(t, modes) for t, _, modes in events],
       [(t, modes) for t, _, modes in parent_events])
    ck("parent second failure critical", parent_events[1][1], "critical")
    ck("child no extra failure", log.count("CM failure mode added"), 2)
    ck("mission start", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log, True)
    ck("child mission success", (log.count(" mission success:"), log.count(" mission aborted:"),
                                 "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log), (1, 0, True))
    ck("parent mission abort", "Time: 16.7498 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in parent_log, True)
    starts = re.findall(r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)
    ends = re.findall(r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)
    ck("postmission parallel CM", (starts, ends), ([('34', '0', 'FM-POS-B'), ('34', '1', 'FM-POS-A')], [('34.5', '0'), ('34.5', '1')]))
    ck("terminal ready event", "Time: 34.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>" in log, True)

    report = native_json(RUN / "report-raw.json")
    summary, system, stock = (report_rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    parent_report = native_json(PARENT_RUN / "report-raw.json")
    parent_summary, parent_system = (report_rows(parent_report, n) for n in ("ResultSummary", "SystemResults"))
    ck("report tables", {t["name"] for t in report["report"]["tables"]},
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("one rep and horizon", (summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"]), (1, 0, 36))
    ck("child versus parent mission success", (summary[0]["MSUF"], parent_summary[0]["MSUF"]), (1, 0))
    ck("aligned 72 System bins", [(r["STINT"], r["ETINT"]) for r in system], [(i / 2, (i + 1) / 2) for i in range(72)])
    ck("aligned 72 Stock bins", [(r["STINT"], r["ETINT"]) for r in stock], [(i / 2, (i + 1) / 2) for i in range(72)])
    ck("two failures and repairs", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (2, 2))
    ck("failure bins", [r["STINT"] for r in system if r["NFAIL"]], [8.5, 16.5])
    ck("child repair after success", [r["STINT"] for r in system if r["NREPT"]], [34.5])
    ck("parent repair after abort", [r["STINT"] for r in parent_system if r["NREPT"]], [23.5])
    ck("zero stock movement", all(close(r[k] or 0, 0) for r in stock for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
    ck("terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))
    ck("full mission exposure", close(0.5 * sum(r["NSYMO"] or 0 for r in system), 26), True)
    ck("parent shorter exposure", 0.5 * sum(r["NSYMO"] or 0 for r in parent_system) < 26, True)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g04-var03-author-native-replay/v1", "case_id": "G04", "variant_id": "G04.var03",
              "run_id": RUN_ID, "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"parent": "active 2-of-3, second A/B failure critical h16.7498, mission aborted",
                              "child": "active 2-of-4 with two POS-C copies, same A/B samples both noncritical, mission succeeds h34",
                              "child_repair_window": "h34–34.5", "child_terminal_ready": 1}, "limits": contract["limits"]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
