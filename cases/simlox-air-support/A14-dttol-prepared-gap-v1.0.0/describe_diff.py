"""Verify accepted A05 lineage and exact A14 DTTOL boundary deltas."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-var02-prepared-spare-probe-v1.0.0" / "native-input.json"
EXPECTED = {
    "parent": "b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d",
    "control": "f9341e525ae78313b355042296b059bc4751a00eb23914b22a11322c0b846b25",
    "zero": "8e871c91a5ba824941bb1faa3b91d1b69c1977d3302a4c2a1de54048d8ab5401",
    "below": "1b3f9c294c28dc4c53fdb9b7c0a67c1cd9cee776ccaf7f167a8e127e1e7ac608",
    "edge": "0b98bae7f3d832449895049cff15e52b6ea4388af96e7516e65a5134a8ec21ef",
    "above": "2ba6346570a5e4ab97f293e2b48e57f6da1be932b82a397d7bcfd32b34ae9fa6",
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
    models = {name: tables(path) for name, path in paths.items()}
    changes = {"parent_to_control": delta(models["parent"], models["control"]),
               **{f"control_to_{v}": delta(models["control"], models[v])
                  for v in ("zero", "below", "edge", "above")}}
    assert set(changes["parent_to_control"]) == {
        "ProblemDescription", "SystemDeployment", "Unit", "MissionType",
        "OperationProfile", "MissionPreparation", "Tasks"}
    for variant in ("zero", "below", "edge", "above"):
        assert set(changes[f"control_to_{variant}"]) == {"ProblemDescription", "MissionDependence"}
    result = {"schema": "simlox-a14-dttol-prepared-gap-v100-exact-diff/v1",
              "sources_sha256": EXPECTED, "changes": changes}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    out = HERE / "exact-diff.json"
    if out.exists():
        assert out.read_bytes() == raw
    else:
        out.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
