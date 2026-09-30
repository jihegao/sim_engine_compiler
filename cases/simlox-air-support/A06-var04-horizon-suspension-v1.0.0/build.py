"""Stop accepted A06 extendable mission at 12.5 inside observed second gap."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A06-extendable-prepared-gap-v1.0.0" / "native-input.json"
PARENT_SHA = "5b53aa2cbaacb283e15bb7e7852afba215ec7fe5961434c3c2ce6f06768125c7"
OUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} structure")
    match = matches[0]
    return [c["name"] for c in match["columns"]], match["instances"][0]["rows"]


def replace_field(doc: dict, name: str, field: str, before: object,
                  after: object, count: int) -> None:
    columns, rows = table(doc, name)
    if len(rows) != count or field not in columns:
        raise ValueError(f"unexpected {name}.{field} structure")
    index = columns.index(field)
    if any(row[index] != before for row in rows):
        raise ValueError(f"unexpected {name}.{field} value")
    for row in rows:
        row[index] = after


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted A06 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    replace_field(doc, "ProblemDescription", "PDESC",
                  "A06 extendable four-hour prepared-replacement probe",
                  "A06 extendable mission stopped during second suspension", 1)
    replace_field(doc, "Control", "SIMPE", 16.0, 12.5, 1)
    replace_field(doc, "Control", "RCEND", 16.0, 12.5, 1)
    replace_field(doc, "ResultCollection", "RCEND", 16.0, 12.5, 2)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"native_input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
