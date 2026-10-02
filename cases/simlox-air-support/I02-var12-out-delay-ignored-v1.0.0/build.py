"""Build positive TFDT on accepted zero-duration OUT with earlier IN fixed."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var02-out-transfer-v1.0.0" / "native-input.json"
PARENT_SHA = "7b15a1e0a6efcee9c772ac39dd52bb742a6eb23b6b711cf8e3cbc681aabe07e0"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assert sha(PARENT) == PARENT_SHA, "accepted I02.var02 source changed"
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    transfer = tables["ItemTransfer"]
    names = [c["name"] for c in transfer["columns"]]
    rows = transfer["instances"][0]["rows"]
    assert len(rows) == 2
    assert rows[0] == ["<OUTSIDE>", "DEPOT-01", "TEACH-LRU-01", 4.0, 1, 0.0, None]
    assert rows[1] == ["DEPOT-01", "<OUTSIDE>", "TEACH-LRU-01", 6.0, 1, 0.0, None]
    rows[1][names.index("TFDT")] = 2.0
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = (
        "I02.var12 OUT one LRU from DEPOT-01 at h6 with TFDT2 after h4 IN"
    )
    return doc


if __name__ == "__main__":
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    out = HERE / "native-input.json"
    if out.exists():
        assert out.read_bytes() == raw, "frozen OUT-delay input differs"
    else:
        out.write_bytes(raw)
    print(sha(out), len(raw))
