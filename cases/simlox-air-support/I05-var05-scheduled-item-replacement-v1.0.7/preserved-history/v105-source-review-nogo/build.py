#!/usr/bin/env python3
"""Build the unfrozen I05.var05 source candidate from its accepted parent."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[3]
CONTRACT_PATH = PACKAGE / "contract.json"
PARENT_PATH = PACKAGE.parent / "H02-var04-item-damage-replacement-fallback-v1.0.0" / "fallback-input.json"
OUTPUT_PATH = PACKAGE / "native-input.json"
PARENT_SHA256 = "2e29c2ea72304544c68281e8629bd242cca3d6252cbbe7cea2c48e0a00716a97"
CONTRACT_SHA256 = "3caee5543f9fa4f30c3986d25b52e6606b4cc95de824351ced9a2bee13771475"


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
    text = raw.decode("utf-8", errors="strict")
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)


def main() -> None:
    parent_bytes = PARENT_PATH.read_bytes()
    actual_parent_sha = hashlib.sha256(parent_bytes).hexdigest()
    if actual_parent_sha != PARENT_SHA256:
        raise SystemExit(f"parent SHA-256 mismatch: {actual_parent_sha}")
    contract_bytes = CONTRACT_PATH.read_bytes()
    actual_contract_sha = hashlib.sha256(contract_bytes).hexdigest()
    if actual_contract_sha != CONTRACT_SHA256:
        raise SystemExit(f"contract SHA-256 mismatch: {actual_contract_sha}")

    contract = load_json(CONTRACT_PATH)
    parent = load_json(PARENT_PATH)
    if not isinstance(contract, dict) or not isinstance(parent, dict):
        raise SystemExit("contract and parent must be JSON objects")
    model = parent.get("model")
    if not isinstance(model, dict) or not isinstance(model.get("tables"), list):
        raise SystemExit("parent model.tables must be a list")
    child = json.loads(json.dumps(parent, ensure_ascii=False, allow_nan=False))
    tables = child["model"]["tables"]
    table_names = [table.get("name") for table in tables]
    if "ChangesItemReplacement" in table_names:
        raise SystemExit("parent already contains ChangesItemReplacement")

    cell = contract["source_delta"]["problem_description_cell"]
    problem_tables = [table for table in tables if table.get("name") == "ProblemDescription"]
    if len(problem_tables) != 1:
        raise SystemExit("expected exactly one ProblemDescription table")
    rows = problem_tables[0]["instances"][0]["rows"]
    if len(rows) != 1 or rows[0] != [cell["before"]]:
        raise SystemExit("ProblemDescription parent cell does not match frozen contract")
    rows[0][0] = cell["after"]

    schema = contract["change_table_schema"]
    tables.append(
        {
            "name": schema["table"],
            "columns": schema["columns"],
            "instances": [
                {
                    "instance_name": "",
                    "rows": [schema["exact_row"]],
                }
            ],
        }
    )
    OUTPUT_PATH.write_text(
        json.dumps(child, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    output_sha = hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "status": "UNFROZEN_SOURCE_CANDIDATE",
                "parent_sha256": actual_parent_sha,
                "contract_sha256": actual_contract_sha,
                "native_input": str(OUTPUT_PATH),
                "native_input_bytes": OUTPUT_PATH.stat().st_size,
                "native_input_sha256": output_sha,
                "native_actions": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
