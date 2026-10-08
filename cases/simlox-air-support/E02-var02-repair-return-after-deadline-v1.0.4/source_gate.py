"""Read-only accepted-parent and prospective source custody for E02.var02."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from model_common import HERE, REPO, INPUT_PIN, NATIVE_DIR, exact, seal, strict_json

SELECTION = HERE / "source-maps/root-selection-receipt.json"
SELECTION_PIN = {"bytes": 37595, "sha256": "1207a61dc842fba2c0102c4ea03bbc142b7fd8f560ae3970df67bcc47e3a12f5"}
CATALOG_LOCAL = HERE / "source-maps/catalog-local-503.json.bytes"
CATALOG_GIT = HERE / "source-maps/catalog-git-503.json.bytes"
CATALOG_CURRENT = REPO / "cases/simlox-air-support/publication-index-v1.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
SIMLOX = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
INSTALLED = (
    (MANUAL, {"bytes": 18124110, "sha256": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"}),
    (SIMLOX, {"bytes": 33196032, "sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"}),
    (PYTHON, {"bytes": 106448, "sha256": "10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1"}),
    (DICTIONARY, {"bytes": 78577, "sha256": "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0"}),
)
DESIGN = {
    "contract.json": (11182, "f8de374b6f78e661d9f453b96fe701db321f94686d02fbec92b8e4095f8fea3b"),
    "event-oracle.json": (4581, "49983167aa9b17ba6de757d63759bda1030923a7960efaf01b6d3e0556c9e4aa"),
    "report-formulas.json": (11502, "868c9081eaaf801a7a1fedd33b7e733efe2804cb526a443f4fd774f87234f050"),
    "source-delta.json": (1271, "e7dcb2aa9d6f7f4b02801738045472b385a106c56a50e2bc91e6f7d01e8b9a33"),
    "materialize_oracle.py": (27916, "be84653ec3aea6259c03af705279d19f7ed1d50af282c32e2309af8cd6c93b5d"),
    "README.md": (3507, "96ec211a1905524eeedf560b5c804a71f6d93b4515660373ef6e6af72223bdf4"),
    "independent-construction-go.md": (4189, "557df357d289b91e524982afa54ed008b96bf90c51ed1ccaeaa7c4f534df6956"),
}
ORACLES = {
    "log-patterns.json": (16033, "b11b963d2572af36b159326c606ae71f0e525edd0d0b1c3d985e19e96e87b332"),
    "expected-report.json": (100409, "910f3495d9217cb47e884f6a2adabee45b76add700c90c4340c636c1867af7a4"),
    "expected-log-template.bin": (9178, "2ac25ce130a7c4c6f078fdf9aa2ed379dba4fa093380ec0601fc7f9628d777c9"),
    "candidate-input.json": (43701, "fe9579fc77222196ffcd942fb5a09e98e8ebfca5208f7b954dcfcf1c6f05f98b"),
    "receipt.json": (3553, "46543fdd269ce6dd12480473a5d50450c9271c3de73f6fa6538369d66c9f958a"),
}
EXCLUDED_CASE = REPO / "cases/simlox-air-support/E02-var02-repair-return-after-deadline-v1.0.3"
EXCLUDED_INVENTORY = EXCLUDED_CASE / "source-inventory.json"
EXCLUDED_INVENTORY_PIN = {"bytes": 13804, "sha256": "35f7cec140d2404a5692c7f8853ccf2fd01beb73b48c3446f0b689a3d7db3e97"}
EXCLUDED_MANIFEST = EXCLUDED_CASE / "prelaunch-manifest.json"
EXCLUDED_MANIFEST_PIN = {"bytes": 64182, "sha256": "ef5675a7054f43bbbfe26376b8cc411678533e7b28054db9116737407271d123"}
EXCLUDED_CUSTODY = REPO / "tmp/e02-var02-failed-native-custody-v103-20261009-01/receipt.json"
EXCLUDED_CUSTODY_PIN = {"bytes": 30795, "sha256": "b81c5abb847f8d16819cdcb18419a680da6ad5b53c1977f2f46b783e41e6a98f"}
HISTORY_MAP = HERE / "preserved-history/original-proof-map.json"
HISTORY_MAP_PIN = {"bytes": 8922, "sha256": "06907f4e8c5bc837d429d8ce111a2df54384f9dad24874a15656079c958d84ed"}


def excluded_history() -> dict[str, object]:
    inventory = strict_json(exact(EXCLUDED_INVENTORY, EXCLUDED_INVENTORY_PIN))
    assert inventory["source_count"] == 77 and len(inventory["source_files"]) == 77
    seen = set()
    for row in inventory["source_files"]:
        rel = Path(row["path"])
        assert not rel.is_absolute() and ".." not in rel.parts
        assert row["path"].casefold() not in seen
        seen.add(row["path"].casefold())
        path = (EXCLUDED_CASE / rel).resolve(strict=True)
        assert path.is_relative_to(EXCLUDED_CASE.resolve(strict=True))
        exact(path, row)
        assert path.stat().st_file_attributes & 1, "excluded source is writable"
    exact(EXCLUDED_MANIFEST, EXCLUDED_MANIFEST_PIN)
    assert EXCLUDED_INVENTORY.stat().st_file_attributes & 1
    assert EXCLUDED_MANIFEST.stat().st_file_attributes & 1
    custody = strict_json(exact(EXCLUDED_CUSTODY, EXCLUDED_CUSTODY_PIN))
    assert custody["schema"] == "e02-var02-root-excluded-failure-custody/v100"
    assert custody["decision"] == "NO_GO_PRESERVED" and custody["semantic_acceptance"] is False
    assert custody["source_bytes_modes_attributes_stable"] is True
    originals = custody["originals_after_freeze"]
    copies = custody["copies"]
    assert type(originals) is dict and len(originals) == 40
    assert type(copies) is dict and len(copies) == 26
    for name, pin in originals.items():
        path = Path(name)
        exact(path, pin)
        st = path.stat()
        assert st.st_mode == pin["mode"] and st.st_file_attributes == pin["attributes"]
        assert st.st_file_attributes & 1
    for name, pin in copies.items():
        path = Path(custody["diagnostic_copy"]) / name
        exact(path, pin)
        assert path.stat().st_file_attributes & 1
        original = Path(custody["original_run"]) / name
        assert str(original) in originals
        assert {key: originals[str(original)][key] for key in ("bytes", "sha256")} == pin
    return {"excluded_sources": 79, "excluded_failed_originals": 40,
            "excluded_diagnostic_copies": 26, "semantic_acceptance": False}


def original_proof_history() -> int:
    mapping = strict_json(exact(HISTORY_MAP, HISTORY_MAP_PIN))
    assert mapping["schema"] == "e02-var02-v104-original-proof-map/v1"
    assert mapping["semantic_acceptance"] is False and mapping["native_authorization"] is False
    rows = mapping["records"]
    assert type(rows) is list and len(rows) == 23
    assert len({row["role"].casefold() for row in rows}) == 23
    for row in rows:
        assert set(row) == {"role", "path", "bytes", "sha256", "state"}
        path = REPO / row["path"]
        assert path.resolve(strict=True).is_relative_to(REPO.resolve(strict=True))
        exact(path, row)
        assert path.stat().st_file_attributes & 1
    return 23


def typed_equal(a: object, b: object) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b, strict=True))
    return a == b


def selected_git_pairs(rows: list[dict], base: str) -> None:
    paths = [r["path"] for r in rows]
    assert len(paths) == len(set(paths)) == 39
    result = subprocess.run(["git", "ls-tree", "-r", "-z", base, "--", *paths],
                            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert result.stderr == b""
    tree: dict[str, str] = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        head, name = record.split(b"\t", 1)
        mode, kind, oid = head.decode("ascii").split(" ")
        path = name.decode("utf-8")
        assert kind == "blob" and path not in tree
        tree[path] = oid
    assert set(tree) == set(paths)
    assert all(tree[row["path"]] == row["oid"] for row in rows)
    oids = list(dict.fromkeys(row["oid"] for row in rows))
    raw = subprocess.run(["git", "cat-file", "--batch"], cwd=REPO,
                         input=("\n".join(oids) + "\n").encode("ascii"),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert raw.stderr == b""
    offset = 0
    blobs: dict[str, bytes] = {}
    for oid in oids:
        end = raw.stdout.index(b"\n", offset)
        head = raw.stdout[offset:end].decode("ascii").split(" ")
        assert len(head) == 3 and head[:2] == [oid, "blob"]
        count = int(head[2]); start = end + 1
        blobs[oid] = raw.stdout[start:start + count]
        assert len(blobs[oid]) == count and raw.stdout[start + count:start + count + 1] == b"\n"
        offset = start + count + 1
    assert offset == len(raw.stdout)
    for row in rows:
        blob = blobs[row["oid"]]
        assert len(blob) == row["git"]["bytes"]
        assert hashlib.sha256(blob).hexdigest() == row["git"]["sha256"]


def verify(require_absent_native: bool = False) -> dict[str, object]:
    history = excluded_history()
    proof_count = original_proof_history()
    selected = strict_json(exact(SELECTION, SELECTION_PIN))
    assert type(selected) is dict and selected["base"] == "7b9dc461d629e28ed6f719d6c155dad9db9dca60"
    assert selected["decision"] == "ELIGIBLE_FOR_CONTRACT_REVIEW_ONLY"
    rows = selected["accepted_source_pairs"]
    assert type(rows) is list and len(rows) == 39
    for row in rows:
        rel = Path(row["path"])
        assert not rel.is_absolute() and ".." not in rel.parts
        target = (REPO / rel).resolve(strict=True)
        assert target.is_relative_to(REPO.resolve(strict=True))
        exact(target, row["disk"])
    selected_git_pairs(rows, selected["base"])
    originals = selected["mandatory_originals"]
    assert type(originals) is list and len(originals) == 42
    assert len({row["path"].casefold() for row in originals}) == 42
    for row in originals:
        path = Path(row["path"])
        exact(path, row)
        st = path.stat()
        assert st.st_mode == row["original_mode"]
        assert getattr(st, "st_file_attributes", None) == row["original_attributes"]
    for path, pin in INSTALLED:
        exact(path, pin)
    exact(HERE / "native-input.json", INPUT_PIN)
    for name, (size, sha) in DESIGN.items():
        exact(HERE / "preserved-design" / name, {"bytes": size, "sha256": sha})
    for name, (size, sha) in ORACLES.items():
        exact(HERE / "preserved-oracle" / name, {"bytes": size, "sha256": sha})
    local = strict_json(exact(CATALOG_LOCAL, selected["catalog_local_crlf"]))
    remote = strict_json(exact(CATALOG_GIT, selected["catalog_git_lf"]))
    assert typed_equal(local, remote) and len(local["entries"]) == 503
    current = strict_json(CATALOG_CURRENT.read_bytes())
    assert type(current) is dict and set(current) == set(local)
    assert type(current["entries"]) is list and len(current["entries"]) >= 503
    for key in local:
        if key not in ("entries", "as_of"):
            assert typed_equal(local[key], current[key]), key
    assert all(typed_equal(a, b) for a, b in zip(local["entries"], current["entries"][:503], strict=True))
    assert len({row["publication_id"] for row in current["entries"]}) == len(current["entries"])
    if require_absent_native:
        assert not NATIVE_DIR.exists(), "native directory must be absent before preflight"
    return {"schema": "e02-var02-source-gate/v104", "passed": True,
            "accepted_disk_git_pairs": 39, "mandatory_originals": 42,
            "excluded_history": history,
            "historical_original_proofs": proof_count,
            "catalog_prefix_entries": 503, "native_calls": 0, "accepted_checker_calls": 0}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
