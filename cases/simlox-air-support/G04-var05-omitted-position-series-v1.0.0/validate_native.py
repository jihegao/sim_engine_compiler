"""Author replay of the paired omitted-position RBD native evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, make, rows
from check_roundtrip import native_json, populated

IDS = {arm: f"g04-var05-{arm}-v100-ssh-20261003-01" for arm in ARMS}
PARENT_RUN = HERE.parent / "G04-three-branch-threshold-v1.0.0" / "runs" / "g04-kn-one-v100-ssh-20261002-01"
OUT = HERE / "author-validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table_map(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def events(log: str) -> list[tuple]:
    result = []
    for match in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                             r"(.*?)\n(?=Time:|$)", log, re.S):
        modes = re.findall(r"Failure Mode: (FM-POS-[A-Z]) on materiel: <(POS-[A-Z]),0>", match.group(3))
        result.append((float(match.group(1)), match.group(2), modes))
    return result


def close(actual: object, expected: float, tol: float = 1e-4) -> bool:
    return isinstance(actual, (int, float)) and math.isclose(float(actual), expected, rel_tol=0, abs_tol=tol)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, diff, parent = read(HERE / "contract.json"), read(HERE / "exact-diff.json"), read(PARENT)
    ck("contract identity", (contract["case_id"], contract["variant_id"]), ("G04", "G04.var05"))
    ck("parent input seal", sha(PARENT), PARENT_SHA)
    ck("parent closure seal", sha(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"])
    ck("exact diff seal", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff parent seal", diff["parent_sha256"], PARENT_SHA)
    source = {}
    for arm in ARMS:
        doc = read(HERE / f"{arm}-input.json")
        source[arm] = doc
        ck(f"{arm} input seal", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"{arm} builder replay", make(arm), doc)
        before, after = table_map(parent), table_map(doc)
        changed = {name: {"before": before[name], "after": after[name]} for name in before if before[name] != after[name]}
        ck(f"{arm} exact diff rows", diff["arms"][arm]["changed"], changed)
        ck(f"{arm} diff input seal", diff["arms"][arm]["input_sha256"], contract["input_sha256"][arm])
        expected = ["CMLocation", "FailureMode", "MaterielOperationalModes", "MaterielPosition", "MaterielStructure", "ProblemDescription"]
        if arm == "included":
            expected += ["RBDParallel", "RBDParallelStructure"]
        ck(f"{arm} changed tables", sorted(changed), sorted(expected))
        ck(f"{arm} physical POS-D", rows(doc, "MaterielStructure")[3], ["POS-D", "TEACH-AIR-01", 1, 1.0, None, None])
        ck(f"{arm} POS-D failure", rows(doc, "FailureMode")[-1],
           ["FM-POS-D", "Position D direct repair", "POS-D", 1000000.0, "OPHOURS", 1.0, None, None, None])
        ck(f"{arm} unchanged mission and controls", (rows(doc, "MissionType"), rows(doc, "OperationProfile"), rows(doc, "Control")),
           (rows(parent, "MissionType"), rows(parent, "OperationProfile"), rows(parent, "Control")))
    omitted, included = source["omitted"], source["included"]
    pair_changes = [n for n in table_map(omitted) if table_map(omitted)[n] != table_map(included)[n]]
    ck("pair RBD-only semantic delta", pair_changes, ["ProblemDescription", "RBDParallel", "RBDParallelStructure"])
    ck("omitted RBD", (rows(omitted, "RBDParallel")[0][2:4], [r[1] for r in rows(omitted, "RBDParallelStructure")]),
       ([1, 3], ["POS-A", "POS-B", "POS-C"]))
    ck("included RBD", (rows(included, "RBDParallel")[0][2:4], [r[1] for r in rows(included, "RBDParallelStructure")]),
       ([1, 4], ["POS-A", "POS-B", "POS-C", "POS-D"]))

    observations = {}
    for arm in ARMS:
        run = HERE / "runs" / IDS[arm]
        inv, closure, steps, rt = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        prefix = arm + ": "
        ck(prefix + "run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
           (IDS[arm], arm, IDS[arm], arm))
        ck(prefix + "SSH session-zero", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
           (0, True, "session0_ssh_cli"))
        ck(prefix + "GUI and serial queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(prefix + "registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
        ck(prefix + "stable sources", closure["source_hashes_before"], closure["source_hashes_after"])
        seals = closure["source_hashes_before"]
        paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT, "parent_closure": PARENT_RUN / "closure.json",
                 "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
                 "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
        for name, path in paths.items():
            ck(prefix + f"source seal {name}", seals[name], sha(path))
        ck(prefix + "installed pins", (seals["exe"], seals["manual"], seals["dictionary"]),
           (contract["source"]["exe_sha256"], contract["source"]["manual_sha256"], contract["source"]["dictionary_sha256"]))
        ck(prefix + "invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(prefix + "accepted native outcome", (closure["error"], closure["native_outcome"]), (None, "zero_error_reviewed_warnings"))
        ck(prefix + "five native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
           [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
        ck(prefix + "13 raw files", len(closure["raw"]), 13)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(prefix + f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
        ck(prefix + "roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(source[arm]), populated(native_json(run / "roundtrip-raw.json"))
        ck(prefix + "23 populated tables", len(authored), 23)
        for name, value in authored.items():
            ck(prefix + f"native table {name}", exported.get(name), value)
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        ck(prefix + "conversion counts", marker.groups() if marker else None, ("0", "1", "0"))
        ck(prefix + "reviewed warning", re.findall(r"\(warning #(\d+)\)", run_log), ["108"])
        ck(prefix + "no converter errors", re.findall(r"\(error #(\d+)\)", run_log), [])

        log = (run / "model.log").read_text(encoding="utf-8-sig")
        ev = events(log)
        observations[arm] = ev
        expected_events = [(8.2973, "noncritical", [("FM-POS-B", "POS-B")]),
                           (10.1716, "critical" if arm == "omitted" else "noncritical",
                            [("FM-POS-B", "POS-B"), ("FM-POS-D", "POS-D")])]
        if arm == "included":
            expected_events.append((13.1113, "noncritical", [("FM-POS-B", "POS-B"), ("FM-POS-D", "POS-D"), ("FM-POS-A", "POS-A")]))
        ck(prefix + "failure identities and criticality", ev, expected_events)
        ck(prefix + "no extra failure event", log.count("CM failure mode added"), len(expected_events))
        ck(prefix + "mission start", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log, True)
        if arm == "omitted":
            ck(prefix + "critical abort and return", ("Time: 10.1716 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in log,
                                                       "Time: 12.3433 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:" in log,
                                                       log.count(" mission success:")), (True, True, 0))
            expected_starts, expected_ends = [('12.3433', '1', 'FM-POS-D'), ('12.3433', '0', 'FM-POS-B')], [('12.8433', '1'), ('12.8433', '0')]
        else:
            ck(prefix + "mission success", ("Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log,
                                              log.count(" mission aborted:")), (True, 0))
            expected_starts, expected_ends = [('34', '0', 'FM-POS-B'), ('34', '1', 'FM-POS-D'), ('34', '2', 'FM-POS-A')], [('34.5', '0'), ('34.5', '1'), ('34.5', '2')]
        starts = re.findall(r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[ABD])", log)
        ends = re.findall(r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)
        ck(prefix + "postmission parallel CM", (starts, ends), (expected_starts, expected_ends))

        report = native_json(run / "report-raw.json")
        summary, system, stock = (report_rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(prefix + "report tables", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        ck(prefix + "one rep and horizon", (summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"]), (1, 0, 36))
        ck(prefix + "mission success fraction", summary[0]["MSUF"], 0 if arm == "omitted" else 1)
        ck(prefix + "72 System bins", [(r["STINT"], r["ETINT"]) for r in system], [(i / 2, (i + 1) / 2) for i in range(72)])
        ck(prefix + "72 Stock bins", [(r["STINT"], r["ETINT"]) for r in stock], [(i / 2, (i + 1) / 2) for i in range(72)])
        n = 2 if arm == "omitted" else 3
        ck(prefix + "failure and repair counts", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)), (n, n))
        ck(prefix + "failure bins", [r["STINT"] for r in system if r["NFAIL"]], [8, 10] if arm == "omitted" else [8, 10, 13])
        ck(prefix + "repair bin", [r["STINT"] for r in system if r["NREPT"]], [12.5] if arm == "omitted" else [34.5])
        ck(prefix + "half-hour repair occupancy", close(sum(r["SYDT"] or 0 for r in system), 0.5), True)
        ck(prefix + "no stock movement", all(close(r[k] or 0, 0) for r in stock for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(prefix + "terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))
        ck(prefix + "operating exposure", close(0.5 * sum(r["NSYMO"] or 0 for r in system),
                                                4.343287855386734 if arm == "omitted" else 26), True)
    ck("matched B and D failure times", [(e[0], e[2][-1]) for e in observations["omitted"]],
       [(e[0], e[2][-1]) for e in observations["included"][:2]])
    ck("opposite D criticality", (observations["omitted"][1][1], observations["included"][1][1]),
       ("critical", "noncritical"))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g04-var05-author-native-replay/v1", "case_id": "G04", "variant_id": "G04.var05",
              "run_ids": IDS, "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"matched_pos_b_hour": 8.2973, "matched_pos_d_hour": 10.1716,
                              "omitted": "D critical, abort h10.1716, return h12.3433, two CM complete h12.8433",
                              "included": "D noncritical, later A h13.1113, success h34, three CM complete h34.5"},
              "limits": contract["limits"]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
