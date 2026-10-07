"""Read-only byte and source provenance for the fixed I03.var06 OUT candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from build import construct, typed_equal, verify as verify_diff

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GIT = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe")
CONTRACT_SHA = "f03452c24030789f64a25df0419ffd574f97411a9ea0e1faa83df5743a22f793"
RUN_ID = "i03-var06-out-dt4-v100-ssh-20261008-01"


def identity(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check_bytes(path: Path, expected: dict) -> dict:
    assert path.is_file(), f"missing: {path}"
    actual = identity(path.read_bytes())
    assert actual == {k: expected[k] for k in ("bytes", "sha256")}, (str(path), actual, expected)
    return actual


def strict_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(strict_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(strict_equal(a, b) for a, b in zip(left, right))
    return left == right


def git_tree(base: str) -> dict[str, str]:
    result = subprocess.run([str(GIT), "ls-tree", "-r", "-z", base], cwd=REPO, capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    tree = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        header, path = record.split(b"\t", 1)
        mode, kind, oid = header.split(b" ")
        assert kind == b"blob" and mode in (b"100644", b"100755")
        key = path.decode("utf-8")
        assert key not in tree
        tree[key] = oid.decode("ascii")
    return tree


def git_blob(tree: dict[str, str], path: str) -> bytes:
    assert path in tree, path
    result = subprocess.run([str(GIT), "cat-file", "blob", tree[path]], cwd=REPO, capture_output=True)
    assert result.returncode == 0, path
    return result.stdout


def verify_catalog(contract: dict, tree: dict[str, str], mode: str, custody: dict) -> dict:
    item = contract["source_lineage"]["catalog_at_selection"]
    rows = [r for r in custody["records"] if r["original_path"] == item["path"]]
    assert len(rows) == 1 and rows[0]["original_if_present_must_match"] is False
    archive_path = HERE / rows[0]["owned_copy"]
    assert check_bytes(archive_path, item["local_disk"]) == check_bytes(archive_path, rows[0])
    archive = json.loads(archive_path.read_text(encoding="utf-8-sig"))
    assert type(archive) is dict and type(archive.get("entries")) is list
    assert len(archive["entries"]) == item["entry_count"] == 491
    assert strict_equal({k: v for k, v in archive.items() if k != "entries"}, item["metadata"])
    assert identity(git_blob(tree, item["path"])) == item["published_git_at_base"]
    live_path = REPO / item["path"]
    live_bytes = live_path.read_bytes()
    if mode == "live":
        assert identity(live_bytes) == item["local_disk"], "live prelaunch catalog drift"
    live = json.loads(live_bytes.decode("utf-8-sig"))
    assert type(live) is dict and live.keys() == archive.keys()
    assert strict_equal({k: v for k, v in live.items() if k != "entries"}, item["metadata"])
    assert type(live["entries"]) is list and len(live["entries"]) >= 491
    assert strict_equal(live["entries"][:491], archive["entries"]), "catalog prefix drift"
    ids = [entry["publication_id"] for entry in live["entries"]]
    assert all(type(x) is str and x for x in ids) and len(ids) == len(set(ids))
    return {"archived_entries": 491, "live_entries": len(ids),
            "archive_sha256": item["local_disk"]["sha256"],
            "base_git_sha256": item["published_git_at_base"]["sha256"]}


def verify(mode: str = "live", manifest: Path | None = None) -> dict:
    assert mode in ("live", "sealed")
    check_bytes(HERE / "contract.json", {"bytes": 174913, "sha256": CONTRACT_SHA})
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    assert contract["run_id"] == RUN_ID and contract["version"] == "1.0.0"
    lineage = contract["source_lineage"]
    custody = json.loads((HERE / "root-context-custody.json").read_text(encoding="utf-8"))
    assert custody["schema"] == "i03-var06-root-context-custody/v1" and len(custody["records"]) == 12
    records = {}
    for item in custody["records"]:
        copy = HERE / item["owned_copy"]
        records[item["owned_copy"]] = check_bytes(copy, item)
        original = REPO / item["original_path"]
        if item["original_if_present_must_match"] and original.exists():
            check_bytes(original, item)
    tree = git_tree(lineage["base_commit"])
    for section, count in (("parent_source_disk_and_git_at_base", 192),
                           ("accepted_dependency_source_disk_and_git_at_base", 20),
                           ("accepted_secondary_context_source_disk_and_git_at_base", 2)):
        pins = lineage[section]
        assert len(pins) == count
        for item in pins:
            records[item["path"]] = check_bytes(REPO / item["path"], item["local_disk"])
            assert identity(git_blob(tree, item["path"])) == item["published_git_at_base"], item["path"]
            assert item["byte_equal"] is (item["local_disk"] == item["published_git_at_base"])
    for section, count in (("accepted_parent_and_context_raw", 59),
                           ("accepted_secondary_context_run_files", 59)):
        pins = lineage[section]
        assert len(pins) == count
        for item in pins:
            records[item["original_path"]] = check_bytes(Path(item["original_path"]), item)
    assert len(lineage["installed"]) == 3
    for item in lineage["installed"]:
        records[item["path"]] = check_bytes(Path(item["path"]), item)
    for item in lineage["required_docs"]:
        records[item["path"]] = check_bytes(REPO / item["path"], item)
    catalog = verify_catalog(contract, tree, mode, custody)
    source = lineage["authoritative_parent_index"]
    check_bytes(REPO / source["path"], source)
    parent = json.loads((HERE.parent / "I03-var02-idle-crew-out-v1.0.2/native-input.json").read_text())
    child_path = HERE / "native-input.json"
    child = json.loads(child_path.read_text(encoding="utf-8"))
    assert typed_equal(child, construct(parent, contract))
    diff = verify_diff(parent, child, contract)
    expected_diff = json.loads((HERE / "exact-diff.json").read_text())
    assert expected_diff["child_sha256"] == identity(child_path.read_bytes())["sha256"]
    assert all(strict_equal(diff[k], expected_diff[k]) for k in diff)
    if mode == "live":
        assert not (HERE / "runs" / RUN_ID).exists(), "reserved run exists before preflight"
    if manifest is not None:
        doc = json.loads(manifest.read_text(encoding="utf-8-sig"))
        assert doc["schema"] == "i03-var06-out-dt4-prelaunch-manifest/v1"
        assert doc["contract_sha256"] == CONTRACT_SHA and doc["run_id"] == RUN_ID
        assert sum(x["key"] == "catalog_live_prelaunch" for x in doc["source_files"]) == 1
        for entry in doc["source_files"]:
            path = Path(entry["path"])
            if not path.is_absolute():
                path = REPO / path
            if entry["key"] == "catalog_live_prelaunch":
                assert path.resolve(strict=True) == (REPO / lineage["catalog_at_selection"]["path"]).resolve(strict=True)
                assert {k: entry[k] for k in ("bytes", "sha256")} == lineage["catalog_at_selection"]["local_disk"]
                if mode == "live":
                    check_bytes(path, entry)
                else:
                    archive = next(x for x in custody["records"] if x["original_path"] == lineage["catalog_at_selection"]["path"])
                    check_bytes(HERE / archive["owned_copy"], entry)
            else:
                check_bytes(path, entry)
    return {"schema": "i03-var06-out-dt4-source-verifier/v1", "passed": True,
            "mode": mode, "parent_source_pairs": 192, "accepted_dependency_pairs": 20,
            "secondary_context_source_pairs": 2, "accepted_raw_records": 118,
            "installed_files": 3, "owned_root_context_records": 12,
            "input_sha256": identity(child_path.read_bytes())["sha256"],
            "catalog": catalog, "source_map": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "sealed"), default="live")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.mode, args.manifest)
    except Exception as exc:
        result = {"schema": "i03-var06-out-dt4-source-verifier/v1", "passed": False,
                  "mode": args.mode, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(0 if result["passed"] else 1)
