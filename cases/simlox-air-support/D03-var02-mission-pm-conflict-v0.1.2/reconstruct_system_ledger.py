"""Rebuild every half-hour SystemResults field from native lifecycle events.

Four unchanged state templates come from the accepted D03 parent. Event
identities choose the state for each bin; PM start/completion markers are
added from event times. This checker is also run against all parent bins as
a prelaunch positive control.
"""
from __future__ import annotations

import re
from typing import Any

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import table_rows  # noqa: E402

EVENT = {
    "allocation": r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission allocates system: <TEACH-AIR-01,0>$",
    "start": r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission starting, duration: 2 : <TEACH-AIR-01,0>$",
    "success": r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission success: $",
    "completion": r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission completed: <TEACH-AIR-01,0>$",
}
PM_START = r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$"
PM_DONE = r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$"


def mission_events(log: str) -> dict[str, dict[int, float]]:
    result: dict[str, dict[int, float]] = {}
    for name, pattern in EVENT.items():
        pairs = [(int(identity), float(time)) for time, identity in re.findall(pattern, log, re.MULTILINE)]
        if len(pairs) != len(set(identity for identity, _ in pairs)):
            raise ValueError(f"duplicate mission {name} identity")
        result[name] = dict(pairs)
    return result


def pm_events(log: str) -> tuple[list[float], list[float]]:
    starts = [float(x) for x in re.findall(PM_START, log, re.MULTILINE)]
    ends = [float(x) for x in re.findall(PM_DONE, log, re.MULTILINE)]
    if len(starts) != len(ends) or any(end <= start for start, end in zip(starts, ends)):
        raise ValueError("PM event intervals incomplete")
    return starts, ends


def templates(parent_report: dict[str, Any]) -> dict[str, dict]:
    parent_rows = {row["STINT"]: row for row in table_rows(parent_report, "SystemResults")}
    return {name: parent_rows[time] for name, time in
            (("ready", 18.5), ("reserved", 19.5), ("mission", 20.5), ("pm", 24.5))}


def compare(report: dict[str, Any], log: str, parent_report: dict[str, Any]) -> dict[str, Any]:
    rows = table_rows(report, "SystemResults")
    if len(rows) != 120 or [(r["STINT"], r["ETINT"]) for r in rows] != [
        (i / 2, (i + 1) / 2) for i in range(120)
    ]:
        raise ValueError("SystemResults grid differs from 120 half-hour rows")
    mission = mission_events(log)
    pm_start, pm_done = pm_events(log)
    if set(mission["allocation"]) != set(mission["start"]) or set(mission["start"]) != set(mission["completion"]):
        raise ValueError("mission allocation/start/completion identity sets differ")
    forms = templates(parent_report)
    differences = []
    counts = {"ready": 0, "reserved": 0, "mission": 0, "pm": 0}
    compared = 0
    for row in rows:
        t = row["STINT"]
        states = []
        if any(start <= t < end for start, end in zip(pm_start, pm_done)):
            states.append("pm")
        if any(mission["start"][i] <= t < mission["completion"][i] for i in mission["start"]):
            states.append("mission")
        if any(mission["allocation"][i] <= t < mission["start"][i] for i in mission["start"]):
            states.append("reserved")
        if len(states) > 1:
            raise ValueError(f"native lifecycle overlap at hour {t}: {states}")
        state = states[0] if states else "ready"
        counts[state] += 1
        expected = dict(forms[state])
        expected["STINT"] = t
        expected["ETINT"] = row["ETINT"]
        for marker in ("NPMS", "NPMT", "NSYDT"):
            expected[marker] = 0
        expected["SYDT"] = None
        if t in pm_start:
            expected.update({"NPMS": 1, "SYDT": 1, "NSYDT": 1})
        if t in pm_done:
            expected["NPMT"] = 1
        if set(row) != set(expected):
            differences.append({"hour": t, "field": "<schema>", "actual": sorted(row), "expected": sorted(expected)})
            continue
        for field, want in expected.items():
            got = row[field]
            compared += 1
            equal = (abs(got - want) <= 5e-5 if isinstance(got, (int, float)) and
                     isinstance(want, (int, float)) else got == want)
            if not equal:
                differences.append({"hour": t, "state": state, "field": field,
                                    "actual": got, "expected": want})
    return {"passed": not differences, "field_comparisons": compared,
            "expected_comparisons": 120 * len(forms["ready"]),
            "state_bins": counts, "mission_events": mission,
            "pm_starts": pm_start, "pm_completions": pm_done,
            "differences": differences}
