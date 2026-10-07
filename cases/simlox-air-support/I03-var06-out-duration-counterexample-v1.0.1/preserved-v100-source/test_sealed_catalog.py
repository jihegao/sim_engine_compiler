"""Pure in-memory catalog append probes through the production source verifier."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import verify_sources as source
from make_prelaunch_manifest import candidate


def rejected(call) -> bool:
    try:
        call()
    except (AssertionError, KeyError, TypeError, ValueError):
        return True
    return False


def main() -> dict:
    contract = json.loads((source.HERE / "contract.json").read_text(encoding="utf-8"))
    catalog_item = contract["source_lineage"]["catalog_at_selection"]
    catalog_path = source.REPO / catalog_item["path"]
    original_bytes = catalog_path.read_bytes()
    original = json.loads(original_bytes.decode("utf-8-sig"))
    assert len(original["entries"]) == 491
    baseline_manifest = candidate(True, "live")
    manifest = {"schema": "i03-var06-out-dt4-prelaunch-manifest/v1",
                "contract_sha256": source.CONTRACT_SHA, "run_id": source.RUN_ID,
                "source_files": [{"key": "catalog_live_prelaunch", "path": catalog_item["path"],
                                  **catalog_item["local_disk"]}]}
    test_manifest = source.HERE / "preserved-root-context" / "catalog-test-manifest-synthetic.json"
    # The manifest is injected in memory; never write a new file or alter the live catalog.
    original_read_text = Path.read_text
    original_read_bytes = Path.read_bytes

    def scenario(document: dict, mode: str, check_builder: bool = False) -> bool:
        simulated = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        def bytes_override(path: Path) -> bytes:
            if path == catalog_path:
                return simulated
            return original_read_bytes(path)

        def text_override(path: Path, *args, **kwargs) -> str:
            if path == test_manifest:
                return json.dumps(manifest, ensure_ascii=False)
            return original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_bytes", bytes_override), patch.object(Path, "read_text", text_override):
            assert source.verify(mode, test_manifest)["passed"]
            if check_builder:
                assert source.strict_equal(candidate(True, "sealed"), baseline_manifest)
            return True

    appended = copy.deepcopy(original)
    new_entry = copy.deepcopy(appended["entries"][-1])
    new_entry["publication_id"] = "synthetic.append.only.for.in.memory.test"
    appended["entries"].append(new_entry)
    assert scenario(appended, "sealed", check_builder=True)
    assert rejected(lambda: scenario(appended, "live"))
    wrong_prefix = copy.deepcopy(appended)
    wrong_prefix["entries"][0]["publication_id"] = "synthetic.corrupt.prefix"
    assert rejected(lambda: scenario(wrong_prefix, "sealed"))
    wrong_metadata = copy.deepcopy(appended)
    metadata_key = next(k for k in wrong_metadata if k != "entries")
    wrong_metadata[metadata_key] = True
    assert rejected(lambda: scenario(wrong_metadata, "sealed"))
    duplicate = copy.deepcopy(appended)
    duplicate["entries"][-1]["publication_id"] = duplicate["entries"][0]["publication_id"]
    assert rejected(lambda: scenario(duplicate, "sealed"))
    return {"schema": "i03-var06-sealed-catalog-test/v1", "passed": True,
            "accepted_valid_append": 1, "rejected_mutations": 4,
            "sealed_builder_reproduced_provisional": True,
            "live_catalog_unchanged": catalog_path.read_bytes() == original_bytes}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, separators=(",", ":")))
