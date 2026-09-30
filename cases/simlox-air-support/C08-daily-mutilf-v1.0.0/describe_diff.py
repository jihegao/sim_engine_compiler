"""Freeze exact parent/variant lineage for daily MUTILF controls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
LINKS = {
    "no-shift-control": (PARENT, ["ProblemDescription", "ResourceStationData"], "ResourceStationData.SHPID CREW-DAY to null"),
    "zero-budget": (HERE / "no-shift-control-input.json", ["ProblemDescription", "Resource"], "Resource.MUTILF null to 0"),
    "finite-budget": (HERE / "no-shift-control-input.json", ["ProblemDescription", "Resource"], "Resource.MUTILF null to 0.03125"),
    "station-override": (HERE / "finite-budget-input.json", ["ProblemDescription", "ResourceStationData"], "ResourceStationData.MUTILF null to 1"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_bytes())["model"]["tables"]}


def main() -> None:
    entries = {}
    for variant, (parent, expected, delta) in LINKS.items():
        child = HERE / f"{variant}-input.json"
        before, after = tables(parent), tables(child)
        assert before.keys() == after.keys()
        changed = sorted(n for n in before if before[n] != after[n])
        assert changed == expected
        assert all(before[n]["columns"] == after[n]["columns"] and len(before[n]["instances"]) == len(after[n]["instances"]) == 1 for n in changed)
        entries[variant] = {
            "parent": str(parent.relative_to(HERE.parent)) if parent == PARENT else parent.stem.removesuffix("-input"),
            "parent_sha256": sha(parent),
            "input_sha256": sha(child),
            "changed_tables": changed,
            "business_delta": delta,
            "unchanged_table_count": len(before) - len(changed),
        }
    a = tables(HERE / "no-shift-control-input.json")
    z = tables(HERE / "zero-budget-input.json")
    f = tables(HERE / "finite-budget-input.json")
    o = tables(HERE / "station-override-input.json")
    assert a["ResourceStationData"]["instances"][0]["rows"][0][9] is None
    assert [d["Resource"]["instances"][0]["rows"][0][6] for d in (a, z, f, o)] == [None, 0.0, 0.03125, 0.03125]
    assert [d["ResourceStationData"]["instances"][0]["rows"][0][4] for d in (a, z, f, o)] == [None, None, None, 1.0]
    result = {"schema": "simlox-c08-daily-mutilf-exact-diff/v1", "accepted_parent_sha256": sha(PARENT), "variants": entries}
    path = HERE / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(sha(path))


if __name__ == "__main__":
    main()
