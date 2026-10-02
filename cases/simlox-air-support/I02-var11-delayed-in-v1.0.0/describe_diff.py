"""Verify exact TFDT-only business delta from accepted I02.var01."""
import hashlib
import json
from pathlib import Path
from build import HERE, PARENT, PARENT_SHA


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    found = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(found) == len(doc["model"]["tables"])
    return found


def main():
    assert sha(PARENT) == PARENT_SHA
    before, after = tables(PARENT), tables(HERE / "native-input.json")
    assert set(before) == set(after) and len(before) == 32
    changed = sorted(n for n in before if before[n] != after[n])
    assert changed == ["ItemTransfer", "ProblemDescription"]
    assert before["ItemTransfer"]["columns"] == after["ItemTransfer"]["columns"]
    old, new = [t["ItemTransfer"]["instances"][0]["rows"][0] for t in (before, after)]
    names = [c["name"] for c in before["ItemTransfer"]["columns"]]
    delta = [(names[i], a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b]
    assert delta == [("TFDT", 0.0, 2.0)]
    assert before["ProblemDescription"]["columns"] == after["ProblemDescription"]["columns"]
    assert len(before["ProblemDescription"]["instances"][0]["rows"]) == 1
    result = {"schema": "simlox-i02-var11-delayed-in-exact-diff/v1", "parent_sha256": PARENT_SHA,
              "child_sha256": sha(HERE / "native-input.json"), "changed_tables": changed,
              "unchanged_table_count": 30, "item_transfer_delta": delta,
              "description_delta": [before["ProblemDescription"]["instances"][0]["rows"][0][0],
                                    after["ProblemDescription"]["instances"][0]["rows"][0][0]]}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    out = HERE / "exact-diff.json"
    if out.exists():
        assert out.read_bytes() == raw, "frozen diff differs"
    else:
        out.write_bytes(raw)
    print(json.dumps({"exact_diff_sha256": sha(out), "child_sha256": result["child_sha256"]}))


if __name__ == "__main__":
    main()
