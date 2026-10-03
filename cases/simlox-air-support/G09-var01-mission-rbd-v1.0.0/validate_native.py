"""Author replay of G09.var01 mission-selected series/parallel RBD."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, MODE, PAR_MISSION, PARENT, PARENT_SHA, SCHEMA_DONOR, SCHEMA_DONOR_SHA, SERIES, make, rows
from check_roundtrip import native_json, populated

CONTROL = HERE.parent / "G04-series-active-parallel-v1.0.1" / "runs"
PAR_RUN = CONTROL / "g04-parallel-v101-ssh-20261002-01"
SER_RUN = CONTROL / "g04-series-v101-ssh-20261002-01"
RUN = HERE / "runs" / "g09-var01-mixed-v100-ssh-20261003-01"
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
    checks: list[dict] = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None, "want": want if got != want else None})

    contract, diff, parent = read(HERE / "contract.json"), read(HERE / "exact-diff.json"), read(PARENT)
    child = read(HERE / "mixed-input.json")
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G09", "G09.var01", "1.0.0-candidate"))
    ck("accepted parallel source and closure", (sha(PARENT), sha(PAR_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("accepted series donor and closure", (sha(SCHEMA_DONOR), sha(SER_RUN / "closure.json")),
       (SCHEMA_DONOR_SHA, contract["schema_and_control_donor"]["native_closure_sha256"]))
    ck("frozen input and diff", (sha(HERE / "mixed-input.json"), sha(HERE / "exact-diff.json")),
       (contract["input_sha256"], contract["exact_diff_sha256"]))
    ck("builder replay", make(), child)
    ck("diff seals", (diff["parent_sha256"], diff["input_sha256"]), (PARENT_SHA, contract["input_sha256"]))
    before, after = ({t["name"]: t for t in d["model"]["tables"]} for d in (parent, child))
    changed = {n: {"before": before.get(n), "after": after.get(n)} for n in after if before.get(n) != after.get(n)}
    ck("exact eight-table delta", changed, diff["changed"])
    ck("eight changed tables", sorted(changed), sorted(("ProblemDescription", "MissionType", "OperationProfile",
       "OperationalModes", "MissionOperationalModes", "MaterielOperationalModes", "RBDSeries", "RBDSeriesStructure")))
    ck("physical and control fixed", [rows(child, n) for n in
       ("FailureMode", "MaterielStructure", "CMLocation", "Control", "SystemDeployment")],
       [rows(parent, n) for n in ("FailureMode", "MaterielStructure", "CMLocation", "Control", "SystemDeployment")])
    ck("three mission schedule", [(r[1], r[2]) for r in rows(child, "OperationProfile")],
       [("BASIC-MISSION", 8.0), (PAR_MISSION, 20.0), ("BASIC-MISSION", 32.0)])
    missions = rows(child, "MissionType")
    ck("mission behavior fields identical", missions[0][2:], missions[1][2:])
    ck("two mission-to-system modes", rows(child, "MissionOperationalModes"),
       [["BASIC-MISSION", "TEACH-AIR-01", MODE, None], [PAR_MISSION, "TEACH-AIR-01", "G04-OPS", None]])
    ck("system series mapping", rows(child, "MaterielOperationalModes")[-1],
       ["TEACH-AIR-01", MODE, SERIES, None, 1.0, None])
    ck("series block and leaves", (rows(child, "RBDSeries"), rows(child, "RBDSeriesStructure")),
       ([[SERIES, "Both physical positions required", None]],
        [[SERIES, "POS-A", "G04-OPS", 1, None], [SERIES, "POS-B", "G04-OPS", 1, None]]))
    ck("parallel block unchanged", (rows(child, "RBDParallel"), rows(child, "RBDParallelStructure")),
       (rows(parent, "RBDParallel"), rows(parent, "RBDParallelStructure")))

    inv, closure, steps, rt = (read(RUN / name) for name in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
       (RUN.name, "mixed", "G09.var01", RUN.name))
    ck("SSH0 GUI queue", (inv["session_id"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
       inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
    ck("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    source_paths = {"input": HERE / "mixed-input.json", "parent": PARENT, "parent_closure": PAR_RUN / "closure.json",
                    "schema_donor": SCHEMA_DONOR, "schema_donor_closure": SER_RUN / "closure.json",
                    "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
                    "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
                    "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
    for name, path in source_paths.items():
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
        ck(f"raw {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
    ck("roundtrip", (rt["passed"], rt["differences"], rt["source_sha256"]),
       (True, [], contract["input_sha256"]))
    authored, exported = populated(child), populated(native_json(RUN / "roundtrip-raw.json"))
    ck("25 populated tables", len(authored), 25)
    for name, value in authored.items():
        ck(f"native table {name}", exported.get(name), value)

    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
    ck("conversion marker", marker.groups() if marker else None, ("0", "1", "0"))
    ck("warning/error codes", (re.findall(r"\(warning #(\d+)\)", runlog),
       re.findall(r"\(error #(\d+)\)", runlog)), (["108"], []))
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    series_log = (SER_RUN / "model.log").read_text(encoding="utf-8-sig")
    parallel_log = (PAR_RUN / "model.log").read_text(encoding="utf-8-sig")
    events = EVENT.findall(log)
    ck("mixed B/B/A severity", events,
       [("8.62763", "critical", "FM-POS-B"), ("20.8222", "noncritical", "FM-POS-B"),
        ("33.0996", "critical", "FM-POS-A")])
    ck("matched event time and identities across controls", [(x[0], x[2]) for x in events],
       [(x[0], x[2]) for x in EVENT.findall(series_log)])
    ck("matched parallel event time and identities", [(x[0], x[2]) for x in events],
       [(x[0], x[2]) for x in EVENT.findall(parallel_log)])
    ck("series control criticality", [x[1] for x in EVENT.findall(series_log)], ["critical"] * 3)
    ck("parallel control criticality", [x[1] for x in EVENT.findall(parallel_log)], ["noncritical"] * 3)
    ck("mission type/order starts", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission starting", log),
       [("8", "BASIC-MISSION"), ("20", PAR_MISSION), ("32", "BASIC-MISSION")])
    ck("mission aborts", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission aborted:", log),
       [("8.62763", "BASIC-MISSION"), ("33.0996", "BASIC-MISSION")])
    ck("parallel mission succeeds", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission success:", log),
       [("22", PAR_MISSION)])
    ck("direct CM completions", re.findall(r"Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed", log),
       ["9.62763", "22.5", "34.0996"])

    report = native_json(RUN / "report-raw.json")
    summary, system, stock = (report_rows(report, name) for name in
                              ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("report tables", {t["name"] for t in report["report"]["tables"]},
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("replication horizon", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP")), (1, 0, 36))
    ck("one of three missions succeeds", math.isclose(summary[0]["MSUF"], 1 / 3, abs_tol=1e-6, rel_tol=0), True)
    ck("72 aligned bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
       ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
    ck("failure repair counts", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (3, 3))
    ck("failure bins", [r["STINT"] for r in system if r["NFAIL"]], [8.5, 20.5, 33.0])
    ck("no stock movement", all(not r[k] for r in stock for k in
       ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
    ck("terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g09-var01-author-native-replay/v1", "case_id": "G09", "variant_id": "G09.var01",
              "run_id": RUN.name, "passed": not failed, "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failed": failed,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": "same seeded B/B/A failure times as accepted G04 controls; BASIC series h8/h32 critical-abort, PAR parallel h20 noncritical-success",
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
