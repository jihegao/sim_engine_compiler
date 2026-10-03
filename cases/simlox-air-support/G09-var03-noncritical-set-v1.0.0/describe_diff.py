"""Recompute exact NCID/QTYNC1 delta from accepted G09.var01."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, make


def mapped(doc: dict) -> dict:
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    if len(tables) != len(doc["model"]["tables"]):
        raise ValueError("duplicate table")
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    before, after = mapped(json.loads(PARENT.read_bytes())), mapped(make())
    changed = {n: {"before": before.get(n), "after": after.get(n)}
               for n in after if before.get(n) != after.get(n)}
    if set(changed) != {"ProblemDescription", "MaterielOperationalModes",
                        "RBDNonCriticalSet", "RBDNonCriticalSetItems"}:
        raise ValueError(f"unexpected changed tables: {sorted(changed)}")
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G09",
              "variant_id": "G09.var03", "parent_sha256": PARENT_SHA,
              "input_sha256": hashlib.sha256((HERE / "nc-b1-input.json").read_bytes()).hexdigest(),
              "changed": changed}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
