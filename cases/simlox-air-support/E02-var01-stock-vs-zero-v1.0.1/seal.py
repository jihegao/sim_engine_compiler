"""Create a deterministic index of the existing E02.var01 comparison evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def record(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> dict:
    source_paths = {
        "reviewed_contract": HERE / "contract.json",
        "author_replay_source": HERE / "replay.py",
        "author_replay_result": HERE / "author-replay.json",
        "independent_replay_source": HERE / "review" / "independent_replay.py",
        "independent_replay_result": HERE / "review" / "independent-replay.json",
        "independent_review": HERE / "review" / "independent-static-postrun-2026-10-06.md",
        "readme": HERE / "README.md",
        "index_builder": HERE / "seal.py",
        "original_no_go_contract": ROOT / "E02-var01-stock-vs-zero-v0.1.0" / "contract.json",
        "original_no_go_review": ROOT / "E02-var01-stock-vs-zero-v0.1.0" / "review" / "independent-contract-no-go-2026-10-06.md",
        "corrected_contract_go_review": ROOT / "E02-var01-stock-vs-zero-v0.1.1" / "review" / "independent-contract-go-2026-10-06.md",
        "original_failed_replay_source": ROOT / "E02-var01-stock-vs-zero-v1.0.0" / "replay.py",
        "original_failed_replay_result_raw_bytes": ROOT / "E02-var01-stock-vs-zero-v1.0.0" / "review" / "author-replay-failed.json",
        "original_failed_replay_diagnostic": ROOT / "E02-var01-stock-vs-zero-v1.0.0" / "review" / "author-replay-failure-2026-10-06.md",
    }
    parents = {}
    for label, package, run_id in (
        ("stock_one", "E01-local-spare-explicit-replacement-v1.0.0", "e01-v100-ssh-20260929-01"),
        ("stock_zero", "E02-zero-stock-local-backorder-v1.0.0", "e02-v100-ssh-20260929-01"),
    ):
        parent = ROOT / package
        run = parent / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        parents[label] = {
            "package": package,
            "run_id": run_id,
            "local_run_dir": str(run),
            "native_input": record(parent / "native-input.json"),
            "accepted_signoff": record(parent / "cli-scope-signoff-2026-09-29.md"),
            "closure": record(run / "closure.json"),
            "invocation": record(run / "invocation.json"),
            "raw": {name: {"bytes": info["bytes"], "sha256": info["sha256"]} for name, info in sorted(closure["raw"].items())},
        }
        for name, info in parents[label]["raw"].items():
            if record(run / name) != info:
                raise ValueError(f"raw seal mismatch: {label}/{name}")
    return {
        "schema": "simlox-issue18-derived-evidence-index/v1",
        "case_id": "E02",
        "variant_id": "E02.var01",
        "version": "1.0.1",
        "status": "native_behavior_accepted_cli_scope_ready_for_publication",
        "publication_state": "not_published",
        "evidence_mode": "read-only comparison of two accepted native runs; no new native process or source model",
        "manual_sha256_inherited_from_accepted_parents": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
        "simlox_exe_sha256_in_accepted_invocations": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
        "e05_prerequisite_signoff": record(ROOT / "E05-local-repair-reissue-v1.0.0" / "cli-scope-signoff-2026-09-29.md"),
        "source": {key: {"path": str(path.relative_to(ROOT)).replace("\\", "/"), **record(path)} for key, path in source_paths.items()},
        "parents": parents,
        "author_checks": 88,
        "independent_checks": 574,
        "limits": "one fixed-seed CLI contrast; original failed snapshots excluded; no new native behavior, GUI visual or cross-engine claim",
    }


if __name__ == "__main__":
    output = HERE / "evidence-index.json"
    output.write_bytes((json.dumps(main(), indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
    print(output)
