"""Verify and freeze the exact D11.var03 drift delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
INPUT = HERE / "native-input.json"
EXPECTED = ['MaterielPM', 'OperationProfile', 'ProblemDescription']


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
        "schema": "simlox-d11-enreg-drift-parent-diff/v1", "parent_sha256": PARENT_SHA,
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
