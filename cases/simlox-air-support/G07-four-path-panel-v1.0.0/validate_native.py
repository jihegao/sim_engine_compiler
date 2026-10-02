"""Author replay of four bridge-path permutations and the accepted fourth path."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, MAPPING, PARENT, PARENT_SHA, TARGET, live_paths, make, rows
from check_roundtrip import native_json, populated

IDS = {arm: f"g07-panel-{arm}-v100-ssh-20261003-01" for arm in ARMS}
PARENT_RUN = HERE.parent / "G07-bridge-diagonal-v1.0.0" / "runs" / "g07-var01-bridge-v100-ssh-20261003-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def report_rows(doc: dict, name: str) -> list[dict]:
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r, strict=True)) for inst in t["instances"] for r in inst["rows"]]


def failure_events(log: str) -> list[tuple]:
    result = []
    for match in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                             r"(.*?)\n(?=Time:|$)", log, re.S):
        modes = re.findall(r"Failure Mode: (FM-POS-[A-Z]) on materiel: <(POS-[A-Z]),0>", match.group(3))
        result.append((float(match.group(1)), match.group(2), modes))
    return result


def close(x: object, y: float, tol: float = 1e-4) -> bool:
    return isinstance(x, (int, float)) and math.isclose(float(x), y, rel_tol=0, abs_tol=tol)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, got: object, want: object) -> None:
        checks.append({"name": name, "passed": got == want,
                       "got": got if got != want else None, "want": want if got != want else None})

    contract, diff, parent = read(HERE / "contract.json"), read(HERE / "exact-diff.json"), read(PARENT)
    ck("contract identity", (contract["case_id"], contract["variant_ids"]), ("G07", ["G07.var01", "G07.var02"]))
    ck("accepted parent input", sha(PARENT), PARENT_SHA)
    ck("accepted parent closure", sha(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"])
    ck("diff seal", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff parent", diff["parent_sha256"], PARENT_SHA)
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    ck("parent unique LL+BR+UR event prefix", failure_events(parent_log), [
        (8.62763, "noncritical", [("FM-POS-B", "POS-B")]),
        (16.7498, "noncritical", [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")]),
    ])
    ck("parent mission success", "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in parent_log, True)
    observations = {}
    for arm in ARMS:
        doc = read(HERE / f"{arm}-input.json")
        p = arm + ": "
        ck(p + "input seal", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(p + "builder replay", make(arm), doc)
        before, after = tables(parent), tables(doc)
        changed = {name: {"before": before[name], "after": after[name]} for name in before if before[name] != after[name]}
        ck(p + "exact table diff", diff["arms"][arm]["changed"], changed)
        ck(p + "only description and bridge row changed", sorted(changed), ["ProblemDescription", "RBDBridge"])
        ck(p + "diff input seal", diff["arms"][arm]["input_sha256"], contract["input_sha256"][arm])
        ck(p + "physical, failure, mission and controls fixed",
           [rows(doc, n) for n in ("MaterielPosition", "MaterielStructure", "MaterielOperationalModes", "FailureMode",
                                   "CMLocation", "MissionType", "OperationProfile", "Control")],
           [rows(parent, n) for n in ("MaterielPosition", "MaterielStructure", "MaterielOperationalModes", "FailureMode",
                                      "CMLocation", "MissionType", "OperationProfile", "Control")])
        ck(p + "bridge slot permutation", rows(doc, "RBDBridge")[0][2:7],
           [f"POS-{MAPPING[arm][slot]}" for slot in ("UL", "LL", "BR", "UR", "LR")])
        ck(p + "first B failure leaves path", len(live_paths(MAPPING[arm], {"B"})) > 0, True)
        ck(p + "remaining source path after B/A", live_paths(MAPPING[arm], {"B", "A"}),
           [] if TARGET[arm] is None else [TARGET[arm]])

        run = HERE / "runs" / IDS[arm]
        inv, closure, steps, rt = (read(run / n) for n in
                                   ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        ck(p + "run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
           (IDS[arm], arm, IDS[arm], arm))
        ck(p + "case/variants", (inv["case_id"], inv["variant_ids"]), ("G07", ["G07.var01", "G07.var02"]))
        ck(p + "session-zero SSH", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
           (0, True, "session0_ssh_cli"))
        ck(p + "GUI and queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(p + "registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
        ck(p + "source stable", closure["source_hashes_before"], closure["source_hashes_after"])
        source_paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT,
                        "parent_closure": PARENT_RUN / "closure.json", "contract": HERE / "contract.json",
                        "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
                        "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
                        "runner": HERE / "run_native_ssh.ps1"}
        for name, path in source_paths.items():
            ck(p + f"source seal {name}", closure["source_hashes_before"][name], sha(path))
        ck(p + "installed source seals", tuple(closure["source_hashes_before"][n] for n in ("exe", "manual", "dictionary")),
           tuple(contract["source"][n + "_sha256"] for n in ("exe", "manual", "dictionary")))
        ck(p + "invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(p + "native outcome", (closure["error"], closure["native_outcome"], closure["conversion"]["errors"],
                                  closure["conversion"]["warning_codes"], closure["conversion"]["notes"]),
           (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
        ck(p + "five native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
           [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
        ck(p + "13 raw files", len(closure["raw"]), 13)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(p + f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
        ck(p + "roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(doc), populated(native_json(run / "roundtrip-raw.json"))
        ck(p + "22 populated tables", len(authored), 22)
        for name, value in authored.items():
            ck(p + f"native table {name}", exported.get(name), value)
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog)
        ck(p + "conversion counts", marker.groups() if marker else None, ("0", "1", "0"))
        ck(p + "reviewed warning", re.findall(r"\(warning #(\d+)\)", runlog), ["108"])
        ck(p + "no converter errors", re.findall(r"\(error #(\d+)\)", runlog), [])
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        ev = failure_events(log)
        observations[arm] = ev
        ck(p + "matched B/A event timeline", ev, [
            (8.62763, "noncritical", [("FM-POS-B", "POS-B")]),
            (16.7498, "critical" if arm == "allbroken" else "noncritical",
             [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")]),
        ])
        ck(p + "exactly two failures", log.count("CM failure mode added"), 2)
        ck(p + "mission starts", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log, True)
        if arm == "allbroken":
            ck(p + "critical abort/return", ("Time: 16.7498 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in log,
                                               "Time: 23.2498 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:" in log,
                                               log.count(" mission success:")), (True, True, 0))
            repair_time = "23.7498"
        else:
            ck(p + "success/no abort", ("Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log,
                                         log.count(" mission aborted:")), (True, 0))
            repair_time = "34.5"
        ck(p + "two CM completions", re.findall(r"^Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed$", log, re.M),
           [(repair_time, "0"), (repair_time, "1")])
        report = native_json(run / "report-raw.json")
        summary, system, stock = (report_rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(p + "report tables", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        ck(p + "one replication/horizon", (summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"]), (1, 0, 36))
        ck(p + "success fraction", summary[0]["MSUF"], 0 if arm == "allbroken" else 1)
        ck(p + "72 aligned System/Stock bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        ck(p + "two failures/repairs", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (2, 2))
        ck(p + "failure bins", [r["STINT"] for r in system if r["NFAIL"]], [8.5, 16.5])
        ck(p + "repair bin", [r["STINT"] for r in system if r["NREPT"]], [23.5 if arm == "allbroken" else 34.5])
        ck(p + "half-hour repair occupancy", close(sum(r["SYDT"] or 0 for r in system), 0.5), True)
        ck(p + "no stock movement", all(close(r[k] or 0, 0) for r in stock for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(p + "terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))
        ck(p + "operating exposure", close(0.5 * sum(r["NSYMO"] or 0 for r in system),
                                            15.249790668487549 if arm == "allbroken" else 26), True)
    ck("all arms match parent B/A timing", [[e[0] for e in observations[arm]] for arm in ARMS], [[8.62763, 16.7498]] * 4)
    ck("allbroken alone makes A critical", [observations[arm][1][1] for arm in ARMS],
       ["noncritical", "noncritical", "noncritical", "critical"])

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g07-four-path-panel-author-native-replay/v1", "case_id": "G07",
              "variant_ids": ["G07.var01", "G07.var02"], "run_ids": IDS, "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed), "failed": failed,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"matched": "B h8.62763 noncritical and A h16.7498 across all arms and accepted parent",
                              "unique_paths": "UL+UR, LL+LR, UL+BR+LR and accepted-parent LL+BR+UR each leave A noncritical and succeed h34",
                              "allbroken": "A critical, abort h16.7498, return h23.2498"},
              "limits": contract["limits"]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
