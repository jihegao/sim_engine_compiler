"""Read-only exact populated-table import/export check for F04.var03."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE_SHA = "30875386d868448b9fb8beaa4ad1c6da0f77f3d6b22eb7def2d09f12116f3aa7"


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


def validate(run: Path) -> dict:
    issues = []
    for name in ("input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if issues:
        return {"passed": False, "differences": issues}
    source_sha = sha(run / "input.json")
    if source_sha != SOURCE_SHA or sha(HERE / "native-input.json") != SOURCE_SHA:
        issues.append("input fingerprint differs")
    before, after = populated(parse(run / "input.json")), populated(parse(run / "roundtrip-raw.json"))
    for name, table in before.items():
        if after.get(name) != table:
            issues.append(f"authored columns/rows changed: {name}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {"schema": "simlox-f04-system-window-import-export/v1", "passed": not issues,
            "differences": issues, "source_sha256": source_sha,
            "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "populated_tables": sorted(before),
            "native_added_populated_tables": sorted(set(after) - set(before)),
            "scope": "import_export_identity_only", "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = validate(Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result = {"passed": False, "differences": [f"checker exception: {exc}"]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
