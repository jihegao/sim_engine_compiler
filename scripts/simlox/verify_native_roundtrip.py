"""Compare every nonempty SIMLOX business row after jimport/jexport."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def normalize(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def table_rows(path: Path) -> dict[str, Counter]:
    model = json.loads(path.read_text(encoding="utf-8-sig"))["model"]
    result = {}
    for table in model["tables"]:
        columns = [column["name"] for column in table["columns"]]
        rows = []
        for instance in table["instances"]:
            for raw in instance["rows"]:
                if any(value not in (None, "") for value in raw):
                    row = normalize(dict(zip(columns, raw)))
                    rows.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
        result[table["name"]] = Counter(rows)
    return result


def compare(input_path: Path, export_path: Path) -> dict:
    original, exported = table_rows(input_path), table_rows(export_path)
    entries = []
    for name in sorted(original.keys() | exported.keys()):
        a, b = original.get(name, Counter()), exported.get(name, Counter())
        if a or b:
            entries.append({
                "table": name,
                "input_rows": sum(a.values()),
                "export_rows": sum(b.values()),
                "exact_nonempty_multiset": a == b,
                "input_only": list((a - b).elements())[:3],
                "export_only": list((b - a).elements())[:3],
            })
    return {"input": str(input_path), "export": str(export_path), "all_equal": all(row["exact_nonempty_multiset"] for row in entries), "tables": entries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("export", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = compare(args.input, args.export)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_equal": result["all_equal"], "business_tables": len(result["tables"])}))
    if not result["all_equal"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
