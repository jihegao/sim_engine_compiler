"""In-memory postpublication catalog tests of the production source verifier."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

from verify_sources import HERE, REPO, identity, verify


class MemoryManifest:
    def __init__(self, document: dict):
        self.document = document

    def read_text(self, encoding: str) -> str:
        assert encoding == "utf-8-sig"
        return json.dumps(self.document, ensure_ascii=False)


def rejects(action) -> None:
    try:
        action()
    except (AssertionError, ValueError, KeyError, TypeError):
        return
    raise AssertionError("catalog mutation escaped source verifier")


def main() -> None:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    catalog = contract["source_lineage"]["catalog_at_selection"]
    live_path = (REPO / catalog["path"]).resolve(strict=True)
    historical = json.loads((HERE / catalog["owned_exact_archive"]).read_text(encoding="utf-8-sig"))
    manifest = MemoryManifest({
        "schema": "i03-var02-v102-prelaunch-manifest/v2",
        "contract_sha256": "1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29",
        "run_id": contract["run_id"],
        "source_files": [{"key": "catalog_live_prelaunch", "path": str(live_path), **catalog["local_disk"]}],
    })
    original_read_bytes = Path.read_bytes

    def run_with_live(document: dict, mode: str):
        altered = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        def read_bytes(path: Path) -> bytes:
            if path.resolve(strict=True) == live_path:
                return altered
            return original_read_bytes(path)
        with patch.object(Path, "read_bytes", read_bytes):
            return verify(mode, manifest)

    appended = copy.deepcopy(historical)
    added = copy.deepcopy(appended["entries"][-1])
    added["publication_id"] = "synthetic.append.only.for.memory.test"
    appended["entries"].append(added)
    sealed = run_with_live(appended, "sealed")
    assert sealed["passed"] and sealed["catalog"]["live_entries"] == 491
    assert sealed["source_map"][str(live_path)] == catalog["local_disk"]
    rejects(lambda: run_with_live(appended, "live"))
    wrong_metadata = copy.deepcopy(appended)
    metadata_key = next(k for k in historical if k != "entries")
    wrong_metadata[metadata_key] = True
    rejects(lambda: run_with_live(wrong_metadata, "sealed"))
    wrong_prefix = copy.deepcopy(appended)
    wrong_prefix["entries"][0]["publication_id"] += ".changed"
    rejects(lambda: run_with_live(wrong_prefix, "sealed"))
    print(json.dumps({"schema": "i03-var02-v102-sealed-catalog-self-check/v1",
                      "passed": True, "accepted_append_entries": 1,
                      "rejections": 3, "historical_catalog": identity((HERE / catalog["owned_exact_archive"]).read_bytes())},
                     separators=(",", ":")))


if __name__ == "__main__":
    main()
