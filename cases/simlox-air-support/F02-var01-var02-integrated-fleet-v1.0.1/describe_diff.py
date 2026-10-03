"""Freeze exact authored table changes from D05 and the paired failure switch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, ROOT, SOURCES


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def main() -> None:
    parent_path = ROOT / SOURCES["D05"][0]
    if digest(parent_path) != SOURCES["D05"][1]:
        raise ValueError("D05 parent changed")
    parent = json.loads(parent_path.read_bytes())
    arms = {arm: json.loads((HERE / f"{arm}-input.json").read_bytes()) for arm in ("deterministic", "risk")}
    old = tables(parent)
    out = {"schema": "simlox-f02-paired-exact-authored-diff/v1", "parent": {"path": SOURCES["D05"][0], "sha256": digest(parent_path)}, "arms": {}}
    for arm, doc in arms.items():
        new = tables(doc)
        if set(new) - set(old) != {"MissionTurnround"} or set(old) - set(new):
            raise ValueError(f"table set changed in {arm}: {set(old) ^ set(new)}")
        changed = {}
        for name in sorted(new):
            before = old.get(name)
            if before != new[name]:
                if before and [c["name"] for c in before["columns"]] != [c["name"] for c in new[name]["columns"]]:
                    raise ValueError(f"columns changed in {name}")
                changed[name] = {"before": before["instances"][0]["rows"] if before else None, "after": new[name]["instances"][0]["rows"]}
        out["arms"][arm] = {"input_sha256": digest(HERE / f"{arm}-input.json"), "changed_tables": changed}
    a, b = arms["deterministic"], arms["risk"]
    differences = []
    for name in sorted(tables(a)):
        left, right = tables(a)[name], tables(b)[name]
        for i, (lr, rr) in enumerate(zip(left["instances"][0]["rows"], right["instances"][0]["rows"])):
            for j, (lv, rv) in enumerate(zip(lr, rr)):
                if lv != rv:
                    differences.append({"table": name, "row": i, "column": left["columns"][j]["name"], "deterministic": lv, "risk": rv})
    if differences != [{"table": "MissionType", "row": 1, "column": "MFF", "deterministic": 0.0, "risk": 1.0}]:
        raise ValueError(f"unexpected paired differences: {differences}")
    out["paired_differences"] = differences
    raw = (json.dumps(out, indent=2, ensure_ascii=False) + "\n").encode()
    path = HERE / "exact-diff.json"
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("frozen exact diff changed")
    else:
        path.write_bytes(raw)
    print(json.dumps({"exact_diff_sha256": hashlib.sha256(raw).hexdigest(), "changed_tables": {arm: sorted(out["arms"][arm]["changed_tables"]) for arm in out["arms"]}}))


if __name__ == "__main__":
    main()
