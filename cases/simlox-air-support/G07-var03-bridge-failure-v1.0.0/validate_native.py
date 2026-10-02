"""Replay source, guarded native, event and report evidence for G07.var03."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import CONTROL, CONTROL_SHA, HERE, MAPPING, PARENT, PARENT_SHA, live_paths, make, rows
from check_roundtrip import native_json, populated

RUN_ID = "g07-var03-brfirst-v100-ssh-20261003-01"
PARENT_RUN = HERE.parent / "G07-four-path-panel-v1.0.0" / "runs" / "g07-panel-allbroken-v100-ssh-20261003-01"
CONTROL_RUN = HERE.parent / "G07-four-path-panel-v1.0.0" / "runs" / "g07-panel-ulur-v100-ssh-20261003-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_rows(doc: dict, name: str) -> list[dict]:
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r, strict=True)) for inst in t["instances"] for r in inst["rows"]]


def failure_events(log: str) -> list[tuple]:
    out = []
    for m in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                         r"(.*?)\n(?=Time:|$)", log, re.S):
        modes = re.findall(r"Failure Mode: (FM-POS-[A-Z]) on materiel: <(POS-[A-Z]),0>", m.group(3))
        out.append((float(m.group(1)), m.group(2), modes))
    return out


def close(value: object, expected: float, tol: float = 1e-4) -> bool:
    return isinstance(value, (int, float)) and math.isclose(float(value), expected, rel_tol=0, abs_tol=tol)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None, "want": want if got != want else None})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    child, parent = read(HERE / "brfirst-input.json"), read(PARENT)
    ck("contract identity", (contract["case_id"], contract["variant_id"]), ("G07", "G07.var03"))
    ck("parent and comparator input seals", (sha(PARENT), sha(CONTROL)), (PARENT_SHA, CONTROL_SHA))
    ck("accepted closure seals", (sha(PARENT_RUN / "closure.json"), sha(CONTROL_RUN / "closure.json")),
       (contract["accepted_parent"]["native_closure_sha256"], contract["accepted_comparator"]["native_closure_sha256"]))
    ck("frozen input/diff seals", (sha(HERE / "brfirst-input.json"), sha(HERE / "exact-diff.json")),
       (contract["input_sha256"], contract["exact_diff_sha256"]))
    ck("builder replay", make(), child)
    ck("diff parent/child pins", (diff["parent_sha256"], diff["input_sha256"]),
       (PARENT_SHA, contract["input_sha256"]))
    source_tables = {t["name"]: t for t in parent["model"]["tables"]}
    child_tables = {t["name"]: t for t in child["model"]["tables"]}
    changed = {n: {"before": source_tables[n], "after": child_tables[n]}
               for n in source_tables if source_tables[n] != child_tables[n]}
    ck("exact table delta", diff["changed"], changed)
    ck("only bridge and description changed", sorted(changed), ["ProblemDescription", "RBDBridge"])
    ck("bridge slot row", rows(child, "RBDBridge")[0][2:7],
       [f"POS-{MAPPING[s]}" for s in ("UL", "LL", "BR", "UR", "LR")])
    ck("B bridge first leaves direct routes", live_paths({"B"}), [("UL", "UR"), ("LL", "LR")])
    ck("A later leaves upper direct route", live_paths({"B", "A"}), [("UL", "UR")])

    run = HERE / "runs" / RUN_ID
    inv, closure, steps, rt = (read(run / n) for n in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
       (RUN_ID, "brfirst", "G07.var03", RUN_ID))
    ck("session-zero SSH and preserved GUI", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
                                              inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("prelife option restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
    ck("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    source_paths = {"input": HERE / "brfirst-input.json", "parent": PARENT,
                    "parent_closure": PARENT_RUN / "closure.json", "comparator": CONTROL,
                    "comparator_closure": CONTROL_RUN / "closure.json", "contract": HERE / "contract.json",
                    "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
                    "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
                    "runner": HERE / "run_native_ssh.ps1"}
    for name, path in source_paths.items():
        ck(f"source seal {name}", closure["source_hashes_before"][name], sha(path))
    ck("installed source seals", tuple(closure["source_hashes_before"][n] for n in ("exe", "manual", "dictionary")),
       tuple(contract["source"][n + "_sha256"] for n in ("exe", "manual", "dictionary")))
    ck("invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
    ck("native outcome", (closure["error"], closure["native_outcome"], closure["conversion"]["errors"],
                          closure["conversion"]["warning_codes"], closure["conversion"]["notes"]),
       (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
    ck("five native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("13 raw files", len(closure["raw"]), 13)
    for name, seal in closure["raw"].items():
        path = run / name
        ck(f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
    ck("roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
       (True, [], contract["input_sha256"]))
    authored, exported = populated(child), populated(native_json(run / "roundtrip-raw.json"))
    ck("22 populated tables", len(authored), 22)
    for name, value in authored.items():
        ck(f"native table {name}", exported.get(name), value)

    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
    ck("conversion counts", marker.groups() if marker else None, ("0", "1", "0"))
    ck("reviewed warning", re.findall(r"\(warning #(\d+)\)", runlog), ["108"])
    ck("no converter error", re.findall(r"\(error #(\d+)\)", runlog), [])
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    control_log = (CONTROL_RUN / "model.log").read_text(encoding="utf-8-sig")
    ck("matched B/A timeline", failure_events(log), [
        (8.62763, "noncritical", [("FM-POS-B", "POS-B")]),
        (16.7498, "noncritical", [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")])])
    ck("allbroken comparator A critical", failure_events(parent_log)[1][1], "critical")
    ck("bridge-second comparator A noncritical", failure_events(control_log)[1][1], "noncritical")
    ck("same matched failure times", [[e[0] for e in failure_events(l)] for l in (log, parent_log, control_log)],
       [[8.62763, 16.7498]] * 3)
    ck("mission starts and succeeds", ("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log,
                                       "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log,
                                       log.count(" mission aborted:")), (True, True, 0))
    ck("two CM completions", re.findall(r"^Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed$", log, re.M),
       [("34.5", "0"), ("34.5", "1")])
    report = native_json(run / "report-raw.json")
    summary, system, stock = (report_rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("report tables", {t["name"] for t in report["report"]["tables"]},
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("replication/horizon/success", (summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"], summary[0]["MSUF"]),
       (1, 0, 36, 1))
    ck("72 aligned bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
       ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
    ck("two failures/repairs", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (2, 2))
    ck("failure and repair bins", ([r["STINT"] for r in system if r["NFAIL"]],
                                     [r["STINT"] for r in system if r["NREPT"]]), ([8.5, 16.5], [34.5]))
    ck("half-hour CM occupancy", close(sum(r["SYDT"] or 0 for r in system), 0.5), True)
    ck("no stock movement", all(close(r[k] or 0, 0) for r in stock for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
    ck("terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))
    ck("26 operating hours", close(0.5 * sum(r["NSYMO"] or 0 for r in system), 26), True)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g07-var03-author-native-replay/v1", "case_id": "G07", "variant_id": "G07.var03",
              "run_id": RUN_ID, "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"bridge_first": "B at h8.62763 is BR and noncritical; A at h16.7498 is LL and noncritical; mission succeeds h34",
                              "accepted_allbroken": "same B/A timeline; A critical and mission aborts h16.7498",
                              "accepted_bridge_second": "same B/A timeline; A is BR and noncritical"},
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
