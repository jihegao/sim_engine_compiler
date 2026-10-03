"""Author replay of the omitted POS-B NCID/QTYNC1 pair."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated

PARENT_RUN = HERE.parent / "G09-var01-mission-rbd-v1.0.0" / "runs" / "g09-var01-mixed-v100-ssh-20261003-01"
SERIES = HERE.parent / "G04-series-active-parallel-v1.0.1"
SERIES_RUN = SERIES / "runs" / "g04-series-v101-ssh-20261002-01"
DIAGNOSTIC = HERE.parent / "G09-var03-noncritical-set-v1.0.0"
DIAGNOSTIC_RUN = DIAGNOSTIC / "runs" / "g09-var03-nc-b1-v100-ssh-20261003-01"
EVENT = re.compile(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+\d+ failures?:\s+Failure Mode: (FM-POS-[AB])", re.M)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def mapped(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def delta(a: dict, b: dict) -> dict:
    return {n: {"before": a.get(n), "after": b.get(n)} for n in b if a.get(n) != b.get(n)}


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None, "want": want if got != want else None})

    contract, diff, parent = (read(p) for p in (HERE / "contract.json", HERE / "exact-diff.json", PARENT))
    child = {arm: read(HERE / f"{arm}-input.json") for arm in ARMS}
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G09", "G09.var03", "1.0.1-candidate"))
    ck("parent source/closure", (sha(PARENT), sha(PARENT_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("series source/closure", (sha(SERIES / "series-input.json"), sha(SERIES_RUN / "closure.json")),
       (contract["series_control"]["input_sha256"], contract["series_control"]["native_closure_sha256"]))
    ck("excluded diagnostic source/closure", (sha(DIAGNOSTIC / "nc-b1-input.json"),
       sha(DIAGNOSTIC_RUN / "closure.json")),
       (contract["excluded_diagnostic"]["input_sha256"], contract["excluded_diagnostic"]["native_closure_sha256"]))
    ck("exact diff seal", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff parent/input pins", (diff["parent_sha256"], diff["input_sha256"]),
       (PARENT_SHA, contract["input_sha256"]))
    ck("builder replay", {arm: make(arm) for arm in ARMS}, child)
    pm = mapped(parent)
    cm = {arm: mapped(child[arm]) for arm in ARMS}
    ck("from-parent exact delta", {arm: delta(pm, cm[arm]) for arm in ARMS}, diff["from_parent"])
    ck("between-arm exact delta", delta(cm[ARMS[0]], cm[ARMS[1]]), diff["between_arms"])
    for arm in ARMS:
        ck(f"input seal {arm}", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"mission modes fixed {arm}", rows(child[arm], "MissionOperationalModes"), rows(parent, "MissionOperationalModes"))
        ck(f"one-leaf series {arm}", rows(child[arm], "RBDSeriesStructure"),
           [["G09-SER-RBD", "POS-A", "G04-OPS", 1, None]])
        for name in ("FailureMode", "MaterielStructure", "CMLocation", "Control", "SystemDeployment",
                     "RBDSeries", "RBDParallel", "RBDParallelStructure", "OperationProfile"):
            ck(f"fixed {name} {arm}", rows(child[arm], name), rows(parent, name))
    ck("system RBID fixed both", [rows(child[a], "MaterielOperationalModes")[-1][2] for a in ARMS],
       ["G09-SER-RBD", "G09-SER-RBD"])
    ck("NCID only in NC arm", [rows(child[a], "MaterielOperationalModes")[-1][3] for a in ARMS],
       [None, "G09-NC-B"])
    ck("NC set member", rows(child[ARMS[1]], "RBDNonCriticalSetItems"),
       [["G09-NC-B", "POS-B", 1, 1.0, None]])

    runlogs: dict[str, str] = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g09-var03-{arm}-v101-ssh-20261003-01"
        inv, closure, steps, rt = (read(run / n) for n in
            ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        ck(f"run identity {arm}", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
           (run.name, arm, "G09.var03", run.name))
        ck(f"SSH0 GUI queue {arm}", (inv["session_id"],
           "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
           inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(f"registry restored {arm}",
           (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
        ck(f"source stable {arm}", closure["source_hashes_before"], closure["source_hashes_after"])
        source_paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT,
            "parent_closure": PARENT_RUN / "closure.json", "series_control": SERIES / "series-input.json",
            "series_control_closure": SERIES_RUN / "closure.json", "diagnostic": DIAGNOSTIC / "nc-b1-input.json",
            "diagnostic_closure": DIAGNOSTIC_RUN / "closure.json", "contract": HERE / "contract.json",
            "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
            "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
            "runner": HERE / "run_native_ssh.ps1"}
        for name, path in source_paths.items():
            ck(f"source seal {arm} {name}", closure["source_hashes_before"][name], sha(path))
        ck(f"installed seals {arm}", tuple(closure["source_hashes_before"][n] for n in
           ("exe", "manual", "dictionary")), tuple(contract["source"][n + "_sha256"] for n in
           ("exe", "manual", "dictionary")))
        ck(f"invocation seal {arm}", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(f"native outcome {arm}", (closure["error"], closure["native_outcome"],
           closure["conversion"]["errors"], closure["conversion"]["warning_codes"],
           closure["conversion"]["notes"]),
           (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
        ck(f"five steps {arm}", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
           [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
        ck(f"13 raw files {arm}", len(closure["raw"]), 13)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"raw {arm} {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
        ck(f"roundtrip {arm}", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(child[arm]), populated(native_json(run / "roundtrip-raw.json"))
        ck(f"populated table count {arm}", len(authored), 25 if arm == ARMS[0] else 27)
        for name, value in authored.items():
            ck(f"native table {arm} {name}", exported.get(name), value)
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
        ck(f"conversion marker {arm}", marker.groups() if marker else None, ("0", "1", "0"))
        ck(f"warning/error codes {arm}", (re.findall(r"\(warning #(\d+)\)", runlog),
           re.findall(r"\(error #(\d+)\)", runlog)), (["108"], []))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        runlogs[arm] = log
        expected = [("8.62763", "critical" if arm == ARMS[0] else "noncritical", "FM-POS-B"),
                    ("20.8222", "noncritical", "FM-POS-B"),
                    ("33.0996", "critical", "FM-POS-A")]
        ck(f"B/B/A event severity {arm}", EVENT.findall(log), expected)
        ck(f"mission starts {arm}", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission starting", log),
           [("8", "BASIC-MISSION"), ("20", "PAR-MISSION"), ("32", "BASIC-MISSION")])
        ck(f"mission aborts {arm}", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission aborted:", log),
           [("8.62763", "BASIC-MISSION"), ("33.0996", "BASIC-MISSION")] if arm == ARMS[0]
           else [("33.0996", "BASIC-MISSION")])
        ck(f"mission successes {arm}", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission success:", log),
           [("22", "PAR-MISSION")] if arm == ARMS[0] else [("10", "BASIC-MISSION"), ("22", "PAR-MISSION")])
        ck(f"CM completions {arm}", re.findall(r"Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed", log),
           (["9.62763", "22.5", "34.0996"] if arm == ARMS[0]
            else ["10.5", "22.5", "34.0996"]))
        report = native_json(run / "report-raw.json")
        summary, system, stock = (report_rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"report tables {arm}", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        ck(f"replication horizon {arm}", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP")), (1, 0, 36))
        ck(f"mission success fraction {arm}", math.isclose(summary[0]["MSUF"],
           1 / 3 if arm == ARMS[0] else 2 / 3, abs_tol=1e-6, rel_tol=0), True)
        ck(f"72 aligned bins {arm}", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        ck(f"failure repair counts {arm}",
           (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (3, 3))
        ck(f"failure bins {arm}", [r["STINT"] for r in system if r["NFAIL"]], [8.5, 20.5, 33.0])
        ck(f"no stock movement {arm}", all(not r[k] for r in stock for k in
           ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(f"terminal ready {arm}", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))
    ck("matched event times and IDs", [(x[0], x[2]) for x in EVENT.findall(runlogs[ARMS[0]])],
       [(x[0], x[2]) for x in EVENT.findall(runlogs[ARMS[1]])])
    ck("excluded diagnostic remained critical", EVENT.findall((DIAGNOSTIC_RUN / "model.log").read_text(encoding="utf-8-sig"))[0][1], "critical")

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g09-var03-author-native-replay/v1", "case_id": "G09", "variant_id": "G09.var03",
              "run_ids": {arm: f"g09-var03-{arm}-v101-ssh-20261003-01" for arm in ARMS},
              "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": "omitted physical B is critical in control, noncritical with NCID/QTYNC1; matched seeded B/B/A times, BASIC h8 succeeds only in NC arm",
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
