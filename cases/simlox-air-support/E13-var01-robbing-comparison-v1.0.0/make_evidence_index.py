"""Seal E13.var01 source and local raw after two read-only replays pass."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "evidence-index.json"
PACKAGES = [
    "E13-var01-two-item-robbing-probe-v0.1.0",
    "E13-var01-two-item-robbing-probe-v0.1.1",
    "E13-var01-two-item-robbing-probe-v0.1.2",
    "E13-var01-two-item-no-robbing-control-v0.1.3",
    HERE.name,
]
RUNS = [
    (PACKAGES[0], "e13-var01-two-item-probe-v010-ssh-20261004-01", False),
    (PACKAGES[1], "e13-var01-two-item-probe-v011-ssh-20261004-01", False),
    (PACKAGES[2], "e13-var01-two-item-probe-v012-ssh-20261004-01", True),
    (PACKAGES[3], "e13-var01-no-robbing-control-v013-ssh-20261004-01", True),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    author = json.loads((HERE / "author-validation-2026-10-04.json").read_text(encoding="utf-8"))
    independent = json.loads((HERE / "review" / "independent-verdict.json").read_text(encoding="utf-8"))
    assert author["passed"] and not author["failures"]
    assert independent["passed"] and not independent["failures"]
    parent = ROOT / "E03-two-aircraft-shared-spare-v1.0.0"
    assert sha(parent / "native-input.json") == "657c0d52116c09ef2dbd009209f461f6fb4ed3570327c4305e0e4608f208cbf0"
    assert sha(parent / "runs" / "e03-v100-ssh-20260929-01" / "closure.json") == "b200b18fbbed80dcc7ff9e9f4e2e1d7952734449b49a400a509d054090a9b7d6"
    assert sha(parent / "cli-scope-signoff-2026-09-29.md") == "dedf59901c805c7bbfd6c7421f02d0b051d0fbbc38c97819970988203e47c4e1"
    source = []
    for package in PACKAGES:
        base = ROOT / package
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path == OUTPUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            source.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    runs = []
    for package, run_id, accepted in RUNS:
        run = ROOT / package / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run_id and closure["error"] is None and len(closure["raw"]) == 12
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
        assert closure["invocation_sha256"] == sha(run / "invocation.json")
        for name, meta in closure["raw"].items():
            path = run / name
            assert path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
        runs.append({"package": package, "run_id": run_id, "accepted_paired_arm": accepted,
                     "local_path": str(run.resolve()), "closure_sha256": sha(run / "closure.json"),
                     "invocation_sha256": sha(run / "invocation.json"), "raw": closure["raw"]})
    result = {"schema": "simlox-e13-var01-robbing-comparison-v100-evidence-index/v1", "case_id": "E13",
              "variant_id": "E13.var01", "version": "1.0.0", "publication_state": "not_published",
              "source": source, "runs": runs, "accepted_raw_count": 24, "diagnostic_raw_count": 24,
              "parent_input_sha256": sha(parent / "native-input.json"),
              "parent_closure_sha256": sha(parent / "runs" / "e03-v100-ssh-20260929-01" / "closure.json"),
              "parent_signoff_sha256": sha(parent / "cli-scope-signoff-2026-09-29.md"),
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "paired_raw": 24, "diagnostic_raw": 24,
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
