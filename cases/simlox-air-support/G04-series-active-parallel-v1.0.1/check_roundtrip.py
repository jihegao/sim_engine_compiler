"""Source-bound G04 RBD import/export and basic native-output gate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCES = {
    "series": "3adc1cf0d75dd9418e816d0e06bdc502af5d37d975beafbba8f781c94d2763e8",
    "parallel": "ea56a9daf8705189c9162529355b28636ef7db168987b17ee90cdedbe9bb4b6f",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
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


def row_tables(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            if table["name"] in result or any(len(row) != len(table["columns"]) for row in rows):
                raise ValueError(f"duplicate or nonrectangular {table['name']}")
            result[table["name"]] = (table["columns"], rows)
    return result


def check(run: Path) -> dict:
    arm = native_json(run / "invocation.json")["arm"]
    expected = SOURCES[arm]
    issues = []
    if sha(HERE / f"{arm}-input.json") != expected or sha(run / "input.json") != expected:
        issues.append("source fingerprint differs")
    before = row_tables(native_json(run / "input.json"))
    after = row_tables(native_json(run / "roundtrip-raw.json"))
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
    reports = {t["name"] for t in report["report"]["tables"]}
    if not {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(reports):
        issues.append("required report table absent")
    return {"schema": "simlox-g04-series-active-parallel-v101-roundtrip/v1", "passed": not issues,
            "differences": issues, "arm": arm, "source_sha256": expected,
            "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "report_sha256": sha(run / "report-raw.json"),
            "row_tables": sorted(before), "native_added_row_tables": sorted(set(after) - set(before)),
            "scope": "import_export_and_basic_output_only", "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = check(Path(sys.argv[1]))
    except Exception as exc:
        result = {"passed": False, "differences": [f"{type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
