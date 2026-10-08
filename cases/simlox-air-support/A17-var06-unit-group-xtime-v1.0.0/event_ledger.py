"""Full physical-log gate and independent-under-hash group mission ledger."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from model_common import HERE, LOG_SHA

M = "<BASIC-MISSION,TEACH-GROUP,0,0,0>"
AIR = ["<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>"]
UNITS = ["<TEACH-UNIT at <BASE-01,0>>", "<TEACH-UNIT-2 at <BASE-02,0>>"]
BASES = ["BASE-01", "BASE-02"]
CONTINUATIONS = {0: "SIMLOX LOG FILE", 1: "36", 41: " no failures ",
                 42: " no PMTasks", 48: "   ", 51: " no failures ",
                 52: " no PMTasks", 58: "   "}
TIME_RE = re.compile(r"^Time: (0|7|8|8\.5|9\.5|10|24) (.*)$")


def semantic(raw: bytes) -> dict:
    assert not raw.startswith(b"\xef\xbb\xbf") and raw.count(b"\n") == raw.count(b"\r\n") == 60
    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == 60
    assert {i: text for i, text in enumerate(lines) if not text.startswith("Time: ")} == CONTINUATIONS
    timed = []
    for i, line in enumerate(lines):
        if i in CONTINUATIONS:
            continue
        match = TIME_RE.fullmatch(line)
        assert match is not None, (i, line)
        timed.append((i, float(match.group(1)), match.group(2)))
    assert len(timed) == 52 and [h for _, h, _ in timed] == sorted(h for _, h, _ in timed)

    def unique(hour: float, fragment: str) -> int:
        hits = [i for i, h, body in timed if h == hour and fragment in body]
        assert len(hits) == 1, (hour, fragment, hits)
        return hits[0]

    assert unique(7, "<TEACH-GROUP> mission ordered: BASIC-MISSION") < unique(7, f"{M} mission created:")
    assert unique(7, f"{M} mission created:") < unique(7, f"{M} mission activated, systems requested: 2")
    allocations = [unique(7, f"{M} mission allocates system: {air}") for air in AIR]
    assert allocations[0] < allocations[1]
    for n, (air, unit, base) in enumerate(zip(AIR, UNITS, BASES, strict=True)):
        assert unique(0, f"{air} nbr ready increased at unit: {unit}") < allocations[n]
        assert allocations[n] < unique(7, f"{air} nbr ready decreased at unit: {unit}")
        start = unique(7, f"{air} preparation started, mission: {M}")
        end = unique(7, f"{air} preparation ended, mission: {M}")
        assert allocations[n] < start < end
        turn_start = unique(10, f"{air} turnround started, mission: {M}")
        turn_end = unique(10, f"{air} turnround ended, mission: {M}")
        arrival = unique(10, f"<TEACH-AIR-01,{base},0> System arrives {air}, mission success,")
        ready = unique(10, f"{air} nbr ready increased at unit: {unit}")
        assert turn_start < turn_end < arrival < ready
        assert len([i for i, h, body in timed if h == 10 and body == f"<TEACH-AIR-01,{base},0> System ready {air}"]) == 2
        assert unique(10, f"{unit} systems ready: 1 :{air}") > ready
    launch = unique(8, f"{M} mission starting, duration: 2 : {AIR[0]},{AIR[1]}")
    task_start = unique(8.5, f"{M} task starting: {AIR[0]},{AIR[1]}")
    task_end = unique(9.5, f"{M} task completed: {AIR[0]},{AIR[1]}")
    success = unique(10, f"{M} mission success:")
    completed = unique(10, f"{M} mission completed: {AIR[0]},{AIR[1]}")
    assert allocations[1] < launch < task_start < task_end < success < completed
    assert unique(24, "Start of day no 1") == 59
    return {"physical_lines": 60, "timed_lines": 52, "aircraft_home_units": ["TEACH-UNIT", "TEACH-UNIT-2"],
            "mission_start": 8, "task_start": 8.5, "task_end": 9.5, "success_return": 10}


def verify(raw: bytes) -> dict:
    ledger = semantic(raw)
    expected = (HERE / "prospective-log-oracle.bytes").read_bytes()
    assert len(expected) == 4039 and hashlib.sha256(expected).hexdigest() == LOG_SHA
    assert raw == expected, "XTIME physical log changed from prospective accepted-parent transcript"
    return {"schema": "a17-var06-physical-ledger/v100", "passed": True, **ledger}


def verify_file(path: Path) -> dict:
    return verify(path.read_bytes())


if __name__ == "__main__":
    raise SystemExit("Use verify_file(path) from the source-bound child checker")
