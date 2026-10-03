"""Fuse accepted G01 LRU/SRU structure with E05's repeat-demand exposure."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "G01-var01-lru-sru-v1.0.1" / "native-input.json"
PARENT_SHA = "9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9"
REFERENCE = ROOT / "E05-local-repair-reissue-v1.0.0" / "native-input.json"
REFERENCE_SHA = "ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca"
OUTPUT = HERE / "native-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table/instances")
    return found[0]


def rows(t: dict) -> list[dict]:
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for row in t["instances"][0]["rows"]]


def set_cell(doc: dict, name: str, key: str | None, target: str | None, field: str, expected: object, value: object) -> None:
    t = table(doc, name)
    names = [c["name"] for c in t["columns"]]
    matches = [row for row in t["instances"][0]["rows"] if key is None or row[names.index(key)] == target]
    if len(matches) != 1 or matches[0][names.index(field)] != expected:
        raise ValueError(f"unexpected {name}.{field} source")
    matches[0][names.index(field)] = value


def build() -> dict:
    if sha(PARENT) != PARENT_SHA or sha(REFERENCE) != REFERENCE_SHA:
        raise ValueError("accepted source fingerprint differs")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    system_rate = rows(table(ref, "System"))[0]["FRT"]
    item_rate = rows(table(ref, "Item"))[0]["FRT"]
    if system_rate != item_rate or system_rate != 450000:
        raise ValueError("E05 reference rate differs")
    set_cell(doc, "ProblemDescription", None, None, "PDESC", "G01.var01 traditional LRU/SRU chain with local replacements", "F01.var01 integrated nested LRU/SRU repair and local reissue")
    set_cell(doc, "System", "SID", "TEACH-AIR-01", "FRT", 300000, system_rate)
    set_cell(doc, "Item", "IID", "TEACH-LRU-01", "FRT", 300000, item_rate)
    set_cell(doc, "Item", "IID", "TEACH-SRU-01", "FRT", 300000, item_rate)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen native input differs")
    print(json.dumps({"input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
