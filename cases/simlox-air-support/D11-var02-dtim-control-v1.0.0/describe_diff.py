"""Verify and freeze the exact D11.var02 control delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D11-var01-atim-control-v1.0.0" / "native-input.json"
PARENT_SHA = "94c0addbaff610b656b25dd328949ea9710ab9a593cafebe488f7bfca665ead8"
INPUT = HERE / "native-input.json"
EXPECTED = ['OperationProfile', 'ProblemDescription']


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    doc = json.loads(path.read_bytes())
    return {t["name"]: t for t in doc["model"]["tables"]}


def main() -> None:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("frozen D11 parent differs")
    before, after = tables(PARENT), tables(INPUT)
    if set(before) != set(after):
        raise ValueError("unexpected table add/remove")
    changed = sorted(name for name in before if before[name] != after[name])
    if changed != EXPECTED:
        raise ValueError(f"unexpected changed tables: {changed}")
    result = {
        "schema": "simlox-d11-dtim-control-parent-diff/v1", "parent_sha256": PARENT_SHA,
        "child_sha256": sha(INPUT), "changed_tables": changed,
        "unchanged_tables": len(before) - len(changed),
        "changes": {name: {"before": before[name]["instances"][0]["rows"],
                           "after": after[name]["instances"][0]["rows"]} for name in changed},
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "exact-diff.json"
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    if not path.exists():
        path.write_bytes(raw)
    print(json.dumps({"changed_tables": changed, "unchanged_tables": result["unchanged_tables"],
                      "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
