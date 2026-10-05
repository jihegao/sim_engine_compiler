"""Check every authored row-containing table against a native JSON export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def populated(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    return {
        table["name"]: {
            "columns": [(column["name"], column["datatype"]) for column in table["columns"]],
            "rows": [row for instance in table["instances"] for row in instance["rows"]],
        }
        for table in document["model"]["tables"]
        if any(instance["rows"] for instance in table["instances"])
    }


parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("exported", type=Path)
parser.add_argument("result", type=Path)
arguments = parser.parse_args()
source = populated(arguments.source)
exported = populated(arguments.exported)
mismatches = [name for name, value in source.items() if exported.get(name) != value]
result = {
    "schema": "simlox-i07-var02-roundtrip/v1",
    "passed": len(source) == 22 and not mismatches,
    "authored_populated_tables": len(source),
    "native_export_populated_tables": len(exported),
    "mismatches": mismatches,
}
arguments.result.write_bytes((json.dumps(result, indent=2) + "\n").encode())
print(json.dumps(result))
raise SystemExit(0 if result["passed"] else 1)
