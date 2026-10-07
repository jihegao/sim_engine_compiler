"""Frozen v1.0.7 source/event-derived cell bounds, without report fitting."""
from __future__ import annotations

from collections import defaultdict
import math
import re

SERIAL = 0.0000005
SYSTEM_TIME = {"NSYRY", "NSYMA", "NSYMO", "NSYMP", "NSYRP", "NSYPM",
               "NSYWR", "NSYUA", "NSYA", "STACC", "FTMO"}
RESOURCE_TIME = {"NR", "NRUM", "NRW", "NRA", "NRRI", "NRRT", "NRRO"}
CEILING = {"system": 0.00035, "ftmo": 0.00012,
           "resource": 0.00035, "resource_total": 0.00005,
           "mission": 0.00005, "sydt": 0.00010}


def printed_time_uncertainty(log: str) -> dict[float, float]:
    """Half a unit in each literal log timestamp's last decimal place.

    These exact scheduled edges are certified by the frozen source and typed
    event ledger: initiation h0, preparation h7.5, launch h8, HOME PM due h9,
    and the h12 report horizon. A new unsourced edge at one of these printed
    times is rejected by the physical event ledger before cell comparison.
    """
    source_exact = {0.0, 7.5, 8.0, 9.0, 12.0}
    out: dict[float, float] = {}
    for line in log.splitlines():
        match = re.match(r"^Time:\s*(\d+(?:\.(\d+))?)\s", line)
        if not match:
            continue
        t = float(match.group(1))
        digits = len(match.group(2) or "")
        uncertainty = 0.0 if t in source_exact else 0.5 * 10 ** (-digits)
        if t in out:
            assert out[t] == uncertainty, ("inconsistent timestamp precision", t)
        out[t] = uncertainty
    assert out and all(t >= 0 for t in out)
    return out


def contributing_edges(changes: dict, field: str) -> list[tuple[float, float]]:
    if field in {"NR", "NRA"}:
        return [(t, -delta) for t, delta in changes.get("NRRT", [])]
    if field == "NSYUA":
        return sum((changes.get(k, []) for k in ("NSYRP", "NSYPM", "NSYWR")), [])
    if field == "NSYA":
        return [(t, -delta) for t, delta in contributing_edges(changes, "NSYUA")]
    if field == "FTMO" or field == "STACC":
        return changes.get("NSYMO", [])
    return changes.get(field, [])


def exposure_bound(field: str, *, table: str, row: int, expected: float, edges: dict,
                   uncertainty: dict[float, float], fleet: int, horizon: float) -> float:
    if table == "ResourceResultsTotal":
        begin, end, denom, ceiling = 0.0, horizon, horizon, CEILING["resource_total"]
    else:
        begin, end, denom = row / 2, (row + 1) / 2, 0.5
        ceiling = CEILING["ftmo" if field == "FTMO" else
                          "system" if table == "SystemResults" else "resource"]
    # Combine simultaneous signed jumps before assigning uncertainty. This
    # makes a same-time wait-to-work transition an invariant total unavailable.
    by_time: dict[float, float] = defaultdict(float)
    for t, jump in contributing_edges(edges["changes"], field):
        if begin <= t <= end:
            by_time[t] += jump
    magnitude = 0.0
    for t, jump in by_time.items():
        assert t in uncertainty, ("unprinted transition", field, t)
        magnitude += abs(jump) * uncertainty[t]
    if field == "FTMO":
        assert fleet == 3
        denom *= fleet
    time_bound = magnitude / denom
    # No uncertain contributing edge means an exact source-fixed whole bin.
    if time_bound == 0:
        # Only a noninteger count/fleet ratio needs decimal serialization.
        # An exact whole-bin FTMO zero (or one) is a source invariant.
        return SERIAL if field == "FTMO" and not float(expected).is_integer() else 0.0
    bound = time_bound + SERIAL
    assert bound <= ceiling, ("precision evidence insufficient", table, row, field, bound, ceiling)
    return bound


def cell_bound(table: str, row: int, field: str, expected: object,
               edges: dict, uncertainty: dict[float, float]) -> float:
    if (table, row, field) in {("SystemResults", 18, "NSYWR"),
                               ("ResourceResults", 18, "NRW")}:
        assert edges.get("special_home_boundary_valid") is True, "HOME h9 exception physical predicate absent"
        assert expected == 1
        return 0.000003
    if table == "SystemResults" and field in SYSTEM_TIME:
        return exposure_bound(field, table=table, row=row, expected=expected, edges=edges,
                              uncertainty=uncertainty, fleet=edges["fleet"], horizon=edges["horizon"])
    if table == "ResourceResults" and field in RESOURCE_TIME:
        return exposure_bound(field, table=table, row=row, expected=expected, edges=edges,
                              uncertainty=uncertainty, fleet=edges["fleet"], horizon=edges["horizon"])
    if table == "ResourceResultsTotal" and field in RESOURCE_TIME:
        return exposure_bound(field, table=table, row=row, expected=expected, edges=edges,
                              uncertainty=uncertainty, fleet=edges["fleet"], horizon=edges["horizon"])
    if table == "ResultSummary" and field in {"MTMF", "STMF"}:
        start, end = edges["mission_edges"]
        assert start in uncertainty and end in uncertainty
        # Frozen MissionType.DURN is one hour.
        bound = uncertainty[start] + uncertainty[end] + SERIAL
        assert bound <= CEILING["mission"]
        return bound
    if table == "SystemResults" and field == "SYDT" and expected is not None:
        periods = edges["down_edges"].get(row, [])
        assert periods, ("SYDT without completed downtime", row)
        bound = sum(uncertainty[a] + uncertainty[b] for a, b in periods) / len(periods) + SERIAL
        assert bound <= CEILING["sydt"]
        return bound
    # Every other field is a frozen source constant, discrete counter, null,
    # exact ID, or exact report interval. Unknown fractional dependencies fail.
    return 0.0


def compare(expected: dict, actual: dict, *, edges: dict, log: str) -> tuple[list[str], int]:
    assert set(expected) == set(actual)
    uncertainty = printed_time_uncertainty(log)
    errors: list[str] = []
    checked = 0
    for table, rows in expected.items():
        observed = actual[table]
        if len(rows) != len(observed):
            errors.append(f"{table}: row count")
            continue
        for i, (want, got) in enumerate(zip(rows, observed)):
            if list(want) != list(got):
                errors.append(f"{table}[{i}]: columns")
                continue
            for field, value in want.items():
                checked += 1
                found = got[field]
                label = f"{table}[{i}].{field}"
                if isinstance(value, bool) or isinstance(found, bool):
                    errors.append(label + ": boolean")
                elif value is None or isinstance(value, str):
                    if value != found:
                        errors.append(label + ": null/identity")
                elif not isinstance(found, (int, float)) or not math.isfinite(found):
                    errors.append(label + ": nonnumeric")
                else:
                    bound = cell_bound(table, i, field, value, edges, uncertainty)
                    if abs(found - value) > bound:
                        errors.append(f"{label}: expected={value} observed={found} bound={bound}")
    return errors, checked
