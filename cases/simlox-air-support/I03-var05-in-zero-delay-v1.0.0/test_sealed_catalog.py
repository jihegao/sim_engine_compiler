"""PURE in-memory catalog-append and typed-prefix corruption probes."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

from make_prelaunch_manifest import body, candidate
from source_gate import REPO, verify

LIVE = (REPO / "cases/simlox-air-support/publication-index-v1.json").resolve(strict=True)
ORIGINAL_READ_BYTES = Path.read_bytes


def simulate(value: bytes, operation):
    def reader(path: Path) -> bytes:
        if path.resolve(strict=True) == LIVE:
            return value
        return ORIGINAL_READ_BYTES(path)
    with patch.object(Path, "read_bytes", reader):
        return operation()


def rejected(operation) -> None:
    try:
        operation()
    except (AssertionError, ValueError, TypeError, KeyError):
        return
    raise AssertionError("catalog semantic mutation escaped")


def run() -> dict:
    original = json.loads(ORIGINAL_READ_BYTES(LIVE))
    assert len(original["entries"]) == 494
    base = body(candidate(provisional=True, mode="sealed"))
    appended = copy.deepcopy(original)
    new_entry = copy.deepcopy(appended["entries"][-1])
    new_entry["publication_id"] = "i03-var05-synthetic-later-append-unique-id"
    appended["entries"].append(new_entry)
    appended_bytes = (json.dumps(appended, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    observed = simulate(appended_bytes, lambda: verify("sealed"))
    assert observed["catalog"]["historical_prefix_checked"] == 494
    assert observed["catalog"]["live_entries_observed"] == 495
    assert simulate(appended_bytes, lambda: body(candidate(provisional=True, mode="sealed"))) == base
    rejected(lambda: simulate(appended_bytes, lambda: verify("live")))
    changed_prefix = copy.deepcopy(appended)
    changed_prefix["entries"][0]["publication_id"] = "corrupted historical prefix"
    rejected(lambda: simulate(json.dumps(changed_prefix).encode(), lambda: verify("sealed")))
    changed_metadata = copy.deepcopy(appended)
    changed_metadata["schema_version"] = "corrupted" if "schema_version" in changed_metadata else None
    rejected(lambda: simulate(json.dumps(changed_metadata).encode(), lambda: verify("sealed")))
    duplicate_id = copy.deepcopy(appended)
    duplicate_id["entries"][-1]["publication_id"] = duplicate_id["entries"][0]["publication_id"]
    rejected(lambda: simulate(json.dumps(duplicate_id).encode(), lambda: verify("sealed")))
    return {"schema": "i03-var05-sealed-catalog-pure-test/v1", "simulated_live_entries": 495,
            "historical_prefix_checked": 494, "manifest_bytes_stable_after_append": True,
            "semantic_mutations_rejected": 4, "native_calls": 0}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
