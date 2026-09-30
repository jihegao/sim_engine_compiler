"""Verify exact source deltas and seal the A14 structural diff."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-continuous-baseline-v1.0.1" / "native-continuous.json"
EXPECTED = {
    "parent": "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea",
    "control": "9735fb952230fdc73ecfed0232b24593665649cd975394556740af34ba64464d",
    "oneway": "281de20b7645115ac5b03d89e53f8ee2100d64921cf0b8bbadb02a70d29c5a98",
    "mutual": "2a171ae186c532ecd8bdee154e08c895f92b8f9f5e5feed2b8c89c30ed60389c",
    "opposing": "5488e751c4e723bbf647491889036f191e84e4c97ebed1fae5a6de678aaf3621",
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
    result = {"schema": "simlox-a14-mutual-stagger-exact-diff/v1", "sources_sha256": EXPECTED, "changes": changes}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
