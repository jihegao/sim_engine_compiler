"""Replay both fresh accepted J04.var02 runs and their aggregate repeatability."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import validate

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "review/author-pair-validation-2026-10-01.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    contract = validate.load(HERE / "contract.json")
    runs = [HERE / "runs" / run_id for run_id in contract["expected_observation"]["run_ids"]]
    results = [validate.validate(run) for run in runs]
    errors = [f"{result['run_id']}: {message}" for result in results for message in result["differences"]]
    reports = [validate.load(run / "report-raw.json") for run in runs]
    if reports[0] != reports[1]:
        errors.append("same-seed native JSON reports differ")
    if (runs[0] / "model.log").read_bytes() != (runs[1] / "model.log").read_bytes():
        errors.append("same-seed first-replication event logs differ")
    invocations = [validate.load(run / "invocation.json") for run in runs]
    if invocations[0].get("created_utc") == invocations[1].get("created_utc"):
        errors.append("accepted runs do not have distinct invocations")
    details = []
    for run, result in zip(runs, results, strict=True):
        closure = validate.load(run / "closure.json")
        details.append({
            "run_id": run.name, "passed": result["passed"], "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"),
            "validation_sha256": sha(run / "validation.json"), "report_sha256": sha(run / "report-raw.json"),
            "first_replication_log_sha256": sha(run / "model.log"),
            "nrep": result["nrep"], "rsmtmf": result["rsmtmf"],
            "average_aircraft_flight_hours": result["average_aircraft_flight_hours"],
            "raw_seal_count": len(closure["raw"]),
        })
    result = {
        "schema": "simlox-j04-var02-confidence-stop-author-pair/v1",
        "case_id": "J04", "variant_id": "J04.var02", "version": "1.0.0",
        "passed": not errors, "differences": errors, "runs": details,
        "semantic_report_identical": reports[0] == reports[1],
        "first_replication_event_log_identical": (runs[0] / "model.log").read_bytes() == (runs[1] / "model.log").read_bytes(),
        "raw_seal_count": sum(item["raw_seal_count"] for item in details),
        "limits": "ENLOG exposes only replication 1; aggregate report rows do not identify the other 80 realized mission counts or the rolling ten-replication criterion.",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.parent.mkdir(exist_ok=True)
    if OUTPUT.exists() and OUTPUT.read_bytes() != raw:
        raise ValueError("frozen author pair result differs")
    if not OUTPUT.exists():
        OUTPUT.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "differences": errors, "raw_seals": result["raw_seal_count"],
                      "semantic_report_identical": result["semantic_report_identical"]}))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
