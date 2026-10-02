"""Build matched h9/h11 BETWEEN arrivals from accepted I02.var03."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var03-between-transfer-v1.0.0" / "native-input.json"
PARENT_SHA = "4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560"
ARMS = {"early": 9.0, "late": 11.0}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(hour: float, arm: str) -> dict:
    assert sha(PARENT) == PARENT_SHA, "accepted I02.var03 source changed"
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    transfer = tables["ItemTransfer"]
    rows = transfer["instances"][0]["rows"]
    names = [c["name"] for c in transfer["columns"]]
    assert len(rows) == 2
    assert rows[0] == ["<OUTSIDE>", "DEPOT-01", "TEACH-LRU-01", 4.0, 1, 0.0, None]
    assert rows[1] == ["DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 1, 0.0, None]
    rows[1][names.index("TFTIME")] = hour
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = (
        f"I02.var10 {arm.upper()} one-unit BETWEEN depot to base at h{hour:g} after h4 IN"
    )
    return doc


if __name__ == "__main__":
    for arm, hour in ARMS.items():
        raw = (json.dumps(build(hour, arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        out = HERE / f"{arm}-input.json"
        if out.exists():
            assert out.read_bytes() == raw, f"frozen {arm} input differs"
        else:
            out.write_bytes(raw)
        print(arm, sha(out), len(raw))
