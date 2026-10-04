"""Seal accepted K03 delimited-text reimport and its native source chain."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "K03-var01-cli-text-export-v1.0.1"
PARENT_RUN = PARENT / "runs" / "k03-var01-text-v101-ssh-20261004-01"
K02_RUN = HERE.parent / "K02-var01-json-structure-v1.0.1" / "runs" / "k02-var01-named-v101-ssh-20261004-01"
RUN = HERE / "runs" / "k03-var01-reimport-v100-ssh-20261004-01"
FILES = [
    ".gitattributes", ".gitignore", "contract.json", "run_native_ssh.ps1",
    "validate_native.py", "make_evidence_index.py",
    "author-native-validation-2026-10-04.json", "README.md",
    "cli-scope-signoff-2026-10-04.md", "review/independent_replay.py",
    "review/independent-verdict.json", "review/static-review-2026-10-04.md",
]


def seal(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def seal_run(path):
    closure = json.loads((path / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == path.name and closure["error"] is None
    assert closure["invocation_sha256"] == seal(path / "invocation.json")["sha256"]
    raw = {}
    for name, expected in closure["raw"].items():
        actual = seal(path / name)
        assert (actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"])
        raw[name] = actual
    return {"closure": seal(path / "closure.json"), "invocation": seal(path / "invocation.json"), "raw": raw}


def main():
    data = {
        "schema": "simlox-k03-var01-text-reimport-evidence-index/v1",
        "case_id": "K03", "variant_id": "K03.var01", "version": "1.0.0",
        "publication_state": "candidate_bounded_reimport_only",
        "files": {name: seal(HERE / name) for name in FILES},
        "accepted_parent": {
            "text": seal(PARENT_RUN / "model.txt"),
            "json_export": seal(PARENT_RUN / "model-raw.json"),
            "closure": seal(PARENT_RUN / "closure.json"),
            "signoff": seal(PARENT / "cli-scope-signoff-2026-10-04.md"),
        },
        "k02_behavior_parent": {
            "event_log": seal(K02_RUN / "model.log"),
            "report": seal(K02_RUN / "report-raw.json"),
        },
        "manual": seal(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")),
        "native_run": seal_run(RUN),
    }
    target = HERE / "evidence-index.json"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"raw": len(data["native_run"]["raw"]), "index_sha256": seal(target)["sha256"]}))


if __name__ == "__main__":
    main()
