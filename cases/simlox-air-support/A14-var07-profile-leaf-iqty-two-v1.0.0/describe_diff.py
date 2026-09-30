"""Seal the one-field A14.var07 negative input delta."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A14-profile-repeated-v1.0.1" / "profile-input.json"
PARENT_SHA = "11993115206c2176c45f83e4706ede703b5f1a994ed7c0ad737fe37c07c759cb"
INPUT_SHA = "0cf06efc8fc50f1ac2771e904dd7dd84dc503e4ee1a72b8fc1ce47e9e15c77cf"


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_bytes())["model"]["tables"]}


def main() -> None:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    child = HERE / "native-input.json"
    assert hashlib.sha256(child.read_bytes()).hexdigest() == INPUT_SHA
    a, b = tables(PARENT), tables(child)
    assert a.keys() == b.keys()
    changes = {name: {"before": a[name], "after": b[name]}
               for name in a if a[name] != b[name]}
    assert set(changes) == {"ProblemDescription", "OperationProfile"}
    op_before = a["OperationProfile"]["instances"][0]["rows"]
    op_after = b["OperationProfile"]["instances"][0]["rows"]
    cols = [c["name"] for c in a["OperationProfile"]["columns"]]
    assert a["OperationProfile"]["columns"] == b["OperationProfile"]["columns"]
    altered = [(i, col, x, y) for i, (r0, r1) in enumerate(zip(op_before, op_after, strict=True))
               for col, x, y in zip(cols, r0, r1, strict=True) if x != y]
    assert altered == [(2, "IQTY", 1, 2)], altered
    result = {"schema": "simlox-a14-var07-leaf-iqty-two-exact-diff/v1",
              "parent_sha256": PARENT_SHA, "input_sha256": INPUT_SHA,
              "changed_tables": changes, "operation_profile_cell_delta": altered}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
