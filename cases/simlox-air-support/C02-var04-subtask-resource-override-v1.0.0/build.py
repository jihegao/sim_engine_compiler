"""Build or byte-check the frozen C02.var04 pair from accepted C02."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C02-joint-resources-v1.0.2" / "inputs" / "single-equipment-zero.json"
PARENT_SHA = "f22fa4ef442ec7690238d86b1a04f18c6455ae1aa56c769cfbbe4025786ab5a5"
CONTRACT_SHA = "5458f7b0615ecd8e25d1cba9fd25b14151297112c4446f29eb8bac3371ad31a3"
DESCRIPTIONS = {
    "joint": "C02.var04 joint explicit INSPECT set with unavailable E-GSE",
    "crewonly": "C02.var04 crew-only explicit INSPECT set omitting main E-GSE",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [t for t in document["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]["instances"][0]


def build(parent: dict, arm: str) -> dict:
    result = copy.deepcopy(parent)
    table(result, "ProblemDescription")["rows"][0][0] = DESCRIPTIONS[arm]
    main = table(result, "TaskResource")["rows"]
    assert main == []
    main.extend([
        ["PREP-FIXED", "P-CREW", 1, 1, None, None, None, None],
        ["PREP-FIXED", "E-GSE", 1, 1, None, None, None, None],
    ])
    explicit = table(result, "SubTaskResource")["rows"]
    assert len(explicit) == 2 and [row[2] for row in explicit] == ["P-CREW", "E-GSE"]
    if arm == "crewonly":
        explicit.pop()
    return result


def flattened(document: dict) -> dict[str, object]:
    result = {}
    for t in document["model"]["tables"]:
        for i, instance in enumerate(t["instances"]):
            for j, row in enumerate(instance["rows"]):
                assert len(row) == len(t["columns"])
                for column, value in zip(t["columns"], row):
                    result[f"{t['name']}[{i},{j}].{column['name']}"] = value
    return result


def diff(left: dict, right: dict) -> list[dict]:
    a, b = flattened(left), flattened(right)
    return [{"cell": key, "before_exists": key in a, "before": a.get(key),
             "after_exists": key in b, "after": b.get(key)}
            for key in sorted(a.keys() | b.keys())
            if (key in a) != (key in b) or a.get(key) != b.get(key)]


def frozen_write(path: Path, data: bytes) -> None:
    if path.exists():
        assert path.read_bytes() == data, f"frozen bytes changed: {path}"
    else:
        path.write_bytes(data)


def main() -> None:
    assert sha((HERE / "contract.json").read_bytes()) == CONTRACT_SHA
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    parent = json.loads(raw)
    models = {arm: build(parent, arm) for arm in DESCRIPTIONS}
    for arm, model in models.items():
        data = (json.dumps(model, ensure_ascii=False, indent=2) + "\n").encode()
        frozen_write(HERE / f"{arm}-input.json", data)
        print(arm, len(data), sha(data))
    record = {
        "schema": "c02-var04-v100-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "parent_to_joint": diff(parent, models["joint"]),
        "parent_to_crewonly": diff(parent, models["crewonly"]),
        "joint_to_crewonly": diff(models["joint"], models["crewonly"]),
    }
    assert len(record["joint_to_crewonly"]) == 10
    assert {r["cell"].split("[")[0] for r in record["joint_to_crewonly"]} == {
        "ProblemDescription", "SubTaskResource"}
    frozen_write(HERE / "exact-diff.json", (json.dumps(record, indent=2) + "\n").encode())


if __name__ == "__main__":
    main()
