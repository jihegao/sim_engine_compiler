"""Seal the D15 seed panel sources and both immutable local native runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


CASE = Path(__file__).resolve().parent
NATIVE_ID = "d15-var01-pmrf-seed-panel-v101-ssh-20261004-01"
SELECTED_ID = "d15-var01-pmrf-seed-panel-v101-item-report-ssh-20261004-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entry(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_entry(run_id: str) -> dict:
    path = CASE / "runs" / run_id
    closure = load(path / "closure.json")
    assert closure["run_id"] == run_id and closure["error"] is None
    assert sha(path / "invocation.json") == closure["invocation_sha256"]
    for name, seal in closure["raw"].items():
        assert entry(path / name) == seal, (run_id, name)
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    return {
        "run_id": run_id,
        "local_directory": str(path),
        "invocation": entry(path / "invocation.json"),
        "closure": entry(path / "closure.json"),
        "raw": closure["raw"],
    }


contract = load(CASE / "contract.json")
assert contract["run_id"] == NATIVE_ID
assert contract["selected_report_run_id"] == SELECTED_ID
native = run_entry(NATIVE_ID)
selected = run_entry(SELECTED_ID)
assert load(CASE / "runs" / SELECTED_ID / "closure.json")["source_closure_sha256"] == native["closure"]["sha256"]
assert len(native["raw"]) == 102 and len(selected["raw"]) == 22
sources = [
    ".gitattributes",
    ".gitignore",
    "build.py",
    "contract.json",
    "make_report_settings.py",
    "run_native_ssh.ps1",
    "run_item_reports_ssh.ps1",
    *[f"seed{seed}-{kind}-input.json" for seed in range(2, 7) for kind in ("certain", "fractional")],
    "review/preflight-2026-10-04.md",
    "review/independent_replay.py",
    "review/independent-verdict.json",
]
result = {
    "schema": "simlox-d15-pmrf-seed-panel-evidence-index/v1",
    "case_id": "D15",
    "variant_id": "D15.var01",
    "version": "1.0.1",
    "publication_state": "not_published",
    "source": {name: entry(CASE / name) for name in sources},
    "excluded_predecessor": {
        "package": "../D15-var01-pmrf-scheduled-v1.0.0",
        "closure_sha256": contract["dependency"]["excluded_diagnostic_closure_sha256"],
    },
    "runs": {"native": native, "selected_item_report": selected},
    "raw_files_total": len(native["raw"]) + len(selected["raw"]),
    "manual_sha256": contract["manual"]["sha256"],
    "limits": contract["limits"],
}
(CASE / "evidence-index.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"native_closure": native["closure"]["sha256"], "selected_closure": selected["closure"]["sha256"], "raw_files": result["raw_files_total"]}, indent=2))
