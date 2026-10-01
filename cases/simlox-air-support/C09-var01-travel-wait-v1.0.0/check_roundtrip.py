"""Validate authored C09.var01 business tables after native import/export."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCES = {
    "short": "739d7a9ad8e6759a20401a3bf65c63b13c39c42e035a7d9acc28af6f5fc83fe7",
    "equal": "4595a90dafb24ebc4b36662dd2f5738d7f03f1001f4acb8347099f181c15a177",
    "long": "0bf327220330d00b79de37e920ff62529cee0d40265e9d9a1f57f0b3cb165ae7",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native SIMLOX exports may contain trailing commas. Normalize a parser
        # copy while retaining and hashing the untouched raw output.
        out: list[str] = []
        quoted = escaped = False
        for i, char in enumerate(raw):
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
            elif char == "," and raw[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def populated(doc: dict) -> dict[str, dict]:
    result = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate table {name}")
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            if any(len(row) != len(table["columns"]) for row in rows):
                raise ValueError(f"nonrectangular table {name}")
            result[name] = {"columns": table["columns"], "rows": rows}
    return result


def validate(run: Path) -> dict:
    issues: list[str] = []
    for name in ("invocation.json", "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if issues:
        return {"schema": "simlox-c09-var01-import-export/v1", "passed": False, "differences": issues}
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    variant = invocation["variant"]
    source_sha = SOURCES[variant]
    if sha(run / "input.json") != source_sha or sha(HERE / f"{variant}-input.json") != source_sha:
        issues.append("frozen source fingerprint differs")
    before = populated(parse_native(run / "input.json"))
    after = populated(parse_native(run / "roundtrip-raw.json"))
    for name, table in before.items():
        if after.get(name) != table:
            issues.append(f"authored business columns/rows changed or missing: {name}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {
        "schema": "simlox-c09-var01-import-export/v1", "passed": not issues,
        "differences": issues, "variant": variant, "source_sha256": source_sha,
        "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
        "sxi_sha256": sha(run / "model.sxi"),
        "populated_tables": sorted(before),
        "native_added_populated_tables": sorted(set(after) - set(before)),
        "scope": "import_export_identity_only", "publication_state": "not_published",
    }


def main() -> int:
    try:
        result = validate(Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result = {"schema": "simlox-c09-var01-import-export/v1", "passed": False,
                  "differences": [f"validation error: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
