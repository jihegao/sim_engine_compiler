"""Require only the invalid ItemStructure NFFF cell to be erased on export."""

import argparse
import json
from pathlib import Path


def tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    return {table["name"]: table for table in doc["model"]["tables"]}


parser = argparse.ArgumentParser()
for argument in ("source", "exported", "result"):
    parser.add_argument(argument, type=Path)
args = parser.parse_args()
source, exported = tables(args.source), tables(args.exported)
populated = {name for name, table in source.items() if any(instance["rows"] for instance in table["instances"])}
bad = []
if len(source) != 31 or len(populated) != 21:
    bad.append("source table cardinality")
for name in populated:
    original = source[name]
    actual = exported.get(name)
    if actual is None or original["columns"] != actual["columns"]:
        bad.append(f"{name}: columns")
        continue
    before = [row for instance in original["instances"] for row in instance["rows"]]
    after = [row for instance in actual["instances"] for row in instance["rows"]]
    if name == "ItemStructure":
        expected = json.loads(json.dumps(before))
        if len(expected) != 3 or expected[1][0] != "TEACH-SRU-01" or expected[1][4] != 4.0 or expected[1][6] != 5.0:
            bad.append("ItemStructure: authored target")
        else:
            expected[1][6] = None
            if after != expected:
                bad.append("ItemStructure: more than target NFFF erased")
    elif after != before:
        bad.append(f"{name}: unexpected change")
result = {"schema": "simlox-e14-var05-import-rejection-check/v1", "passed": not bad,
          "authored_populated_tables": len(populated), "expected_erased_cell": "ItemStructure rec2 TEACH-SRU-01 NFFF5->null",
          "mismatches": bad}
args.result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result))
raise SystemExit(0 if result["passed"] else 1)
