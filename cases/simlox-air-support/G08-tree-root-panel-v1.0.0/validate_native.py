"""Replay frozen G08 tree sources and both guarded native runs."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, RBID, make, rows
from check_roundtrip import native_json, populated

PARENT_RUN = HERE.parent / "G04-three-branch-threshold-v1.0.0" / "runs" / "g04-kn-two-v100-ssh-20261002-01"
RUN = {arm: HERE / "runs" / f"g08-{arm}-v100-ssh-20261003-01" for arm in ARMS}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def failure_events(log: str) -> list[tuple[float, str, str]]:
    found = []
    for event in re.finditer(
        r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
        r"(.*?)(?=\nTime:|\n<TEACH-AIR-01,0> aborts|$)", log, re.S
    ):
        modes = re.findall(r"Failure Mode: (FM-POS-[A-Z])", event.group(3))
        found.append((float(event.group(1)), event.group(2), modes[-1]))
    return found


def close(value: object, expected: float, tol: float = 1e-4) -> bool:
    return isinstance(value, (float, int)) and math.isclose(float(value), expected, abs_tol=tol, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None, "want": want if got != want else None})

    contract, diff, parent = read(HERE / "contract.json"), read(HERE / "exact-diff.json"), read(PARENT)
    ck("contract identity", (contract["case_id"], contract["variant_ids"], contract["version"]),
       ("G08", ["G08.var01", "G08.var02"], "1.0.0-candidate"))
    ck("accepted parent source and closure", (sha(PARENT), sha(PARENT_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("frozen diff", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff parent", diff["parent_sha256"], PARENT_SHA)
    ck("arms", sorted(diff["arms"]), sorted(ARMS))
    for arm in ARMS:
        child = read(HERE / f"{arm}-input.json")
        ck(f"{arm} frozen input", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"{arm} builder replay", make(arm), child)
        ck(f"{arm} diff input pin", diff["arms"][arm]["input_sha256"], contract["input_sha256"][arm])
        before, after = ({t["name"]: t for t in d["model"]["tables"]} for d in (parent, child))
        changed = {name: {"before": before.get(name), "after": after.get(name)}
                   for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)}
        ck(f"{arm} exact eight-table diff", diff["arms"][arm]["changed"], changed)
        ck(f"{arm} changed table names", sorted(changed), sorted(("ProblemDescription", "MaterielPosition",
           "MaterielStructure", "MaterielOperationalModes", "RBDParallel", "RBDParallelStructure",
           "RBDTree", "RBDTreeStructure")))
        root = "POS-A" if arm == "roota" else "POS-B"
        leaves = [f"POS-{letter}" for letter in "ABCD" if f"POS-{letter}" != root]
        ck(f"{arm} tree definition", rows(child, "RBDTree"),
           [[RBID, f"Three leaf paths through common root {root}", 2, None]])
        ck(f"{arm} root leaf edges", rows(child, "RBDTreeStructure"),
           [[RBID, root, leaf, "G04-OPS", "G04-OPS", 1, None] for leaf in leaves])
        ck(f"{arm} failure mission control fixed",
           [rows(child, n) for n in ("FailureMode", "MissionType", "OperationProfile", "Control")],
           [rows(parent, n) for n in ("FailureMode", "MissionType", "OperationProfile", "Control")])
        ck(f"{arm} D has no failure", all(r[2] != "POS-D" for r in rows(child, "FailureMode")), True)

        run = RUN[arm]
        inv, closure, steps, rt = (read(run / name) for name in
                                    ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        ck(f"{arm} run identity", (inv["run_id"], inv["arm"], closure["run_id"]),
           (run.name, arm, run.name))
        ck(f"{arm} SSH0 GUI queue", (inv["session_id"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
           inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(f"{arm} registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]),
           ("NO", "NO"))
        ck(f"{arm} source stable", closure["source_hashes_before"], closure["source_hashes_after"])
        source_paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT,
                        "parent_closure": PARENT_RUN / "closure.json", "contract": HERE / "contract.json",
                        "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
                        "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
                        "runner": HERE / "run_native_ssh.ps1"}
        for name, path in source_paths.items():
            ck(f"{arm} source seal {name}", closure["source_hashes_before"][name], sha(path))
        ck(f"{arm} installed seals", tuple(closure["source_hashes_before"][n] for n in
           ("exe", "manual", "dictionary")), tuple(contract["source"][n + "_sha256"] for n in
           ("exe", "manual", "dictionary")))
        ck(f"{arm} invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(f"{arm} native outcome", (closure["error"], closure["native_outcome"],
           closure["conversion"]["errors"], closure["conversion"]["warning_codes"],
           closure["conversion"]["notes"]), (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
        ck(f"{arm} five steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
           [(name, "completed", 0, True) for name in
            ("import", "export", "calc", "jsonreport", "check_import_export")])
        ck(f"{arm} 13 raw files", len(closure["raw"]), 13)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
        ck(f"{arm} roundtrip", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(child), populated(native_json(run / "roundtrip-raw.json"))
        ck(f"{arm} populated table count", len(authored), 23)
        for name, value in authored.items():
            ck(f"{arm} native table {name}", exported.get(name), value)
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
        ck(f"{arm} converter counts", marker.groups() if marker else None, ("0", "1", "0"))
        ck(f"{arm} warning/error codes", (re.findall(r"\(warning #(\d+)\)", runlog),
           re.findall(r"\(error #(\d+)\)", runlog)), (["108"], []))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        ck(f"{arm} first B failure", failure_events(log)[0],
           (8.62763, "noncritical" if arm == "roota" else "critical", "FM-POS-B"))
        ck(f"{arm} abort time", re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:", log),
           ["16.7498"] if arm == "roota" else ["8.62763"])
        ck(f"{arm} no mission success", " mission success:" in log, False)
        ck(f"{arm} CM completion count", len(re.findall(r"^Time: [\d.]+  system CM task \d+ on <TEACH-AIR-01,0> completed$", log, re.M)),
           2 if arm == "roota" else 1)
        report = native_json(run / "report-raw.json")
        summary, system, stock = (report_rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm} report tables", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        ck(f"{arm} replication horizon success", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP", "MSUF")),
           (1, 0, 36, 0))
        ck(f"{arm} 72 aligned bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        ck(f"{arm} failures repairs", (sum(r["NFAIL"] or 0 for r in system),
           sum(r["NREPT"] or 0 for r in system)), (2, 2) if arm == "roota" else (1, 1))
        ck(f"{arm} failure bins", [r["STINT"] for r in system if r["NFAIL"]],
           [8.5, 16.5] if arm == "roota" else [8.5])
        ck(f"{arm} no stock movement", all(close(r[k] or 0, 0) for r in stock for k in
           ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(f"{arm} terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]),
           (1, 0, 0))

    ck("root A second critical", failure_events((RUN["roota"] / "model.log").read_text(encoding="utf-8-sig"))[1],
       (16.7498, "critical", "FM-POS-A"))
    ck("root B only one event after early abort",
       len(failure_events((RUN["rootb"] / "model.log").read_text(encoding="utf-8-sig"))), 1)
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g08-tree-root-panel-author-native-replay/v1.0.0", "case_id": "G08",
              "variant_ids": ["G08.var01", "G08.var02"], "run_ids": [RUN[a].name for a in ARMS],
              "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": "B h8.62763 noncritical under root A, critical/abort under root B; root A later fails h16.7498 critical/abort; no path labels in native log",
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
