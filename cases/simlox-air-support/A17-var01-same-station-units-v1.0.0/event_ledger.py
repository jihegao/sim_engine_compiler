"""Source-bound two-unit physical ledger and complete log-form check."""

from __future__ import annotations

import hashlib
import json
import re

from model_common import FORMS_SHA, HERE, read_pinned_json

UNIT = {0: "TEACH-UNIT", 1: "TEACH-UNIT-2"}
MISSION = "<BASIC-MISSION,TEACH-GROUP,0,0,0>"


def line_at(lines: list[str], index: int, exact: str) -> None:
    assert lines[index - 1] == exact, (index, lines[index - 1], exact)


def timed(lines: list[str]) -> list[float]:
    result = []
    for line in lines:
        if line.startswith("Time:"):
            match = re.match(r"^Time: ([0-9]+(?:\.[0-9]+)?)\b", line)
            assert match, line
            result.append(float(match.group(1)))
    assert result == sorted(result)
    return result


def semantic(raw: bytes, require_primary: bool = True) -> dict:
    assert raw.endswith(b"\r\n") and raw.count(b"\r\n") == 60 and raw.count(b"\n") == 60
    lines = raw.decode("utf-8-sig").splitlines()
    assert len(lines) == 60 and lines[:2] == ["SIMLOX LOG FILE", "36"]
    hours = timed(lines)
    assert len(hours) == 52
    assert sorted(set(hours)) == [0, 7, 8, 8.5, 9.5, 10, 24]
    forms = read_pinned_json(HERE / "prospective-complete-log-forms.json", FORMS_SHA)["full_forms"]
    assert len(forms) == 8

    line_at(lines, 9, "Time: 0  Start of day no 0")
    ready = {0: 0, 1: 0}
    owner = dict(UNIT)
    for system, (failure_line, ready_line, count_line) in enumerate(((3, 4, 5), (6, 7, 8))):
        assert f"<TEACH-AIR-01,{system}> Next random failure will occur 1e+010" in lines[failure_line - 1]
        expected = f"Time: 0 <TEACH-AIR-01,{system}> nbr ready increased at unit: <{UNIT[system]} at <BASE-01,"
        assert lines[ready_line - 1].startswith(expected)
        assert lines[ready_line - 1].endswith(">>")
        ready[system] += 1
        assert lines[count_line - 1].startswith(f"Time: 0 <{UNIT[system]} at <BASE-01,")
        assert lines[count_line - 1].endswith(f"> systems ready: 1 :<TEACH-AIR-01,{system}>")

    line_at(lines, 10, "Time: 7 <TEACH-GROUP> mission ordered: BASIC-MISSION")
    line_at(lines, 11, f"Time: 7 {MISSION} mission created: ")
    line_at(lines, 12, f"Time: 7 {MISSION} mission activated, systems requested: 2")
    for system, allocation, decrement in ((0, 13, 14), (1, 16, 17)):
        line_at(lines, allocation, f"Time: 7 {MISSION} mission allocates system: <TEACH-AIR-01,{system}>")
        assert ready[system] == 1 and owner[system] == UNIT[system]
        assert lines[decrement - 1].startswith(f"Time: 7 <TEACH-AIR-01,{system}> nbr ready decreased at unit: <{UNIT[system]} at <BASE-01,")
        ready[system] -= 1
        assert ready[system] == 0
    line_at(lines, 15, "Time: 7 <TEACH-AIR-01,0> releases excess resources (if any)")
    line_at(lines, 18, "Time: 7 <TEACH-AIR-01,1> releases excess resources (if any)")
    for system, start, end, marker in ((0, 19, 21, 22), (1, 20, 23, 24)):
        line_at(lines, start, f"Time: 7 <TEACH-AIR-01,{system}> preparation started, mission: {MISSION}")
        line_at(lines, end, f"Time: 7 <TEACH-AIR-01,{system}> preparation ended, mission: {MISSION}")
        line_at(lines, marker, f"Time: 7 <TEACH-AIR-01,{system}> Next random failure will occur 1e+010")
    for system, i in ((0, 25), (0, 26), (1, 27), (1, 28)):
        line_at(lines, i, f"Time: 8 <TEACH-AIR-01,{system}> Next random failure will occur 1e+010")
    line_at(lines, 29, f"Time: 8 {MISSION} mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
    line_at(lines, 30, f"Time: 8.5 {MISSION} task starting: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
    line_at(lines, 31, f"Time: 9.5 {MISSION} task completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
    line_at(lines, 32, f"Time: 10 {MISSION} mission success: ")
    line_at(lines, 33, f"Time: 10 {MISSION} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
    for system, marker, soon, start in ((0, 34, 35, 36), (1, 37, 38, 39)):
        line_at(lines, marker, f"Time: 10 <TEACH-AIR-01,{system}> Next random failure will occur 1e+010")
        assert lines[soon - 1].startswith("Time: 10 <TEACH-AIR-01,BASE-01,")
        assert lines[soon - 1].endswith(f"> System soon ready <TEACH-AIR-01,{system}>, estimated remaining time: 0")
        line_at(lines, start, f"Time: 10 <TEACH-AIR-01,{system}> turnround started, mission: {MISSION} reduction factor: 1")

    return_order = []
    for first in (40, 50):
        block = lines[first - 1:first + 9]
        assert len(block) == 10
        match = re.fullmatch(r"Time: 10 <TEACH-AIR-01,([01])> turnround ended, mission: " + re.escape(MISSION), block[0])
        assert match
        system = int(match.group(1))
        assert system not in return_order and owner[system] == UNIT[system] and ready[system] == 0
        return_order.append(system)
        assert block[1].startswith("Time: 10 <TEACH-AIR-01,BASE-01,")
        assert block[1].endswith(f"> System arrives <TEACH-AIR-01,{system}>, mission success, ")
        assert block[2:4] == [" no failures ", " no PMTasks"]
        assert block[4].startswith(f"Time: 10 <TEACH-AIR-01,{system}> nbr ready increased at unit: <{UNIT[system]} at <BASE-01,")
        assert block[5] == block[6]
        assert block[5].startswith("Time: 10 <TEACH-AIR-01,BASE-01,")
        assert block[5].endswith(f"> System ready <TEACH-AIR-01,{system}>")
        assert block[7].startswith(f"Time: 10 <{UNIT[system]} at <BASE-01,")
        assert block[7].endswith(f"> systems ready: 1 :<TEACH-AIR-01,{system}>")
        assert block[8].startswith("Time: 10 <TEACH-AIR-01,BASE-01,")
        assert block[8].endswith("> Repair task priority list: ")
        assert block[9] == "   "
        ready[system] += 1
    assert sorted(return_order) == [0, 1] and ready == {0: 1, 1: 1}
    line_at(lines, 60, "Time: 24  Start of day no 1")

    matched = [f for f in forms if f["lines"] == lines]
    assert len(matched) == 1, "complete lexical form outside frozen finite set"
    arm = matched[0]
    assert len(raw) == arm["crlf_bytes"]
    assert hashlib.sha256(raw).hexdigest() == arm["crlf_sha256"], "exact CRLF log bytes differ"
    assert arm["h10_return_block_order"] == return_order
    if require_primary:
        assert arm["status"] == "PRIMARY_CONTRACT_PASS_CANDIDATE", "predeclared diagnostic arm is NO_GO"
    return {"schema": "a17-var01-physical-log/v1", "passed": True, "full_lines": 60, "timed_lines": 52,
            "arm_id": arm["arm_id"], "arm_status": arm["status"], "ready_by_unit": dict(zip(UNIT.values(), ready.values(), strict=True)),
            "owner_by_physical_id": owner, "mission_id": MISSION, "mission_success_hour": 10,
            "native_calls": 0}


if __name__ == "__main__":
    raise SystemExit("Use semantic(raw) from a source-bound checker")
