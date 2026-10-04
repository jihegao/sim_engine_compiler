"""Seal E14 frozen sources and both immutable local native runs."""
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


def run_entry(run_id: str) -> dict:
    directory = CASE / "runs" / run_id
    closure = load(directory / "closure.json")
    assert closure["run_id"] == run_id and closure["error"] is None
    assert entry(directory / "invocation.json")["sha256"] == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    for name, seal in closure["raw"].items():
        assert entry(directory / name) == seal, (run_id, name)
    return {"run_id": run_id, "local_directory": str(directory),
            "invocation": entry(directory / "invocation.json"),
            "closure": entry(directory / "closure.json"), "raw": closure["raw"]}


def main() -> None:
    contract = load(CASE / "contract.json")
    native = run_entry(contract["run_id"])
    selected = run_entry(contract["selected_report_run_id"])
    assert load(CASE / "runs" / contract["selected_report_run_id"] / "closure.json")["source_closure_sha256"] == native["closure"]["sha256"]
    assert len(native["raw"]) == 102 and len(selected["raw"]) == 62
    files = [".gitattributes", ".gitignore", "build.py", "contract.json", "make_report_settings.py",
             "run_native_ssh.ps1", "run_item_reports_ssh.ps1", "validate.py", "make_evidence_index.py",
             *[f"seed{seed}-{arm}-input.json" for seed in contract["seeds"] for arm in contract["arms"]],
             "review/preflight-2026-10-05.md", "review/author-validation-2026-10-05.json",
             "review/independent_replay.py", "review/independent-verdict.json"]
    result = {
        "schema": "simlox-e14-two-sru-panel-evidence-index/v1",
        "case_id": "E14", "variant_ids": contract["variant_ids"], "version": "1.0.0",
        "publication_state": "not_published",
        "source": {name: entry(CASE / name) for name in files},
        "parent": {"package": contract["dependency"]["accepted_parent"],
                   "input_sha256": contract["dependency"]["parent_input_sha256"],
                   "signoff_sha256": contract["dependency"]["parent_signoff_sha256"]},
        "runs": {"native": native, "selected_item_report": selected},
        "raw_files_total": len(native["raw"]) + len(selected["raw"]),
        "manual_sha256": contract["manual"]["sha256"], "limits": contract["limits"],
    }
    destination = CASE / "evidence-index.json"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"native_closure": native["closure"]["sha256"],
                      "selected_closure": selected["closure"]["sha256"],
                      "raw_files": result["raw_files_total"],
                      "index_sha256": entry(destination)["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
