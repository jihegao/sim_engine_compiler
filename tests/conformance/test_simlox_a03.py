"""A03 parent boundary and two-aircraft event acceptance."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "cases/simlox-air-support/A03-two-aircraft-formation"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a03_is_exactly_one_wave_two_aircraft_delta() -> None:
    builder = load("build")
    parent = json.loads(builder.PARENT.read_text(encoding="utf-8"))
    child = builder.build()
    assert builder.sha256(builder.PARENT) == builder.PARENT_SHA256
    assert sorted(builder.changed_tables(parent, child)) == ["MissionType", "OperationProfile", "SystemDeployment"]
    assert [row["STIM"] for row in builder.rows(child, "OperationProfile")] == [8.0]
    assert [(row["NOS"], row["MNOS"]) for row in builder.rows(child, "MissionType")] == [(2, 2)]
    assert [row["QTYPS"] for row in builder.rows(child, "SystemDeployment")] == [2]
    assert (BASE / "native-input.json").read_bytes() == (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode()


def test_a03_rejects_single_aircraft_and_split_mission() -> None:
    validator = load("validate")
    tag = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    lines = [
        "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
        f"Time: 7 {tag} mission created: ",
        f"Time: 7 {tag} mission activated, systems requested: 2",
        f"Time: 7 {tag} mission allocates system: <TEACH-AIR-01,0>",
        f"Time: 7 {tag} mission allocates system: <TEACH-AIR-01,1>",
        f"Time: 8 {tag} mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
        f"Time: 10 {tag} mission success: ",
        f"Time: 10 {tag} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
    ]
    assert validator.check_events("\n".join(lines)) == []
    assert validator.check_events("\n".join(lines).replace(",<TEACH-AIR-01,1>", ""))
    assert validator.check_events("\n".join(lines).replace(tag, "<BASIC-MISSION,TEACH-UNIT,0,0,1>", 1))
