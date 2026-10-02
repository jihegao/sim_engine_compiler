"""Publish hashes for the local negative native diagnostic without copying raw files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "d14-var04-position-monit-y-v100-ssh-20261002-01"
OUT = HERE / "evidence-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    source = {}
    for name in ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
                 "validate_rejection.py", "contract.json", "exact-diff.json", "native-input.json",
                 "author-validation.json", "independent_replay.py", "independent-verdict.json"):
        path = HERE / name
        if not path.is_file():
            raise FileNotFoundError(path)
        source[name] = {"sha256": sha(path), "bytes": path.stat().st_size}
    folder = HERE / "runs" / RUN_ID
    closure = json.loads((folder / "closure.json").read_text(encoding="utf-8-sig"))
    if closure["error"] is not None or closure["run_id"] != RUN_ID or closure["arm"] != "position-monit-y":
        raise ValueError("diagnostic closure rejected")
    raw = {}
    for name, entry in closure["raw"].items():
        path = folder / name
        if sha(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            raise ValueError(f"raw seal mismatch: {name}")
        raw[name] = entry
    doc = {"schema": "simlox-d14-var04-evidence-index/v1", "case_id": "D14",
           "variant_id": "D14.var04", "version": "1.0.0", "publication_state": "not_published",
           "source": source, "manual_sha256": contract["source"]["manual_sha256"],
           "dictionary_sha256": contract["source"]["dictionary_sha256"],
           "accepted_parent": contract["accepted_parent"],
           "run": {"run_id": RUN_ID, "local_directory": str(folder.resolve()),
                   "input_sha256": contract["input_sha256"],
                   "invocation_sha256": sha(folder / "invocation.json"),
                   "closure_sha256": sha(folder / "closure.json"), "raw": raw},
           "scope": "exact converter error #361; no valid simulation output; local native files remain ignored"}
    encoded = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes() != encoded:
            raise ValueError("frozen evidence index differs")
    else:
        OUT.write_bytes(encoded)
    print(json.dumps({"evidence_index_sha256": hashlib.sha256(encoded).hexdigest(),
                      "raw_records": len(raw)}))


if __name__ == "__main__":
    main()
