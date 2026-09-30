"""Build frozen C05 mission-resource capacity candidates from accepted A03."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
PARENT_SHA256 = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"


def table(model: dict, name: str) -> dict:
    return next(t for t in model["tables"] if t["name"] == name)


def build(capacity: int) -> dict:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    result = copy.deepcopy(json.loads(raw))
    model = result["model"]
    table(model, "Resource")["instances"][0]["rows"] = [
        ["MISSION-CREW", "Mission crew held during flight", None, None, None, "SPECIAL", None, None]
    ]
    table(model, "ResourceAllocation")["instances"][0]["rows"] = [
        ["AIR_BASIC", "MISSION-CREW", "BASE-01", capacity, None]
    ]
    model["tables"].append(
        {
            "columns": [
                {"datatype": "string", "key": True, "name": "MTID"},
                {"datatype": "string", "key": True, "name": "SID"},
                {"datatype": "string", "key": True, "name": "RID"},
                {"datatype": "integer", "name": "QTY"},
                {"datatype": "string", "name": "NOTE"},
            ],
            "instances": [{"instance_name": "", "rows": [["BASIC-MISSION", "TEACH-AIR-01", "MISSION-CREW", 1, None]]}],
            "name": "MissionResource",
        }
    )
    table(model, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"C05 mission crew capacity {capacity}; two-aircraft A03 wave"
    )
    return result


def main() -> None:
    for capacity in (2, 1, 0):
        path = HERE / f"capacity-{capacity}-input.json"
        payload = (json.dumps(build(capacity), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == payload, f"frozen candidate differs: {path}"
        else:
            path.write_bytes(payload)
        print(capacity, hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    main()
