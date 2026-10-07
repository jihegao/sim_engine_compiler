"""Read-only 32-table SIMLOX import/export and metadata gate."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

from build import typed_equal

HERE = Path(__file__).resolve().parent
INPUT_SHA = "3ff558fd5389b1d0e67ec93676a79f9cb00f23823f0514bccf5591c90174f694"
SCHEMA = "i03-var06-out-dt4-roundtrip/v1"
PLACEHOLDERS = {"Item", "ItemStructure", "StationStructure", "SystemRepair", "ItemRepair",
                "ItemReorder", "TaskResource", "MaterielPM", "PMLocation", "StockAllocation", "ItemReplacement"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        out: list[str] = []
        quote = escape = False
        for i, char in enumerate(text):
            if quote:
                out.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    quote = False
            elif char == '"':
                quote = True
                out.append(char)
            elif char == ',':
                j = i + 1
                while j < len(text) and text[j].isspace():
                    j += 1
                if j == len(text) or text[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out))


def table_shape(tables: list[dict]) -> None:
    assert len(tables) == 32
    names = [t["name"] for t in tables]
    assert len(set(names)) == 32
    for table in tables:
        assert set(table) == {"name", "columns", "instances"}, table["name"]
        assert len(table["instances"]) == 1
        assert set(table["instances"][0]) == {"instance_name", "rows"}
        columns = table["columns"]
        assert len({col["name"] for col in columns}) == len(columns)
        for row in table["instances"][0]["rows"]:
            assert len(row) == len(columns)


def rows_equal(columns: list[dict], expected: list[list], observed: list[list]) -> bool:
    if len(expected) != len(observed):
        return False
    for a, b in zip(expected, observed):
        if len(a) != len(columns) or len(b) != len(columns):
            return False
        for col, x, y in zip(columns, a, b):
            if x is None:
                if y is not None:
                    return False
            elif col["datatype"] == "double":
                if type(x) not in (int, float) or type(y) not in (int, float) or not math.isfinite(y) or x != y:
                    return False
            elif not typed_equal(x, y):
                return False
    return True


def check(run: Path) -> dict:
    source = HERE / "native-input.json"
    assert digest(source) == digest(run / "input.json") == INPUT_SHA
    authored = parse(source)
    exported = parse(run / "roundtrip-raw.json")
    assert set(authored) == set(exported) == {"model"}
    am, em = authored["model"], exported["model"]
    assert set(am) == set(em) == {"database_version", "tables"}
    assert type(am["database_version"]) is int and typed_equal(am["database_version"], em["database_version"]) and am["database_version"] == 20160627
    at, et = am["tables"], em["tables"]
    table_shape(at)
    table_shape(et)
    assert [t["name"] for t in at] == [t["name"] for t in et]
    populated = 0
    placeholders = set()
    for a, e in zip(at, et):
        assert typed_equal(a["columns"], e["columns"]), (a["name"], "columns")
        assert typed_equal([i["instance_name"] for i in a["instances"]], [i["instance_name"] for i in e["instances"]]), (a["name"], "instance")
        ai, ei = a["instances"][0], e["instances"][0]
        if ai["rows"]:
            populated += 1
            assert rows_equal(a["columns"], ai["rows"], ei["rows"]), (a["name"], "rows")
            assert a["name"] not in PLACEHOLDERS
        else:
            placeholders.add(a["name"])
            assert a["name"] in PLACEHOLDERS
            assert ei["rows"] == [[None] * len(a["columns"])], (a["name"], "placeholder")
    assert populated == 21 and placeholders == PLACEHOLDERS
    for name, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!")):
        assert marker in (run / name).read_text(encoding="utf-8-sig", errors="replace")
    return {"schema": SCHEMA, "passed": True, "issues": [], "input_sha256": INPUT_SHA,
            "export_sha256": digest(run / "roundtrip-raw.json"), "table_objects": 32,
            "row_containing_tables": 21, "all_null_placeholder_tables": 11}


if __name__ == "__main__":
    try:
        result = check(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": SCHEMA, "passed": False, "issues": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, separators=(",", ":")))
    sys.exit(0 if result["passed"] else 1)
