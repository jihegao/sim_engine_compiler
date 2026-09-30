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
    "control": "68c43a51e199462cfb8bda26fa23de90f5ed4776d5feff92e5339640e1330111",
    "explicit": "10cc545f9fb842048518ac94902d5854e1b3e5148114e8b2a3613ff09a22a381",
    "profile": "11993115206c2176c45f83e4706ede703b5f1a994ed7c0ad737fe37c07c759cb",
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
    assert set(changes["parent_to_control"]) == {"ProblemDescription", "Control", "OperationProfile", "ResultCollection"}
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
