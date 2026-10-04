"""Read-only lossless populated-table import/export check for J09.var05."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE_SHA = "43db0df2332602ea7667e7a4afd8eeb50d6ebf33c7c15d93c2e946ba645875de"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native export can put a trailing comma before a closing bracket.
        out: list[str] = []
        quoted = escaped = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def populated(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate table {name}")
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            if any(len(row) != len(table["columns"]) for row in rows):
                raise ValueError(f"nonrectangular table {name}")
            result[name] = {"columns": table["columns"], "rows": rows}
    return result


def scale_roundtrip_lossless(authored: dict, exported: dict) -> bool:
    """Native adds documented optional ScaleFactors fields as null columns."""
    a_names = [c["name"] for c in authored["columns"]]
    e_names = [c["name"] for c in exported["columns"]]
    if len(a_names) != 6 or len(set(e_names)) != len(e_names) or not set(a_names) <= set(e_names):
        return False
    if len(authored["rows"]) != 1 or len(exported["rows"]) != 1:
        return False
    a = dict(zip(a_names, authored["rows"][0]))
    e = dict(zip(e_names, exported["rows"][0]))
    if any(e[k] != v for k, v in a.items()):
        return False
    if any(e[k] is not None for k in set(e_names) - set(a_names)):
        return False
    if any(c["datatype"] != "double" for c in exported["columns"]):
        return False
    return True


def validate(run: Path) -> dict:
    issues = []
    for name in ("input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if issues:
        return {"passed": False, "differences": issues}
    source_sha = sha(run / "input.json")
    if source_sha != SOURCE_SHA or sha(HERE / "scaled-input.json") != SOURCE_SHA:
        issues.append("input fingerprint differs")
    before, after = populated(parse(run / "input.json")), populated(parse(run / "roundtrip-raw.json"))
    for name, table in before.items():
        if after.get(name) != table and not (name == "ScaleFactors" and
                                             after.get(name) is not None and
                                             scale_roundtrip_lossless(table, after[name])):
            issues.append(f"authored columns/rows changed: {name}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {"schema": "simlox-j09-var05-import-export/v1", "passed": not issues,
            "differences": issues, "source_sha256": source_sha,
            "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "populated_tables": sorted(before),
            "native_added_populated_tables": sorted(set(after) - set(before)),
            "scale_factors_native_null_columns": sorted(set(c["name"] for c in after["ScaleFactors"]["columns"]) - set(c["name"] for c in before["ScaleFactors"]["columns"])) if "ScaleFactors" in after else [],
            "scope": "source_values_lossless_with_scale_factor_null_expansion", "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = validate(Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result = {"passed": False, "differences": [f"checker exception: {exc}"]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
