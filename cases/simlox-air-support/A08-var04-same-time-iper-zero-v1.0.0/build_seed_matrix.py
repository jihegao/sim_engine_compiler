"""Freeze 32 one-replication seed inputs from the A08.var04 aggregate source."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "native-input.json"
BASE_SHA = "bae76ba5a88871129fb2669a8d04744745b8831f11d0dec96c7594d621793485"
MANIFEST = HERE / "seed-matrix-v1.json"
INPUTS = HERE / "seed-inputs"
SEEDS = tuple(range(1, 33))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def set_one(doc: dict, name: str, field: str, before: object, after: object) -> None:
    table, = (t for t in doc["model"]["tables"] if t["name"] == name)
    instance, = table["instances"]
    columns = [c["name"] for c in table["columns"]]
    row, = instance["rows"]
    if field not in columns or row[columns.index(field)] != before:
        raise ValueError(f"unexpected {name}.{field}")
    row[columns.index(field)] = after


def input_bytes(seed: int) -> bytes:
    if seed not in SEEDS:
        raise ValueError("seed outside frozen matrix")
    raw = BASE.read_bytes()
    if sha(raw) != BASE_SHA:
        raise ValueError("A08 aggregate source fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    set_one(doc, "Control", "NREPS", 32, 1)
    set_one(doc, "Control", "RSEED", "1", str(seed))
    set_one(doc, "ProblemDescription", "PDESC",
            "A08.var04 three simultaneous missions at hour 8, 32 replications",
            f"A08.var04 same-time seed {seed:02d}, one replication")
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def manifest_bytes() -> bytes:
    result = {"schema": "simlox-a08-var04-seed-matrix/v1",
              "parent_input_sha256": BASE_SHA, "seeds": [
                  {"seed": seed, "input_sha256": sha(input_bytes(seed)),
                   "input_name": f"seed-{seed:02d}.json"} for seed in SEEDS],
              "publication_state": "not_published"}
    return (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--write-inputs", action="store_true")
    args = parser.parse_args()
    raw = manifest_bytes()
    if args.write_manifest:
        if MANIFEST.exists():
            raise FileExistsError(MANIFEST)
        MANIFEST.write_bytes(raw)
    elif MANIFEST.read_bytes() != raw:
        raise ValueError("frozen seed manifest differs")
    if args.write_inputs:
        INPUTS.mkdir(exist_ok=True)
        for seed in SEEDS:
            path = INPUTS / f"seed-{seed:02d}.json"
            expected = input_bytes(seed)
            if path.exists():
                if path.read_bytes() != expected:
                    raise ValueError(f"existing seed input differs: {path}")
            else:
                path.write_bytes(expected)
    print(json.dumps({"manifest_sha256": sha(raw), "seeds": len(SEEDS)}))


if __name__ == "__main__":
    main()
