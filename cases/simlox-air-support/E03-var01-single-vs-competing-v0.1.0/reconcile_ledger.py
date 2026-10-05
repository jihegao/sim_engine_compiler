"""Reconcile every E03.var01 half-hour report row against its native events."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "e03-var01-single-v010-ssh-20261006-01"
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402

LOG_SHA = "91003601616f8e0fb7b969859a3cec99b0f2a2383fa92e698742a5de145189e7"
REPORT_SHA = "81c93097accf7eb82be031939dcb162bf6356e2bbe58dd4cf65978a58d6d6102"
CLOSURE_SHA = "0c12233574445246d8732f3f1d4202fce3e091a39cef5118a6a5a9ca6ac08690"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sole_time(log: str, fragment: str, *, exact_body: bool = False) -> float:
    pattern = (r"^Time: ([\d.]+)  " + re.escape(fragment) + r"$") if exact_body else (r"^Time: ([\d.]+) .*" + re.escape(fragment))
    times = [float(match[1]) for match in re.finditer(pattern, log, re.M)]
    if len(times) != 1:
        raise ValueError(f"expected one event {fragment}: {times}")
    return times[0]


def occupancy(start: float, end: float, left: float, right: float) -> float:
    return max(0.0, min(end, right) - max(start, left)) / (right - left)


def main() -> int:
    if sha(RUN / "model.log") != LOG_SHA or sha(RUN / "report-raw.json") != REPORT_SHA or sha(RUN / "closure.json") != CLOSURE_SHA:
        raise ValueError("sealed native evidence differs")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    report = json.loads(native.remove_trailing_commas((RUN / "report-raw.json").read_bytes()))
    system = native.table_rows(report, "SystemResults")
    stock = native.table_rows(report, "StockTotalResults")
    mission_alloc = sole_time(log, "mission allocates system: <TEACH-AIR-01,0>")
    failure = sole_time(log, "critical random failure added")
    repair_start = sole_time(log, "system SURP task 0 on <TEACH-AIR-01,0> started", exact_body=True)
    demand = sole_time(log, "Item demand arrives")
    issue = sole_time(log, "Take replacement item <TEACH-LRU-01,0,0> from stock")
    ready = sole_time(log, "System ready <TEACH-AIR-01,0>")
    returned = sole_time(log, "Put back replacement item <TEACH-LRU-01,0,1> to stock")
    errors: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            errors.append(label)

    ck("event order", 0 <= mission_alloc < failure < repair_start == demand == issue < ready < returned < 36)
    ck("72 system and stock rows", len(system) == len(stock) == 72)
    for i, (sy, st) in enumerate(zip(system, stock)):
        left, right = i * .5, (i + 1) * .5
        ck(f"interval {i}", sy["STINT"] == st["STINT"] == left and sy["ETINT"] == st["ETINT"] == right)
        rep = occupancy(repair_start, ready, left, right)
        busy = occupancy(mission_alloc, ready, left, right)
        ck(f"system availability {i}", abs(sy["NSYA"] - (2 - rep)) < 1e-4)
        ck(f"system repair occupancy {i}", abs(sy["NSYRP"] - rep) < 1e-4)
        ck(f"system ready occupancy {i}", abs(sy["NSYRY"] - (2 - busy)) < 1e-4)
        ck(f"system waiting {i}", sy["NSYWI"] == 0)
        ck(f"failure and repair event bins {i}", sy["NFAIL"] == int(left <= failure < right) and sy["NREPT"] == int(left <= ready < right))
        ck(f"demand and backorder bins {i}", st["NDF"] == int(left <= demand < right) and st["NBO"] == 0)
        ck(f"other stock demand channels {i}", all(st[k] == 0 for k in ("NDD", "NDR", "NDP", "NLD")))
    ck("summary failed single mission", len(native.table_rows(report, "ResultSummary")) == 1 and native.table_rows(report, "ResultSummary")[0]["MSUF"] == 0)
    result = {"schema": "simlox-e03-var01-ledger-reconciliation/v1", "run_id": RUN.name, "passed": not errors, "checks": checks, "differences": errors, "events_hours": {"mission_allocation": mission_alloc, "failure": failure, "demand_and_spare_issue": demand, "system_ready": ready, "removed_item_return": returned}, "system_rows": len(system), "stock_rows": len(stock), "system_available_aircraft_hours": sum(row["NSYA"] for row in system) * .5, "system_repair_aircraft_hours": sum(row["NSYRP"] for row in system) * .5, "stock_backorder_hours": sum(row["NBO"] for row in stock) * .5, "stock_pnb_note": "PNB is retained as a raw report field; physical on-hand IDs come from model.log, not PNB", "model_log_sha256": LOG_SHA, "report_sha256": REPORT_SHA, "closure_sha256": CLOSURE_SHA}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
