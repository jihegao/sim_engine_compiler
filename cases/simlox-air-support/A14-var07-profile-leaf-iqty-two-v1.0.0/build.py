"""Build the A14.var07 ambiguous profile-leaf quantity input."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A14-profile-repeated-v1.0.1" / "profile-input.json"
PARENT_SHA = "11993115206c2176c45f83e4706ede703b5f1a994ed7c0ad737fe37c07c759cb"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def put(tab: dict, record: list, field: str, before: object, after: object) -> None:
    idx = [c["name"] for c in tab["columns"]].index(field)
    if record[idx] != before:
        raise ValueError(f"unexpected {tab['name']}.{field}: {record[idx]!r}")
    record[idx] = after


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A14.var06 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    pd = table(doc, "ProblemDescription")
    put(pd, pd["instances"][0]["rows"][0], "PDESC", "A14 repeated dependency v101 profile",
        "A14.var07 profile EXECUTE leaf IQTY=2 negative")
    op = table(doc, "OperationProfile")
    records = op["instances"][0]["rows"]
    columns = [c["name"] for c in op["columns"]]
    named = [dict(zip(columns, row, strict=True)) for row in records]
    targets = [row for row, values in zip(records, named, strict=True)
               if values["PRID"] == "A14-WAVE" and values["SPRID"] == "EXECUTE" and values["STIM"] == 8.0]
    if len(targets) != 1:
        raise ValueError("accepted EXECUTE leaf differs")
    put(op, targets[0], "IQTY", 1, 2)
    return doc


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "native-input.json"
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("frozen input differs")
    else:
        path.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
