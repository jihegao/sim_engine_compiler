"""Make exact, inert copies of unpublished design and root context.

Default mode only verifies the owned copies. The original tmp paths are
optional at later replay; accepted raw and published source remain mandatory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DESIGN = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
MAP = HERE / "context-custody-v2.json"
COPY_DIR = HERE / "preserved-context"


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def declared() -> list[dict]:
    source = DESIGN["source_lineage"]
    paths = list(source["design_history"])
    paths += [
        {"path": source["root_selection_receipt"]["path"], **{k: source["root_selection_receipt"][k] for k in ("bytes", "sha256")}},
        {"path": source["root_installed_pin_receipt"]["path"], **{k: source["root_installed_pin_receipt"][k] for k in ("bytes", "sha256")}},
        {"path": "tmp/i03-var05-independent-contract-v4-go-20261008.md", "bytes": 2862,
         "sha256": "e343d15fdaddb51a940c183c0d22b509356f9067cd96203eea29377155c34664"},
        {"path": "tmp/issue18-root-i03var05-construction-go-20261008.json", "bytes": 2158,
         "sha256": "df2c7dba3d75c55ce65dd070c2f1d016be3a04b44fb4c9f022a7969bb5bf9fb5"},
        {"path": "tmp/i03-var05-prospective-contract-design-v4-20261008.json", "bytes": 121824,
         "sha256": "95ba77bcac344e023f140a39b4f88b4f94160d07c2a4e94563ff84de592f7331"},
        {"path": "tmp/build-i03-var05-design-v4-20261008.py", "bytes": 25646,
         "sha256": "e3662908ab1c2ff76bef2d9d1fe8c321b966073d5647bf4fa2900db8d2fe4496"},
        {"path": "tmp/i03-var05-root-contract-history-20261008.json", "bytes": 1429,
         "sha256": "a2ac7142349f03d6d0c9598d2a8a47b653659fa8f0a64af3c30c9ea36ba4a9bc"},
        {"path": "tmp/i03-var05-root-input-byte-audit-20261008.json", "bytes": 1718,
         "sha256": "79dca326383666193ae2552ba333413674474e41df0ad65aac8a2889b7e7beea"},
    ]
    paths += [{"path": "cases/simlox-air-support/publication-index-v1.json",
               **source["catalog_local_point_time"]}]
    assert len(paths) == len({row["path"] for row in paths})
    return paths


def records(write: bool) -> list[dict]:
    rows = []
    if write:
        COPY_DIR.mkdir(exist_ok=True)
    for index, item in enumerate(declared(), 1):
        original = REPO / item["path"]
        wanted = {key: item[key] for key in ("bytes", "sha256")}
        copy = COPY_DIR / f"c{index:03d}.bytes"
        if write:
            data = original.read_bytes()
            assert pin(data) == wanted, item["path"]
            if copy.exists():
                assert copy.read_bytes() == data, copy
            else:
                copy.write_bytes(data)
        data = copy.read_bytes()
        assert pin(data) == wanted, copy
        if original.exists() and item["path"] != "cases/simlox-air-support/publication-index-v1.json":
            assert pin(original.read_bytes()) == wanted, original
        rows.append({"original_path": item["path"], "owned_copy": copy.relative_to(HERE).as_posix(), **wanted,
                     "original_if_present_must_match": item["path"] != "cases/simlox-air-support/publication-index-v1.json"})
    return rows


def main() -> None:
    write = sys.argv[1:] == ["--write"]
    assert not sys.argv[1:] or write
    rows = records(write)
    result = {"schema": "i03-var05-context-custody/v2", "records": rows,
              "accepted_original_raw_are_separate_and_mandatory": 112}
    body = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if MAP.exists():
        assert MAP.read_bytes() == body
    else:
        assert write
        MAP.write_bytes(body)
    print(json.dumps({"schema": result["schema"], "owned_copies": len(rows),
                      "map": pin(body)}, sort_keys=True))


if __name__ == "__main__":
    main()
