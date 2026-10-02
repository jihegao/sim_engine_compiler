"""Freeze the one-field model delta from accepted D14.var01."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D14-var01-monitored-item-pm-v1.0.1" / "native-input-monitored.json"
INPUT = HERE / "native-input.json"
OUT = HERE / "exact-diff.json"


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_bytes())["model"]["tables"]}


def main() -> None:
    before, after = tables(PARENT), tables(INPUT)
    changes = {name: {"before": before.get(name), "after": after.get(name)}
               for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)}
    if sorted(changes) != ["MaterielPM", "ProblemDescription"]:
        raise ValueError("unexpected changed tables")
    old = changes["MaterielPM"]["before"]
    new = changes["MaterielPM"]["after"]
    fields = [c["name"] for c in old["columns"]]
    a, b = old["instances"][0]["rows"][0], new["instances"][0]["rows"][0]
    assert [(fields[i], a[i], b[i]) for i in range(len(fields)) if a[i] != b[i]] == [("MID", "TEACH-LRU-01", "POS-A")]
    data = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "D14",
            "variant_id": "D14.var04", "parent_sha256": hashlib.sha256(PARENT.read_bytes()).hexdigest(),
            "input_sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(), "changed": changes}
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes() != raw:
            raise ValueError("frozen exact diff differs")
    else:
        OUT.write_bytes(raw)
    print(json.dumps({"changed_tables": sorted(changes), "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
