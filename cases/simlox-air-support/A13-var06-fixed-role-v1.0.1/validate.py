"""Author replay of the sealed A13.var06 START Fixed-role matrix."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, VARIANTS, build
from check_roundtrip import parse_native, populated
from describe_diff import delta

RUNS = {v: HERE / "runs" / f"a13-var06-{v}-v101-20261001-01" for v in VARIANTS}
OUT = HERE / "review" / "author-validation-2026-10-01.json"
CONTRACT_SHA = "91c140b3ec55ea1f9290587570313f05ab695a09aebb4f625e26101803b62288"
DIFF_SHA = "8fe235546fa32d75dddf9d3609bea28fc4dc951f9391144b241744e7cf14a8d1"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
ACCEPTED = ("fixed-fixed", "prec-cont-control", "dep-cont-control", "dep-cont-dependency")


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

    def ck(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("contract frozen", sha(HERE / "contract.json") == CONTRACT_SHA)
    ck("parent accepted", sha(PARENT) == PARENT_SHA == contract["parent"]["input_sha256"])
    ck("exact diff frozen", sha(HERE / "exact-diff.json") == DIFF_SHA == contract["exact_diff_sha256"])
    ck("manual fingerprint", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["source"]["manual_sha256"])
    ck("dictionary fingerprint", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["source"]["dictionary_sha256"])
    parent_tables = {t["name"]: t for t in read(PARENT)["model"]["tables"]}
    sources: dict[str, dict] = {}
    for v in VARIANTS:
        path = HERE / f"{v}-input.json"
        ck(f"{v} source hash", sha(path) == contract["inputs_sha256"][v])
        doc = read(path)
        ck(f"{v} builder identity", doc == build(v))
        sources[v] = doc
        child_tables = {t["name"]: t for t in doc["model"]["tables"]}
        ck(f"{v} exact parsed diff", delta(parent_tables, child_tables) == diff["changed_tables"][v])
        roles = {r["MTID"]: r for r in rows(doc, "MissionType", "model")}
        continuous = "RECON" if v.startswith("prec-cont") else "FOLLOW" if v.startswith("dep-cont") else None
        for mission in ("RECON", "FOLLOW"):
            row = roles[mission]
            expected = ("CONTINUOUS", None, None) if mission == continuous else (None, .25, .25)
            ck(f"{v} {mission} role/travel", (row["MPAT"], row["TFOUT"], row["TFRET"]) == expected)
        ck(f"{v} dependency table presence", ("MissionDependence" in child_tables) == (not v.endswith("control")))
    for role in ("prec-cont", "dep-cont"):
        control = sources[f"{role}-control"]
        dependent = sources[f"{role}-dependency"]
        before = {t["name"]: t for t in control["model"]["tables"]}
        after = {t["name"]: t for t in dependent["model"]["tables"]}
        ck(f"{role} matched pair", set(delta(before, after)) == {"ProblemDescription", "MissionDependence"})

    reports: dict[str, dict] = {}
    events: dict[str, str] = {}
    for v, run in RUNS.items():
        invocation, closure, steps = (read(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        ck(f"{v} run identity", invocation["run_id"] == closure["run_id"] == run.name and invocation["variant"] == v)
        ck(f"{v} SSH ancestry", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0
           and invocation["ssh_connection_present"] and "sshd.exe" in [n.lower() for n in invocation["ssh_ancestor_names"]])
        ck(f"{v} GUI and mutex", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1
           and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
        ck(f"{v} invocation seal", sha(run / "invocation.json") == closure["invocation_sha256"])
        ck(f"{v} closure success", closure["error"] is None and closure["scope"] == "start_dependency_fixed_role_matrix")
        ck(f"{v} stable source fingerprints", closure["source_hashes_before"] == closure["source_hashes_after"])
        hashes = closure["source_hashes_before"]
        ck(f"{v} source/exe closure", (hashes["parent"], hashes["input"], hashes["contract"],
                                       hashes["exact_diff"], hashes["simlox_exe"]) ==
           (PARENT_SHA, contract["inputs_sha256"][v], CONTRACT_SHA, DIFF_SHA, EXE_SHA))
        for key, filename in (("builder", "build.py"), ("diff_checker", "describe_diff.py"),
                              ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
            ck(f"{v} {key} closure", hashes[key] == sha(HERE / filename))
        expected_steps = ["import", "export", "calc"] + (["jsonreport"] if v in ACCEPTED else []) + ["check_import_export"]
        ck(f"{v} ordered steps", [s["name"] for s in steps] == expected_steps)
        ck(f"{v} guarded steps", all(s["status"] == ("calc_observed" if s["name"] == "calc" else "completed")
                                   and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
        for name, item in closure["raw"].items():
            path = run / name
            ck(f"{v} raw {name}", path.stat().st_size == item["bytes"] and sha(path) == item["sha256"])
        ck(f"{v} copied input", sha(run / "input.json") == contract["inputs_sha256"][v])
        rt = read(run / "roundtrip-validation.json")
        count = 13 if v.endswith("control") else 14
        ck(f"{v} roundtrip checker", rt["passed"] and not rt["differences"] and len(rt["populated_tables"]) == count)
        before, after = populated(sources[v]), populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{v} source rows roundtrip", len(before) == count and all(after.get(name) == tab for name, tab in before.items()))
        log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{v} warnings", sorted(re.findall(r"warning #(\d+)", log)) == ["108", "126"])
        if v == "prec-cont-dependency":
            ck("non-Fixed precedent converter count", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log) == [("1", "2", "0")])
            ck("non-Fixed precedent error #223", re.findall(r"error #(\d+)", log) == ["223"] and
               "Dependency type equal to Start requires that precedent mission is FIXED" in log and "TEACH-UNIT/RECON//8.000000" in log)
            ck("non-Fixed precedent invalid SXO", (run / "model.sxo").stat().st_size == 4)
            ck("non-Fixed precedent no event/report", not (run / "model.log").exists() and not (run / "report-raw.json").exists())
            continue
        ck(f"{v} zero converter errors", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log) == [("0", "2", "0")])
        ck(f"{v} valid output", (run / "model.sxo").stat().st_size > 1000 and
           (run / "model.log").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)
        event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        report = parse_native(run / "report-raw.json")
        events[v], reports[v] = event, report
        ck(f"{v} two mission starts", event.count("mission starting,") == 2)
        ck(f"{v} both allocated before FOLLOW schedule", "Time: 7 <RECON,TEACH-UNIT,0,0,0> mission allocates system:" in event
           and "Time: 9 <FOLLOW,TEACH-UNIT,0,0,1> mission allocates system:" in event)
        ck(f"{v} RECON start/success", "Time: 8 <RECON,TEACH-UNIT,0,0,0> mission starting, duration: 4" in event
           and "Time: 12 <RECON,TEACH-UNIT,0,0,0> mission success:" in event)
        follow_start = 12 if v == "fixed-fixed" else 10
        follow_end = 14 if v == "fixed-fixed" else 12
        ck(f"{v} FOLLOW start/success", f"Time: {follow_start} <FOLLOW,TEACH-UNIT,0,0,1> mission starting, duration: 2" in event
           and f"Time: {follow_end} <FOLLOW,TEACH-UNIT,0,0,1> mission success:" in event)
        ck(f"{v} no abort/failure", "mission aborted:" not in event and "failure occurred" not in event.lower())
        if v == "dep-cont-dependency":
            ck("continuous dependent suspended and resumed", "Time: 10 <FOLLOW,TEACH-UNIT,0,0,1> mission suspended:" in event
               and "Time: 12 <FOLLOW,TEACH-UNIT,0,0,1> mission resumed:" in event)
            ck("continuous dependent task starts at precedent return", "Time: 12 <FOLLOW,TEACH-UNIT,0,0,1> task starting:" in event
               and "Time: 10 <FOLLOW,TEACH-UNIT,0,0,1> task starting:" not in event)
        else:
            ck(f"{v} no suspension", "mission suspended:" not in event)
        summary, = rows(report, "ResultSummary", "report")
        ck(f"{v} summary scope", (summary["NREP"], summary["RTILW"], summary["RTIUP"]) == (1, 0, 24))
        factor = 2 / 3 if v == "dep-cont-dependency" else 1.0
        ck(f"{v} MTMF/STMF", abs(summary["MTMF"] - factor) < 1e-6 and abs(summary["STMF"] - factor) < 1e-6)
        ck(f"{v} MSTF/MSUF", summary["MSTF"] == summary["MSUF"] == 1)
        system, stock = rows(report, "SystemResults", "report"), rows(report, "StockTotalResults", "report")
        ck(f"{v} 48 half-hour bins", len(system) == len(stock) == 48)
        expected_op = ([(8, 12), (12, 14)] if v == "fixed-fixed" else
                       [(8, 12)] if v == "dep-cont-dependency" else
                       [(8, 12), (10, 12)])
        expected_suspended = [(10, 12)] if v == "dep-cont-dependency" else []
        for i, (sy, st) in enumerate(zip(system, stock, strict=True)):
            lo, hi = i / 2, (i + 1) / 2
            op = sum(max(0, min(hi, end) - max(lo, start)) for start, end in expected_op) / .5
            susp = sum(max(0, min(hi, end) - max(lo, start)) for start, end in expected_suspended) / .5
            ck(f"{v} bin {i} aligned", (sy["STINT"], sy["ETINT"], st["STINT"], st["ETINT"]) == (lo, hi, lo, hi))
            ck(f"{v} bin {i} operating", abs(sy["NSYMO"] - op) < 1e-6)
            ck(f"{v} bin {i} suspended", abs(sy["NSYMS"] - susp) < 1e-6)
            ck(f"{v} bin {i} aircraft ledger", sy["NSYA"] == 2 and abs(sy["NSYRY"] + sy["NSYMA"] - 2) < 1e-6)
            ck(f"{v} bin {i} no failure/repair", all(sy[k] == 0 for k in
               ("NREPT", "NPMT", "NFAIL", "NDAM", "NSYRP", "NSYPM", "NROBT", "NRCFG")))
            ck(f"{v} bin {i} no stock demand", all(st[k] == 0 for k in
               ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
        ck(f"{v} total aircraft-hours", abs(sum(sy["NSYMO"] * .5 for sy in system) - (4 if v == "dep-cont-dependency" else 6)) < 1e-6
           and abs(sum(sy["NSYMS"] * .5 for sy in system) - (2 if v == "dep-cont-dependency" else 0)) < 1e-6)
        ck(f"{v} terminal ready", system[-1]["NSYRY"] == 2 and system[-1]["NSYMA"] == 0)
    ck("continuous dependent matched source behavior differs", sha(RUNS["dep-cont-control"] / "model.log") != sha(RUNS["dep-cont-dependency"] / "model.log"))
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a13-var06-fixed-role-v101-author-validation/v1",
              "passed": not failed, "check_count": len(checks), "passed_count": len(checks)-len(failed),
              "failed_count": len(failed), "failures": failed,
              "run_ids": {v: run.name for v, run in RUNS.items()},
              "decision": "bounded_role_matrix_go_if_passed",
              "limits": ["One START dependency, two no-failure aircraft, one schedule and one installed executable.",
                         "The CONTINUOUS dependent is accepted and suspended rather than delayed at launch; no general START rule follows.",
                         "GUI visual content and cross-engine equivalence unverified."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failed": failed[:8]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
