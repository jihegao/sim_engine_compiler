"""Seal K01.var04 source, review and accepted native artifacts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "k01-var04-duration-v100-ssh-20261004-01"
PARENT_RUN = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A01/a01-bound-final-20260927-03")
FILES = [
    "native-input.json", "contract.json", "exact-diff.json", "build.py",
    "check_roundtrip.py", "run_native_ssh.ps1", "validate_native.py",
    "make_evidence_index.py", "author-native-validation-2026-10-04.json",
    "README.md", "cli-scope-signoff-2026-10-04.md",
    "review/independent_replay.py", "review/independent-verdict.json",
    "review/static-review-2026-10-04.md",
]


def seal(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == RUN.name and closure["error"] is None
    assert closure["invocation_sha256"] == seal(RUN / "invocation.json")["sha256"]
    raw = {}
    for name, expected in closure["raw"].items():
        actual = seal(RUN / name)
        assert (actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"])
        raw[name] = actual
    result = {
        "schema": "simlox-k01-var04-evidence-index/v1",
        "case_id": "K01", "variant_id": "K01.var04", "version": "1.0.0",
        "publication_state": "candidate",
        "files": {name: seal(HERE / name) for name in FILES},
        "accepted_parent": {
            "input": seal(HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"),
            "closure": seal(PARENT_RUN / "closure.json"),
            "report": seal(PARENT_RUN / "report-raw.json"),
            "event_log": seal(PARENT_RUN / "model.log"),
        },
        "native_runs": {RUN.name: {"closure": seal(RUN / "closure.json"),
                                   "invocation": seal(RUN / "invocation.json"),
                                   "raw": raw}},
    }
    path = HERE / "evidence-index.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accepted_runs": 1, "accepted_raw_files": len(raw),
                      "evidence_index_sha256": seal(path)["sha256"]}))


if __name__ == "__main__":
    main()
