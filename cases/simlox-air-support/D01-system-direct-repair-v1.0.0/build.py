"""Derive a bounded stochastic system direct-repair D01 slice from A02."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
PARENT_SHA256 = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return matches[0]


def fields(t: dict) -> list[str]:
    return [column["name"] for column in t["columns"]]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def update(t: dict, **values: object) -> None:
    if len(rows(t)) != 1 or len(rows(t)[0]) != len(fields(t)) or set(values) - set(fields(t)):
        raise ValueError(f"unexpected {t['name']} shape or fields")
    for key, value in values.items():
        rows(t)[0][fields(t).index(key)] = value


def make_row(t: dict, **values: object) -> list:
    if set(values) - set(fields(t)):
        raise ValueError(f"unknown {t['name']} columns")
    return [values.get(field) for field in fields(t)]


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted A02 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    update(table(model, "ProblemDescription"), PDESC="D01 system-level direct repair: one aircraft, fixed 0.5 h repair, stochastic operational failure")
    update(table(model, "System"), FRT=300000)
    repair = table(model, "SystemRepair")
    if rows(repair):
        raise ValueError("parent SystemRepair is not empty")
    rows(repair).append(make_row(repair, SID="TEACH-AIR-01", STID="BASE-01", DIRPT=0.5, SURPT=0.0, DIRPF=1.0, SURPF=1.0))
    return doc


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--write", action="store_true")
    parsed = args.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if parsed.write:
        if OUTPUT.exists():
            raise FileExistsError(f"refusing to overwrite {OUTPUT}")
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen D01 input differs from generator")
    print(json.dumps({"case_id": "D01", "variant": "system-direct-repair", "parent_sha256": PARENT_SHA256, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
