#!/usr/bin/env python3
"""Independently shaped structural check for the I05.var05 source candidate."""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
CONTRACT_PATH = PACKAGE / "contract.json"
PARENT_PATH = PACKAGE.parent / "H02-var04-item-damage-replacement-fallback-v1.0.0" / "fallback-input.json"
PARENT_PACKAGE = PACKAGE.parent / "H02-var04-item-damage-replacement-fallback-v1.0.0"
CHILD_PATH = PACKAGE / "native-input.json"
PARENT_SHA256 = "2e29c2ea72304544c68281e8629bd242cca3d6252cbbe7cea2c48e0a00716a97"
CONTRACT_SHA256 = "12cf9fd1382a7c693bf0af910c71a83bf9c31c3ee47f4cead12846b2dd426233"


def fail(message: str) -> None:
    raise AssertionError(message)


def reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> object:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM is not permitted: {path}")
    return json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


def same_typed_value(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            same_typed_value(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            same_typed_value(a, b) for a, b in zip(left, right)
        )
    return left == right


def main() -> None:
    parent_bytes = PARENT_PATH.read_bytes()
    contract_bytes = CONTRACT_PATH.read_bytes()
    parent_sha = hashlib.sha256(parent_bytes).hexdigest()
    contract_sha = hashlib.sha256(contract_bytes).hexdigest()
    if parent_sha != PARENT_SHA256:
        fail(f"parent SHA-256 mismatch: {parent_sha}")
    if contract_sha != CONTRACT_SHA256:
        fail(f"contract SHA-256 mismatch: {contract_sha}")

    contract = load_json(CONTRACT_PATH)
    parent = load_json(PARENT_PATH)
    child = load_json(CHILD_PATH)
    if not all(isinstance(value, dict) for value in (contract, parent, child)):
        fail("contract, parent, and child must be JSON objects")

    schema = contract["change_table_schema"]
    parent_provenance = contract["accepted_parent_evidence"]
    evidence_index_path = PARENT_PACKAGE / "evidence-index.json"
    signoff_path = PARENT_PACKAGE / "cli-scope-signoff-2026-10-02.md"
    for source, expected, label in (
        (evidence_index_path, parent_provenance["evidence_index"], "parent evidence index"),
        (signoff_path, parent_provenance["scope_signoff"], "parent scope signoff"),
    ):
        data = source.read_bytes()
        if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
            fail(f"{label} bytes/hash differ from the contract")
    parent_index = load_json(evidence_index_path)
    parent_run = parent_index["accepted_runs"]["fallback"]
    expected_run = parent_provenance["fallback_run"]
    if parent_run["run_id"] != expected_run["run_id"]:
        fail("accepted parent fallback run ID differs from the contract")
    if parent_run["input_sha256"] != expected_run["input_sha256"] or parent_run["input_sha256"] != parent_sha:
        fail("accepted parent fallback input differs from the pinned parent")
    if parent_run["model_log_sha256"] != expected_run["model_log_sha256"]:
        fail("accepted parent fallback log hash differs from the contract")
    if parent_run["report_sha256"] != expected_run["report_sha256"]:
        fail("accepted parent fallback report hash differs from the contract")
    raw_seals = parent_run["raw"]
    if len(raw_seals) != expected_run["raw_artifact_count"]:
        fail("accepted parent raw artifact count differs from the contract")
    raw_root = Path(parent_run["local_path"])
    for name, seal in raw_seals.items():
        raw_path = raw_root / name
        if not raw_path.is_file():
            fail(f"accepted parent raw artifact missing: {name}")
        before = raw_path.stat()
        before_attributes = getattr(before, "st_file_attributes", None)
        before_mode = stat.S_IMODE(before.st_mode)
        if before_attributes != expected_run["raw_file_custody"]["observed_windows_attributes"]:
            fail(f"accepted parent raw artifact attributes changed: {name}")
        if before_mode != expected_run["raw_file_custody"]["observed_permission_mode"]:
            fail(f"accepted parent raw artifact permission mode changed: {name}")
        raw_bytes = raw_path.read_bytes()
        if len(raw_bytes) != seal["bytes"] or hashlib.sha256(raw_bytes).hexdigest() != seal["sha256"]:
            fail(f"accepted parent raw artifact bytes/hash differ: {name}")
        raw_bytes_after = raw_path.read_bytes()
        after = raw_path.stat()
        if hashlib.sha256(raw_bytes_after).hexdigest() != seal["sha256"]:
            fail(f"accepted parent raw artifact changed while being read: {name}")
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before_attributes != getattr(after, "st_file_attributes", None)
            or before_mode != stat.S_IMODE(after.st_mode)
        ):
            fail(f"accepted parent raw artifact metadata changed while being read: {name}")
    p_tables = parent["model"]["tables"]
    c_tables = child["model"]["tables"]
    if len(c_tables) != len(p_tables) + 1:
        fail("child must contain exactly one appended table")
    if [t.get("name") for t in c_tables[:-1]] != [t.get("name") for t in p_tables]:
        fail("parent table order must remain an unchanged prefix")

    added = c_tables[-1]
    if added.get("name") != "ChangesItemReplacement":
        fail("the appended table must be ChangesItemReplacement")
    if added.keys() != {"name", "columns", "instances"}:
        fail("the appended table object contains unexpected or missing fields")
    if not same_typed_value(added.get("columns"), schema["columns"]):
        fail("native column objects/order/metadata differ from the frozen contract")
    expected_instance = {
        "instance_name": "",
        "rows": [schema["exact_row"]],
    }
    if not same_typed_value(added.get("instances"), [expected_instance]):
        fail("the new table must have one empty-named instance and exactly the frozen row")
    if not same_typed_value(added.get("instances")[0]["rows"][0], schema["exact_row"]):
        fail("the sole row differs from the frozen typed values")

    cell = contract["source_delta"]["problem_description_cell"]
    p_desc = [t for t in p_tables if t.get("name") == "ProblemDescription"]
    c_desc = [t for t in c_tables[:-1] if t.get("name") == "ProblemDescription"]
    if len(p_desc) != 1 or len(c_desc) != 1:
        fail("expected one parent and one child ProblemDescription table")
    if p_desc[0]["instances"][0]["rows"][0][0] != cell["before"]:
        fail("parent ProblemDescription does not match the frozen before value")
    if c_desc[0]["instances"][0]["rows"][0][0] != cell["after"]:
        fail("child ProblemDescription does not match the frozen after value")

    restored = json.loads(json.dumps(child, ensure_ascii=False, allow_nan=False))
    restored["model"]["tables"].pop()
    restored_desc = next(t for t in restored["model"]["tables"] if t.get("name") == "ProblemDescription")
    restored_desc["instances"][0]["rows"][0][0] = cell["before"]
    if not same_typed_value(restored, parent):
        fail("restoring the two allowed changes must reproduce the full typed parent tree")

    child_bytes = CHILD_PATH.read_bytes()
    print(
        json.dumps(
            {
                "status": "PASS_UNFROZEN_SOURCE_DELTA",
                "parent_sha256": parent_sha,
                "contract_sha256": contract_sha,
                "accepted_parent_run_id": expected_run["run_id"],
                "accepted_parent_raw_artifacts_verified": len(raw_seals),
                "accepted_parent_raw_attributes_verified": expected_run["raw_file_custody"]["observed_windows_attributes"],
                "accepted_parent_raw_permission_mode_verified": expected_run["raw_file_custody"]["observed_permission_mode"],
                "child_bytes": len(child_bytes),
                "child_sha256": hashlib.sha256(child_bytes).hexdigest(),
                "parent_table_count": len(p_tables),
                "child_table_count": len(c_tables),
                "new_table_instances": 1,
                "new_rows": 1,
                "changed_existing_cells": 1,
                "native_actions": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL_UNFROZEN_SOURCE_DELTA: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
