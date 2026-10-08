"""Copy a fixed small external proof list into inert, byte-identical custody files.

Default verifies. --write is a one-time construction operation; it never touches
the original proofs or the frozen prelaunch bundle.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LIST = HERE / "postrun-context-originals.json"
MAP = HERE / "postrun-context-custody.json"
COPIES = HERE / "preserved-postrun-context"


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def body(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def paths() -> list[Path]:
    raw = json.loads(LIST.read_bytes())
    assert raw["schema"] == "i03-var08-fixed-postrun-context-originals/v1"
    names = raw["repo_relative_paths"]
    assert type(names) is list and names and len(names) == len(set(names))
    assert all(type(name) is str and name.startswith(("tmp/i03-var08-",
                                                     "tmp/build-i03-var08-",
                                                     "tmp/make-i03-var08-")) for name in names)
    return [REPO / name for name in names]


def candidate() -> dict:
    rows = []
    for index, original in enumerate(paths(), 1):
        owned = COPIES / f"c{index:03d}.bytes"
        data = owned.read_bytes()
        expected = pin(data)
        if original.exists():
            assert pin(original.read_bytes()) == expected, original
        rows.append({"original_path": str(original),
                     "owned_copy": owned.relative_to(HERE).as_posix(), **expected})
    assert len(rows) == len({row["owned_copy"] for row in rows})
    return {"schema": "i03-var08-postrun-external-proof-custody/v1",
            "records": rows, "original_tmp_optional_after_publication": True,
            "accepted_and_new_native_original_raw_still_mandatory": True}


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--dry"], ["--write"])
    if args == ["--write"]:
        assert not MAP.exists() and not COPIES.exists()
        COPIES.mkdir()
        for index, original in enumerate(paths(), 1):
            data = original.read_bytes()
            (COPIES / f"c{index:03d}.bytes").write_bytes(data)
        MAP.write_bytes(body(candidate()))
    else:
        assert MAP.read_bytes() == body(candidate())
    value = candidate()
    print(json.dumps({"records": len(value["records"]), "map": pin(MAP.read_bytes()),
                      "written": args == ["--write"]}, sort_keys=True))


if __name__ == "__main__":
    main()
