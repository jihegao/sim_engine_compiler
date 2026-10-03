"""Check local D07.var04 raw seals and freeze bounded rejection evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/d07-var04-child-frt-v100-ssh-20261003-01"
OUTPUT = HERE / "evidence-index.json"
FILES = [
    ".gitattributes", ".gitignore", "README.md", "build.py", "native-input.json",
    "contract.json", "describe_diff.py", "parent-diff.json", "check_roundtrip.py",
    "run_native_ssh.ps1", "validate_rejection.py", "make_evidence_index.py",
    "review/author-rejection-validation-2026-10-03.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-03.json",
    "cli-scope-signoff-2026-10-03.md",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build() -> dict:
    closure = read(RUN / "closure.json")
    if closure["error"] is not None or closure["source_hashes_before"] != closure["source_hashes_after"] or len(closure["raw"]) != 9:
        raise ValueError("native closure not clean or raw set incomplete")
    for name, record in closure["raw"].items():
        path = RUN / name
        if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"raw seal differs: {name}")
    author = read(HERE / "review/author-rejection-validation-2026-10-03.json")
    independent = read(HERE / "review/independent-readonly-2026-10-03.json")
    if not author["passed"] or not independent["passed"]:
        raise ValueError("acceptance replay failed")
    return {
        "schema": "simlox-d07-var04-v100-evidence-index/v1",
        "case_id": "D07", "variant_id": "D07.var04", "version": "1.0.0",
        "scope": "one installed LRU KM FRT10000 exceeds mother system KM FRT5000; native converter error #2041 only",
        "native_run_id": RUN.name, "local_path": str(RUN.resolve()),
        "files_sha256": {name: sha(HERE / name) for name in FILES},
        "invocation_sha256": sha(RUN / "invocation.json"),
        "closure_sha256": sha(RUN / "closure.json"),
        "sxo_sha256": sha(RUN / "model.sxo"),
        "raw": closure["raw"],
        "source_hashes": closure["source_hashes_before"],
        "author_checks": author["checks_passed"],
        "independent_checks": independent["checks_passed"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("evidence index differs")
    print(json.dumps({"index_sha256": sha(OUTPUT)}))


if __name__ == "__main__":
    main()
