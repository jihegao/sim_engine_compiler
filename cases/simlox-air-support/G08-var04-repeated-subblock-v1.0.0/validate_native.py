"""Author replay of G08.var04 aligned physical/tree repeated-C native case."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated

PARENT_RUN = HERE.parent / "G08-var03-nbreq-boundary-v1.0.0" / "runs" / "g08-var03-high-v100-ssh-20261003-01"
COMPARATOR = HERE.parent / "G08-tree-root-panel-v1.0.0" / "runs" / "g08-roota-v100-ssh-20261003-01"
RUN = HERE / "runs" / "g08-var04-repeated-v100-ssh-20261003-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def close(value: object, expected: float, tol: float = 1e-4) -> bool:
    return isinstance(value, (int, float)) and math.isclose(float(value), expected, rel_tol=0, abs_tol=tol)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None, "want": want if got != want else None})

    contract, diff, parent, child = (read(path) for path in
                                    (HERE / "contract.json", HERE / "exact-diff.json", PARENT, HERE / "repeated-input.json"))
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G08", "G08.var04", "1.0.0-candidate"))
    ck("accepted parent source closure", (sha(PARENT), sha(PARENT_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("frozen child diff", (sha(HERE / "repeated-input.json"), sha(HERE / "exact-diff.json")),
       (contract["input_sha256"], contract["exact_diff_sha256"]))
    ck("builder replay", make(), child)
    before, after = ({t["name"]: t for t in d["model"]["tables"]} for d in (parent, child))
    changed = {n: {"before": before[n], "after": after[n]} for n in before if before[n] != after[n]}
    ck("three changed tables", sorted(changed), ["MaterielStructure", "ProblemDescription", "RBDTreeStructure"])
    ck("exact diff rows", (diff["parent_sha256"], diff["input_sha256"], diff["changed"]),
       (PARENT_SHA, contract["input_sha256"], changed))
    ck("NBREQ held at three", (rows(parent, "RBDTree")[0][2], rows(child, "RBDTree")[0][2]), (3, 3))
    ck("physical C quantity", ([r for r in rows(parent, "MaterielStructure") if r[:2] == ["POS-C", "TEACH-AIR-01"]][0][2],
                               [r for r in rows(child, "MaterielStructure") if r[:2] == ["POS-C", "TEACH-AIR-01"]][0][2]),
       (1, 2))
    ck("tree C quantity", (rows(parent, "RBDTreeStructure")[1][5], rows(child, "RBDTreeStructure")[1][5]), (1, 2))
    ck("other tree edges fixed", [rows(child, "RBDTreeStructure")[i] for i in (0, 2)],
       [rows(parent, "RBDTreeStructure")[i] for i in (0, 2)])
    ck("C no failure mode", all(r[2] != "POS-C" for r in rows(child, "FailureMode")), True)
    ck("failure mission control fixed", [rows(child, n) for n in
       ("FailureMode", "MissionType", "OperationProfile", "Control")],
       [rows(parent, n) for n in ("FailureMode", "MissionType", "OperationProfile", "Control")])

    inv, closure, steps, rt = (read(RUN / name) for name in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
       (RUN.name, "repeated", "G08.var04", RUN.name))
    ck("SSH0 GUI queue", (inv["session_id"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
       inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
    ck("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    paths = {"input": HERE / "repeated-input.json", "parent": PARENT,
             "parent_closure": PARENT_RUN / "closure.json", "contract": HERE / "contract.json",
             "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
             "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
             "runner": HERE / "run_native_ssh.ps1"}
    for name, path in paths.items():
        ck(f"source seal {name}", closure["source_hashes_before"][name], sha(path))
    ck("installed seals", tuple(closure["source_hashes_before"][n] for n in
       ("exe", "manual", "dictionary")), tuple(contract["source"][n + "_sha256"] for n in
       ("exe", "manual", "dictionary")))
    ck("invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    ck("native outcome", (closure["error"], closure["native_outcome"], closure["conversion"]["errors"],
       closure["conversion"]["warning_codes"], closure["conversion"]["notes"]),
       (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
    ck("five steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("13 raw files", len(closure["raw"]), 13)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
    ck("roundtrip", (rt["passed"], rt["differences"], rt["source_sha256"]),
       (True, [], contract["input_sha256"]))
    authored, exported = populated(child), populated(native_json(RUN / "roundtrip-raw.json"))
    ck("23 populated tables", len(authored), 23)
    for name, value in authored.items():
        ck(f"native table {name}", exported.get(name), value)
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
    ck("conversion marker", marker.groups() if marker else None, ("0", "1", "0"))
    ck("warning/error codes", (re.findall(r"\(warning #(\d+)\)", runlog),
       re.findall(r"\(error #(\d+)\)", runlog)), (["108"], []))
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    ck("parent B critical abort", ("Time: 8.62763 <TEACH-AIR-01,0> critical CM failure mode added" in parent_log,
       "Time: 8.62763 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in parent_log), (True, True))
    ck("candidate B NC A critical", re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added", log),
       [("8.62763", "noncritical"), ("16.7498", "critical")])
    ck("candidate abort", re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:", log),
       ["16.7498"])
    ck("candidate event log matches accepted NBREQ2", sha(RUN / "model.log"), sha(COMPARATOR / "model.log"))
    ck("two CM completions", len(re.findall(r"^Time: [\d.]+  system CM task \d+ on <TEACH-AIR-01,0> completed$", log, re.M)), 2)
    report = native_json(RUN / "report-raw.json")
    summary, system, stock = (report_rows(report, n) for n in
                              ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("report tables", {t["name"] for t in report["report"]["tables"]},
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("replication horizon no success", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP", "MSUF")),
       (1, 0, 36, 0))
    ck("72 aligned bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
       ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
    ck("two failures and repairs", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (2, 2))
    ck("failure bins", [r["STINT"] for r in system if r["NFAIL"]], [8.5, 16.5])
    ck("no stock movement", all(close(r[k] or 0, 0) for r in stock for k in
       ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
    ck("terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g08-var04-author-native-replay/v1.0.0", "case_id": "G08",
              "variant_id": "G08.var04", "run_id": RUN.name, "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed), "failed": failed,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": "aligned healthy C quantity2 supplies fourth source-defined leaf; B h8.62763 NC versus NBREQ3 parent C/abort; A h16.7498 C/abort",
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
