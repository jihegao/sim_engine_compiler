"""Check frozen E06 input against native import/export without accepting behavior."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402

INPUT_SHA = {
    "local": "b460c6948c2299c521fb9e24c69c1ebc7dfd976702b5e380b13b5f5abf666b95",
    "upstream": "7febb8c32afaa24fbf3bad94ba240e53236d8967c6fe6df51b4cfb7686828b0d",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def populated(path: Path) -> dict:
    doc = json.loads(native.remove_trailing_commas(path.read_bytes()))
    result = {}
    for table in doc["model"]["tables"]:
        if table["name"] in result:
            raise ValueError(f"duplicate table {table['name']}")
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            if any(len(row) != len(table["columns"]) for row in rows):
                raise ValueError(f"nonrectangular table {table['name']}")
            result[table["name"]] = {"columns": table["columns"], "rows": rows}
    return result


def validate(run: Path) -> dict:
    errors = []
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    variant = invocation["variant"]
    expected = INPUT_SHA[variant]
    required = ("input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log")
    for name in required:
        if not (run / name).is_file() or (run / name).stat().st_size <= 4:
            errors.append(f"{name} missing/empty")
    if errors:
        return {"passed": False, "differences": errors}
    if sha(run / "input.json") != expected or sha(HERE / f"{variant}-input.json") != expected:
        errors.append("frozen input fingerprint differs")
    before, after = populated(run / "input.json"), populated(run / "roundtrip-raw.json")
    for name, table in before.items():
        if after.get(name) != table:
            errors.append(f"{name} source rows/columns differ")
    if len(before) != 21:
        errors.append(f"expected 21 source populated tables, saw {len(before)}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        errors.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        errors.append("export completion marker absent")
    return {"schema": "simlox-e06-var01-import-export/v1", "variant": variant,
            "passed": not errors, "differences": errors,
            "source_sha256": expected, "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "sxi_sha256": sha(run / "model.sxi"), "populated_tables": sorted(before),
            "native_added_populated_tables": sorted(set(after) - set(before)),
            "scope": "import_export_identity_only", "publication_state": "not_published"}


if __name__ == "__main__":
    report = validate(Path(sys.argv[1]))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
