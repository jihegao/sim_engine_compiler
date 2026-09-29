"""Check one traditional-clock matrix variant's import/export identity."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE_SHA = {
    "item-calhours": "e6287abc8e3292aeef8ac2b2ff30daecddcb998eb2659c4741690e70b9879239",
    "item-missions": "99b3daaa36febae511e195c71f739dd34b23182f7c8e49f6db47b433b35c5dbc",
    "rate-ophours": "b76dd77056378ca06c0134ddd363816d9c9ac211e4f36181fb597eca0e9b4797",
    "rate-calhours": "70ba834f4fb2c6bd2ba4558e1c499024652b533f297951e53445585925b9e713",
    "rate-missions": "0fb2b7dd2761fe051d5ebc3c2c2cfdd957142c4f60db7c027efaa10a7c289262",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
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
            elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
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
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    variant = invocation["variant"]
    if variant not in SOURCE_SHA:
        raise ValueError(f"unknown sealed variant {variant}")
    issues: list[str] = []
    required = ["input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log"]
    for name in required:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            issues.append(f"missing/empty {name}")
    if issues:
        return {"schema": "simlox-d02-var06-roundtrip/v1", "variant": variant,
                "passed": False, "differences": issues}
    expected = SOURCE_SHA[variant]
    if sha(run / "input.json") != expected or sha(HERE / f"native-input-{variant}.json") != expected:
        issues.append("input source fingerprint differs")
    before = populated(parse_native(run / "input.json"))
    after = populated(parse_native(run / "roundtrip-raw.json"))
    for name, table in before.items():
        if after.get(name) != table:
            issues.append(f"business columns/rows changed or missing in {name}")
    expected_count = 18 if variant.startswith("item-") else 19
    if len(before) != expected_count:
        issues.append(f"source row-containing table count {len(before)} != {expected_count}")
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    return {"schema": "simlox-d02-var06-roundtrip/v1", "variant": variant,
            "passed": not issues, "differences": issues,
            "source_sha256": expected, "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "sxi_sha256": sha(run / "model.sxi"),
            "row_containing_tables": sorted(before),
            "scope": "import_export_identity_only", "publication_state": "not_published"}


def main() -> int:
    try:
        result = validate(Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result = {"schema": "simlox-d02-var06-roundtrip/v1", "passed": False,
                  "differences": [f"checker error: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
