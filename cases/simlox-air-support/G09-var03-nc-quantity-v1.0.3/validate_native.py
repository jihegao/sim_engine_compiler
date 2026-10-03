"""Author replay of the two-copy QTYNC1/QTYNC2 BASIC mission pair."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated
from describe_diff import delta, mapped

BASE = HERE.parent / "G09-var03-default-noncritical-v1.0.1"
DIAG = HERE.parent / "G09-var03-nc-quantity-v1.0.2"
EVENT = re.compile(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+\d+ failures?:\s+Failure Mode: (FM-POS-[AB])", re.M)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def main() -> None:
    checks = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None, "want": want if got != want else None})

    contract, diff, parent = (read(x) for x in (HERE / "contract.json", HERE / "exact-diff.json", PARENT))
    docs = {arm: read(HERE / f"{arm}-input.json") for arm in ARMS}
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G09", "G09.var03", "1.0.3-candidate"))
    ck("parent and control pins", (sha(PARENT), sha(BASE / "runs" / "g09-var03-omitted-nc-b1-v101-ssh-20261003-01" / "closure.json"),
        sha(BASE / "omitted-control-input.json"), sha(BASE / "runs" / "g09-var03-omitted-control-v101-ssh-20261003-01" / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"], contract["accepted_control"]["input_sha256"],
        contract["accepted_control"]["native_closure_sha256"]))
    for arm in ARMS:
        d = contract["excluded_diagnostic"]
        ck(f"diagnostic pins {arm}", (sha(DIAG / f"{arm}-input.json"),
           sha(DIAG / "runs" / f"g09-var03-{arm}-v102-ssh-20261003-01" / "closure.json")),
           (d["input_sha256"][arm], d["native_closure_sha256"][arm]))
    ck("diff seal", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff pins", (diff["parent_sha256"], diff["input_sha256"]), (PARENT_SHA, contract["input_sha256"]))
    ck("builder replay", {arm: make(arm) for arm in ARMS}, docs)
    pm, cm = mapped(parent), {arm: mapped(docs[arm]) for arm in ARMS}
    ck("from-parent delta", {arm: delta(pm, cm[arm]) for arm in ARMS}, diff["from_parent"])
    ck("between-arm delta", delta(cm["qty1"], cm["qty2"]), diff["between_arms"])
    for arm in ARMS:
        ck(f"input seal {arm}", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"physical B QTYPM2 {arm}", rows(docs[arm], "MaterielStructure")[1][2], 2)
        ck(f"NCID set {arm}", rows(docs[arm], "MaterielOperationalModes")[-1][3], "G09-NC-B")
        ck(f"NC QTYNC {arm}", rows(docs[arm], "RBDNonCriticalSetItems"),
           [["G09-NC-B", "POS-B", 1 if arm == "qty1" else 2, 1.0, None]])
        ck(f"all BASIC {arm}", [(r[1], r[2]) for r in rows(docs[arm], "OperationProfile")],
           [("BASIC-MISSION", 8.0), ("BASIC-MISSION", 20.0), ("BASIC-MISSION", 32.0)])
        for table in ("FailureMode", "CMLocation", "Control", "SystemDeployment", "RBDSeries", "RBDParallel",
                      "RBDSeriesStructure", "RBDParallelStructure", "MaterielOperationalModes", "MissionOperationalModes"):
            ck(f"parent fixed {arm} {table}", rows(docs[arm], table), rows(parent, table))
    logs = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g09-var03-{arm}-v103-ssh-20261003-01"
        inv, closure, steps, rt = (read(run / n) for n in
           ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        ck(f"run identity {arm}", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
           (run.name, arm, "G09.var03", run.name))
        ck(f"SSH0 GUI mutex {arm}", (inv["session_id"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
           inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(f"registry restored {arm}", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
        ck(f"source stable {arm}", closure["source_hashes_before"], closure["source_hashes_after"])
        paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT,
          "parent_closure": BASE / "runs" / "g09-var03-omitted-nc-b1-v101-ssh-20261003-01" / "closure.json",
          "control": BASE / "omitted-control-input.json",
          "control_closure": BASE / "runs" / "g09-var03-omitted-control-v101-ssh-20261003-01" / "closure.json",
          "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
          "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
          "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
        for x in ARMS:
            paths[f"diagnostic_{x}"] = DIAG / f"{x}-input.json"
            paths[f"diagnostic_{x}_closure"] = DIAG / "runs" / f"g09-var03-{x}-v102-ssh-20261003-01" / "closure.json"
        for name, path in paths.items():
            ck(f"source seal {arm} {name}", closure["source_hashes_before"][name], sha(path))
        ck(f"installed seals {arm}", tuple(closure["source_hashes_before"][n] for n in ("exe", "manual", "dictionary")),
           tuple(contract["source"][n + "_sha256"] for n in ("exe", "manual", "dictionary")))
        ck(f"invocation seal {arm}", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(f"native outcome {arm}", (closure["error"], closure["native_outcome"], closure["conversion"]["errors"],
           closure["conversion"]["warning_codes"], closure["conversion"]["notes"]),
           (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
        ck(f"five steps {arm}", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
           [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
        ck(f"13 raw files {arm}", len(closure["raw"]), 13)
        for name, seal in closure["raw"].items():
            ck(f"raw {arm} {name}", ((run / name).stat().st_size, sha(run / name)),
               (seal["bytes"], seal["sha256"]))
        ck(f"roundtrip result {arm}", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(docs[arm]), populated(native_json(run / "roundtrip-raw.json"))
        ck(f"27 populated tables {arm}", len(authored), 27)
        for name, value in authored.items():
            ck(f"roundtrip table {arm} {name}", exported.get(name), value)
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
        ck(f"conversion marker {arm}", marker.groups() if marker else None, ("0", "1", "0"))
        ck(f"diagnostic codes {arm}", (re.findall(r"\(warning #(\d+)\)", runlog), re.findall(r"\(error #(\d+)\)", runlog)),
           (["108"], []))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        logs[arm] = log
        ck(f"B fault severity {arm}", EVENT.findall(log),
           [("8.37658", "noncritical", "FM-POS-B"), ("20.4933", "noncritical", "FM-POS-B"),
            ("21.742", "critical" if arm == "qty1" else "noncritical", "FM-POS-B")])
        ck(f"mission starts {arm}", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission starting", log),
           [("8", "BASIC-MISSION"), ("20", "BASIC-MISSION"), ("32", "BASIC-MISSION")])
        ck(f"mission aborts {arm}", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission aborted:", log),
           [("21.742", "BASIC-MISSION")] if arm == "qty1" else [])
        ck(f"mission successes {arm}", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission success:", log),
           [(t, "BASIC-MISSION") for t in (["10", "34"] if arm == "qty1" else ["10", "22", "34"])])
        ck(f"CM completions {arm}", re.findall(r"Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed", log),
           ["10.5", "22.5", "22.5"])
        report = native_json(run / "report-raw.json")
        summary, system, stock = (report_rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"report tables {arm}", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        ck(f"report horizon {arm}", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP")), (1, 0, 36))
        ck(f"mission success fraction {arm}", math.isclose(summary[0]["MSUF"],
           2 / 3 if arm == "qty1" else 1, rel_tol=0, abs_tol=1e-6), True)
        ck(f"72 aligned bins {arm}", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        ck(f"failure repairs {arm}", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (3, 3))
        ck(f"failure bins {arm}", [r["STINT"] for r in system if r["NFAIL"]], [8, 20, 21.5])
        ck(f"no stock movement {arm}", all(not r[k] for r in stock for k in
           ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(f"terminal ready {arm}", tuple(system[-1][k] for k in ("NSYRY", "NSYRP", "NSYMO")), (1, 0, 0))
    ck("matched B fault times", [(x[0], x[2]) for x in EVENT.findall(logs["qty1"])],
       [(x[0], x[2]) for x in EVENT.findall(logs["qty2"])])
    for arm in ARMS:
        diaglog = (DIAG / "runs" / f"g09-var03-{arm}-v102-ssh-20261003-01" / "model.log").read_text(encoding="utf-8-sig")
        ck(f"diagnostic PAR second B was critical {arm}", EVENT.findall(diaglog)[2][1], "critical")
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g09-var03-author-native-replay/v1", "case_id": "G09", "variant_id": "G09.var03",
      "run_ids": {arm: f"g09-var03-{arm}-v103-ssh-20261003-01" for arm in ARMS},
      "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
      "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
      "observation": "Two installed POS-B copies; matched h20 BASIC second B fault is critical/abort with QTYNC1 and noncritical/success with QTYNC2.",
      "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
