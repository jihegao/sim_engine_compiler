"""Build a matched-seed subsystem quantity/environment frequency panel."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G12-var01-two-subsystems-v1.0.0" / "native-input.json"
PARENT_SHA = "25490c7da29019183ddc25aaed7953741bfc67261d535419941d56fc59767c7b"
VARIANTS = ("baseline", "qty-two", "env-two")
SEEDS = tuple(range(2, 14))


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def row(doc: dict, name: str, key: object) -> list:
    matches = [r for r in table(doc, name)["instances"][0]["rows"] if r[0] == key]
    if len(matches) != 1:
        raise ValueError(f"unexpected {name} row {key}")
    return matches[0]


def put(doc: dict, name: str, key: object, field: str, value: object) -> None:
    t = table(doc, name)
    row(doc, name, key)[[c["name"] for c in t["columns"]].index(field)] = value


def build(variant: str, seed: int) -> dict:
    if variant not in VARIANTS or seed not in SEEDS:
        raise ValueError("outside frozen panel")
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G12.var01 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    description = table(doc, "ProblemDescription")["instances"][0]["rows"]
    if description != [["G12.var01 two linked subsystems with leaf calendar PM"]]:
        raise ValueError("parent description differs")
    description[0][0] = f"G12.var02 seed {seed} 256-replication {variant} subsystem frequency"
    control = row(doc, "Control", 1)
    cols = [c["name"] for c in table(doc, "Control")["columns"]]
    if (control[cols.index("SIMPE")], control[cols.index("ENPM")], control[cols.index("ENLOG")]) != (60.0, "Y", "Y"):
        raise ValueError("parent horizon or PM/log differs")
    control[cols.index("NREPS")] = 256
    control[cols.index("RSEED")] = str(seed)
    if row(doc, "System", "TEACH-AIR-01")[3] != 0 or row(doc, "System", "TEACH-SUB-B")[3] != 0:
        raise ValueError("parent failure rate differs")
    put(doc, "System", "TEACH-AIR-01", "FRT", None)
    put(doc, "System", "TEACH-SUB-B", "FRT", 50000)
    repair = table(doc, "SystemRepair")
    if repair["instances"][0]["rows"]:
        raise ValueError("parent system repair unexpectedly populated")
    repair["instances"][0]["rows"].append(
        ["TEACH-SUB-B", "BASE-01", 0.5, 0.5, 1.0, 1.0, None, None, None, None, None, None, None, None, None])
    structure = table(doc, "SystemStructure")
    b = row(doc, "SystemStructure", "TEACH-SUB-B")
    scols = [c["name"] for c in structure["columns"]]
    if (b[scols.index("MSID")], b[scols.index("QTYPM")], b[scols.index("ENVF")]) != ("TEACH-AIR-01", 1, 1.0):
        raise ValueError("parent subsystem B relation differs")
    if variant == "qty-two":
        b[scols.index("QTYPM")] = 2
    elif variant == "env-two":
        b[scols.index("ENVF")] = 2.0
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    encoded = (json.dumps(build(args.variant, args.seed), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(json.dumps({"seed": args.seed, "variant": args.variant,
                      "parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(encoded).hexdigest()}))


if __name__ == "__main__":
    main()
