"""Build related-PM MNOCC=2/3 candidates from accepted D10.var01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D10-var01-missions-v1.0.0" / "native-input.json"
PARENT_SHA = "6607991260e3f911d0121c7949443409a57937e95f80c7e4f3a2faa6ac20ba72"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build(cap: int) -> bytes:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted D10.var01 parent differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    pm = tables["MaterielPM"]
    names = [column["name"] for column in pm["columns"]]
    small = pm["instances"][0]["rows"][0]
    if small[names.index("PMID")] != "MS2" or small[names.index("PMINT")] != 2:
        raise ValueError("unexpected parent PM")
    small[names.index("MNOCC")] = cap
    large = copy.deepcopy(small)
    large[names.index("PMID")] = "MS3"
    large[names.index("DESCR")] = "Three-mission service includes MS2"
    large[names.index("PMINT")] = 3.0
    large[names.index("PMRID")] = "MS2"
    large[names.index("MNOCC")] = None
    pm["instances"][0]["rows"].append(large)
    tables["PMLocation"]["instances"][0]["rows"].append(
        ["MS3", "TEACH-AIR-01", "BASE-01", 1.0, None, None, "PM-MS3", None, None]
    )
    tables["Tasks"]["instances"][0]["rows"].append(
        ["PM-MS3", "One-hour three-mission service", None, None, None]
    )
    tables["TaskBreakDown"]["instances"][0]["rows"].append(
        ["PM-MS3", 1, "INSPECT", 1.0, None, None]
    )
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = (
        f"D11 related PM MS3 includes MS2; MS2 MNOCC={cap}"
    )
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    hashes = {}
    for cap in (2, 3):
        output = HERE / f"native-related-cap-{cap}.json"
        raw = build(cap)
        if args.write:
            if output.exists():
                raise FileExistsError(output)
            output.write_bytes(raw)
        elif output.read_bytes() != raw:
            raise ValueError(f"frozen related cap {cap} differs")
        hashes[str(cap)] = sha(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashes}))


if __name__ == "__main__":
    main()
