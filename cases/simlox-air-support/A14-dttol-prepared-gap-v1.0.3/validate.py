"""Author replay of frozen A14 DTTOL half-hour SUPPORT gap and five native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VARIANTS = ("control", "zero", "below", "edge", "above")
RUNS = {v: HERE / "runs" / f"a14-dttol-{v}-v103-20261001-01" for v in VARIANTS}
INPUT_SHA = {
    "control": "6756a61111bd1db6378353c4fe2c093f1d466ee4fa6a4ca7759600c35d8908c1",
    "zero": "f3bee7f935580fd90d5a60f6aa66c0307762c12d67b5c2ad575e8ddb6ecdfd3f",
    "below": "f995814acac489ec3d1dd382da952957ab5c6f7b19a1a4e36f4cf6b67b9b433f",
    "edge": "3018ba6ae23aa95fb0c1c1a209d6dfa733daf50d8a1a59a0f2cbdedab5f28c52",
    "above": "7823e5c922680cd04b6592920c14ad5a62c7b1857df5d9f7f27ee632e77ee00b",
}
PARENT_SHA = "b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d"
DONOR_SHA = "4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213"
DIFF_SHA = "2537166e6183b56586914e0c247d4fefdda0991412ade955bb4d9037c140211b"
checks = 0


def yes(value: bool, label: str) -> None:
    global checks
    if not value:
        raise AssertionError(label)
    checks += 1


def near(value: float, target: float, label: str, tol: float = 1e-5) -> None:
    yes(abs(value - target) <= tol, label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, name: str, root: str = "report") -> list[dict]:
    match = [t for t in doc[root]["tables"] if t["name"] == name]
    yes(len(match) == 1, f"{name} unique")
    cols = [c["name"] for c in match[0]["columns"]]
    out = []
    for inst in match[0]["instances"]:
        for values in inst["rows"]:
            yes(len(values) == len(cols), f"{name} rectangular")
            out.append(dict(zip(cols, values, strict=True)))
    return out


def source() -> None:
    contract = read(HERE / "contract.json")
    yes(contract["case_id"] == "A14" and contract["variant_id"] == "A14.var02", "contract identity")
    yes(contract["inputs_sha256"] == INPUT_SHA, "contract input hashes")
    yes(contract["parent"]["input_sha256"] == PARENT_SHA and contract["schema_source"]["input_sha256"] == DONOR_SHA, "contract source hashes")
    yes(contract["exact_diff_sha256"] == DIFF_SHA, "contract diff hash")
    yes(sha(ROOT / "A05-var02-prepared-spare-probe-v1.0.0" / "native-input.json") == PARENT_SHA, "accepted A05 parent")
    yes(sha(ROOT / "A11-mixed-type-minimum-v1.0.0" / "required-input.json") == DONOR_SHA, "accepted A11 schema source")
    yes(sha(HERE / "exact-diff.json") == DIFF_SHA, "frozen exact diff")
    for variant in VARIANTS:
        yes(sha(HERE / f"{variant}-input.json") == INPUT_SHA[variant], f"{variant} input")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["source"]["manual_sha256"], "manual fingerprint")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["source"]["dictionary_sha256"], "dictionary fingerprint")
    control = {t["name"]: t for t in parse_native(HERE / "control-input.json")["model"]["tables"]}
    for variant, tol in (("zero", 0), ("below", .49), ("edge", .5), ("above", .51)):
        model = parse_native(HERE / f"{variant}-input.json")
        tables = {t["name"]: t for t in model["model"]["tables"]}
        yes(set(tables) - set(control) == {"MissionDependence"} and not (set(control) - set(tables)), f"{variant} single table delta")
        yes(all(tables[k] == control[k] for k in control if k != "ProblemDescription"), f"{variant} common model identical")
        dep, = rows(model, "MissionDependence", "model")
        yes((dep["DUNID"], dep["DMTID"], dep["DSTIM"], dep["PUNID"], dep["PMTID"], dep["PSTIM"],
             dep["DTYPE"], dep["MUTD"], dep["DTTOL"]) ==
            ("TEACH-UNIT", "EXECUTE", 8.0, "TEACH-UNIT", "SUPPORT", 8.0, "CONTINUOUS", "N", tol), f"{variant} dependency row")
    types = rows(parse_native(HERE / "control-input.json"), "System", "model")
    yes([(x["SID"], x["FRT"]) for x in types] == [("TEACH-AIR-01", 300000), ("EXEC-AIR-01", 0)], "typed failure clocks")
    deployed = rows(parse_native(HERE / "control-input.json"), "SystemDeployment", "model")
    yes([(x["SID"], x["QTYPS"]) for x in deployed] == [("TEACH-AIR-01", 3), ("EXEC-AIR-01", 1)], "typed deployment")
    required = rows(parse_native(HERE / "control-input.json"), "MissionSystem", "model")
    yes([(x["MTID"], x["SID"], x["NOS"], x["MNOS"]) for x in required] ==
        [("SUPPORT", "TEACH-AIR-01", 2, 2), ("EXECUTE", "EXEC-AIR-01", 1, 1)], "typed mission requirements")


def replay(variant: str) -> None:
    run = RUNS[variant]
    seal, invocation, steps = (read(run / n) for n in ("closure.json", "invocation.json", "steps.json"))
    yes(seal["error"] is None and seal["run_id"] == run.name, f"{variant} closure")
    yes(seal["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} invocation sealed")
    yes(seal["source_hashes_before"] == seal["source_hashes_after"], f"{variant} source stable")
    sources = seal["source_hashes_before"]
    yes(sources["input"] == INPUT_SHA[variant] and sources["parent"] == PARENT_SHA and sources["schema_donor"] == DONOR_SHA, f"{variant} source lineage")
    for key, file in (("contract", "contract.json"), ("builder", "build.py"),
                      ("exact_diff", "exact-diff.json"), ("diff_checker", "describe_diff.py"),
                      ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
        yes(sources[key] == sha(HERE / file), f"{variant} sealed {key}")
    yes(invocation["case_id"] == "A14" and invocation["variant"] == variant and invocation["execution_mode"] == "ssh_cli_v1", f"{variant} provenance")
    yes(invocation["session_id"] == 0 and invocation["ssh_connection_present"]
        and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant} GUI/session")
    yes(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} native mutex")
    yes([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} five steps")
    yes(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant} step outcomes")
    for file, entry in seal["raw"].items():
        yes((run / file).stat().st_size == entry["bytes"] and sha(run / file) == entry["sha256"], f"{variant} raw {file}")
    yes(sha(run / "input.json") == INPUT_SHA[variant], f"{variant} copied input")
    rt = read(run / "roundtrip-validation.json")
    yes(rt["passed"] and not rt["differences"] and len(rt["populated_tables"]) == (17 if variant == "control" else 18), f"{variant} row roundtrip")
    before, after = (populated(parse_native(run / file)) for file in ("input.json", "roundtrip-raw.json"))
    yes(all(after.get(n) == t for n, t in before.items()), f"{variant} exact supplied rows")
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    yes("Input conversion completed. Errors: 0, Warnings: 3" in conversion, f"{variant} zero converter errors")
    yes("warning #108" in conversion and conversion.count("warning #126") == 2, f"{variant} classified warnings")
    yes((run / "model.sxo").stat().st_size > 1000, f"{variant} nonempty output")
    event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    yes(event.count("mission ordered:") == 2 and event.count("mission starting,") == 2, f"{variant} two missions")
    yes("Time: 7 <SUPPORT,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>" in event
        and "Time: 7 <SUPPORT,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,1>" in event, f"{variant} support allocation")
    yes("Time: 7 <EXECUTE,TEACH-UNIT,0,0,1> mission allocates system: <EXEC-AIR-01,3>" in event, f"{variant} execution allocation")
    yes("Time: 8 <SUPPORT,TEACH-UNIT,0,0,0> mission starting, duration: 4" in event
        and "Time: 8 <EXECUTE,TEACH-UNIT,0,0,1> mission starting, duration: 3.9" in event, f"{variant} starts")
    yes("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in event, f"{variant} same support failure")
    yes("Time: 9.8829 <SUPPORT,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,2>" in event, f"{variant} distinct spare")
    yes("Time: 9.8829 <SUPPORT,TEACH-UNIT,0,0,0> mission suspended: <TEACH-AIR-01,1>" in event, f"{variant} support suspends")
    yes("Time: 10.3829 <TEACH-AIR-01,2> preparation ended, mission: <SUPPORT" in event, f"{variant} spare prepared")
    yes("Time: 10.3829 <SUPPORT,TEACH-UNIT,0,0,0> mission resumed:" in event, f"{variant} support resumes")
    yes("Time: 11.9 <EXECUTE,TEACH-UNIT,0,0,1> mission success:" in event
        and "Time: 12 <SUPPORT,TEACH-UNIT,0,0,0> mission success:" in event, f"{variant} both succeed")
    yes("mission aborted:" not in event and "mission cancelled:" not in event, f"{variant} no abort")
    yes("critical random failure added" in event and event.count("critical random failure added") == 1, f"{variant} one failure")
    yes("critical random failure added" not in "\n".join(x for x in event.splitlines() if "<EXEC-AIR-01" in x), f"{variant} execution type healthy")
    susp = [line for line in event.splitlines() if "<EXECUTE,TEACH-UNIT,0,0,1> mission suspended:" in line]
    resumes = [line for line in event.splitlines() if "<EXECUTE,TEACH-UNIT,0,0,1> mission resumed:" in line]
    if variant == "control":
        yes(susp == resumes == [], "control no execution suspension")
    else:
        yes(any(line.startswith("Time: 8 ") for line in susp) and any(line.startswith("Time: 8 ") for line in resumes), f"{variant} zero-time startup transition")
        gap = {"zero": "9.8829", "below": "10.3729", "edge": "10.3829", "above": None}[variant]
        gap_susp = [line for line in susp if not line.startswith("Time: 8 ")]
        gap_resume = [line for line in resumes if not line.startswith("Time: 8 ")]
        yes((len(gap_susp), len(gap_resume)) == ((0, 0) if gap is None else (1, 1)), f"{variant} gap event count")
        if gap is not None:
            yes(gap_susp[0].startswith(f"Time: {gap} ") and gap_resume[0].startswith("Time: 10.3829 "), f"{variant} tolerance threshold time")
    report = parse_native(run / "report-raw.json")
    summary, = rows(report, "ResultSummary")
    yes((summary["NREP"], summary["RTILW"], summary["RTIUP"]) == (1, 0, 16), f"{variant} report horizon")
    yes(summary["MSTF"] == summary["MSUF"] == 0, f"{variant} fixed-only factors excluded")
    systems, stock = rows(report, "SystemResults"), rows(report, "StockTotalResults")
    yes(len(systems) == len(stock) == 32, f"{variant} 32 bins each")
    for i, (sy, st) in enumerate(zip(systems, stock, strict=True)):
        hour = i / 2
        yes((sy["STINT"], sy["ETINT"], st["STINT"], st["ETINT"]) == (hour, hour + .5, hour, hour + .5), f"{variant} bin {i} alignment")
        near(sy["NSYRY"] + sy["NSYMA"] + sy["NSYRP"], 4, f"{variant} bin {i} aircraft conservation")
        yes(-1e-5 <= sy["NSYMA"] - sy["NSYMO"] - sy["NSYMS"] - sy["NSYMP"] <= 3 + 1e-5,
            f"{variant} bin {i} assigned plus waiting aircraft ledger")
        yes(all(st[k] == 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant} bin {i} no stock demand")
        yes(all(sy[k] == 0 for k in ("NPMT", "NDAM", "NSYPM", "NROBT", "NRCFG")), f"{variant} bin {i} no other maintenance")
    expected_susp = .5 + {"control": 0, "zero": .5, "below": .01, "edge": 0, "above": 0}[variant]
    expected_oper = 10.9 - {"control": 0, "zero": .5, "below": .01, "edge": 0, "above": 0}[variant]
    near(sum(sy["NSYMS"] * .5 for sy in systems), expected_susp, f"{variant} suspended aircraft-hours")
    near(sum(sy["NSYMO"] * .5 for sy in systems), expected_oper, f"{variant} operating aircraft-hours")
    near(sum(sy["NSYRP"] * .5 for sy in systems), .5, f"{variant} repair aircraft-hours")
    near(sum(sy["NSYMP"] * .5 for sy in systems), 1.5, f"{variant} preparation aircraft-hours")
    yes(sum(sy["NFAIL"] for sy in systems) == 1 and sum(sy["NREPT"] for sy in systems) == 1, f"{variant} one failure/repair")
    yes(systems[-1]["NSYRY"] == 4 and systems[-1]["NSYMA"] == systems[-1]["NSYRP"] == 0, f"{variant} terminal ready")
    # Native summary fractions are checked as observed readouts, not used as a
    # general formula for continuous missions or cross-engine equivalence.
    expected_factors = {
        "control": (.9367088675498962, .9159663915634155),
        "zero": (.8734177350997925, .8739495873451233),
        "below": (.9354430437088013, .9151260256767273),
        "edge": (.9367088675498962, .9159663915634155),
        "above": (.9367088675498962, .9159663915634155),
    }[variant]
    near(summary["MTMF"], expected_factors[0], f"{variant} MTMF", 1e-6)
    near(summary["STMF"], expected_factors[1], f"{variant} STMF", 1e-6)


def main() -> None:
    source()
    for variant in VARIANTS:
        replay(variant)
    result = {
        "schema": "simlox-a14-dttol-prepared-gap-author-validation/v1",
        "passed": True, "checks": checks,
        "decision": "bounded_go_half_hour_precedent_gap_dttol_suspension_threshold",
        "runs": {v: RUNS[v].name for v in VARIANTS},
        "excluded_diagnostics": ["v1.0.0 execution ended before gap",
                                 "v1.0.1 dependent failure allocation changed",
                                 "v1.0.2 abort hypothesis falsified"],
        "finding": "With one matched half-hour SUPPORT suspension, EXECUTE suspends after DTTOL 0 or 0.49 and resumes at SUPPORT recovery; at 0.5 it records only a same-time transition, and at 0.51 none. All five EXECUTE missions succeed.",
        "limits": ["One fixed seed and one prepared support replacement in one explicit unit.",
                   "Other gap lengths, failure schedules, multiple precedents, profiles, GUI and cross-engine behavior unverified."],
    }
    path = HERE / "review" / "author-validation-2026-10-01.json"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": True, "checks": checks, "decision": result["decision"]}))


if __name__ == "__main__":
    main()
