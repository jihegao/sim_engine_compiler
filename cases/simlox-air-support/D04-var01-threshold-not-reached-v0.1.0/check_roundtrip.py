"""Check exact authored-table identity in the D04.var01 native import/export."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

SOURCE_SHA = "cb8d6045df3b395583e3df2290b61376afa4fa9e8bc82a1c6f53fcfb44e2bddd"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))


def populated(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate table {name}")
        columns = table["columns"]
        instances = table["instances"]
        for instance in instances:
            for row in instance["rows"]:
                if len(row) != len(columns):
                    raise ValueError(f"nonrectangular table {name}")
        if any(instance["rows"] for instance in instances):
            result[name] = {"columns": columns, "instances": instances}
    return result


def validate(run: Path) -> dict:
    issues = []
    for name in ("input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if issues:
        return {"schema": "simlox-d04-var01-v010-roundtrip/v1", "passed": False,
                "differences": issues, "publication_state": "not_published"}
    if sha(run / "input.json") != SOURCE_SHA or sha(HERE / "native-input.json") != SOURCE_SHA:
        issues.append("frozen input SHA differs")
    before, after = populated(parse(run / "input.json")), populated(parse(run / "roundtrip-raw.json"))
    for name, authored in before.items():
        if after.get(name) != authored:
            issues.append(f"authored columns, instances or rows changed/missing: {name}")
    if len(before) != 18:
        issues.append(f"expected 18 row-containing authored tables; found {len(before)}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {"schema": "simlox-d04-var01-v010-roundtrip/v1", "passed": not issues,
            "differences": issues, "source_sha256": SOURCE_SHA,
            "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "sxi_sha256": sha(run / "model.sxi"),
            "authored_row_containing_tables": sorted(before),
            "native_added_row_containing_tables": sorted(set(after) - set(before)),
            "scope": "import_export_identity_only", "publication_state": "not_published"}


def main() -> int:
    run = Path(sys.argv[1])
    try:
        result = validate(run)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result = {"schema": "simlox-d04-var01-v010-roundtrip/v1", "passed": False,
                  "differences": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
