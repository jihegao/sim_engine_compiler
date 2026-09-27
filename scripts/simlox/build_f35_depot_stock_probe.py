"""Derive isolated F35 depot-stock probes from pinned canonical and SIMLOX inputs.

Only product-f35-part-0018 changes from zero to two units at the upper depot.
The SIMLOX candidate also adds the missing station link and an explicit zero
stock row at the lower station. It does not claim transport-policy equivalence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


EXPECTED = {
    "canonical": "a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d",
    "simlox": "e32bb75b94b44573d208fe415243c223de88802f1e3df99c8bd2ab47ff772e6a",
    "native_template": "a73c6295d5e93bf93d84d610ce89edfcde9d7d15c60c6c482a6756650055611f",
}
PRODUCT = "product-f35-part-0018"
UPPER_NODE = "support-org-dadui"
LOWER_NODE = "support-org-1783479792728"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def table(model: dict, name: str) -> dict:
    matches = [entry for entry in model["model"]["tables"] if entry["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {name} table, got {len(matches)}")
    return matches[0]


def rows(entry: dict) -> list[dict]:
    columns = [column["name"] for column in entry["columns"]]
    instances = entry["instances"]
    if len(instances) != 1:
        raise ValueError(f"expected one {entry['name']} instance")
    return [dict(zip(columns, row, strict=True)) for row in instances[0]["rows"]]


def append_row(entry: dict, row: dict) -> None:
    columns = [column["name"] for column in entry["columns"]]
    entry["instances"][0]["rows"].append([row.get(column) for column in columns])


def build_canonical(original: dict) -> dict:
    result = copy.deepcopy(original)
    nodes = {node["id"]: node for node in result["support_network"]["nodes"]}
    if set(nodes) != {UPPER_NODE, LOWER_NODE}:
        raise ValueError("unexpected F35 support nodes")
    if nodes[UPPER_NODE]["inventory"].get(PRODUCT) != 0:
        raise ValueError("upper stock is no longer zero")
    if nodes[LOWER_NODE]["inventory"].get(PRODUCT) != 0:
        raise ValueError("lower stock is no longer zero")
    routes = result["support_network"]["organization_graph"]["transport_policies"]
    if len(routes) != 1 or any(
        routes[0].get(key) != expected
        for key, expected in {
            "from_organization_node_id": UPPER_NODE,
            "to_organization_node_id": LOWER_NODE,
            "capacity": 1,
            "transport_time_hours": 2.0,
        }.items()
    ):
        raise ValueError("unexpected canonical transport route")
    nodes[UPPER_NODE]["inventory"][PRODUCT] = 2
    return result


def build_simlox(original: dict, native_template: dict, canonical: dict) -> tuple[dict, dict]:
    result = copy.deepcopy(original)
    if any(entry["name"] == "StationStructure" for entry in result["model"]["tables"]):
        raise ValueError("the SIMLOX source already has station transport")
    stations = {row["STID"] for row in rows(table(result, "Station"))}
    if stations != {"BASE", "DEPOT"}:
        raise ValueError("unexpected SIMLOX stations")
    matching = [
        component for component in canonical["equipment_tree"]["components"]
        if component.get("product_id") == PRODUCT
    ]
    if len(matching) != 1:
        raise ValueError(f"expected one canonical component for {PRODUCT}")
    item_id = matching[0]["id"]
    item_rows = rows(table(result, "Item"))
    if sum(str(row["IID"]).upper() == item_id.upper() for row in item_rows) != 1:
        raise ValueError(f"missing SIMLOX item {item_id}")

    station_structure = copy.deepcopy(table(native_template, "StationStructure"))
    station_structure["instances"][0]["rows"] = []
    append_row(
        station_structure,
        {
            "STID": "BASE",
            "MSTID": "DEPOT",
            "TFRMS": 2,
            "TTOMS": 2,
            "DFRAC": 1,
            "OPOL": "FAST",
            "NOTE": "depot-to-base 2h; reverse 2h SIMLOX-required assumption; canonical route capacity 1 not represented",
        },
    )
    result["model"]["tables"].append(station_structure)

    stock = table(result, "StockAllocation")
    if any(str(row["IID"]).upper() == item_id.upper() for row in rows(stock)):
        raise ValueError(f"source SIMLOX stock already includes {item_id}")
    for station_id, quantity in (("BASE", 0), ("DEPOT", 2)):
        append_row(
            stock,
            {
                "POINT": "F35",
                "IID": item_id,
                "STID": station_id,
                "STSIZ": quantity,
                # ROSIZ is intentionally absent: SIMLOX ignores it for a
                # repairable item and emits warning #170 when supplied.
                "NOTE": f"probe {PRODUCT}; canonical depot stock={quantity}",
            },
        )
    return result, {"item_id": item_id, "upper_stock": 2, "lower_stock": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", required=True, type=Path)
    parser.add_argument("--simlox", required=True, type=Path)
    parser.add_argument("--native-template", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    paths = {
        "canonical": args.canonical,
        "simlox": args.simlox,
        "native_template": args.native_template,
    }
    for name, path in paths.items():
        actual = sha256(path)
        if actual != EXPECTED[name]:
            raise ValueError(f"{name} SHA-256 changed: {actual}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    canonical_source = load(args.canonical)
    canonical = build_canonical(canonical_source)
    simlox, mapping = build_simlox(load(args.simlox), load(args.native_template), canonical_source)
    canonical_path = args.output_dir / "f35-depot2-canonical.json"
    simlox_path = args.output_dir / "f35-depot2-v2-candidate.json"
    write(canonical_path, canonical)
    write(simlox_path, simlox)
    ledger = {
        "source_sha256": EXPECTED,
        "product_id": PRODUCT,
        "canonical_change": f"{UPPER_NODE}.inventory[{PRODUCT}]: 0 -> 2",
        "simlox_change": "BASE -> DEPOT station hierarchy, 2-hour inbound and assumed 2-hour reverse time; add item stock BASE=0 and DEPOT=2",
        "limits": "SIMLOX StationStructure does not encode canonical per-shipment quantity cap=1; SIMLOX ItemRepair still has instant refurbishment placeholder",
        "mapping": mapping,
        "outputs_sha256": {
            "canonical": sha256(canonical_path),
            "simlox": sha256(simlox_path),
        },
    }
    write(args.output_dir / "depot2-ledger.json", ledger)
    print(json.dumps(ledger, ensure_ascii=False))


if __name__ == "__main__":
    main()
