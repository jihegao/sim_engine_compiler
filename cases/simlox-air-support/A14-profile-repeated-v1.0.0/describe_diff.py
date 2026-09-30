"""Verify and seal exact A14 repeated-profile source deltas."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A14-continuous-end-abort-v1.0.1" / "control-input.json"
DONOR = HERE.parent / "A09-hierarchical-operation-profile-v1.0.1" / "native-nested.json"
EXPECTED = {
    "parent": "f81445ad2daba09321e7a55ad67c5355b7e4a14ec3a58bbf10fbfcd18b343376",
    "donor": "e795c5fcf563f8e42ab9e9cb161a925bec3b06157cbbecde7901e99bfec91d85",
    "control": "ebbc28a0337410542eb67a78d9161bbca966ed91ec92e37021ef2d2b75aa8254",
    "explicit": "1f2f70aedaa346d75c8b5eeffe88947216da3e643f52eea6de80897bd9c32bef",
    "profile": "7cc231074f863e96db018876e5864cf2ba45a21555c66f5d60ed7aa607635408",
}


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_bytes())["model"]["tables"]}


def delta(before: dict, after: dict) -> dict:
    return {n: {"before": before.get(n), "after": after.get(n)}
            for n in sorted(before.keys() | after.keys()) if before.get(n) != after.get(n)}


def main() -> None:
    paths = {"parent": PARENT, "donor": DONOR,
             **{v: HERE / f"{v}-input.json" for v in ("control", "explicit", "profile")}}
    for name, path in paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED[name], name
    model = {name: tables(path) for name, path in paths.items()}
    changes = {"parent_to_control": delta(model["parent"], model["control"]),
               "control_to_explicit": delta(model["control"], model["explicit"]),
               "control_to_profile": delta(model["control"], model["profile"])}
    assert set(changes["parent_to_control"]) == {"ProblemDescription", "Control", "OperationProfile"}
    assert set(changes["control_to_explicit"]) == {"ProblemDescription", "MissionDependence"}
    assert set(changes["control_to_profile"]) == {"ProblemDescription", "MissionDependenceProfile"}
    result = {"schema": "simlox-a14-repeated-profile-exact-diff/v1", "sources_sha256": EXPECTED,
              "changes": changes}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
