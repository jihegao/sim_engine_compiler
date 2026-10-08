"""Closed ordered source inventory; root promotes a reviewed candidate exactly once."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_LIST = HERE / "source-list.json"
INVENTORY = HERE / "source-inventory.json"
FUTURE_FILES = frozenset({"source-inventory.json", "prelaunch-manifest.json",
                          "README-publication.md", "REPRODUCTION-postrun.md",
                          "results-summary.json", "publication-entry.json",
                          "cli-scope-signoff-2026-10-09.md", "make_evidence_index.py",
                          "evidence-index.json"})
FUTURE_REVIEW_PREFIXES = ("preflight-ssh0-", "independent-prelaunch-",
                          "independent-postrun-", "independent-content-")
GENERATED_TOP = frozenset({"runs", "test-output", "transport-evidence", "__pycache__"})
INERT_TOP = {"preserved-postrun": "postrun", "preserved-raw": "raw",
             "preserved-preflight": "preflight"}


def excluded(rel: str) -> bool:
    parts = rel.split("/")
    if parts[0] in GENERATED_TOP:
        return True
    if len(parts) == 2 and parts[0] in INERT_TOP:
        stem = INERT_TOP[parts[0]]
        return parts[1] == "custody.json" or re.fullmatch(rf"{stem}-[0-9]{{3}}\.bytes", parts[1]) is not None
    if rel in FUTURE_FILES:
        return True
    if len(parts) == 2 and parts[0] == "review":
        return any(parts[1].startswith(prefix) for prefix in FUTURE_REVIEW_PREFIXES)
    return False


def owned_paths() -> tuple[str, ...]:
    doc = json.loads(SOURCE_LIST.read_text(encoding="utf-8"))
    assert type(doc) is dict and set(doc) == {"schema", "files"}
    assert doc["schema"] == "e02-var02-owned-source-list/v104"
    files = doc["files"]
    assert type(files) is list and all(type(x) is str for x in files)
    assert "source-list.json" in files and "make_source_inventory.py" in files
    assert len(files) == len(set(files)) == len({x.casefold() for x in files})
    for rel in files:
        path = Path(rel)
        assert not path.is_absolute() and ".." not in path.parts and rel == path.as_posix()
        assert not excluded(rel), rel
    return tuple(files)


def document() -> dict[str, object]:
    owned = owned_paths()
    observed = set()
    for root, dirs, files in os.walk(HERE, topdown=True, followlinks=False):
        place = Path(root)
        if place == HERE:
            dirs[:] = [name for name in dirs if name not in GENERATED_TOP]
        for name in dirs:
            path = place / name
            assert not path.is_symlink() and not (path.stat().st_file_attributes & 0x400), str(path)
        for name in files:
            path = place / name
            rel = path.relative_to(HERE).as_posix()
            if not excluded(rel):
                observed.add(rel)
    assert observed == set(owned), {"missing": sorted(set(owned) - observed),
                                    "unknown": sorted(observed - set(owned))}
    rows = []
    for rel in owned:
        path = HERE / rel
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_file_attributes & 0x1, f"owned source writable: {rel}"
        body = path.read_bytes()
        rows.append({"path": rel, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
    return {"schema": "e02-var02-source-inventory/v104", "source_count": len(rows), "source_files": rows}


def encode(value: dict[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--candidate", type=Path)
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    body = encode(document())
    if args.candidate is not None:
        assert args.candidate.is_absolute() and not args.candidate.is_relative_to(HERE)
        with args.candidate.open("xb") as stream:
            stream.write(body)
    elif args.write:
        with INVENTORY.open("xb") as stream:
            stream.write(body)
    else:
        assert INVENTORY.read_bytes() == body
    print(json.dumps({"schema": "e02-var02-source-inventory-check/v104",
                      "passed": True, "source_count": document()["source_count"],
                      "sha256": hashlib.sha256(body).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
