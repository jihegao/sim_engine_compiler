"""Full predeclared E02.var02 physical transcript and ID0 causal ledger."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from model_common import HERE, PATTERN_PIN, exact, strict_json

PATTERNS = HERE / "preserved-oracle/log-patterns.json"
AIR = "<TEACH-AIR-01,0>"
LRU = "<TEACH-LRU-01,0,0>"
M2 = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
M3 = "<BASIC-MISSION,TEACH-UNIT,0,0,2>"


def semantic(raw: bytes, patterns: dict | None = None) -> dict[str, object]:
    if patterns is None:
        patterns = strict_json(exact(PATTERNS, PATTERN_PIN))
    assert type(patterns) is dict and set(patterns) == {
        "schema", "physical_lines", "timed_lines", "line_ending", "status", "lines"}
    assert patterns["physical_lines"] == 123 and patterns["timed_lines"] == 99
    assert type(patterns["lines"]) is list and len(patterns["lines"]) == 123
    assert not raw.startswith(b"\xef\xbb\xbf") and raw.endswith(b"\r\n")
    assert raw.count(b"\n") == raw.count(b"\r\n") == 123
    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == 123
    timed = 0
    for index, (text, row) in enumerate(zip(lines, patterns["lines"], strict=True)):
        assert type(row) is dict
        if row["kind"] == "literal":
            assert set(row) == {"kind", "text"} and text == row["text"], (index, text)
        else:
            assert set(row) == {"kind", "prefix", "number_regex", "finite", "greater_than_hour"}
            assert row["kind"] == "bounded_numeric" and index == 103
            assert row["finite"] is True and type(row["greater_than_hour"]) in (int, float)
            assert text.startswith(row["prefix"])
            number = text[len(row["prefix"]):]
            assert re.fullmatch(row["number_regex"], number)
            assert math.isfinite(float(number)) and float(number) > row["greater_than_hour"] == 34
        timed += text.startswith("Time: ")
    assert timed == 99
    # Source-derived state transitions: one aircraft and one LRU, no second launch.
    assert lines[61].endswith("planned to last for 10.75 hours")
    assert [line.split(" ", 2)[1] for line in lines[62:67]] == ["19", "19", "19", "19", "20.3333"]
    assert all(M2 in lines[i] for i in range(63, 67))
    assert "mission waiting:  timeout at 20.3333" in lines[65]
    assert "mission cancelled:" in lines[66]
    assert lines[67:73] == [
        " Systems ready: ", " Systems in prep: ", " Systems in reconfig: ",
        " Systems preassigned: ", " Systems in assign buffer: ", ""]
    assert all("mission allocates system:" not in line and "mission starting," not in line
               for line in lines if M2 in line)
    assert "direct repair subtask" in lines[73] and "completed" in lines[73]
    assert all(LRU in lines[i] for i in (74, 75, 76))
    assert "Backorder removed, waiting time was 10.9167" in lines[77]
    assert all(AIR in lines[i] for i in (80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91))
    assert "System ready" in lines[91] and "systems ready: 1" in lines[92]
    assert lines[93] == "Time: 24  Start of day no 1"
    assert all(M3 in lines[i] for i in (95, 96, 97, 100, 101, 105, 106, 107, 108, 109))
    assert "mission allocates system" in lines[97] and AIR in lines[97]
    assert "mission starting, duration: 2" in lines[105]
    assert "task starting:" in lines[106] and "task completed:" in lines[107]
    assert "mission success:" in lines[108] and "mission completed:" in lines[109]
    assert "turnround started" in lines[112] and "turnround ended" in lines[113]
    assert "System arrives" in lines[114] and "nbr ready increased" in lines[117]
    assert "systems ready: 1" in lines[120]
    return {"schema": "e02-var02-physical-ledger/v104", "physical_lines": 123,
            "timed_lines": 99, "second_mission_cancel_hour": 20.3333,
            "repair_complete_hour": 20.9167, "aircraft_ready_hour": 21.25,
            "third_mission_success_hour": 34, "terminal_backorders": 0}


def verify_file(path: Path) -> dict[str, object]:
    return semantic(path.read_bytes())
