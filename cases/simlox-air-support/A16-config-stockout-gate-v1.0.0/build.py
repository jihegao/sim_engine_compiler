"""Remove the B configuration spare from the frozen two-config A16 model."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A16-two-config-reconfiguration-v1.0.0" / "native-input.json"
PARENT_SHA = "07d92a51632b770dfda9d71fdcf042bd73642cc64433171a71e4bab8d76f1ef7"
E02 = HERE.parent / "E02-zero-stock-local-backorder-v1.0.0" / "native-input.json"
E02_SHA = "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd"


def rows(doc, name):
    return next(t for t in doc["model"]["tables"] if t["name"] == name)["instances"][0]["rows"]


def build():
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(E02.read_bytes()).hexdigest() == E02_SHA
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    rows(doc, "ProblemDescription")[0][0] = "A16 paired B-stockout control: no B item for second reconfiguration"
    stock = rows(doc, "StockAllocation")
    target = next(row for row in stock if row[1] == "TEACH-LRU-B")
    target[3] = 0  # E02 accepted zero nominal stock form.
    return doc


if __name__ == "__main__":
    target = HERE / "native-input.json"
    generated = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if target.exists():
        assert target.read_text(encoding="utf-8") == generated
    else:
        target.write_text(generated, encoding="utf-8", newline="\n")
    print(hashlib.sha256(target.read_bytes()).hexdigest())
