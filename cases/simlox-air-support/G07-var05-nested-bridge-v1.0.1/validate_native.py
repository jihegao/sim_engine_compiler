"""Author replay of G07.var05 nested-series bridge source and native evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, RBID, make, rows
from check_roundtrip import native_json, populated

RUN_ID = "g07-var05-nested-v101-ssh-20261003-01"
PARENT_RUN = HERE.parent / "G07-var03-bridge-failure-v1.0.0" / "runs" / "g07-var03-brfirst-v100-ssh-20261003-01"
DIAG = HERE.parent / "G07-var05-nested-bridge-v1.0.0"
DIAG_RUN = DIAG / "runs" / "g07-var05-nested-v100-ssh-20261003-01"


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
    child, parent = read(HERE / "nested-input.json"), read(PARENT)
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G07", "G07.var05", "1.0.1-candidate"))
    ck("accepted parent source/closure", (sha(PARENT), sha(PARENT_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("rejected predecessor source/closure", (sha(DIAG / "nested-input.json"), sha(DIAG_RUN / "closure.json")),
       (contract["diagnostic_predecessor"]["input_sha256"], contract["diagnostic_predecessor"]["native_closure_sha256"]))
    ck("predecessor diagnostic error", (read(DIAG_RUN / "closure.json")["native_outcome"],
                                        read(DIAG_RUN / "closure.json")["conversion"]["error_codes"]),
       ("converter_error_requires_review", ["462"]))
    ck("frozen child/diff", (sha(HERE / "nested-input.json"), sha(HERE / "exact-diff.json")),
       (contract["input_sha256"], contract["exact_diff_sha256"]))
    ck("builder replay", make(), child)
    ck("diff source/child pins", (diff["parent_sha256"], diff["input_sha256"]), (PARENT_SHA, contract["input_sha256"]))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    changed = {n: {"before": before[n], "after": after[n]} for n in before if before[n] != after[n]}
    ck("exact diff", diff["changed"], changed)
    ck("seven changed tables", sorted(changed), ["MaterielOperationalModes", "MaterielPosition", "MaterielStructure",
                                               "ProblemDescription", "RBDBridge", "RBDSeries", "RBDSeriesStructure"])
    ck("nested bridge slot/mode", (rows(child, "RBDBridge")[0][2:7], rows(child, "RBDBridge")[0][9]),
       (["POS-E", "POS-A", RBID, "POS-C", "POS-D"], None))
    ck("nested series rows", rows(child, "RBDSeriesStructure"),
       [[RBID, "POS-B", "G04-OPS", 1, None], [RBID, "POS-F", "G04-OPS", 1, None]])
    ck("healthy F installed", ([r for r in rows(child, "MaterielStructure") if "POS-F" in r[:2]],
                               [r for r in rows(child, "MaterielOperationalModes") if r[0] == "POS-F"]),
       ([["POS-F", "TEACH-AIR-01", 1, 1.0, None, None], ["TEACH-LRU-01", "POS-F", 1, 1.0, None, None]],
        [["POS-F", "G04-OPS", None, None, 1.0, None]]))
    ck("no F failure mode", all(r[2] != "POS-F" for r in rows(child, "FailureMode")), True)
    ck("failure/mission/control fixed", [rows(child, n) for n in ("FailureMode", "MissionType", "OperationProfile", "Control")],
       [rows(parent, n) for n in ("FailureMode", "MissionType", "OperationProfile", "Control")])

    run = HERE / "runs" / RUN_ID
    inv, closure, steps, rt = (read(run / n) for n in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
       (RUN_ID, "nested", "G07.var05", RUN_ID))
    ck("SSH0/GUI/queue", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
                            inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
    ck("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    source_paths = {"input": HERE / "nested-input.json", "parent": PARENT, "parent_closure": PARENT_RUN / "closure.json",
                    "diagnostic": DIAG / "nested-input.json", "diagnostic_closure": DIAG_RUN / "closure.json",
                    "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
                    "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
                    "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
    for name, path in source_paths.items():
        ck(f"source seal {name}", closure["source_hashes_before"][name], sha(path))
    ck("installed source seals", tuple(closure["source_hashes_before"][n] for n in ("exe", "manual", "dictionary")),
       tuple(contract["source"][n + "_sha256"] for n in ("exe", "manual", "dictionary")))
    ck("invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
    ck("native outcome", (closure["error"], closure["native_outcome"], closure["conversion"]["errors"],
                          closure["conversion"]["warning_codes"], closure["conversion"]["notes"]),
       (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
    ck("five steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("13 raw files", len(closure["raw"]), 13)
    for name, seal in closure["raw"].items():
        path = run / name
        ck(f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
    ck("roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
       (True, [], contract["input_sha256"]))
    authored, exported = populated(child), populated(native_json(run / "roundtrip-raw.json"))
    ck("24 populated tables", len(authored), 24)
    for name, value in authored.items():
        ck(f"native table {name}", exported.get(name), value)

    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
    ck("conversion counts", marker.groups() if marker else None, ("0", "1", "0"))
    ck("reviewed warning", re.findall(r"\(warning #(\d+)\)", runlog), ["108"])
    ck("no converter errors", re.findall(r"\(error #(\d+)\)", runlog), [])
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    ck("byte-identical parent event log", sha(run / "model.log"), sha(PARENT_RUN / "model.log"))
    ck("matched B/A timeline", failure_events(log), [
        (8.62763, "noncritical", [("FM-POS-B", "POS-B")]),
        (16.7498, "noncritical", [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")])])
    ck("mission success/no abort", ("Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log,
                                    log.count(" mission aborted:")), (True, 0))
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
    ck("failure/repair bins", ([r["STINT"] for r in system if r["NFAIL"]],
                               [r["STINT"] for r in system if r["NREPT"]]), ([8.5, 16.5], [34.5]))
    ck("half-hour CM occupancy", close(sum(r["SYDT"] or 0 for r in system), 0.5), True)
    ck("no stock movement", all(close(r[k] or 0, 0) for r in stock for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
    ck("terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))
    ck("26 operating hours", close(0.5 * sum(r["NSYMO"] or 0 for r in system), 26), True)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g07-var05-author-native-replay/v1.0.1", "case_id": "G07", "variant_id": "G07.var05",
              "run_id": RUN_ID, "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"nested": "BR series B+healthy F, B h8.62763 then A h16.7498 NC, event log byte-identical to parent, mission success h34",
                              "rejected_predecessor": "v1.0.0 converter #462 with BROPM supplied; no simulation accepted"},
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
