"""One-time exact author source handoff for root freeze before manifest creation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from make_prelaunch_manifest import candidate
from verify_sources import HERE, REPO

OUTPUT = REPO / "tmp/i03-var06-author-freeze-ready-20261008.json"


def main() -> None:
    assert sys.argv[1:] in ([], ["--write"])
    manifest = candidate(False)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    owned = [item for item in manifest["source_files"]
             if Path(item["path"]).is_relative_to(HERE)]
    assert len({item["key"] for item in manifest["source_files"]}) == manifest["source_count"]
    doc = {"schema": "i03-var06-author-source-freeze-handoff/v1",
           "run_id": manifest["run_id"], "native_runs_started": 0,
           "prelaunch_manifest_path": str(HERE / "prelaunch-manifest.json"),
           "predicted_manifest_bytes": len(manifest_bytes),
           "predicted_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
           "source_count": manifest["source_count"],
           "owned_source_count": len(owned),
           "owned_source_files": owned,
           "fixed_roles": {name: next(item for item in manifest["source_files"] if item["key"] == name)
                           for name in ("child_contract", "child_input", "runner_script",
                                        "behavior_validator", "independent_replay",
                                        "independent_self_check")},
           "large_helper_original_raw_pins": manifest["helper_large_original_raw_pins"],
           "manifest_not_yet_written": not (HERE / "prelaunch-manifest.json").exists()}
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if sys.argv[1:] == ["--write"]:
        assert not OUTPUT.exists() and doc["manifest_not_yet_written"]
        OUTPUT.write_bytes(data)
    else:
        assert OUTPUT.is_file() and OUTPUT.read_bytes() == data
    print(json.dumps({"schema": doc["schema"], "passed": True,
                      "source_count": doc["source_count"],
                      "owned_source_count": doc["owned_source_count"],
                      "predicted_manifest_sha256": doc["predicted_manifest_sha256"],
                      "handoff_sha256": hashlib.sha256(data).hexdigest()}, separators=(",", ":")))


if __name__ == "__main__":
    main()
