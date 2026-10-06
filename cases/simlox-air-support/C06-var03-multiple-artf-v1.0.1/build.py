"""Create or byte-check the two frozen C06.var03 authored inputs."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C06-alternative-resource-v1.0.0" / "primary-0-artf-2-input.json"
PARENT_SHA = "42aeabcf2f7ca79efc568c515bfd5989715cdc0270f59acaad3bfe46c974bd1f"
CONTRACT_SHA = "48a29f63e819e85dc3f9de856199c63441f32f34104dade338ef1ca246bd2384"
ARMS = {"factor1": 1.0, "factor3": 3.0}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]["instances"][0]


def build(parent: dict, arm: str) -> dict:
    doc = copy.deepcopy(parent)
    factor = ARMS[arm]
    table(doc, "ProblemDescription")["rows"][0][0] = (
        f"C06.var03 two alternative resource requirements; second ARTF {factor:g}; first ARTF 2"
    )
    table(doc, "Resource")["rows"].extend([
        ["P-AUX", "Second required primary personnel", None, None, None, "SPECIAL", None, None],
        ["P-AUXALT", "Second alternative personnel", None, None, None, "SPECIAL", None, None],
    ])
    table(doc, "ResourceAllocation")["rows"].extend([
        ["AIR_BASIC", "P-AUX", "BASE-01", 0, None],
        ["AIR_BASIC", "P-AUXALT", "BASE-01", 2, None],
    ])
    table(doc, "SubTaskResource")["rows"].append(
        ["PREP-FIXED", 1, "P-AUX", 1, 1, "P-AUXALT", factor, None, None]
    )
    return doc


def flatten(doc: dict) -> dict:
    out = {}
    for t in doc["model"]["tables"]:
        for instance_no, inst in enumerate(t["instances"]):
            for row_no, row in enumerate(inst["rows"]):
                for col, value in zip(t["columns"], row):
                    out[f"{t['name']}[{instance_no},{row_no}].{col['name']}"] = value
    return out


def changes(a: dict, b: dict) -> list[dict]:
    left, right = flatten(a), flatten(b)
    return [{"cell": k, "before": left.get(k), "after": right.get(k)}
            for k in sorted(left.keys() | right.keys()) if left.get(k) != right.get(k)]


def frozen_write(path: Path, raw: bytes) -> None:
    if path.exists():
        assert path.read_bytes() == raw, f"frozen bytes differ: {path}"
    else:
        path.write_bytes(raw)


def main() -> None:
    assert sha((HERE / "contract.json").read_bytes()) == CONTRACT_SHA
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    parent = json.loads(raw)
    arms = {name: build(parent, name) for name in ARMS}
    for name, doc in arms.items():
        path = HERE / f"{name}-input.json"
        payload = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        frozen_write(path, payload)
        print(name, len(payload), sha(payload))
    diff = {"schema": "c06-var03-v101-exact-diff/v1",
            "parent_sha256": PARENT_SHA,
            "parent_to_factor1": changes(parent, arms["factor1"]),
            "parent_to_factor3": changes(parent, arms["factor3"]),
            "factor1_to_factor3": changes(arms["factor1"], arms["factor3"])}
    frozen_write(HERE / "exact-diff.json", (json.dumps(diff, indent=2) + "\n").encode())
    assert {x["cell"].split("[")[0] for x in diff["parent_to_factor1"]} == {
        "ProblemDescription", "Resource", "ResourceAllocation", "SubTaskResource"}
    assert len(diff["factor1_to_factor3"]) == 2


if __name__ == "__main__":
    main()
