"""Check exact authored-table import/export identity; no behavior acceptance."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

INPUT_SHA = "fa7b9040fced6267aa5781cb0761df41b803c0cccaf8c218a2aa0c1de01b24bb"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def populated(doc):
    result = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate table {name}")
        columns = table["columns"]
        if any(len(row) != len(columns) for instance in table["instances"]
               for row in instance["rows"]):
            raise ValueError(f"nonrectangular table {name}")
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
        issues.append("frozen/run input SHA differs")
    before = populated(json.loads(remove_trailing_commas((run / "input.json").read_bytes())))
    after = populated(json.loads(remove_trailing_commas((run / "roundtrip-raw.json").read_bytes())))
    for name, authored in before.items():
        if after.get(name) != authored:
            issues.append(f"authored columns, instances or rows differ: {name}")
    if len(before) != 21:
        issues.append(f"expected 21 populated authored tables, found {len(before)}")
    for name, marker in (("import.log", "Import completed!"),
                         ("export.log", "Export completed!")):
        if marker not in (run / name).read_text(encoding="utf-8-sig", errors="replace"):
            issues.append(f"{name} completion marker absent")
    return {"schema": "simlox-b04-var02-zero-crew-roundtrip/v1", "passed": not issues,
            "issues": issues, "source_sha256": INPUT_SHA,
            "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "sxi_sha256": sha(run / "model.sxi"),
            "authored_populated_tables": sorted(before),
            "scope": "import_export_identity_only", "publication_state": "not_published"}


def main():
    try:
        result = validate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": "simlox-b04-var02-zero-crew-roundtrip/v1", "passed": False,
                  "issues": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
