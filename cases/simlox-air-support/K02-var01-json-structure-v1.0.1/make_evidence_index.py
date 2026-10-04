"""Seal accepted K02 named run, excluded probes and all frozen source/review files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "K02-var01-json-structure-v1.0.0"
PARENT = HERE.parent / "K01-var04-parent-child-model-diff-v1.0.0"
FILES = [
    ".gitattributes", ".gitignore", "build.py", "check_roundtrip.py",
    "contract.json", "exact-diff.json", "inactive2-input.json", "named-input.json",
    "run_native_ssh.ps1", "validate_native.py", "make_evidence_index.py",
    "author-native-validation-2026-10-04.json", "README.md",
    "cli-scope-signoff-2026-10-04.md", "review/independent_replay.py",
    "review/independent-verdict.json", "review/static-review-2026-10-04.md",
]
OLD_FILES = [
    ".gitattributes", ".gitignore", "build.py", "check_roundtrip.py",
    "contract.json", "exact-diff.json", "inactive-input.json", "named-input.json",
    "run_native_ssh.ps1", "README.md",
]
RUNS = {
    "accepted_named_v101": HERE / "runs" / "k02-var01-named-v101-ssh-20261004-01",
    "excluded_inactive2_v101": HERE / "runs" / "k02-var01-inactive2-v101-ssh-20261004-01",
    "excluded_inactive_index1_v100": OLD / "runs" / "k02-var01-inactive-v100-ssh-20261004-01",
    "excluded_named_strict_v100": OLD / "runs" / "k02-var01-named-v100-ssh-20261004-01",
}


def seal(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def seal_run(path):
    closure = json.loads((path / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == path.name
    assert closure["invocation_sha256"] == seal(path / "invocation.json")["sha256"]
    raw = {}
    for name, expected in closure["raw"].items():
        actual = seal(path / name)
        assert (actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"])
        raw[name] = actual
    return {"closure": seal(path / "closure.json"), "invocation": seal(path / "invocation.json"),
            "raw": raw, "closure_error": closure["error"]}


def main():
    data = {
        "schema": "simlox-k02-var01-json-structure-evidence-index/v1",
        "case_id": "K02", "variant_id": "K02.var01", "version": "1.0.1",
        "publication_state": "candidate_named_only",
        "files": {name: seal(HERE / name) for name in FILES},
        "excluded_v100_source_files": {name: seal(OLD / name) for name in OLD_FILES},
        "accepted_parent": {
            "source": seal(PARENT / "native-input.json"),
            "signoff": seal(PARENT / "cli-scope-signoff-2026-10-04.md"),
            "closure": seal(PARENT / "runs" / "k01-var04-duration-v100-ssh-20261004-01" / "closure.json"),
            "report": seal(PARENT / "runs" / "k01-var04-duration-v100-ssh-20261004-01" / "report-raw.json"),
            "event_log": seal(PARENT / "runs" / "k01-var04-duration-v100-ssh-20261004-01" / "model.log"),
        },
        "native_runs": {name: seal_run(path) for name, path in RUNS.items()},
    }
    assert data["native_runs"]["accepted_named_v101"]["closure_error"] is None
    assert all(data["native_runs"][name]["closure_error"] is not None for name in RUNS if name != "accepted_named_v101")
    target = HERE / "evidence-index.json"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accepted_raw": len(data["native_runs"]["accepted_named_v101"]["raw"]),
                      "excluded_raw": sum(len(data["native_runs"][name]["raw"]) for name in RUNS if name != "accepted_named_v101"),
                      "index_sha256": seal(target)["sha256"]}))


if __name__ == "__main__":
    main()
