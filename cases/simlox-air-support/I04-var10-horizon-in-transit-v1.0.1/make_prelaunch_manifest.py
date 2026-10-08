"""Deterministic exact prelaunch source map; root alone writes canonical bytes."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from make_source_inventory import HERE, body as inventory_body, candidate as inventory_candidate
from model_common import pin, read
from source_gate import (ARCHIVE, BASE, CAT_LIVE, CAT_LOCAL, CORRUPT_FILE_PIN,
                         CORRUPT_FILE_WITNESS, PARENT, REPO,
                         RUN_DIR, RUN_ID, exact, verify)

SCHEMA = "i04-var10-horizon-transit-prelaunch-manifest/v101"
CONTRACT_SHA = "40b6193c7efabf44901bab2c71f57d7090b8a2b52253117a19f96370363fa1bb"
ROLES = {
    "prospective-contract.json": "prospective_contract",
    "execution-contract.json": "execution_binding",
    "native-input.json": "child_input",
    "validate_native_cli.py": "behavior_validator",
    "run_native_ssh.ps1": "runner_script",
    "review/independent_replay.py": "independent_replay",
    "review/independent_self_check.py": "independent_self_check",
}


def contract_original_rows(value):
    rows = {}
    def visit(node):
        if isinstance(node, dict):
            if {"path", "bytes", "sha256"} <= node.keys():
                path = Path(node["path"])
                if not path.is_absolute():
                    assert ".." not in path.parts
                    path = REPO / path
                    assert path.resolve(strict=True).is_relative_to(REPO)
                identity = str(path.resolve(strict=True)).casefold()
                expected = {key: node[key] for key in ("bytes", "sha256")}
                if identity in rows:
                    assert rows[identity][1] == expected
                else:
                    rows[identity] = (path, expected)
            for item in node.values():
                visit(item)
        elif isinstance(node, list):
            for item in node:
                visit(item)
    visit(value)
    return list(rows.values())


def candidate(provisional=False, mode="sealed"):
    assert type(provisional) is bool and mode in ("live", "sealed")
    check = verify(mode)
    assert check["owned_pure_proof_copies"] == (0 if provisional else 21)
    assert (check["parent_sources"], check["parent_git_disk_pairs"],
            check["accepted_dependency_pairs"], check["parent_manifest_roles"],
            check["mandatory_parent_original_raw"],
            check["mandatory_parent_preflight_originals"],
            check["excluded_v100_sources"], check["owned_context_copies"],
            check["converter_negative_witnesses"],
            check["mandatory_prospective_proof_originals"],
            check["catalog"]["historical_prefix_checked"]) == (401, 403, 76, 456, 153, 15, 24, 30, 1, 24, 499)
    assert read(HERE / "execution-contract.json")["native_run_directory"] == str(RUN_DIR)
    records, keys, identities = [], set(), {}

    def add(key, path: Path, wanted=None):
        absolute = path.resolve(strict=True)
        assert key.casefold() not in keys, key
        keys.add(key.casefold())
        got = pin(absolute)
        if wanted is not None:
            assert got == {name: wanted[name] for name in ("bytes", "sha256")}, key
        identity = str(absolute).casefold()
        if identity in identities:
            assert identities[identity] == got, (key, "duplicate path has different seal")
        identities[identity] = got
        records.append({"key": key, "path": str(absolute), **got})

    owned = inventory_candidate(provisional)
    for row in owned["source_files"]:
        add(ROLES.get(row["relative_path"], "owned:" + row["relative_path"]),
            Path(row["path"]), row)
    if not provisional:
        inventory_path = HERE / "source-inventory.json"
        assert inventory_path.read_bytes() == inventory_body(owned)
        add("owned_source_inventory", inventory_path)

    parent_index = read(PARENT / "evidence-index.json")
    exact(PARENT / "evidence-index.json", {"bytes": 176439,
        "sha256": "09e0fe50532797f97d13b3a17fdd886adfc9a18c925038b15058b3850b2273ff"})
    assert len(parent_index["source_files"]) == 401
    for index, row in enumerate(parent_index["source_files"]):
        add(f"accepted_parent_source:{index}", PARENT / row["path"], row)
    parent_manifest = read(PARENT / "prelaunch-manifest.json")
    assert len(parent_manifest["source_files"]) == 456
    for index, row in enumerate(parent_manifest["source_files"]):
        add(f"accepted_parent_role:{index}", Path(row["path"]), row)
    assert sum(row["key"].startswith("local_only_context_original:") for row in parent_manifest["source_files"]) == 2
    for index, row in enumerate(parent_index["raw_files"]):
        add(f"accepted_parent_raw:{index}", Path(row["path"]), row)
    for index, row in enumerate(parent_index["preflight_original_files"]):
        add(f"accepted_parent_preflight:{index}", Path(row["path"]), row)
    assert len(parent_index["raw_files"]) == 153 and len(parent_index["preflight_original_files"]) == 15
    pairs = read(HERE / "parent-source-pairs.json")
    assert len(pairs["records"]) == 403
    for index, row in enumerate(pairs["records"]):
        add(f"accepted_current_source:{index}", REPO / row["path"], row)
    contract = read(HERE / "prospective-contract.json")
    originals = contract_original_rows(contract)
    assert len(originals) == check["contract_originals"]
    for index, (path, row) in enumerate(originals):
        add(f"prospective_contract_original:{index}", path, row)
    context = read(HERE / "context-custody.json")
    assert len(context["records"]) == 30 and context["originals_mandatory_on_this_host"] is True
    for index, row in enumerate(context["records"]):
        assert row["owned_copy"] == f"preserved-context/context-{index:03d}.bytes"
        add(f"excluded_v100_or_context_original:{index}", Path(row["original_path"]), row)
    prospective_proof = read(HERE / "prospective-proof-custody.json")
    assert len(prospective_proof["records"]) == 24
    for index, row in enumerate(prospective_proof["records"]):
        assert row["disposition"] == "mandatory_host_original"
        add(f"prospective_review_original:{index}", Path(row["original_path"]), row)
    for index, row in enumerate(read(REPO / "tmp/i04-var10-v100-excluded-construction-inventory-20261008.json")["source_files"]):
        add(f"excluded_v100_owned:{index}", REPO / row["path"], row)
    assert index + 1 == 24
    add("converter_corrupt_file_negative_original", CORRUPT_FILE_WITNESS, CORRUPT_FILE_PIN)
    assert str(CAT_LIVE) == str((REPO / "cases/simlox-air-support/publication-index-v1.json").resolve(strict=True))
    if mode == "live":
        assert not RUN_DIR.exists()
    return {"schema": SCHEMA, "run_id": RUN_ID, "native_run_directory": str(RUN_DIR),
            "file_line_ascii_bytes": 121, "file_line_ascii_max": 199,
            "base_commit": BASE, "contract_sha256": CONTRACT_SHA,
            "execution_binding_sha256": pin(HERE / "execution-contract.json")["sha256"],
            "source_count": len(records), "source_files": records,
            "live_catalog_prelaunch_pin": {"path": str(CAT_LIVE), **CAT_LOCAL},
            "historical_catalog_prefix_always_checked": 499,
            "accepted_parent_indexed_sources": 401,
            "accepted_current_source_git_pairs": 403,
            "accepted_dependency_git_pairs": 76,
            "accepted_parent_manifest_roles": 456,
            "accepted_parent_raw": 153,
            "accepted_parent_preflight_originals": 15,
            "total_parent_original_raw": 168,
            "excluded_v100_source_files": 24,
            "owned_context_copies": 30,
            "owned_pure_proof_copies": check["owned_pure_proof_copies"],
            "contract_originals": len(originals),
            "converter_corrupt_file_negative_originals": 1,
            "mandatory_prospective_proof_originals": 24,
            "local_only_context_originals": 2,
            "new_native_runs_authorized_by_manifest": 0,
            "independent_method_state": "provisional" if provisional else "exact methods pinned; fresh approval required"}


def body(document):
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main():
    args = sys.argv[1:]
    external = len(args) == 2 and args[0] in ("--candidate", "--provisional-candidate")
    assert external or args in ([], ["--dry"], ["--provisional"], ["--write"])
    provisional = args == ["--provisional"] or (external and args[0] == "--provisional-candidate")
    mode = "live" if args in (["--write"], ["--provisional"]) or external else "sealed"
    data = body(candidate(provisional, mode))
    target = HERE / "prelaunch-manifest.json"
    if external:
        output = Path(args[1]).absolute()
        assert output.parent.is_dir() and not output.exists() and output.is_relative_to(REPO / "tmp")
        with output.open("xb") as stream:
            stream.write(data)
    elif args == ["--write"]:
        assert not target.exists()
        with target.open("xb") as stream:
            stream.write(data)
    elif not args:
        assert target.read_bytes() == data
    print(json.dumps({"schema": "i04-var10-horizon-transit-manifest-check/v101",
                      "source_count": len(json.loads(data)["source_files"]),
                      "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args == ["--write"], "candidate_written": external,
                      "provisional": provisional, "mode": mode}, sort_keys=True))


if __name__ == "__main__":
    main()
