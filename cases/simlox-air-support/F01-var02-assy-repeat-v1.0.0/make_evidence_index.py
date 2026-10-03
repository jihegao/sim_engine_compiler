"""Seal accepted F01.var02 source and local native artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/f01-var02-assy-v100-ssh-20261004-01"
OUT = HERE / "evidence-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    author = json.loads((HERE / "author-validation-2026-10-04.json").read_text(encoding="utf-8"))
    reviewer = json.loads((HERE / "review/independent-verdict.json").read_text(encoding="utf-8"))
    assert author["passed"] and not author["failures"] and reviewer["passed"] and not reviewer["failures"]
    for key in ("accepted_behavior_parent", "accepted_structural_reference"):
        pin = contract[key]
        base = ROOT / pin["package"]
        input_file = pin.get("input", "native-input.json")
        assert sha(base / input_file) == pin["input_sha256"]
        assert sha(base / "runs" / pin["run_id"] / "closure.json") == pin["closure_sha256"]
        assert sha(base / "evidence-index.json") == pin["evidence_index_sha256"]
    assert sha(HERE / "native-input.json") == contract["native_input_sha256"]
    assert sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == RUN.name and closure["error"] is None and len(closure["raw"]) == 12
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(RUN / "invocation.json")
    for name, meta in closure["raw"].items():
        path = RUN / name
        assert path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
    result = {"schema": "simlox-f01-var02-assy-evidence-index/v1", "case_id": "F01",
              "variant_id": "F01.var02", "version": "1.0.0", "publication_state": "not_published",
              "source": source,
              "accepted_behavior_parent_input_sha256": contract["accepted_behavior_parent"]["input_sha256"],
              "accepted_structural_reference_input_sha256": contract["accepted_structural_reference"]["input_sha256"],
              "run": {"run_id": RUN.name, "local_path": str(RUN.resolve()),
                      "closure_sha256": sha(RUN / "closure.json"),
                      "invocation_sha256": sha(RUN / "invocation.json"), "raw": closure["raw"]},
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "raw_files": len(closure["raw"]),
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
