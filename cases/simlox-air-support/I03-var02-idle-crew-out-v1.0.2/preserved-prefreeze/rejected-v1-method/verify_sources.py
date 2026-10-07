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
        assert doc["schema"] == "i03-var02-v102-prelaunch-manifest/v1"
        assert doc["contract_sha256"] == CONTRACT_SHA and doc["run_id"] == contract["run_id"]
        for item in doc["source_files"]:
            path = Path(item["path"])
            if not path.is_absolute():
                path = REPO / path
            records[str(path)] = check_bytes(path, item)
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
