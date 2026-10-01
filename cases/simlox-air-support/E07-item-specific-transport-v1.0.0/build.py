"""Derive one complete item-specific transport link from accepted E04 FAST."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E04-upstream-transport-fast-v1.0.0" / "native-input.json"
PARENT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
DICTIONARY_SHA = "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0"
OUTPUT = HERE / "native-input.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc, name):
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return found[0]


def build():
    if sha(PARENT) != PARENT_SHA or sha(DICTIONARY) != DICTIONARY_SHA:
        raise ValueError("accepted parent or installed table dictionary changed")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    description = table(doc, "ProblemDescription")
    description["instances"][0]["rows"][0][0] = "E07 item-specific FAST route overrides general two-hour transport with one-hour down and three-hour up"
    general = table(doc, "StationStructure")
    general_columns = {column["name"]: column for column in general["columns"]}
    item_column = next(column for column in table(doc, "Item")["columns"] if column["name"] == "IID")
    names = ("IID", "STID", "MSTID", "TFRMS", "TTOMS", "DFRAC", "OPOL", "PFRMS", "PTOMS", "NOTE")
    columns = [copy.deepcopy(item_column if name == "IID" else general_columns[name]) for name in names]
    columns[0]["key"] = columns[1]["key"] = columns[2]["key"] = True
    row = ["TEACH-LRU-01", "BASE-01", "DEPOT-01", 1.0, 3.0, 1.0, "FAST", None, None, None]
    link = {"columns": columns, "instances": [{"instance_name": "", "rows": [row]}], "name": "ItemStationStructure"}
    doc["model"]["tables"].append(link)
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen E07 input differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
