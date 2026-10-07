"""File-based byte provenance gate; no native calls or filesystem writes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT_SHA = "1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29"
ROOT_COMPANION_CONTEXT = {
    "i03-var02-v102-root-construction-gate-20261007.json": {"bytes": 1370, "sha256": "204177b023bf6caa4219c379769e2e671345a9a2a430c377d9026dd531a32fd0"},
    "i03-var02-v102-root-freeze-failure-history-20261007.json": {"bytes": 1427, "sha256": "ecee8cacd5851d275b26825ddc5f06129abfec2ed0cee374aae136aaae83d315"},
    "probe-i03-var02-independent-ledger-20261007.py": {"bytes": 1756, "sha256": "ed2ec5eb8371d90c8bf24b3f1b11cb2801ccd1ceef330978008e1a2a4d6b045b"},
    "i03-var02-independent-ledger-probes-20261007.json": {"bytes": 555, "sha256": "078ddc254f135c2df1041128e758439effbc10604ec29f8bb91d605c6d906678"},
    "probe-i03-var02-independent-v2-20261007.py": {"bytes": 3890, "sha256": "29a1aac31ae2d019523ddc17a7f58bd73c0e3933bd6621c1e267351334bde178"},
    "i03-var02-independent-v2-probes-20261007.json": {"bytes": 10345, "sha256": "ca72cc90189b64cf603d39a047cf3f9e226c0bce669d8de215fc4311a52e0db5"},
    "probe-i03-var02-independent-v3-20261007.py": {"bytes": 3947, "sha256": "faecd46890ab7e29767b58f0a3df3c38ae9d1aba4edad8700de12aa48107d2d1"},
    "i03-var02-independent-v3-probes-20261007.json": {"bytes": 10428, "sha256": "4c7a2d732980518813fd399e382c8c1408e3368370d911611c45e9c516c922ee"},
    "probe-i03-var02-independent-v3-final-20261007.py": {"bytes": 3959, "sha256": "10fe9e9d17a813c602581a463a84c3668d84cc8b53a9234ec7424789ffb9bf88"},
    "i03-var02-independent-v3-final-probes-20261007.json": {"bytes": 10434, "sha256": "09fdab95afd1b53a2d728c1cfd9173f68ea24d42923a407b3e32773702985cd4"},
    "probe-i03-var02-author-v3-20261007.py": {"bytes": 4328, "sha256": "748ce7ebfc23f5797c9720010913039b9712c16e254d845a50e55e667909b5ae"},
    "i03-var02-author-v3-root-probes-20261007.json": {"bytes": 11648, "sha256": "42a52867a40b827ce1f2b4e1662cb59f681130771411cad85521b627f0d44436"},
    "probe-i03-var02-author-v3-final-20261007.py": {"bytes": 4340, "sha256": "5325ae3e724b4914460d2a0c62e8c30cbfe957fe2b274f838f21a8c9f501b38a"},
    "i03-var02-author-v3-final-root-probes-20261007.json": {"bytes": 12801, "sha256": "f5ea997fb21aaecb33a4221e041485b472a327f26353573dda25a8698e546433"},
    "probe-i03-var02-author-queue-context-20261007.py": {"bytes": 1917, "sha256": "94d9b615b530b215baf4722b8938017a41f1eae2a14cc6b547b804425f321621"},
    "i03-var02-author-queue-context-probes-20261007.json": {"bytes": 849, "sha256": "c419860ad7ea713b30fbf9a64f299f3edc8bcb1644ed2f87f1724b56c9f7a76a"},
    "probe-i03-var02-author-queue-final-20261007.py": {"bytes": 1915, "sha256": "e3b45fa6940c23fa11b75311bdb9ccaa49c9cdcf8893c8cb784e5e9e1dcb119c"},
    "i03-var02-author-queue-final-probes-20261007.json": {"bytes": 848, "sha256": "fefc2da148162abc0298a7f14c16911900d8e7e596746c6a43882714debef472"},
}


def identity(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check_bytes(path: Path, expected: dict) -> dict:
    assert path.is_file(), f"missing: {path}"
    actual = identity(path.read_bytes())
    assert actual == {key: expected[key] for key in ("bytes", "sha256")}, (str(path), actual, expected)
    return actual


def strict_equal(a: object, b: object) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(strict_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    return a == b


def published_blob(base: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{base}:{path}"], cwd=REPO)


def verify_catalog(contract: dict, mode: str) -> dict:
    item = contract["source_lineage"]["catalog_at_selection"]
    archive_path = HERE / item["owned_exact_archive"]
    check_bytes(archive_path, item["owned_archive_pin"])
    archive = json.loads(archive_path.read_text(encoding="utf-8-sig"))
    assert len(archive["entries"]) == item["entry_count_at_selection"] == 490
    assert strict_equal({k: v for k, v in archive.items() if k != "entries"}, item["exact_metadata_at_selection"])
    base = contract["ownership"]["base_commit"]
    assert identity(published_blob(base, item["path"])) == item["published_git_at_base"]
    live_path = REPO / item["path"]
    live_bytes = live_path.read_bytes()
    if mode == "live":
        assert identity(live_bytes) == item["local_disk"], "prelaunch catalog changed; new gate required"
    live = json.loads(live_bytes.decode("utf-8-sig"))
    assert type(live) is dict and live.keys() == archive.keys()
    assert strict_equal({k: v for k, v in live.items() if k != "entries"},
                        {k: v for k, v in archive.items() if k != "entries"}), "catalog metadata drift"
    assert type(live["entries"]) is list and len(live["entries"]) >= 490
    assert strict_equal(live["entries"][:490], archive["entries"]), "catalog historical prefix drift"
    ids = [e["publication_id"] for e in live["entries"]]
    assert all(type(i) is str and i for i in ids) and len(ids) == len(set(ids)), "catalog publication ID drift"
    return {"archived_entries": 490, "live_entries": len(live["entries"]),
            "archive_sha256": item["owned_archive_pin"]["sha256"],
            "base_git_sha256": item["published_git_at_base"]["sha256"]}


def verify_manifest_entry(entry: dict, mode: str, contract: dict) -> tuple[Path, dict]:
    path = Path(entry["path"])
    if not path.is_absolute():
        path = REPO / path
    if entry["key"] == "catalog_live_prelaunch":
        catalog = contract["source_lineage"]["catalog_at_selection"]
        assert path.resolve(strict=True) == (REPO / catalog["path"]).resolve(strict=True)
        assert {k: entry[k] for k in ("bytes", "sha256")} == catalog["local_disk"]
        archive = HERE / catalog["owned_exact_archive"]
        historical = check_bytes(archive, entry)
        if mode == "live":
            check_bytes(path, entry)
        # Sealed replay retains the source map's historical prelaunch identity.
        # verify_catalog has already checked the current catalog's exact prefix/metadata.
        return path, historical
    return path, check_bytes(path, entry)


def verify(mode: str, manifest: Path | None = None) -> dict:
    check_bytes(HERE / "contract.json", {"bytes": (HERE / "contract.json").stat().st_size, "sha256": CONTRACT_SHA})
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    assert contract["package"] == HERE.name and contract["version"] == "1.0.2"
    assert contract["run_id"] == "i03-var02-idle-out-v102-ssh-20261007-01"
    lineage = contract["source_lineage"]
    base = contract["ownership"]["base_commit"]
    records = {}
    for section in ("excluded_v100_NO_GO_files", "excluded_v101_NO_GO_files", "owned_historical_root_context"):
        for item in lineage[section]:
            copy = HERE / item["owned_inert_copy"]
            records[item["owned_inert_copy"]] = check_bytes(copy, item)
            original = REPO / item["original_path"]
            if original.exists():
                check_bytes(original, item)
    accepted = lineage["accepted_source_local_vs_published_git_at_base"]
    assert len(accepted) == 20
    for item in accepted:
        records[item["path"]] = check_bytes(REPO / item["path"], item["local_disk"])
        assert identity(published_blob(base, item["path"])) == item["published_git_at_base"], item["path"]
    raw = lineage["accepted_original_run_records"]
    assert len(raw) == 34
    for item in raw:
        records[item["path"]] = check_bytes(Path(item["path"]), item)
    for name in ("exe", "manual", "dictionary"):
        item = lineage["installed"][name]
        records[item["path"]] = check_bytes(Path(item["path"]), item)
    for name in ("root_selection_receipt", "root_live_context"):
        item = lineage[name]
        # The owned copy is mandatory; tmp original is historical context only.
        records[item["path"]] = check_bytes(HERE / "preserved-root-context" / Path(item["path"]).name, item)
    for name, pin in ROOT_COMPANION_CONTEXT.items():
        records["preserved-root-context/" + name] = check_bytes(HERE / "preserved-root-context" / name, pin)
        original = REPO / "tmp" / name
        if original.exists():
            check_bytes(original, pin)
    catalog = verify_catalog(contract, mode)
    if manifest is not None:
        doc = json.loads(manifest.read_text(encoding="utf-8-sig"))
        assert doc["schema"] == "i03-var02-v102-prelaunch-manifest/v2"
        assert doc["contract_sha256"] == CONTRACT_SHA and doc["run_id"] == contract["run_id"]
        assert sum(item["key"] == "catalog_live_prelaunch" for item in doc["source_files"]) == 1
        for item in doc["source_files"]:
            path, pin = verify_manifest_entry(item, mode, contract)
            records[str(path)] = pin
    return {"schema": "i03-var02-v102-source-verifier/v1", "passed": True,
            "mode": mode, "accepted_local_git_pairs": len(accepted), "accepted_raw_records": len(raw),
            "installed_files": 3, "historical_owned_copies": sum(len(lineage[k]) for k in ("excluded_v100_NO_GO_files", "excluded_v101_NO_GO_files", "owned_historical_root_context")) + len(ROOT_COMPANION_CONTEXT),
            "catalog": catalog, "source_map": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "sealed"), default="live")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.mode, args.manifest)
    except Exception as exc:
        result = {"schema": "i03-var02-v102-source-verifier/v1", "passed": False,
                  "mode": args.mode, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(0 if result["passed"] else 1)
