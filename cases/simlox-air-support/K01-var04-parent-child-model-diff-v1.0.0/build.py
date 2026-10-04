"""Build K01.var04 from the accepted A01 teaching model, preserving all other cells."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"


def table(doc, name):
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1, name
    return matches[0]


def cell(doc, name, column):
    t = table(doc, name)
    assert len(t["instances"]) == 1 and len(t["instances"][0]["rows"]) == 1
    names = [c["name"] for c in t["columns"]]
    return t["instances"][0]["rows"][0], names.index(column)


def build():
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA
    doc = json.loads(raw)
    description, di = cell(doc, "ProblemDescription", "PDESC")
    duration, ui = cell(doc, "MissionType", "DURN")
    mission_id, mi = cell(doc, "MissionType", "MTID")
    assert description[di] == "A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence"
    assert mission_id[mi] == "BASIC-MISSION" and duration[ui] == 2.0
    description[di] = "K01.var04 v1.0.0 A01-derived three-hour model comparison"
    duration[ui] = 3.0
    return doc


if __name__ == "__main__":
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "native-input.json"
    if target.exists():
        assert target.read_bytes() == raw, "frozen child input changed"
    else:
        target.write_bytes(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))
