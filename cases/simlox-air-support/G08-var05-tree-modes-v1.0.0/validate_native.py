"""Author replay of G08.var05 selected tree operational-mode arms."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated

PARENT_RUN = HERE.parent / "G08-tree-root-panel-v1.0.0" / "runs" / "g08-roota-v100-ssh-20261003-01"
RUN = {arm: HERE / "runs" / f"g08-var05-{arm}-v100-ssh-20261003-01" for arm in ARMS}
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
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"]),
       ("G08", "G08.var05", "1.0.0-candidate"))
    ck("accepted source and closure", (sha(PARENT), sha(PARENT_RUN / "closure.json")),
       (PARENT_SHA, contract["accepted_parent"]["native_closure_sha256"]))
    ck("frozen exact diff", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff parent", diff["parent_sha256"], PARENT_SHA)
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_events = EVENT.findall(parent_log)
    ck("accepted parent events", parent_events,
       [("8.62763", "noncritical", "FM-POS-B"), ("16.7498", "critical", "FM-POS-B")])
    ck("accepted parent A failure in second event", "Failure Mode: FM-POS-A" in parent_log, True)
    expected_events = {
        "mother75": [("8.68469", "noncritical", "FM-POS-B"),
                     ("19.5142", "critical", "FM-POS-B")],
        "sub75": [("8.75316", "critical", "FM-POS-A")],
    }
    for arm in ARMS:
        child = read(HERE / f"{arm}-input.json")
        ck(f"{arm} frozen input", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"{arm} builder replay", make(arm), child)
        ck(f"{arm} diff input seal", diff["arms"][arm]["input_sha256"], contract["input_sha256"][arm])
        before, after = ({t["name"]: t for t in d["model"]["tables"]} for d in (parent, child))
        changed = {n: {"before": before[n], "after": after[n]} for n in before if before[n] != after[n]}
        ck(f"{arm} four changed tables", sorted(changed),
           sorted(("ProblemDescription", "OperationalModes", "MaterielOperationalModes", "RBDTreeStructure")))
        ck(f"{arm} exact changed tables", changed, diff["arms"][arm]["changed"])
        ck(f"{arm} unchanged physical and mission controls",
           [rows(child, n) for n in ("FailureMode", "RBDTree", "MissionType", "OperationProfile", "Control")],
           [rows(parent, n) for n in ("FailureMode", "RBDTree", "MissionType", "OperationProfile", "Control")])
        mode = "G08-A-75" if arm == "mother75" else "G08-B-75"
        pos = "POS-A" if arm == "mother75" else "POS-B"
        ck(f"{arm} mode definition", [r[0] for r in rows(child, "OperationalModes")], ["G04-OPS", mode])
        ck(f"{arm} usage row", [r for r in rows(child, "MaterielOperationalModes") if r[0] == pos][-1],
           [pos, mode, None, None, 0.75, None])
        tree = rows(child, "RBDTreeStructure")
        ck(f"{arm} selected tree modes", [(r[3], r[4]) for r in tree],
           [(mode, "G04-OPS")] * 3 if arm == "mother75" else
           [("G04-OPS", mode), ("G04-OPS", "G04-OPS"), ("G04-OPS", "G04-OPS")])

        run = RUN[arm]
        inv, closure, steps, rt = (read(run / name) for name in
                                    ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        ck(f"{arm} run identity", (inv["run_id"], inv["arm"], inv["variant_id"], closure["run_id"]),
           (run.name, arm, "G08.var05", run.name))
        ck(f"{arm} SSH0 GUI queue",
           (inv["session_id"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]],
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
        ck(f"{arm} 23 populated tables", len(authored), 23)
        for name, value in authored.items():
            ck(f"{arm} native table {name}", exported.get(name), value)

        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
        ck(f"{arm} conversion marker", marker.groups() if marker else None, ("0", "1", "0"))
        ck(f"{arm} warning/error codes", (re.findall(r"\(warning #(\d+)\)", runlog),
           re.findall(r"\(error #(\d+)\)", runlog)), (["108"], []))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        events = EVENT.findall(log)
        ck(f"{arm} events and identities", events, expected_events[arm])
        ck(f"{arm} native timing differs from parent", events != parent_events, True)
        ck(f"{arm} event log differs from parent", sha(run / "model.log") != sha(PARENT_RUN / "model.log"), True)
        ck(f"{arm} mission abort", re.findall(r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:", log),
           ["19.5142"] if arm == "mother75" else ["8.75316"])
        ck(f"{arm} no success", " mission success:" in log, False)
        ck(f"{arm} complete CM count", len(re.findall(r"^Time: [\d.]+  system CM task \d+ on <TEACH-AIR-01,0> completed$", log, re.M)),
           2 if arm == "mother75" else 1)
        report = native_json(run / "report-raw.json")
        summary, system, stock = (report_rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm} report tables", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        ck(f"{arm} replication horizon success", tuple(summary[0][k] for k in ("NREP", "RTILW", "RTIUP", "MSUF")),
           (1, 0, 36, 0))
        ck(f"{arm} 72 aligned bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        count = 2 if arm == "mother75" else 1
        ck(f"{arm} failure repair counts", (sum(r["NFAIL"] or 0 for r in system),
           sum(r["NREPT"] or 0 for r in system)), (count, count))
        ck(f"{arm} failure bins", [r["STINT"] for r in system if r["NFAIL"]],
           [8.5, 19.5] if arm == "mother75" else [8.5])
        ck(f"{arm} no stock movement", all(not r[k] for r in stock for k in
           ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(f"{arm} terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]),
           (1, 0, 0))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g08-var05-author-native-replay/v1", "case_id": "G08",
              "variant_id": "G08.var05", "run_ids": [RUN[a].name for a in ARMS], "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed), "failed": failed,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": "full-rate B h8.62763 NC then A h16.7498 C; mother75 B h8.68469 NC then A h19.5142 C; sub75 A h8.75316 C with no B event before abort",
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("passed", "passed_count", "failed_count", "failed")}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
