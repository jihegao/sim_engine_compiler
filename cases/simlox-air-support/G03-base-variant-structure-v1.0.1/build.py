"""Build the two G03 BSID structure probes from the accepted A01 source."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"


def table(model, name):
    return next(t for t in model["tables"] if t["name"] == name)["instances"][0]["rows"]


def build(variant):
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    document = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    model = document["model"]
    base = table(model, "System")[0]
    base[3] = None  # Let the native engine derive FRT from the structure.
    base[4] = None
    base[1] = "Base aircraft with installed base LRU"
    sid = "TEACH-VAR-ADD" if variant == "add" else "TEACH-VAR-EX"
    system = copy.deepcopy(base)
    system[0] = sid
    system[1] = "Variant adding LRU" if variant == "add" else "Variant excluding base LRU"
    system[9] = base[0]  # BSID, never CBSID.
    table(model, "System").append(system)
    item_template = [None] * 29
    item_template[3] = 0
    item_template[4] = "OPHOURS"
    item_template[5] = "LRU"
    item_template[20] = 1.0
    base_item = copy.deepcopy(item_template)
    base_item[0:2] = ["TEACH-LRU-BASE", "Base installed LRU"]
    table(model, "Item").append(base_item)
    table(model, "ItemStructure").append(["TEACH-LRU-BASE", base[0], 1, 1.0, None, None, None, None, None])
    if variant == "add":
        extra_item = copy.deepcopy(item_template)
        extra_item[0:2] = ["TEACH-LRU-ADD", "Variant additional LRU"]
        table(model, "Item").append(extra_item)
        table(model, "ItemStructure").append(["TEACH-LRU-ADD", sid, 1, 1.0, None, None, None, None, None])
    else:
        table(model, "ItemStructure").append(["TEACH-LRU-BASE", sid, 0, 1.0, None, None, None, None, None])
    table(model, "SystemDeployment")[0][0] = sid
    table(model, "Unit")[0][1] = "One variant aircraft teaching unit"
    table(model, "ProblemDescription")[0][0] = f"G03 BSID {variant} flown variant; A01 teaching parent; no J35/F35 equivalence"
    return document


if __name__ == "__main__":
    for variant in ("add", "exclude"):
        target = HERE / f"{variant}-input.json"
        generated = json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n"
        if target.exists():
            assert target.read_text(encoding="utf-8") == generated, target
        else:
            target.write_text(generated, encoding="utf-8", newline="\n")
        print(variant, hashlib.sha256(target.read_bytes()).hexdigest())
