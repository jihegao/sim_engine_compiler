"""Replay sealed A04 native evidence against its frozen two-day contract."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, PROFILE_SOURCE, PROFILE_SHA, CHILD, build, sha
from check_roundtrip import parse_native

RUN_ID = "a04-two-day-form-v100-ssh-20260930-01"
RUN = HERE / "runs" / RUN_ID
OUT = HERE / "review" / "author-two-day-validation-2026-09-30.json"
INPUT_SHA = "9e2eac17e0408903e099e6ce054ebf4b91db1ca79036afe29638ee8a41d40711"
DIFF_SHA = "111cf01bb3cc648cb476b68b015cc507a6582dc7e20ff2cd59cec88344211d40"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
STARTS = [8, 20, 32, 44]
ENDS = [10, 22, 34, 46]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(doc: dict, name: str, root: str) -> tuple[list[str], list[list]]:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {name} table")
    t = matches[0]
    if len(t["instances"]) != 1:
        raise ValueError(f"expected one {name} instance")
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    diff = json.loads((HERE / "parent-diff.json").read_text(encoding="utf-8"))
    child = json.loads(CHILD.read_text(encoding="utf-8"))
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE_SOURCE.read_text(encoding="utf-8"))
    ck("accepted A03 source SHA", digest(PARENT), PARENT_SHA)
    ck("accepted A09 profile SHA", digest(PROFILE_SOURCE), PROFILE_SHA)
    ck("frozen A04 source SHA", digest(CHILD), INPUT_SHA)
    ck("contract input SHA", contract["native_input_sha256"], INPUT_SHA)
    ck("contract identity and state", (contract["case_id"], contract["case_version"], contract["publication_state"]),
       ("A04", "1.0.0-candidate", "not_published"))
    ck("builder reproduces child", build(), child)
    ck("exact diff SHA", digest(HERE / "parent-diff.json"), DIFF_SHA)
    ck("exact changed tables", sorted(diff["changed_tables_only"]),
       sorted(["ProblemDescription", "Control", "OperationProfile", "Unit", "ResultCollection"]))
    ck("unchanged parent tables", diff["unchanged_table_count"], 26)
    parent_tables = {t["name"]: t for t in parent["model"]["tables"]}
    child_tables = {t["name"]: t for t in child["model"]["tables"]}
    ck("exact parent table names", sorted(parent_tables), sorted(child_tables))
    ck("diff reproduces every table", all((diff["changed_tables"][n]["parent"] == parent_tables[n]
                                            and diff["changed_tables"][n]["child"] == child_tables[n])
                                           if n in diff["changed_tables"] else parent_tables[n] == child_tables[n]
                                           for n in parent_tables), True)
    pcols, prows = rows(child, "OperationProfile", "model")
    ck("A09 profile copied exactly", prows, rows(profile, "OperationProfile", "model")[1])
    mcols, mrows = rows(child, "MissionType", "model")
    dcols, drows = rows(child, "SystemDeployment", "model")
    ck("minimum and nominal aircraft", (mrows[0][mcols.index("MNOS")], mrows[0][mcols.index("NOS")]), (2, 2))
    ck("deployed aircraft", drows[0][dcols.index("QTYPS")], 2)
    ck("copied input SHA", digest(RUN / "input.json"), INPUT_SHA)
    ck("copied input identity", (RUN / "input.json").read_bytes() == CHILD.read_bytes(), True)

    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    ck("invocation run identity", (invocation["case_id"], invocation["run_id"]), ("A04", RUN_ID))
    ck("invocation input/parent/profile", (invocation["input_sha256"], invocation["parent_sha256"],
                                          invocation["profile_source_sha256"]), (INPUT_SHA, PARENT_SHA, PROFILE_SHA))
    ck("SSH session 0", (invocation["session_id"], invocation["ssh_connection_present"]), (0, True))
    ck("sshd ancestor", "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]], True)
    ck("host-wide mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    ck("GUI PID and active session", (invocation["gui"]["pid"], invocation["gui"]["session_id"]), (13340, 1))
    ck("installed executable SHA", invocation["simlox_exe_sha256"], EXE_SHA)
    ck("raw closure invocation seal", closure["invocation_sha256"], digest(RUN / "invocation.json"))
    ck("closure no error", closure["error"], None)
    ck("source hashes stable", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("source input/parent/profile seals", [closure["source_hashes_before"][x] for x in
                                              ["input", "parent", "profile_source"]],
       [INPUT_SHA, PARENT_SHA, PROFILE_SHA])
    for name, path in [("contract", HERE / "contract.json"), ("builder", HERE / "build.py"),
                       ("checker", HERE / "check_roundtrip.py"), ("runner_script", HERE / "run_native_ssh.ps1")]:
        ck(f"source {name} seal", closure["source_hashes_before"][name], digest(path))
    ck("raw closure file set", sorted(closure["raw"]), sorted(p.name for p in RUN.iterdir()
                                                        if p.is_file() and p.name not in {"closure.json", "invocation.json"}))
    for name, stamp in sorted(closure["raw"].items()):
        ck(f"raw {name} size/SHA", (stamp["bytes"], stamp["sha256"]),
           ((RUN / name).stat().st_size, digest(RUN / name)))
    ck("five completed steps", [(x["name"], x["status"], x["exit_code"], x["gui_preserved"])
                                for x in steps],
       [(name, "completed", 0, True) for name in
        ["import", "export", "calc", "jsonreport", "check_import_export"]])
    ck("roundtrip 13 source tables", (roundtrip["passed"], len(roundtrip["populated_tables"]),
                                      roundtrip["source_sha256"]), (True, 13, INPUT_SHA))
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion error/warning counts", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+)", log),
       [("0", "2")])
    ck("warning codes", sorted(re.findall(r"warning #(\d+)", log)), ["108", "126"])
    ck("report export completed", "Generating Json-report" in
       (RUN / "report-export.log").read_text(encoding="utf-8-sig", errors="replace"), True)

    events = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    ck("four distinct mission starts", sum("mission starting" in line for line in events), 4)
    ck("four distinct mission successes", sum("mission success:" in line for line in events), 4)
    ck("four mission completions", sum("mission completed:" in line for line in events), 4)
    ck("no cancel/abort/failure", any(re.search(r"mission (?:cancel|abort)|critical random failure added", line, re.I)
                                      for line in events), False)
    for j, (start, end) in enumerate(zip(STARTS, ENDS, strict=True)):
        label = f"<BASIC-MISSION,TEACH-UNIT,0,0,{j}>"
        marked = [(i, line) for i, line in enumerate(events) if label in line]
        # The unit order line has no mission instance label, so check separately.
        ck(f"wave {j} order at {start-1}", sum(f"Time: {start-1} <TEACH-UNIT> mission ordered" in x for x in events), 1)
        ck(f"wave {j} allocates two aircraft", sorted(re.findall(r"<TEACH-AIR-01,([01])>", "\n".join(
            line for _, line in marked if "mission allocates system" in line))), ["0", "1"])
        ck(f"wave {j} starts on time as formation", sum(
            f"Time: {start} {label} mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in line
            for _, line in marked), 1)
        ck(f"wave {j} success on time", sum(f"Time: {end} {label} mission success:" in line for _, line in marked), 1)
        ck(f"wave {j} completion includes both", sum(
            f"Time: {end} {label} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in line
            for _, line in marked), 1)
        ck(f"wave {j} both return to base", sorted(re.findall(r"System arrives <TEACH-AIR-01,([01])>, mission success",
            "\n".join(x for x in events if x.startswith(f"Time: {end} ")))), ["0", "1"])
    ck("terminal day marker", any(line.startswith("Time: 48  Start of day") for line in events), True)

    report = parse_native(RUN / "report-raw.json")
    ck("nonempty report table names", sorted(t["name"] for t in report["report"]["tables"]
                                           if any(i["rows"] for i in t["instances"])),
       ["ProblemDescription", "ResultSummary", "StockTotalResults", "SystemResults"])
    scols, summary = rows(report, "ResultSummary", "report")
    sm = dict(zip(scols, summary[0], strict=True))
    ck("one repetition and 48-hour stop", (sm["NREP"], sm["RTILW"], sm["RTIUP"]), (1, 0, 48))
    ck("summary mission success and fulfillment", (sm["MTMF"], sm["MSTF"], sm["MSUF"], sm["STMF"]),
       (1, 1, 1, 1))
    c, raw_rows = rows(report, "SystemResults", "report")
    system = [dict(zip(c, row, strict=True)) for row in raw_rows]
    ck("96 aligned system bins", [(r["STINT"], r["ETINT"]) for r in system],
       [(i / 2, (i + 1) / 2) for i in range(96)])
    ck("two aircraft available each bin", [r["NSYA"] for r in system], [2] * 96)
    mission_indices = {i for start in STARTS for i in range(2 * start, 2 * (start + 2))}
    prep_indices = {i for start in STARTS for i in range(2 * (start - 1), 2 * start)}
    ck("mission operation two aircraft in exact bins", [r["NSYMO"] for r in system],
       [2 if i in mission_indices else 0 for i in range(96)])
    ck("mission assigned/prep two aircraft", [r["NSYMA"] for r in system],
       [2 if i in prep_indices | mission_indices else 0 for i in range(96)])
    ck("ready aircraft state", [r["NSYRY"] for r in system],
       [0 if i in prep_indices | mission_indices else 2 for i in range(96)])
    ck("mission count in exact bins", [r["FTMO"] for r in system],
       [1 if i in mission_indices else 0 for i in range(96)])
    ck("system time accepted", sum(r["STACC"] for r in system) * 0.5, 16.0)
    for field in ["NFAIL", "NREPT", "NPMT", "NDAM", "NROBT", "NSYRP", "NSYPM", "NSYWR", "NSYWI"]:
        ck(f"zero {field} report", sum(r[field] for r in system), 0)
    ck("terminal two ready", (system[-1]["NSYRY"], system[-1]["NSYMO"]), (2, 0))
    stock_cols, raw_stock = rows(report, "StockTotalResults", "report")
    stock = [dict(zip(stock_cols, row, strict=True)) for row in raw_stock]
    ck("96 aligned stock bins", [(r["STINT"], r["ETINT"]) for r in stock],
       [(i / 2, (i + 1) / 2) for i in range(96)])
    for field in ["NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"]:
        ck(f"zero {field} stock", sum(r[field] for r in stock), 0)

    result = {"schema": "simlox-a04-two-day-formation-author-validation/v1", "case_id": "A04",
              "run_id": RUN_ID, "passed": all(x["passed"] for x in checks),
              "passed_count": sum(x["passed"] for x in checks),
              "failed_count": sum(not x["passed"] for x in checks), "checks": checks,
              "scope": "one_fixed_seed_four_wave_two_aircraft_native_cli",
              "publication_state": "not_published"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ["run_id", "passed", "passed_count", "failed_count"]}))
    if not result["passed"]:
        print([x["name"] for x in checks if not x["passed"]])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
