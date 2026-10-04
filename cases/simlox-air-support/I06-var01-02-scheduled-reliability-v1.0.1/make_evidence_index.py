"""Seal the I06 scheduled reliability panel's local native evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent


def entry(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(CASE / "contract.json")
    directory = CASE / "runs" / contract["run_id"]
    closure = load(directory / "closure.json")
    assert closure["run_id"] == contract["run_id"] and closure["error"] is None
    assert entry(directory / "invocation.json")["sha256"] == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 122
    for name, seal in closure["raw"].items():
        assert entry(directory / name) == seal, name
    sources = [".gitattributes", ".gitignore", "build.py", "contract.json", "run_native_ssh.ps1",
               "validate.py", "make_evidence_index.py",
               *[f"{kind}-seed{seed}-{arm}-input.json" for kind in contract["kinds"] for seed in contract["seeds"] for arm in contract["arms"]],
               "review/preflight-2026-10-05.md", "review/author-validation-2026-10-05.json",
               "review/independent_replay.py", "review/independent-verdict.json"]
    result = {
        "schema": "simlox-i06-scheduled-reliability-evidence-index/v1",
        "case_id": "I06", "version": CASE.name.rsplit("-v", 1)[-1],
        "publication_state": "excluded_diagnostic" if CASE.name.endswith("v1.0.0") else "not_published",
        "source": {name: entry(CASE / name) for name in sources},
        "run": {"run_id": contract["run_id"], "local_directory": str(directory),
                "invocation": entry(directory / "invocation.json"),
                "closure": entry(directory / "closure.json"), "raw": closure["raw"]},
        "raw_files_total": len(closure["raw"]),
        "parents": {"item_input_sha256": contract["dependency"]["item_parent_input_sha256"],
                    "fm_input_sha256": contract["dependency"]["fm_parent_input_sha256"]},
        "excluded_diagnostic_closure_sha256": contract["dependency"].get("excluded_diagnostic_closure_sha256"),
        "manual_sha256": contract["manual"]["sha256"],
        "limits": contract["limits"],
    }
    destination = CASE / "evidence-index.json"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"closure_sha256": result["run"]["closure"]["sha256"],
                      "raw_files": len(closure["raw"]),
                      "index_sha256": entry(destination)["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
