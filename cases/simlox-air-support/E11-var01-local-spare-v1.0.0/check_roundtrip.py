"""Check E11.var01 local spare import/export identity; this does not accept behavior."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SHA = "b5efd8e6a1d85d4bd89a6a99be70fd44538955480baf4f25514653d46147ffc2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Preserve the raw byte hash; normalize only a parser copy of the
        # native writer's known trailing-comma form.
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
            elif char == "," and raw[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def populated(doc: dict) -> dict[str, dict]:
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
    issues: list[str] = []
    required = ["input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"]
    for name in required:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if issues:
        return {"schema": "simlox-e11-var01-local-spare-v100-import-export/v1", "passed": False, "differences": issues}
    if sha(run / "input.json") != SHA or sha(HERE / "native-input.json") != SHA:
        issues.append("input source fingerprint differs")
    source = parse_native(run / "input.json")
    exported = parse_native(run / "roundtrip-raw.json")
    before = populated(source)
    after = populated(exported)
    for name, table in before.items():
        if after.get(name) != table:
            issues.append(f"business columns/rows changed or missing in {name}")
    if len(before) != 22 or not set(before).issubset(after):
        issues.append(f"source populated table names missing: {sorted(set(before) - set(after))}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {
        "schema": "simlox-e11-var01-local-spare-v100-import-export/v1",
        "passed": not issues,
        "differences": issues,
        "source_sha256": SHA,
        "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
        "sxi_sha256": sha(run / "model.sxi"),
        "populated_tables": sorted(before),
        # SIMLOX fills built-in default tables during export. They are not
        # author-supplied business rows, and this probe does not accept them.
        "native_added_populated_tables": sorted(set(after) - set(before)),
        "scope": "import_export_identity_only",
        "conversion_status": "not_run",
        "simulation_behavior_status": "not_run",
        "publication_state": "not_published",
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_roundtrip.py RUN_DIR")
    run = Path(sys.argv[1])
    try:
        result = validate(run)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result = {
            "schema": "simlox-e11-var01-local-spare-v100-import-export/v1",
            "passed": False,
            "differences": [f"probe validation error: {type(exc).__name__}: {exc}"],
            "scope": "import_export_identity_only",
            "publication_state": "not_published",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
