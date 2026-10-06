"""Check exact authored-table identity in the A01 sum-to-one import/export."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

SOURCE_SHA = "242d83ba901e7f64dc8a0ccefd4f5a405a51ede86359e240d4abb12bf543b1f9"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def populated(doc):
    result = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate table {name}")
        for instance in table["instances"]:
            for row in instance["rows"]:
                if len(row) != len(table["columns"]):
                    raise ValueError(f"nonrectangular table {name}")
        if any(instance["rows"] for instance in table["instances"]):
            result[name] = {"columns": table["columns"], "instances": table["instances"]}
    return result

def validate(run):
    issues = []
    for name in ("input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if issues:
        return {"schema": "simlox-a01-var01-sum-one-v010-roundtrip/v1", "passed": False,
                "differences": issues, "publication_state": "not_published"}
    if sha(run / "input.json") != SOURCE_SHA or sha(HERE / "native-input.json") != SOURCE_SHA:
        issues.append("frozen input SHA differs")
    before = populated(json.loads(remove_trailing_commas((run / "input.json").read_bytes())))
    after = populated(json.loads(remove_trailing_commas((run / "roundtrip-raw.json").read_bytes())))
    for name, authored in before.items():
        if after.get(name) != authored:
            issues.append(f"authored columns, instances or rows changed/missing: {name}")
    if len(before) != 13:
        issues.append(f"expected 13 row-containing authored tables; found {len(before)}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {"schema": "simlox-a01-var01-sum-one-v010-roundtrip/v1", "passed": not issues,
            "differences": issues, "source_sha256": SOURCE_SHA,
            "roundtrip_sha256": sha(run / "roundtrip-raw.json"), "sxi_sha256": sha(run / "model.sxi"),
            "authored_row_containing_tables": sorted(before),
            "native_added_row_containing_tables": sorted(set(after) - set(before)),
            "scope": "import_export_identity_only", "publication_state": "not_published"}

def main():
    try:
        result = validate(Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result = {"schema": "simlox-a01-var01-sum-one-v010-roundtrip/v1", "passed": False,
                  "differences": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
