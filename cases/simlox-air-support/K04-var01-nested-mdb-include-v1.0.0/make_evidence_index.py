"""Seal K04 nested MDB sources, native closure, reviews, and parent chain."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs" / "k04-var01-nested-mdb-v100-ssh-20261004-01"
PARENT = ROOT / "K05-var05-runtime-mdb-include-v1.0.2"
PARENT_RUN = PARENT / "runs" / "k05-var05-mdb-v102-ssh-20261004-01"
K02_RUN = ROOT / "K02-var01-json-structure-v1.0.1" / "runs" / "k02-var01-named-v101-ssh-20261004-01"
SXI_DIAGNOSTIC = ROOT / "K04-var01-one-level-include-v1.0.0" / "runs" / "k04-var01-include-v100-ssh-20261004-01"
FILES = [
    ".gitattributes", ".gitignore", "README.md", "build.py", "contract.json",
    "create_level1_mdb_x86.ps1", "create_level2_mdb_x86.ps1",
    "main-input.json", "level1-source.json", "level2-source.json", "run_native_ssh.ps1",
    "validate_native.py", "author-native-validation-2026-10-04.json",
    "make_evidence_index.py", "cli-scope-signoff-2026-10-04.md",
]


def seal(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def seal_run(path, accepted):
    closure = json.loads((path / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == path.name
    if accepted:
        assert closure["error"] is None
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == seal(path / "invocation.json")["sha256"]
    raw = {}
    for name, expected in closure["raw"].items():
        actual = seal(path / name)
        assert (actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"])
        raw[name] = actual
    return {"closure": seal(path / "closure.json"),
            "invocation": seal(path / "invocation.json"), "raw": raw}


def main():
    review_files = sorted(path for path in (HERE / "review").rglob("*")
                          if path.is_file() and "__pycache__" not in path.parts)
    assert len(review_files) >= 3, "independent and static reviews absent"
    data = {
        "schema": "simlox-k04-var01-nested-mdb-evidence-index/v1",
        "case_id": "K04", "variant_id": "K04.var01", "version": "1.0.0",
        "publication_state": "candidate_bounded_nested_mdb_only",
        "files": {name: seal(HERE / name) for name in FILES},
        "review_files": {str(path.relative_to(HERE)).replace("\\", "/"): seal(path)
                         for path in review_files},
        "accepted_parent": {
            "main_input": seal(PARENT / "main-input.json"),
            "database_source": seal(PARENT / "database-source.json"),
            "closure": seal(PARENT_RUN / "closure.json"),
            "event_log": seal(PARENT_RUN / "model.log"),
            "report": seal(PARENT_RUN / "report-raw.json"),
            "signoff": seal(PARENT / "cli-scope-signoff-2026-10-04.md"),
        },
        "k02_behavior_ancestor": {
            "event_log": seal(K02_RUN / "model.log"),
            "report": seal(K02_RUN / "report-raw.json"),
        },
        "manual": seal(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")),
        "accepted_native_run": seal_run(RUN, accepted=True),
        "excluded_sparse_sxi_diagnostic": seal_run(SXI_DIAGNOSTIC, accepted=False),
    }
    target = HERE / "evidence-index.json"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accepted_raw": len(data["accepted_native_run"]["raw"]),
                      "review_files": len(review_files),
                      "index_sha256": seal(target)["sha256"]}))


if __name__ == "__main__":
    main()
