"""Check every authored populated table after native import/export."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
INPUT_SHA = "d1ff80f7e0de8259b6f38b6373c7ad4797d897e17c4397a7060dfbefbeb851dc"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # SIMLOX 2017 export puts trailing commas in some arrays.
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


def populated(path):
    result = {}
    for table in parse(path)["model"]["tables"]:
        name = table["name"]
        assert name not in result
        rows = [r for instance in table["instances"] for r in instance["rows"]]
        if rows:
            assert all(len(r) == len(table["columns"]) for r in rows)
            result[name] = {"columns": table["columns"], "rows": rows}
    return result


def check(run):
    assert sha(HERE / "native-input.json") == sha(run / "input.json") == INPUT_SHA
    before = populated(run / "input.json")
    after = populated(run / "roundtrip-raw.json")
    differences = [name for name, value in before.items() if after.get(name) != value]
    if "Import completed!" not in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace"):
        differences.append("import completion marker")
    if "Export completed!" not in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"):
        differences.append("export completion marker")
    return {"schema": "simlox-k01-var04-roundtrip/v1", "passed": not differences,
            "differences": differences, "input_sha256": INPUT_SHA,
            "roundtrip_sha256": sha(run / "roundtrip-raw.json"),
            "populated_tables": sorted(before), "populated_table_count": len(before),
            "native_added_populated_tables": sorted(set(after) - set(before))}


if __name__ == "__main__":
    try:
        result = check(Path(sys.argv[1]))
    except Exception as exc:
        result = {"passed": False, "differences": [f"checker exception: {exc}"]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
