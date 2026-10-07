"""Read-only source, raw, and historical catalog provenance for I03.var11."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from build import construct, typed_equal, verify as verify_diff
from copy_root_evidence import verify as verify_root_evidence

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GIT = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe")
CONTRACT_SHA = "67bef26d4fdec4d34e88b20e177239fb973aeba7152f72d26d4d9f9a4f9a79c1"
RUN_ID = "i03-var11-out-unarrived-v100-ssh-20261008-01"
SCHEMA = "i03-var11-out-unarrived-source-verifier/v1"


def identity(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check_bytes(path: Path, expected: dict) -> dict:
    assert path.is_file(), f"missing original or owned evidence: {path}"
    actual = identity(path.read_bytes())
    assert actual == {key: expected[key] for key in ("bytes", "sha256")}, (str(path), actual)
    return actual


def type_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(type_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(type_equal(a, b) for a, b in zip(left, right))
    return left == right


def git_tree(base: str) -> dict[str, str]:
    result = subprocess.run([str(GIT), "ls-tree", "-r", "-z", base], cwd=REPO, capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    tree = {}
    for record in result.stdout.split(b"\0"):
        if record:
            header, path = record.split(b"\t", 1)
            mode, kind, oid = header.split(b" ")
            if kind == b"blob" and mode in (b"100644", b"100755"):
                key = path.decode("utf-8")
                assert key not in tree
                tree[key] = oid.decode("ascii")
    return tree


def git_blob(tree: dict[str, str], path: str) -> bytes:
    assert path in tree, path
    result = subprocess.run([str(GIT), "cat-file", "blob", tree[path]], cwd=REPO, capture_output=True)
    assert result.returncode == 0, path
    return result.stdout


def check_catalog_live(archive: dict, live_bytes: bytes, item: dict, mode: str) -> int:
    if mode == "live":
        assert identity(live_bytes) == item["local_disk"], "prelaunch catalog byte drift"
    live = json.loads(live_bytes.decode("utf-8-sig"))
    assert type(live) is dict and live.keys() == archive.keys()
    assert type_equal({k: v for k, v in live.items() if k != "entries"}, item["metadata"])
    assert type(live["entries"]) is list and len(live["entries"]) >= 492
    assert type_equal(live["entries"][:492], archive["entries"]), "catalog prefix drift"
    identifiers = [entry["publication_id"] for entry in live["entries"]]
    assert all(type(x) is str and x for x in identifiers) and len(identifiers) == len(set(identifiers))
    return len(identifiers)


def catalog_gate(contract: dict, tree: dict, mode: str, custody: dict) -> dict:
    item = contract["source_lineage"]["catalog_at_selection"]
    archive_item = custody["historical_catalog"]
    assert archive_item["original_path"] == item["path"]
    assert archive_item["owned_copy"] == item["owned_exact_archive"]
    archive_bytes = (HERE / item["owned_exact_archive"]).read_bytes()
    assert identity(archive_bytes) == item["local_disk"] == {
        key: archive_item[key] for key in ("bytes", "sha256")}
    assert identity(git_blob(tree, item["path"])) == item["published_git_at_base"]
    archive = json.loads(archive_bytes.decode("utf-8-sig"))
    assert type(archive) is dict and type(archive.get("entries")) is list
    assert len(archive["entries"]) == item["entry_count"] == 492
    assert type_equal({k: v for k, v in archive.items() if k != "entries"}, item["metadata"])
    count = check_catalog_live(archive, (REPO / item["path"]).read_bytes(), item, mode)
    return {"archived_entries": 492, "live_entries": count,
            "archive_sha256": item["local_disk"]["sha256"],
            "base_git_sha256": item["published_git_at_base"]["sha256"]}


def verify(mode: str = "live", manifest: Path | None = None) -> dict:
    assert mode in ("live", "sealed")
    check_bytes(HERE / "contract.json", {"bytes": 325510, "sha256": CONTRACT_SHA})
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    assert contract["run_id"] == RUN_ID and contract["version"] == "1.0.0"
    lineage = contract["source_lineage"]
    custody = json.loads((HERE / "root-selection-custody.json").read_text(encoding="utf-8"))
    assert custody["schema"] == "i03-var11-root-selection-custody/v1"
    assert len(custody["records"]) == len(lineage["root_selection_context"]) == 7
    assert verify_root_evidence()["owned_context_records"] == 38
    source_map = {}
    additional = json.loads((HERE / "root-evidence-custody.json").read_text(encoding="utf-8"))
    for item in additional["records"]:
        source_map[item["owned_copy"]] = check_bytes(HERE / item["owned_copy"], item)
    for contract_pin, item in zip(lineage["root_selection_context"], custody["records"]):
        assert contract_pin["path"] == item["original_path"]
        assert contract_pin["owned_inert_copy"] == item["owned_copy"]
        assert {key: contract_pin[key] for key in ("bytes", "sha256")} == {
            key: item[key] for key in ("bytes", "sha256")}
        source_map[item["owned_copy"]] = check_bytes(HERE / item["owned_copy"], item)
        original = Path(item["original_path"])
        if original.exists():
            check_bytes(original, item)
    tree = git_tree(lineage["base_commit"])
    pairs = lineage["primary_parent_source_and_secondary_context_source_disk_vs_git_at_base"]
    assert len(pairs) == 452
    for item in pairs:
        source_map[item["path"]] = check_bytes(REPO / item["path"], item["local_disk"])
        assert identity(git_blob(tree, item["path"])) == item["published_git_at_base"], item["path"]
    raw = lineage["original_raw"]
    assert len(raw) == 144
    assert sum(item["classification"] == "accepted_or_required_context" for item in raw) == 118
    assert sum(item["classification"] == "excluded_failed_v100_witness" for item in raw) == 26
    accepted = [item for item in raw if item["classification"] == "accepted_or_required_context"]
    failed = [item for item in raw if item["classification"] == "excluded_failed_v100_witness"]
    assert sum(Path(item["original_path"]).name == "closure.json" for item in accepted) == 6
    assert sum(Path(item["original_path"]).name == "invocation.json" for item in accepted) == 6
    assert sum(Path(item["original_path"]).name == "closure.json" for item in failed) == 1
    assert sum(Path(item["original_path"]).name == "invocation.json" for item in failed) == 1
    for item in raw:
        source_map[item["original_path"]] = check_bytes(Path(item["original_path"]), item)
    assert len(lineage["installed"]) == 3
    for item in lineage["installed"]:
        source_map[item["path"]] = check_bytes(Path(item["path"]), item)
    assert len(lineage["required_docs"]) == 8
    for item in lineage["required_docs"]:
        source_map[item["path"]] = check_bytes(REPO / item["path"], item)
    for name in ("accepted_primary_parent_index", "published_secondary_context_index"):
        item = lineage[name]
        check_bytes(REPO / item["path"], item)
    catalog = catalog_gate(contract, tree, mode, custody)
    source_map[lineage["catalog_at_selection"]["owned_exact_archive"]] = check_bytes(
        HERE / lineage["catalog_at_selection"]["owned_exact_archive"],
        lineage["catalog_at_selection"]["local_disk"])
    parent = json.loads((HERE.parent / "I03-var02-idle-crew-out-v1.0.2/native-input.json").read_text(encoding="utf-8"))
    child_path = HERE / "native-input.json"
    child = json.loads(child_path.read_text(encoding="utf-8"))
    assert typed_equal(child, construct(parent, contract))
    diff = verify_diff(parent, child, contract)
    stored_diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    assert stored_diff["child_sha256"] == identity(child_path.read_bytes())["sha256"]
    assert all(type_equal(diff[k], stored_diff[k]) for k in diff)
    if mode == "live":
        assert not (HERE / "runs" / RUN_ID).exists(), "reserved run already exists"
    if manifest is not None:
        doc = json.loads(manifest.read_text(encoding="utf-8-sig"))
        assert doc["schema"] == "i03-var11-out-unarrived-prelaunch-manifest/v1"
        assert doc["contract_sha256"] == CONTRACT_SHA and doc["run_id"] == RUN_ID
        assert not any(entry["key"] == "catalog_live_prelaunch" for entry in doc["source_files"])
        live_pin = doc["live_catalog_prelaunch_pin"]
        assert live_pin["path"] == str((REPO / lineage["catalog_at_selection"]["path"]).resolve(strict=True))
        assert {key: live_pin[key] for key in ("bytes", "sha256")} == lineage["catalog_at_selection"]["local_disk"]
        if mode == "live":
            check_bytes(Path(live_pin["path"]), live_pin)
        for entry in doc["source_files"]:
            path = Path(entry["path"])
            if not path.is_absolute():
                path = REPO / path
            check_bytes(path, entry)
    return {"schema": SCHEMA, "passed": True, "mode": mode,
            "source_pairs": 452, "accepted_raw_records": 118,
            "accepted_nonclosure_raw_records": 106,
            "accepted_closure_records": 6, "accepted_invocation_records": 6,
            "excluded_failed_witness_raw_records": 26, "original_raw_records": 144,
            "installed_files": 3, "owned_selection_records": 7,
            "owned_additional_context_records": 38,
            "input_sha256": identity(child_path.read_bytes())["sha256"],
            "catalog": catalog, "source_map": source_map}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "sealed"), default="live")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        verdict = verify(args.mode, args.manifest)
    except Exception as exc:
        verdict = {"schema": SCHEMA, "passed": False, "mode": args.mode,
                   "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(verdict, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(0 if verdict["passed"] else 1)
