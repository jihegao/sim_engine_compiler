"""Author replay of the two frozen G03.var04 native arms."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA, make
from check_roundtrip import native_json, populated

IDS = {"grandchild": "g03-var04-grandchild-v100-ssh-20261003-01",
       "invalid-reference": "g03-var04-invalid-reference-v100-ssh-20261003-01"}
OUT = HERE / "author-validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(doc: dict, name: str) -> list:
    return tables(doc)[name]["instances"][0]["rows"]


def report_rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    checks = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    parent = read(PARENT)
    ck("contract identity", (contract["case_id"], contract["variant_id"]), ("G03", "G03.var04"))
    ck("accepted parent input", sha(PARENT), PARENT_SHA)
    parent_closure = HERE.parent / contract["accepted_parent"]["package"] / "runs" / contract["accepted_parent"]["run_id"] / "closure.json"
    ck("accepted parent closure", sha(parent_closure), contract["accepted_parent"]["native_closure_sha256"])
    ck("exact diff seal", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("exact diff parent", diff["parent_sha256"], PARENT_SHA)
    ck("arm set", set(diff["arms"]), set(ARMS))
    docs = {}
    for arm in ARMS:
        doc = read(HERE / f"{arm}-input.json")
        docs[arm] = doc
        ck(f"{arm} input seal", sha(HERE / f"{arm}-input.json"), contract["input_sha256"][arm])
        ck(f"{arm} builder replay", make(arm), doc)
        before, after = tables(parent), tables(doc)
        changed = {name: {"before": before[name], "after": after[name]} for name in before if before[name] != after[name]}
        ck(f"{arm} four-table delta", sorted(changed), ["ProblemDescription", "System", "SystemDeployment", "SystemRepair"])
        ck(f"{arm} exact diff rows", diff["arms"][arm]["changed"], changed)
        ck(f"{arm} diff input seal", diff["arms"][arm]["input_sha256"], contract["input_sha256"][arm])
        ck(f"{arm} deployment", rows(doc, "SystemDeployment"),
           [["TEACH-VAR-GRAND", "TEACH-UNIT", 1, 1, None, None, None],
            ["TEACH-AIR-01", "TEACH-BASE-UNIT", 1, 1, None, None, None]])
        ck(f"{arm} base and variant unchanged", rows(doc, "System")[:2], rows(parent, "System"))
        ck(f"{arm} item structure unchanged", rows(doc, "ItemStructure"), rows(parent, "ItemStructure"))
        ck(f"{arm} source schedule unchanged", (rows(doc, "Operations"), rows(doc, "OperationProfile")),
           (rows(parent, "Operations"), rows(parent, "OperationProfile")))
        ck(f"{arm} BSID", rows(doc, "System")[2][9], "TEACH-VAR-ADD" if arm == "grandchild" else "TEACH-NO-SUCH")

    valid, invalid = docs["grandchild"], docs["invalid-reference"]
    difference = {n: (tables(valid)[n], tables(invalid)[n]) for n in tables(valid) if tables(valid)[n] != tables(invalid)[n]}
    ck("arms differ in System and description", sorted(difference), ["ProblemDescription", "System"])
    v_system, i_system = rows(valid, "System"), rows(invalid, "System")
    ck("only System.BSID differs", (v_system[:2], v_system[2][:9], v_system[2][10:]),
       (i_system[:2], i_system[2][:9], i_system[2][10:]))

    for arm in ARMS:
        run = HERE / "runs" / IDS[arm]
        inv, closure, steps, rt = (read(run / n) for n in
                                   ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        prefix = f"{arm}: "
        ck(prefix + "run identity", (inv["run_id"], inv["arm"], closure["run_id"], closure["arm"]),
           (IDS[arm], arm, IDS[arm], arm))
        ck(prefix + "session-zero SSH", (inv["session_id"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]], inv["execution_mode"]),
           (0, True, "session0_ssh_cli"))
        ck(prefix + "GUI and queue", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
           (13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(prefix + "registry restored", (inv["prelife_log_option_before"], closure["prelife_log_option_after"]), ("NO", "NO"))
        ck(prefix + "stable sources", closure["source_hashes_before"], closure["source_hashes_after"])
        sources = closure["source_hashes_before"]
        paths = {"input": HERE / f"{arm}-input.json", "parent": PARENT, "parent_closure": parent_closure,
                 "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json", "builder": HERE / "build.py",
                 "diff_builder": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1"}
        for key, path in paths.items():
            ck(prefix + f"source seal {key}", sources[key], sha(path))
        ck(prefix + "installed source pins", (sources["exe"], sources["manual"], sources["dictionary"]),
           (contract["source"]["exe_sha256"], contract["source"]["manual_sha256"], contract["source"]["dictionary_sha256"]))
        ck(prefix + "invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
        ck(prefix + "no runner error", closure["error"], None)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(prefix + f"raw seal {name}", (path.stat().st_size, sha(path)), (seal["bytes"], seal["sha256"]))
        ck(prefix + "roundtrip checker", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], contract["input_sha256"][arm]))
        authored, exported = populated(docs[arm]), populated(native_json(run / "roundtrip-raw.json"))
        ck(prefix + "18 populated source tables", len(authored), 18)
        for name, value in authored.items():
            ck(prefix + f"native rows {name}", exported.get(name), value)
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        if arm == "grandchild":
            ck(prefix + "outcome", closure["native_outcome"], "zero_error_reviewed_warnings")
            ck(prefix + "guarded steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
               [(n, "completed", 0, True) for n in ("import", "export", "calc", "jsonreport", "check_import_export")])
            ck(prefix + "conversion counts", marker.groups() if marker else None, ("0", "2", "0"))
            ck(prefix + "reviewed warning codes", re.findall(r"\(warning #(\d+)\)", run_log), ["108", "2053"])
            ck(prefix + "zero-rate item warning", "rec 1: (warning #2053) FRT is zero for: TEACH-LRU-BASE" in run_log, True)
            ck(prefix + "no converter error", re.findall(r"\(error #(\d+)\)", run_log), [])
            log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
            created = re.findall(r"^Time: (\d+) <BASIC-MISSION,([^,]+),[^>]+> mission created:", log, re.M)
            ck(prefix + "six per-unit mission creations", created,
               [(str(t), unit) for t in (7, 19, 31) for unit in ("TEACH-UNIT", "TEACH-BASE-UNIT")])
            allocations = re.findall(r"^Time: (\d+) <BASIC-MISSION,([^,]+),[^>]+> mission allocates system: <([^>]+)>$", log, re.M)
            ck(prefix + "separate assignments", allocations,
               [(str(t), unit, sys) for t in (7, 19, 31) for unit, sys in
                (("TEACH-UNIT", "TEACH-VAR-GRAND,0"), ("TEACH-BASE-UNIT", "TEACH-AIR-01,1"))])
            ck(prefix + "inherited added-LRU failure", re.findall(r"^Time: ([\d.]+) <TEACH-VAR-GRAND,0> critical random failure added", log, re.M), ["9.8829"])
            ck(prefix + "failure item and path", "subitem failed: <TEACH-LRU-ADD,0,1> connection path: TEACH-VAR-GRAND - TEACH-VAR-GRAND - TEACH-LRU-ADD" in log, True)
            ck(prefix + "base has no failure", re.findall(r"<TEACH-AIR-01,1> critical random failure added", log), [])
            ck(prefix + "grandchild abort", re.findall(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,[^>]+> mission aborted:", log, re.M), ["9.8829"])
            ck(prefix + "grandchild two successes", re.findall(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,[^>]+> mission success:", log, re.M), ["22", "34"])
            ck(prefix + "base three successes", re.findall(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-BASE-UNIT,[^>]+> mission success:", log, re.M), ["10", "22", "34"])
            phrases = {"spare demand": "Time: 10 <TEACH-LRU-ADD,0,BASE-01,0> Item demand arrives from pos <TEACH-VAR-GRAND,BASE-01,0>",
                       "spare taken": "Time: 10 <TEACH-LRU-ADD,0,BASE-01,0> Take replacement item <TEACH-LRU-ADD,0,0> from stock",
                       "system replacement complete": "Time: 10.5  system SURP task 0 on <TEACH-VAR-GRAND,0> completed",
                       "item repair complete": "Time: 11.25  item DIRP task 1 on <TEACH-LRU-ADD,0,1> completed",
                       "stock replenished": "Time: 11.25 <TEACH-LRU-ADD,0,BASE-01,0> Put back replacement item <TEACH-LRU-ADD,0,1> to stock"}
            for name, phrase in phrases.items():
                ck(prefix + name, phrase in log, True)
            ck(prefix + "terminal unit identities", ("Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-VAR-GRAND,0>" in log,
                                                     "Time: 34 <TEACH-BASE-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,1>" in log), (True, True))
            report = native_json(run / "report-raw.json")
            ck(prefix + "report tables", {t["name"] for t in report["report"]["tables"]},
               {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
            summary, systems, stocks = (report_rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
            ck(prefix + "one rep and horizon", (summary[0]["NREP"], summary[0]["RTILW"], summary[0]["RTIUP"]), (1, 0, 36))
            ck(prefix + "five of six mission success", math.isclose(summary[0]["MSUF"], 5 / 6, abs_tol=1e-6), True)
            ck(prefix + "72 aligned System bins", [(r["STINT"], r["ETINT"]) for r in systems], [(i / 2, (i + 1) / 2) for i in range(72)])
            ck(prefix + "72 aligned Stock bins", [(r["STINT"], r["ETINT"]) for r in stocks], [(i / 2, (i + 1) / 2) for i in range(72)])
            ck(prefix + "one failure and replacement", (sum(r["NFAIL"] or 0 for r in systems), sum(r["NREPT"] or 0 for r in systems)), (1, 1))
            ck(prefix + "terminal two ready", (systems[-1]["NSYRY"], systems[-1]["NSYRP"], systems[-1]["NSYPM"]), (2, 0, 0))
            ck(prefix + "one demand zero backorder", (sum(r["NDF"] or 0 for r in stocks), sum(r["NBO"] or 0 for r in stocks)), (1, 0))
            ck(prefix + "no PM", (sum(r["NPMS"] or 0 for r in systems), sum(r["NPMT"] or 0 for r in systems)), (0, 0))
        else:
            ck(prefix + "diagnostic outcome", closure["native_outcome"], "converter_error_requires_review")
            ck(prefix + "guarded diagnostic steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
               [("import", "completed", 0, True), ("export", "completed", 0, True),
                ("calc", "diagnostic_converter_error", 0, True), ("check_import_export", "completed", 0, True)])
            ck(prefix + "conversion counts", marker.groups() if marker else None, ("1", "3", "0"))
            ck(prefix + "explicit BSID error", re.findall(r"^rec 3: \(error #(\d+)\) Unknown base system identifier \(BSID\):\s+(\S+)", run_log, re.M), [("18", "TEACH-NO-SUCH")])
            ck(prefix + "diagnostic warnings", re.findall(r"\(warning #(\d+)\)", run_log), ["108", "126", "380"])
            ck(prefix + "no behavioral report", (closure["report_present"], (run / "report-raw.json").exists(), (run / "model.log").exists()), (False, False, False))
            ck(prefix + "four-byte SXO", (closure["sxo_bytes"], (run / "model.sxo").stat().st_size), (4, 4))

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g03-var04-author-native-replay/v1", "case_id": "G03", "variant_id": "G03.var04",
              "run_ids": IDS, "passed": not failed, "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "failed": failed, "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "observation": {"valid_failure_hour": 9.8829, "valid_grandchild_missions": "abort, success, success",
                              "valid_base_missions": "success, success, success", "valid_spare_hour": 10,
                              "valid_system_ready_hour": 10.5, "valid_item_restock_hour": 11.25,
                              "invalid_converter_error_code": 18, "invalid_reference": "TEACH-NO-SUCH"},
              "limits": contract["limits"]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
