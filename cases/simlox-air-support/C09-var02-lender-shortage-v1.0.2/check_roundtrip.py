"""Strict authored-row import/export check; no SIMLOX invocation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
INPUT_SHA = {
    "ordinary": "b971efb41492789f32475aae7fa9f37c0e30e9461203b48d37e08e2747e8d2e3",
    "shortage": "fc65462d65c0fea1017f81e41dc283a9a1f666e7b1f42aeb262fc6f5b8384bff",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path) -> dict:
    s = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
        for i, ch in enumerate(s):
            if quoted:
                out.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    quoted = False
            elif ch == '"':
                quoted = True
                out.append(ch)
            elif ch == ",":
                j = i + 1
                while j < len(s) and s[j].isspace():
                    j += 1
                if j >= len(s) or s[j] not in "}]":
                    out.append(ch)
            else:
                out.append(ch)
        return json.loads("".join(out))


def tables(doc: dict) -> dict:
    found = {}
    for t in doc["model"]["tables"]:
        name = t["name"]
        assert name not in found, f"duplicate table {name}"
        instances = []
        for instance in t["instances"]:
            rows = instance["rows"]
            assert all(len(row) == len(t["columns"]) for row in rows), name
            instances.append((instance.get("instance_name"), rows))
        found[name] = (t["columns"], instances)
    return found


def check(run: Path, arm: str) -> dict:
    issues = []
    source = HERE / f"{arm}-input.json"
    expected_sha = INPUT_SHA[arm]
    assert sha(source) == sha(run / "input.json") == expected_sha, "frozen input SHA"
    authored, exported = parse(source), parse(run / "roundtrip-raw.json")
    before, after = tables(authored), tables(exported)
    if authored["model"]["database_version"] != exported["model"]["database_version"]:
        issues.append("database_version")
    populated = 0
    if set(before) != set(after):
        issues.append("table name set")
    for name, (columns, instances) in before.items():
        if name not in after:
            issues.append(f"missing table {name}")
            continue
        native_columns, native_instances = after[name]
        if columns != native_columns:
            issues.append(f"columns {name}")
        if sorted(n for n, _ in native_instances) != sorted(n for n, _ in instances):
            issues.append(f"instance names {name}")
        authored_rows = [r for _, rows in instances for r in rows]
        exported_rows = [r for _, rows in native_instances for r in rows]
        if not authored_rows and any(any(value is not None for value in row) for row in exported_rows):
            issues.append(f"unexpected populated native row {name}")
        if not any(rows for _, rows in instances):
            continue
        populated += 1
        for instance_name, rows in instances:
            matches = [r for n, r in native_instances if n == instance_name]
            if len(matches) != 1 or matches[0] != rows:
                issues.append(f"rows {name}/{instance_name}")
    if populated != 25:
        issues.append(f"authored row-containing tables {populated} !=25")
    for log, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!")):
        if marker not in (run / log).read_text(encoding="utf-8-sig", errors="replace"):
            issues.append(f"{log} completion absent")
    return {"schema": "c09-var02-v102-roundtrip/v1", "arm": arm,
            "passed": not issues, "issues": issues, "authored_row_tables": populated,
            "source_sha256": expected_sha, "export_sha256": sha(run / "roundtrip-raw.json")}


if __name__ == "__main__":
    try:
        result = check(Path(sys.argv[1]), sys.argv[2])
    except Exception as exc:
        result = {"schema": "c09-var02-v102-roundtrip/v1", "passed": False,
                  "issues": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
