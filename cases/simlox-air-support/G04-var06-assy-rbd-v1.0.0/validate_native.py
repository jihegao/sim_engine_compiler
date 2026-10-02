"""Author replay of the assembly-owned RBD native evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, SERIES_REFERENCE, SERIES_REFERENCE_SHA, make, rows
from check_roundtrip import native_json, populated

IDS = {arm: f"g04-var06-assy-{arm}-v100-ssh-20261003-01" for arm in ARMS}
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
    found = []
    for match in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                             r"(.*?)\n(?=Time:|$)", log, re.S):
        failures = re.findall(r"Failure Mode: (FM-POS-[A-Z]) on materiel: <(POS-[A-Z]),0> connection path: ([^\n]+)", match.group(3))
        found.append((float(match.group(1)), match.group(2), failures))
    return found


def close(actual: object, expected: float, tol: float = 1e-4) -> bool:
    return isinstance(actual, (int, float)) and math.isclose(float(actual), expected, abs_tol=tol)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, diff, parent = read(HERE / "contract.json"), read(HERE / "exact-diff.json"), read(PARENT)
    ck("identity", (contract["case_id"], contract["variant_id"]), ("G04", "G04.var06"))
    ck("accepted parent seal", sha(PARENT), PARENT_SHA)
    ck("accepted parent closure", sha(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"])
    ck("accepted schema donor", sha(SERIES_REFERENCE), SERIES_REFERENCE_SHA)
    ck("schema donor contract", contract["schema_donor"]["input_sha256"], SERIES_REFERENCE_SHA)
    ck("exact diff seal", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff parent seal", diff["parent_sha256"], PARENT_SHA)
    source = {}
    for arm in ARMS:
        doc = read(HERE / f"{arm}-input.json")
        source[arm] = doc
        ck(f"{arm} input seal", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"{arm} builder replay", make(arm), doc)
        before, after = table_map(parent), table_map(doc)
        changed = {name: {"before": before.get(name), "after": after.get(name)}
                   for name in after if before.get(name) != after[name]}
        ck(f"{arm} exact diff rows", diff["arms"][arm]["changed"], changed)
        ck(f"{arm} diff input seal", diff["arms"][arm]["input_sha256"], contract["input_sha256"][arm])
        ck(f"{arm} changed table set", sorted(changed), sorted([
            "ProblemDescription", "Item", "MaterielStructure", "MaterielOperationalModes",
            "RBDParallel", "RBDParallelStructure", "RBDSeries", "RBDSeriesStructure"
        ]))
        ck(f"{arm} same mission, failures, repairs and controls",
           [rows(doc, name) for name in ("MissionType", "OperationProfile", "FailureMode", "CMLocation", "Control")],
           [rows(parent, name) for name in ("MissionType", "OperationProfile", "FailureMode", "CMLocation", "Control")])
        ck(f"{arm} assembly physical parent", rows(doc, "MaterielStructure")[:4],
           [["TEACH-ASSY-01", "TEACH-AIR-01", 1, 1.0, None, None],
            *[[f"POS-{letter}", "TEACH-ASSY-01", 1, 1.0, None, None] for letter in "ABC"]])
        ck(f"{arm} system RBD root", rows(doc, "RBDSeriesStructure")[0],
           ["G04-SYS-ROOT", "TEACH-ASSY-01", "G04-OPS", 1, None])
    parallel, series = source["parallel"], source["series"]
    ck("pair source delta", [name for name in table_map(parallel)
                             if table_map(parallel)[name] != table_map(series)[name]],
       ["ProblemDescription", "MaterielOperationalModes", "RBDParallel", "RBDParallelStructure", "RBDSeries", "RBDSeriesStructure"])
    ck("parallel assembly mode and blocks", (rows(parallel, "MaterielOperationalModes")[1][2],
                                               [r[1] for r in rows(parallel, "RBDParallelStructure")]),
       ("G04-ASSY-PARALLEL", ["POS-A", "POS-B", "POS-C"]))
    ck("series assembly mode and blocks", (rows(series, "MaterielOperationalModes")[1][2],
                                             [r[1] for r in rows(series, "RBDSeriesStructure")[1:]]),
       ("G04-ASSY-SERIES", ["POS-A", "POS-B", "POS-C"]))

    observations = {}
    for arm in ARMS:
        run = HERE / "runs" / IDS[arm]
        inv, closure, steps, rt = (read(run / name) for name in
                                   ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        prefix = arm + ": "
        ck(prefix + "run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
           (IDS[arm], arm, IDS[arm], arm))
        ck(prefix + "SSH session zero", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
           (0, True, "session0_ssh_cli"))
        ck(prefix + "GUI and queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(prefix + "registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
        ck(prefix + "stable source hashes", closure["source_hashes_before"], closure["source_hashes_after"])
        paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT, "parent_closure": PARENT_RUN / "closure.json",
                 "schema_donor": SERIES_REFERENCE, "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
                 "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
                 "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
        for name, path in paths.items():
            ck(prefix + f"source seal {name}", closure["source_hashes_before"][name], sha(path))
        ck(prefix + "installed pins", tuple(closure["source_hashes_before"][n] for n in ("exe", "manual", "dictionary")),
           tuple(contract["source"][n + "_sha256"] for n in ("exe", "manual", "dictionary")))
        ck(prefix + "invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(prefix + "native outcome", (closure["error"], closure["native_outcome"], closure["conversion"]["errors"],
                                       closure["conversion"]["warning_codes"], closure["conversion"]["notes"]),
           (None, "zero_error_reviewed_warnings", 0, ["108"], 0))
        ck(prefix + "five completed native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
           [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
        ck(prefix + "13 sealed raw files", len(closure["raw"]), 13)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(prefix + f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
        ck(prefix + "roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(source[arm]), populated(native_json(run / "roundtrip-raw.json"))
        ck(prefix + "populated table count", len(authored), 25 if arm == "parallel" else 23)
        for name, value in authored.items():
            ck(prefix + f"native table {name}", exported.get(name), value)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        found = events(log)
        observations[arm] = found
        ck(prefix + "failure identity, time, criticality and ASSY path",
           [(time, state, [(mode, pos, "TEACH-ASSY-01" in path) for mode, pos, path in failures])
            for time, state, failures in found],
           [(8.62763, "noncritical" if arm == "parallel" else "critical",
             [("FM-POS-B", "POS-B", True)])] +
           ([(16.7498, "noncritical", [("FM-POS-B", "POS-B", True), ("FM-POS-A", "POS-A", True)])]
            if arm == "parallel" else []))
        ck(prefix + "no extra failure event", log.count("CM failure mode added"), 2 if arm == "parallel" else 1)
        ck(prefix + "mission start", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log, True)
        if arm == "parallel":
            ck(prefix + "mission success and no abort", ("Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log,
                                                    log.count(" mission aborted:")), (True, 0))
            ck(prefix + "two postmission repairs", (len(re.findall(r"^Time: [\d.]+  system CM task \d+ on <TEACH-AIR-01,0> completed", log, re.M)),
                                                    "Time: 34.5 <TEACH-AIR-01,BASE-01,0> Maintained system arrives" in log), (2, True))
        else:
            ck(prefix + "critical abort and return", ("Time: 8.62763 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in log,
                                                    "Time: 9.25527 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:" in log,
                                                    log.count(" mission success:")), (True, True, 0))
            ck(prefix + "repair and ready", ("Time: 9.75527  system CM task 0 on <TEACH-AIR-01,0> completed" in log,
                                               "Time: 9.75527 <TEACH-AIR-01,BASE-01,0> System ready" in log), (True, True))
        report = native_json(run / "report-raw.json")
        summary, system, stock = (report_rows(report, name) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(prefix + "report table set", {t["name"] for t in report["report"]["tables"]},
           {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        ck(prefix + "one replication and horizon", (summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"]), (1, 0, 36))
        ck(prefix + "mission success fraction", summary[0]["MSUF"], 1 if arm == "parallel" else 0)
        ck(prefix + "72 System and Stock bins", ([r["STINT"] for r in system], [r["STINT"] for r in stock]),
           ([i / 2 for i in range(72)], [i / 2 for i in range(72)]))
        ck(prefix + "failure and repair counts", (sum(r["NFAIL"] or 0 for r in system), sum(r["NREPT"] or 0 for r in system)),
           (2, 2) if arm == "parallel" else (1, 1))
        ck(prefix + "failure bins", [r["STINT"] for r in system if r["NFAIL"]], [8.5, 16.5] if arm == "parallel" else [8.5])
        ck(prefix + "repair bin", [r["STINT"] for r in system if r["NREPT"]], [34.5] if arm == "parallel" else [9.5])
        ck(prefix + "half-hour repair occupancy", close(sum(r["SYDT"] or 0 for r in system), 0.5), True)
        ck(prefix + "no stock movement", all(close(r[k] or 0, 0) for r in stock for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), True)
        ck(prefix + "terminal ready", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]), (1, 0, 0))
        ck(prefix + "operating exposure", close(0.5 * sum(r["NSYMO"] or 0 for r in system),
                                                26 if arm == "parallel" else 1.2552660703659058), True)
    ck("matched first failure", [(e[0], e[2][0][:2]) for e in observations["parallel"][:1]],
       [(e[0], e[2][0][:2]) for e in observations["series"][:1]])
    ck("opposite first failure criticality", (observations["parallel"][0][1], observations["series"][0][1]),
       ("noncritical", "critical"))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g04-var06-author-native-replay/v1", "case_id": "G04", "variant_id": "G04.var06",
              "run_ids": IDS, "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"matched_first_failure": "FM-POS-B at h8.62763; noncritical parallel, critical series",
                              "parallel": "A later h16.7498; success h34; two CM complete h34.5",
                              "series": "abort h8.62763; return h9.25527; one CM complete h9.75527"},
              "limits": contract["limits"]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:4]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
