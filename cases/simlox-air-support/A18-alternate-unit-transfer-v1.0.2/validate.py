"""Read-only author replay of A18 structural transfer and failed controls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {name: HERE / "runs" / f"a18-{name}-v102-20261001-01" for name in ("configured", "absent")}
DIAG0 = ROOT / "A18-alternate-unit-transfer-v1.0.0"
DIAG1 = ROOT / "A18-alternate-unit-transfer-v1.0.1"
EXPECTED = {
    "parent": "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974",
    "configured": "0cc2a25c572e9b2f4f1f3054ef139ebfbb749324318d0302d5e99fcfc36c859a",
    "absent": "eaae8621e88a74fc6ed800ab04b87a623f85623c0401c4c2db34ea5eb96d57d3",
    "diff": "728683ea17a8a8b819d3123c5086e833b43bb290b642e1ca2c63252e7f6b269f",
}
checks = 0


def yes(condition: bool, label: str) -> None:
    global checks
    if not condition:
        raise AssertionError(label)
    checks += 1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(document: dict, name: str, root: str = "report") -> list[dict]:
    t, = (t for t in document[root]["tables"] if t["name"] == name)
    columns = [c["name"] for c in t["columns"]]
    return [dict(zip(columns, row, strict=True)) for instance in t["instances"] for row in instance["rows"]]


def source() -> None:
    contract = read(HERE / "contract.json")
    yes(contract["configured_input_sha256"] == EXPECTED["configured"], "contract configured")
    yes(contract["absent_input_sha256"] == EXPECTED["absent"], "contract absent")
    yes(contract["parent_input_sha256"] == EXPECTED["parent"], "contract parent")
    yes(contract["exact_diff_sha256"] == EXPECTED["diff"], "contract exact diff")
    yes(sha(ROOT / "A17-multi-unit-group-v1.0.0" / "native-input.json") == EXPECTED["parent"], "accepted A17 source")
    # The pre-run diff builder hashed LF serialization, while Windows wrote
    # CRLF bytes. The native closure independently seals the actual file.
    diff_bytes = (HERE / "exact-diff.json").read_bytes()
    yes(hashlib.sha256(diff_bytes.replace(b"\r\n", b"\n")).hexdigest() == EXPECTED["diff"], "exact diff canonical LF content")
    for variant in RUNS:
        yes(sha(HERE / f"{variant}-input.json") == EXPECTED[variant], f"{variant} input")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["source_manual_sha256"], "installed manual")
    yes(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["source_dictionary_sha256"], "installed dictionary")
    configured = parse_native(HERE / "configured-input.json")
    absent = parse_native(HERE / "absent-input.json")
    ct = {t["name"]: t for t in configured["model"]["tables"]}
    at = {t["name"]: t for t in absent["model"]["tables"]}
    yes(set(ct) - set(at) == {"AlternateUnit"} and not (set(at) - set(ct)), "control table delta")
    yes(all(ct[name] == at[name] for name in ct.keys() & at.keys() if name != "ProblemDescription"), "control field delta")
    yes(table(configured, "Control", "model")[0]["ENALU"] == table(absent, "Control", "model")[0]["ENALU"] == "Y", "control ENALU fixed")
    yes(table(configured, "AlternateUnit", "model") == [{"USTID": "TEACH-UNIT", "AUNID": "TEACH-UNIT-2", "PRI": 1, "NOTE": None}], "one alternate relation")
    yes([r["QTYPS"] for r in table(configured, "SystemDeployment", "model")] == [1, 2], "one plus two aircraft")
    yes({r["PRID"]: r["IQTY"] for r in table(configured, "OperationProfile", "model")} == {"BASIC-SCHEDULE": 1, "ALT-IDLE": 0}, "explicit idle profile")


def closure(run: Path, variant: str) -> tuple[str, dict]:
    seal = read(run / "closure.json")
    invocation = read(run / "invocation.json")
    steps = read(run / "steps.json")
    yes(seal["error"] is None and seal["run_id"] == run.name, f"{variant} closure success")
    yes(seal["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} invocation seal")
    yes(seal["source_hashes_before"] == seal["source_hashes_after"], f"{variant} source stability")
    ss = seal["source_hashes_before"]
    yes(ss["input"] == EXPECTED[variant] and ss["parent"] == EXPECTED["parent"] and ss["exact_diff"] == sha(HERE / "exact-diff.json"), f"{variant} frozen input lineage")
    for field, path in (("contract", HERE / "contract.json"), ("builder", HERE / "build.py"), ("diff_checker", HERE / "describe_diff.py"), ("checker", HERE / "check_roundtrip.py"), ("runner_script", HERE / "run_native_ssh.ps1")):
        yes(ss[field] == sha(path), f"{variant} {field} source seal")
    yes(invocation["case_id"] == "A18" and invocation["variant"] == variant and invocation["execution_mode"] == "ssh_cli_v1", f"{variant} provenance")
    yes(invocation["session_id"] == 0 and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant} GUI/session guard")
    yes(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} queue")
    yes([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} five steps")
    yes(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant} steps pass")
    for name, entry in seal["raw"].items():
        path = run / name
        yes(path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], f"{variant} raw seal {name}")
    yes(sha(run / "input.json") == EXPECTED[variant], f"{variant} run input")
    rt = read(run / "roundtrip-validation.json")
    yes(rt["passed"] and rt["differences"] == [] and len(rt["populated_tables"]) == (14 if variant == "configured" else 13), f"{variant} exact business roundtrip")
    before = populated(parse_native(run / "input.json"))
    after = populated(parse_native(run / "roundtrip-raw.json"))
    yes(all(after.get(name) == rowset for name, rowset in before.items()), f"{variant} source rows unchanged")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    yes("Input conversion completed. Errors: 0, Warnings: 2" in log, f"{variant} zero converter errors")
    yes("warning #108" in log and "warning #126" in log, f"{variant} classified warnings")
    yes(("notice #320" in log) == (variant == "configured"), f"{variant} obsolete AlternateUnit notice")
    yes((run / "model.sxo").stat().st_size > 1000, f"{variant} nonempty SXO")
    return (run / "model.log").read_text(encoding="utf-8-sig", errors="replace"), parse_native(run / "report-raw.json")


def behavior(variant: str, event_log: str, report: dict) -> None:
    yes(event_log.count("mission ordered:") == 1 and "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION" in event_log, f"{variant} one planned call")
    yes("_MISSION" not in event_log, f"{variant} no generated default mission")
    yes("Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>" in event_log, f"{variant} original aircraft allocated")
    transferred = variant == "configured"
    yes(("is moved to alternate unit: <TEACH-UNIT-2>" in event_log) == transferred, f"{variant} transfer event")
    yes(("Time: 7 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>" in event_log) == transferred, f"{variant} original release")
    yes(("Time: 8 <BASIC-MISSION,TEACH-UNIT-2,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,1>,<TEACH-AIR-01,2>" in event_log) == transferred, f"{variant} alternate two-aircraft launch")
    yes(("Time: 10 <BASIC-MISSION,TEACH-UNIT-2,0,0,0> mission success:" in event_log) == transferred, f"{variant} mission success")
    yes(("Time: 8.33333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:" in event_log) == (not transferred), f"{variant} cancellation branch")
    yes(event_log.count("mission starting,") == int(transferred), f"{variant} launch cardinality")
    yes(event_log.count("mission success:") == int(transferred), f"{variant} success cardinality")
    yes("failure occurred" not in event_log.lower(), f"{variant} no failure events")
    summary, = table(report, "ResultSummary")
    yes(summary["NREP"] == 1 and summary["RTILW"] == 0 and summary["RTIUP"] == 36, f"{variant} result scope")
    for factor in ("MTMF", "MSTF", "MSUF", "STMF"):
        yes(summary[factor] == int(transferred), f"{variant} {factor}")
    system = table(report, "SystemResults")
    stock = table(report, "StockTotalResults")
    yes(len(system) == len(stock) == 72, f"{variant} 72 bins")
    for i, (sy, st) in enumerate(zip(system, stock, strict=True)):
        start = i / 2
        yes((sy["STINT"], sy["ETINT"], st["STINT"], st["ETINT"]) == (start, start + 0.5, start, start + 0.5), f"{variant} bin {i} time")
        yes(abs(sy["NSYRY"] + sy["NSYMA"] - 3) < 1e-5 and sy["NSYA"] == 3, f"{variant} bin {i} aircraft accounting")
        yes(sy["NSYMO"] == (2 if transferred and 8 <= start < 10 else 0), f"{variant} bin {i} operation")
        yes(all(sy[k] == 0 for k in ("NREPT", "NPMT", "NFAIL", "NDAM", "NSYRP", "NSYPM", "NROBT", "NRCFG")), f"{variant} bin {i} no fault/repair")
        yes(all(st[k] == 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant} bin {i} no stock demand")
    yes(sum(sy["NSYMO"] * 0.5 for sy in system) == (4 if transferred else 0), f"{variant} aircraft-hour integral")
    yes(system[-1]["NSYRY"] == 3 and system[-1]["NSYMA"] == 0, f"{variant} terminal ready")


def diagnostics() -> None:
    run0 = DIAG0 / "runs" / "a18-enabled-v100-20261001-01"
    run1y = DIAG1 / "runs" / "a18-enabled-v101-20261001-01"
    run1n = DIAG1 / "runs" / "a18-disabled-v101-20261001-01"
    for run in (run0, run1y, run1n):
        seal = read(run / "closure.json")
        yes(seal["error"] is None and seal["source_hashes_before"] == seal["source_hashes_after"], f"diagnostic {run.name} source stability")
        yes(all(sha(run / name) == entry["sha256"] for name, entry in seal["raw"].items()), f"diagnostic {run.name} raw closure")
    log0 = (run0 / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    yes("Time: 0 <TEACH-UNIT-2> mission ordered:" in log0 and "duration: 36" in log0, "v100 generated default mission")
    yes("Time: 8.33333 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission cancelled:" in log0, "v100 planned mission cancelled")
    yes(sha(run1y / "model.log") == sha(run1n / "model.log"), "v101 ENALU Y/N event logs byte-identical")
    yes(table(parse_native(run1y / "roundtrip-raw.json"), "Control", "model")[0]["ENALU"] == "Y", "v101 enabled switch roundtrip")
    yes(table(parse_native(run1n / "roundtrip-raw.json"), "Control", "model")[0]["ENALU"] == "N", "v101 disabled switch roundtrip")
    yes("is moved to alternate unit: <TEACH-UNIT-2>" in (run1n / "model.log").read_text(encoding="utf-8-sig", errors="replace"), "v101 disabled still transferred")


def main() -> None:
    source()
    for variant, run in RUNS.items():
        event_log, report = closure(run, variant)
        behavior(variant, event_log, report)
    diagnostics()
    result = {
        "schema": "simlox-a18-alternate-unit-author-validation/v1",
        "passed": True,
        "checks": checks,
        "decision": "bounded_go_structural_alternate_unit_transfer",
        "runs": {variant: run.name for variant, run in RUNS.items()},
        "diagnostics": ["a18-enabled-v100-20261001-01", "a18-enabled-v101-20261001-01", "a18-disabled-v101-20261001-01"],
        "finding": "One explicit AlternateUnit row transfers the single two-aircraft fixed mission at hour 7, releases the ordinary aircraft, launches two alternate aircraft at hour 8 and succeeds at hour 10. Without the row, the mission cancels at 8.33333. ENALU=N in an earlier paired probe did not suppress transfer despite exact roundtrip and remains a limitation.",
        "limitations": ["One seed, one alternate, no faults or resource contention.", "Alternate priority and delayed readiness, ENALU switch semantics, GUI and cross-engine behavior remain unverified."],
    }
    output = HERE / "review" / "author-validation-2026-10-01.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": result["passed"], "checks": checks, "decision": result["decision"]}))


if __name__ == "__main__":
    main()
