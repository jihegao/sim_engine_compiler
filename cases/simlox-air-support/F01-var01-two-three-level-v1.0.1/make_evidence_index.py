"""Seal accepted F01.var01 pair and excluded predecessor diagnostic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "evidence-index.json"
DIAG = ROOT / "F01-var01-nested-reissue-v1.0.0"
RUNS = [
    (DIAG, "f01-var01-nested-v100-ssh-20261004-01", False),
    (HERE, "f01-var01-two-v101-ssh-20261004-01", True),
    (HERE, "f01-var01-three-v101-ssh-20261004-01", True),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    author = json.loads((HERE / "author-validation-2026-10-04.json").read_text(encoding="utf-8"))
    independent = json.loads((HERE / "review/independent-verdict.json").read_text(encoding="utf-8"))
    assert author["passed"] and not author["failures"] and independent["passed"] and not independent["failures"]
    for role in ("two", "three"):
        parent = contract[f"accepted_{role}_level_parent"]
        base = ROOT / parent["package"]
        assert sha(base / "native-input.json") == parent["input_sha256"]
        assert sha(base / "runs" / parent["run_id"] / "closure.json") == parent["native_closure_sha256"]
    diagnostic = json.loads((DIAG / "diagnostic-2026-10-04.json").read_text(encoding="utf-8"))
    assert diagnostic["publication_state"] == "not_published"
    assert diagnostic["run_id"] == contract["preceding_unpublished_diagnostic"]["run_id"]
    assert diagnostic["closure_sha256"] == contract["preceding_unpublished_diagnostic"]["closure_sha256"]
    assert diagnostic["input_sha256"] == contract["preceding_unpublished_diagnostic"]["input_sha256"]
    assert diagnostic["observed_installed_lru_failures"] == 1 and diagnostic["observed_lru_stock_reissues"] == 0
    assert sha(DIAG / "runs" / contract["preceding_unpublished_diagnostic"]["run_id"] / "closure.json") == contract["preceding_unpublished_diagnostic"]["closure_sha256"]
    source = []
    for base in (DIAG, HERE):
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path == OUTPUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            source.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    runs = []
    for base, run_id, accepted in RUNS:
        run = base / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run_id and closure["error"] is None and len(closure["raw"]) == 12
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
        assert closure["invocation_sha256"] == sha(run / "invocation.json")
        for name, meta in closure["raw"].items():
            path = run / name
            assert path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
        runs.append({"package": base.name, "run_id": run_id, "accepted": accepted,
                     "local_path": str(run.resolve()), "closure_sha256": sha(run / "closure.json"),
                     "invocation_sha256": sha(run / "invocation.json"), "raw": closure["raw"]})
    result = {"schema": "simlox-f01-var01-two-three-evidence-index/v1", "case_id": "F01",
              "variant_id": "F01.var01", "version": "1.0.1", "publication_state": "not_published",
              "source": source, "runs": runs, "accepted_raw_count": 24, "diagnostic_raw_count": 12,
              "two_parent_input_sha256": contract["accepted_two_level_parent"]["input_sha256"],
              "three_parent_input_sha256": contract["accepted_three_level_parent"]["input_sha256"],
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": 24, "diagnostic_raw": 12,
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
