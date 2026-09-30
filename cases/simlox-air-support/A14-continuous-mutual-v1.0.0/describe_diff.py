"""Verify exact source deltas and seal the A14 structural diff."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-continuous-baseline-v1.0.1" / "native-continuous.json"
EXPECTED = {
    "parent": "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea",
    "control": "47e9c68a9026048c422f97de14a162f200bc977a2c4ae1a611305696e859c3fa",
    "oneway": "3dd4b6d23b24ac33e6913a48f8953ee3dc950ac321a591efa3e268bb0627792f",
    "mutual": "15b920fd1d4fe4b9657994e9865143dae52aff05fff4e18b6ca008f7c559c3f7",
    "opposing": "2c568136e037aaeac30d77ac515d12f322e443c1ae7e2ce385848f7e7b575978",
}


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_bytes())["model"]["tables"]}


def delta(before: dict, after: dict) -> dict:
    return {n: {"before": before.get(n), "after": after.get(n)}
            for n in sorted(before.keys() | after.keys()) if before.get(n) != after.get(n)}


def main() -> None:
    paths = {"parent": PARENT, **{v: HERE / f"{v}-input.json" for v in EXPECTED if v != "parent"}}
    for name, path in paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED[name], name
    all_tables = {name: tables(path) for name, path in paths.items()}
    changes = {"parent_to_control": delta(all_tables["parent"], all_tables["control"]),
               **{f"control_to_{v}": delta(all_tables["control"], all_tables[v])
                  for v in ("oneway", "mutual", "opposing")}}
    assert set(changes["parent_to_control"]) == {"ProblemDescription", "MissionType", "OperationProfile"}
    for variant in ("oneway", "mutual", "opposing"):
        assert set(changes[f"control_to_{variant}"]) == {"ProblemDescription", "MissionDependence"}
    result = {"schema": "simlox-a14-continuous-mutual-exact-diff/v1", "sources_sha256": EXPECTED, "changes": changes}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
