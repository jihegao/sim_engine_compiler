"""Build one positive-duration IN from accepted tracked zero-duration IN."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var01-in-transfer-v1.0.2" / "native-input.json"
PARENT_SHA = "85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assert sha(PARENT) == PARENT_SHA, "accepted I02.var01 source changed"
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    transfer = tables["ItemTransfer"]
    names = [c["name"] for c in transfer["columns"]]
    row = transfer["instances"][0]["rows"][0]
    assert len(transfer["instances"][0]["rows"]) == 1 and row[names.index("TFDT")] == 0.0
    assert row[:5] == ["<OUTSIDE>", "DEPOT-01", "TEACH-LRU-01", 4.0, 1]
    row[names.index("TFDT")] = 2.0
    description = tables["ProblemDescription"]
    description["instances"][0]["rows"][0][0] = "I02.var11 IN one LRU to DEPOT-01 at h4 with TFDT2 and tracked item report"
    return doc


if __name__ == "__main__":
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    out = HERE / "native-input.json"
    if out.exists():
        assert out.read_bytes() == raw, "frozen delayed IN input differs"
    else:
        out.write_bytes(raw)
    print(sha(out), len(raw))
