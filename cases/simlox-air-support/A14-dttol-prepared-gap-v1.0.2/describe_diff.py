"""Verify accepted A05 lineage and exact A14 DTTOL boundary deltas."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-var02-prepared-spare-probe-v1.0.0" / "native-input.json"
EXPECTED = {
    "parent": "b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d",
    "control": "6756a61111bd1db6378353c4fe2c093f1d466ee4fa6a4ca7759600c35d8908c1",
    "zero": "f3bee7f935580fd90d5a60f6aa66c0307762c12d67b5c2ad575e8ddb6ecdfd3f",
    "below": "f995814acac489ec3d1dd382da952957ab5c6f7b19a1a4e36f4cf6b67b9b433f",
    "edge": "3018ba6ae23aa95fb0c1c1a209d6dfa733daf50d8a1a59a0f2cbdedab5f28c52",
    "above": "7823e5c922680cd04b6592920c14ad5a62c7b1857df5d9f7f27ee632e77ee00b",
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
        "ProblemDescription", "System", "SystemDeployment", "Unit", "MissionType",
        "OperationProfile", "MissionPreparation", "Tasks", "MissionSystem"}
    for variant in ("zero", "below", "edge", "above"):
        assert set(changes[f"control_to_{variant}"]) == {"ProblemDescription", "MissionDependence"}
    result = {"schema": "simlox-a14-dttol-prepared-gap-v102-exact-diff/v1",
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
