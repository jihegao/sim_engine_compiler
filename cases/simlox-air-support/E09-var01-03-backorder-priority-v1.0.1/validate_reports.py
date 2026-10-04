"""Author check of E09 station-selected native ITEM report time integrals."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "e09-backorder-priority-v101-item-report-ssh-20261004-01"
NATIVE = HERE / "runs" / "e09-backorder-priority-v101-ssh-20261004-01"
ARMS = ("fifo", "priority", "disabled")
STATIONS = ("base-01", "base-02", "depot-01")
CHECKS: list[tuple[str, bool]] = []


def check(name: str, value: bool) -> None:
    CHECKS.append((name, bool(value)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def mapped(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, values, strict=True)) for instance in table["instances"] for values in instance["rows"]]


def average(a: float, b: float, intervals: list[tuple[float, float, float]]) -> float:
    return sum(max(0.0, min(b, end) - max(a, start)) * level for start, end, level in intervals) / (b - a)


contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
native_closure = json.loads((NATIVE / "closure.json").read_text(encoding="utf-8-sig"))
check("run pin", RUN.name == contract["selected_report_run_id"] == closure["run_id"])
check("native closure pin", closure["source_closure_sha256"] == sha(NATIVE / "closure.json"))
check("native closure clean", native_closure["error"] is None)
check("report closure clean", closure["error"] is None)
check("nine exports", len(closure["raw"]) == 20 and len(json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))) == 9)
for name, seal in closure["raw"].items():
    file = RUN / name
    check(f"sealed {name}", file.is_file() and file.stat().st_size == seal["bytes"] and sha(file) == seal["sha256"])

all_rows: dict[tuple[str, str], list[dict]] = {}
for arm in ARMS:
    for station in STATIONS:
        file = RUN / f"{arm}-{station}-item-report-raw.json"
        tables = {table["name"]: table for table in parse_native(file)["report"]["tables"]}
        check(f"ItemResults exists {arm}/{station}", "ItemResults" in tables)
        if "ItemResults" not in tables:
            continue
        rows = mapped(tables["ItemResults"])
        all_rows[arm, station] = rows
        check(f"72 rows {arm}/{station}", len(rows) == 72)
        check(f"station and item identity {arm}/{station}", all(row["STID"] == station.upper() and row["IID"] == "TEACH-LRU-01" for row in rows))
        check(f"half-hour bins {arm}/{station}", all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(rows)))
        check(f"nonnegative stock/backorders {arm}/{station}", all(row["STOHA"] >= 0 and row["NBO"] >= 0 for row in rows))

        first_arrival = 16.6667 if arm == "priority" else 15.9246
        second_arrival = 15.9246 if arm == "priority" else 16.6667
        if station == "base-01":
            stock = [(0, 10.7579, 1), (first_arrival, 23.4473, 1), (28.614, 35.5, 1)]
            bo: list[tuple[float, float, float]] = []
            check(f"opening stock target {arm}/{station}", all(row["STSZ"] == 1 for row in rows))
        elif station == "base-02":
            stock = []
            bo = [(11.5, second_arrival, 1)]
            check(f"opening stock target {arm}/{station}", all(row["STSZ"] == 0 for row in rows))
        else:
            stock = []
            bo = [(10.7579, 11.5, 1), (11.5, 14.9246, 2), (14.9246, 15.6667, 1), (23.4473, 27.614, 1), (35.5, 36, 1)]
            check(f"opening stock target {arm}/{station}", all(row["STSZ"] == 0 for row in rows))
        for i, row in enumerate(rows):
            a, b = i / 2, (i + 1) / 2
            check(f"stock integral {arm}/{station}/{i}", abs(row["STOHA"] - average(a, b, stock)) < 0.0003)
            check(f"backorder integral {arm}/{station}/{i}", abs(row["NBO"] - average(a, b, bo)) < 0.0003)

for station in STATIONS:
    check(f"FIFO/disabled report parity {station}", all_rows.get(("fifo", station)) == all_rows.get(("disabled", station)))
check("priority earlier BASE-02 backorder clearance", all_rows["priority", "base-02"][31]["NBO"] < all_rows["fifo", "base-02"][31]["NBO"])
check("priority later BASE-01 restock", all_rows["priority", "base-01"][31]["STOHA"] < all_rows["fifo", "base-01"][31]["STOHA"])

failed = [name for name, passed in CHECKS if not passed]
result = {
    "schema": "simlox-e09-v101-author-item-report-validation/v1",
    "run_id": RUN.name,
    "native_closure_sha256": sha(NATIVE / "closure.json"),
    "selected_report_closure_sha256": sha(RUN / "closure.json"),
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failed),
    "failed": failed,
    "verdict": "GO_BOUNDED" if not failed else "NO_GO",
    "method": "All 72 half-hour STOHA/NBO rows for each of nine native station-selected reports are compared with piecewise event intervals; tolerance 0.0003 covers four-decimal event-log timing.",
}
(HERE / "author-report-validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
if failed:
    raise SystemExit(1)
