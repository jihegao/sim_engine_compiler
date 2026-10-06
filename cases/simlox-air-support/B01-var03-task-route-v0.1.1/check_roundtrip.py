"""Check all authored B01.var03 task-route rows against native JSON roundtrip."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

INPUT_SHA = "0cdb2bb68dcd49197988caba76b8d41e700b774139da98f33296c74c0d0d3c7b"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_containing(doc):
    result = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate table: {name}")
        columns = table["columns"]
        for instance in table["instances"]:
            for row in instance["rows"]:
                if len(row) != len(columns):
                    raise ValueError(f"nonrectangular table: {name}")
        if any(instance["rows"] for instance in table["instances"]):
            result[name] = {"columns": columns, "instances": table["instances"]}
    return result


def validate(run):
    issues = []
    for name in ("input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if issues:
        return {"passed": False, "issues": issues}
    if sha(run / "input.json") != INPUT_SHA or sha(HERE / "native-input.json") != INPUT_SHA:
        issues.append("frozen input SHA differs")
    input_doc = json.loads(remove_trailing_commas((run / "input.json").read_bytes()))
    output_doc = json.loads(remove_trailing_commas((run / "roundtrip-raw.json").read_bytes()))
    before = row_containing(input_doc)
    after = row_containing(output_doc)
    for name, authored in before.items():
        if after.get(name) != authored:
            issues.append(f"authored columns, instances or rows changed/missing: {name}")
    profile = after.get("OperationProfile")
    if not profile:
        issues.append("OperationProfile absent")
    else:
        fields = [x["name"] for x in profile["columns"]]
        rows = profile["instances"][0]["rows"]
        if len(rows) != 3 or [(row[fields.index("SPRID")], row[fields.index("STIM")]) for row in rows] != [
            ("HOT-SORTIE", 8.0), ("HOT-SORTIE", 12.0), ("HOT-SORTIE", 16.0)
        ]:
            issues.append("explicit hot mission mapping differs")
    if len(before) != 17:
        issues.append(f"expected 17 row-containing authored tables, found {len(before)}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {"schema": "simlox-b01-var03-task-route-roundtrip/v1", "passed": not issues, "issues": issues,
            "source_sha256": INPUT_SHA, "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "sxi_sha256": sha(run / "model.sxi"), "authored_row_containing_tables": sorted(before),
            "scope": "import_export_identity_only", "publication_state": "not_published"}


def main():
    try:
        result = validate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": "simlox-b01-var03-task-route-roundtrip/v1", "passed": False,
                  "issues": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
