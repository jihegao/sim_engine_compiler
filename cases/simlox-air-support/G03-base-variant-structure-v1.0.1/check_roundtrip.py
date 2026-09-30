"""Check source-bound G03 native import/export and elementary run artifacts."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCES = {"add": "82e7b380402fc1e91afa3ffb104b6e99220094cf2fe3139a6c13a74e4a6327ad", "exclude": "79622dcc60d7172b3d09812f82e581d2e8a9f779790f24ab236508916a3875c2"}


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
            if table["name"] == "System" and len(rows) != len({row[0] for row in rows}):
                raise ValueError("duplicate System SID")
            assert all(len(row) == len(table["columns"]) for row in rows), table["name"]
            tables[table["name"]] = (table["columns"], rows)
    return tables


def check(run):
    invocation = native_json(run / "invocation.json")
    variant = invocation["variant"]
    expected_sha = SOURCES[variant]
    differences = []
    if sha(HERE / f"{variant}-input.json") != expected_sha or sha(run / "input.json") != expected_sha:
        differences.append("source fingerprint differs")
    source = populated(native_json(run / "input.json"))
    exported = populated(native_json(run / "roundtrip-raw.json"))
    for name, contents in source.items():
        if exported.get(name) != contents:
            differences.append(f"roundtrip changed {name}")
    for log, marker in (("import.log", "Import completed!"), ("export.log", "Export completed!")):
        if marker not in (run / log).read_text(encoding="utf-8-sig", errors="replace"):
            differences.append(f"missing {marker}")
    report = native_json(run / "report-raw.json")
    if not isinstance(report, dict) or not report:
        differences.append("invalid/empty report")
    else:
        tables = {table["name"]: table for table in report["report"]["tables"]}
        if not {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(tables):
            differences.append("missing default metrics and stock ledgers")
        else:
            system = tables["SystemResults"]
            names = [column["name"] for column in system["columns"]]
            rows = [row for instance in system["instances"] for row in instance["rows"]]
            if len(rows) != 72 or not rows or rows[-1][names.index("NSYRY")] != 1:
                differences.append("36-hour terminal one-variant ready state absent")
            if any(row[names.index("NFAIL")] != 0 for row in rows):
                differences.append("unexpected failure in zero-rate structure probe")
            stock = tables["StockTotalResults"]
            stock_names = [column["name"] for column in stock["columns"]]
            stock_rows = [row for instance in stock["instances"] for row in instance["rows"]]
            if not stock_rows or any(row[stock_names.index("NBO")] != 0 for row in stock_rows):
                differences.append("unexpected stock backorder")
    if "Input conversion completed. Errors: 0" not in (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"):
        differences.append("conversion did not finish with zero errors")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    sid = "TEACH-VAR-ADD" if variant == "add" else "TEACH-VAR-EX"
    if f"mission allocates system: <{sid}," not in log or f"mission starting, duration: 2 : <{sid}," not in log or f"System arrives <{sid}," not in log or "mission success" not in log:
        differences.append("variant individual mission lifecycle absent")
    if not (run / "model.sxo").is_file() or (run / "model.sxo").stat().st_size <= 4:
        differences.append("missing output model")
    return {"schema": "simlox-g03-base-variant-v100-check/v1", "passed": not differences, "differences": differences, "variant": variant, "source_sha256": expected_sha, "roundtrip_sha256": sha(run / "roundtrip-raw.json"), "report_sha256": sha(run / "report-raw.json"), "populated_tables": sorted(source), "scope": "native_import_export_and_basic_output_only", "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = check(Path(sys.argv[1]))
    except Exception as exc:
        result = {"passed": False, "differences": [f"{type(exc).__name__}: {exc}"], "publication_state": "not_published"}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
