"""Author replay of bounded F04.var02 fixed-128 native repeat runs."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

HERE = Path(__file__).resolve().parent
RUNS = {
    arm: HERE / "runs" / f"f04-var02-stochastic-v100-repeat-{arm}-ssh-20261004-01"
    for arm in ("a", "b")
}
RAW = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "replication-report-raw.json", "replication-report-export.log",
    "steps.json", "roundtrip-validation.json",
}
T127 = 1.9788195347


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> tuple[dict, bool]:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        out: list[str] = []
        quoted = escaped = False
        n = len(raw)
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == ",":
                j = i + 1
                while j < n and raw[j].isspace():
                    j += 1
                if j >= n or raw[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out)), True


def rows(report: dict, name: str) -> list[dict]:
    found = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    table = found[0]
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, record))
            for instance in table["instances"] for record in instance["rows"]]


def close(actual: float, expected: float, tol: float = 2e-5) -> bool:
    return math.isclose(actual, expected, rel_tol=tol, abs_tol=tol)


def metric(values: list[float], target_kind: str, target: float) -> dict:
    assert len(values) == 128
    mean = statistics.mean(values)
    sd = statistics.stdev(values)
    half = T127 * sd / math.sqrt(len(values))
    limit = target if target_kind == "absolute" else target * abs(mean)
    return {
        "n": len(values), "mean": mean, "sample_sd": sd,
        "nominal_t95_halfwidth": half, "target_kind": target_kind,
        "target": target, "allowed_halfwidth": limit,
        "meets_target": half <= limit, "minimum": min(values), "maximum": max(values),
    }


def validate_run(label: str, run: Path, contract: dict) -> dict:
    closure = read(run / "closure.json")
    invocation = read(run / "invocation.json")
    assert closure["error"] is None and closure["publication_state"] == "not_published"
    assert closure["invocation_sha256"] == sha(run / "invocation.json")
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    sources = closure["source_hashes_before"]
    assert sources["native_input"] == contract["input_sha256"] == sha(HERE / "native-input.json")
    assert sources["contract"] == sha(HERE / "contract.json")
    assert sources["exact_diff"] == contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json")
    assert sources["report_settings"] == contract["report_settings"]["one_byte_outpr_enabled_sha256"]
    for name in ("build.py", "describe_diff.py", "make_report_settings.py",
                 "check_roundtrip.py", "run_native_ssh.ps1"):
        assert sources[name] == sha(HERE / name), name
    assert invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
    assert invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
    assert invocation["gui"]["pid"] == 13340
    assert invocation["source_hashes_before"] == sources
    assert set(closure["raw"]) == RAW
    for name, info in closure["raw"].items():
        path = run / name
        assert path.stat().st_size == info["bytes"] and sha(path) == info["sha256"], name
    assert sha(run / "input.json") == contract["input_sha256"]
    steps = read(run / "steps.json")
    assert [step["name"] for step in steps] == [
        "import", "export", "calc", "jsonreport", "replication_report",
        "check_import_export"]
    assert all(step["status"] == "completed" and step["exit_code"] == 0 for step in steps)
    assert all(step.get("gui_preserved") for step in steps[:5])
    roundtrip = read(run / "roundtrip-validation.json")
    assert roundtrip["passed"] and len(roundtrip["populated_tables"]) == 31
    assert roundtrip["source_sha256"] == contract["input_sha256"]
    log = (run / "run.log").read_text(errors="replace")
    assert re.search(r"Input conversion completed\. Errors: 0, Warnings: 1, Notes: 0", log)
    assert re.findall(r"\(warning #(\d+)\)", log) == ["108"]
    assert not re.search(r"\((?:error|notice) #", log)

    default, default_repaired = native_json(run / "report-raw.json")
    enabled = read(run / "replication-report-raw.json")
    default_names = {t["name"] for t in default["report"]["tables"]}
    enabled_names = {t["name"] for t in enabled["report"]["tables"]}
    assert enabled_names - default_names == {
        "Replications", "SystemResultsReplication", "SystemResultsReplicationTotal"}
    reps = rows(enabled, "Replications")
    totals = rows(enabled, "SystemResultsReplicationTotal")
    horizon = rows(enabled, "SystemResultsReplication")
    assert len(reps) == 128 and len(totals) == len(horizon) == 256
    assert [r["REPNO"] for r in reps] == list(range(1, 129))
    assert reps[0]["RSEED"] == "1" and len({r["RSEED"] for r in reps}) == 128
    units = ("TEACH-UNIT", "TEACH-UNIT-2")
    by_key = {(r["REPLID"], r["UNID"]): r for r in totals}
    assert len(by_key) == 256
    assert set(by_key) == {(rep, unit) for rep in range(1, 129) for unit in units}
    assert all(r["SID"] == "TEACH-AIR-01" for r in totals)
    for row in horizon:
        assert (row["STINT"], row["ETINT"]) == (0, 1032)
        total = by_key[(row["REPLID"], row["UNID"])]
        assert close(row["STACC"], total["STACC"])
        assert row["NFAIL"] == total["NFAIL"]

    event = (run / "model.log").read_text(errors="replace")
    starts = re.findall(r"^Time: [\d.]+ <[^>]+> mission starting,", event, re.M)
    successes = re.findall(r"^Time: [\d.]+ <[^>]+> mission success:", event, re.M)
    aborts = re.findall(r"^Time: [\d.]+ <[^>]+> mission aborted:", event, re.M)
    failures = re.findall(r"^Time: [\d.]+ <TEACH-AIR-01,\d+> critical random failure added", event, re.M)
    assert (len(starts), len(successes), len(aborts), len(failures)) == (63, 43, 20, 27)
    assert close(reps[0]["FMSUC"], len(successes) / len(starts))
    assert sum(by_key[(1, unit)]["NFAIL"] for unit in units) == len(failures)
    for phrase in ("Item demand arrives", "Backorder added", "Take replacement item",
                   "transport task 0 starts", "System to repair", "P-MAINT"):
        assert phrase in event, phrase
    summary = rows(default, "ResultSummary")[0]
    assert summary["NREP"] == 128 and (summary["RTILW"], summary["RTIUP"]) == (0, 1032)
    for reported, replicated in (("MTMF", "FMTAC"), ("MSTF", "FMSTA"),
                                  ("MSUF", "FMSUC"), ("STMF", "FSTAC")):
        assert close(summary[reported], statistics.mean(row[replicated] for row in reps))
    system = rows(default, "SystemResults")
    stock = rows(default, "StockTotalResults")
    resource = rows(default, "ResourceResults")
    assert len(system) == len(stock) == len(resource) == 2064
    for table in (system, stock, resource):
        assert all(close(row["STINT"], i / 2) and close(row["ETINT"], (i + 1) / 2)
                   for i, row in enumerate(table))
    assert all(close(row["NSYA"] + row["NSYUA"], 8, 1e-4) for row in system)
    flight = [sum(by_key[(rep, unit)]["STACC"] for unit in units) * 1032
              for rep in range(1, 129)]
    aggregate_flight = sum((row["ETINT"] - row["STINT"]) * row["STACC"] for row in system)
    assert close(aggregate_flight, statistics.mean(flight))
    failure_counts = [sum(by_key[(rep, unit)]["NFAIL"] for unit in units)
                      for rep in range(1, 129)]
    assert close(sum(row["NFAIL"] for row in system), statistics.mean(failure_counts))
    metrics = {
        "mission_success_fraction": metric([row["FMSUC"] for row in reps], "absolute", .05),
        "aircraft_flight_hours": metric(flight, "relative", .05),
        "observed_failures": metric(failure_counts, "relative", .10),
    }
    assert all(data["meets_target"] for data in metrics.values())
    return {
        "run_id": run.name, "closure_sha256": sha(run / "closure.json"),
        "raw_files_verified": len(closure["raw"]),
        "default_report_parser_corrected_trailing_comma": default_repaired,
        "replication_ids": len(reps), "system_total_rows": len(totals),
        "first_replication": {
            "mission_starts": len(starts), "mission_successes": len(successes),
            "mission_aborts": len(aborts), "critical_random_failures": len(failures),
            "aircraft_flight_hours_from_system_stacc": flight[0],
        },
        "metrics": metrics,
        "aggregate_descriptive": {
            "stock_backorder_item_hours": sum((r["ETINT"] - r["STINT"]) * r["NBO"] for r in stock),
            "resource_booked_hours": sum((r["ETINT"] - r["STINT"]) * r["NRUM"] for r in resource),
            "resource_queued_hours": sum((r["ETINT"] - r["STINT"]) * r["NRW"] for r in resource),
            "terminal_ready": system[-1]["NSYRY"],
            "terminal_unavailable": system[-1]["NSYUA"],
        },
    }


def main() -> None:
    contract = read(HERE / "contract.json")
    assert contract["version"] == "1.0.0-candidate"
    reports = {arm: validate_run(arm, run, contract) for arm, run in RUNS.items()}
    same = {}
    for name in ("model.log", "report-raw.json", "replication-report-raw.json"):
        same[name] = sha(RUNS["a"] / name) == sha(RUNS["b"] / name)
    assert all(same.values())
    result = {
        "schema": "simlox-f04-stochastic-43day-author-validation/v1",
        "decision": "GO_BOUNDED",
        "scope": "F04.var02 eight-aircraft 43-day fixed-128 CLI stochastic slice only",
        "run_reports": reports,
        "same_seed_repeat_byte_identical": same,
        "limitations": contract["limitations"],
    }
    target = HERE / "author-native-validation-2026-10-04.json"
    raw = (json.dumps(result, indent=2) + "\n").encode()
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(json.dumps({
        "decision": result["decision"],
        "validation_sha256": hashlib.sha256(raw).hexdigest(),
        "metrics": reports["a"]["metrics"],
        "repeat_identical": same,
    }, indent=2))


if __name__ == "__main__":
    main()
