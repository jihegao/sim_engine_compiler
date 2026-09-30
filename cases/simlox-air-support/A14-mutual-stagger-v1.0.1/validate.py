"""Author replay of the sealed four-way staggered A14 dependency contrast."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, VARIANTS, build
from check_roundtrip import parse_native, populated
from describe_diff import delta

RUNS = {v: HERE / "runs" / f"a14-stagger-{v}-v101-20261001-01" for v in VARIANTS}
OUT = HERE / "review" / "author-validation-2026-10-01.json"
CONTRACT_SHA = "a0b09823bb44823684ecc5190e1f49a4f6f4a839e11da1882526ea642c0f3999"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
DIFF_SHA = "530637c4f9c1b6939a83b742db7b30b6ee380ed9e38132f9a3ee6b2b56f151c0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, name: str, root: str) -> list[dict]:
    table, = (t for t in doc[root]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, values, strict=True))
            for instance in table["instances"] for values in instance["rows"]]


def overlap(low: float, high: float, start: float, end: float) -> float:
    return max(0.0, min(high, end) - max(low, start))


def main() -> None:
    checks: list[dict] = []

    def ck(label: str, value: bool) -> None:
        checks.append({"name": label, "passed": bool(value)})

    contract, exact = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("frozen contract hash", sha(HERE / "contract.json") == CONTRACT_SHA)
    ck("accepted parent hash", sha(PARENT) == PARENT_SHA == contract["parent"]["input_sha256"])
    ck("exact diff hash", sha(HERE / "exact-diff.json") == DIFF_SHA == contract["exact_diff_sha256"])
    ck("manual fingerprint", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["source"]["manual_sha256"])
    ck("dictionary fingerprint", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["source"]["dictionary_sha256"])
    parent = {t["name"]: t for t in read(PARENT)["model"]["tables"]}
    inputs: dict[str, dict] = {}
    for v in VARIANTS:
        path = HERE / f"{v}-input.json"
        ck(f"{v} input hash", sha(path) == contract["inputs_sha256"][v])
        doc = read(path)
        ck(f"{v} builder identity", doc == build(v))
        inputs[v] = doc
    tabs = {v: {t["name"]: t for t in doc["model"]["tables"]} for v, doc in inputs.items()}
    expected_diff = {"parent_to_control": delta(parent, tabs["control"]),
                     **{f"control_to_{v}": delta(tabs["control"], tabs[v])
                        for v in ("oneway", "mutual", "opposing")}}
    ck("exact source diff", exact["changes"] == expected_diff)
    ck("parent change tables", set(expected_diff["parent_to_control"]) ==
       {"ProblemDescription", "MissionType", "OperationProfile"})
    for v in ("oneway", "mutual", "opposing"):
        ck(f"{v} changed tables", set(expected_diff[f"control_to_{v}"]) ==
           {"ProblemDescription", "MissionDependence"})
    ck("mission types", [(r["MTID"], r["MPAT"], r["DURN"], r["NOS"], r["MNOS"])
                         for r in rows(inputs["control"], "MissionType", "model")] ==
       [("SUPPORT", "CONTINUOUS", 2.0, 1, 1), ("EXECUTE", "CONTINUOUS", 4.0, 1, 1)])
    ck("staggered profile", [(r["SPRID"], r["STIM"], r["IQTY"])
                             for r in rows(inputs["control"], "OperationProfile", "model")] ==
       [("SUPPORT", 8.0, 1), ("EXECUTE", 8.1, 1)])
    dependency_rows = {v: rows(inputs[v], "MissionDependence", "model")
                       for v in ("oneway", "mutual", "opposing")}
    ck("dependency row counts", [len(dependency_rows[v]) for v in ("oneway", "mutual", "opposing")] == [1, 1, 2])
    ck("mutual flag contrast", [(r["DMTID"], r["PMTID"], r["DTYPE"], r["MUTD"])
                                for v in ("oneway", "mutual", "opposing") for r in dependency_rows[v]] ==
       [("EXECUTE", "SUPPORT", "CONTINUOUS", "N"),
        ("EXECUTE", "SUPPORT", "CONTINUOUS", "Y"),
        ("EXECUTE", "SUPPORT", "CONTINUOUS", "N"),
        ("SUPPORT", "EXECUTE", "CONTINUOUS", "N")])

    report_tables: dict[str, dict] = {}
    for v, run in RUNS.items():
        inv, closure, steps = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{v} run identity", inv["run_id"] == run.name and closure["run_id"] == run.name and inv["variant"] == v)
        ck(f"{v} SSH provenance", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0
           and inv["ssh_connection_present"] and "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]])
        ck(f"{v} GUI and mutex", inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1
           and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
        ck(f"{v} invocation seal", sha(run / "invocation.json") == closure["invocation_sha256"])
        ck(f"{v} closure success", closure["error"] is None and closure["scope"] == "staggered_mutual_opposing_contrast")
        ck(f"{v} source stable", closure["source_hashes_before"] == closure["source_hashes_after"])
        source = closure["source_hashes_before"]
        ck(f"{v} parent/input/contract/exe seal", (source["parent"], source["input"], source["contract"], source["exact_diff"], source["simlox_exe"]) ==
           (PARENT_SHA, contract["inputs_sha256"][v], CONTRACT_SHA, DIFF_SHA, EXE_SHA))
        for key, name in (("builder", "build.py"), ("diff_checker", "describe_diff.py"),
                          ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
            ck(f"{v} sealed {key}", source[key] == sha(HERE / name))
        ck(f"{v} steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
                              for s in steps] == [(n, "completed", 0, True) for n in
                                                  ("import", "export", "calc", "jsonreport", "check_import_export")])
        for name, info in closure["raw"].items():
            artifact = run / name
            ck(f"{v} raw seal {name}", artifact.stat().st_size == info["bytes"] and sha(artifact) == info["sha256"])
        ck(f"{v} copied input", sha(run / "input.json") == contract["inputs_sha256"][v])
        rt = read(run / "roundtrip-validation.json")
        expected_count = 13 if v == "control" else 14
        ck(f"{v} roundtrip checker", rt["passed"] and not rt["differences"] and len(rt["populated_tables"]) == expected_count)
        source_rows = populated(inputs[v])
        export_rows = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{v} all source rows roundtrip", len(source_rows) == expected_count and
           all(export_rows.get(name) == tab for name, tab in source_rows.items()))
        log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{v} conversion counts", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log) == [("0", "2", "0")])
        ck(f"{v} warnings", sorted(re.findall(r"warning #(\d+)", log)) == ["108", "126"])
        ck(f"{v} valid output", (run / "model.sxo").stat().st_size > 1000 and (run / "model.log").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)
        event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        report = parse_native(run / "report-raw.json")
        report_tables[v] = report
        ck(f"{v} two starts", event.count("mission starting,") == 2)
        ck(f"{v} support start", "Time: 8 <SUPPORT,TEACH-UNIT,0,0,0> mission starting, duration: 2" in event)
        ck(f"{v} execute start", "Time: 8.1 <EXECUTE,TEACH-UNIT,0,0,1> mission starting, duration: 4" in event)
        ck(f"{v} support success", "Time: 10 <SUPPORT,TEACH-UNIT,0,0,0> mission success:" in event)
        ck(f"{v} no failure", "failure occurred" not in event.lower())
        if v == "control":
            ck("control execute success", "Time: 12.1 <EXECUTE,TEACH-UNIT,0,0,1> mission success:" in event and "mission aborted:" not in event)
        else:
            ck(f"{v} execute abort", "Time: 10 <EXECUTE,TEACH-UNIT,0,0,1> mission aborted:" in event and "Time: 12.1 <EXECUTE" not in event)
        if v in ("mutual", "opposing"):
            ck(f"{v} support suspension", "Time: 8 <SUPPORT,TEACH-UNIT,0,0,0> mission suspended:" in event
               and "Time: 8.1 <SUPPORT,TEACH-UNIT,0,0,0> mission resumed:" in event)
            ck(f"{v} support task start after resume", "Time: 8.1 <SUPPORT,TEACH-UNIT,0,0,0> task starting:" in event)
        else:
            ck(f"{v} no suspension", "mission suspended:" not in event)
        summary, = rows(report, "ResultSummary", "report")
        expected_exposure = {"control": 6.0, "oneway": 3.9, "mutual": 3.8, "opposing": 3.8}[v]
        ck(f"{v} summary scope", (summary["NREP"], summary["RTILW"], summary["RTIUP"]) == (1, 0, 16))
        ck(f"{v} MTMF/STMF", abs(summary["MTMF"] - expected_exposure / 6) < 1e-6
           and abs(summary["STMF"] - expected_exposure / 6) < 1e-6)
        ck(f"{v} continuous fixed-only factors", summary["MSTF"] == summary["MSUF"] == 0)
        systems, stocks = rows(report, "SystemResults", "report"), rows(report, "StockTotalResults", "report")
        ck(f"{v} 32 bins", len(systems) == len(stocks) == 32)
        operating = ([(8.0, 10.0), (8.1, 12.1)] if v == "control" else
                     [(8.0, 10.0), (8.1, 10.0)] if v == "oneway" else
                     [(8.1, 10.0), (8.1, 10.0)])
        suspended = [(8.0, 8.1)] if v in ("mutual", "opposing") else []
        for i, (sy, st) in enumerate(zip(systems, stocks, strict=True)):
            low, high = i / 2, (i + 1) / 2
            ck(f"{v} bin {i} aligned", (sy["STINT"], sy["ETINT"], st["STINT"], st["ETINT"]) == (low, high, low, high))
            op = sum(overlap(low, high, a, b) for a, b in operating) / .5
            susp = sum(overlap(low, high, a, b) for a, b in suspended) / .5
            ck(f"{v} bin {i} operation", abs(sy["NSYMO"] - op) < 1e-6)
            ck(f"{v} bin {i} suspension", abs(sy["NSYMS"] - susp) < 1e-6)
            ck(f"{v} bin {i} aircraft ledger", sy["NSYA"] == 2 and
               abs(sy["NSYRY"] + sy["NSYMA"] - 2) < 1e-6)
            ck(f"{v} bin {i} no failure/repair", all(sy[k] == 0 for k in
               ("NREPT", "NPMT", "NFAIL", "NDAM", "NSYRP", "NSYPM", "NROBT", "NRCFG")))
            ck(f"{v} bin {i} no stock demand", all(st[k] == 0 for k in
               ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
        ck(f"{v} total operating hours", abs(sum(sy["NSYMO"] * .5 for sy in systems) - expected_exposure) < 1e-6)
        ck(f"{v} total suspended hours", abs(sum(sy["NSYMS"] * .5 for sy in systems) - (.1 if suspended else 0)) < 1e-6)
        ck(f"{v} terminal two ready", systems[-1]["NSYRY"] == 2 and systems[-1]["NSYMA"] == 0)

    ck("MUTD and opposing event logs identical", sha(RUNS["mutual"] / "model.log") == sha(RUNS["opposing"] / "model.log"))
    without_description = lambda doc: {t["name"]: t for t in doc["report"]["tables"] if t["name"] != "ProblemDescription"}
    ck("MUTD and opposing report rows identical", without_description(report_tables["mutual"]) == without_description(report_tables["opposing"]))
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a14-mutual-stagger-v101-author-validation/v1",
              "passed": not failed, "check_count": len(checks), "passed_count": len(checks) - len(failed),
              "failed_count": len(failed), "failures": failed,
              "decision": "bounded_go_if_passed",
              "run_ids": {v: path.name for v, path in RUNS.items()},
              "scope": "staggered no-failure two-mission MUTD versus opposing ordinary rows",
              "limits": ["Two earlier frozen deadlock predictions remain NO-GO diagnostics.",
                         "No general MUTD equivalence or universal no-deadlock rule follows.",
                         "GUI visual content and cross-engine equivalence unverified."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failed": failed[:8]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
