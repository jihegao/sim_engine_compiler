"""Check source-bound G03 material contrast import/export and basic output."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCES = {
    "base-control": "246449c7aeb1866bb73cdd73e810dc2da8b1fd7ffdb804742b72f6c3a7bc63b5",
    "add-inherited": "6c8f06d94422bbafe901c44712e1a47a43582048cb5e6e5ff67b16cd820c38b9",
    "add-extra": "c12e1ae3ddb58e0daa4432e243e547b1fd4a174244dff93861ba86b84679f497",
    "exclude-base": "5599a24ad957b967bae70d857944773e218b10820f2046213297945c19f19148",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path):
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


def populated(doc):
    tables = {}
    for table in doc["model"]["tables"]:
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            if table["name"] in tables or any(len(row) != len(table["columns"]) for row in rows):
                raise ValueError(f"duplicate or nonrectangular table {table['name']}")
            tables[table["name"]] = (table["columns"], rows)
    return tables


def check(run):
    variant = native_json(run / "invocation.json")["variant"]
    expected_sha = SOURCES[variant]
    differences = []
    if sha(HERE / f"{variant}-input.json") != expected_sha or sha(run / "input.json") != expected_sha:
        differences.append("source fingerprint differs")
    before = populated(native_json(run / "input.json"))
    after = populated(native_json(run / "roundtrip-raw.json"))
    for name, contents in before.items():
        if after.get(name) != contents:
            differences.append(f"roundtrip changed {name}")
    for log, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!")):
        if marker not in (run / log).read_text(encoding="utf-8-sig", errors="replace"):
            differences.append(f"missing {marker}")
    if "Input conversion completed. Errors: 0" not in (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"):
        differences.append("nonzero or missing conversion status")
    report = native_json(run / "report-raw.json")
    if not isinstance(report, dict) or not {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset({table["name"] for table in report["report"]["tables"]}):
        differences.append("required report tables missing")
    return {"schema": "simlox-g03-effective-item-v100-roundtrip/v1", "passed": not differences, "differences": differences, "variant": variant, "source_sha256": expected_sha, "roundtrip_sha256": sha(run / "roundtrip-raw.json"), "report_sha256": sha(run / "report-raw.json"), "populated_tables": sorted(before), "scope": "native_import_export_and_basic_output_only", "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = check(Path(sys.argv[1]))
    except Exception as exc:
        result = {"passed": False, "differences": [f"{type(exc).__name__}: {exc}"], "publication_state": "not_published"}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
