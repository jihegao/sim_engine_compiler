"""Check B02 scalar control roundtrip, treating only an all-null placeholder as empty."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

INPUT_SHA = "7596ea50dc770bf9726a0d3300c0c2b0a881b772e57db0c3a079a3629714a939"


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
    mission = after.get("MissionType")
    if mission:
        fields = [x["name"] for x in mission["columns"]]
        rows = mission["instances"][0]["rows"]
        if len(rows) != 1 or rows[0][fields.index("NOPER")] != 1.0:
            issues.append("MissionType.NOPER1 not retained")
    prep = after.get("MissionPreparation")
    if not prep:
        issues.append("MissionPreparation absent")
    else:
        fields = [x["name"] for x in prep["columns"]]
        rows = prep["instances"][0]["rows"]
        if len(rows) != 1 or rows[0][fields.index("DURN")] != 0.75 or rows[0][fields.index("TID")] != "PREP-FIXED":
            issues.append("MissionPreparation overridden scalar/TID not retained")
    source_breakdown = [t for t in input_doc["model"]["tables"] if t["name"] == "TaskBreakDown"]
    exported_breakdown = [t for t in output_doc["model"]["tables"] if t["name"] == "TaskBreakDown"]
    if len(source_breakdown) != 1 or len(exported_breakdown) != 1:
        issues.append("TaskBreakDown table missing/duplicate")
    else:
        src, dst = source_breakdown[0], exported_breakdown[0]
        if dst["columns"] != src["columns"] or len(dst["instances"]) != 1 or dst["instances"][0]["instance_name"] != src["instances"][0]["instance_name"]:
            issues.append("TaskBreakDown columns/instance changed")
        source_rows = src["instances"][0]["rows"]
        returned_rows = dst["instances"][0]["rows"]
        if source_rows != [] or returned_rows not in ([], [[None] * len(src["columns"])]):
            issues.append("TaskBreakDown acquired a populated row")
    if len(before) != 16:
        issues.append(f"expected 16 row-containing authored tables, found {len(before)}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {"schema": "simlox-b02-var06-roundtrip/v1", "passed": not issues, "issues": issues,
            "source_sha256": INPUT_SHA, "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "sxi_sha256": sha(run / "model.sxi"), "authored_row_containing_tables": sorted(before),
            "scope": "import_export_identity_only", "publication_state": "not_published"}


def main():
    try:
        result = validate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": "simlox-b02-var06-roundtrip/v1", "passed": False,
                  "issues": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
