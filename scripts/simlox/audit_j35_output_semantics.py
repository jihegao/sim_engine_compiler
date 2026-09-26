"""Audit output arithmetic for the pinned J35 SIMLOX and reference runs.

This verifies each runtime's report against its own model/result. It does not
assert cross-runtime event or random-stream equivalence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path


EXPECTED_SHA256 = {
    "canonical": "30c20086cbf400dd35e132f71498c1d05c256d74a1384355b703ccc713601559",
    "model": "88033e3c83ed039c4ffff32da1f5c3b2ef91cd3a25318adac3020f30caece5c5",
    "plan": "44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb",
    "simlox": "2f066cecd9f56036638469e680078dab095161d10504abc7cbbda28f99fbf5ab",
    "reference_seed0": "804ddceff79884f6b8c56b89870691c7c1a7ab22f9317593a691b36fb7825bf1",
    "reference_seed1": "686edd86b7cba086c1f11be42ddc10d31202a0a1272a5974da45ac93d9b3fc87",
}


def rows(payload: dict, container: str, name: str) -> list[dict]:
    table, = [entry for entry in payload[container]["tables"] if entry["name"] == name]
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in table["instances"][0]["rows"]]


def intervals(records: list[dict], horizon_hours: int) -> None:
    assert len(records) == horizon_hours * 2
    for index, row in enumerate(records):
        assert math.isclose(row["STINT"], index / 2, abs_tol=1e-9)
        assert math.isclose(row["ETINT"], (index + 1) / 2, abs_tol=1e-9)


def count_from_fraction(fraction: float, denominator: int) -> int:
    count = round(fraction * denominator)
    if not 0 <= count <= denominator or abs(fraction - count / denominator) > 1e-6:
        raise ValueError(f"fraction {fraction} cannot represent integer count/{denominator}")
    return count


def reference_counts(result: dict, plan: dict) -> dict:
    missions = result["terminal_state"]["missions"]
    planned = sum(mission["planned_start"] <= result["time"] for mission in plan["missions"])
    started = sum(mission["actual_start"] is not None for mission in missions)
    successful = sum(bool(mission["succeeded"]) for mission in missions)
    metrics = result["metrics"]
    assert len(missions) == len(plan["missions"]) == 104
    assert (planned, successful) == (metrics["planned_mission_waves"], metrics["successful_mission_waves"])
    assert math.isclose(metrics["mission_success_rate"], successful / planned, abs_tol=1e-12)
    assert metrics["launched_sorties"] == started * 2
    return {
        "seed": result["seed"],
        "end_minute": result["time"],
        "stop_reason": result["stop_reason"],
        "planned_waves": planned,
        "started_waves": started,
        "successful_waves": successful,
        "mission_success_rate": metrics["mission_success_rate"],
        "shortage_events": metrics["shortage_events"],
        "spare_demand_total": metrics["spare_demand_total"],
        "resource_delay_trace_rows": sum(event["kind"] in {"personnel_delay", "equipment_shortage"}
                                         for event in result["trace"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in EXPECTED_SHA256:
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payloads = {}
    evidence = {}
    for name, expected in EXPECTED_SHA256.items():
        path = getattr(args, name)
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise ValueError(f"{name} SHA-256 changed: {actual}")
        evidence[f"{name}_sha256"] = actual
        decoded = raw.decode("utf-8-sig")
        if name == "simlox":
            # SIMLOX 2017 writes trailing commas; preserve raw bytes on disk.
            decoded = re.sub(r",\s*([}\]])", r"\1", decoded)
        payloads[name] = json.loads(decoded)
    model = payloads["model"]
    plan = payloads["plan"]
    canonical = payloads["canonical"]
    simlox = payloads["simlox"]
    summary, = rows(simlox, "report", "ResultSummary")
    control, = rows(model, "model", "Control")
    mission_type, = rows(model, "model", "MissionType")
    profile = rows(model, "model", "OperationProfile")
    system = rows(simlox, "report", "SystemResults")
    stock = rows(simlox, "report", "StockTotalResults")
    resources = rows(simlox, "report", "ResourceResults")
    horizon_hours = 1032
    if (summary["NREP"], summary["RTILW"], summary["RTIUP"]) != (1, 0, horizon_hours):
        raise ValueError("SIMLOX result period or sample count changed")
    if (control["SIMPE"], control["RCINT"], len(profile), mission_type["MSUCPT"]) != (1032, 0.5, 104, 0.75):
        raise ValueError("SIMLOX mission or collection settings changed")
    if (plan["duration_minutes"] != horizon_hours * 60 or len(plan["missions"]) != 104
            or canonical["time"]["duration_minutes"] != horizon_hours * 60
            or canonical["time"]["sample_every_minutes"] != 30):
        raise ValueError("canonical Plan horizon or mission count changed")
    for records in (system, stock, resources):
        intervals(records, horizon_hours)
    started = count_from_fraction(summary["MSTF"], 104)
    successful = count_from_fraction(summary["MSUF"], 104)
    if successful > started:
        raise ValueError("SIMLOX successful fixed missions exceed starts")
    reference = [reference_counts(payloads[f"reference_seed{seed}"], plan) for seed in (0, 1)]
    if reference[0]["end_minute"] != 61920 or reference[1]["end_minute"] != 61464:
        raise ValueError("reference stop times changed")
    duration = sum(row["ETINT"] - row["STINT"] for row in system)
    mean_ready = sum(row["NSYRY"] * (row["ETINT"] - row["STINT"]) for row in system) / duration
    backorder_hours = sum(row["NBO"] * (row["ETINT"] - row["STINT"]) for row in stock)
    output = {
        "evidence": evidence,
        "scope": "input/denominator and within-report arithmetic only; no cross-runtime sample or event parity",
        "horizon": {
            "input_minutes": plan["duration_minutes"],
            "simlox_report_hours": [summary["RTILW"], summary["RTIUP"]],
            "simlox_intervals": len(system),
            "interval_minutes": 30,
            "reference_seed0_end_minute": reference[0]["end_minute"],
            "reference_seed1_end_minute": reference[1]["end_minute"],
        },
        "simlox_fixed_missions": {
            "planned": len(profile),
            "started_from_MSTF": started,
            "successful_from_MSUF": successful,
            "MSTF_raw": summary["MSTF"],
            "MSUF_raw": summary["MSUF"],
            "MTMF_time_fraction_raw": summary["MTMF"],
            "STMF_system_time_fraction_raw": summary["STMF"],
            "preparations_started_system_count": sum(row["NPSTA"] for row in system),
            "preparations_succeeded_system_count": sum(row["NPSUC"] for row in system),
        },
        "reference": reference,
        "simlox_ready_systems": {
            "time_average_NSYRY": mean_ready,
            "time_average_NSYRY_divided_by_eight": mean_ready / 8,
            "canonical_operational_availability_exported": "operational_availability" in payloads["reference_seed0"]["metrics"],
        },
        "simlox_stock": {
            "time_average_backorders_NBO": backorder_hours / duration,
            "backorder_hours": backorder_hours,
            "intervals_with_backorder": sum(row["NBO"] > 0 for row in stock),
            "failure_demand_volume_NDF": sum(row["NDF"] for row in stock),
        },
        "simlox_resources": {
            "intervals_with_unsatisfied_maintenance_resource_demand_NRW": sum(row["NRW"] > 0 for row in resources),
        },
        "report_limit": {
            "system_interval_STREQ_sum": sum(row["STREQ"] or 0 for row in system),
            "fixed_mission_rows_exported": any("FixedMission" in table["name"].replace(" ", "")
                                                  for table in simlox["report"]["tables"]),
            "event_or_rng_tape_exported": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"planned": 104, "simlox_started": started, "simlox_successful": successful,
                      "reference_seed1_started": reference[1]["started_waves"],
                      "reference_seed1_successful": reference[1]["successful_waves"],
                      "reference_seed1_end_minute": reference[1]["end_minute"]}))


if __name__ == "__main__":
    main()
