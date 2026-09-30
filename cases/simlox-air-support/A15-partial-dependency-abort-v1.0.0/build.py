"""Add one custom KM utilization row to the accepted A14 abort/control pair."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT_DIR = HERE.parent / "A14-continuous-end-abort-v1.0.1"
PARENTS = {
    "control": ("control-input.json", "f81445ad2daba09321e7a55ad67c5355b7e4a14ec3a58bbf10fbfcd18b343376"),
    "dependent": ("dependent-input.json", "67484243a3b35395e21dcd6554a95c2637986086c4523d5e1ba99e2890d21de3"),
}
RATES = {"hour": (60.0, "1/HOUR"), "mission": (240.0, "1/MISSION")}
VARIANTS = tuple(f"{mode}-{rate}" for mode in PARENTS for rate in RATES)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(document: dict, name: str) -> dict:
    matches = [t for t in document["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1
    return matches[0]


def build(variant: str) -> dict:
    assert variant in VARIANTS
    mode, rate = variant.split("-")
    parent_name, parent_sha = PARENTS[mode]
    parent_bytes = (PARENT_DIR / parent_name).read_bytes()
    assert sha(parent_bytes) == parent_sha
    document = copy.deepcopy(json.loads(parent_bytes))
    table(document, "ProblemDescription")["instances"][0]["rows"][0][0] = f"A15 custom KM {mode} {rate} A14 contrast"
    operation = table(document, "OperationParameter")
    assert operation["instances"][0]["rows"] == [[None, None, None]]
    operation["instances"][0]["rows"] = [["KM", "Abstract custom mission exposure", None]]
    names = [t["name"] for t in document["model"]["tables"]]
    assert "MissionTypeUtilization" not in names
    assert [row[0] for row in table(document, "MissionType")["instances"][0]["rows"]] == ["SUPPORT", "EXECUTE"]
    amount, unit = RATES[rate]
    utilization = {
        "name": "MissionTypeUtilization",
        "columns": [
            {"datatype": "string", "key": True, "name": "MTID"},
            {"datatype": "string", "key": True, "name": "SID"},
            {"datatype": "string", "key": True, "name": "OPID"},
            {"datatype": "double", "name": "UTIL"},
            {"datatype": "string", "name": "UTILU"},
            {"datatype": "string", "name": "NOTE"},
        ],
        "instances": [{"instance_name": "", "rows": [["EXECUTE", "TEACH-AIR-01", "KM", amount, unit, None]]}],
    }
    document["model"]["tables"].insert(names.index("OperationParameter") + 1, utilization)
    assert len(document["model"]["tables"]) == len(names) + 1
    return document


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if args.write and not path.exists():
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw, f"frozen input differs: {path}"
        print(variant, sha(raw), len(raw))


if __name__ == "__main__":
    main()
