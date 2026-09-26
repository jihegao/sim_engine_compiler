"""Read-only corrected A01 collection-window analysis; never alters native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_horizon_variants import ENDS, REPO, ROOT
from validate_collection import validate

BASE = REPO / "data/local/simlox-case-library/v1/collection-runs"
OUTPUT = ROOT / "collection-window-review-v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    runs = []
    for variant in ENDS:
        run_id = f"a01-collection-{variant.replace('_', '-')}-20260927-01"
        run = BASE / run_id
        original = run / "validation.json"
        if not original.is_file():
            raise FileNotFoundError(original)
        reviewed = validate(run, variant, write=False)
        if reviewed["status"] != "native_probe_recorded":
            raise ValueError(f"collection probe not valid: {run_id}")
        runs.append({"variant": variant, "run_id": run_id, "run_dir": str(run.resolve()),
                     "original_validation_sha256": sha(original),
                     "raw_input_sha256": sha(run / "input.json"),
                     "raw_report_sha256": sha(run / "report-raw.json"),
                     "raw_enlog_sha256": sha(run / "model.log"),
                     "observation": reviewed["observation"]})
    return {"analysis_version": "collection-window-review-v2",
            "analyzer_path": "tools/validate_collection.py",
            "analyzer_sha256": sha(ROOT / "tools/validate_collection.py"),
            "source_input_sha256": sha(ROOT / "A01-single-aircraft-single-mission/native-input.json"),
            "read_only": True, "raw_native_files_changed": False,
            "runs": runs}


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(OUTPUT)


if __name__ == "__main__":
    main()
