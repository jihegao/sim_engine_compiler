"""Read-only B03.var01 retrospective full-report replay. No native invocation.

Expected values come from pinned source rows, typed physical events, and the
contract's explicitly bounded empty-stock presentation. The native report is
read only at the final comparison gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT_SHA = "28765ddfeb99c595318d63cc0bd9e6a364bd2122d8a592b2fdd81a4d0a4cea44"
REVIEW_GO_SHA = "8d2eba9d13389e04be02500ce0afb727a42fad6f75fef3d159c67188e8895917"
SUMMARY = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "RSMTMF": 0,
           "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}
STOCK_NULL = {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS"}
STOCK_ZERO = {"NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT"}
SYSTEM_OCCUPANCY = {"NSYRY", "NSYMA", "NSYMO", "NSYMP", "NSYMR", "NSYA", "FTMO"}
SYSTEM_COUNTERS = {"NPSTA", "NPSUC", "STACC"}
REPORT_ROWS = {"ProblemDescription": 1, "ResultSummary": 1, "SystemResults": 72, "StockTotalResults": 72}


def digest(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check_pin(path: Path, pin: dict[str, object]) -> None:
    assert digest(path.read_bytes()) == {"bytes": pin["bytes"], "sha256": pin["sha256"]}, str(path)


def parse_native(data: bytes) -> object:
    """Remove trailing commas outside quoted strings, preserving string bytes."""
    source = data.decode("utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for position, char in enumerate(source):
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
        elif char == ",":
            next_position = position + 1
            while next_position < len(source) and source[next_position].isspace():
                next_position += 1
            if next_position == len(source) or source[next_position] not in "}]":
                out.append(char)
        else:
            out.append(char)
    assert not quoted and not escaped
    return json.loads("".join(out))


def tables(document: dict, root_key: str) -> dict[str, dict]:
    objects = document[root_key]["tables"]
    names = [table["name"] for table in objects]
    assert len(names) == len(set(names))
    return {table["name"]: table for table in objects}


def nonblank_rows(table: dict) -> list[tuple[str, list]]:
    rows = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            if any(value is not None for value in row):
                rows.append((instance["instance_name"], row))
    return rows


def source_rows(source: dict, name: str) -> list[dict[str, object]]:
    table = tables(source, "model")[name]
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for _, row in nonblank_rows(table)]


def check_provenance(contract: dict, git: str = "git") -> int:
    assert digest((HERE / "contract.json").read_bytes())["sha256"] == CONTRACT_SHA
    assert digest((HERE / "review/independent-contract-go-2026-10-07.md").read_bytes())["sha256"] == REVIEW_GO_SHA
    assert contract["version"] == "0.1.2" and contract["variant_id"] == "B03.var01"
    checked = 2
    base = contract["base_commit"]
    for entry in contract["accepted_source_files"]:
        path = REPO / entry["path"]
        check_pin(path, entry["local_disk"])
        published = subprocess.check_output([git, "show", f"{base}:{entry['path']}"], cwd=REPO)
        assert digest(published) == entry["published_git_at_base"], entry["path"]
        checked += 2
    catalog = contract["published_parent_scope"]["catalog_snapshot_at_base"]
    archived = (HERE / "preserved-v011/preserved-root-context/publication-index-at-base.json").read_bytes()
    assert digest(archived) == catalog["local_disk"]
    base_blob = subprocess.check_output([git, "show", f"{base}:cases/simlox-air-support/publication-index-v1.json"], cwd=REPO)
    assert digest(base_blob) == catalog["published_git_at_base"]
    live = json.loads((REPO / "cases/simlox-air-support/publication-index-v1.json").read_text(encoding="utf-8-sig"))
    historic = json.loads(archived.decode("utf-8-sig"))
    assert all(live[key] == historic[key] for key in historic if key != "entries")
    assert live["entries"][:len(historic["entries"])] == historic["entries"]
    checked += 3
    for entry in contract["installed"].values():
        check_pin(Path(entry["path"]), entry)
        checked += 1
    owner = contract["ownership"]["root_selection"]
    owner_copy = HERE / "preserved-v011/preserved-root-context/b03-owner-selection.json"
    check_pin(owner_copy, owner["local_disk"])
    original_owner = REPO / owner["path"]
    if original_owner.exists():
        check_pin(original_owner, owner["local_disk"])
    checked += 1
    for item in contract["excluded_v010"]["files"]:
        check_pin(REPO / item["original_path"], item)
        check_pin(HERE / item["inert_copy_path"], item)
        checked += 2
    excluded = contract["excluded_v011"]
    for item in excluded["files"] + excluded["root_probe_context"]:
        check_pin(REPO / item["original_path"], item)
        check_pin(HERE / item["inert_copy_path"], item)
        checked += 2
    b02_format = contract["full_report_gate"]["B02_format_corroboration"]
    check_pin(Path(b02_format["original_path"]), b02_format["local_disk"])
    checked += 1
    for entry in contract["parent_runs"]:
        directory = Path(entry["original_directory"])
        for name in ["input", "closure", "invocation"]:
            check_pin(directory / f"{name}.json", entry[name])
            checked += 1
        closure = json.loads((directory / "closure.json").read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == entry["run_id"] and closure["raw"] == entry["raw"]
        assert closure["input_sha256"] == contract["prerequisites"]["accepted_B03_input_sha256"]
        for name, pin in entry["raw"].items():
            check_pin(directory / name, pin)
            checked += 1
        for name, pin in entry["other_local_files"].items():
            check_pin(directory / name, pin)
            checked += 1
    failed, accepted = contract["parent_runs"]
    assert failed["status"] == "EXCLUDED_AUTHOR_VALIDATION_FAILURE"
    assert accepted["status"] == "ACCEPTED_PARENT_RUN"
    assert failed["raw"]["model.log"] == accepted["raw"]["model.log"]
    assert failed["raw"]["report-raw.json"] == accepted["raw"]["report-raw.json"]
    old_validator = failed["failed_validator_source"]
    assert old_validator["recorded_sha256"] == "450dbc7aa7b4a1ca79a2d4bd5dad1b946a40f3bf666d415ad65ad6bd6b448384"
    assert old_validator["original_bytes_available"] is False
    failed_dir = Path(failed["original_directory"])
    failed_verdict = json.loads((failed_dir / "validation.json").read_text(encoding="utf-8-sig"))
    assert failed_verdict["passed"] is False and failed_verdict["run_id"] == failed["run_id"]
    accepted_dir = Path(accepted["original_directory"])
    accepted_verdict = json.loads((accepted_dir / "validation.json").read_text(encoding="utf-8-sig"))
    assert accepted_verdict["passed"] is True and accepted_verdict["run_id"] == accepted["run_id"]
    invocation = json.loads((accepted_dir / "invocation.json").read_text(encoding="utf-8-sig"))
    assert invocation["run_id"] == accepted["run_id"] and invocation["session_id"] == 0
    assert invocation["ssh_connection_present"] is True and invocation["ssh_client_present"] is True
    assert "sshd.exe" in invocation["ssh_ancestor_names"]
    assert invocation["coexisting_gui"]["pid"] == 13340 and invocation["coexisting_gui"]["session_id"] == 1
    assert invocation["coexisting_gui"]["responding_at_preflight"] is True
    assert invocation["input_sha256"] == contract["prerequisites"]["accepted_B03_input_sha256"]
    steps = json.loads((accepted_dir / "steps.json").read_text(encoding="utf-8-sig"))
    assert [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"]
    assert all(type(step["exit_code"]) is int and step["exit_code"] == 0 and step["coexisting_gui_present_after"] is True for step in steps)
    converter = (accepted_dir / "run.log").read_text(encoding="utf-8-sig")
    assert "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter
    assert re.findall(r"\(warning #(\d+)\)", converter) == ["108", "126"]
    checked += 4
    return checked


def check_source_and_roundtrip(contract: dict, source: dict, export: dict) -> tuple[list[dict], int]:
    assert set(source) == set(export) == {"model"}
    assert set(source["model"]) == set(export["model"]) == {"database_version", "tables"}
    source_tables = tables(source, "model")
    export_tables = tables(export, "model")
    assert list(source_tables) == list(export_tables) and len(source_tables) == 31
    assert source["model"]["database_version"] == export["model"]["database_version"]
    populated = 0
    for name, original in source_tables.items():
        exported = export_tables[name]
        assert set(original) == set(exported) == {"name", "columns", "instances"}
        assert original["columns"] == exported["columns"], name
        assert len(original["instances"]) == len(exported["instances"]), name
        assert [item["instance_name"] for item in original["instances"]] == [item["instance_name"] for item in exported["instances"]], name
        assert nonblank_rows(original) == nonblank_rows(exported), name
        for before, after in zip(original["instances"], exported["instances"], strict=True):
            assert set(before) == set(after) == {"instance_name", "rows"}, name
            if before["rows"]:
                assert before["rows"] == after["rows"], name
            else:
                assert len(after["rows"]) == 1 and all(value is None for value in after["rows"][0]), name
        populated += bool(nonblank_rows(original))
    assert populated == 14
    controls = source_rows(source, "Control")
    assert len(controls) == 1
    control = controls[0]
    assert (control["NREPS"], control["SIMPE"], control["RCINT"], control["RCSTA"], control["RCEND"], control["ENLOG"], control["ENPM"]) == (1, 36, .5, 0, 36, "Y", "N")
    missions = source_rows(source, "MissionType")
    assert {m["MTID"] for m in missions} == {"COLD-FIRST", "HOT-SORTIE"}
    assert all((m["NOS"], m["MNOS"], m["NOPER"], m["DURN"]) == (1, 1, 1, 2) for m in missions)
    schedule = source_rows(source, "OperationProfile")
    assert [(row["SPRID"], row["STIM"]) for row in schedule] == [("COLD-FIRST", 8), ("HOT-SORTIE", 12), ("HOT-SORTIE", 16)]
    prep = {row["MTID"]: row for row in source_rows(source, "MissionPreparation")}
    assert {key: (value["TID"], value["DURN"], value["SID"], value["STID"]) for key, value in prep.items()} == {"COLD-FIRST": ("PREP-FIXED", .75, "TEACH-AIR-01", "BASE-01"), "HOT-SORTIE": ("HOT-PREP", .75, "TEACH-AIR-01", "BASE-01")}
    breakdown = source_rows(source, "TaskBreakDown")
    assert [(row["TID"], row["SEQ"], row["SUTID"]) for row in breakdown] == [("PREP-FIXED", 1, "INSPECT"), ("PREP-FIXED", 2, "SERVICE"), ("HOT-PREP", 1, "HOT-SERVICE")]
    assert math.isclose(sum(row["DURN"] for row in breakdown if row["TID"] == "PREP-FIXED"), .5, abs_tol=1e-12)
    assert math.isclose(sum(row["DURN"] for row in breakdown if row["TID"] == "HOT-PREP"), 1 / 6, abs_tol=1e-12)
    assert len(source_rows(source, "System")) == 1
    assert (source_rows(source, "System")[0]["SID"], source_rows(source, "System")[0]["FRT"]) == ("TEACH-AIR-01", 0)
    empty_mechanism_tables = {"Item", "ItemStructure", "SystemRepair", "ItemRepair", "ItemReorder",
                              "TaskResource", "Resource", "ResourceAllocation", "MaterielPM", "PMLocation",
                              "StockAllocation", "ItemReplacement", "SubTaskResource"}
    assert all(not source_rows(source, name) for name in empty_mechanism_tables)
    return schedule, populated


@dataclass(frozen=True)
class Event:
    index: int
    token: str
    time: float
    text: str

    @property
    def uncertainty(self) -> float:
        if "." not in self.token:
            return .5  # overridden for typed source-exact integer edges
        return .5 * 10 ** -len(self.token.split(".", 1)[1])


def events(log: bytes) -> list[Event]:
    out = []
    for index, line in enumerate(log.decode("utf-8-sig").splitlines()):
        match = re.match(r"^Time:\s*([0-9]+(?:\.[0-9]+)?)\s+(.*)$", line)
        if match:
            out.append(Event(index, match.group(1), float(match.group(1)), match.group(2)))
    assert out and all(a.time <= b.time for a, b in zip(out, out[1:]))
    return out


def account_for_every_timed_line(records: list[Event]) -> None:
    """Classify the complete printed timeline, including inert native diagnostics."""
    mission = r"<(?:COLD-FIRST|HOT-SORTIE),TEACH-UNIT,0,0,[012]>"
    aircraft = r"<TEACH-AIR-01,0>"
    stationed = r"<TEACH-AIR-01,BASE-01,0>"
    prep_task = rf"system preparation task [012] on {aircraft}"
    subtask = rf"subtask [0-3] seqno [12] within {prep_task}"
    specs = {
        "random_failure_diagnostic": (rf"{aircraft} Next random failure will occur 1e\+010", 25),
        "start_of_day": (r"\s*Start of day no [01]", 2),
        "unit_ready_snapshot": (rf"<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :{aircraft}", 4),
        "repair_priority_empty": (rf"{stationed} Repair task priority list:\s*", 3),
        "release_excess_resources": (rf"{aircraft} releases excess resources \(if any\)", 3),
        "ready_decreased": (rf"{aircraft} nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>", 3),
        "ready_increased": (rf"{aircraft} nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>", 4),
        "mission_ordered": (r"<TEACH-UNIT> mission ordered: (?:COLD-FIRST|HOT-SORTIE)", 3),
        "mission_created": (rf"{mission} mission created:\s*", 3),
        "mission_activated": (rf"{mission} mission activated, systems requested: 1", 3),
        "mission_allocates": (rf"{mission} mission allocates system: {aircraft}", 3),
        "preparation_started": (rf"{aircraft} preparation started, mission: {mission}", 3),
        "main_task_started": (rf"\s*{prep_task} started", 3),
        "subtask_started": (rf"\s*{subtask} started", 4),
        "resource_request_none": (rf"\s*{subtask} requests resources: no resources needed", 4),
        "resource_availability_test": (rf"\s*{subtask} resource availability test", 4),
        "subtask_performing": (rf"\s*{subtask} starts performing, planned to last for [0-9]+(?:\.[0-9]+)? hours", 4),
        "subtask_completed": (rf"\s*{subtask} completed", 4),
        "main_task_completed": (rf"\s*{prep_task} completed", 3),
        "preparation_ended": (rf"{aircraft} preparation ended, mission: {mission}", 3),
        "mission_start": (rf"{mission} mission starting, duration: 2 : {aircraft}", 3),
        "on_station_task_start": (rf"{mission} task starting: {aircraft}", 3),
        "on_station_task_end": (rf"{mission} task completed: {aircraft}", 3),
        "mission_success": (rf"{mission} mission success:\s*", 3),
        "mission_completed": (rf"{mission} mission completed: {aircraft}", 3),
        "soon_ready": (rf"{stationed} System soon ready {aircraft}, estimated remaining time: 0", 3),
        "turnround_started": (rf"{aircraft} turnround started, mission: {mission} reduction factor: 1", 3),
        "turnround_ended": (rf"{aircraft} turnround ended, mission: {mission}", 3),
        "system_arrives": (rf"{stationed} System arrives {aircraft}, mission success,\s*", 3),
        "system_ready": (rf"{stationed} System ready {aircraft}", 6),
    }
    compiled = {name: (re.compile(pattern), count) for name, (pattern, count) in specs.items()}
    categories: dict[str, list[Event]] = {name: [] for name in specs}
    for record in records:
        matched = [name for name, (pattern, _) in compiled.items() if pattern.fullmatch(record.text)]
        assert len(matched) == 1, (record.index, record.text, matched)
        categories[matched[0]].append(record)
    assert len(records) == 121
    assert all(len(categories[name]) == count for name, (_, count) in specs.items()), \
        {name: len(rows) for name, rows in categories.items()}
    # These diagnostics do not supply a physical state transition. Their exact
    # typed timetable is a bounded native presentation check for this sealed run.
    diagnostic_times = {
        "random_failure_diagnostic": Counter({"0": 1, "7": 2, "7.16667": 3, "7.5": 2,
                                               "8": 2, "10": 1, "11": 2, "11.1667": 2,
                                               "12": 2, "14": 1, "15": 2, "15.1667": 2,
                                               "16": 2, "18": 1}),
        "start_of_day": Counter({"0": 1, "24": 1}),
        "unit_ready_snapshot": Counter({"0": 1, "10": 1, "14": 1, "18": 1}),
        "repair_priority_empty": Counter({"10": 1, "14": 1, "18": 1}),
        "release_excess_resources": Counter({"7": 1, "11": 1, "15": 1}),
        "ready_decreased": Counter({"7": 1, "11": 1, "15": 1}),
    }
    for name, expected in diagnostic_times.items():
        assert Counter(event.token for event in categories[name]) == expected, name


def one(records: list[Event], phrase: str, expected_time: float, *, source_exact: bool = False,
        whole_line: bool = False) -> Event:
    def matches(record: Event) -> bool:
        if not (record.text.strip() == phrase if whole_line else phrase in record.text):
            return False
        bound = 0 if source_exact else record.uncertainty + 1e-10
        return abs(record.time - expected_time) <= bound
    found = [record for record in records if matches(record)]
    assert len(found) == 1, (phrase, len(found))
    record = found[0]
    bound = 0 if source_exact else record.uncertainty + 1e-10
    assert abs(record.time - expected_time) <= bound, (phrase, record.time, expected_time, bound)
    return record


def ordered(*records: Event) -> None:
    assert all(a.index < b.index for a, b in zip(records, records[1:])), [r.text for r in records]


def check_events(records: list[Event], schedule: list[dict], mission_types: list[dict],
                 breakdown: list[dict], declared_integrals: dict[str, float]) -> dict[str, list[tuple[float, float]]]:
    account_for_every_timed_line(records)
    assert len([r for r in records if " mission ordered:" in r.text]) == 3
    assert len([r for r in records if " mission starting," in r.text]) == 3
    assert len([r for r in records if " mission success:" in r.text]) == 3
    assert len([r for r in records if " mission completed:" in r.text]) == 3
    assert len([r for r in records if "preparation started, mission:" in r.text]) == 3
    assert len([r for r in records if "preparation ended, mission:" in r.text]) == 3
    assert len([r for r in records if " task starting:" in r.text]) == 3
    assert len([r for r in records if " task completed:" in r.text]) == 3
    assert len([r for r in records if "turnround started, mission:" in r.text]) == 3
    assert len([r for r in records if "turnround ended, mission:" in r.text]) == 3
    assert len([r for r in records if "System soon ready" in r.text]) == 3
    assert len([r for r in records if "System arrives <TEACH-AIR-01,0>, mission success" in r.text]) == 3
    assert len([r for r in records if "System ready <TEACH-AIR-01,0>" in r.text]) == 6
    assert len([r for r in records if "nbr ready decreased at unit:" in r.text]) == 3
    assert len([r for r in records if "nbr ready increased at unit:" in r.text]) == 4
    assert len([r for r in records if re.fullmatch(r"\s*system preparation task \d+ on .* started", r.text)]) == 3
    assert len([r for r in records if re.fullmatch(r"\s*system preparation task \d+ on .* completed", r.text)]) == 3
    assert len([r for r in records if re.fullmatch(r"\s*subtask \d+ seqno \d+ within system preparation task \d+ on .* started", r.text)]) == 4
    assert len([r for r in records if re.fullmatch(r"\s*subtask \d+ seqno \d+ within system preparation task \d+ on .* completed", r.text)]) == 4
    assert not any("mission canceled" in r.text or "mission cancelled" in r.text or "allocated to maintenance task" in r.text or "Replacement item demand" in r.text for r in records)
    intervals: dict[str, list[tuple[float, float]]] = {name: [] for name in
              ("ready", "preparation", "prepared_wait", "operation")}
    ready_since = 0.0
    mission_by_id = {row["MTID"]: row for row in mission_types}
    work_by_task_seq = {(row["TID"], row["SEQ"]): row["DURN"] for row in breakdown}
    assert len(mission_by_id) == 2 and len(work_by_task_seq) == 3
    for ordinal, profile in enumerate(schedule):
        mtid = profile["SPRID"]
        launch = profile["STIM"]
        notice = launch - 1
        finish = launch + 2
        mission = f"<{mtid},TEACH-UNIT,0,0,{ordinal}>"
        aircraft = "<TEACH-AIR-01,0>"
        task_id = ordinal
        task_name = "PREP-FIXED" if ordinal == 0 else "HOT-PREP"
        prep_end = notice + (.5 if ordinal == 0 else 1 / 6)
        intervals["ready"].append((ready_since, notice))
        head = [one(records, f"mission ordered: {mtid}", notice, source_exact=True),
                one(records, f"{mission} mission created:", notice, source_exact=True),
                one(records, f"{mission} mission activated", notice, source_exact=True),
                one(records, f"{mission} mission allocates system: {aircraft}", notice, source_exact=True),
                one(records, f"{aircraft} preparation started, mission: {mission}", notice, source_exact=True),
                one(records, f"system preparation task {task_id} on {aircraft} started", notice, source_exact=True, whole_line=True)]
        ordered(*head)
        step_numbers = [(0, 1, notice, notice + 1 / 6), (1, 2, notice + 1 / 6, prep_end)] if ordinal == 0 else [(ordinal + 1, 1, notice, prep_end)]
        previous = head[-1]
        for subtask, seq, start, end in step_numbers:
            stem = f"subtask {subtask} seqno {seq} within system preparation task {task_id} on {aircraft}"
            step = [one(records, stem + " started", start, source_exact=(start == notice)),
                    one(records, stem + " requests resources: no resources needed", start, source_exact=(start == notice)),
                    one(records, stem + " resource availability test", start, source_exact=(start == notice)),
                    one(records, stem + " starts performing", start, source_exact=(start == notice)),
                    one(records, stem + " completed", end, source_exact=(end == 7.5))]
            ordered(previous, *step)
            planned = re.search(r"planned to last for ([0-9]+(?:\.[0-9]+)?) hours$", step[3].text)
            assert planned, step[3].text
            literal = planned.group(1)
            decimal_half_unit = .5 * 10 ** -len(literal.split(".", 1)[1]) if "." in literal else .5
            assert decimal_half_unit + 5e-7 <= 1.1e-4 * .5, (stem, literal, "annotation precision exceeds contract ceiling")
            source_duration = work_by_task_seq[(task_name, seq)]
            assert abs(float(literal) - source_duration) <= decimal_half_unit + 5e-7, (stem, literal, source_duration)
            previous = step[-1]
        duration = mission_by_id[mtid]["DURN"]
        task_start = launch + mission_by_id[mtid]["TFOUT"] * duration
        task_end = finish - mission_by_id[mtid]["TFRET"] * duration
        tail = [one(records, f"system preparation task {task_id} on {aircraft} completed", prep_end, source_exact=(prep_end == 7.5), whole_line=True),
                one(records, f"{aircraft} preparation ended, mission: {mission}", prep_end, source_exact=(prep_end == 7.5)),
                one(records, f"{mission} mission starting, duration: 2 : {aircraft}", launch, source_exact=True),
                one(records, f"{mission} task starting: {aircraft}", task_start, source_exact=True),
                one(records, f"{mission} task completed: {aircraft}", task_end, source_exact=True),
                one(records, f"{mission} mission success:", finish, source_exact=True),
                one(records, f"{mission} mission completed: {aircraft}", finish, source_exact=True),
                one(records, f"<TEACH-AIR-01,BASE-01,0> System soon ready {aircraft}, estimated remaining time: 0", finish, source_exact=True),
                one(records, f"{aircraft} turnround started, mission: {mission} reduction factor: 1", finish, source_exact=True),
                one(records, f"{aircraft} turnround ended, mission: {mission}", finish, source_exact=True),
                one(records, f"System arrives {aircraft}, mission success", finish, source_exact=True)]
        ordered(previous, *tail)
        ready = [r for r in records if r.time == finish and f"System ready {aircraft}" in r.text]
        assert len(ready) == 2 and min(r.index for r in ready) > tail[-1].index
        increased = one(records, f"{aircraft} nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>", finish, source_exact=True)
        assert tail[-1].index < increased.index < min(r.index for r in ready)
        intervals["preparation"].append((head[4].time, prep_end))
        intervals["prepared_wait"].append((prep_end, tail[2].time))
        intervals["operation"].append((tail[2].time, tail[5].time))
        ready_since = increased.time
    assert len([r for r in records if "requests resources: no resources needed" in r.text]) == 4
    assert len([r for r in records if "starts performing, planned to last for" in r.text]) == 4
    initial_ready = one(records, "<TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>", 0, source_exact=True)
    assert initial_ready.index < one(records, "mission ordered: COLD-FIRST", 7, source_exact=True).index
    assert not any(r.time > 18 and ("mission ordered:" in r.text or "preparation started" in r.text) for r in records)
    intervals["ready"].append((ready_since, 36.0))
    integral_keys = {"ready": "NSYRY_unassigned_ready", "preparation": "NSYMP_active_preparation",
                     "prepared_wait": "NSYMR_assigned_prepared_waiting", "operation": "NSYMO_operation"}
    expected_integrals = {
        key: sum(b - a for a, b in spans) for key, spans in intervals.items()}
    declared = declared_integrals
    for key, field in integral_keys.items():
        assert math.isclose(expected_integrals[key], declared[field], abs_tol=1e-10), (field, expected_integrals[key])
    assigned = expected_integrals["preparation"] + expected_integrals["prepared_wait"] + expected_integrals["operation"]
    assert math.isclose(assigned, declared["NSYMA_total_assigned"], abs_tol=1e-10)
    assert math.isclose(36.0, declared["NSYA_total_aircraft"], abs_tol=1e-10)
    assert math.isclose(expected_integrals["operation"], declared["FTMO_operation_for_one_aircraft"], abs_tol=1e-10)
    return intervals


def overlap(start: float, end: float, intervals: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(end, b) - max(start, a)) for a, b in intervals)


def report_schema(contract: dict, report: dict) -> dict[str, dict]:
    assert set(report) == {"report"}
    assert set(report["report"]) == {"tables"}
    named = tables(report, "report")
    declared = contract["full_report_gate"]
    assert list(named) == [entry["name"] for entry in declared["native_tables_in_order"]]
    for name, table in named.items():
        assert set(table) == {"name", "columns", "instances"}, name
        expected_names = declared["column_order_exact"][name]
        assert [column["name"] for column in table["columns"]] == expected_names, name
        expected_columns = []
        for column in expected_names:
            if column == "PDESC" or column in {"UNID", "SID"}:
                datum = "string"
            elif column == "NREP":
                datum = "integer"
            else:
                datum = "double"
            meta = {"datatype": datum, "name": column}
            if (name == "SystemResults" and column in {"UNID", "SID", "STINT", "ETINT"}) or (name == "StockTotalResults" and column in {"STINT", "ETINT"}):
                meta["key"] = True
            expected_columns.append(meta)
        assert table["columns"] == expected_columns, name
        assert len(table["instances"]) == 1
        assert set(table["instances"][0]) == {"instance_name", "rows"}, name
        assert table["instances"][0]["instance_name"] == declared["instance_names_exact"][name]
        assert len(table["instances"][0]["rows"]) == REPORT_ROWS[name]
        assert all(len(row) == len(expected_names) for row in table["instances"][0]["rows"])
    return named


def report_expected(contract: dict, source: dict, intervals: dict[str, list[tuple[float, float]]]) -> dict[str, list[dict]]:
    description = source_rows(source, "ProblemDescription")[0]["PDESC"]
    values = {"ProblemDescription": [{"PDESC": description}], "ResultSummary": [SUMMARY.copy()],
              "SystemResults": [], "StockTotalResults": []}
    system_columns = contract["full_report_gate"]["column_order_exact"]["SystemResults"]
    stock_columns = contract["full_report_gate"]["column_order_exact"]["StockTotalResults"]
    field_basis = contract["full_report_gate"]["system_zero_field_basis"]
    event_zero = set(field_basis["source_event_zero_fields"])
    presentation_zero = field_basis["bounded_native_presentation_fields"]
    assert set(presentation_zero) == {"NSYAL", "STREQ", "STF", "STLOW", "SYDTU"}
    assert all(value == 0 for value in presentation_zero.values())
    keys = {"UNID", "SID", "STINT", "ETINT"}
    dynamic = {"NSYRY", "NSYMP", "NSYMR", "NSYMO", "NSYMA", "NSYA", "FTMO", "STACC", "NPSTA", "NPSUC"}
    assert set(system_columns) == keys | dynamic | event_zero | set(presentation_zero) | {"SYDT"}
    assert len(event_zero) == 20 and len(set(system_columns)) == 40
    for index in range(72):
        start, end = index / 2, (index + 1) / 2
        row = {name: 0 for name in event_zero}
        row.update(presentation_zero)
        row.update({"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": start, "ETINT": end,
                    "SYDT": None, "NSYA": 1})
        row["NSYRY"] = overlap(start, end, intervals["ready"]) / .5
        row["NSYMP"] = overlap(start, end, intervals["preparation"]) / .5
        row["NSYMR"] = overlap(start, end, intervals["prepared_wait"]) / .5
        row["NSYMO"] = overlap(start, end, intervals["operation"]) / .5
        row["NSYMA"] = row["NSYMP"] + row["NSYMR"] + row["NSYMO"]
        row["FTMO"] = row["NSYMO"]  # one physical aircraft in one unit
        row["STACC"] = int(any(a <= start < b for a, b in intervals["operation"]))
        row["NPSTA"] = sum(start <= a < end for a, _ in intervals["preparation"])
        row["NPSUC"] = sum(start <= b < end for _, b in intervals["preparation"])
        assert set(row) == set(system_columns)
        assert abs(row["NSYRY"] + row["NSYMA"] - 1) < 1e-10
        values["SystemResults"].append(row)
        stock = {name: 0 for name in STOCK_ZERO}
        stock.update({"STINT": start, "ETINT": end, "PNB": 1})
        stock.update({name: None for name in STOCK_NULL})
        assert set(stock) == set(stock_columns)
        assert all(stock[name] == 0 for name in STOCK_ZERO)
        values["StockTotalResults"].append(stock)
    return values


def field_bound(table: str, field: str, expected: object, row_index: int, records: list[Event]) -> float:
    if table != "SystemResults" or field not in SYSTEM_OCCUPANCY:
        return 0
    if isinstance(expected, bool) or not isinstance(expected, (int, float)) or expected == 0 or float(expected).is_integer():
        return 0
    # The only fractional state boundaries are the hot preparation completions.
    assert row_index in {22, 30} and field in {"NSYMP", "NSYMR"}
    expected_time = 11 + 1 / 6 if row_index == 22 else 15 + 1 / 6
    matching = [r for r in records if "preparation ended, mission: <HOT-SORTIE" in r.text and abs(r.time - expected_time) <= r.uncertainty + 1e-10]
    assert len(matching) == 1
    bound = matching[0].uncertainty / .5 + 5e-7
    assert bound <= 1.1e-4
    return bound


def same_cell(observed: object, expected: object, bound: float) -> bool:
    if expected is None or isinstance(expected, str):
        return type(observed) is type(expected) and observed == expected
    if isinstance(observed, bool) or not isinstance(observed, (int, float)) or not math.isfinite(observed):
        return False
    if bound == 0:
        return observed == expected
    return abs(observed - expected) <= bound


def compare_report(contract: dict, report: dict, expected: dict[str, list[dict]], records: list[Event]) -> int:
    named = report_schema(contract, report)
    count = 0
    for name, table in named.items():
        columns = [column["name"] for column in table["columns"]]
        rows = table["instances"][0]["rows"]
        for row_index, (observed_row, expected_row) in enumerate(zip(rows, expected[name], strict=True)):
            for field, observed in zip(columns, observed_row, strict=True):
                target = expected_row[field]
                bound = field_bound(name, field, target, row_index, records)
                assert same_cell(observed, target, bound), (name, row_index, field, observed, target, bound)
                count += 1
    assert count == 4044
    return count


def run(*, report_override: dict | None = None, log_override: bytes | None = None) -> dict[str, object]:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    source_checks = check_provenance(contract)
    raw = Path(contract["parent_runs"][1]["original_directory"])
    source = json.loads((raw / "input.json").read_text(encoding="utf-8-sig"))
    export = parse_native((raw / "roundtrip-raw.json").read_bytes())
    schedule, populated = check_source_and_roundtrip(contract, source, export)
    log = (raw / "model.log").read_bytes() if log_override is None else log_override
    records = events(log)
    intervals = check_events(records, schedule, source_rows(source, "MissionType"),
                             source_rows(source, "TaskBreakDown"), contract["full_report_gate"]["system_integrals_h"])
    expected = report_expected(contract, source, intervals)
    report = parse_native((raw / "report-raw.json").read_bytes()) if report_override is None else report_override
    cells = compare_report(contract, report, expected, records)
    return {"schema": "b03-var01-author-readonly-replay/v1", "decision": "GO_BOUNDED_AUTHOR_REPLAY",
            "contract_sha256": CONTRACT_SHA, "accepted_run_id": contract["parent_runs"][1]["run_id"],
            "excluded_run_id": contract["parent_runs"][0]["run_id"], "source_and_raw_identity_checks": source_checks,
            "roundtrip_populated_tables": populated, "report_cells": cells,
            "state_integrals_h": contract["full_report_gate"]["system_integrals_h"],
            "new_native_runs": 0, "scope": "retrospective explicit cold-first full-report classification only"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write to a new path only; default prints read-only verdict")
    args = parser.parse_args()
    verdict = json.dumps(run(), sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as target:
            target.write(verdict)
    else:
        print(verdict, end="")
