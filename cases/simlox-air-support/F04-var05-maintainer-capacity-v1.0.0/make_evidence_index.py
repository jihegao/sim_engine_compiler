"""Seal accepted F04.var05 source, replay and native artifacts by SHA-256."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "f04-var05-maintainer-capacity-v100-ssh-20261004-01"
FILES = [
    "native-input.json", "contract.json", "exact-diff.json",
    "build.py", "describe_diff.py", "check_roundtrip.py",
    "run_native_ssh.ps1", "validate_native.py", "make_evidence_index.py",
    "author-native-validation-2026-10-04.json", "README.md",
    "cli-scope-signoff-2026-10-04.md",
    "review/static-review-2026-10-04.md",
    "review/independent_replay.py", "review/independent-verdict.json",
]


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> None:
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == RUN.name and closure["error"] is None
    assert closure["invocation_sha256"] == seal(RUN / "invocation.json")["sha256"]
    raw = {}
    for name, expected in closure["raw"].items():
        actual = seal(RUN / name)
        assert (actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"])
        raw[name] = actual
    result = {
        "schema": "simlox-f04-maintainer-capacity-evidence-index/v1",
        "case_id": "F04", "variant_id": "F04.var05", "version": "1.0.0",
        "publication_state": "candidate",
        "files": {name: seal(HERE / name) for name in FILES},
        "native_runs": {
            RUN.name: {"closure": seal(RUN / "closure.json"),
                       "invocation": seal(RUN / "invocation.json"), "raw": raw}
        },
    }
    path = HERE / "evidence-index.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accepted_runs": 1, "accepted_raw_files": len(raw),
                      "evidence_index_sha256": seal(path)["sha256"]}))


if __name__ == "__main__":
    main()
