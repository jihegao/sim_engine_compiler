"""Verify exact source table rows survive the native import/export cycle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SHA = {"leaf-cm-pm": "0a4cdcdfb70aa586e80382ea0ce385c4b0cefbd957b542d80a478c73517d652e"}


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
        raise SystemExit("usage: check_roundtrip.py RUN_DIR leaf-cm-pm")
    run, arm = Path(sys.argv[1]), sys.argv[2]
    errors = []
    required = ("input.json", "roundtrip-raw.json", "model.sxi", "import.log", "export.log")
    for name in required:
        p = run / name
        if not p.is_file() or p.stat().st_size < 5:
            errors.append(f"missing or empty {name}")
    result = {"schema": "simlox-g12-var03-leaf-cm-pm-roundtrip/v1", "arm": arm,
              "source_sha256": SHA[arm], "publication_state": "not_published"}
    if not errors:
        if sha(HERE / "native-input.json") != SHA[arm] or sha(run / "input.json") != SHA[arm]:
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
