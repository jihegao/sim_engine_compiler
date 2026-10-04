"""Read-only full authored-row and instance metadata comparison for K02.var01."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE_SHA = {
    "inactive2": "0614e3cb935b519369197b3d3ee4991a28c25cb80b6f9a593615a12fa85f0389",
    "named": "b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Installed native exporter may emit trailing commas.
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


def tables(path):
    result = {}
    for table in parse(path)["model"]["tables"]:
        assert table["name"] not in result
        result[table["name"]] = table
    return result


def check(arm, run):
    assert arm in SOURCE_SHA
    assert sha(HERE / f"{arm}-input.json") == sha(run / "input.json") == SOURCE_SHA[arm]
    before, after = tables(run / "input.json"), tables(run / "roundtrip-raw.json")
    issues = []
    row_tables = []
    instance_counts = {}
    native_added_empty_default = False
    for name, source in before.items():
        exported = after.get(name)
        if exported is None:
            issues.append(f"missing table {name}")
            continue
        if source["columns"] != exported["columns"]:
            issues.append(f"column definitions differ: {name}")
        if any(instance["rows"] for instance in source["instances"]):
            row_tables.append(name)
            if name == "Station" and arm == "named":
                extra = exported["instances"][:1]
                native_added_empty_default = (
                    len(exported["instances"]) == len(source["instances"]) + 1
                    and len(extra) == 1 and extra[0].get("instance_name") == ""
                    and extra[0].get("rows") == [[None] * len(source["columns"])]
                    and extra[0].get("inactive_rows") in (None, [])
                )
                if not native_added_empty_default or source["instances"] != exported["instances"][1:]:
                    issues.append("named Station instances differ beyond allowed empty default")
            elif source["instances"] != exported["instances"]:
                issues.append(f"authored instances/rows/inactive metadata differ: {name}")
            instance_counts[name] = len(source["instances"])
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("import completion marker absent")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        issues.append("export completion marker absent")
    op = before["OperationProfile"]
    names = [c["name"] for c in op["columns"]]
    precise = op["instances"][0]["rows"][0][names.index("DTIM")]
    native_op = after["OperationProfile"]["instances"][0]["rows"][0][names.index("DTIM")]
    if precise != native_op or precise != 0.3333333333333333:
        issues.append("OperationProfile.DTIM binary64 value changed")
    return {
        "schema": "simlox-k02-var01-structured-roundtrip/v1", "arm": arm,
        "passed": not issues, "differences": issues,
        "input_sha256": SOURCE_SHA[arm], "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
        "authored_row_table_count": len(row_tables),
        "authored_row_tables": sorted(row_tables),
        "authored_instance_counts": instance_counts,
        "native_added_row_tables": sorted(name for name, table in after.items() if name not in row_tables and any(x["rows"] for x in table["instances"])),
        "double_precision_binary64_preserved": precise == native_op,
        "native_added_empty_default_station_instance": native_added_empty_default,
        "precision_source_decimal": "0.3333333333333333",
    }


if __name__ == "__main__":
    try:
        result = check(sys.argv[1], Path(sys.argv[2]))
    except Exception as exc:
        result = {"passed": False, "differences": [f"checker exception: {exc}"]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
