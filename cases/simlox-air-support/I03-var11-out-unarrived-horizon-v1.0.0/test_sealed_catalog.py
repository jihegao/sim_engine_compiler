"""In-memory prefix and type probes; never modifies the live catalog."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from verify_sources import HERE, check_catalog_live


def rejects(action) -> None:
    try:
        action()
    except (AssertionError, KeyError, TypeError, ValueError):
        return
    raise AssertionError("catalog mutation escaped")


def main() -> None:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    item = contract["source_lineage"]["catalog_at_selection"]
    archived_bytes = (HERE / item["owned_exact_archive"]).read_bytes()
    archive = json.loads(archived_bytes.decode("utf-8-sig"))
    assert check_catalog_live(archive, archived_bytes, item, "live") == 492
    appended = copy.deepcopy(archive)
    appended["entries"].append({"publication_id": "in-memory.probe.unique"})
    encode = lambda doc: (json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    assert check_catalog_live(archive, encode(appended), item, "sealed") == 493
    rejects(lambda: check_catalog_live(archive, encode(appended), item, "live"))
    duplicate = copy.deepcopy(appended)
    duplicate["entries"][-1]["publication_id"] = duplicate["entries"][0]["publication_id"]
    rejects(lambda: check_catalog_live(archive, encode(duplicate), item, "sealed"))
    changed = copy.deepcopy(appended)
    changed["entries"][0]["publication_id"] = "changed-prior-entry"
    rejects(lambda: check_catalog_live(archive, encode(changed), item, "sealed"))
    changed = copy.deepcopy(appended)
    changed["meaning"] = True
    rejects(lambda: check_catalog_live(archive, encode(changed), item, "sealed"))
    changed = copy.deepcopy(appended)
    changed["entries"][0]["positive_pair_accepted"] = True
    rejects(lambda: check_catalog_live(archive, encode(changed), item, "sealed"))
    print(json.dumps({"schema": "i03-var11-catalog-self-check/v1", "passed": True,
                      "archived_entries": 492, "synthetic_appended_entries": 493,
                      "semantic_rejections": 5}, separators=(",", ":")))


if __name__ == "__main__":
    main()
