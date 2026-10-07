"""Independent read-only byte and custody audit for the frozen v100 preflight bundle."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
GIT = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe")
MANIFEST_SHA = "ce196b80f2365519885fb97b77eda0b04737736f239dfac46903df99edcf42a9"
CONTRACT_SHA = "f03452c24030789f64a25df0419ffd574f97411a9ea0e1faa83df5743a22f793"
EXPECTED_ROLES = {
    "child_contract": "contract.json",
    "child_input": "native-input.json",
    "behavior_validator": "validate_native_cli.py",
    "runner_script": "run_native_ssh.ps1",
    "independent_replay": "review/independent_replay.py",
    "independent_self_check": "review/independent_self_check.py",
}


def seal(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(path: Path, record: dict) -> None:
    assert path.is_file(), str(path)
    assert seal(path.read_bytes()) == {k: record[k] for k in ("bytes", "sha256")}, str(path)


def typed(a: object, b: object) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed(x, y) for x, y in zip(a, b))
    return a == b


def main() -> None:
    manifest_path = HERE / "prelaunch-manifest.json"
    check(manifest_path, {"bytes": 172903, "sha256": MANIFEST_SHA})
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "i03-var06-out-dt4-prelaunch-manifest/v1"
    assert manifest["source_count"] == len(manifest["source_files"]) == 445
    assert manifest["native_runs_authorized_by_manifest"] == 0
    assert manifest["run_id"] == "i03-var06-out-dt4-v100-ssh-20261008-01"
    assert manifest["contract_sha256"] == CONTRACT_SHA
    assert not (HERE / "runs" / manifest["run_id"]).exists()
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    assert seal((HERE / "contract.json").read_bytes())["sha256"] == CONTRACT_SHA

    records = manifest["source_files"]
    keys = [x["key"] for x in records]
    paths = [x["path"] for x in records]
    assert len(set(keys)) == len(keys) and len(set(paths)) == len(paths)
    by_key = {x["key"]: x for x in records}
    for role, relative in EXPECTED_ROLES.items():
        assert Path(by_key[role]["path"]) == HERE / relative
    assert by_key["independent_replay"]["sha256"] == "c3727fff989fff711482371c89298c4f2b147eea6e07f0610406897459979836"
    assert by_key["independent_self_check"]["sha256"] == "1b0ae63dbf3c829d96024fa13874a9a0bf61038acbac5fbd6b7920f41b7eac0e"
    assert by_key["child_input"]["sha256"] == "3ff558fd5389b1d0e67ec93676a79f9cb00f23823f0514bccf5591c90174f694"
    for record in records:
        check(Path(record["path"]), record)

    lineage = contract["source_lineage"]
    assert lineage["base_commit"] == "3887a7fd5e387f078a716e49df62f894ce767700"
    tree_raw = subprocess.check_output([str(GIT), "ls-tree", "-rz", lineage["base_commit"]], cwd=REPO)
    tree = {}
    for row in tree_raw.split(b"\0"):
        if row:
            header, path = row.split(b"\t", 1)
            tree[path.decode("utf-8")] = header.split(b" ")[-1].decode("ascii")
    pair_sections = (
        ("parent_source_disk_and_git_at_base", 192),
        ("accepted_dependency_source_disk_and_git_at_base", 20),
        ("accepted_secondary_context_source_disk_and_git_at_base", 2),
    )
    pair_count = 0
    for section, expected_count in pair_sections:
        pairs = lineage[section]
        assert len(pairs) == expected_count
        for pair in pairs:
            check(REPO / pair["path"], pair["local_disk"])
            oid = tree[pair["path"]]
            blob = subprocess.check_output([str(GIT), "cat-file", "blob", oid], cwd=REPO)
            assert seal(blob) == pair["published_git_at_base"], pair["path"]
            assert pair["byte_equal"] is (pair["local_disk"] == pair["published_git_at_base"])
            pair_count += 1

    accepted = lineage["accepted_parent_and_context_raw"] + lineage["accepted_secondary_context_run_files"]
    assert len(accepted) == 118
    for raw in accepted:
        check(Path(raw["original_path"]), raw)
    helper = json.loads((HERE / "helper-root-custody.json").read_text(encoding="utf-8"))
    assert len(helper["records"]) == 28
    small = [x for x in helper["records"] if x["owned_copy"] is not None]
    large = [x for x in helper["records"] if x["owned_copy"] is None]
    assert len(small) == 26 and len(large) == 2
    for row in small:
        check(HERE / row["owned_copy"], row)
    assert manifest["helper_large_original_raw_pins"] == [
        {"path": x["original_path"], "bytes": x["bytes"], "sha256": x["sha256"]} for x in large
    ]
    for row in large:
        path = REPO / row["original_path"]
        if path.exists():
            check(path, row)

    root_custody = json.loads((HERE / "root-context-custody.json").read_text(encoding="utf-8"))
    assert len(root_custody["records"]) == 12
    for row in root_custody["records"]:
        check(HERE / row["owned_copy"], row)
    catalog_item = lineage["catalog_at_selection"]
    archive_row = next(x for x in root_custody["records"] if x["original_path"] == catalog_item["path"])
    archive_path = HERE / archive_row["owned_copy"]
    check(archive_path, catalog_item["local_disk"])
    current = json.loads((REPO / catalog_item["path"]).read_text(encoding="utf-8-sig"))
    archive = json.loads(archive_path.read_text(encoding="utf-8-sig"))
    assert len(archive["entries"]) == catalog_item["entry_count"] == 491
    assert len(current["entries"]) >= 491
    assert typed(current["entries"][:491], archive["entries"])
    assert typed({k: v for k, v in current.items() if k != "entries"},
                 {k: v for k, v in archive.items() if k != "entries"})
    ids = [x["publication_id"] for x in current["entries"]]
    assert len(ids) == len(set(ids))

    print(json.dumps({"schema": "i03-var06-independent-pure-preflight-audit/v1",
                      "passed": True, "manifest_sha256": MANIFEST_SHA,
                      "source_records": len(records), "source_pairs_local_and_git": pair_count,
                      "accepted_original_raw_records": len(accepted),
                      "helper_owned_small_copies": len(small),
                      "helper_large_optional_original_pins": len(large),
                      "root_context_copies": len(root_custody["records"]),
                      "catalog_archived_prefix": 491}, sort_keys=True))


if __name__ == "__main__":
    main()
