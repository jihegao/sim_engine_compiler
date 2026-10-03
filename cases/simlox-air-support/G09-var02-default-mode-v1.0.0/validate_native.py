"""Author replay for omitted PAR mission mode and native default-series behavior."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated

RUN = HERE / "runs" / "g09-var02-default-v100-ssh-20261003-01"
PARENT_RUN = HERE.parent / "G09-var01-mission-rbd-v1.0.0" / "runs" / "g09-var01-mixed-v100-ssh-20261003-01"
SERIES = HERE.parent / "G04-series-active-parallel-v1.0.1"
SERIES_RUN = SERIES / "runs" / "g04-series-v101-ssh-20261002-01"
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

    contract, diff, parent, child = (read(p) for p in
        (HERE / "contract.json", HERE / "exact-diff.json", PARENT, HERE / "default-input.json"))
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G09", "G09.var02", "1.0.0-candidate"))
    ck("accepted parent source and closure", (sha(PARENT), sha(PARENT_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("accepted series source and closure", (sha(SERIES / "series-input.json"), sha(SERIES_RUN / "closure.json")),
       (contract["series_control"]["input_sha256"], contract["series_control"]["native_closure_sha256"]))
    ck("frozen input and diff", (sha(HERE / "default-input.json"), sha(HERE / "exact-diff.json")),
       (contract["input_sha256"], contract["exact_diff_sha256"]))
    ck("builder replay", make(), child)
    ck("diff seals", (diff["parent_sha256"], diff["input_sha256"]),
       (PARENT_SHA, contract["input_sha256"]))
    before, after = ({t["name"]: t for t in d["model"]["tables"]} for d in (parent, child))
    changed = {n: {"before": before.get(n), "after": after.get(n)} for n in after if before.get(n) != after.get(n)}
    ck("exact two-table delta", changed, diff["changed"])
    ck("two changed tables", sorted(changed), ["MissionOperationalModes", "ProblemDescription"])
    ck("only BASIC explicitly mapped", rows(child, "MissionOperationalModes"),
       [["BASIC-MISSION", "TEACH-AIR-01", "G09-SER-OPS", None]])
    ck("schedule fixed", rows(child, "OperationProfile"), rows(parent, "OperationProfile"))
    for name in ("FailureMode", "MaterielStructure", "CMLocation", "Control", "SystemDeployment",
                 "RBDSeries", "RBDSeriesStructure", "RBDParallel", "RBDParallelStructure",
                 "MaterielOperationalModes", "MissionType"):
        ck(f"fixed table {name}", rows(child, name), rows(parent, name))

    inv, closure, steps, rt = (read(RUN / name) for name in
                              ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
       (RUN.name, "default", "G09.var02", RUN.name))
    ck("SSH0 GUI queue", (inv["session_id"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
       inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
    ck("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    source_paths = {"input": HERE / "default-input.json", "parent": PARENT,
        "parent_closure": PARENT_RUN / "closure.json", "series_control": SERIES / "series-input.json",
        "series_control_closure": SERIES_RUN / "closure.json", "contract": HERE / "contract.json",
        "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
        "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
        "runner": HERE / "run_native_ssh.ps1"}
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
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    series_log = (SERIES_RUN / "model.log").read_text(encoding="utf-8-sig")
    events = EVENT.findall(log)
    ck("default B/B/A criticality", events,
       [("8.62763", "critical", "FM-POS-B"), ("20.8222", "critical", "FM-POS-B"),
        ("33.0996", "critical", "FM-POS-A")])
    ck("parent matched fault times/identities", [(x[0], x[2]) for x in events],
       [(x[0], x[2]) for x in EVENT.findall(parent_log)])
    ck("parent PAR h20 noncritical", EVENT.findall(parent_log)[1][1], "noncritical")
    ck("series control fault severities", events, EVENT.findall(series_log))
    ck("mission starts", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission starting", log),
       [("8", "BASIC-MISSION"), ("20", "PAR-MISSION"), ("32", "BASIC-MISSION")])
    ck("three mission aborts", re.findall(r"Time: ([\d.]+) <([A-Z-]+),TEACH-UNIT,0,0,\d+> mission aborted:", log),
       [("8.62763", "BASIC-MISSION"), ("20.8222", "PAR-MISSION"), ("33.0996", "BASIC-MISSION")])
    ck("no mission success", re.findall(r"mission success:", log), [])
    ck("parent PAR success", re.findall(r"Time: ([\d.]+) <PAR-MISSION,TEACH-UNIT,0,0,\d+> mission success:", parent_log), ["22"])
    ck("three direct CM completions", re.findall(r"Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed", log),
       ["9.62763", "21.8222", "34.0996"])

    report = native_json(RUN / "report-raw.json")
    summary, system, stock = (report_rows(report, name) for name in
                              ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("report tables", {t["name"] for t in report["report"]["tables"]},
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("replication horizon", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP")), (1, 0, 36))
    ck("no mission succeeds", math.isclose(summary[0]["MSUF"], 0, abs_tol=1e-9, rel_tol=0), True)
    ck("72 aligned bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
       ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
    ck("failure repair counts", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (3, 3))
    ck("failure bins", [r["STINT"] for r in system if r["NFAIL"]], [8.5, 20.5, 33.0])
    ck("no stock movement", all(not r[k] for r in stock for k in
       ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
    ck("terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g09-var02-author-native-replay/v1", "case_id": "G09", "variant_id": "G09.var02",
              "run_id": RUN.name, "passed": not failed, "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failed": failed,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": "same seeded B/B/A times; omitted PAR mapping changes h20 POS-B to critical and abort; BASIC remains explicit series",
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
