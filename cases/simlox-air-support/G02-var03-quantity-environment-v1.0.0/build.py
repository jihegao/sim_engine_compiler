"""Build controlled G02.var03 QTYPM/ENVF frequency-propagation probes."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G02-var01-position-modes-v1.0.0" / "native-input.json"
PARENT_SHA = "5ef40eb302544e551282dd7dd3617a6ae160954f600dea605f26140ea551a19e"
VARIANTS = ("baseline", "qty-two", "env-two")


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return matches[0]


def row(table: dict, key: str) -> list:
    rows = table["instances"][0]["rows"]
    matches = [r for r in rows if r[0] == key]
    if len(matches) != 1:
        raise ValueError(f"unexpected row {key}")
    return matches[0]


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G02.var01 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    description = table(doc, "ProblemDescription")
    description_fields = [c["name"] for c in description["columns"]]
    description["instances"][0]["rows"][0][description_fields.index("PDESC")] = (
        f"G02.var03 256-replication {variant} frequency propagation control"
    )
    control = table(doc, "Control")
    control_fields = [c["name"] for c in control["columns"]]
    row(control, 1)[control_fields.index("NREPS")] = 256
    modes = table(doc, "FailureMode")
    mode_fields = [c["name"] for c in modes["columns"]]
    for name in ("FM-POS-A", "FM-POS-B"):
        row(modes, name)[mode_fields.index("FRQ")] = 50000.0
    structure = table(doc, "MaterielStructure")
    structure_fields = [c["name"] for c in structure["columns"]]
    pos_b = [r for r in structure["instances"][0]["rows"]
             if r[0] == "POS-B" and r[1] == "TEACH-AIR-01"]
    if len(pos_b) != 1 or pos_b[0][structure_fields.index("QTYPM")] != 1 \
            or pos_b[0][structure_fields.index("ENVF")] != 1.0:
        raise ValueError("unexpected parent POS-B structure")
    if variant == "qty-two":
        pos_b[0][structure_fields.index("QTYPM")] = 2
    elif variant == "env-two":
        pos_b[0][structure_fields.index("ENVF")] = 2.0
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    hashes = {}
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        output = HERE / f"{variant}-input.json"
        if args.write:
            if output.exists():
                raise FileExistsError(output)
            output.write_bytes(raw)
        elif output.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {variant}")
        hashes[variant] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs_sha256": hashes}))


if __name__ == "__main__":
    main()
