"""Author replay of the frozen G09.var06 NC-set usage pair."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated
from describe_diff import delta, mapped

PARENT_RUN = HERE.parent / "G09-var03-default-noncritical-v1.0.1" / "runs" / "g09-var03-omitted-nc-b1-v101-ssh-20261003-01"
EVENT = re.compile(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+\d+ failures?:\s+Failure Mode: (FM-POS-[AB])", re.M)
EXPECTED = {
    "ncuse0": {"events": [("21.5663", "noncritical", "FM-POS-B")],
               "cm": ["22.5"], "fail_bins": [21.5], "repair_bins": [22.5]},
    "ncuse1": {"events": [("8.94145", "noncritical", "FM-POS-B"),
                          ("21.2333", "noncritical", "FM-POS-B"),
                          ("33.6494", "noncritical", "FM-POS-B")],
               "cm": ["10.5", "22.5", "34.5"], "fail_bins": [8.5, 21.0, 33.5],
               "repair_bins": [10.5, 22.5, 34.5]},
}


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
                       "got": got if got != want else None,
                       "want": want if got != want else None})

    contract, diff, parent = (read(p) for p in (HERE / "contract.json", HERE / "exact-diff.json", PARENT))
    docs = {a: read(HERE / f"{a}-input.json") for a in ARMS}
    ck("identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G09", "G09.var06", "1.0.0-candidate"))
    ck("parent input/closure", (sha(PARENT), sha(PARENT_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("diff seal/pins", (sha(HERE / "exact-diff.json"), diff["parent_sha256"], diff["input_sha256"]),
       (contract["exact_diff_sha256"], PARENT_SHA, contract["input_sha256"]))
    ck("builder replay", {a: make(a) for a in ARMS}, docs)
    pm, cm = mapped(parent), {a: mapped(docs[a]) for a in ARMS}
    ck("parent exact delta", {a: delta(pm, cm[a]) for a in ARMS}, diff["from_parent"])
    ck("within-pair exact delta", delta(cm["ncuse1"], cm["ncuse0"]), diff["from_ncuse1"])
    for arm, usage in ARMS.items():
        ck(f"input seal {arm}", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"NC item {arm}", rows(docs[arm], "RBDNonCriticalSetItems"),
           [["G09-NC-B", "POS-B", 1, usage, None]])
        ck(f"BASIC NC selection {arm}", rows(docs[arm], "MaterielOperationalModes")[-1],
           ["TEACH-AIR-01", "G09-SER-OPS", "G09-SER-RBD", "G09-NC-B", 1.0, None])
        ck(f"common failure rates {arm}",
           [(r[0], r[2], r[3], r[4]) for r in rows(docs[arm], "FailureMode")],
           [("FM-POS-A", "POS-A", 1e-9, "OPHOURS"),
            ("FM-POS-B", "POS-B", 600000.0, "OPHOURS")])
        for name in ("MaterielStructure", "MissionOperationalModes", "OperationProfile", "Control",
                     "RBDParallelStructure", "RBDSeriesStructure", "CMLocation", "SystemDeployment"):
            ck(f"parent table fixed {arm} {name}", rows(docs[arm], name), rows(parent, name))

        run = HERE / "runs" / f"g09-var06-{arm}-v100-ssh-20261003-01"
        inv, closure, steps, rt = (read(run / n) for n in
                                   ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        ck(f"run identity {arm}", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
           (run.name, arm, "G09.var06", run.name))
        ck(f"SSH0 GUI queue {arm}",
           (inv["session_id"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
            inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(f"registry restored {arm}",
           (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
        ck(f"stable source {arm}", closure["source_hashes_before"], closure["source_hashes_after"])
        paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT,
                 "parent_closure": PARENT_RUN / "closure.json", "contract": HERE / "contract.json",
                 "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
                 "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
                 "runner": HERE / "run_native_ssh.ps1"}
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
        ck(f"27 populated tables {arm}", len(authored), 27)
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
        ck(f"events {arm}", EVENT.findall(log), exp["events"])
        ck(f"starts {arm}",
           re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission starting", log),
           [("8", "BASIC-MISSION"), ("20", "PAR-MISSION"), ("32", "BASIC-MISSION")])
        ck(f"no aborts {arm}", re.findall(r"mission aborted:", log), [])
        ck(f"successes {arm}",
           re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission success:", log),
           [("10", "BASIC-MISSION"), ("22", "PAR-MISSION"), ("34", "BASIC-MISSION")])
        ck(f"direct CM {arm}",
           re.findall(r"Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed", log),
           exp["cm"])
        report = native_json(run / "report-raw.json")
        ck(f"report tables {arm}", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        summary, system, stock = (report_rows(report, n) for n in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"report horizon {arm}", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP")),
           (1, 0, 36))
        ck(f"MSUF {arm}", math.isclose(summary[0]["MSUF"], 1.0, rel_tol=0, abs_tol=1e-6), True)
        ck(f"72 aligned bins {arm}", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        ck(f"failure/repair counts {arm}",
           (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)),
           (len(exp["events"]), len(exp["cm"])))
        ck(f"failure bins {arm}", [r["STINT"] for r in system if r["NFAIL"]], exp["fail_bins"])
        ck(f"repair bins {arm}", [r["STINT"] for r in system if r["NREPT"]], exp["repair_bins"])
        ck(f"no stock movement {arm}", all(not r[k] for r in stock for k in
           ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(f"terminal ready {arm}",
           tuple(system[-1][k] for k in ("NSYRY", "NSYRP", "NSYMO")), (1, 0, 0))
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g09-var06-author-native-replay/v1", "case_id": "G09",
              "variant_id": "G09.var06",
              "run_ids": {a: f"g09-var06-{a}-v100-ssh-20261003-01" for a in ARMS},
              "passed": not failed, "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failed": failed,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": "NC-set USERT0 has no BASIC B fault; USERT1 has noncritical BASIC B faults h8.94145/h33.6494; all missions succeed.",
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
