"""Check source isolation, native round trip, and result limits of depot-stock probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from build_f35_depot_stock_probe import build_canonical, load, rows, table


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_rows(path: Path, name: str) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(re.sub(r",(?=\s*[}\]])", "", text))
    tables = [entry for entry in data["report"]["tables"] if entry["name"] == name]
    if len(tables) != 1:
        raise ValueError(f"expected one report table {name}")
    return rows(tables[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "canonical_source", "canonical_variant", "canonical_summary", "simlox_variant",
        "native_export", "native_model", "result", "raw_report", "run_log",
        "original_report", "batch_baseline_report", "batch_depot_report", "output",
    ):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    expected_canonical = build_canonical(load(args.canonical_source))
    if load(args.canonical_variant) != expected_canonical:
        raise ValueError("canonical variant is not the one-field stock change")
    summary = load(args.canonical_summary)
    if summary["variant_sha256"] != digest(args.canonical_variant):
        raise ValueError("canonical run summary is not for this variant")
    if summary["seed"] != 1 or summary["plan_fingerprint"] != "553fb1736716912a7e253e7d44fdd92421e562c1c0494331ffcda6f181c05a57":
        raise ValueError("canonical run identity differs")
    if summary["metrics"]["transport_replenishment_events"] != 2 or summary["metrics"]["total_transport_delay_minutes"] != 240:
        raise ValueError("canonical shipment diagnostics differ")
    arrivals = [
        (event["details"]["requested_minute"], event["time"])
        for event in summary["transport_events"]
        if event["kind"] == "transport_arrived"
    ]
    if arrivals != [(866, 986), (927, 1047)]:
        raise ValueError(f"unexpected canonical shipment arrivals: {arrivals}")

    source = load(args.simlox_variant)
    native = load(args.native_export)
    expected_station = rows(table(source, "StationStructure"))
    actual_station = rows(table(native, "StationStructure"))
    if len(expected_station) != 1:
        raise ValueError("expected one station link")
    for field in ("STID", "MSTID", "TFRMS", "TTOMS", "DFRAC", "OPOL", "NOTE"):
        before, after = expected_station[0].get(field), actual_station[0].get(field)
        if isinstance(before, str) and field != "NOTE":
            before, after = before.upper(), str(after).upper()
        if before != after:
            raise ValueError(f"StationStructure.{field}: {after!r} != {before!r}")
    expected_stock = [
        item for item in rows(table(source, "StockAllocation"))
        if item["IID"].upper() == "F35-PART-2602030200000801"
    ]
    actual_stock = [
        item for item in rows(table(native, "StockAllocation"))
        if item["IID"].upper() == "F35-PART-2602030200000801"
    ]
    if len(expected_stock) != 2 or len(actual_stock) != 2:
        raise ValueError("target item must have two stock rows")
    for before, after in zip(expected_stock, actual_stock, strict=True):
        for field in ("POINT", "IID", "STID", "STSIZ", "ROSIZ", "NOTE"):
            x, y = before.get(field), after.get(field)
            if field in ("POINT", "IID", "STID"):
                x, y = str(x).upper(), str(y).upper()
            if x != y:
                raise ValueError(f"StockAllocation.{field}: {y!r} != {x!r}")
    if {row["STID"]: row["STSIZ"] for row in actual_stock} != {"BASE": 0, "DEPOT": 2}:
        raise ValueError("target stock counts differ")
    log = args.run_log.read_text(encoding="utf-8-sig")
    if "Input conversion completed. Errors: 0, Warnings: 0, Notes: 0" not in log:
        raise ValueError("native run has conversion diagnostics")
    if args.native_model.name not in log or args.result.name not in log:
        raise ValueError("run log does not bind model to result")
    report = report_rows(args.raw_report, "ResultSummary")
    if len(report) != 1 or report[0]["NREP"] != 1 or report[0]["RTILW"] != 0 or report[0]["RTIUP"] != 1032:
        raise ValueError("native report identity differs")
    if args.raw_report.read_bytes() != args.original_report.read_bytes():
        raise ValueError("single-run report unexpectedly differs from original v4")
    if args.batch_baseline_report.read_bytes() != args.batch_depot_report.read_bytes():
        raise ValueError("batch reports differ; update the evidence interpretation")
    outcome = {
        "status": "upper-stock-native-roundtrip-verified; SIMLOX transport-not-observed",
        "canonical_shipments": arrivals,
        "simlox_station_link": actual_station[0],
        "simlox_stock": {row["STID"]: row["STSIZ"] for row in actual_stock},
        "single_report_unchanged": True,
        "batch100_report_unchanged": True,
        "sha256": {
            "canonical_variant": digest(args.canonical_variant),
            "simlox_variant": digest(args.simlox_variant),
            "native_model": digest(args.native_model),
            "native_export": digest(args.native_export),
            "result": digest(args.result),
            "raw_report": digest(args.raw_report),
            "batch100_report": digest(args.batch_depot_report),
            "run_log": digest(args.run_log),
        },
    }
    args.output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": outcome["status"], "sha256": outcome["sha256"]}))


if __name__ == "__main__":
    main()
