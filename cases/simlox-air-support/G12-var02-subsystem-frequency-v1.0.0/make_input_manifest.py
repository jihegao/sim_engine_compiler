"""Record every frozen seed/arm input and its exact parent table delta."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, SEEDS, VARIANTS, build


def encoded(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def main() -> None:
    parent = json.loads(PARENT.read_bytes())
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    original = tables(parent)
    entries = {}
    for seed in SEEDS:
        entries[str(seed)] = {}
        for variant in VARIANTS:
            child = build(variant, seed)
            after = tables(child)
            changed = sorted(n for n in original if original[n] != after[n])
            expected = ["Control", "ProblemDescription", "System", "SystemRepair", "SystemStructure"]
            if variant == "baseline":
                expected.remove("SystemStructure")
            assert changed == expected, (seed, variant, changed)
            entries[str(seed)][variant] = {
                "sha256": hashlib.sha256(encoded(child)).hexdigest(),
                "changed_tables": changed,
                "source_rows": {
                    n: after[n]["instances"][0]["rows"] for n in changed
                },
            }
        base = tables(build("baseline", seed))
        for variant in ("qty-two", "env-two"):
            arm = tables(build(variant, seed))
            assert sorted(n for n in base if base[n] != arm[n]) == ["ProblemDescription", "SystemStructure"]
    manifest = {
        "schema": "simlox-g12-var02-frozen-input-panel/v1",
        "parent_input_sha256": PARENT_SHA,
        "seeds": list(SEEDS),
        "arms": list(VARIANTS),
        "common_changes": ["Control.NREPS=256", "Control.RSEED=seed 2..13",
                           "System.TEACH-AIR-01.FRT=blank (computed)",
                           "System.TEACH-SUB-B.FRT=50000 per million OPHOURS",
                           "SystemRepair.TEACH-SUB-B at BASE-01, SURPT=0.5h",
                           "ProblemDescription provenance"],
        "contrasts": {"qty-two": "only TEACH-SUB-B SystemStructure.QTYPM 1->2 plus description",
                      "env-two": "only TEACH-SUB-B SystemStructure.ENVF 1.0->2.0 plus description"},
        "entries": entries,
    }
    output = HERE / "input-manifest.json"
    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output.exists():
        if output.read_bytes() != data:
            raise ValueError("frozen input manifest differs")
    else:
        output.write_bytes(data)
    print(json.dumps({"inputs": len(SEEDS) * len(VARIANTS),
                      "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
