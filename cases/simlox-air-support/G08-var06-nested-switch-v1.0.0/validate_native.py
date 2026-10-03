"""Author replay of G08.var06 nested passive B/E tree-leaf switch panel."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, RBID, SCHEMA_DONOR, SCHEMA_DONOR_SHA, make, rows
from check_roundtrip import native_json, populated

PARENT_RUN = HERE.parent / "G08-var03-nbreq-boundary-v1.0.0" / "runs" / "g08-var03-high-v100-ssh-20261003-01"
RUN = {arm: HERE / "runs" / f"g08-var06-{arm}-v100-ssh-20261003-01" for arm in ARMS}
EVENT = re.compile(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now", re.M)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def close(a: float, b: float, tol: float = 1e-5) -> bool:
    return math.isclose(a, b, abs_tol=tol, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None, "want": want if got != want else None})

    contract, diff, parent = read(HERE / "contract.json"), read(HERE / "exact-diff.json"), read(PARENT)
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G08", "G08.var06", "1.0.0-candidate"))
    ck("accepted parent source and closure", (sha(PARENT), sha(PARENT_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("schema donor", sha(SCHEMA_DONOR), SCHEMA_DONOR_SHA)
    ck("frozen exact diff", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff parent", diff["parent_sha256"], PARENT_SHA)
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    ck("accepted parent B critical abort", (EVENT.findall(parent_log)[0],
       re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:", parent_log)),
       (("8.62763", "critical"), ["8.62763"]))
    ck("accepted NBREQ3", rows(parent, "RBDTree")[0][2], 3)
    arm_docs = {}
    expected = {"instant": {"switch_stop": "8.62763", "a_failure": "11.0942", "return": "14.1884",
                            "repair": "14.6884", "failure_bins": [8.5, 11.0]},
                "delay05": {"switch_stop": "9.12763", "a_failure": "11.5942", "return": "15.1884",
                            "repair": "15.6884", "failure_bins": [8.5, 11.5]}}
    for arm, delay in ARMS.items():
        child = read(HERE / f"{arm}-input.json")
        arm_docs[arm] = child
        ck(f"{arm} frozen input", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"{arm} builder replay", make(arm), child)
        ck(f"{arm} diff input seal", diff["arms"][arm]["input_sha256"], contract["input_sha256"][arm])
        before, after = ({t["name"]: t for t in d["model"]["tables"]} for d in (parent, child))
        changed = {n: {"before": before.get(n), "after": after.get(n)} for n in after if before.get(n) != after.get(n)}
        ck(f"{arm} exact seven-table change", changed, diff["arms"][arm]["changed"])
        ck(f"{arm} seven changed tables", sorted(changed), sorted(("ProblemDescription", "MaterielPosition",
           "MaterielStructure", "MaterielOperationalModes", "RBDParallel", "RBDParallelStructure", "RBDTreeStructure")))
        ck(f"{arm} physical failure, tree and mission fixed",
           [rows(child, n) for n in ("FailureMode", "RBDTree", "MissionType", "OperationProfile", "Control")],
           [rows(parent, n) for n in ("FailureMode", "RBDTree", "MissionType", "OperationProfile", "Control")])
        ck(f"{arm} nested passive definition", rows(child, "RBDParallel"),
           [[RBID, "B active and E passive within tree leaf", 1, 1, delay, "N", None]])
        ck(f"{arm} nested priority links", rows(child, "RBDParallelStructure"),
           [[RBID, "POS-B", "G04-OPS", 1, 1, None], [RBID, "POS-E", "G04-OPS", 1, 2, None]])
        ck(f"{arm} tree nested first leaf", rows(child, "RBDTreeStructure"),
           [["G08-TREE", "POS-A", RBID, "G04-OPS", None, 1, None],
            ["G08-TREE", "POS-A", "POS-C", "G04-OPS", "G04-OPS", 1, None],
            ["G08-TREE", "POS-A", "POS-D", "G04-OPS", "G04-OPS", 1, None]])
        ck(f"{arm} healthy E has no failure mode", "POS-E" in [r[2] for r in rows(child, "FailureMode")], False)

        run = RUN[arm]
        inv, closure, steps, rt = (read(run / name) for name in
                                    ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        ck(f"{arm} run identity", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
           (run.name, arm, "G08.var06", run.name))
        ck(f"{arm} SSH0 GUI queue",
           (inv["session_id"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
            inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(f"{arm} registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]),
           ("NO", "NO"))
        ck(f"{arm} source stable", closure["source_hashes_before"], closure["source_hashes_after"])
        source_paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT,
                        "parent_closure": PARENT_RUN / "closure.json", "schema_donor": SCHEMA_DONOR,
                        "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
                        "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
                        "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
        for name, path in source_paths.items():
            ck(f"{arm} source seal {name}", closure["source_hashes_before"][name], sha(path))
        ck(f"{arm} installed seals", tuple(closure["source_hashes_before"][n] for n in
           ("exe", "manual", "dictionary")), tuple(contract["source"][n + "_sha256"] for n in
           ("exe", "manual", "dictionary")))
        ck(f"{arm} invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(f"{arm} native outcome",
           (closure["error"], closure["native_outcome"], closure["conversion"]["errors"],
            closure["conversion"]["warning_codes"], closure["conversion"]["notes"]),
           (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
        ck(f"{arm} five steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
           [(n, "completed", 0, True) for n in
            ("import", "export", "calc", "jsonreport", "check_import_export")])
        ck(f"{arm} 13 raw files", len(closure["raw"]), 13)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
        ck(f"{arm} roundtrip", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(child), populated(native_json(run / "roundtrip-raw.json"))
        ck(f"{arm} 25 populated tables", len(authored), 25)
        for name, value in authored.items():
            ck(f"{arm} native table {name}", exported.get(name), value)

        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
        ck(f"{arm} conversion marker", marker.groups() if marker else None, ("0", "1", "0"))
        ck(f"{arm} warning/error codes", (re.findall(r"\(warning #(\d+)\)", runlog),
           re.findall(r"\(error #(\d+)\)", runlog)), (["108"], []))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        switch = re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,0><G08-BE-PASSIVE \[POS-B -> POS-E\]>\. switch over started\. Will be finished at ([\d.]+)\.", log)
        stop = re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,0><G08-BE-PASSIVE \[POS-B -> POS-E\]>\. Switch over stopped\.", log)
        ck(f"{arm} explicit nested switch start/end", (switch, stop),
           ([("8.62763", expected[arm]["switch_stop"])], [expected[arm]["switch_stop"]]))
        ck(f"{arm} B then A severity", EVENT.findall(log),
           [("8.62763", "noncritical"), (expected[arm]["a_failure"], "critical")])
        ck(f"{arm} failure identities", (log.count("Failure Mode: FM-POS-B on materiel:"),
           "Failure Mode: FM-POS-A on materiel:" in log),
           (4, True))
        ck(f"{arm} mission abort", re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:", log),
           [expected[arm]["a_failure"]])
        ck(f"{arm} aborted return", re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:", log),
           [expected[arm]["return"]])
        ck(f"{arm} direct CM completion", re.findall(r"Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed", log),
           [expected[arm]["repair"]] * 2)
        ck(f"{arm} no mission success", " mission success:" in log, False)

        report = native_json(run / "report-raw.json")
        summary, system, stock = (report_rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm} report tables", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        ck(f"{arm} replication horizon success", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP", "MSUF")),
           (1, 0, 36, 0))
        ck(f"{arm} 72 aligned bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        ck(f"{arm} failure repair counts", (sum(r["NFAIL"] or 0 for r in system),
           sum(r["NREPT"] or 0 for r in system)), (2, 2))
        ck(f"{arm} failure bins", [r["STINT"] for r in system if r["NFAIL"]], expected[arm]["failure_bins"])
        sw = [(r["STINT"], r["NSYSW"]) for r in system if r["NSYSW"]]
        ck(f"{arm} switching occupancy bins", [x[0] for x in sw], [] if arm == "instant" else [8.5, 9.0])
        ck(f"{arm} switching occupancy hours", close(sum(x[1] for x in sw) * 0.5, delay), True)
        ck(f"{arm} no stock movement", all(not r[k] for r in stock for k in
           ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(f"{arm} terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"], system[-1]["NSYSW"]),
           (1, 0, 0, 0))

    instant, delayed = (arm_docs[x] for x in ("instant", "delay05"))
    pair = {a["name"] for a, b in zip(instant["model"]["tables"], delayed["model"]["tables"], strict=True) if a != b}
    ck("only TSWOV and description vary between nested arms", pair, {"ProblemDescription", "RBDParallel"})
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g08-var06-author-native-replay/v1", "case_id": "G08", "variant_id": "G08.var06",
              "run_ids": [RUN[a].name for a in ARMS], "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed), "failed": failed,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": "parent B h8.62763 critical/abort; both nested arms B h8.62763 noncritical and explicit B->E switch; 0.5h delay occupies NSYSW bins h8.5 and h9; later A critical/abort h11.0942 versus h11.5942",
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
