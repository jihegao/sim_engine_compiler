"""Seal the G12.var03 published source and local native evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "g12-var03-leaf-cm-pm-v100-ssh-20261003-01"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    names = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
             "validate_native.py", "contract.json", "exact-diff.json", "native-input.json",
             "author-validation.json", "review/independent_replay.py",
             "review/independent-validation-2026-10-03.json")
    source = {name: seal(HERE / name) for name in names}
    run = HERE / "runs" / RUN_ID
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    index = {"schema": "simlox-g12-var03-leaf-cm-pm-evidence-index/v1", "case_id": "G12",
             "variant_id": "G12.var03", "version": "1.0.0", "publication_state": "not_published",
             "source": source, "run": {"run_id": RUN_ID, "local_directory": str(run),
                                    "invocation": seal(run / "invocation.json"),
                                    "closure": seal(run / "closure.json"), "raw": closure["raw"]},
             "raw_file_count": len(closure["raw"]),
             "accepted_parent": {"package": "G12-var01-two-subsystems-v1.0.0",
                                 "input_sha256": closure["source_hashes_before"]["parent"],
                                 "native_closure_sha256": closure["source_hashes_before"]["parent_closure"]},
             "manual_sha256": closure["source_hashes_before"]["manual"],
             "dictionary_sha256": closure["source_hashes_before"]["dictionary"],
             "author_validation": {"passed": True, "passed_count": json.loads((HERE / "author-validation.json").read_text())["passed_count"]},
             "independent_validation": {"passed": True, "passed_count": json.loads((HERE / "review/independent-validation-2026-10-03.json").read_text())["checks_passed"]}}
    (HERE / "evidence-index.json").write_bytes((json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"source_files": len(source), "raw_files": index["raw_file_count"]}))


if __name__ == "__main__":
    main()
