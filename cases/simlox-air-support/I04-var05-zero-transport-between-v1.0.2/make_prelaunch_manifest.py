"""Deterministic exact prelaunch source map; root alone writes canonical bytes."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from make_source_inventory import HERE, body as inventory_body, candidate as inventory_candidate
from model_common import pin, read
from source_gate import ARCHIVE, BASE, REPO, RUN_ID, RUN_DIR, exact, verify

SCHEMA = "i04-var05-zero-between-prelaunch-manifest/v102"
CONTRACT_SHA = "2353d18f907803c9023089e70202e7381cad266a0b8c7795bf98586ee067f292"
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
    assert (check["accepted_current_disk_git_pairs"], check["old_v100_owned_sources"],
            check["old_v100_prelaunch_roles"], check["inherited_parent_manifest_roles"],
            check["inherited_parent_base_git_pairs"], check["mandatory_accepted_original_raw"],
            check["failed_v100_originals"], check["failed_v100_preflight_originals"],
            check["mandatory_failed_context_originals"], check["owned_failed_context_copies"],
            check["owned_extra_context_copies"], check["required_docs"], check["installed"]) == (
                403, 130, 1172, 456, 76, 168, 34, 18, 53, 78, 22, 8, 3)
    assert (check["excluded_v101_owned_sources"], check["excluded_v101_prelaunch_roles"],
            check["excluded_v101_failed_preflight_originals"],
            check["excluded_v101_pure_originals"], check["excluded_v101_root_and_copier_originals"]) == (172, 1980, 3, 21, 18)
    assert check["owned_v102_context_copies"] == 20
    selection = read(ARCHIVE / "selection.json.bytes")
    inherited = read(REPO / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.0/prelaunch-manifest.json")
    context = read(HERE / "context-custody.json")
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
            assert identities[identity] == got, (key, absolute, "duplicate path has different seal")
        identities[identity] = got
        records.append({"key": key, "path": str(absolute), **got})

    owned = inventory_candidate(provisional)
    for row in owned["source_files"]:
        add(ROLES.get(row["relative_path"], "owned:" + row["relative_path"]), Path(row["path"]), row)
    if not provisional:
        inventory_path = HERE / "source-inventory.json"
        assert inventory_path.read_bytes() == inventory_body(owned)
        add("owned_source_inventory", inventory_path)
    current = selection["parent_sources_and_catalog"]
    assert len(current) == 404 and current[-1]["path"] == "cases/simlox-air-support/publication-index-v1.json"
    for index, row in enumerate(current[:-1]):
        add(f"accepted_current_source:{index}", REPO / row["path"], row)
    for index, row in enumerate(inherited["source_files"]):
        add(f"inherited_parent_role:{index}", Path(row["path"]), row)
    for index, row in enumerate(selection["parent_mandatory_originals"]):
        add(f"accepted_raw:{index}", Path(row["path"]), row)
    for index, (relative, expected) in enumerate(selection["required_docs"].items()):
        add(f"required_doc:{index}", REPO / relative, expected)
    for name, expected in selection["installed_pins"].items():
        add(f"installed:{name}", Path(expected["path"]), expected)
    assert len(context["records"]) == 131
    host_only = [row for row in context["records"] if row["disposition"] == "mandatory_host_original_no_copy"]
    assert len(host_only) == 53
    for row in host_only:
        add(f"recovery_context_host_original:{row['index']}", Path(row["original_path"]), row)
    prior = read(HERE / "prospective-contract.json")["recovery_v101_method_order"]
    prior_case = REPO / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.1"
    add("excluded_v101_source_inventory", prior_case / "source-inventory.json", prior["inventory"])
    add("excluded_v101_prelaunch_manifest", prior_case / "prelaunch-manifest.json", prior["manifest"])
    assert len(prior["owned_sources"]) == 172 and len(prior["manifest_roles"]) == 1980
    for index, row in enumerate(prior["owned_sources"]):
        add(f"excluded_v101_owned:{index}", Path(row["path"]), row)
    for index, row in enumerate(prior["manifest_roles"]):
        add(f"excluded_v101_role:{index}", Path(row["path"]), row)
    for label, count in (("failed_independent_preflight_originals", 3),
                         ("pure_originals", 21), ("root_and_copier_originals", 18)):
        assert len(prior[label]) == count
        for index, row in enumerate(prior[label]):
            add(f"excluded_v101_{label}:{index}", Path(row["path"]), row)
    add("excluded_v101_independent_no_go", Path(prior["independent_no_go"]["path"]), prior["independent_no_go"])
    assert len(records) == len(keys)
    archive = current[-1]
    assert str(RUN_DIR) == read(HERE / "execution-contract.json")["native_run_directory"]
    if mode == "live":
        assert not RUN_DIR.exists()
    return {"schema": SCHEMA, "run_id": RUN_ID, "native_run_directory": str(RUN_DIR),
            "file_line_ascii_bytes": 121, "file_line_ascii_max": 199,
            "base_commit": BASE,
            "contract_sha256": CONTRACT_SHA,
            "execution_binding_sha256": pin(HERE / "execution-contract.json")["sha256"],
            "source_count": len(records), "source_files": records,
            "live_catalog_prelaunch_pin": {
                "path": str((REPO / archive["path"]).resolve(strict=True)),
                "bytes": archive["bytes"], "sha256": archive["sha256"]},
            "historical_catalog_prefix_always_checked": 497,
            "accepted_current_source_git_pairs": 403,
            "excluded_v100_owned_sources": 130,
            "excluded_v100_prelaunch_roles": 1172,
            "excluded_v101_owned_sources": 172,
            "excluded_v101_prelaunch_roles": 1980,
            "excluded_v101_failed_preflight_originals": 3,
            "excluded_v101_pure_originals": 21,
            "excluded_v101_root_and_copier_originals": 18,
            "inherited_parent_manifest_roles": 456,
            "inherited_parent_base_git_pairs": 76,
            "accepted_raw_records": 168,
            "excluded_failed_witness_originals": 34,
            "failed_preflight_originals": 18,
            "accepted_nonclosure_raw": 152, "accepted_closure_records": 8,
            "accepted_invocation_records": 8,
            "local_only_context_originals": 2,
            "mandatory_host_only_context_originals": 53,
            "owned_recovery_context_copies": 78,
            "owned_extra_context_copies": 22,
            "owned_v102_context_copies": 20,
            "new_native_runs_authorized_by_manifest": 0,
            "independent_method_state": "provisional" if provisional else "exact methods pinned; fresh approval required"}


def body(document):
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main():
    args = sys.argv[1:]
    external_candidate = len(args) == 2 and args[0] in ("--candidate", "--provisional-candidate")
    assert external_candidate or args in ([], ["--dry"], ["--provisional"], ["--write"])
    provisional = args == ["--provisional"] or (external_candidate and args[0] == "--provisional-candidate")
    mode = "live" if args in (["--write"], ["--provisional"]) or external_candidate else "sealed"
    data = body(candidate(provisional, mode))
    target = HERE / "prelaunch-manifest.json"
    if external_candidate:
        external = Path(args[1]).absolute()
        assert external.parent.is_dir() and not external.exists()
        assert external.is_relative_to(REPO / "tmp")
        with external.open("xb") as stream:
            stream.write(data)
    elif args == ["--write"]:
        assert not target.exists()
        with target.open("xb") as stream:
            stream.write(data)
    elif not args:
        assert target.read_bytes() == data
    print(json.dumps({"schema": "i04-var05-zero-between-manifest-check/v102",
                      "source_count": len(json.loads(data)["source_files"]),
                      "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args == ["--write"], "candidate_written": external_candidate,
                      "provisional": provisional,
                      "mode": mode}, sort_keys=True))


if __name__ == "__main__":
    main()
