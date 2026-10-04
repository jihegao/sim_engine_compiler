"""Seal the K04.var03 time-bounded missing-MDB diagnostic and reviews."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs" / "k04-var03-missing-mdb-v100-ssh-20261004-01"
PARENT = ROOT / "K04-var02-relative-cwd-v1.0.4"
PARENT_RUN = PARENT / "runs" / "k04-var02-relative-cwd-v104-ssh-20261004-01"
FILES = [".gitattributes", ".gitignore", "README.md", "contract.json",
         "run_native_ssh.ps1", "validate_diagnostic.py",
         "author-diagnostic-validation-2026-10-04.json",
         "capability-limit-2026-10-04.md", "make_diagnostic_index.py"]


def seal(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    observation = json.loads((RUN / "observation.json").read_text(encoding="utf-8-sig"))
    assert closure["error"] is None
    assert closure["outcome"] == observation["outcome"] == "watchdog_terminated_after_45_seconds"
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == seal(RUN / "invocation.json")["sha256"]
    raw = {}
    for name, expected in closure["raw"].items():
        actual = seal(RUN / name)
        assert (actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"])
        raw[name] = actual
    assert len(raw) == 5
    review_files = sorted(path for path in (HERE / "review").rglob("*")
                          if path.is_file() and "__pycache__" not in path.parts)
    assert len(review_files) >= 3
    data = {
        "schema": "simlox-k04-var03-missing-mdb-diagnostic-index/v1",
        "case_id": "K04", "variant_id": "K04.var03", "version": "1.0.0",
        "publication_state": "diagnostic_not_reusable_published",
        "classification": "cli_noncompletion_through_45_seconds_watchdog_stopped",
        "files": {name: seal(HERE / name) for name in FILES},
        "review_files": {str(path.relative_to(HERE)).replace("\\", "/"): seal(path)
                         for path in review_files},
        "accepted_parent": {
            "model_sxi": seal(PARENT_RUN / "model.sxi"),
            "level1_mdb": seal(PARENT_RUN / "level1.mdb"),
            "closure": seal(PARENT_RUN / "closure.json"),
            "signoff": seal(PARENT / "cli-scope-signoff-2026-10-04.md"),
            "positive_event": seal(PARENT_RUN / "positive-model.log"),
            "positive_report": seal(PARENT_RUN / "positive-report-raw.json"),
        },
        "manual": seal(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")),
        "diagnostic_native_run": {
            "closure": seal(RUN / "closure.json"),
            "invocation": seal(RUN / "invocation.json"),
            "observation": seal(RUN / "observation.json"),
            "raw": raw,
        },
    }
    target = HERE / "diagnostic-evidence-index.json"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"raw": len(raw), "review_files": len(review_files),
                      "index_sha256": seal(target)["sha256"]}))


if __name__ == "__main__":
    main()
