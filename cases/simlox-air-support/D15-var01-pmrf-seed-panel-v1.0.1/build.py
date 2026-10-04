"""Freeze paired D15 PMRF inputs for the prespecified seed panel 2 through 6."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "D15-var01-pmrf-scheduled-v1.0.0"
BASE_SHA = {
    "certain": "4c047fad6e2a36463729959d4334c5107e1f62bbad0a055af51738dc28af5119",
    "fractional": "ed0b027ed5b738e119ba4cb48c82a55926f0beca5e0e787952b7d7c3d0fd8632",
}
SEEDS = (2, 3, 4, 5, 6)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def put(tables: list[dict], name: str, column: str, value: object) -> None:
    found = [t for t in tables if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1 or len(found[0]["instances"][0]["rows"]) != 1:
        raise ValueError((name, "unexpected shape"))
    table = found[0]
    names = [c["name"] for c in table["columns"]]
    table["instances"][0]["rows"][0][names.index(column)] = value


def make(arm: str, seed: int) -> dict:
    if arm not in BASE_SHA or seed not in SEEDS:
        raise ValueError((arm, seed))
    source = (BASE / f"{arm}-input.json").read_bytes()
    if sha(source) != BASE_SHA[arm]:
        raise ValueError("diagnostic source changed")
    doc = copy.deepcopy(json.loads(source))
    tables = doc["model"]["tables"]
    put(tables, "Control", "RSEED", str(seed))
    put(tables, "ProblemDescription", "PDESC", f"D15.var01 prespecified seed{seed} CAL24 PMRF {1.0 if arm == 'certain' else 0.5}")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output = {}
    for seed in SEEDS:
        for arm in ("certain", "fractional"):
            key = f"seed{seed}-{arm}"
            raw = (json.dumps(make(arm, seed), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            path = HERE / f"{key}-input.json"
            if args.write:
                if path.exists():
                    raise FileExistsError(path)
                path.write_bytes(raw)
            elif path.read_bytes() != raw:
                raise ValueError(f"frozen input differs: {key}")
            output[key] = sha(raw)
    print(json.dumps({"base_sha256": BASE_SHA, "inputs": output}))


if __name__ == "__main__":
    main()
