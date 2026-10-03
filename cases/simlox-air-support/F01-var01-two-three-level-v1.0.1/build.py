"""Freeze matched two/three-level repair inputs from accepted E05 and G01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENTS = {
    "two": (ROOT / "E05-local-repair-reissue-v1.0.0/native-input.json", "ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca"),
    "three": (ROOT / "G01-var01-lru-sru-v1.0.1/native-input.json", "9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9"),
}
RATE = 1200000


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def set_cell(doc: dict, name: str, key: str | None, target: str | None, field: str, expected: object, value: object) -> None:
    t = table(doc, name)
    names = [c["name"] for c in t["columns"]]
    rows = [row for row in t["instances"][0]["rows"] if key is None or row[names.index(key)] == target]
    if len(rows) != 1 or rows[0][names.index(field)] != expected:
        raise ValueError(f"unexpected {name}.{field} parent")
    rows[0][names.index(field)] = value


def build(arm: str) -> dict:
    parent, digest = PARENTS[arm]
    if sha(parent) != digest:
        raise ValueError(f"accepted {arm} source changed")
    doc = copy.deepcopy(json.loads(parent.read_text(encoding="utf-8")))
    if arm == "two":
        set_cell(doc, "ProblemDescription", None, None, "PDESC", "E05 local LRU repair, stock return and second issue", "F01.var01 two-level system/LRU repeated local reissue")
        set_cell(doc, "System", "SID", "TEACH-AIR-01", "FRT", 450000, RATE)
        set_cell(doc, "Item", "IID", "TEACH-LRU-01", "FRT", 450000, RATE)
    elif arm == "three":
        set_cell(doc, "ProblemDescription", None, None, "PDESC", "G01.var01 traditional LRU/SRU chain with local replacements", "F01.var01 three-level system/LRU/SRU repeated local reissue")
        set_cell(doc, "System", "SID", "TEACH-AIR-01", "FRT", 300000, RATE)
        set_cell(doc, "Item", "IID", "TEACH-LRU-01", "FRT", 300000, RATE)
        set_cell(doc, "Item", "IID", "TEACH-SRU-01", "FRT", 300000, RATE)
    else:
        raise ValueError(arm)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for arm in PARENTS:
        path = HERE / f"{arm}-level-input.json"
        raw = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} input differs")
        print(json.dumps({"arm": arm, "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
