"""Freeze D07.var03 source and ignored native-run evidence hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "d07-var03-same-key-v100-ssh-20261003-01"
RUN = HERE / "runs" / RUN_ID
OUTPUT = HERE / "evidence-index.json"
FILES = [
    ".gitignore",
    ".gitattributes",
    "README.md",
    "build.py",
    "native-input.json",
    "contract.json",
    "describe_diff.py",
    "parent-diff.json",
    "check_roundtrip.py",
    "run_native_ssh.ps1",
    "validate_native.py",
    "make_evidence_index.py",
    "review/author-validation-2026-10-03.json",
    "review/independent_readonly.py",
    "review/independent-readonly-2026-10-03.json",
    "cli-scope-signoff-2026-10-03.md",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    if closure["error"] is not None or closure["source_hashes_before"] != closure["source_hashes_after"]:
        raise ValueError("native closure failed")
    for name, seal in closure["raw"].items():
        path = RUN / name
        if not path.is_file() or path.stat().st_size != seal["bytes"] or sha(path) != seal["sha256"]:
            raise ValueError(f"raw evidence changed: {name}")
    return {
        "schema": "simlox-d07-var03-v100-evidence-index/v1",
        "case_id": "D07",
        "variant_id": "D07.var03",
        "version": "1.0.0",
        "scope": "both system and installed-item optional OPHOURS FRT100000 override base FRT300000 while matched KM5000 per million remains at 60 KM/hour; fixed-seed same-key precedence only",
        "native_run_id": RUN_ID,
        "local_path": str(RUN.resolve()),
        "files_sha256": {name: sha(HERE / name) for name in FILES},
        "invocation_sha256": sha(RUN / "invocation.json"),
        "closure_sha256": sha(RUN / "closure.json"),
        "raw": closure["raw"],
        "source_hashes": closure["source_hashes_before"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.write:
        OUTPUT.write_text(raw, encoding="utf-8")
    elif OUTPUT.read_text(encoding="utf-8") != raw:
        raise ValueError("evidence index differs")
    print(json.dumps({"variant_id": "D07.var03", "evidence_index_sha256": sha(OUTPUT)}))


if __name__ == "__main__":
    main()
