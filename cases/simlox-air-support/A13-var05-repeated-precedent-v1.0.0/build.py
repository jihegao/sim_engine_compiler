"""Build matched repeated-RECON control and ambiguous START-key probe."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A13-start-dependence-v1.0.0" / "dependent-input.json"
STRUCTURE = ROOT / "A13-var01-multiple-predecessors-v1.0.0" / "multiple-input.json"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
STRUCTURE_SHA = "1d2226850d07d7caf5f58e825bb2d3fdf498f7626fb58e4a6ed4bcfa469d18ae"


def source(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"accepted source changed: {path}")
    return json.loads(raw)


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def col(t: dict, name: str) -> int:
    return [c["name"] for c in t["columns"]].index(name)


def build(dependent: bool) -> dict:
    doc = copy.deepcopy(source(PARENT, PARENT_SHA))
    donor = source(STRUCTURE, STRUCTURE_SHA)
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "A13.var05 duplicate RECON START key" if dependent else "A13.var05 duplicate RECON no-row control"
    )
    deploy = table(doc, "SystemDeployment")
    donor_deploy = table(donor, "SystemDeployment")
    if deploy["columns"] != donor_deploy["columns"]:
        raise ValueError("SystemDeployment columns differ")
    deploy["instances"][0]["rows"][0][col(deploy, "QTYPS")] = 3
    profile = table(doc, "OperationProfile")
    recon = next(r for r in profile["instances"][0]["rows"] if r[col(profile, "SPRID")] == "RECON")
    recon[col(profile, "IQTY")] = 2
    if not dependent:
        doc["model"]["tables"].remove(table(doc, "MissionDependence"))
    return doc


def main() -> None:
    for label, dependent in (("control", False), ("dependency", True)):
        raw = (json.dumps(build(dependent), ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{label}-input.json"
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {label} input changed")
        path.write_bytes(raw)
        print(label, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
