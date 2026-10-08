"""Read-only source, prerequisite raw and historical catalog byte gate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from build import construct, typed_equal

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GIT = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe")
CONTRACT_SHA = "17ab577282e2186040d93195500e9df7565db51922b75468ffe62cc60c7fb30d"
ROOT_PREREQ_SHA = "f899083c931c7ae10f4f1e5f73b9945993dc185ca4ffc0b33b86f595d00d4ae1"
DESIGN_CUSTODY_SHA = "33f0750cc6390f5337a1e01ef8009f60e9eabec6c20ea4c56e343a70e8dd927c"
INPUT_SHA = {
    "control_out1": "c8b98ec133963d49a104426066c8d9e273fae0b5c77f53d9c955dc9b3c22532c",
    "child_out2": "c8558c0707e246465038677bcc3757586d89c9e9ab51157e3166ae6cba4be1eb",
}
RUN_IDS = {
    "control_out1": "i03-var03-control-out1-v100-ssh-20261008-01",
    "child_out2": "i03-var03-child-out2-v100-ssh-20261008-01",
}


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(path: Path, record: dict) -> dict:
    assert path.is_file(), ("missing mandatory original", str(path))
    found = pin(path.read_bytes())
    assert all(found[key] == value for key, value in record.items() if key in found), (str(path), found, record)
    return found


def unique_json(data: bytes) -> object:
    def object_pairs(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            assert key not in result, ("duplicate JSON key", key)
            result[key] = value
        return result

    def nonfinite(value: str) -> None:
        raise ValueError(value)

    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=object_pairs, parse_constant=nonfinite)


def git_tree(base: str) -> dict[str, str]:
    proc = subprocess.run([str(GIT), "ls-tree", "-r", "-z", base], cwd=REPO, capture_output=True)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    tree = {}
    for row in proc.stdout.split(b"\0"):
        if row:
            meta, path = row.split(b"\t", 1)
            mode, kind, oid = meta.split(b" ")
            if kind == b"blob" and mode in (b"100644", b"100755"):
                key = path.decode("utf-8")
                assert key not in tree
                tree[key] = oid.decode("ascii")
    return tree


def git_blob(tree: dict[str, str], relative: str) -> bytes:
    assert relative in tree, relative
    proc = subprocess.run([str(GIT), "cat-file", "blob", tree[relative]], cwd=REPO, capture_output=True)
    assert proc.returncode == 0, (relative, proc.stderr.decode(errors="replace"))
    return proc.stdout


def catalog(contract: dict, tree: dict[str, str], mode: str) -> dict:
    item = contract["source_lineage"]["catalog_at_design"]
    owned = HERE / "preserved-catalog/publication-index-at-design.json.bytes"
    archive_bytes = owned.read_bytes()
    assert pin(archive_bytes) == item["local_disk"]
    assert pin(git_blob(tree, item["path"])) == {k: item["published_git_at_base"][k] for k in ("bytes", "sha256")}
    archive = unique_json(archive_bytes)
    live_bytes = (REPO / item["path"]).read_bytes()
    if mode == "live":
        assert pin(live_bytes) == item["local_disk"], "prelaunch live catalog changed"
    live = unique_json(live_bytes)
    assert type(archive) is type(live) is dict
    assert len(archive["entries"]) == item["entries"] == 493
    assert type(live["entries"]) is list and len(live["entries"]) >= 493
    assert typed_equal({k: v for k, v in archive.items() if k != "entries"}, item["metadata"])
    assert typed_equal({k: v for k, v in live.items() if k != "entries"}, item["metadata"])
    assert typed_equal(live["entries"][:493], archive["entries"])
    ids = [entry["publication_id"] for entry in live["entries"]]
    assert all(type(x) is str and x for x in ids) and len(ids) == len(set(ids))
    return {"archived_entries": 493, "live_entries_observed": len(ids),
            "owned_archive": str(owned), "owned_archive_pin": pin(archive_bytes),
            "base_git_pin": item["published_git_at_base"]}


def historical_custody(contract: dict) -> dict:
    source = contract["source_lineage"]
    for key, copy in (
        ("root_selection_guard", "issue18-next-owner-proof-20261008-receipt.json.bytes"),
        ("root_dependency_audit", "i03-var03-root-dependency-audit-20261008.json.bytes"),
    ):
        row = source[key]
        wanted = {k: row[k] for k in ("bytes", "sha256")}
        check(HERE / "preserved-root-context" / copy, wanted)
        original = REPO / row["path"]
        if original.exists():
            check(original, wanted)
    map_path = HERE / "design-history-custody.json"
    check(map_path, {"sha256": DESIGN_CUSTODY_SHA})
    mapping = unique_json(map_path.read_bytes())
    assert mapping["schema"] == "i03-var03-design-history-custody/v1"
    rows = mapping["records"]
    assert len(rows) == 27 and len({row["owned_copy"] for row in rows}) == 27
    declared = {row["path"]: row for row in source["draft_history"]}
    assert len(declared) == 21
    assert declared.keys() <= {row["original_path"] for row in rows}
    for row in rows:
        wanted = {k: row[k] for k in ("bytes", "sha256")}
        if row["original_path"] in declared:
            assert wanted == {k: declared[row["original_path"]][k] for k in ("bytes", "sha256")}
        check(HERE / row["owned_copy"], wanted)
        original = REPO / row["original_path"]
        if original.exists():
            check(original, wanted)
    return {"root_selection_copies": 2, "design_history_copies": len(rows),
            "design_history_map_sha256": DESIGN_CUSTODY_SHA}


def verify(mode: str = "live", arm: str = "control_out1") -> dict:
    assert mode in ("live", "sealed") and arm in INPUT_SHA
    check(HERE / "contract.json", {"sha256": CONTRACT_SHA})
    contract = unique_json((HERE / "contract.json").read_bytes())
    assert contract["run_ids_proposed_absent"] == list(RUN_IDS.values())
    tree = git_tree(contract["source_lineage"]["base_commit"])
    counts = {"parent_source_pairs": 0, "parent_raw": 0, "prerequisite_source_pairs": 0,
              "prerequisite_original_raw": 0, "docs": 0, "installed": 0}
    for row in contract["source_lineage"]["accepted_parent_source_disk_git_at_base"]:
        path = row["path"]
        assert check(REPO / path, row["disk"]) == row["disk"]
        assert pin(git_blob(tree, path)) == row["git"]
        counts["parent_source_pairs"] += 1
    for row in contract["source_lineage"]["accepted_parent_original_raw"]:
        check(Path(row["path"]), row)
        counts["parent_raw"] += 1
    prereq_path = HERE / "preserved-root-context/i03-var03-root-prerequisite-seals-v2-20261008.json.bytes"
    check(prereq_path, {"sha256": ROOT_PREREQ_SHA})
    prereq = unique_json(prereq_path.read_bytes())
    assert prereq["base"] == contract["source_lineage"]["base_commit"]
    assert prereq["decision"] == "GO_BYTES_ONLY" and prereq["failures"] == []
    assert len(prereq["records"]) == 141 and len(prereq["source_git_identities"]) == 63
    for row in prereq["records"]:
        assert row["pass"] is True
        check(Path(row["path"]), row["observed"])
        if row["role"] == "mandatory_original_raw":
            counts["prerequisite_original_raw"] += 1
    for row in prereq["source_git_identities"]:
        assert check(REPO / row["path"], row["local_disk"]) == row["local_disk"]
        assert pin(git_blob(tree, row["path"])) == row["published_git"]
        counts["prerequisite_source_pairs"] += 1
    assert counts == {"parent_source_pairs": 17, "parent_raw": 34,
                      "prerequisite_source_pairs": 63, "prerequisite_original_raw": 78,
                      "docs": 0, "installed": 0}, counts
    for row in contract["source_lineage"]["required_docs"]:
        assert check(REPO / row["path"], row) == {k: row[k] for k in ("bytes", "sha256")}
        counts["docs"] += 1
    for row in contract["source_lineage"]["installed"]:
        check(Path(row["path"]), row)
        counts["installed"] += 1
    assert counts["docs"] == 8 and counts["installed"] == 3
    cat = catalog(contract, tree, mode)
    history = historical_custody(contract)
    parent = unique_json((REPO / contract["source_delta"]["base"]["path"]).read_bytes())
    for name, wanted in INPUT_SHA.items():
        path = HERE / f"{name}-input.json"
        assert check(path, {"sha256": wanted})["sha256"] == wanted
        assert typed_equal(unique_json(path.read_bytes()), construct(parent, name))
    run = HERE / "runs" / RUN_IDS[arm]
    if mode == "live":
        assert not run.exists(), ("reserved run already exists", str(run))
    return {"schema": "i03-var03-source-gate/v1", "mode": mode, "arm": arm,
            "counts": counts, "catalog": cat, "run_absent": not run.exists(),
            "historical_custody": history,
            "contract_sha256": CONTRACT_SHA, "input_sha256": INPUT_SHA[arm]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "sealed"), default="live")
    parser.add_argument("--arm", choices=tuple(INPUT_SHA), default="control_out1")
    args = parser.parse_args()
    print(json.dumps(verify(args.mode, args.arm), sort_keys=True))
