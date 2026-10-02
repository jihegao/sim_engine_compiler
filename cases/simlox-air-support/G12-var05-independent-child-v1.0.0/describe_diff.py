"""Freeze the exact independently deployed child delta."""
import hashlib
import json
from pathlib import Path
from build import HERE, PARENT, OUT as CHILD

OUT = HERE / "exact-diff.json"
CHANGED = {"ProblemDescription", "Unit", "SystemDeployment", "Operations"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    before = {t["name"]: t for t in json.loads(PARENT.read_bytes())["model"]["tables"]}
    after = {t["name"]: t for t in json.loads(CHILD.read_bytes())["model"]["tables"]}
    changed = {name: {"before": before.get(name), "after": after.get(name)}
               for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)}
    if set(changed) != CHANGED or len(before) != 32 or len(after) != 32:
        raise ValueError("unexpected table delta")
    doc = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G12",
           "variant_id": "G12.var05", "parent_sha256": sha(PARENT),
           "input_sha256": sha(CHILD), "changed": changed}
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes() != data:
            raise ValueError("frozen exact diff differs")
    else:
        OUT.write_bytes(data)
    print(json.dumps({"diff_sha256": hashlib.sha256(data).hexdigest(),
                      "changed_tables": sorted(changed)}))


if __name__ == "__main__":
    main()
