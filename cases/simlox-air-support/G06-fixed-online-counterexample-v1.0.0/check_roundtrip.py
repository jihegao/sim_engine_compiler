"""Check exact authored table roundtrip and native output for G06 fixed arms."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCES = {
    "Y": "ce407655c86e0af85460ba30d32eb28ffc93f54c1acc68bbf4d6fcbee79e723b",
    "N": "06a3cb45320c90f4a90027f562c17e86be46b25bd62b9106b1f6ab0cbcc99aa8",
}
SOURCE_NAMES = {"Y": "fixed-input.json", "N": "fixed-deferred-input.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # SIMLOX 2017 occasionally emits trailing commas. Parse a copy only.
        out = []
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


def authored_tables(document: dict) -> dict:
    result = {}
    for table in document["model"]["tables"]:
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if not rows:
            continue
        if table["name"] in result or any(len(row) != len(table["columns"]) for row in rows):
            raise ValueError(f"duplicate or nonrectangular {table['name']}")
        result[table["name"]] = (table["columns"], rows)
    return result


def check(run: Path) -> dict:
    arm = native_json(run / "invocation.json")["arm"]
    expected = SOURCES[arm]
    issues = []
    if sha(HERE / SOURCE_NAMES[arm]) != expected or sha(run / "input.json") != expected:
        issues.append("source fingerprint differs")
    before = authored_tables(native_json(run / "input.json"))
    after = authored_tables(native_json(run / "roundtrip-raw.json"))
    if len(before) != 23:
        issues.append(f"expected 23 authored row tables, got {len(before)}")
    for name, value in before.items():
        if after.get(name) != value:
            issues.append(f"roundtrip changed {name}")
    for name, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!"),
                         ("run.log", "Input conversion completed. Errors: 0")):
        if marker not in (run / name).read_text(encoding="utf-8-sig", errors="replace"):
            issues.append(f"missing {marker}")
    report = native_json(run / "report-raw.json")
    names = {table["name"] for table in report["report"]["tables"]}
    if not {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(names):
        issues.append("required report table absent")
    return {"schema": "simlox-g06-fixed-online-counterexample-roundtrip/v1", "passed": not issues,
            "differences": issues, "arm": arm, "source_sha256": expected,
            "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "report_sha256": sha(run / "report-raw.json"),
            "row_tables": sorted(before), "native_added_row_tables": sorted(set(after) - set(before)),
            "scope": "import_export_and_basic_output_only", "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = check(Path(sys.argv[1]))
    except Exception as error:
        result = {"passed": False, "differences": [f"{type(error).__name__}: {error}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
