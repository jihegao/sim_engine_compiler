"""Compare all authored row-containing input tables with native JSON export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def populated(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    return {t["name"]: {"columns": [(c["name"], c["datatype"]) for c in t["columns"]],
                        "rows": [r for i in t["instances"] for r in i["rows"]]}
            for t in doc["model"]["tables"] if any(i["rows"] for i in t["instances"])}


p = argparse.ArgumentParser()
p.add_argument("source", type=Path)
p.add_argument("exported", type=Path)
p.add_argument("result", type=Path)
a = p.parse_args()
source, exported = populated(a.source), populated(a.exported)
bad = [name for name, value in source.items() if exported.get(name) != value]
out = {"schema": "simlox-e14-var04-roundtrip/v1", "passed": len(source) == 21 and not bad,
       "authored_populated_tables": len(source), "native_export_populated_tables": len(exported),
       "mismatches": bad}
a.result.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(out))
raise SystemExit(0 if out["passed"] else 1)
