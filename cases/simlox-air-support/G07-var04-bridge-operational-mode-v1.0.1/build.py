"""Give the bridge block its own 0.75-rate materiel operational mode."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G07-var03-bridge-failure-v1.0.0" / "brfirst-input.json"
PARENT_SHA = "b6c40f551355e63e7dc031311794b5dfe1fbda13164d4cffcfce12c1844e8dfd"
MODE = "G07-BR-75"


def rows(doc: dict, name: str) -> list[list]:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]["instances"][0]["rows"]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G07.var03 input changed")
    doc = copy.deepcopy(json.loads(raw))
    modes = rows(doc, "MaterielOperationalModes")
    bridge = rows(doc, "RBDBridge")
    if len(modes) != 6 or [r[:2] for r in modes] != [["TEACH-AIR-01", "G04-OPS"],
                                                      *[[f"POS-{x}", "G04-OPS"] for x in "ABCDE"]]:
        raise ValueError("accepted operational modes changed")
    if len(bridge) != 1 or bridge[0][2:7] != ["POS-E", "POS-A", "POS-B", "POS-C", "POS-D"]:
        raise ValueError("accepted bridge slots changed")
    if bridge[0][7:12] != ["G04-OPS"] * 5:
        raise ValueError("accepted bridge operation changed")
    rows(doc, "ProblemDescription")[0][0] = "G07.var04 BR B mode at 0.75 usage versus accepted full-rate"
    modes.append(["POS-B", MODE, None, None, 0.75, None])
    op_modes = rows(doc, "OperationalModes")
    if op_modes != [["G04-OPS", "Two-position mission RBD", None]]:
        raise ValueError("accepted mode definitions changed")
    op_modes.append([MODE, "Bridge block 0.75-rate usage", None])
    bridge[0][1] = "Bridge B 0.75-rate operating mode"
    bridge[0][9] = MODE  # BROPM; other four slots retain G04-OPS
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "br75-input.json"
    raw = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"br75": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
