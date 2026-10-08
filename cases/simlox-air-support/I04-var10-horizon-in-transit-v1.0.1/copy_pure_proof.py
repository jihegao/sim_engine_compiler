"""Own exact original author and independent PURE proof streams."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from model_common import encode, pin, read, verify_expected

HERE = Path(__file__).resolve().parent
DEST = HERE / "preserved-pure-proof"
MAP = HERE / "pure-proof-custody.json"
AUTHOR_NAMES = tuple(f"{label}-{stream}.bin" for label in
                     ("build", "context", "source", "selfcheck", "converter", "inventory", "manifest")
                     for stream in ("stdout", "stderr")) + ("receipt.json",)
INDEPENDENT_NAMES = ("receipt.json", "stdout.bin", "stderr.bin")


def checked_paths(source):
    document = read(source)
    assert document["schema"] == "i04-var10-pure-proof-originals/v101"
    rows = document["records"]
    assert len(rows) == 21
    paths = [Path(item["path"]).resolve(strict=True) for item in rows]
    assert len({str(path).lower() for path in paths}) == 21
    assert tuple(path.name for path in paths[:15]) == AUTHOR_NAMES
    author_dir = paths[0].parent
    assert author_dir.parent == (HERE / "test-output").resolve(strict=True)
    assert re.fullmatch(r"local-pure-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}", author_dir.name)
    assert all(path.parent == author_dir for path in paths[:15])
    for start in (15, 18):
        assert tuple(path.name for path in paths[start:start + 3]) == INDEPENDENT_NAMES
        assert len({path.parent for path in paths[start:start + 3]}) == 1
    assert paths[15].parent != paths[18].parent != author_dir
    for path, row in zip(paths, rows):
        assert pin(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    return paths, rows


def candidate(source, write=False):
    paths, originals = checked_paths(source)
    if write:
        DEST.mkdir(exist_ok=True)
    records = []
    for number, (path, row) in enumerate(zip(paths, originals)):
        owned = DEST / f"pure-{number:02d}.bytes"
        verify_expected(owned, path.read_bytes(), write)
        records.append({"original_path": str(path),
                        "owned_copy": owned.relative_to(HERE).as_posix(),
                        "bytes": row["bytes"], "sha256": row["sha256"],
                        "original_if_present_must_match": True})
    document = {"schema": "i04-var10-pure-proof-custody/v101", "records": records,
                "originals_optional_after_publication": True,
                "author_record_count": 15, "independent_record_count": 6}
    return verify_expected(MAP, encode(document), write)


def verify():
    mapping = read(MAP)
    assert set(mapping) == {"schema", "records", "originals_optional_after_publication",
                            "author_record_count", "independent_record_count"}
    assert mapping["schema"] == "i04-var10-pure-proof-custody/v101"
    assert mapping["originals_optional_after_publication"] is True
    assert type(mapping["author_record_count"]) is int and mapping["author_record_count"] == 15
    assert type(mapping["independent_record_count"]) is int and mapping["independent_record_count"] == 6
    rows = mapping["records"]
    assert len(rows) == 21
    for number, row in enumerate(rows):
        assert set(row) == {"original_path", "owned_copy", "bytes", "sha256",
                            "original_if_present_must_match"}
        assert row["owned_copy"] == f"preserved-pure-proof/pure-{number:02d}.bytes"
        assert row["original_if_present_must_match"] is True
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert pin(HERE / row["owned_copy"]) == expected
        source = Path(row["original_path"])
        if source.exists():
            assert pin(source) == expected
    assert tuple(Path(row["original_path"]).name for row in rows[:15]) == AUTHOR_NAMES
    author_dir = Path(rows[0]["original_path"]).parent
    assert author_dir.parent == HERE / "test-output"
    assert re.fullmatch(r"local-pure-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}", author_dir.name)
    assert all(Path(row["original_path"]).parent == author_dir for row in rows[:15])
    for start in (15, 18):
        assert tuple(Path(row["original_path"]).name for row in rows[start:start + 3]) == INDEPENDENT_NAMES
        assert len({Path(row["original_path"]).parent for row in rows[start:start + 3]}) == 1
    return 21


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--originals", type=Path)
    args = parser.parse_args()
    if args.write:
        assert args.originals is not None
        print(json.dumps({"schema": "i04-var10-pure-proof-copy/v101",
                          "copies": 21, "map": candidate(args.originals, True)}, sort_keys=True))
    else:
        assert args.originals is None
        print(json.dumps({"schema": "i04-var10-pure-proof-check/v101",
                          "copies": verify()}, sort_keys=True))
