"""Replay frozen G03.var03 source, native seals, identities and aggregate report."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, make
from check_roundtrip import native_json, populated

RUN_ID = "g03-var03-simultaneous-v100-ssh-20261003-01"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = HERE.parent / "G03-effective-item-contrast-v1.0.0" / "runs" / "g03-effective-add-extra-v100-20261001-01"
OUT = HERE / "author-validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(doc: dict, name: str) -> list[list]:
    return tables(doc)[name]["instances"][0]["rows"]


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    parent, child = read(PARENT), read(HERE / "native-input.json")
    ck("contract identity", (contract["case_id"], contract["variant_id"]), ("G03", "G03.var03"))
    ck("parent input pin", sha(PARENT), PARENT_SHA)
    ck("parent closure pin", sha(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"])
    ck("child input pin", sha(HERE / "native-input.json"), contract["input"]["sha256"])
    ck("builder replay", make(), child)
    ck("diff pin", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    before, after = tables(parent), tables(child)
    changed = sorted(n for n in after if before[n] != after[n])
    ck("exact four-table delta", changed, ["Operations", "ProblemDescription", "SystemDeployment", "Unit"])
    ck("diff exact rows", diff["changed"], {n: {"before": before[n], "after": after[n]} for n in changed})
    ck("diff source pins", (diff["parent_sha256"], diff["input_sha256"]), (PARENT_SHA, contract["input"]["sha256"]))
    ck("base and variant deployment", rows(child, "SystemDeployment"),
       [["TEACH-VAR-ADD", "TEACH-UNIT", 1, 1, None, None, None],
        ["TEACH-AIR-01", "TEACH-BASE-UNIT", 1, 1, None, None, None]])
    ck("separate schedule binding", rows(child, "Operations"),
       [["TEACH-UNIT", "BASIC-SCHEDULE", None], ["TEACH-BASE-UNIT", "BASIC-SCHEDULE", None]])
    ck("unchanged item and BSID", (rows(child, "Item"), rows(child, "ItemStructure"), rows(child, "System")),
       (rows(parent, "Item"), rows(parent, "ItemStructure"), rows(parent, "System")))

    inv, closure, steps, rt = (read(RUN / n) for n in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    ck("run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
       (RUN_ID, "simultaneous-base-variant", RUN_ID, "simultaneous-base-variant"))
    ck("session-zero SSH", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
       (0, True, "session0_ssh_cli"))
    ck("GUI and queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
    ck("stable sources", closure["source_hashes_before"], closure["source_hashes_after"])
    source = closure["source_hashes_before"]
    paths = {"input": HERE / "native-input.json", "parent": PARENT, "parent_closure": PARENT_RUN / "closure.json",
             "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
             "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py",
             "runner": HERE / "run_native_ssh.ps1"}
    for key, path in paths.items():
        ck(f"source seal {key}", source[key], sha(path))
    ck("installed source pins", (source["exe"], source["manual"], source["dictionary"]),
       (contract["source"]["exe_sha256"], contract["source"]["manual_sha256"], contract["source"]["dictionary_sha256"]))
    ck("invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    ck("outcome", (closure["error"], closure["native_outcome"]), (None, "zero_error_reviewed_warnings"))
    ck("five guarded steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("13 raw files", len(closure["raw"]), 13)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
    ck("roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
       (True, [], contract["input"]["sha256"]))
    authored, exported = populated(child), populated(native_json(RUN / "roundtrip-raw.json"))
    ck("18 populated source tables", len(authored), 18)
    for name, value in authored.items():
        ck(f"native rows {name}", exported.get(name), value)

    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    ck("conversion counts", marker.groups() if marker else None, ("0", "2", "0"))
    ck("warning codes", re.findall(r"\(warning #(\d+)\)", run_log), ["108", "2053"])
    ck("zero-rate item warning", "rec 1: (warning #2053) FRT is zero for: TEACH-LRU-BASE" in run_log, True)
    ck("no converter errors", re.findall(r"\(error #(\d+)\)", run_log), [])
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    created = re.findall(r"^Time: (\d+) <BASIC-MISSION,([^,]+),[^>]+> mission created:", log, re.M)
    ck("six per-unit mission creations", created,
       [(str(t), unit) for t in (7, 19, 31) for unit in ("TEACH-UNIT", "TEACH-BASE-UNIT")])
    allocations = re.findall(r"^Time: (\d+) <BASIC-MISSION,([^,]+),[^>]+> mission allocates system: <([^>]+)>$", log, re.M)
    ck("stable unit-system assignments", allocations,
       [(str(t), unit, sys) for t in (7, 19, 31) for unit, sys in
        (("TEACH-UNIT", "TEACH-VAR-ADD,0"), ("TEACH-BASE-UNIT", "TEACH-AIR-01,1"))])
    ck("variant added-LRU failure", re.findall(r"^Time: ([\d.]+) <TEACH-VAR-ADD,0> critical random failure added", log, re.M), ["9.8829"])
    ck("failure item and path", "subitem failed: <TEACH-LRU-ADD,0,1> connection path: TEACH-VAR-ADD - TEACH-VAR-ADD - TEACH-LRU-ADD" in log, True)
    ck("base has no failure", re.findall(r"<TEACH-AIR-01,1> critical random failure added", log), [])
    ck("variant abort", re.findall(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,[^>]+> mission aborted:", log, re.M), ["9.8829"])
    ck("variant two successes", re.findall(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,[^>]+> mission success:", log, re.M), ["22", "34"])
    ck("base three successes", re.findall(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-BASE-UNIT,[^>]+> mission success:", log, re.M), ["10", "22", "34"])
    for name, phrase in {"spare demand": "Time: 10 <TEACH-LRU-ADD,0,BASE-01,0> Item demand arrives from pos <TEACH-VAR-ADD,BASE-01,0>",
                         "spare taken": "Time: 10 <TEACH-LRU-ADD,0,BASE-01,0> Take replacement item <TEACH-LRU-ADD,0,0> from stock",
                         "system replacement complete": "Time: 10.5  system SURP task 0 on <TEACH-VAR-ADD,0> completed",
                         "item repair complete": "Time: 11.25  item DIRP task 1 on <TEACH-LRU-ADD,0,1> completed",
                         "stock replenished": "Time: 11.25 <TEACH-LRU-ADD,0,BASE-01,0> Put back replacement item <TEACH-LRU-ADD,0,1> to stock"}.items():
        ck(name, phrase in log, True)
    ck("terminal unit identities", ("Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-VAR-ADD,0>" in log,
                                      "Time: 34 <TEACH-BASE-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,1>" in log), (True, True))

    report = native_json(RUN / "report-raw.json")
    ck("report tables", {t["name"] for t in report["report"]["tables"]},
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary, systems, stocks = (report_rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("one rep and horizon", (summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"]), (1, 0, 36))
    ck("five of six mission success", math.isclose(summary[0]["MSUF"], 5 / 6, abs_tol=1e-6), True)
    ck("72 aligned System bins", [(r["STINT"], r["ETINT"]) for r in systems],
       [(i / 2, (i + 1) / 2) for i in range(72)])
    ck("72 aligned Stock bins", [(r["STINT"], r["ETINT"]) for r in stocks],
       [(i / 2, (i + 1) / 2) for i in range(72)])
    ck("one report failure and system replacement", (sum(r["NFAIL"] or 0 for r in systems), sum(r["NREPT"] or 0 for r in systems)), (1, 1))
    ck("terminal two systems ready", (systems[-1]["NSYRY"], systems[-1]["NSYRP"], systems[-1]["NSYPM"]), (2, 0, 0))
    ck("one stock demand, no backorders", (sum(r["NDF"] or 0 for r in stocks), sum(r["NBO"] or 0 for r in stocks)), (1, 0))
    ck("no PM events", (sum(r["NPMS"] or 0 for r in systems), sum(r["NPMT"] or 0 for r in systems)), (0, 0))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g03-var03-author-native-replay/v1", "case_id": "G03", "variant_id": "G03.var03",
              "run_id": RUN_ID, "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"variant_added_lru_failure_hour": 9.8829, "variant_missions": "abort, success, success",
                              "base_missions": "success, success, success", "spare_exchange_hour": 10,
                              "system_ready_hour": 10.5, "item_restock_hour": 11.25, "terminal_ready": 2},
              "limits": ["One seed and one replication of a base and one BSID add variant at one base.",
                         "Per-unit identities are in the event log; the report is aggregate.",
                         "No CBSID runtime change, simultaneous add/exclude, rate estimate, GUI visual or cross-engine claim."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
