"""Append-stable source custody; Git operations are read-only ls-tree/cat-file."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from build import make
from copy_context import verify as verify_context
from copy_extra_context import verify as verify_extra_context
from copy_v102_context import verify as verify_v102_context
from model_common import parse, pin, read, typed_equal

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OLD = REPO / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.0"
ARCHIVE = HERE / "preserved-context"
GIT = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe")
CAT_REL = "cases/simlox-air-support/publication-index-v1.json"
CAT_LIVE = REPO / CAT_REL
BASE = "d2f6a8604c5e508bc5fec379b9a53dc701c15e5c"
PARENT_BASE = "33193ce8ce5763d9dd892eda9c68ab9d729c8a3a"
RUN_ID = "i04-var05-zero-transport-between-v102-ssh-20261008-01"
RUN_DIR = REPO / "tmp/native-runs/i04v05-v102-20261008-01"
V101 = REPO / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.1"
CONTRACT_PIN = {"bytes": 922508, "sha256": "2353d18f907803c9023089e70202e7381cad266a0b8c7795bf98586ee067f292"}
SELECTION_PIN = {"bytes": 277670, "sha256": "e1476616e4694df1742d095f9976eb57a512953edf6222c9a6cdc74b74ea8cde"}
CATALOG_PINS = {
    "catalog-local-497.json.bytes": {"bytes": 534641, "sha256": "e4c3966bb85829ffafadf9331ef6a719431fbab58c8203bc017d188884cfc696"},
    "catalog-git-497.json.bytes": {"bytes": 529992, "sha256": "ab9bd439b967d15965a54482b783070408d92d9a17a4963b35447b9a3c631dd3"},
}


def exact(path: Path, expected: dict) -> dict:
    assert path.is_file(), ("missing mandatory original", str(path))
    got = pin(path)
    assert got == {"bytes": expected["bytes"], "sha256": expected["sha256"]}, (str(path), got)
    return got


def tree(base: str) -> dict:
    result = subprocess.run([str(GIT), "ls-tree", "-r", "-z", base], cwd=REPO, capture_output=True)
    assert type(result.returncode) is int and result.returncode == 0, result.stderr.decode(errors="replace")
    rows = {}
    for part in result.stdout.split(b"\0"):
        if not part:
            continue
        header, name = part.split(b"\t", 1)
        mode, kind, oid = header.split(b" ")
        assert kind == b"blob" and len(oid) == 40
        path = name.decode("utf-8")
        assert path not in rows
        rows[path] = (mode.decode("ascii"), oid.decode("ascii"))
    return rows


def blobs(oids) -> dict:
    ordered = list(dict.fromkeys(oids))
    assert ordered and all(len(x) == 40 and all(c in "0123456789abcdef" for c in x) for x in ordered)
    result = subprocess.run([str(GIT), "cat-file", "--batch"],
                            input=("\n".join(ordered) + "\n").encode("ascii"),
                            cwd=REPO, capture_output=True)
    assert type(result.returncode) is int and result.returncode == 0, result.stderr.decode(errors="replace")
    raw, offset, found = result.stdout, 0, {}
    for oid in ordered:
        end = raw.index(b"\n", offset)
        header = raw[offset:end].decode("ascii").split(" ")
        assert len(header) == 3 and header[0] == oid and header[1] == "blob"
        size = int(header[2]); assert size >= 0
        data = raw[end + 1:end + 1 + size]
        assert len(data) == size and raw[end + 1 + size:end + 2 + size] == b"\n"
        found[oid] = {"bytes": size, "sha256": hashlib.sha256(data).hexdigest(), "data": data}
        offset = end + size + 2
    assert offset == len(raw) and len(found) == len(ordered)
    return found


def native_run_path(live: bool) -> dict:
    contract = read(HERE / "prospective-contract.json")
    assert str(RUN_DIR) == contract["native_run_directory"] == contract["proposed_native_run_directory"]
    assert RUN_DIR.is_absolute() and RUN_DIR.parent == REPO / "tmp/native-runs"
    if live:
        assert not RUN_DIR.exists()
    for ancestor in (RUN_DIR, *RUN_DIR.parents):
        if ancestor.exists():
            assert not ancestor.is_symlink() and not ancestor.is_junction(), ("reparse ancestor", str(ancestor))
    file_line = "File: " + (RUN_DIR / "model.sxi").as_posix()
    assert file_line.isascii() and len(file_line.encode("ascii")) == 121 <= 199
    return {"native_run_directory": str(RUN_DIR), "file_line_ascii_bytes": 121,
            "max_file_line_ascii_bytes": 199, "absent_observed": not RUN_DIR.exists()}


def catalog(selection: dict, current_tree: dict, git_blobs: dict, mode: str) -> dict:
    local = ARCHIVE / "catalog-local-497.json.bytes"
    archive = read(local)
    live_bytes = CAT_LIVE.read_bytes()
    row = selection["parent_sources_and_catalog"][-1]
    if mode == "live":
        assert pin(CAT_LIVE) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "prelaunch live catalog drift"
    live = parse(live_bytes)
    assert type(archive) is dict and type(live) is dict and list(archive) == list(live)
    assert len(archive["entries"]) == 497 and len(live["entries"]) >= 497
    assert typed_equal({k: v for k, v in archive.items() if k != "entries"},
                       {k: v for k, v in live.items() if k != "entries"})
    assert typed_equal(archive["entries"], live["entries"][:497])
    ids = [item["publication_id"] for item in live["entries"]]
    assert all(type(value) is str and value for value in ids) and len(ids) == len(set(ids))
    assert row["path"] == CAT_REL and current_tree[CAT_REL][1] == row["oid"]
    assert git_blobs[row["oid"]]["data"] == (ARCHIVE / "catalog-git-497.json.bytes").read_bytes()
    return {"historical_prefix_checked": 497, "live_entries_observed": len(ids),
            "owned_local": pin(local), "owned_git": pin(ARCHIVE / "catalog-git-497.json.bytes")}


def verify(mode: str = "live") -> dict:
    assert mode in ("live", "sealed")
    contract = read(HERE / "prospective-contract.json")
    exact(HERE / "prospective-contract.json", CONTRACT_PIN)
    assert contract["schema"] == "i04-var05-prospective-recovery-contract/v102"
    assert contract["proposed_run_id"] == RUN_ID and contract["proposed_package"] == HERE.relative_to(REPO).as_posix()
    for name, expected in CATALOG_PINS.items():
        exact(ARCHIVE / name, expected)
    context = verify_context()
    assert context == {"schema": "i04-var05-v101-context-custody/v1", "records": 131,
                       "owned_copies": 78, "mandatory_host_originals": 53}
    extra_context = verify_extra_context()
    assert extra_context["schema"] == "i04-var05-v101-extra-context-custody/v1"
    assert extra_context["copies"] == 22
    v102_context = verify_v102_context()
    assert v102_context["schema"] == "i04-var05-v102-context-custody/v1" and v102_context["copies"] == 20
    selection_row = contract["selection"]["fresh_v101_selection"]
    assert {k: selection_row[k] for k in ("bytes", "sha256")} == SELECTION_PIN
    exact(ARCHIVE / "selection.json.bytes", SELECTION_PIN)
    original_selection = Path(selection_row["path"])
    if mode == "live" or original_selection.is_file():
        exact(original_selection, SELECTION_PIN)
    selection = read(ARCHIVE / "selection.json.bytes")
    assert selection["base"] == BASE and selection["proposed_run_id"] == "i04-var05-zero-transport-between-v101-ssh-20261008-01"
    assert selection["proposed_native_run_directory"] == str(REPO / "tmp/native-runs/i04v05-v101-20261008-01")
    assert selection["excluded_v100_source_roles_rehashed"] == 1172
    old_inventory_path = OLD / "source-inventory.json"
    old_manifest_path = OLD / "prelaunch-manifest.json"
    old_freeze = contract["provenance"]["excluded_v100_source_freeze"]
    exact(old_inventory_path, old_freeze["source_inventory"])
    exact(old_manifest_path, old_freeze["prelaunch_manifest"])
    old_inventory, old_manifest = read(old_inventory_path), read(old_manifest_path)
    assert old_inventory["source_count"] == len(old_inventory["source_files"]) == 130
    assert old_manifest["source_count"] == len(old_manifest["source_files"]) == 1172
    for row in old_inventory["source_files"]:
        exact(Path(row["path"]), row)
    for row in old_manifest["source_files"]:
        exact(Path(row["path"]), row)
    parent_manifest = read(OLD / "preserved-context/parent-prelaunch-manifest.json.bytes")
    parent_selection = read(OLD / "preserved-context/parent-selection.json.bytes")
    assert parent_manifest["base_commit"] == PARENT_BASE and parent_manifest["source_count"] == 456
    assert parent_selection["base"] == PARENT_BASE and len(parent_selection["accepted_source_refs"]) == 76
    current_tree, parent_tree = tree(BASE), tree(PARENT_BASE)
    current_rows, parent_rows = selection["parent_sources_and_catalog"], parent_selection["accepted_source_refs"]
    assert len(current_rows) == 404 and len({row["path"] for row in current_rows}) == 404
    git_blobs = blobs([row["oid"] for row in current_rows + parent_rows])
    for row in current_rows[:-1]:
        assert current_tree[row["path"]][1] == row["oid"]
        exact(REPO / row["path"], row)
        assert {k: git_blobs[row["oid"]][k] for k in ("bytes", "sha256")} == row["git"]
    for row in parent_rows:
        assert parent_tree[row["path"]][1] == row["oid"]
        exact(REPO / row["path"], row["disk"])
        assert {k: git_blobs[row["oid"]][k] for k in ("bytes", "sha256")} == row["git"]
    inherited = parent_manifest["source_files"]
    assert len(inherited) == len({row["key"] for row in inherited}) == 456
    for row in inherited:
        exact(Path(row["path"]), row)
    helper = next(row for row in inherited if row["key"] == "accepted_capture_helper_ancestry")
    assert exact(HERE / "captured_process.ps1", helper)["sha256"] == "17285b90093c2d80c6241e1345b9926a2e4dd0f0b2b24f831c84c1cfa885b794"
    private = [row for row in inherited if row["key"].startswith("local_only_context_original:")]
    assert len(private) == 2 and all("tmp" in Path(row["path"]).parts for row in private)
    raw = selection["parent_mandatory_originals"]
    assert len(raw) == len({row["path"] for row in raw}) == 168
    for row in raw:
        exact(Path(row["path"]), row)
    for row in contract["recovery"]["frozen_v100_failure_originals"] + contract["recovery"]["frozen_v100_preflight_originals"]:
        exact(Path(row["path"]), row)
    docs = selection["required_docs"]
    assert len(docs) == 8
    for relative, expected in docs.items():
        exact(REPO / relative, expected)
    installed = selection["installed_pins"]
    assert len(installed) == 3
    for expected in installed.values():
        exact(Path(expected["path"]), expected)
    prior = contract["recovery_v101_method_order"]
    exact(V101 / "source-inventory.json", prior["inventory"])
    exact(V101 / "prelaunch-manifest.json", prior["manifest"])
    prior_inventory = read(V101 / "source-inventory.json")
    prior_manifest = read(V101 / "prelaunch-manifest.json")
    assert prior_inventory["source_count"] == len(prior_inventory["source_files"]) == prior["owned_source_count"] == 172
    assert prior_manifest["source_count"] == len(prior_manifest["source_files"]) == prior["manifest_role_count"] == 1980
    assert prior_inventory["source_files"] == prior["owned_sources"]
    assert prior_manifest["source_files"] == prior["manifest_roles"]
    for row in prior_inventory["source_files"] + prior_manifest["source_files"]:
        exact(Path(row["path"]), row)
    for key, count in (("failed_independent_preflight_originals", 3),
                       ("pure_originals", 21), ("root_and_copier_originals", 18)):
        assert len(prior[key]) == count
        for row in prior[key]:
            exact(Path(row["path"]), row)
    exact(Path(prior["independent_no_go"]["path"]), prior["independent_no_go"])
    cat = catalog(selection, current_tree, git_blobs, mode)
    expected_input, _ = make()
    assert (HERE / "native-input.json").read_bytes() == expected_input
    run = native_run_path(mode == "live")
    return {"schema": "i04-var05-source-gate/v102", "mode": mode,
            "accepted_current_disk_git_pairs": 403, "old_v100_owned_sources": 130,
            "old_v100_prelaunch_roles": 1172, "inherited_parent_manifest_roles": 456,
            "inherited_parent_base_git_pairs": 76, "inherited_private_local_only_originals": 2,
            "accepted_capture_helper_ancestry_checked": 1,
            "mandatory_accepted_original_raw": 168, "failed_v100_originals": 34,
            "failed_v100_preflight_originals": 18, "mandatory_failed_context_originals": 53,
            "owned_failed_context_copies": 78, "required_docs": 8, "installed": 3,
            "owned_extra_context_copies": 22,
            "owned_v102_context_copies": 20,
            "excluded_v101_owned_sources": 172, "excluded_v101_prelaunch_roles": 1980,
            "excluded_v101_failed_preflight_originals": 3,
            "excluded_v101_pure_originals": 21,
            "excluded_v101_root_and_copier_originals": 18,
            "catalog": cat, "native_run_path": run,
            "child_input": pin(HERE / "native-input.json"),
            "read_only_git_commands": ["ls-tree -r -z", "cat-file --batch"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "sealed"), default="live")
    print(json.dumps(verify(parser.parse_args().mode), sort_keys=True))
