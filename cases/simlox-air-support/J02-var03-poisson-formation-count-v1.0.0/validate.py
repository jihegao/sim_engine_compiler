"""Read-only native replay of one J02.var03 Poisson-count seed run."""
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
    if run.name != f"j02-var03-seed{seed:02d}-accepted-20261001-01" or invocation.get("schema") != "simlox-j02-var03-poisson-seed-invocation/ssh-cli-v1" or invocation.get("seed") != seed or invocation.get("run_id") != run.name:
        errors.append("invocation identity mismatch")
    if closure.get("schema") != "simlox-j02-var03-poisson-seed-closure/v1" or closure.get("seed") != seed or closure.get("run_id") != run.name or closure.get("state") != "native_steps_complete":
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
    expected_integer = [{"DISTID": "COUNTPOI", "PFAC": 1.0, "BASED": "<POISSON>",
                         "PARAM1": 1.5, "PARAM2": None, "PARAM3": None, "NOTE": None}]
    for label, document in (("source", source), ("export", exported)):
        if build.rows(build.table(document, "IntegerDistributions")) != expected_integer:
            errors.append(f"{label} integer distribution row differs")
        operation = build.rows(build.table(document, "OperationProfile"))
        if len(operation) != 1 or any(operation[0].get(key) != value for key, value in
                                      {"STIM": 8, "ITYPE": "RANDOM", "IQTY": 1,
                                       "IQTYD": "COUNTPOI", "IPER": 0, "IDISP": "EQUIDIST"}.items()):
            errors.append(f"{label} operation profile differs")
        if build.rows(build.table(document, "SystemDeployment"))[0].get("QTYPS") != 12:
            errors.append(f"{label} aircraft deployment differs")
        control = build.rows(build.table(document, "Control"))
        if len(control) != 1 or control[0].get("NREPS") != 1 or control[0].get("RSEED") != str(seed):
            errors.append(f"{label} seed/repetition differs")
        mission_type = build.rows(build.table(document, "MissionType"))[0]
        if mission_type.get("NOS") != 2 or mission_type.get("MNOS") != 2 or mission_type.get("DURN") != 2:
            errors.append(f"{label} two-aircraft formation differs")
    roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append(f"business roundtrip differs: {roundtrip['changed']!r}")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", log))
    if conversion is None or int(conversion[1]) != 0 or warnings != Counter({"108": 1, "126": 1, "211": 1}):
        errors.append(f"converter error or warning set differs: {dict(warnings)}")
    event_log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    mission = r"<BASIC-MISSION,TEACH-UNIT,0,0,(\d+)>"
    start_pattern = re.compile(rf"^Time:\s*([0-9.eE+\-]+) {mission} mission starting, duration: 2 : (.*)$")
    success_pattern = re.compile(rf"^Time:\s*([0-9.eE+\-]+) {mission} mission success:")
    complete_pattern = re.compile(rf"^Time:\s*([0-9.eE+\-]+) {mission} mission completed: (.*)$")
    activation_pattern = re.compile(rf"^Time:\s*([0-9.eE+\-]+) {mission} mission activated, systems requested: (\d+)$")
    allocation_pattern = re.compile(rf"^Time:\s*([0-9.eE+\-]+) {mission} mission allocates system: <TEACH-AIR-01,(\d+)>$")
    lines = event_log.splitlines()
    starts = [(float(match[1]), int(match[2]), [int(value) for value in re.findall(r"<TEACH-AIR-01,(\d+)>", match[3])])
              for line in lines if (match := start_pattern.match(line))]
    successes = [(float(match[1]), int(match[2])) for line in lines if (match := success_pattern.match(line))]
    completions = [(float(match[1]), int(match[2]), [int(value) for value in re.findall(r"<TEACH-AIR-01,(\d+)>", match[3])])
                   for line in lines if (match := complete_pattern.match(line))]
    activations = [(float(match[1]), int(match[2]), int(match[3])) for line in lines if (match := activation_pattern.match(line))]
    allocations = [(float(match[1]), int(match[2]), int(match[3])) for line in lines if (match := allocation_pattern.match(line))]
    count = len(starts)
    if sum(" mission starting, duration:" in line for line in lines) != count:
        errors.append("unparsed mission start event")
    if sum(" mission success:" in line for line in lines if "System arrives" not in line) != len(successes):
        errors.append("unparsed mission success event")
    expected_count = contract["expected_observation"]["frozen_counts_by_seed"][seed - 1]
    if count != expected_count or not 0 <= count <= 5:
        errors.append(f"realized count differs from frozen Poisson panel: {count}")
    expected_ids = list(range(1, count + 1))
    if starts != [(8.0, number, [2 * number - 2, 2 * number - 1]) for number in expected_ids]:
        errors.append(f"mission starts/formation identities differ: {starts!r}")
    if successes != [(10.0, number) for number in expected_ids] or completions != [
            (10.0, number, [2 * number - 2, 2 * number - 1]) for number in expected_ids]:
        errors.append("mission success/completion differs")
    if activations != [(7.0, number, 2) for number in expected_ids]:
        errors.append("mission activation count or requested formation differs")
    if allocations != [(7.0, number, aircraft) for number in expected_ids
                       for aircraft in (2 * number - 2, 2 * number - 1)]:
        errors.append("mission allocations differ")
    if any(" mission cancelled:" in line or " mission aborted:" in line for line in lines):
        errors.append("unexpected cancellation or abort")
    report = load(run / "report-raw.json")
    summary = native.table_rows(report, "ResultSummary")
    expected_success = int(count > 0)
    if len(summary) != 1 or any(summary[0].get(key) != value for key, value in
                                {"NREP": 1, "RTILW": 0, "RTIUP": 36,
                                 "MSTF": expected_success, "MSUF": expected_success}.items()):
        errors.append("ResultSummary differs")
    system = native.table_rows(report, "SystemResults")
    stock = native.table_rows(report, "StockTotalResults")
    if len(system) != 72 or len(stock) != 72:
        errors.append(f"expected 72 System/Stock bins, got {len(system)}/{len(stock)}")
    flight_hours = 0.0
    for index, row in enumerate(system):
        assigned = 2 * count if 14 <= index < 20 else 0
        operating = 2 * count if 16 <= index < 20 else 0
        if any(row.get(key) != value for key, value in
               {"STINT": index * 0.5, "ETINT": (index + 1) * 0.5,
                "NSYA": 12, "NSYRY": 12 - assigned, "NSYMA": assigned,
                "NSYMO": operating,
                "NSYMR": 2 * count if 14 <= index < 16 else 0}.items()):
            errors.append(f"system bin {index} formation occupancy differs")
        if abs(float(row.get("FTMO") or 0) - operating / 12) > 1e-6:
            errors.append(f"system bin {index} flight fraction differs")
        if any(row.get(key) != 0 for key in
               ("NFAIL", "NPMT", "NSYMP", "NSYMC", "NSYMT", "NSYMS")):
            errors.append(f"system bin {index} has unrelated mechanism")
        flight_hours += float(row.get("NSYMO") or 0) * 0.5
    for index, row in enumerate(stock):
        if row.get("STINT") != index * 0.5 or row.get("ETINT") != (index + 1) * 0.5 or row.get("PNB") != 1:
            errors.append(f"stock bin {index} bounds/position differ")
        if any(row.get(key) != 0 for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
            errors.append(f"stock bin {index} unexpected demand")
    if abs(flight_hours - 4 * count) > 2e-4:
        errors.append(f"report flight hours {flight_hours} differ from {4 * count}")
    if system and (system[-1].get("NSYRY") != 12 or system[-1].get("NSYMA") != 0):
        errors.append("aircraft not ready at horizon")
    return {
        "case_id": "J02", "variant_id": "J02.var03", "version": "1.0.0",
        "seed": seed, "run_id": run.name, "passed": not errors, "differences": errors,
        "realized_count": count, "mission_starts": starts, "mission_successes": successes,
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
