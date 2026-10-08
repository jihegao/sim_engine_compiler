"""Read-only 32-table SIMLOX import/export and metadata gate."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

from build import typed_equal

HERE = Path(__file__).resolve().parent
INPUT_SHA = {
    "control_out1": "c8b98ec133963d49a104426066c8d9e273fae0b5c77f53d9c955dc9b3c22532c",
    "child_out2": "c8558c0707e246465038677bcc3757586d89c9e9ab51157e3166ae6cba4be1eb",
}
SCHEMA = "i03-var03-matched-out-roundtrip/v1"
PLACEHOLDERS = {"Item", "ItemStructure", "StationStructure", "SystemRepair", "ItemRepair",
                "ItemReorder", "TaskResource", "MaterielPM", "PMLocation", "StockAllocation", "ItemReplacement"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError(f"nonfinite JSON number: {value}")

    def decode(raw: str) -> dict:
        return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)

    try:
        return decode(text)
    except json.JSONDecodeError:
        # The sealed native report format has one trailing row comma. The
        # import/export and authored input formats have none.
        assert path.name.endswith("report-raw.json"), "trailing comma outside native report"
        out: list[str] = []
        quote = escape = False
        removed = 0
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
                    removed += 1
            else:
                out.append(char)
        repaired = "".join(out)
        assert removed == 1, ("native report trailing comma count", removed)
        return decode(repaired)


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


def check(run: Path, arm: str) -> dict:
    assert arm in INPUT_SHA
    source = HERE / f"{arm}-input.json"
    assert digest(source) == digest(run / "input.json") == INPUT_SHA[arm]
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
    return {"schema": SCHEMA, "arm": arm, "passed": True, "issues": [], "input_sha256": INPUT_SHA[arm],
            "export_sha256": digest(run / "roundtrip-raw.json"), "table_objects": 32,
            "row_containing_tables": 21, "all_null_placeholder_tables": 11}


if __name__ == "__main__":
    try:
        assert len(sys.argv) == 3
        result = check(Path(sys.argv[1]), sys.argv[2])
    except Exception as exc:
        result = {"schema": SCHEMA, "passed": False, "issues": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, separators=(",", ":")))
    sys.exit(0 if result["passed"] else 1)
