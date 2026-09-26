"""Index immutable A01 SIMPE and result-collection boundary evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from build_horizon_variants import ENDS, REPO, ROOT
from build_simpe_margin import ENDS as MARGIN_ENDS
from validate_collection import validate as rederive_collection

BASE = REPO / "data/local/simlox-case-library/v1"
OUTPUT = ROOT / "observation-probes.json"


def artifact(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def inspect(kind: str, variant: str) -> dict:
    prefix = ("horizon" if kind == "simulation_period" else
              "simpe" if kind == "simpe_margin" else "collection")
    run_id = f"a01-{prefix}-{variant.replace('_', '-')}-20260927-01"
    group = ("horizon-runs" if kind == "simulation_period" else
             "simpe-margin-runs" if kind == "simpe_margin" else "collection-runs")
    run = BASE / group / run_id
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace") if (run / "run.log").is_file() else ""
    summary = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    errors = re.findall(r"\(error #(\d+)\) ([^\r\n]+)", log)
    validation = json.loads((run / "validation.json").read_text(encoding="utf-8-sig")) if (run / "validation.json").is_file() else None
    reviewed = rederive_collection(run, variant, write=False) if kind == "result_collection" and validation else None
    files = {name: artifact(run / name) for name in ("input.json", "model.sxi", "model.sxo", "roundtrip-raw.json",
                                                   "run.log", "model.log", "report-raw.json", "validation.json")}
    return {"variant": variant, "requested_end_hours": (MARGIN_ENDS if kind == "simpe_margin" else ENDS)[variant], "run_id": run_id,
            "run_dir": str(run.resolve()),
            "conversion": {"errors": int(summary[1]), "warnings": int(summary[2]), "notes": int(summary[3])} if summary else None,
            "error_details": [{"number": n, "text": t} for n, t in errors],
            "roundtrip": json.loads((run / "roundtrip-check.json").read_text(encoding="utf-8-sig")) if (run / "roundtrip-check.json").is_file() else None,
            "status": validation["status"] if validation else "native_conversion_rejected_or_incomplete",
            "observation": reviewed["observation"] if reviewed else (validation["observation"] if validation else None),
            "derived_review_note": ("Retained first-pass validation.json labeled before-launch as unfinished; corrected classification is in this index, derived read-only from unchanged raw files."
                                    if reviewed and "unfinished_at_requested_end_from_events" in validation["observation"] else None),
            "artifacts": files}


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    doc = {"parent": "A01@1.0.0", "source_input_sha256": "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7",
           "tools": {"simlox_exe_sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
                     "horizon_runner_sha256": hashlib.sha256((ROOT / "tools/run_horizon_probe.ps1").read_bytes()).hexdigest(),
                     "simpe_margin_runner_sha256": hashlib.sha256((ROOT / "tools/run_simpe_margin.ps1").read_bytes()).hexdigest(),
                     "collection_runner_sha256": hashlib.sha256((ROOT / "tools/run_collection_probe.ps1").read_bytes()).hexdigest(),
                     "collection_validator_review_sha256": hashlib.sha256((ROOT / "tools/validate_collection.py").read_bytes()).hexdigest()},
           "time_unit": "hour", "printed_tie_caution": "ENLOG decimal text is not an internal exact-time ordering proof",
           "simulation_period_matrix": [inspect("simulation_period", key) for key in ENDS],
           "simpe_margin_positive_controls": [inspect("simpe_margin", key) for key in MARGIN_ENDS],
           "result_collection_matrix": [inspect("result_collection", key) for key in ENDS]}
    OUTPUT.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(OUTPUT)


if __name__ == "__main__":
    main()
