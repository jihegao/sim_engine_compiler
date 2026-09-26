"""Compute an exact table-row multiset delta between A01 and A02 inputs."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A01 = ROOT / "A01-single-aircraft-single-mission/native-input.json"
A02 = ROOT / "A02-single-aircraft-repeated-missions/native-input.json"


def rows(path: Path) -> dict[str, Counter]:
    model = json.loads(path.read_text(encoding="utf-8"))["model"]
    output = {}
    for table in model["tables"]:
        names = [column["name"] for column in table["columns"]]
        output[table["name"]] = Counter(
            json.dumps(dict(zip(names, row)), ensure_ascii=False, sort_keys=True)
            for instance in table["instances"] for row in instance["rows"]
        )
    return output


def compare(a: Path = A01, b: Path = A02) -> dict:
    left, right = rows(a), rows(b)
    changed = {}
    for name in sorted(left.keys() | right.keys()):
        removed = [json.loads(item) for item in (left.get(name, Counter()) - right.get(name, Counter())).elements()]
        added = [json.loads(item) for item in (right.get(name, Counter()) - left.get(name, Counter())).elements()]
        if added or removed:
            changed[name] = {"added": added, "removed": removed}
    return {"parent_case": "A01@1.0.0", "child_case": "A02@1.0.0", "changed_tables": changed}


def main() -> None:
    out = ROOT / "A02-single-aircraft-repeated-missions/parent-diff.json"
    if out.exists():
        raise FileExistsError(out)
    result = compare()
    if list(result["changed_tables"]) != ["OperationProfile"] or result["changed_tables"]["OperationProfile"]["removed"] or len(result["changed_tables"]["OperationProfile"]["added"]) != 2:
        raise ValueError("A02 must add only two scheduled OperationProfile rows")
    out.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(out)


if __name__ == "__main__":
    main()
