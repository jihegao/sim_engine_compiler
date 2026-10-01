"""Read-only native replay for one source-pinned J01.var05 seed."""
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

CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
TIME = re.compile(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def rows(document: dict, name: str) -> list[dict]:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"missing/duplicate {name}")
    columns = [column["name"] for column in found[0]["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in found[0]["instances"][0]["rows"]]


def events(raw: str) -> list[tuple[float, str]]:
    return [(float(match[1]), match[2]) for line in raw.splitlines()
            if (match := TIME.match(line))]


def validate(run: Path, seed: int) -> dict:
    errors: list[str] = []
    input_name = f"seed-{seed:02d}-input.json"
    panel = load(HERE / "panel-diff.json")
    expected_input = panel["input_sha256"][input_name]
    for name in RAW | {"invocation.json", "closure.json"}:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing artifact: {name}")
    if errors:
        return {"seed": seed, "passed": False, "differences": errors}
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    if invocation.get("schema") != "simlox-j01-var05-seed-invocation/ssh-cli-v1" or invocation.get("seed") != seed or invocation.get("run_id") != run.name:
        errors.append("invocation identity mismatch")
    if invocation.get("input_sha256") != expected_input or sha(run / "input.json") != expected_input:
        errors.append("input identity mismatch")
    if invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
        errors.append("session-0 SSH ancestry unverified")
    gui = invocation.get("coexisting_gui") or {}
    if gui.get("pid") != 13340 or gui.get("session_id") != 1 or gui.get("process_start_utc") != "2026-09-28T10:09:56.8261381Z":
        errors.append("preserved GUI identity mismatch")
    if closure.get("schema") != "simlox-j01-var05-seed-closure/v1" or closure.get("seed") != seed or closure.get("state") != "native_steps_complete":
        errors.append("closure identity/state mismatch")
    if closure.get("invocation_sha256") != sha(run / "invocation.json") or set(closure.get("raw", {})) != RAW:
        errors.append("closure invocation/raw list mismatch")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw seal mismatch: {name}")
    expected_sources = {
        "contract.json": sha(HERE / "contract.json"), "build.py": sha(HERE / "build.py"),
        "validate.py": sha(HERE / "validate.py"), "validate_panel.py": sha(HERE / "validate_panel.py"), "run_native_ssh.ps1": sha(HERE / "run_native_ssh.ps1"),
        "panel-diff.json": CONTRACT["panel_diff_sha256"],
        "parent-input.json": CONTRACT["parent_input_sha256"],
        "database-dictionary.txt": CONTRACT["source"]["database_dictionary_sha256"],
        "manual.pdf": CONTRACT["source"]["manual_sha256"],
        **{f"seed-{n:02d}-input.json": panel["input_sha256"][f"seed-{n:02d}-input.json"] for n in build.SEEDS},
    }
    if set(closure.get("post_source_sha256", {})) != set(expected_sources):
        errors.append("post-source file set mismatch")
    for name, wanted in expected_sources.items():
        if closure.get("post_source_sha256", {}).get(name) != wanted:
            errors.append(f"post-source seal mismatch: {name}")
    for name, wanted in (("contract_sha256", expected_sources["contract.json"]),
                         ("builder_sha256", expected_sources["build.py"]),
                         ("validator_sha256", expected_sources["validate.py"]),
                         ("panel_validator_sha256", expected_sources["validate_panel.py"]),
                         ("runner_sha256", expected_sources["run_native_ssh.ps1"]),
                         ("panel_diff_sha256", expected_sources["panel-diff.json"])):
        if invocation.get(name) != wanted:
            errors.append(f"invocation source mismatch: {name}")
    steps = load(run / "steps.json")
    if [s.get("name") for s in steps] != ["import", "export", "calc", "jsonreport"]:
        errors.append("native step order mismatch")
    if any(s.get("exit_code") != 0 or s.get("coexisting_gui_present_after") is not True for s in steps):
        errors.append("native step failed or GUI lost")
    generated, diff = build.build()
    for name, raw in {**generated, "panel-diff.json": diff}.items():
        if (HERE / name).read_bytes() != raw:
            errors.append(f"builder output mismatch: {name}")
    source, exported = load(run / "input.json"), load(run / "roundtrip-raw.json")
    wanted_dist = {"DISTID": "PREP-LGN", "PFAC": 1, "BASED": "<LOGNORM>", "PARAM1": 0.5,
                   "PARAM2": 0.25, "PARAM3": None, "NOTE": None}
    for label, document in (("source", source), ("export", exported)):
        if rows(document, "TimeDistributions") != [wanted_dist]:
            errors.append(f"{label} distribution row differs")
        prep = rows(document, "MissionPreparation")
        if len(prep) != 1 or prep[0].get("DURN") != 0.5 or prep[0].get("DURND") != "PREP-LGN":
            errors.append(f"{label} preparation reference differs")
        control = rows(document, "Control")
        if len(control) != 1 or control[0].get("NREPS") != 1 or control[0].get("RSEED") != str(seed):
            errors.append(f"{label} seed/repetition differs")
    roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append(f"business roundtrip differs: {roundtrip['changed']!r}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
    if conversion is None or int(conversion[1]) != 0 or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"converter error or warning set differs: {dict(warnings)}")
    event_list = events((run / "model.log").read_text(encoding="utf-8-sig", errors="replace"))
    def hours(marker: str) -> list[float]:
        return [hour for hour, body in event_list if marker in body]
    start, end = hours(" preparation started,"), hours(" preparation ended,")
    mission_start, success = hours(" mission starting, duration:"), hours(" mission success:")
    if len(start) != 1 or start[0] != 7:
        errors.append(f"preparation start differs: {start!r}")
    duration = end[0] - start[0] if len(start) == len(end) == 1 else None
    if duration is None or duration <= 0:
        errors.append(f"preparation duration outside positive LOGNORM support: {duration!r}")
    expected_mission_start = max(8, end[0]) if len(end) == 1 else None
    if (expected_mission_start is None or len(mission_start) != 1 or len(success) != 1
            or abs(mission_start[0] - expected_mission_start) > 2e-5
            or abs(success[0] - (mission_start[0] + 2)) > 5e-5
            or hours(" mission aborted:") or hours(" mission cancelled:")):
        errors.append(f"mission start/success/abort/cancel differs: {mission_start!r}/{success!r}")
    report = load(run / "report-raw.json")
    summary = native.table_rows(report, "ResultSummary")
    if len(summary) != 1 or any(summary[0].get(key) != value for key, value in
                                {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}.items()):
        errors.append("ResultSummary differs from one successful repetition")
    system = native.table_rows(report, "SystemResults")
    stock = native.table_rows(report, "StockTotalResults")
    if len(system) != 72 or len(stock) != 72:
        errors.append(f"expected 72 System/Stock bins, got {len(system)}/{len(stock)}")
    prep_hours = 0.0
    flight_hours = 0.0
    for index, row in enumerate(system):
        if row.get("STINT") != index * 0.5 or row.get("ETINT") != (index + 1) * 0.5 or row.get("NSYA") != 1:
            errors.append(f"system bin {index} bounds/aircraft count differ")
        prep_hours += float(row.get("NSYMP") or 0) * 0.5
        flight_hours += float(row.get("NSYMO") or 0) * 0.5
    for index, row in enumerate(stock):
        if row.get("STINT") != index * 0.5 or row.get("ETINT") != (index + 1) * 0.5 or row.get("PNB") != 1:
            errors.append(f"stock bin {index} bounds/stock position differ")
        if any(row.get(field) != 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
            errors.append(f"stock bin {index} has unexpected demand")
    if duration is not None and abs(prep_hours - duration) > 2e-4:
        errors.append(f"reported preparation-hours {prep_hours} differ from event duration {duration}")
    if abs(flight_hours - 2) > 2e-4:
        errors.append(f"reported mission operating-hours {flight_hours} differ from two-hour mission")
    if system and (system[-1].get("NSYRY") != 1 or system[-1].get("NSYMA") != 0):
        errors.append("aircraft not ready at terminal horizon")
    return {"case_id": "J01", "variant_id": "J01.var05", "version": "1.0.0", "seed": seed,
            "run_id": run.name, "passed": not errors, "differences": errors,
            "sample_preparation_hours": duration, "report_preparation_hours": prep_hours,
            "report_flight_hours": flight_hours,
            "mission_start_hour": mission_start[0] if len(mission_start) == 1 else None,
            "mission_success_hour": success[0] if len(success) == 1 else None,
            "notice_overrun": bool(len(end) == 1 and end[0] > 8),
            "roundtrip": roundtrip, "publication_state": "not_published"}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: validate.py RUN_DIRECTORY SEED")
    seed = int(sys.argv[2])
    if seed not in build.SEEDS:
        raise SystemExit("seed outside frozen panel")
    result = validate(Path(sys.argv[1]), seed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
