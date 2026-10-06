"""Check exact authored-table identity for forbidden <REPAIR> preparation."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

INPUT_SHA = "e408ff21a8dc9cb7c12ae5acd50d14089846299a4382e40303c9d68edc472d7e"


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
    before = row_containing(json.loads(remove_trailing_commas((run / "input.json").read_bytes())))
    after = row_containing(json.loads(remove_trailing_commas((run / "roundtrip-raw.json").read_bytes())))
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
    breakdown = after.get("TaskBreakDown")
    if not breakdown:
        issues.append("TaskBreakDown absent")
    else:
        fields = [x["name"] for x in breakdown["columns"]]
        rows = breakdown["instances"][0]["rows"]
        actual = [(r[fields.index("TID")], r[fields.index("SEQ")], r[fields.index("SUTID")], r[fields.index("DURN")], r[fields.index("DURND")]) for r in rows]
        if actual != [("PREP-FIXED", 1, "<REPAIR>", 1/6, None), ("PREP-FIXED", 2, "SERVICE", 1/3, None)]:
            issues.append("TaskBreakDown forbidden repair/preparation row not retained")
    if len(before) != 17:
        issues.append(f"expected 17 row-containing authored tables, found {len(before)}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {"schema": "simlox-b02-var04-roundtrip/v1", "passed": not issues, "issues": issues,
            "source_sha256": INPUT_SHA, "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "sxi_sha256": sha(run / "model.sxi"), "authored_row_containing_tables": sorted(before),
            "scope": "import_export_identity_only", "publication_state": "not_published"}


def main():
    try:
        result = validate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": "simlox-b02-var04-roundtrip/v1", "passed": False,
                  "issues": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
