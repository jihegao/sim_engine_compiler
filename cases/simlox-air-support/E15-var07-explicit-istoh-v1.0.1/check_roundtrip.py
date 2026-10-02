"""Check both E15 authored input tables after native import/export."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SHA = {
    "default": "602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e",
    "explicit-three": "bb57aecc7285d8eef5c71ba1b7f6b6f7dd9fb4cc46f3e6d88e863eb1da3f206f",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
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


def validate(run: Path, arm: str) -> dict:
    issues = []
    for name in ("input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if issues:
        return {"passed": False, "differences": issues}
    expected = SHA[arm]
    if sha(run / "input.json") != expected or sha(HERE / f"native-input-{arm}.json") != expected:
        issues.append("input source fingerprint differs")
    before = populated(parse_native(run / "input.json"))
    after = populated(parse_native(run / "roundtrip-raw.json"))
    for name, table in before.items():
        if after.get(name) != table:
            issues.append(f"business columns/rows changed or missing in {name}")
    if len(before) != 21:
        issues.append(f"expected 21 populated source tables; got {len(before)}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {
        "schema": "simlox-e15-var07-v101-import-export/v1",
        "passed": not issues,
        "differences": issues,
        "arm": arm,
        "source_sha256": expected,
        "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
        "sxi_sha256": sha(run / "model.sxi"),
        "populated_tables": sorted(before),
        "native_added_populated_tables": sorted(set(after) - set(before)),
        "scope": "import_export_identity_only",
        "publication_state": "not_published",
    }


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in SHA:
        raise SystemExit("usage: check_roundtrip.py RUN_DIR default|explicit-three")
    try:
        result = validate(Path(sys.argv[1]), sys.argv[2])
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result = {"passed": False, "differences": [f"probe validation error: {type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
