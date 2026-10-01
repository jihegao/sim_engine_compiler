"""Verify and freeze the exact D10-to-D11 four-mission control delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D10-var01-missions-v1.0.0" / "native-input.json"
PARENT_SHA = "6607991260e3f911d0121c7949443409a57937e95f80c7e4f3a2faa6ac20ba72"
INPUT = HERE / "native-input.json"
EXPECTED = ['MaterielPM', 'PMLocation', 'ProblemDescription', 'TaskBreakDown', 'Tasks']


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    doc = json.loads(path.read_bytes())
    return {t["name"]: t for t in doc["model"]["tables"]}


def main() -> None:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("accepted D10 parent differs")
    before, after = tables(PARENT), tables(INPUT)
    if set(before) != set(after):
        raise ValueError("unexpected table add/remove")
    changed = sorted(name for name in before if before[name] != after[name])
    if changed != EXPECTED:
        raise ValueError(f"unexpected changed tables: {changed}")
    result = {
        "schema": "simlox-d11-atim-control-parent-diff/v1", "parent_sha256": PARENT_SHA,
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
