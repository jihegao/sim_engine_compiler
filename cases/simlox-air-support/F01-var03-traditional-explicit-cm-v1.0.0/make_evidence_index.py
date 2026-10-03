"""Seal F01.var03 source and the immutable native run without copying raw files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/f01-var03-explicit-v100-ssh-20261004-04"
OUT = HERE / "evidence-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    contract = load(HERE / "contract.json")
    author = load(HERE / "author-validation-2026-10-04.json")
    reviewer = load(HERE / "review/independent-verdict.json")
    assert author["passed"] and not author["failures"] and reviewer["passed"] and not reviewer["failures"]
    assert sha(HERE / "explicit-input.json") == contract["explicit_input_sha256"]
    assert sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
    for key, filename in (("accepted_traditional_behavior_parent", "three-level-input.json"),
                          ("accepted_explicit_cm_reference", "native-input.json")):
        pin = contract[key]
        base = ROOT / pin["package"]
        assert sha(base / filename) == pin["input_sha256"]
        assert sha(base / "runs" / pin["run_id"] / "closure.json") == pin["closure_sha256"]
    pin = contract["accepted_traditional_behavior_parent"]
    assert sha(ROOT / pin["package"] / "evidence-index.json") == pin["evidence_index_sha256"]
    source = []
    for path in sorted(HERE.rglob("*")):
        if (not path.is_file() or path == OUT or "runs" in path.parts or "__pycache__" in path.parts
                or path.suffix == ".pyc" or path.name.startswith("cli-scope-signoff-")):
            continue
        source.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
                       "bytes": path.stat().st_size})
    closure = load(RUN / "closure.json")
    assert closure["run_id"] == RUN.name and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(RUN / "invocation.json")
    assert len(closure["raw"]) == 12
    for name, meta in closure["raw"].items():
        path = RUN / name
        assert path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
    result = {"schema": "simlox-f01-var03-traditional-explicit-evidence-index/v1",
              "case_id": "F01", "variant_id": "F01.var03", "version": "1.0.0",
              "publication_state": "not_published", "source": source,
              "runs": [{"state": "accepted_candidate", "run_id": RUN.name,
                        "local_path": str(RUN.resolve()),
                        "closure_sha256": sha(RUN / "closure.json"),
                        "invocation_sha256": sha(RUN / "invocation.json"),
                        "error": closure["error"], "raw": closure["raw"]}],
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "raw_files": len(closure["raw"]),
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
