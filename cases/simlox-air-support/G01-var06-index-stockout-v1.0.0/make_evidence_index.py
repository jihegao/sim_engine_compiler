"""Build compact source/review and sealed native raw hash index for stockout scope."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/g01-var06-stockout-v100-ssh-20261001-01"
FILES = [
    "native-input.json", "contract.json", "build.py", "check_roundtrip.py",
    "run_native_ssh.ps1", "validate_native.py", "describe_diff.py", "exact-diff.json",
    "review/author-validation-2026-10-01.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json",
    "review/independent-static-review-2026-10-01.md",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    if closure.get("error") is not None:
        raise ValueError("closure error")
    for name, record in closure["raw"].items():
        path = RUN / name
        if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"raw seal differs: {name}")
    index = {
        "schema": "simlox-g01-var06-index-stockout-v100-evidence-index/v1",
        "case_id": "G01", "variant_id": "G01.var06", "version": "1.0.0",
        "scope": "one fixed-seed indexed similar-item shortage with unused other-index spare",
        "native_run_id": RUN.name, "local_path": str(RUN.resolve()),
        "files_sha256": {name: sha(HERE / name) for name in FILES},
        "invocation_sha256": sha(RUN / "invocation.json"),
        "closure_sha256": sha(RUN / "closure.json"),
        "sxo_sha256": sha(RUN / "model.sxo"),
        "raw": closure["raw"],
        "installed_executable_sha256": closure["source_hashes_after"]["simlox_exe"],
    }
    print(json.dumps(index, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
