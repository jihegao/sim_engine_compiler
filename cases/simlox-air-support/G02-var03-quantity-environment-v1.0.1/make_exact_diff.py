"""Verify and record the exact 36-input business changes from G02.var01."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G02-var01-position-modes-v1.0.0" / "native-input.json"
VARIANTS = ("baseline", "qty-two", "env-two")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1
    return matches[0]


def set_row(doc: dict, table_name: str, key: object, column: str, value: object) -> None:
    t = table(doc, table_name)
    fields = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    matches = [r for r in rows if r[0] == key]
    assert len(matches) == 1
    matches[0][fields.index(column)] = value


def set_description(doc: dict, seed: int, variant: str) -> None:
    set_row(doc, "ProblemDescription", table(doc, "ProblemDescription")["instances"][0]["rows"][0][0],
            "PDESC", f"G02.var03 seed {seed} 256-replication {variant} frequency propagation control")


def main() -> None:
    assert sha(PARENT) == "5ef40eb302544e551282dd7dd3617a6ae160954f600dea605f26140ea551a19e"
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    inputs = {}
    for seed in range(2, 14):
        inputs[str(seed)] = {}
        for variant in VARIANTS:
            run = HERE / "runs" / f"g02-var03-seed{seed:02d}-{variant}-20261002-01"
            input_path = run / "input.json"
            actual = json.loads(input_path.read_text(encoding="utf-8"))
            expected = copy.deepcopy(parent)
            set_description(expected, seed, variant)
            set_row(expected, "Control", 1, "NREPS", 256)
            set_row(expected, "Control", 256, "RSEED", str(seed))
            set_row(expected, "FailureMode", "FM-POS-A", "FRQ", 50000.0)
            set_row(expected, "FailureMode", "FM-POS-B", "FRQ", 50000.0)
            if variant != "baseline":
                t = table(expected, "MaterielStructure")
                fields = [c["name"] for c in t["columns"]]
                matches = [r for r in t["instances"][0]["rows"] if r[0] == "POS-B" and r[1] == "TEACH-AIR-01"]
                assert len(matches) == 1
                matches[0][fields.index("QTYPM" if variant == "qty-two" else "ENVF")] = 2 if variant == "qty-two" else 2.0
            assert expected == actual, (seed, variant)
            inputs[str(seed)][variant] = sha(input_path)
    result = {
        "schema": "simlox-g02-var03-seed-panel-exact-diff/v1",
        "parent_input_sha256": sha(PARENT),
        "parent_to_each_seed_baseline": [
            "ProblemDescription.PDESC: provenance includes seed and arm",
            "Control.NREPS: 1 -> 256",
            "Control.RSEED: 1 -> exact seed 2..13",
            "FailureMode.FM-POS-A.FRQ: 300000 -> 50000 per million OPHOURS",
            "FailureMode.FM-POS-B.FRQ: 600000 -> 50000 per million OPHOURS"
        ],
        "same_seed_baseline_to_qty_two": [
            "ProblemDescription.PDESC: provenance arm only",
            "MaterielStructure.POS-B.QTYPM: 1 -> 2"
        ],
        "same_seed_baseline_to_env_two": [
            "ProblemDescription.PDESC: provenance arm only",
            "MaterielStructure.POS-B.ENVF: 1.0 -> 2.0"
        ],
        "all_expected_inputs_equal_actual": True,
        "input_sha256_by_seed_and_arm": inputs
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
