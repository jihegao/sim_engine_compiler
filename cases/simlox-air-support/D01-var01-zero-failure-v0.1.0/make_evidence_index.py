"""Seal D01.var01 reviewed source and accepted parent/child raw evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "evidence-index.json"
RUNS = (
    ("parent", ROOT / "D01-installed-lru-direct-repair-v1.0.0" / "runs" / "d01-lru-v100-ssh-20260929-01",
     "3642d558e98abd31f4510e213286182f9ce0d6eda0a86f6185c64f439f7e79f0"),
    ("child", HERE / "runs" / "d01-var01-zero-v010-ssh-20261006-01",
     "a0e396e3cb454e35471fa25625d5adbaee89cdfe402f50a6b8412cb01f5d11fb"),
)
LINEAGE = (
    ("accepted_parent", "D01", ROOT / "D01-installed-lru-direct-repair-v1.0.0" / "cli-scope-signoff-2026-09-29.md",
     "e2c567a5db6b1af672fa279b448b36ff43ed68a90c2c529bdf5506ed2cd39832"),
    ("instructional_prerequisite", "A02", ROOT / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md",
     "608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e"),
    ("zero_rate_warning_precedent", "H02.var01", ROOT / "H02-var01-primary-lru-damage-v1.0.0" / "cli-scope-signoff-2026-10-02.md",
     "2cbf6b91ad08106fe97fd7c928f1c3f0ca2c154228d1b0b15baf7e45ecbebaec"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = []
    for path in sorted(HERE.rglob("*")):
        if (not path.is_file() or path in (OUTPUT, HERE / "cli-scope-signoff-2026-10-06.md")
                or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc"):
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "bytes": path.stat().st_size,
                       "sha256": sha(path)})
    lineage = []
    for role, case_id, path, expected in LINEAGE:
        assert sha(path) == expected, path
        lineage.append({"role": role, "case_id": case_id, "signoff_path": str(path.resolve()),
                        "signoff_bytes": path.stat().st_size, "signoff_sha256": expected})
    runs = []
    for role, run, expected in RUNS:
        closure_path, invocation_path = run / "closure.json", run / "invocation.json"
        assert sha(closure_path) == expected, closure_path
        closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run.name and closure["invocation_sha256"] == sha(invocation_path)
        assert closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"]
        assert len(closure["raw"]) == 12
        for name, seal in closure["raw"].items():
            path = run / name
            assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], path
        runs.append({"role": role, "run_id": run.name, "local_run_dir": str(run.resolve()),
                     "invocation": {"bytes": invocation_path.stat().st_size, "sha256": sha(invocation_path)},
                     "closure": {"bytes": closure_path.stat().st_size, "sha256": expected}, "raw": closure["raw"]})
    original = json.loads((HERE / "review" / "author-validation-v011.json").read_text(encoding="utf-8-sig"))
    corrected = json.loads((HERE / "review" / "author-validation-v012.json").read_text(encoding="utf-8-sig"))
    independent = json.loads((HERE / "review" / "independent-verdict.json").read_text(encoding="utf-8-sig"))
    assert original["passed"] is False and original["checks"] == 54 and original["differences"] == ["bound validate_native_cli.py"]
    assert corrected["passed"] is True and corrected["checks"] == 54 and corrected["differences"] == []
    assert independent["verdict"] == "GO_BOUNDED" and independent["checks"] == independent["passed_checks"] == 496
    index = {
        "schema": "simlox-d01-var01-v010-evidence-index/v1", "case_id": "D01", "variant_id": "D01.var01",
        "version": "0.1.0", "status": "native_behavior_accepted_cli_scope_ready_for_publication",
        "publication_state": "not_published", "source": source, "lineage": lineage,
        "accepted_runs": runs, "accepted_raw_count": 24,
        "author_original_result": "failed_53_of_54_preserved", "author_corrected_checks": 54,
        "independent_checks": 496,
        "scope": "one seeded matched System/Item zero-FRT control with three successful two-hour missions and one unissued physical local spare",
        "limits": "Both FRTs changed together; one seed and executable; no independent field isolation, other failure mechanisms, general reliability, GUI visual, cross-engine or full D01/Issue18 claim. Terminal physical stock is inferred from opening ID0 and no stock transition, not PNB.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": 24,
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
