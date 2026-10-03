"""Check exact native roundtrip of a frozen G09.var04 arm."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SHA = {"use0": "26cd87419a6d31e5d44053ef8b9c710ec78f8b9104d30977276dcbbd2ebb5a7f",
       "use05": "beed9028e57c7393173e79963cadc31d18b7af8634f14a591d79359cbb900b69",
       "use1": "2f69d0ae1411f4fca4b79ec75289695370fe8468b014966879fdefd98e17ea5a",
       "use2": "ee28a65ecaf47fe8b6ec78a8fb8ea3a66c58341e6f0eee7bea54e58d803ca2ca"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(source)
    except json.JSONDecodeError:
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
            elif char == "," and source[i + 1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def populated(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate table: {name}")
        body = [row for inst in table["instances"] for row in inst["rows"]]
        if body:
            if any(len(row) != len(table["columns"]) for row in body):
                raise ValueError(f"nonrectangular table: {name}")
            result[name] = {"columns": table["columns"], "rows": body}
    return result


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in SHA:
        raise SystemExit("usage: check_roundtrip.py RUN_DIR ARM")
    run, arm = Path(sys.argv[1]), sys.argv[2]
    errors = []
    for name in ("input.json", "roundtrip-raw.json", "model.sxi", "import.log", "export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size < 5:
            errors.append(f"missing or empty: {name}")
    result = {"schema": "simlox-g09-usert-boundary-roundtrip/v1", "arm": arm,
              "source_sha256": SHA[arm], "publication_state": "not_published"}
    if not errors:
        if sha(HERE / f"{arm}-input.json") != SHA[arm] or sha(run / "input.json") != SHA[arm]:
            errors.append("frozen input hash changed")
        before, after = populated(native_json(run / "input.json")), populated(native_json(run / "roundtrip-raw.json"))
        for name, value in before.items():
            if after.get(name) != value:
                errors.append(f"business table changed: {name}")
        if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
            errors.append("import marker missing")
        if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
            errors.append("export marker missing")
        result.update(populated_tables=sorted(before), native_added_tables=sorted(set(after) - set(before)),
                      roundtrip_sha256=sha(run / "roundtrip-raw.json"))
    result.update(passed=not errors, differences=errors)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
