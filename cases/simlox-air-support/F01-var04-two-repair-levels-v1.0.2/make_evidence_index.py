"""Seal accepted F01.var04 source and all three immutable native run paths."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "evidence-index.json"
RUNS = [
    ("excluded_diagnostic", ROOT / "F01-var04-two-repair-levels-v1.0.0/runs/f01-var04-levels-v100-ssh-20261004-01", 9),
    ("excluded_diagnostic", ROOT / "F01-var04-two-repair-levels-v1.0.1/runs/f01-var04-levels-v101-ssh-20261004-01", 12),
    ("accepted_candidate", HERE / "runs/f01-var04-levels-v102-ssh-20261004-01", 12),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    contract = load(HERE / "contract.json")
    author = load(HERE / "author-validation-2026-10-04.json")
    reviewer = load(HERE / "review/independent-verdict.json")
    assert author["passed"] and not author["failures"] and reviewer["passed"] and not reviewer["failures"]
    assert sha(HERE / "native-input.json") == contract["native_input_sha256"]
    assert sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
    for key in ("accepted_behavior_parent", "accepted_level_allocation_reference"):
        pin = contract[key]
        base = ROOT / pin["package"]
        assert sha(base / pin["input"]) == pin["input_sha256"]
        assert sha(base / "runs" / pin["run_id"] / "closure.json") == pin["closure_sha256"]
        assert sha(base / "evidence-index.json") == pin["evidence_index_sha256"]
    source = []
    for p in sorted(HERE.rglob("*")):
        if not p.is_file() or p == OUT or "runs" in p.parts or "__pycache__" in p.parts or p.suffix == ".pyc" or p.name.startswith("cli-scope-signoff-"):
            continue
        source.append({"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size})
    runs = []
    for state, directory, count in RUNS:
        closure = load(directory / "closure.json")
        assert closure["run_id"] == directory.name and len(closure["raw"]) == count
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
        assert closure["invocation_sha256"] == sha(directory / "invocation.json")
        if state == "accepted_candidate":
            assert closure["error"] is None and author["closure_sha256"] == sha(directory / "closure.json")
        for name, metadata in closure["raw"].items():
            p = directory / name
            assert p.stat().st_size == metadata["bytes"] and sha(p) == metadata["sha256"]
        runs.append({"state": state, "run_id": directory.name, "local_path": str(directory.resolve()),
                     "closure_sha256": sha(directory / "closure.json"),
                     "invocation_sha256": sha(directory / "invocation.json"), "error": closure["error"],
                     "raw": closure["raw"]})
    assert runs[0]["closure_sha256"] == contract["prior_excluded_diagnostic"]["closure_sha256"]
    assert runs[1]["closure_sha256"] == contract["second_excluded_diagnostic"]["closure_sha256"]
    result = {"schema": "simlox-f01-var04-two-repair-levels-evidence-index/v1",
              "case_id": "F01", "variant_id": "F01.var04", "version": "1.0.2",
              "publication_state": "not_published", "source": source, "runs": runs,
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "raw_files": sum(len(x["raw"]) for x in runs),
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
