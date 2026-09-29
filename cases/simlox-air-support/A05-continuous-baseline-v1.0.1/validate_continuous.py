"""Replay frozen A05 fixed/continuous/initial-shortage native evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, NAMES, build
from check_roundtrip import parse_native

RUNS = {
    "fixed": "a05-fixed-four-hour-v101-ssh-20260930-01",
    "continuous": "a05-continuous-four-hour-v101-ssh-20260930-01",
    "shortage": "a05-initial-shortage-v101-ssh-20260930-01",
}
HASHES = {
    "fixed": "577f95bc8716b7191a783f3ec06ed24c50d61362df1dbf434e9fba846be58b0d",
    "continuous": "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea",
    "shortage": "95d2c855f0e7a99f9892053a89fdff99501dfab78b50bac0265b9d4512a67cca",
}
DIFF_SHA = "9f8014070956b9125e4ef0719058cf7eed0ffa0c514ac02ae1d7c83528f32eeb"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
OUT = HERE / "review" / "author-continuous-validation-2026-09-30.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_rows(doc: dict, root: str, name: str) -> tuple[list[str], list[list]]:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {root}.{name}")
    t = matches[0]
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diffs.json").read_text(encoding="utf-8"))
    ck("accepted A03 parent SHA", sha(PARENT), PARENT_SHA)
    ck("contract case/version/state", (contract["case_id"], contract["case_version"], contract["publication_state"]),
       ("A05", "1.0.1-candidate", "not_published"))
    ck("diff SHA", sha(HERE / "exact-diffs.json"), DIFF_SHA)
    ck("exact three changed-table sets", {key: sorted(value["changed_tables_only"])
                                          for key, value in diff["deltas"].items()},
       {"A03_to_fixed": sorted(["ProblemDescription", "Control", "MissionType", "Unit", "ResultCollection"]),
        "fixed_to_continuous": sorted(["ProblemDescription", "MissionType"]),
        "continuous_to_shortage": sorted(["ProblemDescription", "SystemDeployment", "Unit"])})
    built = build()
    docs = {}
    for variant in RUNS:
        path = HERE / NAMES[variant]
        docs[variant] = json.loads(path.read_text(encoding="utf-8"))
        ck(f"{variant} input SHA", sha(path), HASHES[variant])
        ck(f"{variant} builder identity", docs[variant] == built[variant], True)
    ck("contract input SHA map", contract["inputs"],
       {"fixed_control": HASHES["fixed"], "continuous_control": HASHES["continuous"],
        "continuous_initial_shortage": HASHES["shortage"]})
    for variant, expected in [("fixed", (None, 0.25, 0.25, 2)),
                              ("continuous", ("CONTINUOUS", None, None, 2)),
                              ("shortage", ("CONTINUOUS", None, None, 1))]:
        mc, mr = table_rows(docs[variant], "model", "MissionType")
        dc, dr = table_rows(docs[variant], "model", "SystemDeployment")
        row = dict(zip(mc, mr[0], strict=True))
        dep = dict(zip(dc, dr[0], strict=True))
        ck(f"{variant} MPAT/travel/deployment", (row["MPAT"], row["TFOUT"], row["TFRET"], dep["QTYPS"]), expected)
        ck(f"{variant} four-hour minimum-two mission", (row["DURN"], row["NOS"], row["MNOS"]), (4, 2, 2))

    report_rows = {}
    for variant, run_id in RUNS.items():
        run = HERE / "runs" / run_id
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
        ck(f"{variant} copied input SHA", sha(run / "input.json"), HASHES[variant])
        ck(f"{variant} invocation identity", (invocation["case_id"], invocation["case_version"],
                                               invocation["variant"], invocation["run_id"]),
           ("A05", "1.0.1-candidate", variant, run_id))
        ck(f"{variant} session-0 SSH", (invocation["session_id"], invocation["ssh_connection_present"],
                                        "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]]),
           (0, True, True))
        ck(f"{variant} mutex/GUI", (invocation["queue_mutex"], invocation["gui"]["pid"],
                                    invocation["gui"]["session_id"]), ("Global\\SimloxIssue18NativeQueue", 13340, 1))
        ck(f"{variant} exe SHA", invocation["simlox_exe_sha256"], EXE_SHA)
        ck(f"{variant} invocation seal", closure["invocation_sha256"], sha(run / "invocation.json"))
        ck(f"{variant} no closure error", closure["error"], None)
        ck(f"{variant} stable source seals", closure["source_hashes_before"], closure["source_hashes_after"])
        source = closure["source_hashes_before"]
        ck(f"{variant} three input seals", [source[k] for k in ["fixed", "continuous", "shortage"]],
           [HASHES[k] for k in ["fixed", "continuous", "shortage"]])
        ck(f"{variant} selected source seal", source["input"], HASHES[variant])
        ck(f"{variant} parent seal", source["parent"], PARENT_SHA)
        for key, path in [("contract", HERE / "contract.json"), ("builder", HERE / "build.py"),
                          ("checker", HERE / "check_roundtrip.py"), ("runner_script", HERE / "run_native_ssh.ps1")]:
            ck(f"{variant} {key} seal", source[key], sha(path))
        ck(f"{variant} raw artifact set", sorted(closure["raw"]),
           sorted(p.name for p in run.iterdir() if p.is_file() and p.name not in {"invocation.json", "closure.json"}))
        for name, stamp in sorted(closure["raw"].items()):
            ck(f"{variant} raw {name} size/SHA", (stamp["bytes"], stamp["sha256"]),
               ((run / name).stat().st_size, sha(run / name)))
        ck(f"{variant} five successful steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
                                                for s in steps],
           [(n, "completed", 0, True) for n in ["import", "export", "calc", "jsonreport", "check_import_export"]])
        ck(f"{variant} 13-table roundtrip", (roundtrip["passed"], len(roundtrip["populated_tables"]),
                                              roundtrip["source_sha256"], roundtrip["variant"]),
           (True, 13, HASHES[variant], variant))
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{variant} conversion counts", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+)", runlog),
           [("0", "2")])
        ck(f"{variant} warning codes", sorted(re.findall(r"warning #(\d+)", runlog)), ["108", "126"])
        events = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
        ck(f"{variant} single on-time mission", sum(f"Time: 8 {mission} mission starting, duration: 4" in e for e in events), 1)
        ck(f"{variant} hour-12 completion", sum(f"Time: 12 {mission} mission completed:" in e for e in events), 1)
        ck(f"{variant} hour-12 event success", sum(f"Time: 12 {mission} mission success:" in e for e in events), 1)
        ck(f"{variant} no abort/cancel/failure", any(re.search(r"mission (?:abort|cancel)|critical random failure added", e, re.I)
                                                   for e in events), False)
        allocated = sorted(re.findall(r"mission allocates system: <TEACH-AIR-01,([01])>", "\n".join(events)))
        ck(f"{variant} allocated systems", allocated, ["0"] if variant == "shortage" else ["0", "1"])
        suspended = [e for e in events if e.startswith("Time: 8 ") and "mission suspended:" in e]
        resumed = [e for e in events if e.startswith("Time: 12 ") and "mission resumed:" in e]
        ck(f"{variant} suspension event", len(suspended), 1 if variant == "shortage" else 0)
        ck(f"{variant} end-time resume marker", len(resumed), 1 if variant == "shortage" else 0)
        arrivals = sorted(re.findall(r"System arrives <TEACH-AIR-01,([01])>, mission success",
                                     "\n".join(e for e in events if e.startswith("Time: 12 "))))
        ck(f"{variant} returned aircraft", arrivals, ["0"] if variant == "shortage" else ["0", "1"])
        report = parse_native(run / "report-raw.json")
        ck(f"{variant} nonempty report tables", sorted(t["name"] for t in report["report"]["tables"]
                                                        if any(i["rows"] for i in t["instances"])),
           ["ProblemDescription", "ResultSummary", "StockTotalResults", "SystemResults"])
        sc, sr = table_rows(report, "report", "ResultSummary")
        summary = dict(zip(sc, sr[0], strict=True))
        ck(f"{variant} report horizon", (summary["NREP"], summary["RTILW"], summary["RTIUP"]), (1, 0, 16))
        ck(f"{variant} summary scope metrics", (summary["MSTF"], summary["MSUF"]),
           (1, 1) if variant == "fixed" else (0, 0))
        c, raw = table_rows(report, "report", "SystemResults")
        rows = [dict(zip(c, r, strict=True)) for r in raw]
        report_rows[variant] = rows
        ck(f"{variant} 32 aligned system bins", [(r["STINT"], r["ETINT"]) for r in rows],
           [(i / 2, (i + 1) / 2) for i in range(32)])
        count = 1 if variant == "shortage" else 2
        ck(f"{variant} constant availability", [r["NSYA"] for r in rows], [count] * 32)
        ck(f"{variant} operating systems", [r["NSYMO"] for r in rows],
           [0 if variant == "shortage" else count if 16 <= i < 24 else 0 for i in range(32)])
        ck(f"{variant} suspended systems", [r["NSYMS"] for r in rows],
           [count if variant == "shortage" and 16 <= i < 24 else 0 for i in range(32)])
        ck(f"{variant} assigned systems", [r["NSYMA"] for r in rows],
           [count if 14 <= i < 24 else 0 for i in range(32)])
        ck(f"{variant} ready systems", [r["NSYRY"] for r in rows],
           [0 if 14 <= i < 24 else count for i in range(32)])
        ck(f"{variant} accepted aircraft-hours", sum(r["STACC"] for r in rows) * 0.5,
           0 if variant == "shortage" else 8)
        ck(f"{variant} terminal ready", (rows[-1]["NSYRY"], rows[-1]["NSYMO"], rows[-1]["NSYMS"]),
           (count, 0, 0))
        for field in ["NFAIL", "NREPT", "NPMT", "NDAM", "NROBT", "NSYRP", "NSYPM"]:
            ck(f"{variant} zero {field}", sum(r[field] for r in rows), 0)
        stc, straws = table_rows(report, "report", "StockTotalResults")
        stock = [dict(zip(stc, r, strict=True)) for r in straws]
        ck(f"{variant} 32 aligned stock bins", [(r["STINT"], r["ETINT"]) for r in stock],
           [(i / 2, (i + 1) / 2) for i in range(32)])
        for field in ["NBO", "NDF", "NDD", "NDR", "NDP"]:
            ck(f"{variant} zero {field} stock", sum(r[field] for r in stock), 0)
    ck("fixed/continuous equal coarse state", [[r[k] for r in report_rows["fixed"]]
                                                for k in ["NSYRY", "NSYMA", "NSYMO", "NSYMS", "STACC"]],
       [[r[k] for r in report_rows["continuous"]]
        for k in ["NSYRY", "NSYMA", "NSYMO", "NSYMS", "STACC"]])

    old = HERE.parent / "A05-continuous-baseline-v1.0.0"
    failed = old / "runs" / "a05-continuous-four-hour-v100-ssh-20260930-01"
    ck("excluded v1.0.0 input SHA", sha(old / "native-continuous.json"),
       "260c9508c5c39ce0d31441510b73084c563e4000f3870c105eb769e83d88fef8")
    oldlog = (failed / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("excluded #335 rejection", "(error #335) Out and return time fractions (TFOUT and TFRET) are not allowed"
       in oldlog and "Errors: 1" in oldlog, True)
    ck("excluded invalid SXO and no report", ((failed / "model.sxo").stat().st_size,
        (failed / "report-raw.json").exists()), (4, False))
    oldclosure = json.loads((failed / "closure.json").read_text(encoding="utf-8-sig"))
    ck("excluded closure records failure", oldclosure["error"], "calc output model.sxo absent/empty")

    result = {"schema": "simlox-a05-continuous-author-validation/v1", "case_id": "A05",
              "version": "1.0.1-candidate", "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks),
              "failed_count": sum(not c["passed"] for c in checks), "checks": checks,
              "scope": "three_run_fixed_continuous_initial_shortage_cli",
              "publication_state": "not_published"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ["passed", "passed_count", "failed_count"]}))
    if not result["passed"]:
        print([c["name"] for c in checks if not c["passed"]])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
