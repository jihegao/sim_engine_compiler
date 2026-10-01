"""Index the immutable E07 v1.0.0 failed-roundtrip diagnostic."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "e07-item-route-v100-20261001-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    files = ("native-input.json", "contract.json", "build.py", "exact-diff.json", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1")
    index = {"schema": "simlox-e07-failed-roundtrip-diagnostic-index/v1", "case_id": "E07", "publication_state": "not_published", "reason": "native export inserts null ItemStationStructure.CFRMS/CTOMS columns absent in authored v1.0.0 input; exact roundtrip failed", "native_run_id": RUN.name, "local_path": str(RUN), "files_sha256": {name: sha(HERE / name) for name in files}, "invocation_sha256": sha(RUN / "invocation.json"), "closure_sha256": sha(RUN / "closure.json"), "sxo_sha256": sha(RUN / "model.sxo"), "raw": closure["raw"]}
    output = HERE / "diagnostic-evidence-index.json"
    output.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(sha(output))


if __name__ == "__main__":
    main()
