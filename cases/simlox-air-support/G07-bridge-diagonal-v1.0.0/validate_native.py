"""Author replay of matched bridge-diagonal native runs."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, SCHEMA_DONOR, SCHEMA_DONOR_SHA, make, rows
from check_roundtrip import native_json, populated

IDS = {arm: f"g07-var01-{arm}-v100-ssh-20261003-01" for arm in ARMS}
PARENT_RUN = HERE.parent / "G04-three-branch-threshold-v1.0.0" / "runs" / "g04-kn-one-v100-ssh-20261002-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def report_rows(doc: dict, name: str) -> list[dict]:
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r, strict=True)) for instance in t["instances"] for r in instance["rows"]]


def failure_events(log: str) -> list[tuple]:
    found = []
    for match in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                             r"(.*?)\n(?=Time:|$)", log, re.S):
        modes = re.findall(r"Failure Mode: (FM-POS-[A-Z]) on materiel: <(POS-[A-Z]),0>", match.group(3))
        found.append((float(match.group(1)), match.group(2), modes))
    return found


def close(x: object, y: float, tol: float = 1e-4) -> bool:
    return isinstance(x, (int, float)) and math.isclose(float(x), y, rel_tol=0, abs_tol=tol)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None, "want": want if got != want else None})

    contract, diff, parent = read(HERE / "contract.json"), read(HERE / "exact-diff.json"), read(PARENT)
    ck("contract identity", (contract["case_id"], contract["variant_id"]), ("G07", "G07.var01"))
    ck("parent input seal", sha(PARENT), PARENT_SHA)
    ck("parent closure seal", sha(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"])
    ck("series donor seal", sha(SCHEMA_DONOR), SCHEMA_DONOR_SHA)
    ck("series donor contract", contract["schema_donor"]["input_sha256"], SCHEMA_DONOR_SHA)
    ck("diff seal", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff parent", diff["parent_sha256"], PARENT_SHA)
    source = {}
    for arm in ARMS:
        doc = read(HERE / f"{arm}-input.json")
        source[arm] = doc
        ck(f"{arm} input seal", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"{arm} builder replay", make(arm), doc)
        before, after = tables(parent), tables(doc)
        changes = {name: {"before": before.get(name), "after": after.get(name)}
                   for name in after if before.get(name) != after[name]}
        ck(f"{arm} exact table diff", diff["arms"][arm]["changed"], changes)
        ck(f"{arm} changed tables", sorted(changes), sorted([
            "ProblemDescription", "MaterielPosition", "MaterielStructure", "MaterielOperationalModes",
            "RBDParallel", "RBDParallelStructure", "RBDSeries", "RBDSeriesStructure", "RBDBridge"]))
        ck(f"{arm} parent failure/mission/repair/controls",
           [rows(doc, name) for name in ("FailureMode", "CMLocation", "MissionType", "OperationProfile", "Control")],
           [rows(parent, name) for name in ("FailureMode", "CMLocation", "MissionType", "OperationProfile", "Control")])
        ck(f"{arm} five physical positions", [r[0] for r in rows(doc, "MaterielPosition")], [f"POS-{p}" for p in "ABCDE"])
        ck(f"{arm} five LRU installations", [r[1] for r in rows(doc, "MaterielStructure") if r[0] == "TEACH-LRU-01"],
           [f"POS-{p}" for p in "ABCDE"])
    bridge, routes = source["bridge"], source["routes"]
    ck("paired physical and operational mode rows", [rows(bridge, n) for n in ("MaterielPosition", "MaterielStructure")],
       [rows(routes, n) for n in ("MaterielPosition", "MaterielStructure")])
    ck("paired only topology/description differs",
       [n for n in tables(bridge) if tables(bridge)[n] != tables(routes)[n]],
       ["ProblemDescription", "MaterielOperationalModes", "RBDParallel", "RBDParallelStructure", "RBDSeries", "RBDSeriesStructure", "RBDBridge"])
    ck("bridge five block order", rows(bridge, "RBDBridge")[0][2:7], ["POS-B", "POS-C", "POS-E", "POS-D", "POS-A"])
    ck("bridge five modes", rows(bridge, "RBDBridge")[0][7:12], ["G04-OPS"] * 5)
    ck("control upper/lower routes", [r[1] for r in rows(routes, "RBDSeriesStructure")],
       ["POS-E", "G07-PAR-ROUTES", "POS-B", "POS-D", "POS-C", "POS-A"])

    observed = {}
    for arm in ARMS:
        run = HERE / "runs" / IDS[arm]
        inv, closure, steps, rt = (read(run / name) for name in
                                   ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        p = arm + ": "
        ck(p + "run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
           (IDS[arm], arm, IDS[arm], arm))
        ck(p + "session-zero SSH", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
           (0, True, "session0_ssh_cli"))
        ck(p + "GUI/queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(p + "registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
        ck(p + "sources unchanged", closure["source_hashes_before"], closure["source_hashes_after"])
        source_paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT,
                        "parent_closure": PARENT_RUN / "closure.json", "schema_donor": SCHEMA_DONOR,
                        "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
                        "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
                        "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
        for name, path in source_paths.items():
            ck(p + f"source seal {name}", closure["source_hashes_before"][name], sha(path))
        ck(p + "installed source seals", tuple(closure["source_hashes_before"][n] for n in ("exe", "manual", "dictionary")),
           tuple(contract["source"][n + "_sha256"] for n in ("exe", "manual", "dictionary")))
        ck(p + "invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(p + "accepted native outcome", (closure["error"], closure["native_outcome"], closure["conversion"]["errors"],
                                           closure["conversion"]["warning_codes"], closure["conversion"]["notes"]),
           (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
        ck(p + "five native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
           [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
        ck(p + "13 raw files", len(closure["raw"]), 13)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(p + f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
        ck(p + "roundtrip", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(source[arm]), populated(native_json(run / "roundtrip-raw.json"))
        ck(p + "populated tables", len(authored), 22 if arm == "bridge" else 25)
        for name, value in authored.items():
            ck(p + f"native table {name}", exported.get(name), value)
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
        ck(p + "conversion counts", marker.groups() if marker else None, ("0", "1", "0"))
        ck(p + "warning codes", re.findall(r"\(warning #(\d+)\)", runlog), ["108"])
        ck(p + "no converter errors", re.findall(r"\(error #(\d+)\)", runlog), [])
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        ev = failure_events(log)
        observed[arm] = ev
        ck(p + "failure timeline", ev, [
            (8.62763, "noncritical", [("FM-POS-B", "POS-B")]),
            (16.7498, "noncritical" if arm == "bridge" else "critical",
             [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")]),
        ])
        ck(p + "exactly two failures", log.count("CM failure mode added"), 2)
        ck(p + "mission starts", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log, True)
        if arm == "bridge":
            ck(p + "success/no abort", ("Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log,
                                         log.count(" mission aborted:")), (True, 0))
            repair_time = "34.5"
        else:
            ck(p + "critical abort/return", ("Time: 16.7498 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in log,
                                               "Time: 23.2498 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:" in log,
                                               log.count(" mission success:")), (True, True, 0))
            repair_time = "23.7498"
        ck(p + "two direct CM tasks", re.findall(r"^Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed$", log, re.M),
           [(repair_time, "0"), (repair_time, "1")])
        report = native_json(run / "report-raw.json")
        summary, system, stock = (report_rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(p + "report tables", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        ck(p + "one replication/horizon", (summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"]), (1, 0, 36))
        ck(p + "mission success fraction", summary[0]["MSUF"], 1 if arm == "bridge" else 0)
        ck(p + "72 aligned System/Stock bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        ck(p + "two failures/repairs", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (2, 2))
        ck(p + "failure bins", [r["STINT"] for r in system if r["NFAIL"]], [8.5, 16.5])
        ck(p + "repair bin", [r["STINT"] for r in system if r["NREPT"]], [34.5 if arm == "bridge" else 23.5])
        ck(p + "half-hour repair occupancy", close(sum(r["SYDT"] or 0 for r in system), 0.5), True)
        ck(p + "no stock movement", all(close(r[k] or 0, 0) for r in stock for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(p + "terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))
        ck(p + "operating exposure", close(0.5 * sum(r["NSYMO"] or 0 for r in system),
                                            26 if arm == "bridge" else 15.2498), True)
    ck("matched failure identities and times", [(e[0], e[2][-1]) for e in observed["bridge"]],
       [(e[0], e[2][-1]) for e in observed["routes"]])
    ck("opposite second-failure criticality", (observed["bridge"][1][1], observed["routes"][1][1]),
       ("noncritical", "critical"))
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g07-var01-author-native-replay/v1", "case_id": "G07", "variant_id": "G07.var01",
              "run_ids": IDS, "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"matched": "B h8.62763 then A h16.7498; B NC both",
                              "bridge": "A NC, only C+E+D diagonal remains by source-bound topology, success h34",
                              "routes": "A critical, ordinary routes broken, abort h16.7498, return h23.2498"},
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
