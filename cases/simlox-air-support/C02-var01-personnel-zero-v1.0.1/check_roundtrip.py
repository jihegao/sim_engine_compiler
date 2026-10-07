"""Read-only strict authored-table import/export comparison."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
INPUT_SHA = "bab34055ae4f2ee3efac4fa9cb8f545ba2355daad0751a7d5508947f17d3cec2"
SCHEMA = "c02-var01-v101-roundtrip/v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(source)
    except json.JSONDecodeError:
        # Native SXO may contain trailing commas. Remove only commas outside strings.
        out = []
        quoted = escaped = False
        for i, char in enumerate(source):
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
            elif char == ",":
                j = i + 1
                while j < len(source) and source[j].isspace():
                    j += 1
                if j == len(source) or source[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out))


def check(run: Path) -> dict:
    issues = []
    authored_path = HERE / "native-input.json"
    if sha(authored_path) != sha(run / "input.json") or sha(authored_path) != INPUT_SHA:
        issues.append("input SHA")
    authored = parse(authored_path)
    exported = parse(run / "roundtrip-raw.json")
    if authored["model"]["database_version"] != exported["model"]["database_version"]:
        issues.append("database_version")
    before, after = authored["model"]["tables"], exported["model"]["tables"]
    if len(before) != len(after) or len(before) != 31:
        issues.append("table count")
    if [t["name"] for t in before] != [t["name"] for t in after]:
        issues.append("table order/names")
    populated = 0
    for old, new in zip(before, after):
        name = old["name"]
        if old["columns"] != new["columns"]:
            issues.append(f"columns {name}")
        oi, ni = old["instances"], new["instances"]
        if len(oi) != len(ni) or [x.get("instance_name") for x in oi] != [x.get("instance_name") for x in ni]:
            issues.append(f"instances {name}")
            continue
        for o, n in zip(oi, ni):
            rows, native = o["rows"], n["rows"]
            if rows:
                populated += 1
                if rows != native:
                    issues.append(f"rows {name}")
            elif any(any(value is not None for value in row) for row in native):
                issues.append(f"non-null native placeholder {name}")
            if any(len(row) != len(old["columns"]) for row in rows + native):
                issues.append(f"row width {name}")
    if populated != 20:
        issues.append(f"row-containing tables {populated}")
    for name, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!")):
        if marker not in (run / name).read_text(encoding="utf-8-sig", errors="replace"):
            issues.append(f"{name} completion")
    return {"schema": SCHEMA, "passed": not issues, "issues": issues,
            "input_sha256": INPUT_SHA, "export_sha256": sha(run / "roundtrip-raw.json"),
            "authored_row_tables": populated}


if __name__ == "__main__":
    try:
        result = check(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": SCHEMA, "passed": False, "issues": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, separators=(",", ":")))
    sys.exit(0 if result["passed"] else 1)
