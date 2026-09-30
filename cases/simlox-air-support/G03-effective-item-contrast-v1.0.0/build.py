"""Build fixed-seed G03 material-inheritance contrasts from accepted sources."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENTS = {
    "add": (ROOT / "G03-base-variant-structure-v1.0.1" / "add-input.json", "82e7b380402fc1e91afa3ffb104b6e99220094cf2fe3139a6c13a74e4a6327ad"),
    "exclude": (ROOT / "G03-base-variant-structure-v1.0.1" / "exclude-input.json", "79622dcc60d7172b3d09812f82e581d2e8a9f779790f24ab236508916a3875c2"),
}
D01 = ROOT / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
D01_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
VARIANTS = {
    "base-control": ("add", "TEACH-AIR-01", "TEACH-LRU-BASE"),
    "add-inherited": ("add", "TEACH-VAR-ADD", "TEACH-LRU-BASE"),
    "add-extra": ("add", "TEACH-VAR-ADD", "TEACH-LRU-ADD"),
    "exclude-base": ("exclude", "TEACH-VAR-EX", "TEACH-LRU-BASE"),
}


def rows(doc, name):
    return next(table for table in doc["model"]["tables"] if table["name"] == name)["instances"][0]["rows"]


def build(variant):
    branch, deployed, failing_item = VARIANTS[variant]
    parent, parent_sha = PARENTS[branch]
    assert hashlib.sha256(parent.read_bytes()).hexdigest() == parent_sha
    assert hashlib.sha256(D01.read_bytes()).hexdigest() == D01_SHA
    child = copy.deepcopy(json.loads(parent.read_text(encoding="utf-8")))
    repair_source = json.loads(D01.read_text(encoding="utf-8"))
    rows(child, "ProblemDescription")[0][0] = f"G03 effective item contrast {variant}; fixed-seed D01 repair method"
    rows(child, "SystemDeployment")[0][0] = deployed
    rows(child, "Unit")[0][1] = "One aircraft fixed-seed item contrast"
    for item in rows(child, "Item"):
        item[3] = 300000 if item[0] == failing_item else 0
    rows(child, "OperationProfile").extend(copy.deepcopy(rows(repair_source, "OperationProfile")[1:]))
    system_repair = copy.deepcopy(rows(repair_source, "SystemRepair")[0])
    for system in rows(child, "System"):
        new_row = copy.deepcopy(system_repair)
        new_row[0] = system[0]
        rows(child, "SystemRepair").append(new_row)
    item_repair = copy.deepcopy(rows(repair_source, "ItemRepair")[0])
    item_repair[0] = failing_item
    rows(child, "ItemRepair").append(item_repair)
    stock = copy.deepcopy(rows(repair_source, "StockAllocation")[0])
    stock[1] = failing_item
    rows(child, "StockAllocation").append(stock)
    return child


if __name__ == "__main__":
    for variant in VARIANTS:
        target = HERE / f"{variant}-input.json"
        generated = json.dumps(build(variant), indent=2, ensure_ascii=False) + "\n"
        if target.exists():
            assert target.read_text(encoding="utf-8") == generated, target
        else:
            target.write_text(generated, encoding="utf-8", newline="\n")
        print(variant, hashlib.sha256(target.read_bytes()).hexdigest())
