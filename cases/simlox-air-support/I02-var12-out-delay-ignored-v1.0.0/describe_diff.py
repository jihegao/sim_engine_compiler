"""Check that only the OUT row's TFDT changes, plus description."""
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
    names = [c["name"] for c in before["ItemTransfer"]["columns"]]
    old, new = [t["ItemTransfer"]["instances"][0]["rows"] for t in (before, after)]
    assert len(old) == len(new) == 2 and old[0] == new[0]
    delta = [(names[i], a, b) for i, (a, b) in enumerate(zip(old[1], new[1])) if a != b]
    assert delta == [("TFDT", 0.0, 2.0)]
    assert before["ProblemDescription"]["columns"] == after["ProblemDescription"]["columns"]
    result = {"schema": "simlox-i02-var12-out-delay-exact-diff/v1", "parent_sha256": PARENT_SHA,
              "child_sha256": sha(HERE / "native-input.json"), "changed_tables": changed,
              "unchanged_table_count": 30, "fixed_in_row": old[0], "out_transfer_delta": delta,
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
