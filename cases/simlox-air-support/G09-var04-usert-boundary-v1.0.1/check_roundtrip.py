"""Check exact native roundtrip of a frozen G09.var04 arm."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SHA = {"use0": "ec75dee10ff03050ecc3d3431d40017b6d7cf2732a4cfcca0969ebc8410b3445",
       "use05": "4e121c8b8c86bb650e7060ad77e66049d8eaedc89728a4cc18a7c486b1d27c81",
       "use1": "957e7b16a75c2cc06a6bf2ef6a2a7b9ae0a44e683349c248383281b3ffec5c85",
       "use2": "f5c721233aa40f2ef4b137604799fa7ac382718b49d659d9bb716e2e9166e116"}


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
