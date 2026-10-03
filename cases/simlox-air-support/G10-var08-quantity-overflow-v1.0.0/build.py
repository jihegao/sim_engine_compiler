"""Freeze a single RedundancyLink quantity-overflow negative from accepted G10.var01."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var01-series-two-item-v1.0.1/native-input.json"
PARENT_SHA = "00d4545ee3e58a9fb28e1862552ee3788ad82ed8487159f826af1d47b393a8ba"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return [c["name"] for c in matches[0]["columns"]], matches[0]["instances"][0]["rows"]


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted parent source changed")
    doc = json.loads(raw)
    cols, rows = table(doc, "Redundancy")
    if len(rows) != 1 or rows[0][cols.index("RLID")] != "G10-SER-LINK" or rows[0][cols.index("NRL")] != 2 or rows[0][cols.index("NRLRQ")] != 1:
        raise ValueError("unexpected accepted redundancy")
    cols, rows = table(doc, "ItemStructure")
    installed = [r[cols.index("QTYPM")] for r in rows if r[cols.index("IID")] == "TEACH-LRU-01" and r[cols.index("MID")] == "TEACH-AIR-01"]
    if installed != [2]:
        raise ValueError(f"expected two installed LRU items: {installed}")
    cols, rows = table(doc, "RedundancyLink")
    selected = [r for r in rows if r[cols.index("RLID")] == "G10-SER-LINK" and r[cols.index("IID")] == "TEACH-LRU-01"]
    if len(selected) != 1 or selected[0][cols.index("QTYPL")] != 1:
        raise ValueError("expected one valid LRU per link")
    selected[0][cols.index("QTYPL")] = 2
    cols, rows = table(doc, "ProblemDescription")
    if len(rows) != 1:
        raise ValueError("one description row required")
    rows[0][cols.index("PDESC")] = "G10.var08 LRU QTYPL2 times NRL2 exceeds installed QTYPM2"
    return doc


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "native-input.json"
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("frozen input differs")
    else:
        path.write_bytes(raw)
    print(json.dumps({"sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
