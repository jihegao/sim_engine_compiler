"""Verify exact source table rows survive the native import/export cycle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SHA = {"equidist-control": "9ee61443dc0cd0d774d5c1bc6f77343e87fe25ff9bda3772f2b8f37f520c2748",
       "random-seed1": "6984ce91a40a1a0c491ff7eeda4b808c314d50577ec008d1d9f65780acfac512"}


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
    answer = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        if name in answer:
            raise ValueError(f"duplicate {name}")
        body = [row for instance in table["instances"] for row in instance["rows"]]
        if body:
            if any(len(row) != len(table["columns"]) for row in body):
                raise ValueError(f"nonrectangular {name}")
            answer[name] = {"columns": table["columns"], "rows": body}
    return answer


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in SHA:
        raise SystemExit("usage: check_roundtrip.py RUN_DIR equidist-control|random-seed1")
    run, arm = Path(sys.argv[1]), sys.argv[2]
    errors = []
    required = ("input.json", "roundtrip-raw.json", "model.sxi", "import.log", "export.log")
    for name in required:
        p = run / name
        if not p.is_file() or p.stat().st_size < 5:
            errors.append(f"missing or empty {name}")
    result = {"schema": "simlox-g11-var03-random-prelife-roundtrip/v1", "arm": arm,
              "source_sha256": SHA[arm], "publication_state": "not_published"}
    if not errors:
        if sha(HERE / f"native-input-{arm}.json") != SHA[arm] or sha(run / "input.json") != SHA[arm]:
            errors.append("frozen input hash differs")
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
