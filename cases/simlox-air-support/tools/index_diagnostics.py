"""Record immutable initial/no-preparation diagnostic raw artifacts by hash."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BASE = REPO / "data/local/simlox-case-library/v1"
OUTPUT = ROOT / "diagnostic-evidence.json"
RUNS = (("A01", "a01-initial-20260927-01", 1),
        ("A02", "a02-initial-20260927-01", 3),
        ("A01", "a01-no-prep-row-20260927-01", 0))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    runs = []
    for case_id, run_id, npsta in RUNS:
        folder = BASE / case_id / run_id
        if not folder.is_dir():
            raise FileNotFoundError(folder)
        artifacts = {path.name: {"path": str(path.resolve()), "bytes": path.stat().st_size,
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                     for path in sorted(folder.iterdir()) if path.is_file()}
        runs.append({"case_id": case_id, "run_id": run_id, "directory": str(folder.resolve()),
                     "native_npsta_from_system_results": npsta,
                     "contract_status": "no-preparation mismatch" if npsta else "corrected diagnostic for final input",
                     "artifacts": artifacts})
    doc = {"purpose": "retained initial zero-duration MissionPreparation-row evidence and one row-free correction probe",
           "runs": runs}
    OUTPUT.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(OUTPUT)


if __name__ == "__main__":
    main()
