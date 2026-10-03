"""Seal accepted F02 paired source and local raw runs without publishing raw files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import SOURCES
from validate_native import RUNS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
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
    assert sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"]
    for arm, key in (("deterministic", "F02.var01_deterministic"), ("risk", "F02.var02_risk")):
        assert sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][key]
    for name, (relative, digest) in SOURCES.items():
        assert sha(ROOT / relative) == digest == contract["accepted_inputs"][name]
    source = []
    for path in sorted(HERE.rglob("*")):
        if (not path.is_file() or path == OUT or "runs" in path.parts or "__pycache__" in path.parts
                or path.suffix == ".pyc" or path.name.startswith("cli-scope-signoff-")):
            continue
        source.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    runs = []
    for arm, run_id in RUNS.items():
        run = HERE / "runs" / run_id
        closure = load(run / "closure.json")
        assert closure["run_id"] == run_id and closure["error"] is None
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
        assert closure["invocation_sha256"] == sha(run / "invocation.json")
        assert len(closure["raw"]) == 12
        for name, meta in closure["raw"].items():
            path = run / name
            assert path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
        runs.append({"arm": arm, "state": "accepted_candidate", "run_id": run_id,
                     "local_path": str(run.resolve()), "closure_sha256": sha(run / "closure.json"),
                     "invocation_sha256": sha(run / "invocation.json"), "raw": closure["raw"]})
    out = {"schema": "simlox-f02-paired-evidence-index/v1", "case_id": "F02",
           "variant_ids": ["F02.var01", "F02.var02"], "version": "1.0.2",
           "publication_state": "not_published", "source": source, "runs": runs,
           "excluded_diagnostics": [
               {"package": f"F02-var01-var02-integrated-fleet-v1.0.{v}",
                "diagnostic_sha256": sha(ROOT / f"F02-var01-var02-integrated-fleet-v1.0.{v}" / "diagnostic.json")}
               for v in (0, 1)],
           "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode()
    OUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "raw_files": sum(len(r["raw"]) for r in runs),
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
