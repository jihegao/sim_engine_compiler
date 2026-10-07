"""Read-only byte audit of the frozen v1.0.6 contract and accepted ancestry.

This script uses only Python's standard library and Git blob reads. It never
imports a package checker, writes a file, or starts SIMLOX.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent.parent
REPO = next(p for p in HERE.parents if (p / ".git").exists())
CONTRACT = HERE / "contract.json"


def digest(path: Path) -> dict[str, int | str]:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def expected(path: Path, record: dict) -> None:
    actual = digest(path)
    assert actual == {"bytes": record["bytes"], "sha256": record["sha256"]}, (path, actual, record)


def resolve(path: str, base: Path = HERE) -> Path:
    candidate = Path(path)
    return (candidate if candidate.is_absolute() else base / candidate).resolve()


def git_expected(path: Path, base_commit: str, record: dict) -> None:
    name = path.relative_to(REPO).as_posix()
    data = subprocess.check_output(["git", "-C", str(REPO), "show", f"{base_commit}:{name}"])
    actual = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    assert actual == {"bytes": record["bytes"], "sha256": record["sha256"]}, (path, actual, record)


def literal_pins(node: object) -> list[dict]:
    records = []
    if isinstance(node, dict):
        if {"path", "bytes", "sha256"} <= node.keys():
            records.append(node)
        for item in node.values():
            records.extend(literal_pins(item))
    elif isinstance(node, list):
        for item in node:
            records.extend(literal_pins(item))
    return records


def main() -> None:
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["schema"] == "simlox-c09-var02-lender-shortage-v106-child-contract/v1"
    assert c["case_id"] == "C09" and c["version"] == "1.0.6"
    assert c["base_commit"] == "d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef"
    assert c["planned_child"]["run_id"] == "c09-var02-v106-shortage-ssh-20261007-01"
    assert not (HERE / c["planned_child"]["run_directory"]).exists()
    assert not (HERE / "shortage-input.json").exists()
    assert not (HERE / "run_native_ssh.ps1").exists()

    pins = literal_pins(c)
    for rec in pins:
        expected(resolve(rec["path"]), rec)
    assert len(pins) == 64, len(pins)

    old_manifest = resolve(c["excluded_v105"]["manifest"]["path"])
    m = json.loads(old_manifest.read_text(encoding="utf-8-sig"))
    assert m["schema"] == "c09-var02-v105-prelaunch-manifest/v1"
    assert len(m["source_files"]) == m["source_count"] == 384
    for rec in m["source_files"]:
        expected(resolve(rec["path"]), rec)

    pin = c["published_parent"]["evidence_index"]
    index_path = resolve(pin["path"])
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["source_count"] == 101 and index["raw_count"] == 130
    assert len(index["accepted_source_refs"]) == 77
    assert index["positive_pair_accepted"] is False and index["shortage_arm"] == "not_started_not_tested"
    for rec in index["source_files"]:
        path = resolve(rec["path"], index_path.parent)
        expected(path, rec)
        git_expected(path, c["base_commit"], rec)
    for rec in index["accepted_source_refs"]:
        path = resolve(rec["path"], index_path.parent)
        expected(path, rec["local_disk"])
        git_expected(path, c["base_commit"], rec["published_git"])
    for rec in index["raw_files"]:
        expected(resolve(rec["path"], index_path.parent), rec)

    receipt = c["root_selection_and_owner_receipts"]["new_v106_initial_snapshot"]
    owner = json.loads(resolve(receipt["path"]).read_text(encoding="utf-8-sig"))
    assert owner["utc"] == "2026-10-07T05:55:07.7120445Z"
    assert owner["ssh_present"] and owner["self_session"] == 0 and owner["powershell_major"] == 5
    assert owner["mutex_free"] and not owner["runner_candidates"]
    assert owner["session_query_exit"] == 0 and owner["active_gui_session1_count"] == 1
    assert not owner["v103_run_exists"] and not owner["v106_run_exists"] and not owner["old_shortage_run_exists"]
    assert owner["native"] == [{"pid": 13340, "session": 1,
                                "start_utc": "2026-09-28T10:09:56.8261381Z",
                                "start_ms": 1790590196826, "responding": True}]

    print(json.dumps({"decision": "PIN_AUDIT_PASS", "contract": digest(CONTRACT),
                      "literal_pins": len(pins), "excluded_v105_manifest_records": len(m["source_files"]),
                      "parent_source_disk_git": len(index["source_files"]),
                      "parent_dual_source_refs": len(index["accepted_source_refs"]),
                      "parent_raw": len(index["raw_files"]),
                      "run_absent": True, "child_source_absent": True}, sort_keys=True))


if __name__ == "__main__":
    main()
