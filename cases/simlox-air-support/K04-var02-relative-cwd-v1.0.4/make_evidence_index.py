"""Seal K04.var02 sources, guarded native output, reviews and excluded diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs" / "k04-var02-relative-cwd-v104-ssh-20261004-01"
PARENT = ROOT / "K04-var01-nested-mdb-include-v1.0.0"
PARENT_RUN = PARENT / "runs" / "k04-var01-nested-mdb-v100-ssh-20261004-01"
FILES = [".gitattributes", ".gitignore", "README.md", "build.py", "contract.json",
         "main-input.json", "level1-source.json", "level2-source.json", "run_native_ssh.ps1",
         "validate_native.py", "author-native-validation-2026-10-04.json",
         "make_evidence_index.py", "cli-scope-signoff-2026-10-04.md"]
DIAGNOSTICS = {
    "v1.0.0": ("k04-var02-relative-cwd-v100-ssh-20261004-01", "runner_automatic_args_parameter_error"),
    "v1.0.1": ("k04-var02-relative-cwd-v101-ssh-20261004-01", "alternate_cwd_did_not_fail_include"),
    "v1.0.2": ("k04-var02-relative-cwd-v102-ssh-20261004-01", "relocated_missing_mdb_child_stopped_after_modal_stall"),
    "v1.0.3": ("k04-var02-relative-cwd-v103-ssh-20261004-01", "contract_overclaimed_binary_sxo_equality"),
}


def seal(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def seal_run(path, accepted):
    closure = json.loads((path / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == path.name
    assert closure["invocation_sha256"] == seal(path / "invocation.json")["sha256"]
    if accepted:
        assert closure["error"] is None
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
    raw = {}
    for name, expected in closure["raw"].items():
        actual = seal(path / name)
        assert (actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"])
        raw[name] = actual
    return {"closure": seal(path / "closure.json"),
            "invocation": seal(path / "invocation.json"), "raw": raw,
            "closure_error": closure["error"]}


def main():
    review_files = sorted(path for path in (HERE / "review").rglob("*")
                          if path.is_file() and "__pycache__" not in path.parts)
    assert len(review_files) >= 3, "independent and static review absent"
    diagnostics = {}
    for version, (run_id, reason) in DIAGNOSTICS.items():
        path = ROOT / f"K04-var02-relative-cwd-{version}" / "runs" / run_id
        diagnostics[version] = {"exclusion_reason": reason, **seal_run(path, accepted=False)}
    data = {
        "schema": "simlox-k04-var02-relative-cwd-evidence-index/v1",
        "case_id": "K04", "variant_id": "K04.var02", "version": "1.0.4",
        "publication_state": "candidate_bounded_relative_top_level_mdb_cli_only",
        "files": {name: seal(HERE / name) for name in FILES},
        "review_files": {str(path.relative_to(HERE)).replace("\\", "/"): seal(path)
                         for path in review_files},
        "accepted_parent": {
            "main_input": seal(PARENT / "main-input.json"),
            "level1_source": seal(PARENT / "level1-source.json"),
            "level2_source": seal(PARENT / "level2-source.json"),
            "closure": seal(PARENT_RUN / "closure.json"),
            "event_log": seal(PARENT_RUN / "model.log"),
            "report": seal(PARENT_RUN / "report-raw.json"),
            "signoff": seal(PARENT / "cli-scope-signoff-2026-10-04.md"),
        },
        "manual": seal(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")),
        "accepted_native_run": seal_run(RUN, accepted=True),
        "excluded_diagnostics": diagnostics,
    }
    target = HERE / "evidence-index.json"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accepted_raw": len(data["accepted_native_run"]["raw"]),
                      "review_files": len(review_files),
                      "excluded_diagnostics": list(diagnostics),
                      "index_sha256": seal(target)["sha256"]}))


if __name__ == "__main__":
    main()
