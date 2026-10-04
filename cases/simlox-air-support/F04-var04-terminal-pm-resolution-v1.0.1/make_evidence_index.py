"""Seal accepted F04.var04 and excluded diagnostic artifacts by raw SHA-256."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ACCEPTED = HERE / "runs" / "f04-var04-terminal-pm-v101-ssh-20261004-01"
EXCLUDED_PACKAGE = ROOT / "F04-var04-terminal-pm-resolution-v1.0.0"
EXCLUDED = EXCLUDED_PACKAGE / "runs" / "f04-var04-terminal-pm-v100-ssh-20261004-01"
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


def sealed_run(run: Path) -> dict:
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == run.name and closure["error"] is None
    assert closure["invocation_sha256"] == seal(run / "invocation.json")["sha256"]
    raw = {}
    for name, expected in closure["raw"].items():
        actual = seal(run / name)
        assert (actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"])
        raw[name] = actual
    return {"closure": seal(run / "closure.json"),
            "invocation": seal(run / "invocation.json"), "raw": raw}


def main() -> None:
    result = {
        "schema": "simlox-f04-terminal-pm-evidence-index/v1",
        "case_id": "F04", "variant_id": "F04.var04", "version": "1.0.1",
        "publication_state": "candidate",
        "files": {name: seal(HERE / name) for name in FILES},
        "native_runs": {ACCEPTED.name: sealed_run(ACCEPTED)},
        "excluded_diagnostics": {
            EXCLUDED.name: {
                "reason": "Exact System prefix and exact-zero new-bin hypothesis failed; event-resolution observation retained only as diagnostic.",
                "source": {
                    name: seal(EXCLUDED_PACKAGE / name)
                    for name in ("native-input.json", "contract.json", "exact-diff.json")
                },
                **sealed_run(EXCLUDED),
            }
        },
    }
    path = HERE / "evidence-index.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "accepted_runs": 1, "accepted_raw_files": len(result["native_runs"][ACCEPTED.name]["raw"]),
        "excluded_runs": 1, "excluded_raw_files": len(result["excluded_diagnostics"][EXCLUDED.name]["raw"]),
        "evidence_index_sha256": seal(path)["sha256"],
    }))


if __name__ == "__main__":
    main()
