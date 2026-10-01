"""Build a compact hash index for the locally sealed G01.var01 raw run."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/g01-var01-v101-ssh-20261001-01"
FILES = [
    "native-input.json", "contract.json", "build.py", "check_roundtrip.py",
    "run_native_ssh.ps1", "validate_native.py", "describe_diff.py",
    "exact-diff.json", "review/author-validation-2026-10-01.json",
    "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    for name, record in closure["raw"].items():
        path = RUN / name
        if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"raw seal differs: {name}")
    index = {
        "schema": "simlox-g01-var01-v101-evidence-index/v1",
        "case_id": "G01", "variant_id": "G01.var01", "version": "1.0.1",
        "scope": "one local traditional LRU/SRU replacement and direct SRU repair chain",
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
