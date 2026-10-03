"""Seal the ASSY delta and its accepted structural reference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "F01-var01-two-three-level-v1.0.1/three-level-input.json"
REFERENCE = ROOT / "G01-var04-assy-structure-v1.0.0/native-input.json"
CHILD = HERE / "native-input.json"
OUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(left: Path, right: Path) -> dict:
    a_doc = json.loads(left.read_text(encoding="utf-8"))
    b_doc = json.loads(right.read_text(encoding="utf-8"))
    a = {t["name"]: t for t in a_doc["model"]["tables"]}
    b = {t["name"]: t for t in b_doc["model"]["tables"]}
    assert len(a) == len(a_doc["model"]["tables"])
    assert len(b) == len(b_doc["model"]["tables"])
    assert a.keys() == b.keys()
    changed = []
    for name in a:
        assert a[name]["columns"] == b[name]["columns"]
        if a[name]["instances"] != b[name]["instances"]:
            assert len(a[name]["instances"]) == len(b[name]["instances"]) == 1
            changed.append({"table": name, "before_rows": a[name]["instances"][0]["rows"],
                            "after_rows": b[name]["instances"][0]["rows"]})
    return {"left_sha256": sha(left), "right_sha256": sha(right), "changed_tables": changed,
            "unchanged_tables": len(a) - len(changed)}


def build() -> dict:
    structural = compare(PARENT, CHILD)
    rate = compare(REFERENCE, CHILD)
    assert [x["table"] for x in structural["changed_tables"]] == [
        "ProblemDescription", "Item", "ItemStructure", "ItemReplacement"]
    assert [x["table"] for x in rate["changed_tables"]] == [
        "ProblemDescription", "System", "Item"]
    assert structural["unchanged_tables"] == 27 and rate["unchanged_tables"] == 28
    return {"schema": "simlox-f01-var02-assy-exact-diffs/v1",
            "assy_from_f01_var01": structural, "rate_from_g01_var04": rate}


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        assert OUT.read_bytes() == raw
    else:
        OUT.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(), "changed_tables": 4}))


if __name__ == "__main__":
    main()
