"""Index the sealed accepted E07 v1.0.1 raw files by byte length and SHA-256."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "e07-item-route-v101-20261001-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    files = ("native-input.json", "contract.json", "build.py", "exact-diff.json", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1", "validate_native.py", "author-validation-2026-10-01.json", "review/independent_readonly.py", "review/independent-readonly-2026-10-01.json")
    index = {"schema": "simlox-e07-item-route-evidence-index/v1", "case_id": "E07", "scope": "one item-specific record override on the E04 FAST station pair", "native_run_id": RUN.name, "local_path": str(RUN), "files_sha256": {name: sha(HERE / name) for name in files}, "invocation_sha256": sha(RUN / "invocation.json"), "closure_sha256": sha(RUN / "closure.json"), "sxo_sha256": sha(RUN / "model.sxo"), "raw": closure["raw"], "installed_executable_sha256": closure["source_hashes_before"]["simlox_exe"]}
    output = HERE / "evidence-index.json"
    output.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(sha(output))


if __name__ == "__main__":
    main()
