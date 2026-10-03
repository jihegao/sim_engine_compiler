"""Verify local raw seals and build the compact publication evidence index."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/g10-var06-online-repair-v100-ssh-20261003-01"
FILES = [
    ".gitattributes", ".gitignore", "make_evidence_index.py",
    "native-input.json", "contract.json", "build.py", "describe_diff.py", "exact-diff.json",
    "check_roundtrip.py", "run_native_ssh.ps1", "validate_native.py",
    "review/author-validation-2026-10-03.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-03.json",
    "review/independent-static-review-2026-10-03.md",
    "cli-scope-signoff-2026-10-03.md", "README.md",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    if closure["error"] is not None or len(closure["raw"]) != 13:
        raise ValueError("native closure not clean or raw set incomplete")
    for name, record in closure["raw"].items():
        path = RUN / name
        if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"raw seal differs: {name}")
    author = json.loads((HERE / "review/author-validation-2026-10-03.json").read_text(encoding="utf-8-sig"))
    independent = json.loads((HERE / "review/independent-readonly-2026-10-03.json").read_text(encoding="utf-8-sig"))
    if not author["passed"] or not independent["passed"]:
        raise ValueError("acceptance replay failed")
    index = {
        "schema": "simlox-g10-var06-v100-evidence-index/v1",
        "case_id": "G10", "variant_id": "G10.var06", "version": "1.0.0",
        "scope": "ACTIVE 1-of-2 traditional LRU on-mission repair, one continuous mission, seed1, one repetition, 36 hours",
        "native_run_id": RUN.name, "local_path": str(RUN.resolve()),
        "files_sha256": {name: sha(HERE / name) for name in FILES},
        "invocation_sha256": sha(RUN / "invocation.json"),
        "closure_sha256": sha(RUN / "closure.json"),
        "sxo_sha256": sha(RUN / "model.sxo"),
        "raw": closure["raw"],
        "installed_executable_sha256": closure["source_hashes_after"]["simlox_exe"],
    }
    output = HERE / "evidence-index.json"
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output.exists():
        if output.read_bytes() != raw:
            raise ValueError("evidence index differs")
    else:
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(), "raw_files": len(closure["raw"]), "author_checks": author["checks"], "independent_checks": independent["checks_passed"]}))


if __name__ == "__main__":
    main()
