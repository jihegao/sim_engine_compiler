"""Seal the read-only D01/E01 comparison without touching either native run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> dict:
    paths = {
        "contract": HERE / "contract.json",
        "contract_review": ROOT / "E01-var01-implicit-vs-explicit-v0.1.0" / "review" / "independent-contract-go-2026-10-06.md",
        "author_replay_source": HERE / "replay.py",
        "author_replay_result": HERE / "author-replay.json",
        "independent_replay_source": HERE / "review" / "independent_replay.py",
        "independent_replay_result": HERE / "review" / "independent-verdict.json",
        "independent_review": HERE / "review" / "independent-static-postrun-2026-10-06.md",
        "independent_verdict_git_bytes_rule": HERE / "review" / ".gitattributes",
        "readme": HERE / "README.md",
        "index_builder": HERE / "seal.py",
    }
    parents = {}
    for label, package, run_id in (
        ("implicit", "D01-installed-lru-direct-repair-v1.0.0", "d01-lru-v100-ssh-20260929-01"),
        ("explicit", "E01-local-spare-explicit-replacement-v1.0.0", "e01-v100-ssh-20260929-01"),
    ):
        parent = ROOT / package
        run = parent / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        raw = {name: {"bytes": value["bytes"], "sha256": value["sha256"]} for name, value in sorted(closure["raw"].items())}
        for name, seal in raw.items():
            if record(run / name) != seal:
                raise ValueError(f"raw mismatch: {label}/{name}")
        parents[label] = {
            "package": package,
            "run_id": run_id,
            "local_run_dir": str(run),
            "native_input": record(parent / "native-input.json"),
            "accepted_signoff": record(parent / "cli-scope-signoff-2026-09-29.md"),
            "invocation": record(run / "invocation.json"),
            "closure": record(run / "closure.json"),
            "raw": raw,
        }
    return {
        "schema": "simlox-issue18-derived-evidence-index/v1",
        "case_id": "E01",
        "variant_id": "E01.var01",
        "version": "1.0.0",
        "status": "native_behavior_accepted_cli_scope_ready_for_publication",
        "publication_state": "not_published",
        "evidence_mode": "read-only comparison of accepted D01 and E01 native runs; no new native process",
        "manual_sha256_inherited_from_accepted_parents": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
        "simlox_exe_sha256_in_accepted_invocations": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
        "source": {key: {"path": str(path.relative_to(ROOT)).replace("\\", "/"), **record(path)} for key, path in paths.items()},
        "parents": parents,
        "author_checks": 90,
        "independent_checks": 328,
        "limits": "one accepted fixed-seed implicit 15/15 versus explicit 10/20 contrast; explicitness and durations co-vary, so no isolated causal or general default-rule claim",
    }


if __name__ == "__main__":
    output = HERE / "evidence-index.json"
    output.write_bytes((json.dumps(main(), indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
    print(output)
