"""Seal published I05 source files and local native raw evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def entry(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(HERE / "contract.json")
    run = HERE / "runs" / contract["run_id"]
    closure = load(run / "closure.json")
    assert closure["run_id"] == contract["run_id"] and closure["error"] is None
    assert entry(run / "invocation.json")["sha256"] == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 22
    for name, seal in closure["raw"].items():
        assert entry(run / name) == seal, name
    sources = [
        ".gitattributes", ".gitignore", "build.py", "contract.json", "run_native_ssh.ps1",
        "control-input.json", "change-input.json", "validate.py",
        "make_evidence_index.py", "review/preflight-2026-10-05.md",
        "review/author-validation-2026-10-05.json", "review/independent_replay.py",
        "review/independent-verdict.json", "cli-scope-signoff-2026-10-05.md", "README.md",
    ]
    result = {
        "schema": "simlox-i05-prep-change-evidence-index/v1",
        "case_id": "I05", "variant_id": "I05.var06", "version": "1.0.0",
        "publication_state": "not_published",
        "source": {name: entry(HERE / name) for name in sources},
        "run": {"run_id": contract["run_id"], "local_directory": str(run),
                "invocation": entry(run / "invocation.json"),
                "closure": entry(run / "closure.json"), "raw": closure["raw"]},
        "raw_files_total": len(closure["raw"]),
        "parent_input_sha256": contract["dependency"]["input_sha256"],
        "parent_evidence_sha256": contract["dependency"]["evidence_sha256"],
        "manual_sha256": contract["manual"]["sha256"],
        "dictionary_sha256": contract["manual"]["dictionary_sha256"],
        "limits": contract["limits"],
    }
    destination = HERE / "evidence-index.json"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"closure_sha256": result["run"]["closure"]["sha256"],
                      "raw_files": len(closure["raw"]),
                      "index_sha256": entry(destination)["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
