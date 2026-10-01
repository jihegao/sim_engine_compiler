"""Freeze and validate the fresh accepted G02.var01 native pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from validate import HERE, sha, validate

IDS = ("g02-var01-two-position-accepted-20261001-01",
       "g02-var01-two-position-accepted-20261001-02")
REVIEW = HERE / "review" / "author-pair-validation-2026-10-01.json"


def save_frozen(path: Path, value: dict) -> None:
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f"frozen file differs: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(raw)


def main() -> None:
    validations = []
    for run_id in IDS:
        run = HERE / "runs" / run_id
        result = validate(run)
        if not result["passed"]:
            raise ValueError(f"author validation failed: {run_id}: {result['failures']}")
        save_frozen(run / "validation.json", result)
        manifest = {"schema": "simlox-g02-var01-accepted-run-manifest/v1", "run_id": run_id,
                    "input_sha256": sha(run / "input.json"),
                    "closure_sha256": sha(run / "closure.json"),
                    "validation_sha256": sha(run / "validation.json"),
                    "report_sha256": sha(run / "report-raw.json"),
                    "model_log_sha256": sha(run / "model.log"),
                    "validator_sha256": sha(HERE / "validate.py")}
        save_frozen(run / "run-manifest.json", manifest)
        validations.append({"run_id": run_id, "validation_sha256": sha(run / "validation.json"),
                            "manifest_sha256": sha(run / "run-manifest.json"),
                            "report_sha256": manifest["report_sha256"],
                            "model_log_sha256": manifest["model_log_sha256"]})
    if len({r["report_sha256"] for r in validations}) != 1 or len({r["model_log_sha256"] for r in validations}) != 1:
        raise ValueError("fresh same-seed pair differs in native output bytes")
    output = {"schema": "simlox-g02-var01-author-pair-validation/v1", "passed": True,
              "accepted_runs": validations, "raw_seals": 24,
              "semantic_report_identical": True,
              "scope": "same input, seed and installed executable; position-specific modes and direct CM"}
    save_frozen(REVIEW, output)
    print(json.dumps({"passed": True, "accepted": list(IDS), "raw_seals": 24,
                      "report_sha256": validations[0]["report_sha256"],
                      "model_log_sha256": validations[0]["model_log_sha256"]}))


if __name__ == "__main__":
    main()
