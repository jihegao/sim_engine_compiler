"""Seal F02.var04 active-repair accepted candidate and local native artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/f02-var04-active-repair-v100-ssh-20261004-01"
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
    parent = ROOT / contract["accepted_parent"]["package"]
    sibling = ROOT / contract["accepted_sibling"]["package"]
    assert sha(parent / "risk-input.json") == contract["accepted_parent"]["input_sha256"]
    assert sha(parent / "runs" / contract["accepted_parent"]["run_id"] / "closure.json") == contract["accepted_parent"]["closure_sha256"]
    assert sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"]
    assert sha(sibling / "evidence-index.json") == contract["accepted_sibling"]["evidence_index_sha256"]
    assert sha(sibling / "runs/f02-var04-terminal-v102-ssh-20261004-01/closure.json") == contract["accepted_sibling"]["native_closure_sha256"]
    assert sha(HERE / "repair-input.json") == contract["repair_input_sha256"]
    assert sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
    source = []
    for path in sorted(HERE.rglob("*")):
        if (not path.is_file() or path == OUT or "runs" in path.parts or "__pycache__" in path.parts
                or path.suffix == ".pyc" or path.name.startswith("cli-scope-signoff-")):
            continue
        source.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    closure = load(RUN / "closure.json")
    assert closure["run_id"] == RUN.name and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(RUN / "invocation.json")
    assert len(closure["raw"]) == 12
    for name, meta in closure["raw"].items():
        path = RUN / name
        assert path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
    result = {"schema": "simlox-f02-var04-active-repair-evidence-index/v1", "case_id": "F02",
              "variant_id": "F02.var04", "version": "1.0.0", "publication_state": "not_published",
              "source": source,
              "accepted_parent": {"package": parent.name, "run_id": contract["accepted_parent"]["run_id"],
                                  "closure_sha256": contract["accepted_parent"]["closure_sha256"],
                                  "evidence_index_sha256": contract["accepted_parent"]["evidence_index_sha256"]},
              "accepted_sibling": {"package": sibling.name,
                                   "closure_sha256": contract["accepted_sibling"]["native_closure_sha256"],
                                   "evidence_index_sha256": contract["accepted_sibling"]["evidence_index_sha256"]},
              "run": {"state": "accepted_candidate", "run_id": RUN.name, "local_path": str(RUN.resolve()),
                      "closure_sha256": sha(RUN / "closure.json"), "invocation_sha256": sha(RUN / "invocation.json"),
                      "raw": closure["raw"]},
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    OUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "raw_files": len(closure["raw"]),
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
