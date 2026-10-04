"""Seal accepted F04.var02 and excluded local pilot artifacts by raw SHA-256."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ACCEPTED = [
    HERE / "runs" / f"f04-var02-stochastic-v100-repeat-{arm}-ssh-20261004-01"
    for arm in ("a", "b")
]
EXCLUDED = [
    ROOT / "F04-var02-risk-pilot-v0.1.0" / "runs" /
    "f04-var02-risk-pilot-v010-ssh-20261004-01",
    ROOT / "F04-var02-risk-variance-pilot-v0.2.0" / "runs" /
    "f04-var02-risk-variance-v020-ssh-20261004-01",
]
FILES = [
    "native-input.json", "contract.json", "exact-diff.json",
    "build.py", "describe_diff.py", "make_report_settings.py",
    "check_roundtrip.py", "run_native_ssh.ps1", "validate_native.py",
    "make_evidence_index.py",
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
        "schema": "simlox-f04-stochastic-43day-evidence-index/v1",
        "case_id": "F04", "variant_id": "F04.var02", "version": "1.0.0",
        "publication_state": "candidate",
        "files": {name: seal(HERE / name) for name in FILES},
        "native_runs": {run.name: sealed_run(run) for run in ACCEPTED},
        "excluded_diagnostics": {
            run.name: {"reason": "one-rep mechanism or 32-rep variance diagnostic; excluded from final precision sample",
                       **sealed_run(run)}
            for run in EXCLUDED
        },
    }
    path = HERE / "evidence-index.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "accepted_runs": len(ACCEPTED),
        "accepted_raw_files": sum(len(data["raw"]) for data in result["native_runs"].values()),
        "excluded_runs": len(EXCLUDED),
        "excluded_raw_files": sum(len(data["raw"]) for data in result["excluded_diagnostics"].values()),
        "evidence_index_sha256": seal(path)["sha256"],
    }))


if __name__ == "__main__":
    main()
