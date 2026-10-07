"""Event/source-derived expectations for all six C09 native report tables.

No expected cell is read from the report under test. Printed event times have
finite precision; only fields integrating those times receive a tolerance.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from native_json import read

FIELDS = {
    "ProblemDescription": "PDESC",
    "ResultSummary": "NREP RTILW RTIUP MTMF RSMTMF MSTF RSMSTF MSUF RSMSUF STMF RSSTMF",
    "SystemResults": "UNID SID STINT ETINT NSYRY NSYMA NSYMO NSYMC NSYMP NSYMT NSYMS NSYMR NSYUA NSYA NSYAL FTMO NSYRP NSYPM NSYTP NSYWR NSYWI NSYLA NSYUH NREPT NPMT NFAIL NDAM NPMS NROBT NRCFG STREQ STACC STF STLOW SYDT SYDTU NSYDT NSYSW NPSTA NPSUC",
    "StockTotalResults": "STINT ETINT NBO NBOU ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NWT",
    "ResourceResults": "RID STID STINT ETINT NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO",
    "ResourceResultsTotal": "RID STID NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO",
}
FIELDS = {name: value.split() for name, value in FIELDS.items()}
ROWS = {"ProblemDescription": 1, "ResultSummary": 1, "SystemResults": 72,
        "StockTotalResults": 72, "ResourceResults": 72, "ResourceResultsTotal": 1}
INSTANCES = {"ProblemDescription": "", "ResultSummary": "",
             "SystemResults": "Total over all Units;Total over all Systems;0.00;36.00",
             "StockTotalResults": "0.00;36.00;",
             "ResourceResults": "Total over all Resources;Total over all Stations;0.00;36.00",
             "ResourceResultsTotal": "Total over all Resources;Total over all Stations;0.00;36.00"}
FRACTIONAL_BINS = {"NSYRY", "NSYMA", "NSYMO", "NSYMP", "NSYUA", "NSYA",
                   "FTMO", "NSYRP", "NSYWR", "STACC", "NR", "NRUM", "NRW",
                   "NRA", "NRRI", "NRRT", "NRRO"}
TIME_WEIGHTED_TOTALS = {"NR", "NRUM", "NRW", "NRA", "NRRI", "NRRT", "NRRO"}


@dataclass(frozen=True)
class Event:
    time: float
    text: str
    line: int


def events(path: Path) -> list[Event]:
    output: list[Event] = []
    for line, text in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        found = re.match(r"Time:\s*([0-9.eE+-]+)\s+(.*)", text)
        if found:
            output.append(Event(float(found.group(1)), found.group(2), line))
        elif output:
            old = output[-1]
            output[-1] = Event(old.time, old.text + "\n" + text, old.line)
    return output


def match(evs: list[Event], pattern: str) -> list[Event]:
    regex = re.compile(pattern)
    return [event for event in evs if regex.search(event.text)]


def one(evs: list[Event], pattern: str) -> Event:
    found = match(evs, pattern)
    assert len(found) == 1, (pattern, [(e.time, e.line) for e in found])
    return found[0]


def overlap(a: float, b: float, start: float, end: float) -> float:
    return max(0.0, min(b, end) - max(a, start))


def at_bin(t: float, start: float, end: float) -> bool:
    return start <= t < end


def spans(evs: list[Event], started: str, ended: str) -> list[tuple[float, float]]:
    a, b = match(evs, started), match(evs, ended)
    assert len(a) == len(b)
    result = [(left.time, right.time) for left, right in zip(a, b)]
    assert all(left <= right for left, right in result)
    return result


def evidence(arm: str, log: Path) -> dict:
    evs = events(log)
    assert arm in ("local", "remote", "remote-disabled")
    prep = {}
    flight = {}
    repair = {}
    waiting = {}
    for ident in (0, 1):
        sid = rf"<TEACH-AIR-01,{ident}>"
        prep[ident] = (one(evs, sid + r" preparation started, mission:").time,
                       one(evs, sid + r" preparation ended, mission:").time)
        starts = match(evs, rf"^\s*direct repair subtask \d+ seqno 1 within system DIRP task \d+ on {sid} starts performing")
        ends = match(evs, rf"^\s*direct repair subtask \d+ seqno 1 within system DIRP task \d+ on {sid} completed")
        assert len(starts) == len(ends) and len(starts) <= 1
        if starts:
            repair[ident] = (starts[0].time, ends[0].time)
        increase = match(evs, sid + r" nbr resourcewait increased:")
        decrease = match(evs, sid + r" nbr resourcewait decreased:")
        assert len(increase) <= 1 and len(decrease) <= 1
        if increase:
            waiting[ident] = (increase[0].time, decrease[0].time if decrease else 36.0)
    mission_start = one(evs, r"mission starting, duration:").time
    mission_end = one(evs, r"aborted mission completed:").time
    assert len(match(evs, r"critical random failure added")) == 2
    failures = [e.time for e in match(evs, r"critical random failure added")]
    assert [round(t, 5) for t in failures] == [8.28243, 8.46988]
    assert all(pair == (7.5, 8.0) for pair in prep.values())
    assert mission_start == 8 and abs(mission_end - 8.53243) < 1e-5
    assert len(repair) == (0 if arm == "remote-disabled" else 2)
    flight = {ident: (mission_start, mission_end) for ident in (0, 1)}
    out_start = match(evs, r"remote resource transport task \d+ starts with 1 resources")
    out_end = match(evs, r"remote resource transport task \d+ arrives with 1 resources")
    back_start = match(evs, r"return resource transport task \d+ starts with 1 resources")
    back_end = match(evs, r"return resource transport task \d+ arrives with 1 resources")
    travel: list[tuple[float, float]] = []
    borrowed: list[tuple[float, float]] = []
    if arm == "remote":
        assert all(len(group) == 1 for group in (out_start, out_end, back_start, back_end))
        travel = [(out_start[0].time, out_end[0].time),
                  (back_start[0].time, back_end[0].time)]
        borrowed = [(out_end[0].time, back_start[0].time)]
    else:
        assert not (out_start or out_end or back_start or back_end)
    assert abs(sum(b-a for a,b in travel) - (0.75 if arm == "remote" else 0)) < 0.0001
    assert sum(b-a for a,b in repair.values()) == (0 if arm == "remote-disabled" else 1)
    return {"events": evs, "prep": prep, "flight": flight, "repair": repair,
            "wait": waiting, "mission": (mission_start, mission_end),
            "failures": failures, "travel": travel, "borrowed": borrowed}


def expected(arm: str, source_input: Path, log: Path) -> dict[str, list[list]]:
    event = evidence(arm, log)
    source = read(source_input)
    problem = next(t for t in source["model"]["tables"] if t["name"] == "ProblemDescription")
    description = problem["instances"][0]["rows"][0][0]
    mission_start, mission_end = event["mission"]
    result = {"ProblemDescription": [[description]],
              "ResultSummary": [[1, 0, 36, mission_end-mission_start, 0, 1, 0,
                                 0, 0, mission_end-mission_start, 0]],
              "SystemResults": [], "StockTotalResults": [],
              "ResourceResults": [], "ResourceResultsTotal": []}
    values = {"ResourceResults": {name: 0.0 for name in FIELDS["ResourceResultsTotal"][2:]}}
    for index in range(72):
        start, end = index / 2, (index + 1) / 2
        def weighted(pairs):
            return sum(overlap(a, b, start, end) for a, b in pairs) / .5
        ready = [(0, event["prep"][id][0]) for id in (0, 1)]
        ready += [(pair[1], 36) for pair in event["repair"].values()]
        preparation = weighted(event["prep"].values())
        mission = weighted(event["flight"].values())
        repairing = weighted(event["repair"].values())
        waiting = weighted(event["wait"].values())
        system = {name: 0 for name in FIELDS["SystemResults"]}
        system.update({"UNID": "Total over all Units", "SID": "Total over all Systems",
                       "STINT": start, "ETINT": end,
                       "NSYRY": weighted(ready), "NSYMA": preparation + mission,
                       "NSYMO": mission, "NSYMP": preparation,
                       "NSYUA": repairing + waiting,
                       "NSYA": weighted(ready) + preparation + mission,
                       "FTMO": weighted([event["mission"]]),
                       "NSYRP": repairing, "NSYWR": waiting,
                       "NREPT": sum(at_bin(pair[1], start, end) for pair in event["repair"].values()),
                       "NFAIL": sum(at_bin(t, start, end) for t in event["failures"]),
                       "STACC": mission,
                       "NPSTA": sum(at_bin(pair[0], start, end) for pair in event["prep"].values()),
                       "NPSUC": sum(at_bin(pair[1], start, end) for pair in event["prep"].values()),
                       "SYDT": None})
        if event["repair"] and at_bin(mission_end, start, end):
            system["NSYDT"] = len(event["repair"])
            system["SYDT"] = sum(pair[1]-mission_end for pair in event["repair"].values()) / len(event["repair"])
        result["SystemResults"].append([system[name] for name in FIELDS["SystemResults"]])
        stock = {name: 0 for name in FIELDS["StockTotalResults"]}
        stock.update({"STINT": start, "ETINT": end, "NBOU": None,
                      "ROS": None, "ROST": None, "WT": None, "WTT": None,
                      "WTS": None, "PNB": 1})
        result["StockTotalResults"].append([stock[name] for name in FIELDS["StockTotalResults"]])
        travel = weighted(event["travel"])
        borrowed = weighted(event["borrowed"])
        resource = {name: 0 for name in FIELDS["ResourceResults"]}
        resource.update({"RID": "Total over all Resources", "STID": "Total over all Stations",
                         "STINT": start, "ETINT": end,
                         "NR": 3-travel, "NRUM": preparation + repairing,
                         "NRW": waiting, "NRA": 3-travel, "NRN": 3,
                         "NRRI": borrowed, "NRRT": travel, "NRRO": borrowed})
        result["ResourceResults"].append([resource[name] for name in FIELDS["ResourceResults"]])
        for name in values["ResourceResults"]:
            values["ResourceResults"][name] += resource[name] / 72
    total = {"RID": "Total over all Resources", "STID": "Total over all Stations",
             **values["ResourceResults"]}
    total["NRN"] = 3
    result["ResourceResultsTotal"] = [[total[name] for name in FIELDS["ResourceResultsTotal"]]]
    return result


def cell_equal(got, want, table: str, field: str) -> bool:
    if want is None or isinstance(want, str) or field in {"NFAIL", "NREPT",
                                                         "NSYDT", "NPSTA", "NPSUC", "NRN", "PNB"}:
        return type(got) is type(want) and got == want
    if isinstance(got, bool) or not isinstance(got, (int, float)) or not math.isfinite(got):
        return False
    if isinstance(want, (int, float)) and float(want).is_integer():
        return got == want  # full-bin/zero invariant; timestamp tolerance is irrelevant
    if field in {"STINT", "ETINT"}:
        bound = 0
    elif table == "ResourceResults" and field in {"NR", "NRA", "NRRT"}:
        bound = 0.0001  # printed return h10.2824 loses a decimal place
    elif field in FRACTIONAL_BINS and table in ("SystemResults", "ResourceResults"):
        bound = 5e-5  # printed h8.53243 etc., divided by a half-hour bin
    elif table == "ResultSummary" and field in {"MTMF", "STMF"}:
        bound = 2e-5
    elif table == "ResourceResultsTotal" and field in TIME_WEIGHTED_TOTALS:
        bound = 2e-6
    elif field == "SYDT":
        bound = 2e-5
    else:
        bound = 0  # discrete counts, stable zeros and source constants are exact
    return abs(got - want) <= bound


def check_report(arm: str, source_input: Path, log: Path, report: Path) -> tuple[int, list[str]]:
    want = expected(arm, source_input, log)
    observed = read(report)["report"]["tables"]
    issues: list[str] = []
    if len(observed) != 6 or {t["name"] for t in observed} != set(FIELDS):
        return 0, ["six-table name/topology mismatch"]
    by_name = {t["name"]: t for t in observed}
    cells = 0
    for table_name, names in FIELDS.items():
        table = by_name[table_name]
        actual_names = [c["name"] for c in table["columns"]]
        if actual_names != names:
            issues.append(f"{arm}/{table_name} column topology")
            continue
        instances = table["instances"]
        if len(instances) != 1 or instances[0].get("instance_name") != INSTANCES[table_name]:
            issues.append(f"{arm}/{table_name} instance topology")
            continue
        rows = instances[0]["rows"]
        if len(rows) != ROWS[table_name]:
            issues.append(f"{arm}/{table_name} row count")
            continue
        for index, target in enumerate(want[table_name]):
            actual = rows[index]
            if len(actual) != len(names):
                issues.append(f"{arm}/{table_name}[{index}] width")
                continue
            for field, got, expected_value in zip(names, actual, target):
                cells += 1
                if not cell_equal(got, expected_value, table_name, field):
                    issues.append(f"{arm}/{table_name}[{index},{field}]: {got!r} != {expected_value!r}")
    if cells != 5210:
        issues.append(f"{arm} compared {cells}/5210 cells")
    return cells, issues
