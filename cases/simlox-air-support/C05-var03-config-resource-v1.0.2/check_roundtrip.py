"""Read-only full authored-table roundtrip gate for C05.var03."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
INPUT_SHA = {
    "crew": "6c88e8f5b078e7d02184d8612acda6b5d20ed94398943a7ca7f3472830c2f7ae",
    "radio": "235a6ce2850fb12dc5d3f4da67e709e8646fa2f4f6e2aa9cee3e106da335f57a",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = []
        quoted = escaped = False
        for i, char in enumerate(raw):
            if quoted:
                clean.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                clean.append(char)
            elif char == ",":
                k = i + 1
                while k < len(raw) and raw[k].isspace():
                    k += 1
                if k == len(raw) or raw[k] not in "}]":
                    clean.append(char)
            else:
                clean.append(char)
        return json.loads("".join(clean))


def tablemap(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        assert name not in result, "duplicate table " + name
        instances = []
        for instance in table["instances"]:
            rows = instance["rows"]
            assert all(len(row) == len(table["columns"]) for row in rows), name
            instances.append((instance.get("instance_name"), rows))
        result[name] = (table["columns"], instances)
    return result


def check(run: Path, arm: str) -> dict:
    issues = []
    source = HERE / f"{arm}-input.json"
    assert arm in INPUT_SHA
    assert sha(source) == sha(run / "input.json") == INPUT_SHA[arm], "frozen input identity"
    before_doc, after_doc = parse(source), parse(run / "roundtrip-raw.json")
    if before_doc["model"]["database_version"] != after_doc["model"]["database_version"]:
        issues.append("database_version")
    before, after = tablemap(before_doc), tablemap(after_doc)
    if len(before) != 33 or set(before) != set(after):
        issues.append("33-table identity")
    populated = 0
    for name, (columns, instances) in before.items():
        if name not in after:
            issues.append("missing " + name)
            continue
        native_columns, native_instances = after[name]
        if columns != native_columns:
            issues.append("columns " + name)
        if sorted(n for n, _ in native_instances) != sorted(n for n, _ in instances):
            issues.append("instance names " + name)
        source_rows = [row for _, rows in instances for row in rows]
        native_rows = [row for _, rows in native_instances for row in rows]
        if not source_rows and any(any(value is not None for value in row) for row in native_rows):
            issues.append("non-null native placeholder " + name)
        if not any(rows for _, rows in instances):
            continue
        populated += 1
        for instance_name, rows in instances:
            matches = [value for n, value in native_instances if n == instance_name]
            if len(matches) != 1 or matches[0] != rows:
                issues.append(f"rows {name}/{instance_name}")
    if populated != 24:
        issues.append(f"row-containing authored tables {populated} !=24")
    for name, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!")):
        if marker not in (run / name).read_text(encoding="utf-8-sig", errors="replace"):
            issues.append(name + " completion")
    return {"schema": "c05-var03-v102-roundtrip/v1", "arm": arm,
            "passed": not issues, "issues": issues, "authored_row_tables": populated,
            "source_sha256": INPUT_SHA[arm], "export_sha256": sha(run / "roundtrip-raw.json")}


if __name__ == "__main__":
    try:
        result = check(Path(sys.argv[1]), sys.argv[2])
    except Exception as exc:
        result = {"schema": "c05-var03-v102-roundtrip/v1", "passed": False,
                  "issues": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
