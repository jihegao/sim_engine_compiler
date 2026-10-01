"""Read-only native replay of one J03.var01 time two-point preparation seed run."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402
import build  # noqa: E402

RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def validate(run: Path, seed: int) -> dict:
    errors: list[str] = []
    panel = load(HERE / "panel-diff.json")
    contract = load(HERE / "contract.json")
    name = f"seed-{seed:02d}-input.json"
    expected_input = panel["input_sha256"][name]
    for item in RAW | {"invocation.json", "closure.json"}:
        path = run / item
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing artifact: {item}")
    if errors:
        return {"seed": seed, "passed": False, "differences": errors}
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    if run.name != f"j03-var01-seed{seed:02d}-accepted-20261001-01" or invocation.get("schema") != "simlox-j03-var01-time-two-point-seed-invocation/ssh-cli-v1" or invocation.get("seed") != seed or invocation.get("run_id") != run.name:
        errors.append("invocation identity mismatch")
    if closure.get("schema") != "simlox-j03-var01-time-two-point-seed-closure/v1" or closure.get("seed") != seed or closure.get("run_id") != run.name or closure.get("state") != "native_steps_complete":
        errors.append("closure identity/state mismatch")
    if sha(run / "input.json") != expected_input or invocation.get("input_sha256") != expected_input:
        errors.append("input fingerprint mismatch")
    if invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
        errors.append("session-0 SSH ancestry missing")
    if invocation.get("gui_pid") != 13340 or invocation.get("gui_start_utc") != "2026-09-28T10:09:56.8261381Z" or invocation.get("queue_mutex") != "Global\\SimloxIssue18NativeQueue":
        errors.append("preserved GUI identity mismatch")
    if closure.get("invocation_sha256") != sha(run / "invocation.json") or set(closure.get("raw", {})) != RAW:
        errors.append("raw/invocation closure differs")
    for item, record in closure.get("raw", {}).items():
        path = run / item
        if path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw seal mismatch: {item}")
    expected_sources = {
        "contract.json": sha(HERE / "contract.json"),
        "build.py": sha(HERE / "build.py"),
        "validate.py": sha(HERE / "validate.py"),
        "validate_panel.py": sha(HERE / "validate_panel.py"),
        "run_native_ssh.ps1": sha(HERE / "run_native_ssh.ps1"),
        "panel-diff.json": contract["panel_diff_sha256"],
        "parent-input.json": contract["parent_input_sha256"],
        "database-dictionary.txt": contract["source"]["database_dictionary_sha256"],
        "manual.pdf": contract["source"]["manual_sha256"],
        **{f"seed-{number:02d}-input.json": panel["input_sha256"][f"seed-{number:02d}-input.json"] for number in build.SEEDS},
    }
    if closure.get("post_source_sha256") != expected_sources:
        errors.append("post-source fingerprints differ")
    for field, source in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"),
                          ("validator_sha256", "validate.py"), ("panel_validator_sha256", "validate_panel.py"),
                          ("runner_sha256", "run_native_ssh.ps1"), ("panel_diff_sha256", "panel-diff.json")):
        if invocation.get(field) != expected_sources[source]:
            errors.append(f"invocation source mismatch: {field}")
    steps = load(run / "steps.json")
    if [step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"] or any(
            step.get("exit_code") != 0 or step.get("coexisting_gui_present_after") is not True for step in steps):
        errors.append("native step or GUI guard failed")
    outputs, diff = build.build()
    for filename, raw in {**outputs, "panel-diff.json": diff}.items():
        if (HERE / filename).read_bytes() != raw:
            errors.append(f"builder output mismatch: {filename}")
    source, exported = load(run / "input.json"), load(run / "roundtrip-raw.json")
    expected_time = [
        {"DISTID": "PREP-DET", "PFAC": 0.5, "BASED": "<DETERM>",
         "PARAM1": 0.25, "PARAM2": None, "PARAM3": None, "NOTE": None},
        {"DISTID": "PREP-DET", "PFAC": 0.5, "BASED": "<DETERM>",
         "PARAM1": 0.75, "PARAM2": None, "PARAM3": None, "NOTE": None},
    ]
    for label, document in (("source", source), ("export", exported)):
        if build.rows(build.table(document, "TimeDistributions")) != expected_time:
            errors.append(f"{label} time distribution rows differ")
        prep = build.rows(build.table(document, "MissionPreparation"))
        if len(prep) != 1 or prep[0].get("DURN") != 0.5 or prep[0].get("DURND") != "PREP-DET":
            errors.append(f"{label} preparation reference differs")
        control = build.rows(build.table(document, "Control"))
        if len(control) != 1 or control[0].get("NREPS") != 1 or control[0].get("RSEED") != str(seed):
            errors.append(f"{label} seed/repetition differs")
        if build.rows(build.table(document, "SystemDeployment"))[0].get("QTYPS") != 1:
            errors.append(f"{label} aircraft deployment differs")
    roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append(f"business roundtrip differs: {roundtrip['changed']!r}")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", log))
    if conversion is None or int(conversion[1]) != 0 or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"converter error or warning set differs: {dict(warnings)}")
    event_log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = event_log.splitlines()
    prep_start = re.compile(r"^Time: ([0-9.]+) <TEACH-AIR-01,0> preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>$")
    prep_end = re.compile(r"^Time: ([0-9.]+) <TEACH-AIR-01,0> preparation ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>$")
    performing = re.compile(r"^Time: ([0-9.]+)  subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for ([0-9.]+) hours$")
    mission_start = re.compile(r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>$")
    mission_success = re.compile(r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:")
    mission_complete = re.compile(r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>$")
    def hits(pattern: re.Pattern) -> list[re.Match]:
        return [match for line in lines if (match := pattern.match(line))]
    starts, ends, work = hits(prep_start), hits(prep_end), hits(performing)
    launches, successes, completions = hits(mission_start), hits(mission_success), hits(mission_complete)
    expected_duration = contract["expected_observation"]["frozen_preparation_hours_by_seed"][seed - 1]
    duration = float(ends[0][1]) - float(starts[0][1]) if len(starts) == len(ends) == 1 else None
    if len(starts) != 1 or float(starts[0][1]) != 7 or len(ends) != 1 or duration != expected_duration:
        errors.append(f"preparation event/duration differs: {duration}")
    if len(work) != 1 or float(work[0][1]) != 7 or float(work[0][2]) != expected_duration:
        errors.append("preparation work duration differs")
    if len(launches) != 1 or float(launches[0][1]) != 8 or len(successes) != 1 or float(successes[0][1]) != 10 or len(completions) != 1 or float(completions[0][1]) != 10:
        errors.append("mission start/success/completion differs")
    if any(" mission cancelled:" in line or " mission aborted:" in line for line in lines):
        errors.append("unexpected cancellation or abort")
    report = load(run / "report-raw.json")
    summary = native.table_rows(report, "ResultSummary")
    if len(summary) != 1 or any(summary[0].get(key) != value for key, value in
                                {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}.items()):
        errors.append("ResultSummary differs")
    system = native.table_rows(report, "SystemResults")
    stock = native.table_rows(report, "StockTotalResults")
    if len(system) != 72 or len(stock) != 72:
        errors.append(f"expected 72 System/Stock bins, got {len(system)}/{len(stock)}")
    prep_hours = 0.0
    flight_hours = 0.0
    for index, row in enumerate(system):
        assigned = int(14 <= index < 20)
        operating = int(16 <= index < 20)
        prep_fraction = expected_duration / 0.5 if index == 14 and expected_duration == 0.25 else (1 if index == 14 else (0.5 if index == 15 and expected_duration == 0.75 else 0))
        if any(row.get(key) != value for key, value in
               {"STINT": index * 0.5, "ETINT": (index + 1) * 0.5,
                "NSYA": 1, "NSYRY": 1 - assigned, "NSYMA": assigned,
                "NSYMO": operating, "NSYMP": prep_fraction}.items()):
            errors.append(f"system bin {index} occupancy/preparation differs")
        if abs(float(row.get("FTMO") or 0) - operating) > 1e-6:
            errors.append(f"system bin {index} flight fraction differs")
        if any(row.get(key) != 0 for key in ("NFAIL", "NPMT", "NSYMC", "NSYMT", "NSYMS")):
            errors.append(f"system bin {index} has unrelated mechanism")
        prep_hours += float(row.get("NSYMP") or 0) * 0.5
        flight_hours += float(row.get("NSYMO") or 0) * 0.5
    for index, row in enumerate(stock):
        if row.get("STINT") != index * 0.5 or row.get("ETINT") != (index + 1) * 0.5 or row.get("PNB") != 1:
            errors.append(f"stock bin {index} bounds/position differ")
        if any(row.get(key) != 0 for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
            errors.append(f"stock bin {index} unexpected demand")
    if abs(prep_hours - expected_duration) > 2e-4 or abs(flight_hours - 2) > 2e-4:
        errors.append("preparation or flight hour integral differs")
    if system and (system[-1].get("NSYRY") != 1 or system[-1].get("NSYMA") != 0):
        errors.append("aircraft not ready at horizon")
    return {
        "case_id": "J03", "variant_id": "J03.var01", "version": "1.0.0",
        "seed": seed, "run_id": run.name, "passed": not errors, "differences": errors,
        "sample_preparation_hours": duration, "report_preparation_hours": prep_hours,
        "flight_hours": flight_hours, "roundtrip": roundtrip,
        "publication_state": "not_published",
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: validate.py RUN_DIRECTORY SEED")
    seed = int(sys.argv[2])
    if seed not in build.SEEDS:
        raise SystemExit("seed outside panel")
    result = validate(Path(sys.argv[1]), seed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
