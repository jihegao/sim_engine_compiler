"""Freeze-time owned source inventory; default is read-only dry output."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "source-inventory.json"
EXCLUDED_DIRS = {"runs", "transport-evidence", "test-output", "__pycache__"}
EXCLUDED_REVIEW_PREFIXES = (
    "preflight-", "independent-prelaunch", "independent-control-postrun-go",
    "independent-postrun", "independent-content", "independent-staged", "independent-remote",
)


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(HERE).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def candidate() -> bytes:
    rows = []
    for path in HERE.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in path.relative_to(HERE).parts):
            continue
        rel = path.relative_to(HERE).as_posix()
        if rel == OUT.name or rel.startswith("prelaunch-manifest-"):
            continue
        if rel.startswith("review/") and path.name.startswith(EXCLUDED_REVIEW_PREFIXES):
            continue
        rows.append(pin(path))
    rows.sort(key=lambda item: item["path"])
    assert len({row["path"] for row in rows}) == len(rows)
    return (json.dumps({"schema": "i03-var03-owned-prelaunch-source-inventory/v1",
                        "source_files": rows}, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = candidate()
    if args.write:
        assert not OUT.exists(), "source inventory already exists; preserve and version a failed freeze"
        OUT.write_bytes(data)
    print(json.dumps({"written": args.write, "source_files": len(json.loads(data)["source_files"]),
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
