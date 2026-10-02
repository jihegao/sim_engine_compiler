"""Freeze two child deltas and the isolated extra MISSIONS interval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D14-var03-post-reinstallation-pm-v1.0.0" / "native-input-monitored.json"
ARMS = ("ophours-only", "missions-plus-ophours")
OUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_bytes())["model"]["tables"]}


def compare(a: dict, b: dict) -> dict:
    return {name: {"before": a.get(name), "after": b.get(name)}
            for name in sorted(set(a) | set(b)) if a.get(name) != b.get(name)}


def main() -> None:
    parent = tables(PARENT)
    children = {arm: HERE / f"native-input-{arm}.json" for arm in ARMS}
    bodies = {arm: tables(path) for arm, path in children.items()}
    contrasts = compare(bodies[ARMS[0]], bodies[ARMS[1]])
    if sorted(contrasts) != ["MaterielPMInterval", "ProblemDescription"]:
        raise ValueError(f"unexpected arm contrast: {sorted(contrasts)}")
    doc = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "D14",
           "variant_id": "D14.var05", "parent_sha256": sha(PARENT),
           "arms": {arm: {"input_sha256": sha(path), "changed": compare(parent, bodies[arm])}
                    for arm, path in children.items()}, "arm_contrast": contrasts}
    raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes() != raw:
            raise ValueError("frozen exact diff differs")
    else:
        OUT.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(),
                      "arm_contrast_tables": sorted(contrasts),
                      "changed_tables": {arm: sorted(doc["arms"][arm]["changed"]) for arm in ARMS}}))


if __name__ == "__main__":
    main()
