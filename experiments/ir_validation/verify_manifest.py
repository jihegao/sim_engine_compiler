#!/usr/bin/env python3
"""Verify the manifest's delivered file subset, excluding build-only metadata.

With a git checkout, also require every listed file to be tracked. In the
original blob-materialized workspace, --inventory accepts an explicit JSON
list of repository paths so existence alone cannot admit transfer scratch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

HERE = Path(__file__).resolve().parent


def check_manifest(root: Path, manifest: dict, inventory: set[str] | None = None) -> dict:
    root = root.resolve()
    errors = []
    checked = 0
    for relative, metadata in manifest["files"].items():
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or str(path) != relative:
            errors.append({"path": relative, "error": "invalid relative path"})
            continue
        if path.name.endswith(".base64") or any(part in {"target", "__pycache__"} for part in path.parts):
            errors.append({"path": relative, "error": "transient/build file in delivery inventory"})
            continue
        if inventory is not None and relative not in inventory:
            errors.append({"path": relative, "error": "not in repository inventory"})
            continue
        local = root / relative
        if not local.resolve().is_relative_to(root) or not local.is_file():
            errors.append({"path": relative, "error": "missing or out-of-root file"})
            continue
        data = local.read_bytes()
        if len(data) != metadata["bytes"] or hashlib.sha256(data).hexdigest() != metadata["sha256"]:
            errors.append({"path": relative, "error": "size or SHA256 mismatch"})
            continue
        checked += 1
    return {"verified_files": checked, "listed_files": len(manifest["files"]),
            "repository_inventory_checked": inventory is not None,
            "passed": not errors, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE.parents[1])
    parser.add_argument("--manifest", type=Path, default=HERE / "validation_manifest.json")
    parser.add_argument("--inventory", type=Path, help="JSON array of repository paths for a source snapshot")
    args = parser.parse_args()
    inventory = None
    if args.inventory:
        inventory = set(json.loads(args.inventory.read_text()))
    elif (args.root / ".git").exists():
        result = subprocess.run(["git", "ls-files", "-z"], cwd=args.root,
                                capture_output=True, text=True, check=True)
        inventory = set(result.stdout.split("\0")) - {""}
    result = check_manifest(args.root, json.loads(args.manifest.read_text()), inventory)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
