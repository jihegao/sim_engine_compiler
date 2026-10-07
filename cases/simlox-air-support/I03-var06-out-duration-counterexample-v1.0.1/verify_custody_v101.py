"""Read-only sealed v100/source/raw custody and append-aware catalog verifier."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from json_codec import parse, typed_equal

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT_SHA = "66465e9a5df6c3e5a95f6b9b6b046bb6ea3b448a6512cb3e88ff7f2993f803dc"
MANIFEST_SHA = "ce196b80f2365519885fb97b77eda0b04737736f239dfac46903df99edcf42a9"
GIT = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe")
OLD_MANIFEST = HERE / "preserved-v100-source" / "prelaunch-manifest.json"
CATALOG_ARCHIVE = HERE / "preserved-v100-source" / "preserved-root-context" / "cases__simlox-air-support__publication-index-v1.json"


def identity(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def checked(path: Path, pin: dict) -> dict:
    assert path.is_file(), f"missing exact dependency: {path}"
    actual = identity(path.read_bytes())
    assert actual == {key: pin[key] for key in ("bytes", "sha256")}, (str(path), actual, pin)
    return actual


def git_tree(base: str) -> dict[str, str]:
    result = subprocess.run([str(GIT), "ls-tree", "-r", "-z", base], cwd=REPO, capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    tree = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        mode, kind, oid = header.split(b" ")
        if kind == b"blob" and mode in (b"100644", b"100755"):
            key = name.decode("utf-8")
            assert key not in tree
            tree[key] = oid.decode("ascii")
    return tree


def git_blob(tree: dict[str, str], name: str) -> bytes:
    assert name in tree, name
    result = subprocess.run([str(GIT), "cat-file", "blob", tree[name]], cwd=REPO, capture_output=True)
    assert result.returncode == 0, (name, result.stderr.decode(errors="replace"))
    return result.stdout


def verify() -> dict:
    checked(HERE / "contract.json", {"bytes": 216817, "sha256": CONTRACT_SHA})
    contract = parse(HERE / "contract.json")
    assert contract["version"] == "1.0.1" and contract["ownership"]["new_native_calls"] == 0
    lineage = contract["source_lineage"]
    source_map = parse(HERE / "v100-source-custody.json")
    assert source_map["schema"] == "i03-var06-v101-v100-source-custody/v1"
    assert source_map["record_count"] == len(source_map["records"]) == 117
    owned = {}
    for row in source_map["records"]:
        assert row["owned_copy"].startswith("preserved-v100-source/")
        checked(HERE / row["owned_copy"], row)
        assert row["original"] not in owned
        owned[row["original"]] = row
        original = REPO / row["original"]
        if original.exists():
            checked(original, row)
    context = parse(HERE / "root-context-custody.json")
    assert context["schema"] == "i03-var06-v101-root-context-custody/v1"
    assert context["record_count"] == len(context["records"]) == 30
    for row in context["records"]:
        checked(HERE / row["owned_copy"], row)
        original = REPO / row["original"]
        if original.exists():
            checked(original, row)
    checked(OLD_MANIFEST, {"bytes": 172903, "sha256": MANIFEST_SHA})
    manifest = parse(OLD_MANIFEST)
    assert manifest["source_count"] == len(manifest["source_files"]) == 445
    assert manifest["contract_sha256"] == contract["historical_v100_failed_hypothesis"]["frozen_contract_sha256"]
    old_repo = Path(manifest["source_files"][0]["path"]).parents[3]
    assert old_repo.name == REPO.name
    catalog_pin = lineage["catalog_at_selection"]
    checked(CATALOG_ARCHIVE, catalog_pin["local_disk"])
    archived_catalog = parse(CATALOG_ARCHIVE)
    live_catalog = parse(REPO / catalog_pin["path"])
    assert len(archived_catalog["entries"]) == catalog_pin["entry_count"] == 491
    assert typed_equal({k: v for k, v in archived_catalog.items() if k != "entries"}, catalog_pin["metadata"])
    assert typed_equal({k: v for k, v in live_catalog.items() if k != "entries"}, catalog_pin["metadata"])
    assert len(live_catalog["entries"]) >= 491 and typed_equal(live_catalog["entries"][:491], archived_catalog["entries"])
    ids = [r["publication_id"] for r in live_catalog["entries"]]
    assert all(type(x) is str and x for x in ids) and len(ids) == len(set(ids))
    old_owned_count = 0
    for row in manifest["source_files"]:
        path = Path(row["path"])
        if row["key"] == "catalog_live_prelaunch":
            assert row["sha256"] == catalog_pin["local_disk"]["sha256"]
            checked(CATALOG_ARCHIVE, row)
            continue
        try:
            relative = path.relative_to(old_repo).as_posix()
        except ValueError:
            checked(path, row)  # installed absolute file or accepted external raw
            continue
        if relative in owned:
            checked(HERE / owned[relative]["owned_copy"], row)
            old_owned_count += 1
        else:
            checked(REPO / relative, row)
    assert old_owned_count == 101
    tree = git_tree(lineage["base_commit"])
    dual_count = 0
    for section, count in (("parent_source_disk_and_git_at_base", 192),
                           ("accepted_dependency_source_disk_and_git_at_base", 20),
                           ("accepted_secondary_context_source_disk_and_git_at_base", 2)):
        rows = lineage[section]
        assert len(rows) == count
        for row in rows:
            checked(REPO / row["path"], row["local_disk"])
            assert identity(git_blob(tree, row["path"])) == row["published_git_at_base"], row["path"]
            assert row["byte_equal"] is (row["local_disk"] == row["published_git_at_base"])
            dual_count += 1
    assert dual_count == 214
    assert identity(git_blob(tree, catalog_pin["path"])) == catalog_pin["published_git_at_base"]
    raw_count = 0
    for section in ("accepted_parent_and_context_raw", "accepted_secondary_context_run_files"):
        rows = lineage[section]
        assert len(rows) == 59
        for row in rows:
            checked(Path(row["original_path"]), row)
            raw_count += 1
    assert raw_count == 118
    run_files = contract["historical_failed_run"]["v100_raw_run_files"]
    assert len(run_files) == 26
    for row in run_files:
        checked(REPO / row["path"], row)
    for row in lineage["installed"]:
        checked(Path(row["path"]), row)
    assert len(lineage["installed"]) == 3
    for row in lineage["required_docs"]:
        checked(REPO / row["path"], row)
    return {"schema": "i03-var06-v101-sealed-custody/v1", "passed": True,
            "v100_manifest_records": 445, "v100_archived_source_files": 117,
            "v100_owned_manifest_records": old_owned_count, "small_context_copies": 30,
            "accepted_source_disk_git_pairs": dual_count, "accepted_raw_records": raw_count,
            "failed_child_run_files": len(run_files), "installed_files": 3,
            "catalog_archived_entries": 491, "catalog_live_entries": len(ids)}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, separators=(",", ":")))
