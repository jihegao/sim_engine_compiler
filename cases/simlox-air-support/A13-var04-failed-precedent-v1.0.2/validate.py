"""Author read-only replay of sealed A13.var04 failed-precedent evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A13-start-dependence-v1.0.0" / "dependent-input.json"
RUNS = {v: HERE / "runs" / f"a13-var04-{v}-v102-20261001-01"
        for v in ("failure-control", "failure-dependency")}
OUT = HERE / "review" / "author-validation-2026-10-01.json"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
CONTRACT_SHA = "c40536f52028b94b1639f300d723be15de25948fd7da4b08281f76b11e159012"
DIFF_SHA = "1ef7ccd2227c82046e01747d07ca3fa11bdc3970ac695b2e6ce62d991bb170bb"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, table_name: str, root: str) -> list[dict]:
    tab, = (t for t in doc[root]["tables"] if t["name"] == table_name)
    names = [c["name"] for c in tab["columns"]]
    return [dict(zip(names, record, strict=True))
            for instance in tab["instances"] for record in instance["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, value: bool) -> None:
        checks.append({"name": name, "passed": bool(value)})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("frozen contract", sha(HERE / "contract.json") == CONTRACT_SHA)
    ck("accepted parent", sha(PARENT) == PARENT_SHA == contract["parent"]["input_sha256"])
    ck("frozen exact diff", sha(HERE / "exact-diff.json") == DIFF_SHA == contract["exact_diff_sha256"])
    ck("installed manual", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["source"]["manual_sha256"])
    ck("installed dictionary", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["source"]["dictionary_sha256"])
    parent_tables = {t["name"]: t for t in read(PARENT)["model"]["tables"]}
    sources: dict[str, dict] = {}
    for variant in RUNS:
        path = HERE / f"{variant}-input.json"
        ck(f"{variant} frozen input", sha(path) == contract["inputs_sha256"][variant])
        doc = read(path)
        sources[variant] = doc
        child_tables = {t["name"]: t for t in doc["model"]["tables"]}
        ck(f"{variant} table topology", parent_tables.keys() == child_tables.keys())
        changed = {name: {"before": parent_tables[name]["instances"], "after": tab["instances"]}
                   for name, tab in child_tables.items() if tab != parent_tables[name]}
        ck(f"{variant} exact parent delta", changed == diff["variants"][variant]["changed_tables"])
        mission = {r["MTID"]: r for r in rows(doc, "MissionType", "model")}
        ck(f"{variant} fixed mission and full success point", mission["RECON"]["MPAT"] is None
           and mission["RECON"]["MSUCPT"] == 1.0 and mission["FOLLOW"]["MPAT"] is None
           and mission["FOLLOW"]["MFF"] == 1e-6)
        system, = rows(doc, "System", "model")
        repair, = rows(doc, "SystemRepair", "model")
        ck(f"{variant} paired failure mechanism", system["FRT"] == 300000 and system["OPID"] == "OPHOURS"
           and repair["DIRPT"] == .5 and repair["STID"] == "BASE-01")
        ck(f"{variant} START row presence", len(rows(doc, "MissionDependence", "model")) ==
           (0 if variant.endswith("control") else 1))
    left = {t["name"]: t for t in sources["failure-control"]["model"]["tables"]}
    right = {t["name"]: t for t in sources["failure-dependency"]["model"]["tables"]}
    ck("matched pair only label and START row", {n for n in left if left[n] != right[n]} ==
       {"ProblemDescription", "MissionDependence"})

    reports: dict[str, dict] = {}
    for variant, run in RUNS.items():
        inv, close, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{variant} identity", inv["run_id"] == close["run_id"] == run.name and inv["variant"] == variant)
        ck(f"{variant} session SSH", inv["session_id"] == 0 and inv["ssh_connection_present"]
           and "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]])
        ck(f"{variant} GUI and mutex", inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1
           and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
        ck(f"{variant} invocation seal", sha(run / "invocation.json") == close["invocation_sha256"])
        ck(f"{variant} closure success", close["error"] is None and close["scope"] == "start_dependency_failed_precedent")
        hashes = close["source_hashes_before"]
        ck(f"{variant} stable source hashes", hashes == close["source_hashes_after"])
        ck(f"{variant} pinned source/executable", (hashes["input"], hashes["parent"], hashes["contract"],
            hashes["exact_diff"], hashes["simlox_exe"]) ==
           (contract["inputs_sha256"][variant], PARENT_SHA, CONTRACT_SHA, DIFF_SHA, EXE_SHA))
        for key, name in (("builder", "build.py"), ("diff_checker", "describe_diff.py"),
                          ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
            ck(f"{variant} {key} seal", hashes[key] == sha(HERE / name))
        ck(f"{variant} ordered steps", [s["name"] for s in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"])
        ck(f"{variant} guarded steps", all(s["exit_code"] == 0 and s["gui_preserved"]
           and s["status"] == ("calc_observed" if s["name"] == "calc" else "completed") for s in steps))
        ck(f"{variant} raw file set", set(close["raw"]) == {p.name for p in run.iterdir() if p.is_file()} -
           {"invocation.json", "closure.json"})
        for name, item in close["raw"].items():
            path = run / name
            ck(f"{variant} raw {name}", path.stat().st_size == item["bytes"] and sha(path) == item["sha256"])
        ck(f"{variant} copied input", sha(run / "input.json") == contract["inputs_sha256"][variant])
        roundtrip = read(run / "roundtrip-validation.json")
        count = 14 if variant.endswith("control") else 15
        ck(f"{variant} roundtrip checker", roundtrip["passed"] and not roundtrip["differences"]
           and len(roundtrip["populated_tables"]) == count)
        before = populated(sources[variant])
        after = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{variant} exact business rows", len(before) == count and
           all(after.get(name) == tab for name, tab in before.items()))
        calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{variant} conversion", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", calc) ==
           [("0", "2", "0")] and sorted(re.findall(r"warning #(\d+)", calc)) == ["108", "126"])
        ck(f"{variant} valid outputs", all((run / name).stat().st_size > 1000 for name in
           ("model.sxo", "model.log", "report-raw.json")))
        event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        report = parse_native(run / "report-raw.json")
        reports[variant] = report
        ck(f"{variant} matched RECON failure", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in event
           and "Time: 9.8829 <RECON,TEACH-UNIT,0,0,0> mission aborted:" in event
           and "Time: 10.8829 <RECON,TEACH-UNIT,0,0,0> aborted mission completed:" in event
           and "<RECON,TEACH-UNIT,0,0,0> mission success:" not in event)
        ck(f"{variant} FOLLOW assigned before return", "Time: 9 <FOLLOW,TEACH-UNIT,0,0,1> mission allocates system: <TEACH-AIR-01,1>" in event)
        ck(f"{variant} direct repair", "Time: 10.8829  system DIRP task 0 on <TEACH-AIR-01,0> started" in event
           and "Time: 11.3829  system DIRP task 0 on <TEACH-AIR-01,0> completed" in event)
        if variant.endswith("control"):
            ck("control FOLLOW starts and succeeds", "Time: 10 <FOLLOW,TEACH-UNIT,0,0,1> mission starting, duration: 2" in event
               and "Time: 12 <FOLLOW,TEACH-UNIT,0,0,1> mission success:" in event)
        else:
            ck("START FOLLOW cancels at failed return", "Time: 10.8829 <FOLLOW,TEACH-UNIT,0,0,1> mission cancelled:" in event
               and "<FOLLOW,TEACH-UNIT,0,0,1> mission starting," not in event
               and "<FOLLOW,TEACH-UNIT,0,0,1> mission success:" not in event)
        summary, = rows(report, "ResultSummary", "report")
        ck(f"{variant} summary start/success fractions", summary["MSTF"] == (1 if variant.endswith("control") else .5)
           and summary["MSUF"] == (.5 if variant.endswith("control") else 0))
        system, stock = rows(report, "SystemResults", "report"), rows(report, "StockTotalResults", "report")
        ck(f"{variant} 48 bins", len(system) == len(stock) == 48)
        for i, (sy, st) in enumerate(zip(system, stock, strict=True)):
            lo, hi = i / 2, (i + 1) / 2
            ck(f"{variant} bin {i} aligned", (sy["STINT"], sy["ETINT"], st["STINT"], st["ETINT"]) ==
               (lo, hi, lo, hi))
            ck(f"{variant} bin {i} aircraft conservation", abs(sy["NSYA"] + sy["NSYRP"] - 2) < 1e-5 and
               abs(sy["NSYRY"] + sy["NSYMA"] + sy["NSYRP"] - 2) < 1e-5)
            ck(f"{variant} bin {i} no stock demand", all(st[k] == 0 for k in
               ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
            ck(f"{variant} bin {i} no unrelated activity", all(sy[k] == 0 for k in
               ("NPMT", "NDAM", "NSYPM", "NROBT", "NRCFG")))
        ck(f"{variant} one failure and repair", sum(s["NFAIL"] for s in system) == 1
           and sum(s["NREPT"] for s in system) == 1
           and abs(sum(s["NSYRP"] * .5 for s in system) - .5) < 1e-5)
        expected_op = 4.8829 if variant.endswith("control") else 2.8829
        ck(f"{variant} operating hours", abs(sum(s["NSYMO"] * .5 for s in system) - expected_op) < 1e-4)
        ck(f"{variant} terminal ready", system[-1]["NSYRY"] == 2 and system[-1]["NSYMA"] == 0)
    control, dependent = (rows(reports[v], "SystemResults", "report") for v in RUNS)
    for i, (c, d) in enumerate(zip(control, dependent, strict=True)):
        expected = 1 if 10 <= i / 2 < 12 else 0
        ck(f"paired bin {i} operating delta", abs(c["NSYMO"] - d["NSYMO"] - expected) < 1e-5)
        ck(f"paired bin {i} same failures and repairs", (c["NFAIL"], c["NREPT"], c["NSYRP"]) ==
           (d["NFAIL"], d["NREPT"], d["NSYRP"]))
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a13-var04-failed-precedent-v102-author-validation/v1",
              "passed": not failed, "check_count": len(checks), "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failures": failed,
              "run_ids": {v: r.name for v, r in RUNS.items()},
              "decision": "bounded_failed_precedent_go_if_passed",
              "limits": ["One fixed seed, one failed RECON and one explicit START row.",
                         "Unfinished, absent, multiple and cross-unit precedents unverified."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failed": failed[:8]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
