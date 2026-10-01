"""Build compact hashes for paired G01.var06 sources, reviews and sealed raw runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = [
    "native-identical.json", "native-similar.json", "contract.json", "build.py",
    "check_roundtrip.py", "run_native_ssh.ps1", "validate_native.py",
    "describe_diff.py", "exact-diff.json",
    "review/author-validation-2026-10-01.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json",
    "review/independent-static-review-2026-10-01.md",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    runs = {}
    for kind in ("identical", "similar"):
        run = HERE / "runs" / f"g01-var06-{kind}-v101-ssh-20261001-01"
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        if closure.get("error") is not None:
            raise ValueError(f"{kind} closure error")
        for name, record in closure["raw"].items():
            path = run / name
            if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
                raise ValueError(f"{kind} raw seal differs: {name}")
        runs[kind] = {
            "native_run_id": run.name, "local_path": str(run.resolve()),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "sxo_sha256": sha(run / "model.sxo"),
            "raw": closure["raw"],
            "installed_executable_sha256": closure["source_hashes_after"]["simlox_exe"],
        }
    index = {
        "schema": "simlox-g01-var06-v101-evidence-index/v1",
        "case_id": "G01", "variant_id": "G01.var06", "version": "1.0.1",
        "scope": "one fixed-seed QTYPM2 versus NSIMI2 native indexed-stock contrast",
        "files_sha256": {name: sha(HERE / name) for name in FILES},
        "runs": runs,
    }
    print(json.dumps(index, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
