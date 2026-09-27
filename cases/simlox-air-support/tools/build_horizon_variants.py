"""Create immutable, isolated A01 observation-end probes from the checked input.

Only Control.SIMPE/RCEND and ResultCollection.RCEND change. A normal A01
contract is deliberately not reused as the expected result of these probes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SOURCE = ROOT / "A01-single-aircraft-single-mission/native-input.json"
DEST = REPO / "data/local/simlox-case-library/v1/horizon-inputs"
ENDS = {"before_launch": 7.5, "in_flight": 9.0,
        "before_completion": 9.9999, "printed_tie": 10.0,
        "after_completion": 10.0001}


def set_field(model: dict, table_name: str, column_name: str, value: float) -> None:
    table = next(t for t in model["model"]["tables"] if t["name"] == table_name)
    index = [column["name"] for column in table["columns"]].index(column_name)
    for instance in table["instances"]:
        for row in instance["rows"]:
            row[index] = value


def main() -> None:
    model = json.loads(SOURCE.read_text(encoding="utf-8"))
    if any(DEST.iterdir()) if DEST.exists() else False:
        raise FileExistsError(f"variant input directory already populated: {DEST}")
    DEST.mkdir(parents=True, exist_ok=False) if not DEST.exists() else None
    manifest = {"parent_input": str(SOURCE.resolve()),
                "parent_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "variants": []}
    for name, end in ENDS.items():
        variant = json.loads(json.dumps(model))
        set_field(variant, "Control", "SIMPE", end)
        set_field(variant, "Control", "RCEND", end)
        set_field(variant, "ResultCollection", "RCEND", end)
        path = DEST / f"{name}.json"
        data = (json.dumps(variant, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path.write_bytes(data)
        manifest["variants"].append({"id": name, "end_hours": end,
                                     "input_path": str(path.resolve()),
                                     "input_sha256": hashlib.sha256(data).hexdigest(),
                                     "changed_fields": ["Control.SIMPE", "Control.RCEND", "ResultCollection.RCEND"]})
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
