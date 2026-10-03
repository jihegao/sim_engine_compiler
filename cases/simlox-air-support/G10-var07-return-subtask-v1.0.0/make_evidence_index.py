"""Verify both local raw closures and freeze the compact publication index."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("crew-present", "crew-absent")
FILES = [
    ".gitattributes", ".gitignore", "make_evidence_index.py",
    "native-input-crew-present.json", "native-input-crew-absent.json",
    "contract.json", "build.py", "describe_diff.py", "exact-diff.json",
    "check_roundtrip.py", "run_native_ssh.ps1", "validate_native.py",
    "review/author-validation-2026-10-03.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-03.json",
    "review/independent-static-review-2026-10-03.md",
    "cli-scope-signoff-2026-10-03.md", "README.md",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    author = read(HERE / "review/author-validation-2026-10-03.json")
    independent = read(HERE / "review/independent-readonly-2026-10-03.json")
    if not author["passed"] or not independent["passed"]:
        raise ValueError("acceptance replay failed")
    runs = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g10-var07-{arm}-v100-ssh-20261003-01"
        closure = read(run / "closure.json")
        if closure["error"] is not None or closure["arm"] != arm or len(closure["raw"]) != 13:
            raise ValueError(f"{arm} native closure not clean or raw set incomplete")
        for name, record in closure["raw"].items():
            path = run / name
            if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
                raise ValueError(f"{arm} raw seal differs: {name}")
        runs[arm] = {
            "run_id": run.name,
            "local_path": str(run.resolve()),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "sxo_sha256": sha(run / "model.sxo"),
            "raw": closure["raw"],
            "installed_executable_sha256": closure["source_hashes_after"]["simlox_exe"],
        }
    index = {
        "schema": "simlox-g10-var07-v100-evidence-index/v1",
        "case_id": "G10", "variant_id": "G10.var07", "version": "1.0.0",
        "scope": "paired first repair subtask started/not-started at h9 return, ACTIVE 1-of-2 continuous redundancy, seed1, one repetition, 36 hours",
        "files_sha256": {name: sha(HERE / name) for name in FILES},
        "runs": runs,
    }
    output = HERE / "evidence-index.json"
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output.exists():
        if output.read_bytes() != raw:
            raise ValueError("evidence index differs")
    else:
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(), "raw_files": sum(len(run["raw"]) for run in runs.values()), "author_checks": author["checks"], "independent_checks": independent["checks_passed"]}))


if __name__ == "__main__":
    main()
