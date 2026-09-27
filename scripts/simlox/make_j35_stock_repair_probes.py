"""Build isolated PRU/SPRU spare competition probes from validated phase6 B.

These are native mechanism tests, not a reclassification of J35's 403 LRU.
Faults remain random; a fixed RSEED is only a reproducible native first-sample
trigger after ENLOG confirms actual times. It is not a shared Rust RNG tape.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("C:/Users/user/Documents/Codex/2026-09-26/simlox-j35-event-parity/workspace/evidence/phase6/b-zero-stock-repair/b-zero-stock-repair.json")
SOURCE_SHA = "1b01a20111aed6c6fc96339c512147c862178967c01e67421eb380379b45f8d0"
OUT = ROOT / "data/local/j35-contract-probes"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(model: dict, name: str) -> dict:
    return next(t for t in model["model"]["tables"] if t["name"] == name)


def rows(t: dict) -> list[dict]:
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for instance in t["instances"] for row in instance["rows"]]


def change(t: dict, selector, **updates) -> None:
    names = [c["name"] for c in t["columns"]]
    for instance in t["instances"]:
        for raw in instance["rows"]:
            if selector(dict(zip(names, raw))):
                for key, value in updates.items():
                    raw[names.index(key)] = value


def diff(source: dict, target: dict) -> dict:
    result = {}
    for original in source["model"]["tables"]:
        name = original["name"]
        a, b = rows(original), rows(table(target, name))
        if a != b:
            result[name] = [
                {"row": i, "field": key, "before": old.get(key), "after": new.get(key)}
                for i, (old, new) in enumerate(zip(a, b))
                for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)
            ]
    return result


def make(stem: str, *, system_count: int, repair_enabled: bool) -> None:
    if sha256(SOURCE) != SOURCE_SHA:
        raise ValueError("phase6 source fingerprint changed")
    source = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    model = copy.deepcopy(source)
    control = rows(table(model, "Control"))[0]
    if "RSEED" not in control:
        raise ValueError("Native RSEED field absent; do not claim fixed seed")
    # jexport canonicalizes RSEED as text; preserve exact table roundtrip.
    change(table(model, "Control"), lambda r: True, RSEED="1", NREPS=1, ENLOG="Y")
    # Keep the validated phase6 hierarchy failure rates: native conversion
    # rejects a mother FRT=0 with a positive-FRT child (error #2050).
    change(table(model, "StockAllocation"), lambda r: r["IID"] == "B-TOP-PRU" and r["STID"] == "BASE", STSIZ=1)
    change(table(model, "SystemDeployment"), lambda r: True, QTYPS=system_count)
    change(table(model, "MissionType"), lambda r: True, NOS=system_count, MNOS=system_count)
    change(table(model, "ItemRepair"), lambda r: r["IID"] == "B-SECOND-SPRU", DIRPF=1 if repair_enabled else 0)
    assert len(rows(table(model, "Item"))) == 2
    assert [r["STSIZ"] for r in rows(table(model, "StockAllocation")) if r["IID"] == "B-TOP-PRU" and r["STID"] == "BASE"] == [1]
    assert all(r["STSIZ"] == 0 for r in rows(table(model, "StockAllocation")) if not (r["IID"] == "B-TOP-PRU" and r["STID"] == "BASE"))
    directory = OUT / stem
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stem}.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    provenance = {
        "source": str(SOURCE), "source_sha256": SOURCE_SHA,
        "input": str(path), "input_sha256": sha256(path),
        "changes_from_source": diff(source, model),
        "purpose": "one BASE top PRU spare shared by native systems; source FRT hierarchy, fixed RSEED=1 first sample; compare nonzero secondary repair return",
        "system_count": system_count, "repair_enabled": repair_enabled,
        "limitations": "native instance ordinal is not stable J35 tail; secondary SPRU transaction is not a fixed-Plan LRU transaction",
    }
    (directory / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(stem, provenance["input_sha256"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stem", choices=["p2c-one-no-repair", "p2c-one-repair", "p2c-two-no-repair", "p2c-two-repair", "p2c-one-repair-repeat", "p2c-two-repair-repeat"])
    args = parser.parse_args()
    cases = [
        ("p2c-one-no-repair", 1, False),
        ("p2c-one-repair", 1, True),
        ("p2c-two-no-repair", 2, False),
        ("p2c-two-repair", 2, True),
        ("p2c-one-repair-repeat", 1, True),
        ("p2c-two-repair-repeat", 2, True),
    ]
    for stem, count, enabled in cases:
        if args.stem is None or args.stem == stem:
            make(stem, system_count=count, repair_enabled=enabled)


if __name__ == "__main__":
    main()
