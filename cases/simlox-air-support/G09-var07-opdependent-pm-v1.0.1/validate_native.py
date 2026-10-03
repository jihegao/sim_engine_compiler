"""Author replay of the frozen G09.var07 operation-hour PM pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated
from describe_diff import delta, mapped

ROOT = HERE.parent
PARENT_RUN = ROOT / "G09-var04-usert-boundary-v1.0.1" / "runs" / "g09-var04-use1-v101-ssh-20261003-01"
PM_PATTERN = ROOT / "D10-var02-multi-counter-v1.0.0" / "native-input.json"
PM_PATTERN_RUN = ROOT / "D10-var02-multi-counter-v1.0.0" / "runs" / "d10-multicounter-v100-ssh-20261001-01"
DIAGNOSTIC = ROOT / "G09-var07-opdependent-pm-v1.0.0"
EXPECTED = {"syshalf": {"due": [20.5], "start": ["22"], "end": ["23"]},
            "sysfull": {"due": [9.5, 21.5, 33.5],
                        "start": ["10", "22", "34"], "end": ["11", "23", "35"]}}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_rows(doc: dict, name: str) -> list[dict]:
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r, strict=True)) for inst in t["instances"] for r in inst["rows"]]


def main() -> None:
    checks = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None,
                       "want": want if got != want else None})

    contract, diff, parent = (read(p) for p in (HERE / "contract.json", HERE / "exact-diff.json", PARENT))
    docs = {a: read(HERE / f"{a}-input.json") for a in ARMS}
    ck("identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G09", "G09.var07", "1.0.1-candidate"))
    ck("G09 parent pins", (sha(PARENT), sha(PARENT_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("D10 PM pattern pins", (sha(PM_PATTERN), sha(PM_PATTERN_RUN / "closure.json")),
       (contract["accepted_pm_pattern"]["input_sha256"],
        contract["accepted_pm_pattern"]["native_closure_sha256"]))
    ck("diff seal/pins", (sha(HERE / "exact-diff.json"), diff["parent_sha256"], diff["input_sha256"]),
       (contract["exact_diff_sha256"], PARENT_SHA, contract["input_sha256"]))
    ck("builder replay", {a: make(a) for a in ARMS}, docs)
    pm, cm = mapped(parent), {a: mapped(docs[a]) for a in ARMS}
    ck("parent exact deltas", {a: delta(pm, cm[a]) for a in ARMS}, diff["from_parent"])
    ck("within-pair exact delta", delta(cm["sysfull"], cm["syshalf"]), diff["from_sysfull"])
    for arm in ARMS:
        drun = DIAGNOSTIC / "runs" / f"g09-var07-{arm}-v100-ssh-20261003-01"
        ck(f"diagnostic pins {arm}",
           (sha(DIAGNOSTIC / f"{arm}-input.json"), sha(drun / "closure.json")),
           (contract["excluded_diagnostic"]["input_sha256"][arm],
            contract["excluded_diagnostic"]["native_closure_sha256"][arm]))
        ck(f"diagnostic ENPM N {arm}", rows(read(DIAGNOSTIC / f"{arm}-input.json"), "Control")[0][7], "N")
        ck(f"diagnostic no PM {arm}",
           sum(r["NPMS"] or 0 for r in report_rows(native_json(drun / "report-raw.json"), "SystemResults")), 0)
    for arm, usage in ARMS.items():
        ck(f"input seal {arm}", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"ENPM enabled {arm}", rows(docs[arm], "Control")[0][7], "Y")
        ck(f"BASIC system usage {arm}", rows(docs[arm], "MaterielOperationalModes")[3],
           ["TEACH-AIR-01", "G09-SER-OPS", "G09-SER-RBD", None, usage, None])
        ck(f"PAR system fixed {arm}", rows(docs[arm], "MaterielOperationalModes")[0],
           rows(parent, "MaterielOperationalModes")[0])
        ck(f"system OPHOURS PM {arm}", rows(docs[arm], "MaterielPM"),
           [["SYS-OP15", "System operation-hour PM", "TEACH-AIR-01", 1.5, "OPHOURS",
             None, 0.0, 0.0, None, None, None, None, None, None]])
        ck(f"common failure suppression {arm}", [r[3] for r in rows(docs[arm], "FailureMode")],
           [1e-9, 1e-9])
        for name in ("MissionOperationalModes", "OperationProfile", "MaterielStructure",
                     "RBDParallelStructure", "RBDSeriesStructure", "SystemDeployment"):
            ck(f"parent table fixed {arm} {name}", rows(docs[arm], name), rows(parent, name))
        run = HERE / "runs" / f"g09-var07-{arm}-v101-ssh-20261003-01"
        inv, closure, steps, rt = (read(run / n) for n in
                                   ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        ck(f"run identity {arm}", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
           (run.name, arm, "G09.var07", run.name))
        ck(f"SSH0 GUI mutex {arm}",
           (inv["session_id"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
            inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(f"registry restored {arm}",
           (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
        ck(f"stable source {arm}", closure["source_hashes_before"], closure["source_hashes_after"])
        paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT,
                 "parent_closure": PARENT_RUN / "closure.json", "pm_pattern": PM_PATTERN,
                 "pm_closure": PM_PATTERN_RUN / "closure.json", "contract": HERE / "contract.json",
                 "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
                 "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
                 "runner": HERE / "run_native_ssh.ps1"}
        for tag in ARMS:
            paths[f"diagnostic_{'half' if tag == 'syshalf' else 'full'}"] = DIAGNOSTIC / f"{tag}-input.json"
            paths[f"diagnostic_{'half' if tag == 'syshalf' else 'full'}_closure"] = (
                DIAGNOSTIC / "runs" / f"g09-var07-{tag}-v100-ssh-20261003-01" / "closure.json")
        for name, path in paths.items():
            ck(f"source seal {arm} {name}", closure["source_hashes_before"][name], sha(path))
        ck(f"installed source {arm}",
           tuple(closure["source_hashes_before"][n] for n in ("exe", "manual", "dictionary")),
           tuple(contract["source"][n + "_sha256"] for n in ("exe", "manual", "dictionary")))
        ck(f"invocation seal {arm}", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(f"native result {arm}",
           (closure["error"], closure["native_outcome"], closure["conversion"]["errors"],
            closure["conversion"]["warning_codes"], closure["conversion"]["notes"]),
           (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
        ck(f"five steps {arm}",
           [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
           [(n, "completed", 0, True) for n in
            ("import", "export", "calc", "jsonreport", "check_import_export")])
        ck(f"13 raw {arm}", len(closure["raw"]), 13)
        for name, seal in closure["raw"].items():
            ck(f"raw {arm} {name}", ((run / name).stat().st_size, sha(run / name)),
               (seal["bytes"], seal["sha256"]))
        ck(f"roundtrip result {arm}", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(docs[arm]), populated(native_json(run / "roundtrip-raw.json"))
        ck(f"30 populated tables {arm}", len(authored), 30)
        for name, value in authored.items():
            ck(f"roundtrip table {arm} {name}", exported.get(name), value)
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
        ck(f"converter marker {arm}", marker.groups() if marker else None, ("0", "1", "0"))
        ck(f"converter codes {arm}",
           (re.findall(r"\(warning #(\d+)\)", runlog), re.findall(r"\(error #(\d+)\)", runlog)),
           (["108"], []))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        exp = EXPECTED[arm]
        ck(f"no ordinary faults {arm}", re.findall(r"failure mode added", log), [])
        ck(f"mission starts {arm}",
           re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission starting", log),
           [("8", "BASIC-MISSION"), ("20", "PAR-MISSION"), ("32", "BASIC-MISSION")])
        ck(f"mission success {arm}",
           re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission success:", log),
           [("10", "BASIC-MISSION"), ("22", "PAR-MISSION"), ("34", "BASIC-MISSION")])
        ck(f"no aborts {arm}", re.findall(r"mission aborted:", log), [])
        ck(f"PM starts {arm}", re.findall(r"Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started", log), exp["start"])
        ck(f"PM ends {arm}", re.findall(r"Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed", log), exp["end"])
        ck(f"PMID {arm}", re.findall(r"system PM task \d+ on <TEACH-AIR-01,0> PMID: (\S+)", log),
           ["SYS-OP15"] * len(exp["start"]))
        report = native_json(run / "report-raw.json")
        ck(f"report tables {arm}", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        summary, system, stock = (report_rows(report, n) for n in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"report horizon {arm}", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP")),
           (1, 0, 36))
        ck(f"summary successes {arm}", tuple(summary[0][k] for k in ("MTMF", "MSTF", "MSUF", "STMF")),
           (1, 1, 1, 1))
        ck(f"72 aligned bins {arm}", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        ck(f"PM due bins {arm}", [r["STINT"] for r in system if r["NPMS"]], exp["due"])
        ck(f"PM completed bins {arm}", [r["STINT"] for r in system if r["NPMT"]],
           [float(x) for x in exp["end"]])
        ck(f"PM occupancy bins {arm}", [r["STINT"] for r in system if r["NSYPM"]],
           [float(x) + d for x in exp["start"] for d in (0, 0.5)])
        ck(f"no failure/CM {arm}",
           (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (0, 0))
        ck(f"no stock movement {arm}", all(not r[k] for r in stock for k in
           ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(f"terminal ready {arm}",
           tuple(system[-1][k] for k in ("NSYRY", "NSYRP", "NSYMO", "NSYPM")), (1, 0, 0, 0))
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g09-var07-author-native-replay/v1", "case_id": "G09",
              "variant_id": "G09.var07", "run_ids": {a: f"g09-var07-{a}-v101-ssh-20261003-01" for a in ARMS},
              "passed": not failed, "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failed": failed,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": "Full BASIC USERT1 first PM h10; half BASIC USERT0.5 first PM h22; three versus one PM tasks, all missions succeed.",
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
