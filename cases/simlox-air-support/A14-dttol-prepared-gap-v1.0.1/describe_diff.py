"""Verify accepted A05 lineage and exact A14 DTTOL boundary deltas."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-var02-prepared-spare-probe-v1.0.0" / "native-input.json"
EXPECTED = {
    "parent": "b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d",
    "control": "070f4e242e9edbbb0cbae46fb28b3b6e04693073dd1d0510f4f34c89e7a4f0f1",
    "zero": "24dbe21efa62729bd0b2fd72f99ea6eab23035b3d17e5cdc5a1470392aed6629",
    "below": "ac03d5b234f96adc75bb0b008c2043e17fdeb84591b5a3a97edaa2250a826a01",
    "edge": "fe8724df8d73b808e70c59a65a01b346414f02523be4573ad6de329434cd46c4",
    "above": "a945ff998029dc8ee55e9457d9d66213ca76e0de8fcab86030575e1b2e6dce8c",
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
    result = {"schema": "simlox-a14-dttol-prepared-gap-v101-exact-diff/v1",
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
