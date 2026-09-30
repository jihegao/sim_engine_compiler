"""Verify exact source deltas and seal the A14 v1.0.1 structural diff."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-continuous-baseline-v1.0.1" / "native-continuous.json"
EXPECTED = {
    "parent": "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea",
    "control": "f81445ad2daba09321e7a55ad67c5355b7e4a14ec3a58bbf10fbfcd18b343376",
    "dependent": "67484243a3b35395e21dcd6554a95c2637986086c4523d5e1ba99e2890d21de3",
}


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_bytes())["model"]["tables"]}


def delta(before: dict, after: dict) -> dict:
    return {n: {"before": before.get(n), "after": after.get(n)}
            for n in sorted(before.keys() | after.keys()) if before.get(n) != after.get(n)}


def main() -> None:
    paths = {"parent": PARENT, "control": HERE / "control-input.json",
             "dependent": HERE / "dependent-input.json"}
    for name, path in paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED[name], name
    models = {name: tables(path) for name, path in paths.items()}
    changes = {"parent_to_control": delta(models["parent"], models["control"]),
               "control_to_dependent": delta(models["control"], models["dependent"])}
    assert set(changes["parent_to_control"]) == {"ProblemDescription", "MissionType", "OperationProfile"}
    assert set(changes["control_to_dependent"]) == {"ProblemDescription", "MissionDependence"}
    result = {"schema": "simlox-a14-continuous-end-abort-v101-exact-diff/v1",
              "sources_sha256": EXPECTED, "changes": changes}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
