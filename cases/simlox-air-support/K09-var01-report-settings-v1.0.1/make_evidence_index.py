"""Seal K09 diagnostic and accepted report-only runs without publishing raw data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


CASE = Path(__file__).resolve().parent
PREV = CASE.parent / "K09-var01-report-settings-v1.0.0"
RUN_ID = "k09-var01-report-settings-v101-ssh-20261004-01"
DIAGNOSTIC_ID = "k09-var01-report-settings-v100-ssh-20261004-01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entry(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": digest(path)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_entry(package: Path, run_id: str, *, accepted: bool) -> dict:
    path = package / "runs" / run_id
    closure = load(path / "closure.json")
    assert closure["run_id"] == run_id and closure["error"] is None
    assert digest(path / "invocation.json") == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 8
    for name, seal in closure["raw"].items():
        assert entry(path / name) == seal, (run_id, name)
    return {
        "run_id": run_id,
        "classification": "bounded_candidate" if accepted else "excluded_diagnostic",
        "local_directory": str(path),
        "invocation": entry(path / "invocation.json"),
        "closure": entry(path / "closure.json"),
        "raw": closure["raw"],
    }


contract = load(CASE / "contract.json")
assert contract["run_id"] == RUN_ID
assert contract["excluded_diagnostic"]["run_id"] == DIAGNOSTIC_ID
diagnostic = run_entry(PREV, DIAGNOSTIC_ID, accepted=False)
accepted = run_entry(CASE, RUN_ID, accepted=True)
assert diagnostic["closure"]["sha256"] == contract["excluded_diagnostic"]["closure_sha256"]
sources = {
    "v1.0.0": ["contract.json", "make_report_settings.py", "run_reports_ssh.ps1", "review/independent_replay.py", "review/independent-verdict.json"],
    "v1.0.1": ["contract.json", "make_report_settings.py", "run_reports_ssh.ps1", "review/independent_replay.py", "review/independent-verdict.json"],
}
result = {
    "schema": "simlox-k09-report-settings-evidence-index/v1",
    "case_id": "K09",
    "variant_id": "K09.var01",
    "version": "1.0.1",
    "publication_state": "not_published",
    "source": {
        version: {name: entry((PREV if version == "v1.0.0" else CASE) / name) for name in files}
        for version, files in sources.items()
    },
    "parent": contract["parent"],
    "runs": {"excluded_diagnostic": diagnostic, "bounded_candidate": accepted},
    "raw_files_total": 16,
    "manual_sha256": contract["manual"]["sha256"],
    "limits": contract["limits"],
}
(CASE / "evidence-index.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"diagnostic_closure": diagnostic["closure"]["sha256"], "candidate_closure": accepted["closure"]["sha256"], "raw_files": 16}, indent=2))
