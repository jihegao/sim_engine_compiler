"""Deterministic sealed source map; root alone writes canonical manifest once."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from make_source_inventory import HERE, body as inventory_body, candidate as inventory_candidate
from model_common import pin, read
from source_gate import BASE, REPO, RUN_ID, SELECTION, exact, verify

SCHEMA = "i04-var03-idle-between-prelaunch-manifest/v101"
CONTRACT_SHA = "7c0fd3dd20ab1f52eca3a47e5517f146469a1cec648d64b3ba4e5fbc3dbd1572"
ROLES = {
    "prospective-contract.json": "prospective_contract",
    "execution-contract.json": "execution_binding",
    "native-input.json": "child_input",
    "validate_native_cli.py": "behavior_validator",
    "run_native_ssh.ps1": "runner_script",
    "review/independent_replay.py": "independent_replay",
    "review/independent_self_check.py": "independent_self_check",
}


def candidate(provisional=False, mode="sealed"):
    assert mode in ("live", "sealed")
    check = verify(mode)
    assert (check["accepted_disk_git_pairs"], check["mandatory_accepted_original_raw"],
            check["required_docs"], check["installed"]) == (76, 114, 8, 3)
    selection = read(SELECTION)
    records, keys, paths = [], set(), set()

    def add(key, path: Path, wanted=None):
        absolute = path.resolve(strict=True)
        identity = str(absolute).lower()
        assert key not in keys and identity not in paths, (key, absolute)
        keys.add(key)
        paths.add(identity)
        got = pin(absolute)
        if wanted is not None:
            assert got == {name: wanted[name] for name in ("bytes", "sha256")}, key
        records.append({"key": key, "path": str(absolute), **got})

    owned = inventory_candidate(provisional)
    for row in owned["source_files"]:
        add(ROLES.get(row["relative_path"], "owned:" + row["relative_path"]), Path(row["path"]), row)
    if not provisional:
        inventory_path = HERE / "source-inventory.json"
        assert inventory_path.read_bytes() == inventory_body(owned)
        add("owned_source_inventory", inventory_path)
    for index, row in enumerate(selection["accepted_source_refs"]):
        add(f"accepted_source:{index}", REPO / row["path"], row["disk"])
    for index, row in enumerate(selection["mandatory_original_raw"]):
        add(f"accepted_raw:{index}", Path(row["path"]), row)
    context = read(HERE / "context-custody.json")
    assert context["schema"] == "i04-var03-v101-context-custody/v2"
    assert len(context["records"]) == 181
    for index in (147, 148):
        row = context["records"][index]
        assert row["history_index"] == index
        assert row["disposition"] == "local_only_unrelated_app_context"
        add(f"local_only_context_original:{index}", Path(row["original_path"]), row)
    for index, (relative, wanted) in enumerate(selection["required_docs"].items()):
        path = REPO / relative
        if str(path.resolve(strict=True)).lower() not in paths:
            add(f"required_doc:{index}", path, wanted)
        else:
            exact(path, wanted)
    for name, wanted in selection["installed_refs"].items():
        add("installed:" + name, Path(wanted["path"]), wanted)
    helper = REPO / "cases/simlox-air-support/I03-var08-idle-at-maxut-out-v1.0.0/captured_process.ps1"
    expected_helper = {"bytes": 0, "sha256": "17285b90093c2d80c6241e1345b9926a2e4dd0f0b2b24f831c84c1cfa885b794"}
    expected_helper["bytes"] = (HERE / "captured_process.ps1").stat().st_size
    exact(HERE / "captured_process.ps1", expected_helper)
    add("accepted_capture_helper_ancestry", helper, expected_helper)
    return {"schema": SCHEMA, "run_id": RUN_ID, "base_commit": BASE,
            "contract_sha256": CONTRACT_SHA,
            "execution_binding_sha256": pin(HERE / "execution-contract.json")["sha256"],
            "source_count": len(records), "source_files": records,
            "live_catalog_prelaunch_pin": {
                "path": str((REPO / "cases/simlox-air-support/publication-index-v1.json").resolve(strict=True)),
                **selection["catalog_local"],
            },
            "historical_catalog_prefix_always_checked": 496,
            "accepted_source_git_pairs": 76, "accepted_raw_records": 114,
            "local_only_context_originals": 2,
            "accepted_nonclosure_raw": 100, "accepted_closure_records": 7,
            "accepted_invocation_records": 7,
            "new_native_runs_authorized_by_manifest": 0,
            "independent_method_state": "provisional" if provisional else "exact methods pinned; fresh approval required"}


def body(document):
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main():
    args = sys.argv[1:]
    assert args in ([], ["--dry"], ["--provisional"], ["--write"])
    provisional = args == ["--provisional"]
    mode = "live" if args in (["--write"], ["--provisional"]) else "sealed"
    data = body(candidate(provisional, mode))
    target = HERE / "prelaunch-manifest.json"
    if args == ["--write"]:
        assert not target.exists()
        with target.open("xb") as stream:
            stream.write(data)
    elif not args:
        assert target.read_bytes() == data
    print(json.dumps({"schema": "i04-var03-idle-between-manifest-check/v101",
                      "source_count": len(json.loads(data)["source_files"]),
                      "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args == ["--write"], "provisional": provisional,
                      "mode": mode}, sort_keys=True))


if __name__ == "__main__":
    main()
