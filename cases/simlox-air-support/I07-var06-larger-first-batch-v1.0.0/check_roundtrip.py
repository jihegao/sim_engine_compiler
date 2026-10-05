"""Gate one native export against every authored row-containing table."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def populated(document: dict) -> dict:
    return {
        table["name"]: {
            "columns": [(col["name"], col["datatype"]) for col in table["columns"]],
            "rows": [row for instance in table["instances"] for row in instance["rows"]],
        }
        for table in document["model"]["tables"]
        if any(instance["rows"] for instance in table["instances"])
    }


parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("exported", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
source = populated(read(args.source))
exported = populated(read(args.exported))
failures = [name for name, table in source.items() if exported.get(name) != table]
result = {"schema": "simlox-i07-var06-roundtrip/v1", "passed": not failures and len(source) == 22,
          "authored_populated_tables": len(source), "mismatches": failures,
          "native_export_populated_tables": len(exported)}
args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result))
raise SystemExit(0 if result["passed"] else 1)
