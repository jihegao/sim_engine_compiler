"""Independent, read-only replay of the sealed A17 1.0.0 native run.

This file intentionally imports no case builder, checker, or validator.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys


CASE = Path(__file__).resolve().parents[1]
RUN = CASE / "runs" / "a17-v100-ssh-20260929-01"
PARENT = CASE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
EXPECTED_PARENT = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
EXPECTED_CHILD = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"
RUN_ID = RUN.name
MISSION = "<BASIC-MISSION,TEACH-GROUP,0,0,0>"
AIRCRAFT = ("<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, *, native: bool = False) -> dict | list:
    raw = path.read_text(encoding="utf-8-sig")
    if not native:
        return json.loads(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # SIMLOX's JSON writer emits trailing commas. Only normalize a parser copy.
        out: list[str] = []
        quoted = escaped = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and raw[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def tables(doc: dict, root: str) -> dict[str, dict]:
    result = {}
    for item in doc[root]["tables"]:
        name = item["name"]
        if name in result:
            raise ValueError(f"duplicate {root} table: {name}")
        result[name] = item
    return result


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    result = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            if len(values) != len(names):
                raise ValueError(f"nonrectangular row in {names}")
            result.append(dict(zip(names, values)))
    return result


def normalized(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


def business(table: dict) -> Counter:
    return Counter(
        json.dumps(normalized(row), ensure_ascii=False, sort_keys=True)
        for row in rows(table)
        if any(value not in (None, "") for value in row.values())
    )


def utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() == timezone.utc.utcoffset(parsed) else None


def verify() -> dict:
    errors: list[str] = []
    notes: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    invocation = read_json(RUN / "invocation.json")
    closure = read_json(RUN / "closure.json")
    steps = read_json(RUN / "steps.json")
    contract = read_json(CASE / "contract.json")
    diff = read_json(CASE / "parent-diff.json")
    check(sha(PARENT) == EXPECTED_PARENT, "accepted A03 parent hash differs")
    check(sha(CASE / "native-input.json") == EXPECTED_CHILD, "checked A17 input hash differs")
    check(sha(RUN / "input.json") == EXPECTED_CHILD, "run input hash differs")
    check(contract.get("native_input_sha256") == EXPECTED_CHILD, "contract input hash differs")
    check(contract.get("parent", {}).get("input_sha256") == EXPECTED_PARENT, "contract parent hash differs")
    check(diff.get("parent_input_sha256") == EXPECTED_PARENT and diff.get("child_input_sha256") == EXPECTED_CHILD, "parent-diff fingerprints differ")

    check(invocation.get("schema") == "simlox-a17-v100-native-candidate/ssh-cli-v1", "invocation schema differs")
    check(invocation.get("run_id") == RUN_ID and closure.get("run_id") == RUN_ID, "run identity differs")
    check(invocation.get("case_id") == "A17" and invocation.get("case_version") == "1.0.0-candidate", "case identity differs")
    check(invocation.get("input_sha256") == EXPECTED_CHILD and invocation.get("parent_sha256") == EXPECTED_PARENT, "invocation source hashes differ")
    check(invocation.get("execution_mode") == "ssh_cli_v1" and invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True, "session-0 SSH provenance differs")
    check("sshd.exe" in [str(x).lower() for x in invocation.get("ssh_ancestor_names", [])], "sshd ancestor absent")
    check(invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue", "native queue identity differs")
    gui = invocation.get("gui", {})
    check(gui.get("pid") == 13340 and isinstance(gui.get("session_id"), int) and gui["session_id"] > 0 and utc(gui.get("start_utc")) is not None, "GUI identity or start time differs")
    check(closure.get("schema") == "simlox-a17-v100-native-closure/v1" and closure.get("error") is None, "closure declares an error")
    check(closure.get("invocation_sha256") == sha(RUN / "invocation.json"), "invocation closure hash differs")
    check(invocation.get("publication_state") == closure.get("publication_state") == "not_published", "publication scope differs")

    source_paths = {
        "input": CASE / "native-input.json",
        "parent": PARENT,
        "contract": CASE / "contract.json",
        "builder": CASE / "build.py",
        "checker": CASE / "check_probe.py",
        "python": Path(invocation.get("planned_check", {}).get("executable", "")),
        "probe_script": CASE / "run_native_ssh.ps1",
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    }
    before = invocation.get("source_hashes_before", {})
    check(before == closure.get("source_hashes_before") == closure.get("source_hashes_after"), "before/after source hash records differ")
    for key, path in source_paths.items():
        check(path.is_file() and sha(path) == before.get(key), f"current source hash differs: {key}")
    check(invocation.get("contract_sha256") == before.get("contract") and invocation.get("probe_script_sha256") == before.get("probe_script") and invocation.get("simlox_exe_sha256") == before.get("simlox_exe"), "invocation component hashes differ")

    raw = closure.get("raw", {})
    files = {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"}
    check(set(raw) == files, "closure raw file set differs from run directory")
    for name, record in raw.items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == record.get("bytes") and sha(path) == record.get("sha256"), f"raw artifact seal differs: {name}")

    original = PureWindowsPath(invocation.get("original_run_dir", ""))
    check(original.is_absolute() and original.name == RUN_ID, "original Windows run path differs")
    expected_args = {
        "import": f'-silent -jimport "{original / "input.json"}" -save "{original / "model.sxi"}" -log "{original / "import.log"}" -close',
        "export": f'"{original / "model.sxi"}" -silent -jexport "{original / "roundtrip-raw.json"}" -log "{original / "export.log"}" -close',
        "calc": f'"{original / "model.sxi"}" -silent -threads 1 -calc -log "{original / "run.log"}" -close',
        "jsonreport": f'"{original / "model.sxo"}" -silent -jsonreport "{original / "report-raw.json"}" -log "{original / "report-export.log"}" -close',
    }
    planned = invocation.get("planned_commands", [])
    check([(x.get("name"), x.get("arguments")) for x in planned] == list(expected_args.items()), "planned native commands differ")
    check([x.get("name") for x in steps] == [*expected_args, "check_import_export"], "executed step sequence differs")
    previous = utc(invocation.get("created_utc"))
    for step in steps:
        name = step.get("name")
        start, end = utc(step.get("started_utc")), utc(step.get("completed_utc"))
        check(start is not None and end is not None and start <= end and (previous is None or previous <= start), f"step timestamps differ: {name}")
        previous = end
        check(step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True and step.get("error") is None, f"step status or GUI preservation differs: {name}")
        if name in expected_args:
            check(step.get("arguments") == expected_args[name], f"executed native arguments differ: {name}")

    parent_tables = tables(read_json(PARENT), "model")
    source_tables = tables(read_json(RUN / "input.json"), "model")
    observed_changed = {n for n in parent_tables.keys() | source_tables.keys() if parent_tables.get(n) != source_tables.get(n)}
    check(observed_changed == set(diff.get("changed_tables", {})), "A03-to-A17 table delta differs")
    for name, record in diff.get("changed_tables", {}).items():
        for side, collection in (("before", parent_tables), ("after", source_tables)):
            actual = rows(collection[name]) if name in collection else None
            check(actual == record.get(f"{side}_rows"), f"parent-diff {name} {side} rows differ")
    for name in parent_tables.keys() & source_tables.keys():
        check(parent_tables[name]["columns"] == source_tables[name]["columns"], f"inherited schema changed: {name}")
    def model_rows(name: str) -> list[dict]:
        return rows(source_tables[name])
    check(model_rows("Operations") == [{"USTID": "TEACH-GROUP", "PRID": "BASIC-SCHEDULE", "NOTE": None}], "group operation binding differs")
    check({r["UNID"]: r["STID"] for r in model_rows("Unit")} == {"TEACH-UNIT": "BASE-01", "TEACH-UNIT-2": "BASE-02"}, "explicit unit/base graph differs")
    check({r["USTID"]: r["QTYPS"] for r in model_rows("SystemDeployment")} == {"TEACH-UNIT": 1, "TEACH-UNIT-2": 1}, "one-aircraft-per-unit graph differs")
    check({r["USTID"]: (r["PRI"], r["XTIME"]) for r in model_rows("UnitGroupMember")} == {"TEACH-UNIT": (1, 0), "TEACH-UNIT-2": (2, 0)}, "unit group member graph differs")
    check(len(model_rows("UnitGroup")) == 1 and model_rows("UnitGroup")[0]["UGID"] == "TEACH-GROUP" and model_rows("UnitGroup")[0]["UNPR1"] == "N", "unit group definition differs")
    check({r["STID"] for r in model_rows("Station")} == {"BASE-01", "BASE-02"}, "base identities differ")
    check(len(model_rows("MissionType")) == 1 and model_rows("MissionType")[0]["NOS"] == model_rows("MissionType")[0]["MNOS"] == 2 and model_rows("MissionType")[0]["DURN"] == 2, "two-aircraft mission requirement differs")

    exported_tables = tables(read_json(RUN / "roundtrip-raw.json", native=True), "model")
    changed_business = [name for name in source_tables.keys() | exported_tables.keys() if business(source_tables.get(name, {"columns": [], "instances": []})) != business(exported_tables.get(name, {"columns": [], "instances": []}))]
    check(not changed_business, f"import/export business rows differ: {changed_business}")
    populated = sorted(name for name, table in source_tables.items() if business(table))
    row_containing = sorted(name for name, table in source_tables.items() if rows(table))
    check(len(populated) == 12 and len(row_containing) == 15, "source nonblank/row-containing table counts differ")
    for name, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!"), ("report-export.log", "Generating Json-report")):
        check(marker in (RUN / name).read_text(encoding="utf-8-sig", errors="replace"), f"native {name} completion marker absent")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log, "conversion counts differ")
    warning_codes = re.findall(r"warning #(\d+)", run_log)
    check(Counter(warning_codes) == Counter(("108", "126")), f"unexpected conversion warnings: {warning_codes}")
    check("Starting simulation..." in run_log and "Saving results ..." in run_log, "calculation completion markers absent")

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    timed = []
    for line in log.splitlines():
        m = re.match(r"^Time:\s*([0-9.eE+-]+)\s+(.*)$", line)
        if m:
            timed.append((float(m.group(1)), m.group(2)))
    def event(time: float, fragment: str) -> int:
        return sum(abs(t - time) < 1e-9 and fragment in body for t, body in timed)
    expected_events = [
        (7, "<TEACH-GROUP> mission ordered: BASIC-MISSION"),
        (7, f"{MISSION} mission created:"),
        (7, f"{MISSION} mission activated, systems requested: 2"),
        (7, f"{MISSION} mission allocates system: {AIRCRAFT[0]}"),
        (7, f"{MISSION} mission allocates system: {AIRCRAFT[1]}"),
        (8, f"{MISSION} mission starting, duration: 2 : {','.join(AIRCRAFT)}"),
        (10, f"{MISSION} mission success:"),
        (10, f"{MISSION} mission completed: {','.join(AIRCRAFT)}"),
    ]
    for time, fragment in expected_events:
        check(event(time, fragment) == 1, f"mission event differs at {time}: {fragment}")
    mission_actions = (" mission ordered:", " mission created:", " mission activated,", " mission allocates system:", " mission starting,", " mission success:", " mission completed:", " mission cancelled:", " mission aborted:")
    actual_mission_events = [(t, body) for t, body in timed if any(marker in body for marker in mission_actions)]
    check(len(actual_mission_events) == len(expected_events), "additional/missing mission lifecycle events")
    for aircraft, unit, base in ((AIRCRAFT[0], "TEACH-UNIT", "BASE-01"), (AIRCRAFT[1], "TEACH-UNIT-2", "BASE-02")):
        check(event(0, f"{aircraft} nbr ready increased at unit: <{unit} at <{base},0>>") == 1, f"initial aircraft/unit binding differs: {aircraft}")
        check(event(7, f"{aircraft} nbr ready decreased at unit: <{unit} at <{base},0>>") == 1, f"assignment aircraft/unit binding differs: {aircraft}")
        check(event(7, f"{aircraft} preparation started, mission: {MISSION}") == 1 and event(7, f"{aircraft} preparation ended, mission: {MISSION}") == 1, f"preparation lifecycle differs: {aircraft}")
        check(event(10, f"<TEACH-AIR-01,{base},0> System arrives {aircraft}, mission success,") == 1, f"return base differs: {aircraft}")
        check(event(10, f"{aircraft} nbr ready increased at unit: <{unit} at <{base},0>>") == 1, f"terminal aircraft/unit binding differs: {aircraft}")
        check(event(10, f"<{unit} at <{base},0>> systems ready: 1 :{aircraft}") == 1, f"terminal unit readiness differs: {aircraft}")
    check("mission cancelled:" not in log and "mission aborted:" not in log, "mission cancellation or abort occurred")
    check(" no failures " in log and log.count(" no failures ") == 2, "unexpected failure state on return")

    report_tables = tables(read_json(RUN / "report-raw.json", native=True), "report")
    summary = rows(report_tables["ResultSummary"])
    system = rows(report_tables["SystemResults"])
    check(len(summary) == 1 and all(summary[0].get(k) == v for k, v in {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}.items()), "ResultSummary mission metrics differ")
    check(len(system) == 72, "SystemResults interval count differs")
    check(len(rows(report_tables["StockTotalResults"])) == 72, "StockTotalResults interval count differs")
    flight_hours = mission_hours = 0.0
    for i, record in enumerate(system):
        start, end = i / 2, (i + 1) / 2
        flying = 2 if 8 <= start < 10 else 0
        assigned = 2 if 7 <= start < 10 else 0
        ready = 2 - assigned
        check(record.get("STINT") == start and record.get("ETINT") == end, f"SystemResults grid differs at {i}")
        check(record.get("UNID") == "Total over all Units" and record.get("SID") == "Total over all Systems", f"SystemResults aggregation differs at {i}")
        check(record.get("NSYA") == 2 and record.get("NSYRY") == ready and record.get("NSYMA") == assigned and record.get("NSYMO") == flying, f"SystemResults state differs at {i}")
        check(record.get("FTMO") == (1 if flying else 0), f"SystemResults mission fraction differs at {i}")
        check(record.get("NPSTA") == 0, f"unexpected preparation count at {i}")
        flight_hours += (record.get("NSYMO") or 0) * .5
        mission_hours += (record.get("FTMO") or 0) * .5
    check(math.isclose(flight_hours, 4) and math.isclose(mission_hours, 2), "mission/aircraft hours differ")
    check(system[-1].get("NSYRY") == 2 and system[-1].get("NSYA") == 2 and system[-1].get("NSYMA") == 0 and system[-1].get("NSYMO") == 0, "terminal readiness differs")
    check(rows(report_tables["ProblemDescription"]) == model_rows("ProblemDescription"), "report description differs from input")

    notes.extend([
        "Two sorties are established by the single launch/completion event carrying two distinct aircraft; the exported report contains aggregate SystemResults, not per-unit sortie rows.",
        "GUI preservation is based on sealed runner step checks and process identity; raw evidence does not prove GUI calculation or window content.",
        "The raw invocation records session-0 SSH and GUI identity; active-session and mutex ownership were enforced by the bound runner, not independently observable from the sealed files.",
        "Warnings 108 (simulation logging) and 126 (system without items) are explained by the model. No priority choice, XTIME effect, transfer, implicit unit, GUI-only behavior, or cross-engine equivalence is accepted.",
    ])
    return {
        "schema": "simlox-a17-v100-independent-readonly/v1",
        "review_date": "2026-09-29",
        "run_id": RUN_ID,
        "passed": not errors,
        "differences": errors,
        "evidence": {
            "parent_input_sha256": sha(PARENT),
            "child_input_sha256": sha(RUN / "input.json"),
            "invocation_sha256": sha(RUN / "invocation.json"),
            "closure_sha256": sha(RUN / "closure.json"),
            "report_sha256": sha(RUN / "report-raw.json"),
            "model_log_sha256": sha(RUN / "model.log"),
            "changed_tables": sorted(observed_changed),
            "populated_business_tables": populated,
            "row_containing_tables": row_containing,
            "native_warning_codes": warning_codes,
            "mission_instances": 1,
            "aircraft_ids": list(AIRCRAFT),
            "selected_units": ["TEACH-UNIT", "TEACH-UNIT-2"],
            "sorties": 2,
            "system_result_intervals": len(system),
            "flight_aircraft_hours": flight_hours,
            "terminal_aircraft_ready": system[-1].get("NSYRY"),
        },
        "scope": "independent_cli_behavior_review",
        "publication_state": "not_published",
        "limitations": notes,
    }


def main() -> int:
    try:
        result = verify()
    except Exception as exc:
        result = {"schema": "simlox-a17-v100-independent-readonly/v1", "run_id": RUN_ID, "passed": False, "differences": [f"review exception: {type(exc).__name__}: {exc}"], "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
