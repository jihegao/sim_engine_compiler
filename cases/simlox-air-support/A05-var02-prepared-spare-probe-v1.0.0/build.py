"""Add accepted B01 fixed preparation to the A05 three-aircraft replacement control."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-var02-distinct-spare-probe-v1.0.0" / "native-input.json"
PARENT_SHA = "aab1e4050a107e8490716a9306d9eb461b5c4a0c88430c157a2699afc5a120bb"
PREP_SOURCE = HERE.parent / "B01-fixed-preparation-v1.0.1" / "native-input.json"
PREP_SOURCE_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
OUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} structure")
    return found[0]


def set_one(doc: dict, name: str, field: str, before: object, after: object) -> None:
    t = table(doc, name)
    columns = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or field not in columns or rows[0][columns.index(field)] != before:
        raise ValueError(f"unexpected {name}.{field}")
    rows[0][columns.index(field)] = after


def build() -> dict:
    parent_raw = PARENT.read_bytes()
    prep_raw = PREP_SOURCE.read_bytes()
    if sha(parent_raw) != PARENT_SHA or sha(prep_raw) != PREP_SOURCE_SHA:
        raise ValueError("accepted source fingerprint differs")
    doc = copy.deepcopy(json.loads(parent_raw))
    prep = json.loads(prep_raw)
    set_one(doc, "ProblemDescription", "PDESC",
            "A05 continuous four-hour three-aircraft distinct-spare probe",
            "A05 continuous four-hour three-aircraft fixed-preparation probe")
    for name in ("MissionPreparation", "Tasks"):
        own = table(doc, name)
        source = table(prep, name)
        if own["columns"] != source["columns"] or own["instances"][0]["rows"]:
            raise ValueError(f"unexpected {name} target")
        if len(source["instances"][0]["rows"]) != 1:
            raise ValueError(f"unexpected B01 {name} source")
        own["instances"][0]["rows"] = copy.deepcopy(source["instances"][0]["rows"])
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
